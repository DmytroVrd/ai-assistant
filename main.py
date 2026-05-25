from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from config import get_settings
from db import UserMemoryStore
from handlers import build_router
from i18n import command_definitions, normalize_language
from llm import OpenRouterClient


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)


async def setup_bot_commands(bot: Bot, language: str) -> None:
    await bot.set_my_commands(command_definitions(language))


async def run() -> None:
    settings = get_settings()
    bot = Bot(token=settings.telegram_token, default=DefaultBotProperties(parse_mode=None))
    dispatcher = Dispatcher()
    memory_store = UserMemoryStore(settings)
    llm_client = OpenRouterClient(settings)

    dispatcher.include_router(build_router(memory_store, llm_client, settings))
    await setup_bot_commands(
        bot,
        normalize_language(settings.default_language, "en"),
    )

    try:
        await dispatcher.start_polling(bot)
    finally:
        await llm_client.close()
        memory_store.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(run())
