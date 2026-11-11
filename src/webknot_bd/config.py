"""Runtime settings for the Webknot BD agent."""

from __future__ import annotations

import logging
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]

logger = logging.getLogger("webknot_bd")


class Settings(BaseSettings):
    """Environment-backed settings. Defaults keep the app runnable without Ollama."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ollama_model: str = "llama3"
    ollama_embed_model: str = "nomic-embed-text"
    ollama_base_url: str = "http://127.0.0.1:11434"
    chroma_dir: Path = PROJECT_ROOT / "chroma"
    crm_path: Path = PROJECT_ROOT / "data" / "crm.sqlite"
    data_raw: Path = PROJECT_ROOT / "data" / "raw"
    rerank: bool = False
    use_llm: bool = False
    tavily_api_key: str = ""
    top_k: int = 4
    web_chunk_size: int = 800
    web_chunk_overlap: int = 150
    doc_chunk_size: int = 1000
    doc_chunk_overlap: int = 0

    @field_validator("chroma_dir", "crm_path", "data_raw", mode="before")
    @classmethod
    def _resolve_path(cls, value: str | Path) -> Path:
        path = Path(value)
        if not path.is_absolute():
            return PROJECT_ROOT / path
        return path


settings = Settings()


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
