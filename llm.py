from __future__ import annotations

import asyncio
import json
import logging

import httpx
from pydantic import ValidationError

from config import Settings
from schemas import AssistantResult, ExtractedMemory


logger = logging.getLogger(__name__)

MEMORY_KEYS = {"facts", "goals", "preferences", "topics"}


def parse_extracted_memory(content: object) -> ExtractedMemory:
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("OpenRouter returned empty memory extraction content.")

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Failed to decode memory extraction JSON.") from exc

    if not isinstance(parsed, dict):
        raise RuntimeError("Memory extraction must be a JSON object.")
    if set(parsed) != MEMORY_KEYS:
        raise RuntimeError("Memory extraction JSON must contain exactly the expected keys.")

    try:
        return ExtractedMemory.model_validate(parsed)
    except ValidationError as exc:
        raise RuntimeError("Memory extraction JSON does not match the expected schema.") from exc


def parse_assistant_result(content: object) -> AssistantResult:
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("OpenRouter returned empty assistant content.")

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Failed to decode assistant JSON.") from exc

    if not isinstance(parsed, dict) or set(parsed) != {"reply", "memory"}:
        raise RuntimeError("Assistant JSON must contain exactly reply and memory.")
    if not isinstance(parsed["memory"], dict) or set(parsed["memory"]) != MEMORY_KEYS:
        raise RuntimeError("Assistant memory must contain exactly the expected keys.")

    try:
        result = AssistantResult.model_validate(parsed)
    except ValidationError as exc:
        raise RuntimeError("Assistant JSON does not match the expected schema.") from exc

    if not result.reply.strip():
        raise RuntimeError("Assistant reply is empty.")
    return result


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

    async def generate_reply_with_memory(
        self,
        user_message: str,
        user_context: str,
        *,
        language: str = "en",
    ) -> AssistantResult:
        response_language = "Ukrainian" if language == "uk" else "English"
        empty_context = "No saved context yet."
        prompt = (
            "You are a warm, practical personal assistant with long-term memory. "
            f"Write the reply in {response_language} unless the user explicitly requests another language. "
            "Use saved context only when relevant and never invent user details. "
            "Keep the reply natural, friendly, useful, and reasonably concise. "
            "At the same time, build an accurate evolving profile of the user from the current message. "
            "A detail is worth remembering when it is about the user, is likely to remain true beyond the "
            "immediate moment, and could improve a future answer or help understand the user's personality. "
            "This includes identity, age, location, background, relationships, education, work, skills, "
            "interests, hobbies, favorite activities, likes, dislikes, values, role models or idols, habits, "
            "recurring activities, ongoing projects, constraints, goals, plans, and communication preferences. "
            "Save explicit personal interests, hobbies, locations, and role models even when stated casually. "
            "If one message contains several useful details, save each as a separate concise item. "
            "Classify durable personal details as facts, desired future outcomes as goals, and reusable "
            "interaction choices as preferences. Questions about a subject are not personal facts. "
            "Do not save one-off mundane actions or temporary states that will not matter later, "
            "hypothetical examples, information about other people that is unrelated to the user, "
            "passwords, tokens, financial credentials, or inferred sensitive attributes. "
            "Extract memory only from the current user message, not from the saved context. "
            "Do not return a fact or goal if the same meaning is already present in saved context. "
            "Normalize memory into concise third-person English statements for consistent storage. "
            "All personal profile information must go into facts, goals, or preferences. Never create "
            "alternative keys such as interests, hobbies, location, personality, idol, or profile. "
            "Examples of the classification policy: living in a country is a fact; loving or playing a "
            "sport is a fact; having an idol is a fact; wanting to move abroad is a goal; asking about a "
            "sport is not personal memory; mentioning a one-time bathroom visit is not useful memory. "
            'Return JSON only in exactly this shape: {"reply": "...", "memory": {'
            '"facts": ["..."], "goals": ["..."], "preferences": {"key": "value"}, '
            '"topics": ["..."]}}. All four memory keys are required. '
            "Use empty arrays or an empty object when there is nothing to save."
        )
        messages = [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": (
                    f"Saved user context:\n{user_context or empty_context}\n\n"
                    f"Current user message:\n{user_message}"
                ),
            },
        ]
        last_error: Exception | None = None

        for attempt in range(2):
            payload = {
                "model": self._settings.openrouter_model,
                "messages": messages,
                "response_format": {"type": "json_object"},
                "temperature": 0,
            }
            response = await self._client.post("/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()
            try:
                content = data["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError) as exc:
                last_error = RuntimeError("OpenRouter returned an unexpected assistant payload.")
                if attempt == 0:
                    await asyncio.sleep(0.5)
                    continue
                raise last_error from exc

            try:
                return parse_assistant_result(content)
            except RuntimeError as exc:
                last_error = exc
                logger.warning("Invalid combined assistant response on attempt %s.", attempt + 1)
                if attempt == 0:
                    messages.extend(
                        [
                            {"role": "assistant", "content": content or ""},
                            {
                                "role": "user",
                                "content": (
                                    "Repair the response. Return JSON only with a non-empty reply string "
                                    "and a memory object containing facts, goals, preferences, and topics. "
                                    "facts, goals, and topics must be arrays of strings; preferences must "
                                    "be an object with string values. Do not use any other keys. Move "
                                    "interests, hobbies, location, personality details, and role models "
                                    "into facts."
                                ),
                            },
                        ]
                    )

        raise RuntimeError("OpenRouter failed to return a valid assistant result.") from last_error

    async def extract_memory(self, user_message: str) -> ExtractedMemory:
        prompt = (
            "You are the long-term memory manager for a personal AI assistant. "
            "Decide what information from the current message will improve future personalization. "
            "Extract only information explicitly stated as true about the user. "
            "Useful memory includes identity and background, relationships, education or work, "
            "skills, interests, hobbies, likes and dislikes, habits, recurring activities, "
            "ongoing projects, constraints, goals, plans, and communication preferences. "
            "Interests and hobbies such as loving a sport belong in facts. "
            "Do not treat questions, assistant instructions, hypothetical examples, "
            "temporary requests, or facts about other people as user memory. "
            "Do not store passwords, authentication tokens, financial credentials, or other secrets. "
            "When uncertain, save a user-stated detail if remembering it could make a later response "
            "more relevant, personal, or convenient. "
            'Return JSON exactly in this shape: {"facts": ["..."], "goals": ["..."], '
            '"preferences": {"tone": "..."}, "topics": ["..."]}. '
            "facts: concise durable facts about the user, including interests and hobbies. "
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
