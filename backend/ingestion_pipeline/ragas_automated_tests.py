from pathlib import Path
from langchain_community.document_loaders import DirectoryLoader, PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from ragas.testset import TestsetGenerator
from ragas.run_config import RunConfig
from langchain_openai import ChatOpenAI 
from backend.core.config import settings
from ragas.testset.synthesizers.single_hop.specific import SingleHopSpecificQuerySynthesizer
from ragas.testset.synthesizers.multi_hop import (
    MultiHopAbstractQuerySynthesizer,
    MultiHopSpecificQuerySynthesizer,
)
from sentence_transformers import SentenceTransformer

XKIRO_BASE_URL = "https://api.xkiro.com/v1"
KNOWLEDGE_BASE_DIR = str(Path(__file__).resolve().parent.parent / "knowledge_base")

embedding_model = SentenceTransformer("google/embeddinggemma-300m")


loader = DirectoryLoader(KNOWLEDGE_BASE_DIR, glob="*.pdf", loader_cls=PyPDFLoader)
raw_docs = loader.load()
print(f"Loaded {len(raw_docs)} raw document pages from knowledge base")

text_splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=200)
docs = text_splitter.split_documents(raw_docs)
print(f"Split into {len(docs)} chunks")

generator_llm = ChatOpenAI(
  model="nvidia/nemotron-3-ultra-550b-a55b",
  base_url = "https://integrate.api.nvidia.com/v1",
  api_key = settings.NVIDIA_API_KEY,
  temperature=0.2,
)

critic_llm = ChatOpenAI(
    model="qwen/qwen3.6-max-preview:free",
    api_key=settings.XKIRO_API_KEY,
    base_url=XKIRO_BASE_URL,
    temperature=0.2,
)

distributions = [
    (SingleHopSpecificQuerySynthesizer(llm=generator_llm), 0.4),   
    (MultiHopAbstractQuerySynthesizer(llm=generator_llm), 0.3),   
    (MultiHopSpecificQuerySynthesizer(llm=generator_llm), 0.3),
]

generator = TestsetGenerator.from_langchain(
    generator_llm,
    critic_llm,
    embedding_model
)

run_config = RunConfig(
    max_workers=4,       # throttle concurrency to avoid rate-limit 502/504s
    max_wait=180,        # wait up to 3 min on retries
    max_retries=10,      # retry transient errors aggressively
)

testset = generator.generate_with_langchain_docs(
    documents=docs,
    testset_size=100,
    query_distribution=distributions,
    run_config=run_config,
)

df = testset.to_pandas()
print(f"\nGenerated {len(df)} test questions")
print(f"Columns: {list(df.columns)}")
print("\n--- Sample Questions ---")
print(df[["question", "ground_truth"]].head(10).to_string())

output_path = Path(__file__).resolve().parent / "testset.csv"
df.to_csv(output_path, index=False)
print(f"\nTestset saved to: {output_path}")