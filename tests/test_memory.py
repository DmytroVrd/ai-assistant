from db import _entry_matches_query, is_name_related_query
from memory import heuristic_extract_facts, merge_memories
from schemas import ExtractedMemory


def test_heuristic_extracts_name_age_goal_and_topics() -> None:
    memory = heuristic_extract_facts(
        "Мене звати Дмитро, мені 17 років. Я хочу вивчити AI і Python."
    )

    assert "User's name is Дмитро" in memory.facts
    assert "User is 17 years old" in memory.facts
    assert any("Вивчити AI і Python" == goal for goal in memory.goals)
    assert "AI" in memory.topics
    assert "Python" in memory.topics


def test_merge_memories_deduplicates_values() -> None:
    first = ExtractedMemory(facts=["Любить Python"], topics=["Python"])
    second = ExtractedMemory(facts=["Любить Python"], topics=["Python", "AI"])

    merged = merge_memories(first, second)

    assert merged.facts == ["Любить Python"]
    assert merged.topics == ["Python", "AI"]


def test_name_related_query_detection() -> None:
    assert is_name_related_query("ім'я")
    assert is_name_related_query("забудь як мене звати")
    assert is_name_related_query("name")
    assert not is_name_related_query("python")


def test_entry_matches_partial_and_name_related_queries() -> None:
    assert _entry_matches_query("User's name is Дмитро", "ім'я", name_related=True)
    assert _entry_matches_query("I study Python", "python", name_related=False)
    assert not _entry_matches_query("I study Python", "mongodb", name_related=False)


def test_heuristic_extracts_english_language_preferences() -> None:
    memory = heuristic_extract_facts(
        "My name is Dmytro. I am 17 years old. I want to build an AI portfolio. Please answer in English and keep it short."
    )

    assert "User's name is Dmytro" in memory.facts
    assert "User is 17 years old" in memory.facts
    assert "Build an AI portfolio" in memory.goals
    assert memory.preferences["language"] == "en"
    assert memory.preferences["answer_style"] == "short"


def test_merge_memories_filters_noise_goals() -> None:
    first = ExtractedMemory(goals=["Find out his name"])
    second = ExtractedMemory(goals=["Build an AI portfolio"])

    merged = merge_memories(first, second)

    assert merged.goals == ["Build an AI portfolio"]
