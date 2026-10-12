from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    database_url: str = (
        "postgresql+psycopg2://postgres:postgres@localhost:5432/knowledge_assistant"
    )

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    llm_model: str = "llama3.2"
    embedding_model: str = "nomic-embed-text"
    llm_temperature: float = 0.2

    # Storage
    upload_dir: Path = BASE_DIR / "data" / "uploads"
    index_dir: Path = BASE_DIR / "data" / "faiss_index"
    max_upload_mb: int = 25

    # RAG
    chunk_size: int = 1000
    chunk_overlap: int = 200
    top_k: int = 5
    history_messages: int = 6  # previous messages sent to the LLM for context

    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
