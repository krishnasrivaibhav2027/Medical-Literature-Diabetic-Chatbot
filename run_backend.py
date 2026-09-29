"""
Backend Server Runner
=====================
Sets WindowsSelectorEventLoopPolicy on Windows before initializing Uvicorn.
This ensures psycopg (used by LangGraph PostgreSQL checkpointer) runs in async mode without ProactorEventLoop conflicts.
"""
import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        loop="asyncio",
    )
