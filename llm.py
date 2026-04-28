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

    async def generate_reply(self, user_message: str, user_context: str) -> str:
        system_prompt = (
            "Ти теплий і практичний Telegram AI-асистент з пам'яттю. "
            "Використовуй збережений контекст лише коли він справді доречний. "
            "Не вигадуй фактів, яких немає в контексті. "
            "Відповідай українською, якщо користувач явно не просить іншу мову. "
            "Тримай відповіді природними, дружніми і не надто довгими."
        )
        user_prompt = (
            f"Контекст користувача:\n{user_context or 'Поки що контекст порожній.'}\n\n"
            f"Повідомлення користувача:\n{user_message}"
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
            "Витягни тільки стабільні факти про користувача з повідомлення. "
            "Поверни JSON рівно такого виду: "
            '{"facts": ["..."], "goals": ["..."], "preferences": {"tone": "..."}, "topics": ["..."]}. '
            "facts: короткі факти про користувача. "
            "goals: цілі або наміри користувача. "
            "preferences: тільки стабільні вподобання. "
            "topics: короткі теми повідомлення. "
            "Якщо важливої інформації немає, поверни порожні масиви і порожній об’єкт."
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
