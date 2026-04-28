# Telegram AI Assistant with Memory

Telegram bot on `aiogram` that answers through OpenRouter and stores user memory in MongoDB.

## What it can do

- answer chat messages with an LLM
- remember explicit facts via `/remember`
- keep user memory: goals, facts, preferences, recent topics, and short history
- show saved memory via `/summary`
- remove saved facts with `/forget`
- clear only chat history with `/clear`

## Project structure

- `main.py` - app entrypoint and bot startup
- `config.py` - environment config loading and validation
- `handlers.py` - Telegram command and message handlers
- `db.py` - MongoDB memory store
- `llm.py` - OpenRouter client
- `memory.py` - heuristic memory extraction helpers
- `schemas.py` - Pydantic models
- `scripts/check_setup.py` - smoke test for env, OpenRouter, and MongoDB
- `tests/` - basic tests for memory extraction

## Quick start

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env` and fill in your values.
4. Configure MongoDB:

- local MongoDB: keep `MONGODB_URI=mongodb://localhost:27017`
- MongoDB Atlas: paste your `mongodb+srv://...` connection string into `MONGODB_URI`

5. Run a setup smoke test:

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
ALLOWED_TELEGRAM_USER_ID=6677896612
OPENROUTER_API_KEY=your-openrouter-api-key
OPENROUTER_MODEL=openai/gpt-4o-mini
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB=telegram_ai_assistant
MONGODB_USERS_COLLECTION=users
MONGODB_TIMEOUT_MS=1500
APP_NAME=telegram-ai-assistant
OPENROUTER_SITE_URL=https://github.com/your-username/telegram-ai-assistant
DEFAULT_LANGUAGE=uk
DEFAULT_TONE=friendly
HISTORY_WINDOW=20
REQUEST_TIMEOUT_SECONDS=45
```

## MongoDB options

### Local MongoDB

```env
MONGODB_URI=mongodb://localhost:27017
```

### MongoDB Atlas

```env
MONGODB_URI=mongodb+srv://USERNAME:PASSWORD@cluster0.example.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0
```

When using Atlas, make sure:

- your current IP address is allowed in Atlas Network Access
- your database user and password are correct
- you pasted the full `mongodb+srv://...` string into `.env`

## Example user document

```json
{
  "_id": 123456789,
  "username": "dima123",
  "joined": "2026-04-28",
  "goals": ["Вивчити Python", "Зібрати AI-портфоліо"],
  "facts": ["User's name is Дмитро", "User is 17 years old"],
  "preferences": {"language": "uk", "tone": "friendly"},
  "last_topics": ["Python", "AI"],
  "messages_count": 12
}
```

## Suggested demo flow

1. `/start`
2. `/remember Мене звати Дмитро, мені 17 років`
3. `Я хочу вивчити AI та зібрати портфоліо з 4 проектів`
4. `/summary`
5. `Що мені вчити далі?`

This clearly shows that the assistant uses memory and not only raw chat completions.

## Testing

```bash
python -m pytest
```

## Notes

- The bot uses polling by default because it is the fastest way to ship a portfolio version.
- Memory extraction combines simple heuristics with LLM extraction for better personalization.
- `/clear` removes dialog history but keeps long-term memory.
