"""
CLI Administration Script for Pre-computed Semantic Q&A Cache.
Usage:
    python -m backend.scripts.seed_precomputed_qa [--force] [--status]
"""
import sys
import asyncio
import argparse
import logging

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from sqlalchemy import select, delete, func
from backend.core.database import AsyncSessionLocal, engine, Base
from backend.chatbot.models import PrecomputedQA
from backend.core.semantic_cache import semantic_cache_manager
from backend.chatbot.hybrid_workflow import get_embedding_model

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed_precomputed_qa")


async def show_status():
    async with AsyncSessionLocal() as session:
        count = await semantic_cache_manager.get_count(session)
        print(f"\n[Semantic Cache Status] Total Active Precomputed Q&As: {count}")
        if count > 0:
            res = await session.execute(
                select(PrecomputedQA.id, PrecomputedQA.question, PrecomputedQA.category, PrecomputedQA.hit_count)
                .where(PrecomputedQA.is_active == True)
                .order_by(PrecomputedQA.id)
            )
            rows = res.all()
            print("\nID  | Hits | Category                    | Question")
            print("----+------+-----------------------------+---------------------------------------------------")
            for r in rows:
                print(f"{r.id:<3} | {r.hit_count:<4} | {r.category:<27} | {r.question[:50]}")
            print()


async def seed(force: bool = False):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        if force:
            logger.info("Force flag detected. Clearing existing precomputed_qa rows...")
            await session.execute(delete(PrecomputedQA))
            await session.commit()
            logger.info("Cleared existing records.")

        count = await semantic_cache_manager.get_count(session)
        if count > 0 and not force:
            logger.info("Table already seeded with %d records. Use --force to re-generate.", count)
            return

        logger.info("Starting one-time clinical Q&A generation and embedding...")
        seeded = await semantic_cache_manager.seed_if_empty(session)
        logger.info("Seeding complete. Total rows in database: %d", seeded)

        logger.info("Loading in-memory vector index...")
        await semantic_cache_manager.load_index(session)
        logger.info("Index loaded. Semantic Cache is ready for sub-millisecond inference.")


def main():
    parser = argparse.ArgumentParser(description="Seed or manage Pre-computed Semantic Q&A Cache")
    parser.add_argument("--force", action="store_true", help="Force re-generation and re-seeding even if table is not empty")
    parser.add_argument("--status", action="store_true", help="Show current precomputed Q&A count and records")
    args = parser.parse_args()

    if args.status:
        asyncio.run(show_status())
    else:
        asyncio.run(seed(force=args.force))


if __name__ == "__main__":
    main()
