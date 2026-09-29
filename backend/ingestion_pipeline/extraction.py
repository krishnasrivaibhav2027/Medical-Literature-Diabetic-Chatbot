import fitz
import pdfplumber
from pathlib import Path
from langchain_core.documents import Document

def extract_pdf(pdf_path: str):
    pdf_path = Path(pdf_path)

    pymupdf_doc = fitz.open(pdf_path)
    pdfplumber_doc = pdfplumber.open(pdf_path)

    text_docs = []
    table_docs = []

    try:
        print(f"\nExtracting {len(pymupdf_doc)} pages from {pdf_path.name}...")
        for page_index, (pymupdf_page, pdfplumber_page) in enumerate(zip(pymupdf_doc, pdfplumber_doc.pages), start = 1):
            
            text = pymupdf_page.get_text("text")

            if text:
                text_docs.append(
                    Document(
                        page_content = text,
                        metadata = {
                            "source" : pdf_path.name,
                            "page" : page_index,
                            "content_type": "text"
                        }
                    )
                )
            

            tables = pdfplumber_page.extract_tables()

            for table_index, table in enumerate(tables, start = 1):
                cleaned_table = [
                    row for row in table if row and any(cell and str(cell).strip() for cell in row)
                ]
                if cleaned_table:
                    markdown_table = table_to_markdown(cleaned_table)
                    if markdown_table:
                        table_docs.append(
                            Document(
                                page_content = markdown_table,
                                metadata = {
                                    "source" : pdf_path.name,
                                    "page" : page_index,
                                    "table_number": table_index,
                                    "content_type": "table"
                                }
                            )
                        )
    finally:
        pymupdf_doc.close()
        pdfplumber_doc.close()
    
    print(f"  Extracted {len(text_docs)} Text and {len(table_docs)} Tables.")
    return text_docs, table_docs

def table_to_markdown(table):
    if not table: return ""

    cleaned = []

    for row in table:
        cleaned_row = [
            str(cell).strip().replace("\n", " ").replace("|", "\\|") if cell is not None else ""
            for cell in row
        ]
        if any(cleaned_row):
            cleaned.append(cleaned_row)
        
    if not cleaned:
        return ""

    header = cleaned[0]
    n_cols = len(header)
    if n_cols == 0:
        return ""

    normalized_rows = []
    for row in cleaned[1:]:
        row = row[:n_cols]
        while len(row) < n_cols:
            row.append("")
        normalized_rows.append(row)
    
    markdown = "| " + " | ".join(header) + " |\n"
    markdown += "| " + " | ".join(
        ["---"] * n_cols
    ) + " |\n"
    for row in normalized_rows:
        markdown += "| " + " | ".join(row) + " |\n"

    return markdown