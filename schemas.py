from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class ConversationTurn(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    user_msg: str
    bot_response: str
    topics: list[str] = Field(default_factory=list)


class ExtractedMemory(BaseModel):
    facts: list[str] = Field(default_factory=list)
    goals: list[str] = Field(default_factory=list)
    preferences: dict[str, str] = Field(default_factory=dict)
    topics: list[str] = Field(default_factory=list)


class AssistantResult(BaseModel):
    reply: str
    memory: ExtractedMemory = Field(default_factory=ExtractedMemory)


class UserProfile(BaseModel):
    user_id: int
    username: str | None = None
    joined: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    goals: list[str] = Field(default_factory=list)
    facts: list[str] = Field(default_factory=list)
    preferences: dict[str, str] = Field(default_factory=dict)
    conversation_history: list[ConversationTurn] = Field(default_factory=list)
    summary: str = ""
    last_topics: list[str] = Field(default_factory=list)
    messages_count: int = 0
