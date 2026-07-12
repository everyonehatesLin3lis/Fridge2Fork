from __future__ import annotations

import pytest

from src.services.gemma_client import GemmaClient


@pytest.fixture(autouse=True)
def _google_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_MODE", "google")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)


def test_google_mode_requires_api_key() -> None:
    with pytest.raises(RuntimeError, match="GOOGLE_API_KEY"):
        GemmaClient().generate_text("hello")


def test_google_mode_uses_current_stable_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GOOGLE_MODEL_NAME", raising=False)

    assert GemmaClient().settings.google_model_name == "gemini-3.5-flash"


def test_google_mode_wraps_provider_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    from google import genai

    monkeypatch.setenv("GOOGLE_API_KEY", "not-a-real-key")

    class _BoomModels:
        def generate_content(self, **_kwargs: object) -> None:
            raise ValueError("simulated transport failure")

    class _FakeClient:
        def __init__(self, **_kwargs: object) -> None:
            self.models = _BoomModels()

    monkeypatch.setattr(genai, "Client", _FakeClient)

    with pytest.raises(RuntimeError, match="Google AI \\(Gemini\\) request failed"):
        GemmaClient().generate_text("hello")


def test_google_mode_returns_response_text(monkeypatch: pytest.MonkeyPatch) -> None:
    from google import genai

    monkeypatch.setenv("GOOGLE_API_KEY", "not-a-real-key")

    class _FakeResponse:
        text = "  a real Gemini reply  "

    class _FakeModels:
        def generate_content(self, **_kwargs: object) -> _FakeResponse:
            return _FakeResponse()

    class _FakeClient:
        def __init__(self, **_kwargs: object) -> None:
            self.models = _FakeModels()

    monkeypatch.setattr(genai, "Client", _FakeClient)

    assert GemmaClient().generate_text("hello") == "a real Gemini reply"
