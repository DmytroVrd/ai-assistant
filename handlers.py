from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from config import Settings
from db import MemoryUnavailableError, UserMemoryStore, is_name_related_query
from llm import OpenRouterClient
from memory import heuristic_extract_facts, merge_memories
from schemas import ConversationTurn, ExtractedMemory


logger = logging.getLogger(__name__)

ACCESS_DENIED_TEXT = "\u0426\u0435\u0439 \u0431\u043e\u0442 \u0434\u043e\u0441\u0442\u0443\u043f\u043d\u0438\u0439 \u0442\u0456\u043b\u044c\u043a\u0438 \u0432\u043b\u0430\u0441\u043d\u0438\u043a\u0443."
IDENTITY_ERROR_TEXT = "\u041d\u0435 \u0432\u0434\u0430\u043b\u043e\u0441\u044f \u0432\u0438\u0437\u043d\u0430\u0447\u0438\u0442\u0438 \u043a\u043e\u0440\u0438\u0441\u0442\u0443\u0432\u0430\u0447\u0430 \u0434\u043b\u044f \u0446\u044c\u043e\u0433\u043e \u043f\u043e\u0432\u0456\u0434\u043e\u043c\u043b\u0435\u043d\u043d\u044f."
MEMORY_OFFLINE_TEXT = "\u0421\u0445\u043e\u0432\u0438\u0449\u0435 \u043f\u0430\u043c'\u044f\u0442\u0456 \u0442\u0438\u043c\u0447\u0430\u0441\u043e\u0432\u043e \u043d\u0435\u0434\u043e\u0441\u0442\u0443\u043f\u043d\u0435."
NAME_FORGET_PATTERNS = (
    "\u0437\u0430\u0431\u0443\u0434\u044c \u044f\u043a \u043c\u0435\u043d\u0435 \u0437\u0432\u0430\u0442\u0438",
    "\u0437\u0430\u0431\u0443\u0434\u044c \u043c\u043e\u0454 \u0456\u043c'\u044f",
    "\u0437\u0430\u0431\u0443\u0434\u044c \u043c\u043e\u0435 \u0456\u043c\u044f",
)


def _command_payload(message: Message) -> str:
    return (message.text or "").split(maxsplit=1)[1].strip() if " " in (message.text or "") else ""


def _get_user_identity(message: Message) -> tuple[int, str | None] | None:
    if not message.from_user:
        return None
    return message.from_user.id, message.from_user.username


def _natural_forget_query(text: str) -> str | None:
    lowered = text.casefold().strip()
    if any(pattern in lowered for pattern in NAME_FORGET_PATTERNS):
        return "\u0456\u043c'\u044f"
    if lowered.startswith("\u0437\u0430\u0431\u0443\u0434\u044c "):
        payload = text.strip()[len("\u0437\u0430\u0431\u0443\u0434\u044c ") :].strip()
        return payload or None
    return None


async def _ensure_allowed_user(message: Message, settings: Settings) -> bool:
    identity = _get_user_identity(message)
    if not identity:
        await message.answer(IDENTITY_ERROR_TEXT)
        return False

    user_id, _ = identity
    if user_id != settings.allowed_telegram_user_id:
        await message.answer(ACCESS_DENIED_TEXT)
        return False

    return True


async def _extract_memory(user_message: str, llm_client: OpenRouterClient) -> ExtractedMemory:
    heuristic_memory = heuristic_extract_facts(user_message)
    likely_personal = bool(
        heuristic_memory.facts
        or heuristic_memory.goals
        or heuristic_memory.preferences
        or any(
            token in user_message.casefold()
            for token in ("\u043c\u0435\u043d\u0435", "\u044f ", "\u043c\u043e\u0457", "\u0445\u043e\u0447\u0443", "\u043f\u043b\u0430\u043d\u0443\u044e", "\u0446\u0456\u043b\u044c")
        )
    )

    if not likely_personal:
        return heuristic_memory

    try:
        llm_memory = await llm_client.extract_memory(user_message)
    except Exception:
        logger.exception("Falling back to heuristic memory extraction.")
        return heuristic_memory
    return merge_memories(heuristic_memory, llm_memory)


async def _extract_memory_with_fallback(user_message: str, llm_client: OpenRouterClient) -> ExtractedMemory:
    try:
        return await _extract_memory(user_message, llm_client)
    except Exception:
        logger.exception("Memory extraction failed completely.")
        return heuristic_extract_facts(user_message)


