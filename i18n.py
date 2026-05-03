from __future__ import annotations

from aiogram.types import BotCommand


SUPPORTED_LANGUAGES = ("en", "uk")


TRANSLATIONS = {
    "en": {
        "access_denied": "This bot is available only to the owner.",
        "identity_error": "Failed to identify the user for this message.",
        "memory_offline": "Memory storage is temporarily unavailable.",
        "start_online": (
            "Hi! I am an AI assistant with memory.\n"
            "I can answer questions, remember facts about you, and use them in later replies.\n\n"
            "Commands: /remember, /forget, /facts, /summary, /clear, /language"
        ),
        "start_offline": (
            "Hi! I am an AI assistant with memory.\n"
            "Memory storage is currently unavailable, so I can still chat with you, "
            "but I cannot save new facts until MongoDB is back.\n\n"
            "Commands: /remember, /forget, /facts, /summary, /clear, /language"
        ),
        "remember_example": "Example: /remember I have been studying Python for 3 months",
        "remember_saved": "Saved. I will keep that in mind in future replies.",
        "remember_offline": "Memory storage is temporarily unavailable. I cannot save anything right now.",
        "forget_example": "Example: /forget Python or /forget name",
        "forget_done_with_details": "Done, I removed this from memory:\n{details}",
        "forget_done": "Done, I removed it from memory.",
        "forget_name_missing": "I could not find a saved name in memory.",
        "forget_no_match": "I could not find matching facts or goals in memory.",
        "forget_offline": "Memory storage is temporarily unavailable. I cannot update memory right now.",
        "facts_title": "Here is what is currently stored in memory:",
        "facts_section": "- Facts:",
        "facts_empty": "- Facts: nothing saved yet",
        "goals_section": "- Goals:",
        "goals_empty": "- Goals: nothing saved yet",
        "facts_offline": "Memory storage is temporarily unavailable. I cannot show memory right now.",
        "summary_title": "Here is what I currently remember about you:",
        "summary_username": "- Username: @{username}",
        "summary_username_empty": "- Username: not provided",
        "summary_goals": "- Goals: {value}",
        "summary_facts": "- Facts: {value}",
        "summary_preferences": "- Preferences: {value}",
        "summary_topics": "- Recent topics: {value}",
        "summary_messages": "- Messages in memory: {value}",
        "summary_none": "nothing saved yet",
        "summary_offline": "Memory storage is temporarily unavailable. I cannot show saved data right now.",
        "clear_done": "Conversation history was cleared. Facts, goals, and preferences were kept.",
        "clear_offline": "Memory storage is temporarily unavailable. I cannot clear history right now.",
        "text_only": "For now I only work with text messages.",
        "reply_error": "I could not get a reply from the AI right now. Check the OpenRouter key, model, or network and try again.",
        "memory_suffix": "[Memory is temporarily unavailable.]",
        "language_example": "Example: /language en or /language uk",
        "language_invalid": "Supported languages: en, uk.",
        "language_saved": "Language updated. I will speak English from now on.",
        "commands_start": "Start the bot and show help",
        "commands_remember": "Save a fact about you",
        "commands_forget": "Remove a fact from memory",
        "commands_facts": "Show stored facts and goals",
        "commands_summary": "Show what the bot remembers",
        "commands_clear": "Clear chat history",
        "commands_language": "Switch bot language",
    },
    "uk": {
        "access_denied": "Цей бот доступний тільки власнику.",
        "identity_error": "Не вдалося визначити користувача для цього повідомлення.",
        "memory_offline": "Сховище пам'яті тимчасово недоступне.",
        "start_online": (
            "Привіт! Я AI-асистент з пам'яттю.\n"
            "Я можу відповідати на питання, запам'ятовувати факти про тебе і використовувати їх у наступних відповідях.\n\n"
            "Команди: /remember, /forget, /facts, /summary, /clear, /language"
        ),
        "start_offline": (
            "Привіт! Я AI-асистент з пам'яттю.\n"
            "Зараз сховище пам'яті недоступне, тому я можу спілкуватися, але не збережу нові факти, поки MongoDB не відновиться.\n\n"
            "Команди: /remember, /forget, /facts, /summary, /clear, /language"
        ),
        "remember_example": "Приклад: /remember Я вивчаю Python вже 3 місяці",
        "remember_saved": "Запам'ятав. Врахую це в наступних відповідях.",
        "remember_offline": "Сховище пам'яті тимчасово недоступне. Зараз я не можу нічого зберегти.",
        "forget_example": "Приклад: /forget Python або /forget ім'я",
        "forget_done_with_details": "Готово, я прибрав з пам'яті:\n{details}",
        "forget_done": "Готово, я прибрав це з пам'яті.",
        "forget_name_missing": "Не знайшов збережене ім'я у пам'яті.",
        "forget_no_match": "Не знайшов підходящі факти або цілі у пам'яті.",
        "forget_offline": "Сховище пам'яті тимчасово недоступне. Зараз я не можу змінити пам'ять.",
        "facts_title": "Ось що саме лежить у пам'яті:",
        "facts_section": "- Факти:",
        "facts_empty": "- Факти: поки немає",
        "goals_section": "- Цілі:",
        "goals_empty": "- Цілі: поки немає",
        "facts_offline": "Сховище пам'яті тимчасово недоступне. Зараз я не можу показати пам'ять.",
        "summary_title": "Ось що я зараз про тебе пам'ятаю:",
        "summary_username": "- Username: @{username}",
        "summary_username_empty": "- Username: не вказано",
        "summary_goals": "- Цілі: {value}",
        "summary_facts": "- Факти: {value}",
        "summary_preferences": "- Преференції: {value}",
        "summary_topics": "- Останні теми: {value}",
        "summary_messages": "- Повідомлень у пам'яті: {value}",
        "summary_none": "поки немає",
        "summary_offline": "Сховище пам'яті тимчасово недоступне. Зараз я не можу показати збережені дані.",
        "clear_done": "Історію діалогу очищено. Факти, цілі й преференції я залишив.",
        "clear_offline": "Сховище пам'яті тимчасово недоступне. Зараз я не можу очистити історію.",
        "text_only": "Поки що я працюю тільки з текстовими повідомленнями.",
        "reply_error": "Зараз не вдалося отримати відповідь від AI. Перевір OpenRouter ключ, модель або мережу й спробуй ще раз.",
        "memory_suffix": "[Пам'ять тимчасово недоступна.]",
        "language_example": "Приклад: /language en або /language uk",
        "language_invalid": "Підтримувані мови: en, uk.",
        "language_saved": "Мову змінено. Відтепер я відповідатиму українською.",
        "commands_start": "Запустити бота і побачити підказки",
        "commands_remember": "Запам'ятати факт про тебе",
        "commands_forget": "Видалити факт з пам'яті",
        "commands_facts": "Показати список фактів і цілей",
        "commands_summary": "Показати, що бот про тебе пам'ятає",
        "commands_clear": "Очистити історію діалогу",
        "commands_language": "Змінити мову бота",
    },
}


def normalize_language(value: str | None, fallback: str = "en") -> str:
    candidate = (value or "").strip().casefold()
    return candidate if candidate in SUPPORTED_LANGUAGES else fallback


def t(language: str, key: str, **kwargs: object) -> str:
    normalized = normalize_language(language)
    template = TRANSLATIONS[normalized][key]
    return template.format(**kwargs)


def command_definitions(language: str) -> list[BotCommand]:
    normalized = normalize_language(language)
    return [
        BotCommand(command="start", description=t(normalized, "commands_start")),
        BotCommand(command="remember", description=t(normalized, "commands_remember")),
        BotCommand(command="forget", description=t(normalized, "commands_forget")),
        BotCommand(command="facts", description=t(normalized, "commands_facts")),
        BotCommand(command="summary", description=t(normalized, "commands_summary")),
        BotCommand(command="clear", description=t(normalized, "commands_clear")),
        BotCommand(command="language", description=t(normalized, "commands_language")),
    ]
