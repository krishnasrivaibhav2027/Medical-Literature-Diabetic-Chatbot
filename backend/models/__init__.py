# Import all ORM models here so SQLAlchemy's Base.metadata is fully populated
# before create_tables() is called in main.py.
from backend.users.models import User  # noqa: F401
from backend.chatbot.models import ChatThread, ChatMessage, PrecomputedQA  # noqa: F401
