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


def heuristic_extract_facts(message_text: str) -> ExtractedMemory:
    text = re.sub(r"\s+", " ", message_text.strip())
    lowered = text.casefold()

    facts: list[str] = []
    goals: list[str] = []
    preferences: dict[str, str] = {}

    name_match = re.search(
        "\u043c\u0435\u043d\u0435 \u0437\u0432\u0430\u0442\u0438\\s+"
        "([A-Z\u0410-\u042f\u0406\u0407\u0404\u0490][\\w'\\u2019-]{1,30})",
        text,
        flags=re.IGNORECASE,
    )
    if name_match:
        facts.append(f"User's name is {name_match.group(1)}")

    age_match = re.search(
        "\u043c\u0435\u043d\u0456\\s+(\\d{1,2})\\s*(?:\u0440\u043e\u043a\u0456\u0432|\u0440\\b)",
        text,
        flags=re.IGNORECASE,
    )
    if age_match:
        facts.append(f"User is {age_match.group(1)} years old")

    for pattern in (
        "(?:\u044f\\s+\u0432\u0438\u0432\u0447\u0430\u044e|\u0432\u0438\u0432\u0447\u0430\u044e)\\s+([^.!?]+)",
        "(?:\u044f\\s+\u0446\u0456\u043a\u0430\u0432\u043b\u044e\u0441\u044f|\u0446\u0456\u043a\u0430\u0432\u043b\u044e\u0441\u044f)\\s+([^.!?]+)",
        "(?:\u044f\\s+\u043f\u0440\u0430\u0446\u044e\u044e \u043d\u0430\u0434|\u043f\u0440\u0430\u0446\u044e\u044e \u043d\u0430\u0434)\\s+([^.!?]+)",
        "(?:\u044f\\s+\u043b\u044e\u0431\u043b\u044e|\u043b\u044e\u0431\u043b\u044e)\\s+([^.!?]+)",
    ):
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            facts.append(_sentence_case(match.group(1)))

    for pattern in (
        "(?:\u044f\\s+\u0445\u043e\u0447\u0443|\u0445\u043e\u0447\u0443)\\s+([^.!?]+)",
        "(?:\u044f\\s+\u043f\u043b\u0430\u043d\u0443\u044e|\u043f\u043b\u0430\u043d\u0443\u044e)\\s+([^.!?]+)",
        "(?:\u043c\u043e\u044f\\s+\u0446\u0456\u043b\u044c\\s*(?:-|:)?|\u0446\u0456\u043b\u044c\\s*(?:-|:)?)\\s*([^.!?]+)",
    ):
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            goals.append(_sentence_case(match.group(1)))

    if "\u0443\u043a\u0440\u0430\u0457\u043d\u0441\u044c\u043a" in lowered:
        preferences["language"] = "uk"
    if "\u0430\u043d\u0433\u043b\u0456\u0439\u0441\u044c\u043a" in lowered:
        preferences["language"] = "en"
    if "\u043a\u043e\u0440\u043e\u0442\u043a\u043e" in lowered:
        preferences["answer_style"] = "short"
    if "\u0434\u0435\u0442\u0430\u043b\u044c\u043d\u043e" in lowered:
        preferences["answer_style"] = "detailed"
    if "\u0434\u0440\u0443\u0436" in lowered or "casual" in lowered:
        preferences["tone"] = "friendly"
    if "\u0444\u043e\u0440\u043c\u0430\u043b\u044c" in lowered:
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
        goals=_normalize(merged.goals),
        preferences=merged.preferences,
        topics=_normalize(merged.topics),
    )
