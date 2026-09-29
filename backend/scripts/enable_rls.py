"""
PostgreSQL Row-Level Security (RLS) Setup Script
================================================
Enables Row-Level Security on sensitive user tables (chat_threads and chat_messages).
This guarantees database-level isolation so that even raw SQL queries cannot leak 
cross-tenant medical conversations.
"""

import asyncio
import logging
from sqlalchemy import text
from backend.core.database import engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("enable_rls")

RLS_SQL_STATEMENTS = [
    # 1. Enable RLS on chat_threads
    "ALTER TABLE chat_threads ENABLE ROW LEVEL SECURITY;",
    
    # 2. Enable RLS on chat_messages
    "ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;",
    
    # 3. Drop existing policies if any
    "DROP POLICY IF EXISTS chat_threads_user_isolation ON chat_threads;",
    "DROP POLICY IF EXISTS chat_messages_user_isolation ON chat_messages;",
    
    # 4. Create RLS Policy for chat_threads:
    # Users can only select/insert/update/delete rows matching app.current_user_id
    """
    CREATE POLICY chat_threads_user_isolation ON chat_threads
        FOR ALL
        USING (
            user_id = NULLIF(current_setting('app.current_user_id', true), '')::integer
            OR current_setting('app.is_admin', true) = 'true'
        )
        WITH CHECK (
            user_id = NULLIF(current_setting('app.current_user_id', true), '')::integer
            OR current_setting('app.is_admin', true) = 'true'
        );
    """,
    
    # 5. Create RLS Policy for chat_messages:
    # Messages can only be accessed if their parent thread belongs to app.current_user_id
    """
    CREATE POLICY chat_messages_user_isolation ON chat_messages
        FOR ALL
        USING (
            thread_id IN (
                SELECT id FROM chat_threads 
                WHERE user_id = NULLIF(current_setting('app.current_user_id', true), '')::integer
            )
            OR current_setting('app.is_admin', true) = 'true'
        )
        WITH CHECK (
            thread_id IN (
                SELECT id FROM chat_threads 
                WHERE user_id = NULLIF(current_setting('app.current_user_id', true), '')::integer
            )
            OR current_setting('app.is_admin', true) = 'true'
        );
    """
]

async def apply_rls():
    logger.info("Connecting to PostgreSQL to apply Row-Level Security (RLS)...")
    try:
        async with engine.begin() as conn:
            for stmt in RLS_SQL_STATEMENTS:
                clean_stmt = stmt.strip()
                if clean_stmt:
                    logger.info("Executing: %s", clean_stmt.splitlines()[0])
                    await conn.execute(text(clean_stmt))
        logger.info("Successfully applied PostgreSQL Row-Level Security (RLS) on chat_threads and chat_messages!")
    except Exception as e:
        logger.error("Failed to enable RLS: %s", e)
        raise

if __name__ == "__main__":
    asyncio.run(apply_rls())