def _format_removed_items(removed: dict[str, list[str]]) -> str:
    pieces: list[str] = []
    if removed["facts"]:
        pieces.append("\u0444\u0430\u043a\u0442\u0438: " + "; ".join(removed["facts"]))
    if removed["goals"]:
        pieces.append("\u0446\u0456\u043b\u0456: " + "; ".join(removed["goals"]))
    return "\n".join(pieces)


async def _perform_forget(
    message: Message,
    memory_store: UserMemoryStore,
    query: str,
) -> None:
    identity = _get_user_identity(message)
    if not identity:
        await message.answer(IDENTITY_ERROR_TEXT)
        return

    user_id, username = identity
    try:
        await memory_store.ensure_user(user_id, username)
        removed = await memory_store.forget_fact(user_id, query)
    except MemoryUnavailableError:
        await message.answer(f"{MEMORY_OFFLINE_TEXT} \u0417\u0430\u0440\u0430\u0437 \u044f \u043d\u0435 \u043c\u043e\u0436\u0443 \u0437\u043c\u0456\u043d\u0438\u0442\u0438 \u043f\u0430\u043c'\u044f\u0442\u044c.")
        return

    if removed["facts"] or removed["goals"]:
        details = _format_removed_items(removed)
        if details:
            await message.answer("\u0413\u043e\u0442\u043e\u0432\u043e, \u044f \u043f\u0440\u0438\u0431\u0440\u0430\u0432 \u0437 \u043f\u0430\u043c'\u044f\u0442\u0456:\n" + details)
        else:
            await message.answer("\u0413\u043e\u0442\u043e\u0432\u043e, \u044f \u043f\u0440\u0438\u0431\u0440\u0430\u0432 \u0446\u0435 \u0437 \u043f\u0430\u043c'\u044f\u0442\u0456.")
        return

    if is_name_related_query(query):
        await message.answer("\u041d\u0435 \u0437\u043d\u0430\u0439\u0448\u043e\u0432 \u0437\u0431\u0435\u0440\u0435\u0436\u0435\u043d\u0435 \u0456\u043c'\u044f \u0443 \u043f\u0430\u043c'\u044f\u0442\u0456.")
    else:
        await message.answer("\u041d\u0435 \u0437\u043d\u0430\u0439\u0448\u043e\u0432 \u043f\u0456\u0434\u0445\u043e\u0434\u044f\u0449\u0456 \u0444\u0430\u043a\u0442\u0438 \u0430\u0431\u043e \u0446\u0456\u043b\u0456 \u0443 \u043f\u0430\u043c'\u044f\u0442\u0456.")


