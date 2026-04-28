from db import _entry_matches_query, is_name_related_query
from memory import heuristic_extract_facts, merge_memories
from schemas import ExtractedMemory


def test_heuristic_extracts_name_age_goal_and_topics() -> None:
    memory = heuristic_extract_facts(
        "\u041c\u0435\u043d\u0435 \u0437\u0432\u0430\u0442\u0438 \u0414\u043c\u0438\u0442\u0440\u043e, \u043c\u0435\u043d\u0456 17 \u0440\u043e\u043a\u0456\u0432. \u042f \u0445\u043e\u0447\u0443 \u0432\u0438\u0432\u0447\u0438\u0442\u0438 AI \u0456 Python."
    )

    assert "User's name is \u0414\u043c\u0438\u0442\u0440\u043e" in memory.facts
    assert "User is 17 years old" in memory.facts
    assert any("\u0412\u0438\u0432\u0447\u0438\u0442\u0438 AI \u0456 Python" == goal for goal in memory.goals)
    assert "AI" in memory.topics
    assert "Python" in memory.topics


def test_merge_memories_deduplicates_values() -> None:
    first = ExtractedMemory(facts=["\u041b\u044e\u0431\u0438\u0442\u044c Python"], topics=["Python"])
    second = ExtractedMemory(facts=["\u041b\u044e\u0431\u0438\u0442\u044c Python"], topics=["Python", "AI"])

    merged = merge_memories(first, second)

    assert merged.facts == ["\u041b\u044e\u0431\u0438\u0442\u044c Python"]
    assert merged.topics == ["Python", "AI"]


def test_name_related_query_detection() -> None:
    assert is_name_related_query("\u0456\u043c'\u044f")
    assert is_name_related_query("\u0437\u0430\u0431\u0443\u0434\u044c \u044f\u043a \u043c\u0435\u043d\u0435 \u0437\u0432\u0430\u0442\u0438")
    assert not is_name_related_query("python")


def test_entry_matches_partial_and_name_related_queries() -> None:
    assert _entry_matches_query("User's name is \u0414\u043c\u0438\u0442\u0440\u043e", "\u0456\u043c'\u044f", name_related=True)
    assert _entry_matches_query("I study Python", "python", name_related=False)
    assert not _entry_matches_query("I study Python", "mongodb", name_related=False)
