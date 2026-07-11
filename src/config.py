from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    app_mode: str
    gemma_api_key: str | None
    gemma_model_name: str
    ollama_base_url: str
    google_api_key: str | None
    google_model_name: str


def get_settings() -> Settings:
    """Load application settings from environment variables."""
    load_dotenv()
    return Settings(
        app_mode=os.getenv("APP_MODE", "mock").lower(),
        gemma_api_key=os.getenv("GEMMA_API_KEY"),
        gemma_model_name=os.getenv("GEMMA_MODEL_NAME", "gemma4:e4b"),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        google_model_name=os.getenv("GOOGLE_MODEL_NAME", "gemini-2.0-flash"),
    )
