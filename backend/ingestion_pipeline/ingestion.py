import sys
import asyncio
from pathlib import Path
from typing import List, Tuple
import numpy as np
from sentence_transformers import SentenceTransformer
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import select, func

backend_dir = Path(__file__).resolve().parent.parent
project_root = backend_dir.parent
for path in (str(project_root), str(backend_dir)):
    if path not in sys.path:
        sys.path.insert(0, path)

from backend.ingestion_pipeline.text_splitting import process_pdf
from backend.core.database import AsyncSessionLocal, create_tables
from backend.chatbot.models import DocumentChunk
from backend.chatbot.bm25 import invalidate_bm25_cache

KNOWLEDGE_BASE_DIR = Path.joinpath(Path(__file__).parent.parent, "knowledge_base")

embedding_model = SentenceTransformer("google/embeddinggemma-300m")


def ingest_knowledge_base(knowledge_base_dir = KNOWLEDGE_BASE_DIR):
    kb_path = Path(knowledge_base_dir)
    pdf_files = sorted(kb_path.glob("*.pdf"))

    print(f"Found {len(pdf_files)} PDFs in {kb_path.name}")

    all_docs = []
    all_embeddings = []

    for i, pdf_path in enumerate(pdf_files, start=1):
        print(f"\n[{i}/{len(pdf_files)}] Processing: {pdf_path.name}")
        try:
            docs = process_pdf(str(pdf_path))
            texts = [doc.page_content for doc in docs]
            print(f"\nCreating Embeddings for the chunked documents for doc {i}...")
            embeddings = embedding_model.encode(texts, show_progress_bar=True, batch_size=32)
            all_docs.extend(docs)
            all_embeddings.append(embeddings)

            print(f"  {len(docs)} chunks, {embeddings.shape[1]}d embeddings")
        except Exception as e:
            print(f"  Failed to process {pdf_path.name}: {e}")
            continue
    print("\nAll Embeddings created successfully!\n")

    if all_embeddings:
        all_embeddings = np.vstack(all_embeddings)

    print(f"Total documents: {len(all_docs)}")
    print(f"Total embeddings: {all_embeddings.shape}")

    return all_docs, all_embeddings


async def save_chunks_to_postgres(docs, embeddings):
    """Save extracted document chunks and embeddings into PostgreSQL document_chunks table."""
    await create_tables()

    batch_size = 150
    total = len(docs)
    inserted = 0

    print(f"Saving {total} embeddings to PostgreSQL pgvector (document_chunks table)...")

    async with AsyncSessionLocal() as session:
        for i in range(0, total, batch_size):
            batch_docs = docs[i : i + batch_size]
            batch_embeds = embeddings[i : i + batch_size]

            rows_to_insert = []
            for j, (doc, embed) in enumerate(zip(batch_docs, batch_embeds)):
                idx = i + j
                meta = dict(doc.metadata) if doc.metadata else {}
                doc_id = f"{meta.get('source', 'doc')}_p{meta.get('page', 0)}_{meta.get('content_type', 'chunk')}_{idx}"
                page = meta.get("page")
                if page is not None:
                    try:
                        page = int(page)
                    except (ValueError, TypeError):
                        page = None

                rows_to_insert.append({
                    "id": doc_id,
                    "content": doc.page_content,
                    "source": str(meta.get("source", "knowledge_base")),
                    "page": page,
                    "content_type": str(meta.get("content_type", "text")),
                    "char_length": len(doc.page_content),
                    "metadata_json": meta,
                    "embedding": embed.tolist() if hasattr(embed, "tolist") else list(embed),
                })

            stmt = pg_insert(DocumentChunk).values(rows_to_insert)
            stmt = stmt.on_conflict_do_update(
                index_elements=[DocumentChunk.id],
                set_={
                    "content": stmt.excluded.content,
                    "source": stmt.excluded.source,
                    "page": stmt.excluded.page,
                    "content_type": stmt.excluded.content_type,
                    "char_length": stmt.excluded.char_length,
                    "metadata_json": stmt.excluded.metadata_json,
                    "embedding": stmt.excluded.embedding,
                },
            )
            await session.execute(stmt)
            await session.commit()
            inserted += len(rows_to_insert)
            print(f"  Saved {inserted}/{total} chunks...")

        count_res = await session.execute(select(func.count(DocumentChunk.id)))
        total_in_db = count_res.scalar()

    # Invalidate BM25 cache so next queries include the new corpus
    invalidate_bm25_cache()
    print(f"\nSuccessfully saved to PostgreSQL document_chunks table!")
    print(f"Total chunks in database: {total_in_db}")


if __name__ == "__main__":
    print("Starting ingestion pipeline...")
    docs, embeddings = ingest_knowledge_base()
    if len(docs) == 0:
        print("No documents ingested. Exiting.")
        sys.exit(0)

    asyncio.run(save_chunks_to_postgres(docs, embeddings))