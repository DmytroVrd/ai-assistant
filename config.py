from __future__ import annotations

from functools import lru_cache
import os

from dotenv import load_dotenv
from pydantic import BaseModel, Field


load_dotenv()


class Settings(BaseModel):
    telegram_token: str = Field(alias="TELEGRAM_TOKEN")
    allowed_telegram_user_id: int = Field(alias="ALLOWED_TELEGRAM_USER_ID")
    openrouter_api_key: str = Field(alias="OPENROUTER_API_KEY")
    openrouter_model: str = Field(default="openai/gpt-4o-mini", alias="OPENROUTER_MODEL")
    mongodb_uri: str = Field(default="mongodb://localhost:27017", alias="MONGODB_URI")
    mongodb_db: str = Field(default="telegram_ai_assistant", alias="MONGODB_DB")
    mongodb_users_collection: str = Field(default="users", alias="MONGODB_USERS_COLLECTION")
    mongodb_timeout_ms: int = Field(default=1500, alias="MONGODB_TIMEOUT_MS")
    app_name: str = Field(default="telegram-ai-assistant", alias="APP_NAME")
    openrouter_site_url: str = Field(default="https://github.com/your-username/telegram-ai-assistant", alias="OPENROUTER_SITE_URL")
    default_language: str = Field(default="en", alias="DEFAULT_LANGUAGE")
    default_tone: str = Field(default="friendly", alias="DEFAULT_TONE")
    history_window: int = Field(default=20, alias="HISTORY_WINDOW")
    request_timeout_seconds: float = Field(default=45, alias="REQUEST_TIMEOUT_SECONDS")

    @classmethod
    def from_env(cls) -> "Settings":
        required = ("TELEGRAM_TOKEN", "ALLOWED_TELEGRAM_USER_ID", "OPENROUTER_API_KEY")
        missing = [name for name in required if not os.getenv(name)]
        if missing:
            joined = ", ".join(missing)
            raise RuntimeError(
                f"Missing required environment variables: {joined}. Fill in .env first."
            )

        raw_values = {
            field.alias: os.getenv(field.alias)
            for field in cls.model_fields.values()
            if os.getenv(field.alias) is not None
        }
        return cls.model_validate(raw_values)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()
