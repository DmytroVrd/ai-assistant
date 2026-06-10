from __future__ import annotations

import asyncio
import json
import logging

import httpx
from pydantic import ValidationError

from config import Settings
from schemas import ExtractedMemory


logger = logging.getLogger(__name__)


def parse_extracted_memory(content: object) -> ExtractedMemory:
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("OpenRouter returned empty memory extraction content.")

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Failed to decode memory extraction JSON.") from exc

    if not isinstance(parsed, dict):
        raise RuntimeError("Memory extraction must be a JSON object.")

    try:
        return ExtractedMemory.model_validate(parsed)
    except ValidationError as exc:
        raise RuntimeError("Memory extraction JSON does not match the expected schema.") from exc


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
            "You extract structured long-term memory for a personal assistant. "
            "Extract only information explicitly stated about the user. "
            "Do not treat questions, assistant instructions, hypothetical examples, "
            "or facts about other people as user memory. "
            "Keep only information that could be useful in future conversations. "
            'Return JSON exactly in this shape: {"facts": ["..."], "goals": ["..."], '
            '"preferences": {"tone": "..."}, "topics": ["..."]}. '
            "facts: concise stable facts about the user. "
            "goals: explicit user goals or plans, not the purpose of a question. "
            "preferences: only explicit reusable preferences such as language, tone, or answer style. "
            "topics: up to three concise topics from the current message. "
            "Write extracted values in clear English for consistent storage. "
            "Do not infer sensitive attributes or unsupported details. "
            "If no long-term memory is present, keep facts, goals, and preferences empty; "
            "topics may still describe the message."
        )
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_message},
        ]
        last_error: Exception | None = None

        for attempt in range(2):
            payload = {
                "model": self._settings.openrouter_model,
                "messages": messages,
                "response_format": {"type": "json_object"},
                "temperature": 0,
            }
            extraction_timeout = min(self._settings.request_timeout_seconds, 20)
            response = await self._client.post(
                "/chat/completions",
                json=payload,
                timeout=extraction_timeout,
            )
            response.raise_for_status()
            data = response.json()
            try:
                content = data["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError) as exc:
                last_error = RuntimeError("OpenRouter returned an unexpected memory payload.")
                logger.warning("Unexpected OpenRouter memory payload on attempt %s.", attempt + 1)
                if attempt == 0:
                    await asyncio.sleep(0.5)
                    continue
                raise last_error from exc

            try:
                return parse_extracted_memory(content)
            except RuntimeError as exc:
                last_error = exc
                logger.warning("Invalid LLM memory extraction response on attempt %s.", attempt + 1)
                if attempt == 0:
                    messages.extend(
                        [
                            {"role": "assistant", "content": content or ""},
                            {
                                "role": "user",
                                "content": (
                                    "Your previous JSON was invalid. Return all four keys exactly: "
                                    "facts, goals, preferences, topics. facts, goals, and topics must "
                                    "be arrays of strings. preferences must be an object whose values "
                                    "are strings. Return JSON only."
                                ),
                            },
                        ]
                    )

        raise RuntimeError("OpenRouter failed to return valid structured memory.") from last_error
