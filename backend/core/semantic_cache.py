import logging
import asyncio
import numpy as np
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from sqlalchemy import select, func, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from backend.chatbot.models import PrecomputedQA
from backend.chatbot.token_buffer import tokenize_into_stream_tokens
from backend.core.config import settings
from backend.core.redis import cache_manager, normalize_query_key

logger = logging.getLogger("app.semantic_cache")


# ── Structured Schema for Dynamic LLM Generation ─────────────────────────────
class GeneratedFAQItem(BaseModel):
    question: str = Field(description="A natural, high-frequency question a diabetes patient or clinician would ask")
    answer: str = Field(description="Authoritative, detailed clinical answer strictly grounded in the medical guidelines")
    category: str = Field(description="Clinical topic category (e.g., Diagnostic Criteria, Acute Emergencies, Pharmacotherapy, Chronic Complications, Glycemic Targets)")
    source_title: str = Field(default="Clinical Diabetes Guidelines", description="Source guideline document or section title")


class GeneratedFAQBatch(BaseModel):
    faqs: List[GeneratedFAQItem] = Field(description="List of synthesized high-frequency clinical Q&A pairs")


# ── Core Clinical Focus Areas for Knowledge Base Sampling ─────────────────────
CLINICAL_KNOWLEDGE_TOPICS: List[str] = [
    "What is Type 1 and Type 2 diabetes, primary definitions, autoimmune etiology vs insulin resistance, and key differences",
    "Fasting plasma glucose, HbA1c, and Oral Glucose Tolerance Test (OGTT) diagnostic cutoffs and criteria for diabetes and prediabetes",
    "Hypoglycemia clinical classification, symptoms, Rule of 15 treatment protocol, and emergency glucagon management",
    "Diabetic Ketoacidosis (DKA) warning signs, symptoms, ketones in urine/blood, and emergency management",
    "First-line oral pharmacotherapy, Metformin mechanism of action, contraindications, and common side effects",
    "Insulin storage guidelines (refrigerated unopened vs room temperature opened vials), and GLP-1 receptor agonists and SGLT2 inhibitors",
    "Diabetic peripheral neuropathy daily foot care rules, diabetic retinopathy dilated eye exam frequency, and nephropathy albuminuria screening",
    "Standard glycemic target ranges before and after meals, and Continuous Glucose Monitoring (CGM) Time in Range (TIR) metrics",
    "Common early warning signs and symptoms of diabetes (excessive thirst, frequent urination, unexplained weight loss, fatigue)",
    "Prediabetes definition, fasting glucose and A1C ranges, and lifestyle reversibility with diet and exercise",
]


