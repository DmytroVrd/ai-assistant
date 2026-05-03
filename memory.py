from __future__ import annotations

import re

from schemas import ExtractedMemory


TOPIC_PATTERNS = {
    r"(?<!\w)ai(?!\w)": "AI",
    r"(?<!\w)ml(?!\w)": "ML",
    r"(?<!\w)python(?!\w)": "Python",
    r"(?<!\w)telegram(?!\w)": "Telegram",
    r"(?<!\w)mongodb(?!\w)": "MongoDB",
    r"(?<!\w)startup\w*": "Startups",
    r"(?<!\w)rag(?!\w)": "RAG",
    r"(?<!\w)langchain(?!\w)": "LangChain",
}

NOISE_GOAL_PATTERNS = (
    "дізнатися, як його звуть",
    "дізнатися як його звуть",
    "find out his name",
    "find out what his name is",
    "remember his name",
    "what his name is",
)


def _normalize(items: list[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for item in items:
        cleaned = re.sub(r"\s+", " ", item).strip(" .,!?:;")
        if cleaned and cleaned.casefold() not in seen:
            seen.add(cleaned.casefold())
            normalized.append(cleaned)
    return normalized


def _match_topics(text: str) -> list[str]:
    lowered = text.casefold()
    topics = [label for pattern, label in TOPIC_PATTERNS.items() if re.search(pattern, lowered)]
    return _normalize(topics)


def _sentence_case(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        return ""
    return cleaned[0].upper() + cleaned[1:]


def _is_noise_goal(value: str) -> bool:
    lowered = value.casefold().strip()
    return any(pattern in lowered for pattern in NOISE_GOAL_PATTERNS)


def heuristic_extract_facts(message_text: str) -> ExtractedMemory:
    text = re.sub(r"\s+", " ", message_text.strip())
    lowered = text.casefold()

    facts: list[str] = []
    goals: list[str] = []
    preferences: dict[str, str] = {}

    name_match = re.search(
        r"(?:мене звати|my name is)\s+([A-ZА-ЯІЇЄҐ][\w'\u2019-]{1,30})",
        text,
        flags=re.IGNORECASE,
    )
    if name_match:
        facts.append(f"User's name is {name_match.group(1)}")

    age_match = re.search(
        r"(?:мені\s+(\d{1,2})\s*(?:років|р\b)|i am\s+(\d{1,2})\s+years?\s+old)",
        text,
        flags=re.IGNORECASE,
    )
    if age_match:
        age = age_match.group(1) or age_match.group(2)
        facts.append(f"User is {age} years old")

    for pattern in (
        r"(?:я\s+вивчаю|вивчаю)\s+([^.!?]+)",
        r"(?:я\s+цікавлюся|цікавлюся)\s+([^.!?]+)",
        r"(?:я\s+працюю над|працюю над)\s+([^.!?]+)",
        r"(?:я\s+люблю|люблю)\s+([^.!?]+)",
        r"(?:i study|studying)\s+([^.!?]+)",
        r"(?:i am interested in|interested in)\s+([^.!?]+)",
        r"(?:i work on|working on)\s+([^.!?]+)",
        r"(?:i like)\s+([^.!?]+)",
    ):
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            facts.append(_sentence_case(match.group(1)))

    for pattern in (
        r"(?:я\s+хочу|хочу)\s+([^.!?]+)",
        r"(?:я\s+планую|планую)\s+([^.!?]+)",
        r"(?:моя\s+ціль\s*(?:-|:)?|ціль\s*(?:-|:)?)\s*([^.!?]+)",
        r"(?:i want to|want to)\s+([^.!?]+)",
        r"(?:i plan to|plan to)\s+([^.!?]+)",
        r"(?:my goal is|goal[: ]+)\s*([^.!?]+)",
    ):
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            goals.append(_sentence_case(match.group(1)))

    if "українськ" in lowered:
        preferences["language"] = "uk"
    if "англійськ" in lowered or "english" in lowered:
        preferences["language"] = "en"
    if "коротко" in lowered or "briefly" in lowered or "short answer" in lowered or "keep it short" in lowered:
        preferences["answer_style"] = "short"
    if "детально" in lowered or "detailed" in lowered:
        preferences["answer_style"] = "detailed"
    if "друж" in lowered or "casual" in lowered or "friendly" in lowered:
        preferences["tone"] = "friendly"
    if "формаль" in lowered or "formal" in lowered:
        preferences["tone"] = "formal"

    return ExtractedMemory(
        facts=_normalize(facts),
        goals=_normalize(goals),
        preferences=preferences,
        topics=_match_topics(text),
    )


def merge_memories(*memories: ExtractedMemory) -> ExtractedMemory:
    merged = ExtractedMemory()
    for memory in memories:
        merged.facts.extend(memory.facts)
        merged.goals.extend(memory.goals)
        merged.topics.extend(memory.topics)
        merged.preferences.update(memory.preferences)

    return ExtractedMemory(
        facts=_normalize(merged.facts),
        goals=[goal for goal in _normalize(merged.goals) if not _is_noise_goal(goal)],
        preferences=merged.preferences,
        topics=_normalize(merged.topics),
    )
