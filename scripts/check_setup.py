from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import get_settings
from db import MemoryUnavailableError, UserMemoryStore
from llm import OpenRouterClient


async def check_mongodb() -> tuple[bool, str]:
    settings = get_settings()
    store = UserMemoryStore(settings)
    try:
        await store.ping()
        return True, "MongoDB connection OK"
    except MemoryUnavailableError as exc:
        return False, f"MongoDB check failed: {exc}"
    finally:
        store.close()


async def check_openrouter() -> tuple[bool, str]:
    settings = get_settings()
    client = OpenRouterClient(settings)
    try:
        reply = await client.generate_reply(
            "Reply with one short greeting in Ukrainian.",
            "No saved context yet.",
        )
        memory = await client.extract_memory(
            "Мене звати Дмитро, мені 17 років. Я хочу вивчити AI і Python."
        )
        preview = reply.encode("ascii", "backslashreplace").decode("ascii")
        return True, (
            f"OpenRouter reply OK: {preview[:80]} | "
            f"memory facts={len(memory.facts)} goals={len(memory.goals)} topics={len(memory.topics)}"
        )
    except Exception as exc:
        return False, f"OpenRouter check failed: {type(exc).__name__}: {exc}"
    finally:
        await client.close()


async def main() -> None:
    settings = get_settings()
    print("Loaded settings:")
    print(f"- ALLOWED_TELEGRAM_USER_ID={settings.allowed_telegram_user_id}")
    print(f"- OPENROUTER_MODEL={settings.openrouter_model}")
    print(f"- MONGODB_URI={settings.mongodb_uri}")
    print(f"- MONGODB_DB={settings.mongodb_db}")
    print(f"- MONGODB_USERS_COLLECTION={settings.mongodb_users_collection}")

    mongo_ok, mongo_message = await check_mongodb()
    openrouter_ok, openrouter_message = await check_openrouter()

    print()
    print(mongo_message)
    print(openrouter_message)

    if mongo_ok and openrouter_ok:
        print("\nSetup looks good. Memory should work after you restart the bot.")
    elif openrouter_ok:
        print("\nAI replies work, but memory storage is offline.")
    else:
        print("\nSetup is incomplete. Fix the failed checks above.")


if __name__ == "__main__":
    asyncio.run(main())