class SemanticCacheManager:
    """
    Manages in-memory and Redis-backed pre-computed semantic Q&A caching.
    
    1. Dynamic Generation: The LLM dynamically extracts and synthesizes Q&As from 
       the ChromaDB knowledge base when initialized or on-demand.
    2. One-Time Guard: Checks database count at startup. If records exist, skips LLM 
       generation and loads vectors into RAM in <5ms.
    3. Fast Inference: Vectorized numpy dot product matches queries in <0.2ms.
    """

    def __init__(self):
        self._items: List[Dict[str, Any]] = []
        self._normalized_matrix: Optional[np.ndarray] = None
        self._initialized: bool = False
        self._lock = asyncio.Lock()

    @property
    def is_ready(self) -> bool:
        return self._initialized and self._normalized_matrix is not None and len(self._items) > 0

    async def get_count(self, session: AsyncSession) -> int:
        """Returns the number of active pre-computed Q&A rows in PostgreSQL."""
        try:
            res = await session.execute(
                select(func.count(PrecomputedQA.id)).where(PrecomputedQA.is_active == True)
            )
            return int(res.scalar() or 0)
        except Exception as e:
            logger.warning("Error querying precomputed_qa count: %s", e)
            return 0

    async def generate_faqs_with_llm(
        self,
        session: AsyncSession,
        topics: Optional[List[str]] = None,
        questions_per_topic: int = 2,
    ) -> int:
        """
        Dynamically generates clinical FAQ pairs using the LLM grounded in ChromaDB knowledge base chunks.
        Saves the generated Q&As and their embeddings to PostgreSQL and primes Redis.
        Runs ONCE when the database table is empty or when explicitly triggered via admin CLI.
        """
        from backend.chatbot.hybrid_workflow import get_embedding_model, model
        from backend.chatbot.models import DocumentChunk
        from langchain_core.prompts import ChatPromptTemplate

        topics_to_query = topics or CLINICAL_KNOWLEDGE_TOPICS
        embedder = get_embedding_model()

        generation_prompt = ChatPromptTemplate.from_template(
            "You are a senior clinical endocrinologist and medical guidelines specialist.\n"
            "Based STRICTLY on the attached verified clinical guideline excerpts from the medical knowledge base:\n\n"
            "EXCERPTS:\n"
            "{context}\n\n"
            "Synthesize {count} high-frequency, practical clinical questions and authoritative answers "
            "that a diabetes patient or clinician commonly asks regarding this topic. "
            "Ensure you prioritize the foundational/core question for the topic (e.g., 'What is the difference between Type 1 and Type 2 diabetes?' or 'What are the criteria to diagnose diabetes?'). "
            "Formulate questions naturally and clearly. "
            "Answers must be comprehensive, medically accurate, and directly grounded in the provided excerpts.\n"
            "Respond using the provided structured schema."
        )

        structured_llm = model.with_structured_output(GeneratedFAQBatch)
        chain = generation_prompt | structured_llm

        all_generated_faqs: List[GeneratedFAQItem] = []

        logger.info("Starting dynamic LLM FAQ generation from knowledge base across %d topics...", len(topics_to_query))

        for topic in topics_to_query:
            try:
                # 1. Retrieve most relevant knowledge base chunks from PostgreSQL pgvector for this clinical topic
                topic_embedding = embedder.encode(topic).tolist()
                stmt = (
                    select(DocumentChunk.content, DocumentChunk.metadata_json)
                    .order_by(DocumentChunk.embedding.cosine_distance(topic_embedding))
                    .limit(3)
                )
                topic_res = await session.execute(stmt)
                topic_rows = topic_res.fetchall()

                documents = [r[0] for r in topic_rows]
                metadatas = [r[1] or {} for r in topic_rows]

                if not documents:
                    logger.warning("No knowledge base documents found for topic '%s'. Skipping.", topic[:40])
                    continue

                context_text = "\n\n---\n\n".join(documents)

                # 2. Invoke LLM to synthesize practical clinical Q&A pairs grounded in the excerpts
                batch = await chain.ainvoke({"context": context_text, "count": questions_per_topic})

                if batch and batch.faqs:
                    for faq in batch.faqs:
                        # Fallback source title from ChromaDB metadata if not populated by LLM
                        if not faq.source_title or faq.source_title == "Clinical Diabetes Guidelines":
                            if metadatas and metadatas[0].get("source"):
                                faq.source_title = metadatas[0].get("source")
                        all_generated_faqs.append(faq)
                    logger.info("LLM generated %d clinical FAQs for topic: '%s'", len(batch.faqs), topic[:40])

            except Exception as e:
                logger.error("Failed dynamic LLM generation for topic '%s': %s", topic[:40], e)

        if not all_generated_faqs:
            logger.error("No FAQs were generated by the LLM from the knowledge base.")
            return 0

        # 3. Batch embed all dynamically generated questions
        logger.info("Computing embeddings for %d dynamically generated questions...", len(all_generated_faqs))
        questions = [faq.question for faq in all_generated_faqs]
        embeddings = embedder.encode(questions, show_progress_bar=False, batch_size=32)

        # 4. Insert into PostgreSQL and prime Redis
        saved_count = 0
        for faq, emb in zip(all_generated_faqs, embeddings):
            # Check for duplicate question text to prevent unique constraint violation
            existing = await session.execute(
                select(PrecomputedQA.id).where(PrecomputedQA.question == faq.question)
            )
            if existing.scalar() is not None:
                continue

            sources_payload = [{"title": faq.source_title, "section": faq.category}]
            qa_row = PrecomputedQA(
                question=faq.question,
                answer=faq.answer,
                category=faq.category,
                sources=sources_payload,
                embedding=emb.tolist(),
                is_active=True,
            )
            session.add(qa_row)
            saved_count += 1

            # Prime Redis precomputed key (TTL: 30 days) with pre-tokenized buffer
            tokens_payload = tokenize_into_stream_tokens(faq.answer)
            q_key = normalize_query_key(faq.question, prefix="rag:precomputed:qa")
            await cache_manager.set_json(
                q_key,
                {
                    "question": faq.question,
                    "answer": faq.answer,
                    "tokens": tokens_payload,
                    "category": faq.category,
                    "sources": sources_payload,
                },
                expire_seconds=2592000,
            )

        await session.commit()
        logger.info("Successfully persisted %d dynamically generated FAQs to PostgreSQL & Redis.", saved_count)
        return saved_count

    async def seed_if_empty(self, session: AsyncSession) -> int:
        """
        One-time generation guard:
        If precomputed_qa already contains records, SKIPS GENERATION completely!
        If empty, triggers dynamic LLM generation grounded in ChromaDB knowledge base chunks.
        """
        async with self._lock:
            count = await self.get_count(session)
            if count > 0:
                logger.info(
                    "Precomputed QA table already contains %d entries. Skipping dynamic LLM generation (cached in DB).",
                    count,
                )
                return count

            logger.info("Precomputed QA table is empty. Triggering one-time dynamic LLM generation from knowledge base...")
            generated = await self.generate_faqs_with_llm(session)
            return generated

    async def load_index(self, session: Optional[AsyncSession] = None, force: bool = False) -> None:
        """
        Loads all active precomputed records and vectors from the database into RAM.
        Pre-computes row-normalized matrix for sub-millisecond cosine similarity search.
        Idempotent: skips if already loaded unless force=True.
        """
        async with self._lock:
            if self._initialized and not force and len(self._items) > 0:
                return

            try:
                if session is not None:
                    res = await session.execute(
                        select(PrecomputedQA).where(PrecomputedQA.is_active == True)
                    )
                    rows = res.scalars().all()
                else:
                    from backend.core.database import AsyncSessionLocal
                    async with AsyncSessionLocal() as sess:
                        res = await sess.execute(
                            select(PrecomputedQA).where(PrecomputedQA.is_active == True)
                        )
                        rows = res.scalars().all()

                if not rows:
                    logger.warning("No precomputed QA records found in database to load into semantic cache.")
                    self._items = []
                    self._normalized_matrix = None
                    self._initialized = True
                    return

                items = []
                vectors = []
                for row in rows:
                    items.append({
                        "id": row.id,
                        "question": row.question,
                        "normalized_question": " ".join(row.question.lower().strip().split()),
                        "answer": row.answer,
                        "tokens": tokenize_into_stream_tokens(row.answer),
                        "category": row.category,
                        "sources": row.sources or [],
                        "hit_count": row.hit_count,
                        "updated_at": row.updated_at.timestamp() if row.updated_at else (row.created_at.timestamp() if row.created_at else 0.0),
                    })
                    vectors.append(row.embedding)

                matrix = np.array(vectors, dtype=np.float32)
                # Compute L2 norms along axis 1
                norms = np.linalg.norm(matrix, axis=1, keepdims=True)
                norms[norms == 0] = 1.0  # Avoid division by zero
                normalized_matrix = matrix / norms

                self._items = items
                self._normalized_matrix = normalized_matrix
                self._initialized = True
                logger.info("Loaded %d precomputed Q&A vectors into in-memory semantic cache matrix.", len(items))
            except Exception as e:
                logger.error("Failed to load semantic cache index: %s", e, exc_info=True)
                self._initialized = False

    async def find_match(
        self,
        query: str,
        query_embedding: Optional[List[float]] = None,
        threshold: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Performs vectorized cosine similarity search of the query against precomputed Q&As.
        Prioritizes:
          1. Exact String Match (normalized whitespace & case) -> instant 1.0 score.
          2. High Vector Cosine Similarity with Recency Boost for competitive candidates.
        Returns the best match if cosine similarity >= threshold, else None.
        """
        if not self.is_ready or self._normalized_matrix is None or not self._items:
            return None

        sim_threshold = threshold if threshold is not None else settings.SEMANTIC_CACHE_THRESHOLD

        try:
            # Check fast query-hash cache in Redis first
            sem_cache_key = normalize_query_key(query, prefix="rag:semantic_match")
            cached_match = await cache_manager.get_json(sem_cache_key)
            if cached_match and isinstance(cached_match, dict) and cached_match.get("answer"):
                logger.info("Semantic cache fast-path hit in Redis for query: '%s'", query[:40])
                return cached_match

            norm_query = " ".join(query.lower().strip().split())

            # ── 1. EXACT STRING MATCH PRIORITY ──
            # If the user asked an exact question already present in cache, it wins with 1.0 similarity immediately.
            # If multiple records have the exact question, recency breaks any tie.
            exact_candidates = [
                (idx, item) for idx, item in enumerate(self._items)
                if item.get("normalized_question") == norm_query
            ]
            if exact_candidates:
                best_idx, match_item = max(exact_candidates, key=lambda x: x[1].get("updated_at", 0.0))
                best_score = 1.0
                match_item["hit_count"] = match_item.get("hit_count", 0) + 1
                result = {
                    "id": match_item["id"],
                    "canonical_question": match_item["question"],
                    "answer": match_item["answer"],
                    "tokens": match_item.get("tokens") or tokenize_into_stream_tokens(match_item["answer"]),
                    "category": match_item["category"],
                    "sources": match_item["sources"],
                    "similarity": 1.0,
                    "model": "precomputed-semantic-cache",
                }
                logger.info(
                    "Semantic Cache EXACT MATCH HIT (sim=1.000): '%s' -> '%s' [id=%s]",
                    query[:40],
                    match_item["question"][:40],
                    match_item["id"],
                )
                await cache_manager.set_json(sem_cache_key, result, expire_seconds=604800)
                return result

            # ── 2. VECTOR SEARCH WITH RECENCY BOOST ──
            # Obtain query embedding
            if query_embedding is None:
                from backend.chatbot.hybrid_workflow import get_embedding_model
                model = get_embedding_model()
                q_vec = model.encode(query, show_progress_bar=False)
            else:
                q_vec = np.array(query_embedding, dtype=np.float32)

            q_norm = np.linalg.norm(q_vec)
            if q_norm == 0:
                return None
            normalized_q = (q_vec / q_norm).astype(np.float32)

            # Vectorized dot product across all precomputed Q&As (runs in < 0.2ms)
            similarities = np.dot(self._normalized_matrix, normalized_q)

            # Find all candidate indices meeting minimum similarity threshold
            candidate_indices = np.where(similarities >= sim_threshold)[0]
            if len(candidate_indices) == 0:
                best_score = float(np.max(similarities)) if len(similarities) > 0 else 0.0
                logger.debug(
                    "Semantic Cache Miss (sim=%.3f < %.2f) for query: '%s'",
                    best_score,
                    sim_threshold,
                    query[:40],
                )
                return None

            # For candidates meeting threshold, apply recency boost to rank competitive matches:
            # When candidates are within a competitive window (within 0.04 of max similarity),
            # the more recently created or updated answer takes precedence!
            max_sim = float(np.max(similarities[candidate_indices]))
            competitive_indices = [
                idx for idx in candidate_indices
                if similarities[idx] >= (max_sim - 0.04)
            ]

            # Rank competitive candidates by updated_at descending, then raw similarity
            best_idx = max(
                competitive_indices,
                key=lambda idx: (self._items[idx].get("updated_at", 0.0), similarities[idx])
            )
            best_score = float(similarities[best_idx])

            match_item = self._items[best_idx]
            match_item["hit_count"] = match_item.get("hit_count", 0) + 1
            result = {
                "id": match_item["id"],
                "canonical_question": match_item["question"],
                "answer": match_item["answer"],
                "tokens": match_item.get("tokens") or tokenize_into_stream_tokens(match_item["answer"]),
                "category": match_item["category"],
                "sources": match_item["sources"],
                "similarity": round(best_score, 4),
                "model": "precomputed-semantic-cache",
            }
            logger.info(
                "Semantic Cache HIT (sim=%.3f >= %.2f, recency_boosted): '%s' -> '%s' [id=%s]",
                best_score,
                sim_threshold,
                query[:40],
                match_item["question"][:40],
                match_item["id"],
            )

            # Store match in Redis for repeat requests (TTL: 7 days)
            await cache_manager.set_json(sem_cache_key, result, expire_seconds=604800)
            return result
        except Exception as e:
            logger.warning("Error in semantic cache lookup: %s; falling back to retriever", e)
            return None


semantic_cache_manager = SemanticCacheManager()
