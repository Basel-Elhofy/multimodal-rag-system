"""Application configuration."""
from pydantic_settings import BaseSettings
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    APP_NAME: str = "Multimodal RAG System"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8001

    # Storage
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    DATA_DIR: Path = BASE_DIR / "data"
    VECTOR_DB_PATH: Path = BASE_DIR / "data" / "chroma_db"

    # Embedding - CLIP for multimodal (text + image)
    EMBEDDING_MODEL: str = "sentence-transformers/clip-ViT-B-32"
    EMBEDDING_DIMENSION: int = 512

    # Chunking
    CHUNK_SIZE: int = 1024
    CHUNK_OVERLAP: int = 200

    # Search
    TOP_K: int = 8
    SIMILARITY_THRESHOLD: float = 0.2

    # LLM - LongCat via OpenCode API
    LLM_MODEL: str = "opencode/longcat-2.5-preview-free"
    OPENAI_API_KEY: str = ""
    MAX_TOKENS: int = 2048
    TEMPERATURE: float = 0.7

    # OCR
    TESSERACT_CMD: str = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    OCR_LANG: str = "eng"

    # Database
    DATABASE_URL: str = f"sqlite+aiosqlite:///{BASE_DIR / 'data' / 'rag.db'}"

    class Config:
        env_file = ".env"


settings = Settings()
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
settings.VECTOR_DB_PATH.mkdir(parents=True, exist_ok=True)
