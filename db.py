from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from pymongo import MongoClient
from pymongo.errors import PyMongoError

from config import Settings
from schemas import ConversationTurn, ExtractedMemory, UserProfile


NAME_QUERY_MARKERS = (
    "\u0456\u043c'\u044f",
    "\u0456\u043c\u044f",
    "\u0437\u0432\u0430\u0442\u0438",
    "\u044f\u043a \u043c\u0435\u043d\u0435 \u0437\u0432\u0430\u0442\u0438",
    "name",
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def is_name_related_query(query: str) -> bool:
    lowered = query.casefold().strip()
    return any(marker in lowered for marker in NAME_QUERY_MARKERS)


def _entry_matches_query(entry: str, query: str, *, name_related: bool) -> bool:
    lowered_entry = entry.casefold()
    lowered_query = query.casefold().strip()

    if name_related and ("name is" in lowered_entry or "\u0437\u0432\u0430\u0442\u0438" in lowered_entry):
        return True

    if not lowered_query:
        return False

    return lowered_query in lowered_entry or lowered_entry in lowered_query


class MemoryUnavailableError(RuntimeError):
    pass


class UserMemoryStore:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = MongoClient(
            settings.mongodb_uri,
            serverSelectionTimeoutMS=settings.mongodb_timeout_ms,
            connectTimeoutMS=settings.mongodb_timeout_ms,
            socketTimeoutMS=settings.mongodb_timeout_ms,
        )
        self._collection = self._client[settings.mongodb_db][settings.mongodb_users_collection]

    def close(self) -> None:
        self._client.close()

    async def ping(self) -> None:
        try:
            await asyncio.to_thread(self._client.admin.command, "ping")
        except PyMongoError as exc:
            raise MemoryUnavailableError("MongoDB is unavailable.") from exc

    async def ensure_user(self, user_id: int, username: str | None) -> None:
        try:
            await asyncio.to_thread(self._ensure_user_sync, user_id, username)
        except PyMongoError as exc:
            raise MemoryUnavailableError("MongoDB is unavailable.") from exc

    def _ensure_user_sync(self, user_id: int, username: str | None) -> None:
        joined = _utc_now().date().isoformat()
        self._collection.update_one(
            {"_id": user_id},
            {
                "$setOnInsert": {
                    "_id": user_id,
                    "joined": joined,
                    "created_at": _utc_now(),
                    "goals": [],
                    "facts": [],
                    "preferences": {
                        "language": self._settings.default_language,
                        "tone": self._settings.default_tone,
                    },
                    "conversation_history": [],
                    "summary": "",
                    "last_topics": [],
                    "messages_count": 0,
                },
                "$set": {"username": username},
            },
            upsert=True,
        )

    async def get_profile(self, user_id: int) -> UserProfile:
        try:
            return await asyncio.to_thread(self._get_profile_sync, user_id)
        except PyMongoError as exc:
            raise MemoryUnavailableError("MongoDB is unavailable.") from exc

    def _get_profile_sync(self, user_id: int) -> UserProfile:
        document = self._collection.find_one({"_id": user_id})
        if not document:
            raise KeyError(f"User {user_id} not found in memory store.")

        document["user_id"] = document.pop("_id")
        return UserProfile.model_validate(document)

    async def get_user_context(self, user_id: int) -> str:
        profile = await self.get_profile(user_id)

        lines: list[str] = []
        if profile.summary:
            lines.append(f"Summary: {profile.summary}")
        if profile.goals:
            lines.append("Goals: " + "; ".join(profile.goals))
        if profile.facts:
            lines.append("Facts: " + "; ".join(profile.facts))
        if profile.preferences:
            prefs = ", ".join(f"{key}={value}" for key, value in profile.preferences.items())
            lines.append(f"Preferences: {prefs}")
        if profile.last_topics:
            lines.append("Recent topics: " + ", ".join(profile.last_topics))

        recent_history = profile.conversation_history[-3:]
        if recent_history:
            history_lines = ["Recent conversation:"]
            for turn in recent_history:
                history_lines.append(f"User: {turn.user_msg}")
                history_lines.append(f"Assistant: {turn.bot_response}")
            lines.extend(history_lines)

        return "\n".join(lines)

    async def apply_memory(self, user_id: int, memory: ExtractedMemory) -> None:
        if not any([memory.facts, memory.goals, memory.preferences, memory.topics]):
            return
        try:
            await asyncio.to_thread(self._apply_memory_sync, user_id, memory)
        except PyMongoError as exc:
            raise MemoryUnavailableError("MongoDB is unavailable.") from exc

    def _apply_memory_sync(self, user_id: int, memory: ExtractedMemory) -> None:
        update: dict[str, object] = {}
        if memory.facts:
            update.setdefault("$addToSet", {})["facts"] = {"$each": memory.facts}
        if memory.goals:
            update.setdefault("$addToSet", {})["goals"] = {"$each": memory.goals}
        if memory.topics:
            update.setdefault("$addToSet", {})["last_topics"] = {"$each": memory.topics}
        if memory.preferences:
            update.setdefault("$set", {}).update(
                {f"preferences.{key}": value for key, value in memory.preferences.items()}
            )

        if update:
            self._collection.update_one({"_id": user_id}, update)
            self._refresh_summary_sync(user_id)

    async def save_explicit_fact(self, user_id: int, fact: str) -> None:
        normalized = fact.strip()
        if not normalized:
            return
        try:
            await asyncio.to_thread(
                self._collection.update_one,
                {"_id": user_id},
                {"$addToSet": {"facts": normalized}},
            )
            await asyncio.to_thread(self._refresh_summary_sync, user_id)
        except PyMongoError as exc:
            raise MemoryUnavailableError("MongoDB is unavailable.") from exc

    async def forget_fact(self, user_id: int, query: str) -> dict[str, list[str]]:
        try:
            removed = await asyncio.to_thread(self._forget_fact_sync, user_id, query)
            await asyncio.to_thread(self._refresh_summary_sync, user_id)
            return removed
        except PyMongoError as exc:
            raise MemoryUnavailableError("MongoDB is unavailable.") from exc

    def _forget_fact_sync(self, user_id: int, query: str) -> dict[str, list[str]]:
        document = self._collection.find_one({"_id": user_id}) or {}
        facts = list(document.get("facts", []))
        goals = list(document.get("goals", []))
        name_related = is_name_related_query(query)

        removed_facts = [entry for entry in facts if _entry_matches_query(entry, query, name_related=name_related)]
        removed_goals = [entry for entry in goals if _entry_matches_query(entry, query, name_related=False)]

        if removed_facts:
            self._collection.update_one({"_id": user_id}, {"$pull": {"facts": {"$in": removed_facts}}})
        if removed_goals:
            self._collection.update_one({"_id": user_id}, {"$pull": {"goals": {"$in": removed_goals}}})

        return {"facts": removed_facts, "goals": removed_goals}

    async def list_memory_items(self, user_id: int) -> dict[str, list[str]]:
        profile = await self.get_profile(user_id)
        return {"facts": profile.facts, "goals": profile.goals}

    async def append_conversation(self, user_id: int, turn: ConversationTurn) -> None:
        try:
            await asyncio.to_thread(self._append_conversation_sync, user_id, turn)
        except PyMongoError as exc:
            raise MemoryUnavailableError("MongoDB is unavailable.") from exc

    def _append_conversation_sync(self, user_id: int, turn: ConversationTurn) -> None:
        self._collection.update_one(
            {"_id": user_id},
            {
                "$push": {
                    "conversation_history": {
                        "$each": [turn.model_dump(mode="json")],
                        "$slice": -self._settings.history_window,
                    }
                },
                "$inc": {"messages_count": 1},
            },
        )

    async def clear_history(self, user_id: int) -> None:
        try:
            await asyncio.to_thread(
                self._collection.update_one,
                {"_id": user_id},
                {"$set": {"conversation_history": [], "last_topics": [], "messages_count": 0}},
            )
        except PyMongoError as exc:
            raise MemoryUnavailableError("MongoDB is unavailable.") from exc

    def _refresh_summary_sync(self, user_id: int) -> None:
        document = self._collection.find_one({"_id": user_id}) or {}
        facts = document.get("facts", [])
        goals = document.get("goals", [])
        prefs = document.get("preferences", {})

        parts: list[str] = []
        if facts:
            parts.append("Facts: " + ", ".join(facts[:4]))
        if goals:
            parts.append("Goals: " + ", ".join(goals[:3]))
        if prefs:
            formatted = ", ".join(f"{key}={value}" for key, value in prefs.items())
            parts.append("Preferences: " + formatted)

        self._collection.update_one({"_id": user_id}, {"$set": {"summary": ". ".join(parts)}})
