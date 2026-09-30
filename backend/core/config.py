from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"

class Settings(BaseSettings):
    APP_NAME: str
    APP_VERSION: str
    ENVIRONMENT: str
    DEBUG: bool
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    ALLOWED_ORIGINS: List[str]
    XKIRO_API_KEY: str
    NVIDIA_API_KEY: str
    UPSTASH_REDIS_REST_URL: str
    UPSTASH_REDIS_REST_TOKEN: str
    SEMANTIC_CACHE_THRESHOLD: float = 0.70
    SEMANTIC_CACHE_DIRECT_THRESHOLD: float = 0.80
    JINA_API_KEY: str
    JINA_RERANKER_MODEL: str
    JINA_URL: str
    HUGGING_FACE_TOKEN: Optional[str] = None
    HF_TOKEN: Optional[str] = None
    LANGCHAIN_TRACING_V2: bool = False
    LANGCHAIN_API_KEY: Optional[str] = None
    LANGCHAIN_PROJECT: str = "hybrid-rag-production"
    LANGCHAIN_ENDPOINT: str = "https://api.smith.langchain.com"
    LOG_LEVEL: str = "INFO"
    JINA_EMBEDDING_MODEL: str
    JINA_EMBEDDING_URL: str
    model_config = SettingsConfigDict(
        env_file = _ENV_FILE,
        env_file_encoding = "utf-8",
        extra = "ignore"
    )

settings = Settings()