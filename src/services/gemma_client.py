from __future__ import annotations

import base64
import json
import socket
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from src.config import get_settings


class GemmaClient:
    """Central wrapper for mock and live Gemma calls."""

    def __init__(self) -> None:
        self.settings = get_settings()

    def generate_text(self, prompt: str) -> str:
        """Generate text from a prompt."""
        if self.settings.app_mode == "mock":
            return '{"status": "mock", "message": "Mock Gemma text response"}'
        if self.settings.app_mode == "local":
            return self._call_ollama(prompt)
        if not self.settings.gemma_api_key:
            raise RuntimeError("GEMMA_API_KEY is required when APP_MODE=live.")
        raise NotImplementedError("Live Gemma provider transport should be added in GemmaClient only.")

    def generate_from_image(self, image: Any, prompt: str) -> str:
        """Generate text from an image and prompt."""
        if self.settings.app_mode == "mock":
            return '{"status": "mock", "message": "Mock Gemma multimodal response"}'
        if self.settings.app_mode == "local":
            image_payload = self._image_to_base64(image)
            return self._call_ollama(prompt, images=[image_payload] if image_payload else None)
        if not self.settings.gemma_api_key:
            raise RuntimeError("GEMMA_API_KEY is required when APP_MODE=live.")
        raise NotImplementedError("Live Gemma provider transport should be added in GemmaClient only.")

    def health_check(self) -> str:
        """Return a short response from the configured local model."""
        return self.generate_text("Reply with one short sentence: FridgeAgent local Gemma is ready.")

    def _call_ollama(self, prompt: str, images: list[str] | None = None) -> str:
        payload: dict[str, Any] = {
            "model": self.settings.gemma_model_name,
            "prompt": prompt,
            "stream": False,
        }
        if images:
            payload["images"] = images

        url = f"{self.settings.ollama_base_url.rstrip('/')}/api/generate"
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(request, timeout=120) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (TimeoutError, socket.timeout) as exc:
            raise RuntimeError(
                "Local Gemma timed out while generating a response. The app can continue with fallback logic, "
                "or you can try fewer ingredients, shorter prompts, or restart Ollama."
            ) from exc
        except URLError as exc:
            raise RuntimeError(
                "Could not reach local Ollama. Start it with `ollama serve` and make sure "
                f"`ollama run {self.settings.gemma_model_name}` works."
            ) from exc

        if "error" in data:
            raise RuntimeError(f"Local Gemma error: {data['error']}")
        return str(data.get("response", "")).strip()

    @staticmethod
    def _image_to_base64(image: Any) -> str | None:
        if image is None:
            return None
        if isinstance(image, bytes):
            return base64.b64encode(image).decode("ascii")
        if hasattr(image, "getvalue"):
            return base64.b64encode(image.getvalue()).decode("ascii")
        if hasattr(image, "read"):
            current_position = image.tell() if hasattr(image, "tell") else None
            content = image.read()
            if current_position is not None and hasattr(image, "seek"):
                image.seek(current_position)
            return base64.b64encode(content).decode("ascii")
        return None
