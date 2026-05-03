# Telegram AI-асистент з пам'яттю

[English version](README.md)

Телеграм-бот на `aiogram`, який відповідає через `OpenRouter`, зберігає контекст користувача в `MongoDB` і використовує цю пам'ять для персоналізованих відповідей.

## Що вміє

- відповідає на повідомлення через LLM
- запам'ятовує факти, цілі, теми та коротку історію діалогу
- використовує пам'ять у наступних відповідях
- підтримує `/remember`, `/forget`, `/facts`, `/summary`, `/clear`, `/language`
- має англійський і український інтерфейс бота
- працює тільки для дозволеного Telegram user id

## Стек

- Python 3
- aiogram
- OpenRouter API
- MongoDB Atlas / MongoDB
- pytest

## Архітектура

```text
Telegram -> aiogram handlers -> MongoDB context -> OpenRouter -> reply -> MongoDB update
```

## Структура проекту

- `main.py` — запуск бота та реєстрація Telegram-команд
- `config.py` — конфігурація через `.env`
- `handlers.py` — логіка команд і обробка повідомлень
- `i18n.py` — переклади інтерфейсу та описів команд
- `db.py` — робота з MongoDB та пам'яттю
- `llm.py` — клієнт OpenRouter
- `memory.py` — евристики для витягування фактів
- `schemas.py` — Pydantic-моделі
- `scripts/check_setup.py` — швидка перевірка конфігурації
- `tests/` — базові тести

## Швидкий запуск

1. Створи та активуй віртуальне середовище.
2. Встанови залежності:

```bash
pip install -r requirements.txt
```

3. Скопіюй `.env.example` у `.env`.
4. Заповни токен Telegram-бота, ключ OpenRouter і рядок підключення до MongoDB Atlas.
5. Перевір налаштування:

```bash
python scripts/check_setup.py
```

6. Запусти бота:

```bash
python main.py
```

## Змінні середовища

```env
TELEGRAM_TOKEN=your-telegram-bot-token
ALLOWED_TELEGRAM_USER_ID=123456789
OPENROUTER_API_KEY=your-openrouter-api-key
OPENROUTER_MODEL=openai/gpt-oss-120b:free
MONGODB_URI=mongodb+srv://USERNAME:PASSWORD@cluster0.example.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0
MONGODB_DB=telegram_ai_assistant
MONGODB_USERS_COLLECTION=users
MONGODB_TIMEOUT_MS=5000
APP_NAME=telegram-ai-assistant
OPENROUTER_SITE_URL=https://github.com/DmytroVrd/ai-assiastant
DEFAULT_LANGUAGE=en
DEFAULT_TONE=friendly
HISTORY_WINDOW=20
REQUEST_TIMEOUT_SECONDS=45
```

## MongoDB Atlas

Щоб пам'ять працювала стабільно:

- додай свій поточний IP у `Network Access`
- перевір правильність `database user` і пароля
- встав повний `mongodb+srv://...` рядок у `.env`
- після зміни IP або мережі за потреби онови allowlist в Atlas

## Команди

- `/start` — старт і коротка інструкція
- `/remember <факт>` — явно зберегти факт
- `/forget <запит>` — видалити факт або групу фактів
- `/facts` — показати, що саме зараз лежить у пам'яті
- `/summary` — короткий підсумок пам'яті про користувача
- `/clear` — очистити історію діалогу, не видаляючи довготривалу пам'ять
- `/language <en|uk>` — змінити мову інтерфейсу бота

## Демонстрація

Типовий сценарій:

1. Користувач запускає `/start`
2. Зберігає факт через `/remember`
3. Бот записує факт у MongoDB
4. На наступне питання бот відповідає вже з урахуванням контексту
5. Через `/facts` або `/summary` можна побачити, що саме збережено
6. Через `/language uk` або `/language en` можна перемикати мову інтерфейсу

## Скріншоти

Для англомовного GitHub README використовуються ті самі файли з `docs/screenshots/`:

- `start.png`
- `remember-and-reply.png`
- `facts.png`
- `forget.png`
- `clear.png`

| Старт | Запам'ятовування і персоналізація |
| --- | --- |
| ![Start](docs/screenshots/start-en.png) | ![Remember and reply](docs/screenshots/remember-and-reply-en.png) |

| Збережені факти | Видалення фактів |
| --- | --- |
| ![Facts](docs/screenshots/facts-en2.png) | ![Forget](docs/screenshots/forget-en.png) |

| Очищення історії |
| --- |
| ![Clear](docs/screenshots/clear-en.png) |

## Приклад документа в MongoDB

```json
{
  "_id": 123456789,
  "username": "dima123",
  "created_at": "2026-04-28T12:00:00Z",
  "facts": [
    "User's name is Dmytro",
    "User is interested in Python and AI"
  ],
  "goals": [
    "Вивчити AI",
    "Зібрати AI-портфоліо з практичних проектів"
  ],
  "preferences": {
    "language": "en",
    "tone": "friendly"
  },
  "last_topics": ["AI", "Python"],
  "messages_count": 12
}
```

## Тестування

```bash
python -m pytest
```

## Репозиторій

[GitHub repository](https://github.com/DmytroVrd/ai-assiastant)

## Що демонструє проект

- інтеграцію Telegram Bot API через `aiogram`
- роботу з LLM через OpenRouter
- двомовний UX бота з пам'яттю та преференціями
- зберігання контексту користувача в MongoDB
- продуктову логіку навколо AI-асистента, а не просто один API-виклик
