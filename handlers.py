from __future__ import annotations

import logging

from aiogram import Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import BotCommandScopeChat, Message

from config import Settings
from db import MemoryUnavailableError, UserMemoryStore, is_name_related_query
from formatting import telegram_html_from_markdown
from i18n import command_definitions, normalize_language, t
from llm import OpenRouterClient
from schemas import ConversationTurn, ExtractedMemory


logger = logging.getLogger(__name__)

NAME_FORGET_PATTERNS = (
    "забудь як мене звати",
    "забудь моє ім'я",
    "забудь мое імя",
    "forget my name",
    "forget what my name is",
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
        return "name"
    if lowered.startswith("забудь "):
        payload = text.strip()[len("забудь ") :].strip()
        return payload or None
    if lowered.startswith("forget "):
        payload = text.strip()[len("forget ") :].strip()
        return payload or None
    return None


async def _ensure_user_identity(message: Message, settings: Settings) -> bool:
    identity = _get_user_identity(message)
    fallback_language = normalize_language(settings.default_language, "en")
    if not identity:
        await message.answer(t(fallback_language, "identity_error"))
        return False

    return True


async def _get_user_language(
    memory_store: UserMemoryStore,
    settings: Settings,
    user_id: int | None = None,
) -> str:
    fallback = normalize_language(settings.default_language, "en")
    if user_id is None:
        return fallback
    try:
        profile = await memory_store.get_profile(user_id)
    except Exception:
        return fallback
    return normalize_language(profile.preferences.get("language"), fallback)


async def _set_command_language(message: Message, user_id: int, language: str) -> None:
    await message.bot.set_my_commands(
        command_definitions(language),
        scope=BotCommandScopeChat(chat_id=user_id),
    )


async def _extract_memory(user_message: str, llm_client: OpenRouterClient) -> ExtractedMemory:
    return await llm_client.extract_memory(user_message)


async def _extract_memory_with_fallback(user_message: str, llm_client: OpenRouterClient) -> ExtractedMemory:
    try:
        return await _extract_memory(user_message, llm_client)
    except Exception:
        logger.exception("LLM memory extraction failed; skipping automatic memory update.")
        return ExtractedMemory()


def _format_removed_items(language: str, removed: dict[str, list[str]]) -> str:
    pieces: list[str] = []
    if removed["facts"]:
        label = "facts" if language == "en" else "факти"
        pieces.append(f"{label}: " + "; ".join(removed["facts"]))
    if removed["goals"]:
        label = "goals" if language == "en" else "цілі"
        pieces.append(f"{label}: " + "; ".join(removed["goals"]))
    return "\n".join(pieces)


def _render_memory_list(language: str, items: list[str], empty_key: str, section_key: str) -> list[str]:
    if items:
        lines = [t(language, section_key)]
        lines.extend(f"  {index}. {item}" for index, item in enumerate(items, start=1))
        return lines
    return [t(language, empty_key)]


async def _perform_forget(
    message: Message,
    memory_store: UserMemoryStore,
    settings: Settings,
    query: str,
) -> None:
    identity = _get_user_identity(message)
    fallback_language = normalize_language(settings.default_language, "en")
    if not identity:
        await message.answer(t(fallback_language, "identity_error"))
        return

    user_id, username = identity
    language = await _get_user_language(memory_store, settings, user_id)
    try:
        await memory_store.ensure_user(user_id, username)
        removed = await memory_store.forget_fact(user_id, query)
    except MemoryUnavailableError:
        await message.answer(t(language, "forget_offline"))
        return

    if removed["facts"] or removed["goals"]:
        details = _format_removed_items(language, removed)
        if details:
            await message.answer(t(language, "forget_done_with_details", details=details))
        else:
            await message.answer(t(language, "forget_done"))
        return

    if is_name_related_query(query):
        await message.answer(t(language, "forget_name_missing"))
    else:
        await message.answer(t(language, "forget_no_match"))


def build_router(
    memory_store: UserMemoryStore,
    llm_client: OpenRouterClient,
    settings: Settings,
) -> Router:
    router = Router(name="assistant")

    @router.message(Command("start"))
    async def start_handler(message: Message) -> None:
        if not await _ensure_user_identity(message, settings):
            return

        identity = _get_user_identity(message)
        fallback_language = normalize_language(settings.default_language, "en")
        if not identity:
            await message.answer(t(fallback_language, "identity_error"))
            return

        user_id, username = identity
        try:
            await memory_store.ensure_user(user_id, username)
            language = await _get_user_language(memory_store, settings, user_id)
            await _set_command_language(message, user_id, language)
        except MemoryUnavailableError:
            logger.warning("MongoDB unavailable during /start.")
            await message.answer(t(fallback_language, "start_offline"))
            return

        await message.answer(t(language, "start_online"))

    @router.message(Command("language", "lang"))
    async def language_handler(message: Message) -> None:
        if not await _ensure_user_identity(message, settings):
            return

        payload = _command_payload(message).strip().casefold()
        fallback_language = normalize_language(settings.default_language, "en")
        if not payload:
            await message.answer(t(fallback_language, "language_example"))
            return

        language = normalize_language(payload, "")
        if language not in ("en", "uk"):
            await message.answer(t(fallback_language, "language_invalid"))
            return

        identity = _get_user_identity(message)
        if not identity:
            await message.answer(t(fallback_language, "identity_error"))
            return

        user_id, username = identity
        try:
            await memory_store.ensure_user(user_id, username)
            await memory_store.apply_memory(user_id, ExtractedMemory(preferences={"language": language}))
            await _set_command_language(message, user_id, language)
        except MemoryUnavailableError:
            await message.answer(t(fallback_language, "remember_offline"))
            return

        await message.answer(t(language, "language_saved"))

    @router.message(Command("remember"))
    async def remember_handler(message: Message) -> None:
        if not await _ensure_user_identity(message, settings):
            return

        identity = _get_user_identity(message)
        fallback_language = normalize_language(settings.default_language, "en")
        user_id = identity[0] if identity else None
        language = await _get_user_language(memory_store, settings, user_id)

        payload = _command_payload(message)
        if not payload:
            await message.answer(t(language, "remember_example"))
            return

        if not identity:
            await message.answer(t(fallback_language, "identity_error"))
            return

        user_id, username = identity
        try:
            await memory_store.ensure_user(user_id, username)
            extracted_memory = await _extract_memory_with_fallback(payload, llm_client)
            await memory_store.apply_memory(user_id, extracted_memory)
            if not any(
                [
                    extracted_memory.facts,
                    extracted_memory.goals,
                    extracted_memory.preferences,
                ]
            ):
                await memory_store.save_explicit_fact(user_id, payload)
            if "language" in extracted_memory.preferences:
                language = normalize_language(extracted_memory.preferences["language"], language)
                await _set_command_language(message, user_id, language)
        except MemoryUnavailableError:
            await message.answer(t(language, "remember_offline"))
            return

        await message.answer(t(language, "remember_saved"))

    @router.message(Command("forget"))
    async def forget_handler(message: Message) -> None:
        if not await _ensure_user_identity(message, settings):
            return

        identity = _get_user_identity(message)
        language = await _get_user_language(memory_store, settings, identity[0] if identity else None)
        payload = _command_payload(message)
        if not payload:
            await message.answer(t(language, "forget_example"))
            return

        await _perform_forget(message, memory_store, settings, payload)

    @router.message(Command("facts"))
    async def facts_handler(message: Message) -> None:
        if not await _ensure_user_identity(message, settings):
            return

        identity = _get_user_identity(message)
        fallback_language = normalize_language(settings.default_language, "en")
        if not identity:
            await message.answer(t(fallback_language, "identity_error"))
            return

        user_id, username = identity
        language = await _get_user_language(memory_store, settings, user_id)
        try:
            await memory_store.ensure_user(user_id, username)
            items = await memory_store.list_memory_items(user_id)
        except MemoryUnavailableError:
            await message.answer(t(language, "facts_offline"))
            return

        lines = [t(language, "facts_title")]
        lines.extend(_render_memory_list(language, items["facts"], "facts_empty", "facts_section"))
        lines.extend(_render_memory_list(language, items["goals"], "goals_empty", "goals_section"))
        await message.answer("\n".join(lines))

    @router.message(Command("summary"))
    async def summary_handler(message: Message) -> None:
        if not await _ensure_user_identity(message, settings):
            return

        identity = _get_user_identity(message)
        fallback_language = normalize_language(settings.default_language, "en")
        if not identity:
            await message.answer(t(fallback_language, "identity_error"))
            return

        user_id, username = identity
        language = await _get_user_language(memory_store, settings, user_id)
        try:
            await memory_store.ensure_user(user_id, username)
            profile = await memory_store.get_profile(user_id)
        except MemoryUnavailableError:
            await message.answer(t(language, "summary_offline"))
            return

        none_text = t(language, "summary_none")
        preferences_value = (
            ", ".join(f"{key}={value}" for key, value in profile.preferences.items())
            if profile.preferences
            else none_text
        )
        lines = [
            t(language, "summary_title"),
            t(language, "summary_username", username=profile.username) if profile.username else t(language, "summary_username_empty"),
            t(language, "summary_goals", value=", ".join(profile.goals) if profile.goals else none_text),
            t(language, "summary_facts", value=", ".join(profile.facts) if profile.facts else none_text),
            t(language, "summary_preferences", value=preferences_value),
            t(language, "summary_topics", value=", ".join(profile.last_topics) if profile.last_topics else none_text),
            t(language, "summary_messages", value=profile.messages_count),
        ]
        await message.answer("\n".join(lines))

    @router.message(Command("clear"))
    async def clear_handler(message: Message) -> None:
        if not await _ensure_user_identity(message, settings):
            return

        identity = _get_user_identity(message)
        fallback_language = normalize_language(settings.default_language, "en")
        if not identity:
            await message.answer(t(fallback_language, "identity_error"))
            return

        user_id, username = identity
        language = await _get_user_language(memory_store, settings, user_id)
        try:
            await memory_store.ensure_user(user_id, username)
            await memory_store.clear_history(user_id)
        except MemoryUnavailableError:
            await message.answer(t(language, "clear_offline"))
            return

        await message.answer(t(language, "clear_done"))

    @router.message()
    async def chat_handler(message: Message) -> None:
        if not await _ensure_user_identity(message, settings):
            return

        if not message.text or not message.from_user:
            await message.answer(t(normalize_language(settings.default_language, "en"), "text_only"))
            return

        natural_forget_query = _natural_forget_query(message.text)
        if natural_forget_query is not None:
            await _perform_forget(message, memory_store, settings, natural_forget_query)
            return

        user_id = message.from_user.id
        username = message.from_user.username
        language = await _get_user_language(memory_store, settings, user_id)
        user_context = ""
        memory_enabled = True
        try:
            await memory_store.ensure_user(user_id, username)
            user_context = await memory_store.get_user_context(user_id)
            language = await _get_user_language(memory_store, settings, user_id)
        except MemoryUnavailableError:
            memory_enabled = False
            logger.warning("MongoDB unavailable during chat handling; continuing without memory.")

        try:
            if memory_enabled:
                result = await llm_client.generate_reply_with_memory(
                    message.text,
                    user_context,
                    language=language,
                )
                reply = result.reply
                extracted_memory = result.memory
                logger.info(
                    "LLM memory extraction for user %s: facts=%s goals=%s preferences=%s topics=%s",
                    user_id,
                    len(extracted_memory.facts),
                    len(extracted_memory.goals),
                    len(extracted_memory.preferences),
                    len(extracted_memory.topics),
                )
            else:
                reply = await llm_client.generate_reply(message.text, user_context, language=language)
                extracted_memory = ExtractedMemory()
        except Exception:
            logger.exception("Failed to generate assistant reply.")
            await message.answer(t(language, "reply_error"))
            return

        if not memory_enabled:
            final_reply = reply + "\n\n" + t(language, "memory_suffix")
            await message.answer(telegram_html_from_markdown(final_reply), parse_mode=ParseMode.HTML)
            return

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
            if "language" in extracted_memory.preferences:
                language = normalize_language(extracted_memory.preferences["language"], language)
                await _set_command_language(message, user_id, language)
        except MemoryUnavailableError:
            logger.warning("MongoDB became unavailable while saving memory.")
            memory_enabled = False

        final_reply = reply if memory_enabled else reply + "\n\n" + t(language, "memory_suffix")
        await message.answer(telegram_html_from_markdown(final_reply), parse_mode=ParseMode.HTML)

    return router
