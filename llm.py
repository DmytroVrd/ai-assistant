from __future__ import annotations

import json
import logging

import httpx

from config import Settings
from schemas import ExtractedMemory


logger = logging.getLogger(__name__)


class OpenRouterClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = httpx.AsyncClient(
            base_url="https://openrouter.ai/api/v1",
            timeout=settings.request_timeout_seconds,
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": settings.openrouter_site_url,
                "X-Title": settings.app_name,
            },
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def generate_reply(self, user_message: str, user_context: str, *, language: str = "en") -> str:
        response_language = "Ukrainian" if language == "uk" else "English"
        empty_context = "Поки що контекст порожній." if language == "uk" else "No saved context yet."
        system_prompt = (
            "You are a warm, practical Telegram AI assistant with memory. "
            "Use saved context only when it is actually relevant. "
            "Do not invent facts that are not in the context. "
            f"Reply in {response_language} unless the user explicitly asks for another language. "
            "Keep answers natural, friendly, and not too long."
        )
        user_prompt = (
            f"User context:\n{user_context or empty_context}\n\n"
            f"User message:\n{user_message}"
        )
        payload = {
            "model": self._settings.openrouter_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        response = await self._client.post("/chat/completions", json=payload)
        response.raise_for_status()
        data = response.json()
        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            logger.exception("Unexpected OpenRouter response: %s", data)
            raise RuntimeError("OpenRouter returned an unexpected response payload.") from exc

    async def extract_memory(self, user_message: str) -> ExtractedMemory:
        prompt = (
            "Extract only stable facts about the user from the message. "
            'Return JSON exactly in this shape: {"facts": ["..."], "goals": ["..."], '
            '"preferences": {"tone": "..."}, "topics": ["..."]}. '
            "facts: short facts about the user. "
            "goals: user goals or intentions. "
            "preferences: only stable preferences. "
            "topics: short message topics. "
            "If nothing important is present, return empty arrays and an empty object."
        )
        payload = {
            "model": self._settings.openrouter_model,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_message},
            ],
            "response_format": {"type": "json_object"},
        }
        response = await self._client.post("/chat/completions", json=payload)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Failed to decode memory extraction JSON.") from exc
        return ExtractedMemory.model_validate(parsed)
