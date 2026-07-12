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
    google_use_vertexai: bool
    google_cloud_project: str | None
    google_cloud_location: str
    ollama_timeout_seconds: int
    vision_model_name: str


def get_settings() -> Settings:
    """Load application settings from environment variables."""
    load_dotenv()
    return Settings(
        app_mode=os.getenv("APP_MODE", "mock").lower(),
        gemma_api_key=os.getenv("GEMMA_API_KEY"),
        gemma_model_name=os.getenv("GEMMA_MODEL_NAME", "gemma4:e4b"),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        google_model_name=os.getenv("GOOGLE_MODEL_NAME", "gemini-3.5-flash"),
        google_use_vertexai=os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "false").lower() in {"1", "true", "yes"},
        google_cloud_project=os.getenv("GOOGLE_CLOUD_PROJECT"),
        google_cloud_location=os.getenv("GOOGLE_CLOUD_LOCATION", "global"),
        ollama_timeout_seconds=int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "300")),
        # Separate model for photo analysis; defaults to the main model.
        vision_model_name=os.getenv("VISION_MODEL_NAME", os.getenv("GEMMA_MODEL_NAME", "gemma4:e4b")),
    )