def build_router(
    memory_store: UserMemoryStore,
    llm_client: OpenRouterClient,
    settings: Settings,
) -> Router:
    router = Router(name="assistant")

    @router.message(Command("start"))
    async def start_handler(message: Message) -> None:
        if not await _ensure_allowed_user(message, settings):
            return

        identity = _get_user_identity(message)
        if not identity:
            await message.answer(IDENTITY_ERROR_TEXT)
            return

        user_id, username = identity
        try:
            await memory_store.ensure_user(user_id, username)
        except MemoryUnavailableError:
            logger.warning("MongoDB unavailable during /start.")
            await message.answer(
                "\u041f\u0440\u0438\u0432\u0456\u0442! \u042f AI-\u0430\u0441\u0438\u0441\u0442\u0435\u043d\u0442 \u0437 \u043f\u0430\u043c'\u044f\u0442\u0442\u044e.\n"
                "\u0417\u0430\u0440\u0430\u0437 \u0441\u0445\u043e\u0432\u0438\u0449\u0435 \u043f\u0430\u043c'\u044f\u0442\u0456 \u043d\u0435\u0434\u043e\u0441\u0442\u0443\u043f\u043d\u0435, \u0442\u043e\u043c\u0443 \u044f \u043c\u043e\u0436\u0443 \u0441\u043f\u0456\u043b\u043a\u0443\u0432\u0430\u0442\u0438\u0441\u044f, "
                "\u0430\u043b\u0435 \u043d\u0435 \u0437\u0431\u0435\u0440\u0435\u0436\u0443 \u043d\u043e\u0432\u0456 \u0444\u0430\u043a\u0442\u0438, \u043f\u043e\u043a\u0438 MongoDB \u043d\u0435 \u0432\u0456\u0434\u043d\u043e\u0432\u0438\u0442\u044c\u0441\u044f.\n\n"
                "\u041a\u043e\u043c\u0430\u043d\u0434\u0438: /remember, /forget, /facts, /summary, /clear"
            )
            return

        await message.answer(
            "\u041f\u0440\u0438\u0432\u0456\u0442! \u042f AI-\u0430\u0441\u0438\u0441\u0442\u0435\u043d\u0442 \u0437 \u043f\u0430\u043c'\u044f\u0442\u0442\u044e.\n"
            "\u042f \u043c\u043e\u0436\u0443 \u0432\u0456\u0434\u043f\u043e\u0432\u0456\u0434\u0430\u0442\u0438 \u043d\u0430 \u043f\u0438\u0442\u0430\u043d\u043d\u044f, \u0437\u0430\u043f\u0430\u043c'\u044f\u0442\u043e\u0432\u0443\u0432\u0430\u0442\u0438 \u0444\u0430\u043a\u0442\u0438 \u043f\u0440\u043e \u0442\u0435\u0431\u0435 "
            "\u0456 \u0432\u0438\u043a\u043e\u0440\u0438\u0441\u0442\u043e\u0432\u0443\u0432\u0430\u0442\u0438 \u0457\u0445 \u0443 \u043d\u0430\u0441\u0442\u0443\u043f\u043d\u0438\u0445 \u0432\u0456\u0434\u043f\u043e\u0432\u0456\u0434\u044f\u0445.\n\n"
            "\u041a\u043e\u043c\u0430\u043d\u0434\u0438: /remember, /forget, /facts, /summary, /clear"
        )

    @router.message(Command("remember"))
    async def remember_handler(message: Message) -> None:
        if not await _ensure_allowed_user(message, settings):
            return

        payload = _command_payload(message)
        if not payload:
            await message.answer("\u041f\u0440\u0438\u043a\u043b\u0430\u0434: /remember \u042f \u0432\u0438\u0432\u0447\u0430\u044e Python \u0432\u0436\u0435 3 \u043c\u0456\u0441\u044f\u0446\u0456")
            return

        identity = _get_user_identity(message)
        if not identity:
            await message.answer(IDENTITY_ERROR_TEXT)
            return

        user_id, username = identity
        try:
            await memory_store.ensure_user(user_id, username)
            extracted_memory = await _extract_memory_with_fallback(payload, llm_client)
            await memory_store.apply_memory(user_id, extracted_memory)
            await memory_store.save_explicit_fact(user_id, payload)
        except MemoryUnavailableError:
            await message.answer(f"{MEMORY_OFFLINE_TEXT} \u0417\u0430\u0440\u0430\u0437 \u044f \u043d\u0435 \u043c\u043e\u0436\u0443 \u043d\u0456\u0447\u043e\u0433\u043e \u0437\u0431\u0435\u0440\u0435\u0433\u0442\u0438.")
            return

        await message.answer("\u0417\u0430\u043f\u0430\u043c'\u044f\u0442\u0430\u0432. \u0412\u0440\u0430\u0445\u0443\u044e \u0446\u0435 \u0432 \u043d\u0430\u0441\u0442\u0443\u043f\u043d\u0438\u0445 \u0432\u0456\u0434\u043f\u043e\u0432\u0456\u0434\u044f\u0445.")

    @router.message(Command("forget"))
    async def forget_handler(message: Message) -> None:
        if not await _ensure_allowed_user(message, settings):
            return

        payload = _command_payload(message)
        if not payload:
            await message.answer("\u041f\u0440\u0438\u043a\u043b\u0430\u0434: /forget Python \u0430\u0431\u043e /forget \u0456\u043c'\u044f")
            return

        await _perform_forget(message, memory_store, payload)

    @router.message(Command("facts"))
    async def facts_handler(message: Message) -> None:
        if not await _ensure_allowed_user(message, settings):
            return

        identity = _get_user_identity(message)
        if not identity:
            await message.answer(IDENTITY_ERROR_TEXT)
            return

        user_id, username = identity
        try:
            await memory_store.ensure_user(user_id, username)
            items = await memory_store.list_memory_items(user_id)
        except MemoryUnavailableError:
            await message.answer(f"{MEMORY_OFFLINE_TEXT} \u0417\u0430\u0440\u0430\u0437 \u044f \u043d\u0435 \u043c\u043e\u0436\u0443 \u043f\u043e\u043a\u0430\u0437\u0430\u0442\u0438 \u043f\u0430\u043c'\u044f\u0442\u044c.")
            return

        lines = ["\u041e\u0441\u044c \u0449\u043e \u0441\u0430\u043c\u0435 \u043b\u0435\u0436\u0438\u0442\u044c \u0443 \u043f\u0430\u043c'\u044f\u0442\u0456:"]
        if items["facts"]:
            lines.append("- \u0424\u0430\u043a\u0442\u0438:")
            lines.extend(f"  {index}. {fact}" for index, fact in enumerate(items["facts"], start=1))
        else:
            lines.append("- \u0424\u0430\u043a\u0442\u0438: \u043f\u043e\u043a\u0438 \u043d\u0435\u043c\u0430\u0454")

        if items["goals"]:
            lines.append("- \u0426\u0456\u043b\u0456:")
            lines.extend(f"  {index}. {goal}" for index, goal in enumerate(items["goals"], start=1))
        else:
            lines.append("- \u0426\u0456\u043b\u0456: \u043f\u043e\u043a\u0438 \u043d\u0435\u043c\u0430\u0454")

        await message.answer("\n".join(lines))

    @router.message(Command("summary"))
    async def summary_handler(message: Message) -> None:
        if not await _ensure_allowed_user(message, settings):
            return

        identity = _get_user_identity(message)
        if not identity:
            await message.answer(IDENTITY_ERROR_TEXT)
            return

        user_id, username = identity
        try:
            await memory_store.ensure_user(user_id, username)
            profile = await memory_store.get_profile(user_id)
        except MemoryUnavailableError:
            await message.answer(f"{MEMORY_OFFLINE_TEXT} \u0417\u0430\u0440\u0430\u0437 \u044f \u043d\u0435 \u043c\u043e\u0436\u0443 \u043f\u043e\u043a\u0430\u0437\u0430\u0442\u0438 \u0437\u0431\u0435\u0440\u0435\u0436\u0435\u043d\u0456 \u0434\u0430\u043d\u0456.")
            return

        lines = [
            "\u041e\u0441\u044c \u0449\u043e \u044f \u0437\u0430\u0440\u0430\u0437 \u043f\u0440\u043e \u0442\u0435\u0431\u0435 \u043f\u0430\u043c'\u044f\u0442\u0430\u044e:",
            f"- Username: @{profile.username}" if profile.username else "- Username: \u043d\u0435 \u0432\u043a\u0430\u0437\u0430\u043d\u043e",
            f"- \u0426\u0456\u043b\u0456: {', '.join(profile.goals) if profile.goals else '\u043f\u043e\u043a\u0438 \u043d\u0435\u043c\u0430\u0454'}",
            f"- \u0424\u0430\u043a\u0442\u0438: {', '.join(profile.facts) if profile.facts else '\u043f\u043e\u043a\u0438 \u043d\u0435\u043c\u0430\u0454'}",
            (
                "- \u041f\u0440\u0435\u0444\u0435\u0440\u0435\u043d\u0446\u0456\u0457: "
                + ", ".join(f"{key}={value}" for key, value in profile.preferences.items())
                if profile.preferences
                else "- \u041f\u0440\u0435\u0444\u0435\u0440\u0435\u043d\u0446\u0456\u0457: \u043f\u043e\u043a\u0438 \u043d\u0435\u043c\u0430\u0454"
            ),
            f"- \u041e\u0441\u0442\u0430\u043d\u043d\u0456 \u0442\u0435\u043c\u0438: {', '.join(profile.last_topics) if profile.last_topics else '\u043f\u043e\u043a\u0438 \u043d\u0435\u043c\u0430\u0454'}",
            f"- \u041f\u043e\u0432\u0456\u0434\u043e\u043c\u043b\u0435\u043d\u044c \u0443 \u043f\u0430\u043c'\u044f\u0442\u0456: {profile.messages_count}",
        ]
        await message.answer("\n".join(lines))

    @router.message(Command("clear"))
    async def clear_handler(message: Message) -> None:
        if not await _ensure_allowed_user(message, settings):
            return

        identity = _get_user_identity(message)
        if not identity:
            await message.answer(IDENTITY_ERROR_TEXT)
            return

        user_id, username = identity
        try:
            await memory_store.ensure_user(user_id, username)
            await memory_store.clear_history(user_id)
        except MemoryUnavailableError:
            await message.answer(f"{MEMORY_OFFLINE_TEXT} \u0417\u0430\u0440\u0430\u0437 \u044f \u043d\u0435 \u043c\u043e\u0436\u0443 \u043e\u0447\u0438\u0441\u0442\u0438\u0442\u0438 \u0456\u0441\u0442\u043e\u0440\u0456\u044e.")
            return

        await message.answer("\u0406\u0441\u0442\u043e\u0440\u0456\u044e \u0434\u0456\u0430\u043b\u043e\u0433\u0443 \u043e\u0447\u0438\u0449\u0435\u043d\u043e. \u0424\u0430\u043a\u0442\u0438, \u0446\u0456\u043b\u0456 \u0439 \u043f\u0440\u0435\u0444\u0435\u0440\u0435\u043d\u0446\u0456\u0457 \u044f \u0437\u0430\u043b\u0438\u0448\u0438\u0432.")

    @router.message()
    async def chat_handler(message: Message) -> None:
        if not await _ensure_allowed_user(message, settings):
            return

        if not message.text or not message.from_user:
            await message.answer("\u041f\u043e\u043a\u0438 \u0449\u043e \u044f \u043f\u0440\u0430\u0446\u044e\u044e \u0442\u0456\u043b\u044c\u043a\u0438 \u0437 \u0442\u0435\u043a\u0441\u0442\u043e\u0432\u0438\u043c\u0438 \u043f\u043e\u0432\u0456\u0434\u043e\u043c\u043b\u0435\u043d\u043d\u044f\u043c\u0438.")
            return

        natural_forget_query = _natural_forget_query(message.text)
        if natural_forget_query is not None:
            await _perform_forget(message, memory_store, natural_forget_query)
            return

        user_id = message.from_user.id
        username = message.from_user.username
        user_context = ""
        memory_enabled = True
        try:
            await memory_store.ensure_user(user_id, username)
            user_context = await memory_store.get_user_context(user_id)
        except MemoryUnavailableError:
            memory_enabled = False
            logger.warning("MongoDB unavailable during chat handling; continuing without memory.")

        try:
            reply = await llm_client.generate_reply(message.text, user_context)
        except Exception:
            logger.exception("Failed to generate assistant reply.")
            await message.answer(
                "\u0417\u0430\u0440\u0430\u0437 \u043d\u0435 \u0432\u0434\u0430\u043b\u043e\u0441\u044f \u043e\u0442\u0440\u0438\u043c\u0430\u0442\u0438 \u0432\u0456\u0434\u043f\u043e\u0432\u0456\u0434\u044c \u0432\u0456\u0434 AI. "
                "\u041f\u0435\u0440\u0435\u0432\u0456\u0440 OpenRouter \u043a\u043b\u044e\u0447, \u043c\u043e\u0434\u0435\u043b\u044c \u0430\u0431\u043e \u043c\u0435\u0440\u0435\u0436\u0443 \u0439 \u0441\u043f\u0440\u043e\u0431\u0443\u0439 \u0449\u0435 \u0440\u0430\u0437."
            )
            return

        extracted_memory = await _extract_memory_with_fallback(message.text, llm_client)
        if memory_enabled:
            try:
                await memory_store.apply_memory(user_id, extracted_memory)
                await memory_store.append_conversation(
                    user_id,
                    ConversationTurn(
                        user_msg=message.text,
                        bot_response=reply,
                        topics=extracted_memory.topics,
                    ),
                )
            except MemoryUnavailableError:
                logger.warning("MongoDB became unavailable while saving memory.")
                memory_enabled = False

        if memory_enabled:
            await message.answer(reply)
        else:
            await message.answer(reply + "\n\n[\u041f\u0430\u043c'\u044f\u0442\u044c \u0442\u0438\u043c\u0447\u0430\u0441\u043e\u0432\u043e \u043d\u0435\u0434\u043e\u0441\u0442\u0443\u043f\u043d\u0430.]")

    return router
