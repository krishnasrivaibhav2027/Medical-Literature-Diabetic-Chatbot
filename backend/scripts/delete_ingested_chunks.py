"""
backend/scripts/delete_ingested_chunks.py
Purge all existing document chunks from Supabase PostgreSQL.
Usage:
    python -m backend.scripts.delete_ingested_chunks
"""
import sys
import asyncio
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
project_root = backend_dir.parent
for p in (str(project_root), str(backend_dir)):
    if p not in sys.path:
        sys.path.insert(0, p)

from sqlalchemy import text
from backend.core.database import engine


async def main():
    print("Connecting to Supabase PostgreSQL...")
    async with engine.begin() as conn:
        res = await conn.execute(text("SELECT count(*) FROM document_chunks"))
        current_count = res.scalar()
        print(f"Current document_chunks in Supabase: {current_count}")

        if current_count > 0:
            print("Purging table 'document_chunks'...")
            await conn.execute(text("TRUNCATE TABLE document_chunks;"))
            print("Successfully truncated document_chunks!")
        else:
            print("Table is already empty.")

        res_check = await conn.execute(text("SELECT count(*) FROM document_chunks"))
        print(f"Post-purge document_chunks count: {res_check.scalar()}")

    await engine.dispose()
    print("Database connection closed.")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
