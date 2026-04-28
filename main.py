from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.types import BotCommand, BotCommandScopeChat

from config import get_settings
from db import UserMemoryStore
from handlers import build_router
from llm import OpenRouterClient


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)


async def setup_bot_commands(bot: Bot, allowed_user_id: int) -> None:
    commands = [
        BotCommand(command="start", description="Запустити бота і побачити підказки"),
        BotCommand(command="remember", description="Запам'ятати факт про тебе"),
        BotCommand(command="forget", description="Видалити факт з пам'яті"),
        BotCommand(command="facts", description="Показати точний список фактів і цілей"),
        BotCommand(command="summary", description="Показати, що бот про тебе пам'ятає"),
        BotCommand(command="clear", description="Очистити історію діалогу"),
    ]
    await bot.set_my_commands(commands, scope=BotCommandScopeChat(chat_id=allowed_user_id))


async def run() -> None:
    settings = get_settings()
    bot = Bot(token=settings.telegram_token, default=DefaultBotProperties(parse_mode=None))
    dispatcher = Dispatcher()
    memory_store = UserMemoryStore(settings)
    llm_client = OpenRouterClient(settings)

    dispatcher.include_router(build_router(memory_store, llm_client, settings))
    await setup_bot_commands(bot, settings.allowed_telegram_user_id)

    try:
        await dispatcher.start_polling(bot)
    finally:
        await llm_client.close()
        memory_store.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(run())
