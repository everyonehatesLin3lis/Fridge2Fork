from __future__ import annotations

import base64
import json
import random
import socket
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from src.config import get_settings


class GemmaClient:
    """Central wrapper for mock and live Gemma calls."""

    def __init__(self) -> None:
        self.settings = get_settings()

    def generate_text(self, prompt: str, creative: bool = False) -> str:
        """Generate text from a prompt.

        creative=True raises temperature and randomizes the seed so repeated
        calls with the same prompt produce different output (recipe variety).
        """
        if self.settings.app_mode == "mock":
            return '{"status": "mock", "message": "Mock Gemma text response"}'
        if self.settings.app_mode == "local":
            options = {"temperature": 0.95, "seed": random.randint(0, 2**31 - 1)} if creative else None
            return self._call_ollama(prompt, options=options)
        if self.settings.app_mode == "google":
            return self._call_google_ai(prompt, creative=creative)
        if not self.settings.gemma_api_key:
            raise RuntimeError("GEMMA_API_KEY is required when APP_MODE=live.")
        raise NotImplementedError("Live Gemma provider transport should be added in GemmaClient only.")

    def generate_from_image(self, image: Any, prompt: str) -> str:
        """Generate text from an image and prompt."""
        if self.settings.app_mode == "mock":
            return '{"status": "mock", "message": "Mock Gemma multimodal response"}'
        if self.settings.app_mode == "local":
            image_payload = self._image_to_base64(image)
            # format="json" makes Ollama constrain the output to valid JSON,
            # which vision models like llava do not produce reliably on their own.
            return self._call_ollama(
                prompt,
                images=[image_payload] if image_payload else None,
                model=self.settings.vision_model_name,
                format="json",
            )
        if self.settings.app_mode == "google":
            return self._call_google_ai(prompt, images=[image] if image is not None else None)
        if not self.settings.gemma_api_key:
            raise RuntimeError("GEMMA_API_KEY is required when APP_MODE=live.")
        raise NotImplementedError("Live Gemma provider transport should be added in GemmaClient only.")

    def health_check(self) -> str:
        """Return a short response from the configured local model."""
        return self.generate_text("Reply with one short sentence: FridgeAgent local Gemma is ready.")

    def _call_ollama(
        self,
        prompt: str,
        images: list[str] | None = None,
        model: str | None = None,
        format: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> str:
        payload: dict[str, Any] = {
            "model": model or self.settings.gemma_model_name,
            "prompt": prompt,
            "stream": False,
        }
        if images:
            payload["images"] = images
        if format:
            payload["format"] = format
        if options:
            payload["options"] = options

        url = f"{self.settings.ollama_base_url.rstrip('/')}/api/generate"
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.settings.ollama_timeout_seconds) as response:
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

    def _call_google_ai(self, prompt: str, images: list[Any] | None = None, creative: bool = False) -> str:
        """Call the real Google AI (Gemini) API via the `google-genai` SDK. Used for APP_MODE=google."""
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise RuntimeError(
                "google-genai is not installed. Run `pip install google-genai` to use APP_MODE=google."
            ) from exc

        if not self.settings.google_api_key:
            raise RuntimeError("GOOGLE_API_KEY is required when APP_MODE=google.")

        client = genai.Client(api_key=self.settings.google_api_key)

        contents: list[Any] = [prompt]
        for image in images or []:
            image_bytes = self._image_to_bytes(image)
            if image_bytes:
                contents.append(types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"))

        try:
            response = client.models.generate_content(
                model=self.settings.google_model_name,
                contents=contents,
                config=types.GenerateContentConfig(temperature=0.95) if creative else None,
            )
        except Exception as exc:  # google-genai raises provider-specific exceptions
            raise RuntimeError(f"Google AI (Gemini) request failed: {exc}") from exc

        return (getattr(response, "text", "") or "").strip()

    @staticmethod
    def _image_to_bytes(image: Any) -> bytes | None:
        if image is None:
            return None
        if isinstance(image, bytes):
            return image
        if hasattr(image, "getvalue"):
            return image.getvalue()
        if hasattr(image, "read"):
            current_position = image.tell() if hasattr(image, "tell") else None
            content = image.read()
            if current_position is not None and hasattr(image, "seek"):
                image.seek(current_position)
            return content
        return None

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
