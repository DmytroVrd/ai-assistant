# Telegram AI Assistant with Memory

[Українська версія](README.md)

Telegram bot built with `aiogram` that answers via `OpenRouter`, stores user context in `MongoDB`, and uses that memory to produce personalized replies.

## Features

- answers user messages through an LLM
- stores facts, goals, topics, and short conversation history
- uses saved memory in later replies
- supports `/remember`, `/forget`, `/facts`, `/summary`, `/clear`
- restricts access to an allowed Telegram user id

## Tech stack

- Python 3
- aiogram
- OpenRouter API
- MongoDB Atlas / MongoDB
- pytest

## Architecture

```text
Telegram -> aiogram handlers -> MongoDB context -> OpenRouter -> reply -> MongoDB update
```

## Project structure

- `main.py` — bot startup and Telegram command registration
- `config.py` — environment-based settings
- `handlers.py` — commands and message handling logic
- `db.py` — MongoDB memory backend
- `llm.py` — OpenRouter client
- `memory.py` — heuristic fact extraction
- `schemas.py` — Pydantic models
- `scripts/check_setup.py` — setup smoke test
- `tests/` — basic tests

## Quick start

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env`.
4. Fill in your Telegram bot token, OpenRouter key, and MongoDB Atlas connection string.
5. Run the setup check:

```bash
python scripts/check_setup.py
```

6. Start the bot:

```bash
python main.py
```

## Environment variables

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
DEFAULT_LANGUAGE=uk
DEFAULT_TONE=friendly
HISTORY_WINDOW=20
REQUEST_TIMEOUT_SECONDS=45
```

## MongoDB Atlas notes

To keep memory working reliably:

- add your current IP to `Network Access`
- verify the database username and password
- paste the full `mongodb+srv://...` string into `.env`
- if your IP or network changes, update the Atlas allowlist

## Commands

- `/start` — start the bot and show a short intro
- `/remember <fact>` — store a fact explicitly
- `/forget <query>` — remove a fact or a group of matching facts
- `/facts` — show the exact items stored in memory
- `/summary` — show a short user memory summary
- `/clear` — clear dialog history without removing long-term memory

## Demo flow

Typical flow:

1. The user starts the bot with `/start`
2. Stores a fact with `/remember`
3. The bot writes that fact into MongoDB
4. On the next question, the bot answers using the saved context
5. `/facts` and `/summary` show what was stored

## Screenshots

Place screenshots into `docs/screenshots/` with these names:

- `start.png`
- `remember-and-reply.png`
- `facts.png`
- `forget.png`
- `clear.png`

Once added, they will render automatically in this README.

| Start | Remember and personalized reply |
| --- | --- |
| ![Start](docs/screenshots/start.png) | ![Remember and reply](docs/screenshots/remember-and-reply.png) |

| Stored facts | Forget flow |
| --- | --- |
| ![Facts](docs/screenshots/facts.png) | ![Forget](docs/screenshots/forget.png) |

| Clear history |
| --- |
| ![Clear](docs/screenshots/clear.png) |

## Example MongoDB document

```json
{
  "_id": 123456789,
  "username": "dima123",
  "created_at": "2026-04-28T12:00:00Z",
  "facts": [
    "User's name is Дмитро",
    "User is interested in Python and AI"
  ],
  "goals": [
    "Learn AI",
    "Build a portfolio of 4 projects"
  ],
  "preferences": {
    "language": "uk",
    "tone": "friendly"
  },
  "last_topics": ["AI", "Python"],
  "messages_count": 12
}
```

## Testing

```bash
python -m pytest
```

## Repository

[GitHub repository](https://github.com/DmytroVrd/ai-assiastant)

## What this project demonstrates

- Telegram Bot API integration with `aiogram`
- LLM integration through OpenRouter
- personalized responses based on stored memory
- MongoDB-backed user context storage
- product-oriented AI logic beyond a single chat completion call
