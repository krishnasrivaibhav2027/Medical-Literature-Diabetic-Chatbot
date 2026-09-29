from langchain_text_splitters import RecursiveCharacterTextSplitter
from backend.ingestion_pipeline.extraction import extract_pdf

text_splitter = RecursiveCharacterTextSplitter(
    separators = [
        "\n\n",
        "\n",
        " ",
        ""
    ],
    chunk_size=1000,
    chunk_overlap = 200,
    length_function=len
)


def process_pdf(pdf_path):
    text_docs, table_docs = extract_pdf(pdf_path)
    
    print(f"Extracted {len(text_docs)} Text and {len(table_docs)} Tables.")

    text_chunks = text_splitter.split_documents(text_docs)

    print(f"Text chunks after splitting: {len(text_chunks)}")

    final_docs = text_chunks + table_docs

    print(f"Final documents: {len(final_docs)}")

    return final_docs