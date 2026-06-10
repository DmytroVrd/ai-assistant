import asyncio

import pytest

from db import MemoryUnavailableError, UserMemoryStore, _entry_matches_query, is_name_related_query
from handlers import _extract_memory_with_fallback
from llm import parse_assistant_result, parse_extracted_memory
from schemas import ExtractedMemory


def test_extracted_memory_defaults_to_empty_collections() -> None:
    memory = ExtractedMemory()

    assert memory.facts == []
    assert memory.goals == []
    assert memory.preferences == {}
    assert memory.topics == []


def test_name_related_query_detection() -> None:
    assert is_name_related_query("ім'я")
    assert is_name_related_query("забудь як мене звати")
    assert is_name_related_query("name")
    assert not is_name_related_query("python")


def test_entry_matches_partial_and_name_related_queries() -> None:
    assert _entry_matches_query("User's name is Дмитро", "ім'я", name_related=True)
    assert _entry_matches_query("I study Python", "python", name_related=False)
    assert not _entry_matches_query("I study Python", "mongodb", name_related=False)


def test_extracted_memory_validates_structured_llm_output() -> None:
    memory = ExtractedMemory.model_validate(
        {
            "facts": ["User's name is Dmytro"],
            "goals": ["Build an AI assistant"],
            "preferences": {"language": "en", "answer_style": "short"},
            "topics": ["AI", "Telegram"],
        }
    )

    assert "User's name is Dmytro" in memory.facts
    assert "Build an AI assistant" in memory.goals
    assert memory.preferences["language"] == "en"
    assert memory.preferences["answer_style"] == "short"
    assert memory.topics == ["AI", "Telegram"]


def test_parses_valid_llm_memory_json() -> None:
    memory = parse_extracted_memory(
        '{"facts":["User works with Python"],"goals":[],"preferences":{},"topics":["Python"]}'
    )

    assert memory.facts == ["User works with Python"]
    assert memory.topics == ["Python"]


def test_rejects_invalid_llm_memory_json() -> None:
    try:
        parse_extracted_memory('{"facts":{"name":"Dmytro"},"preferences":[]}')
    except RuntimeError as exc:
        assert "expected keys" in str(exc)
    else:
        raise AssertionError("Invalid structured memory should be rejected.")


def test_parses_combined_reply_and_memory() -> None:
    result = parse_assistant_result(
        '{"reply":"Football is a great hobby!",'
        '"memory":{"facts":["The user enjoys playing football."],'
        '"goals":[],"preferences":{},"topics":["football"]}}'
    )

    assert result.reply == "Football is a great hobby!"
    assert result.memory.facts == ["The user enjoys playing football."]


def test_rejects_combined_result_without_reply() -> None:
    try:
        parse_assistant_result(
            '{"memory":{"facts":[],"goals":[],"preferences":{},"topics":[]}}'
        )
    except RuntimeError as exc:
        assert "reply and memory" in str(exc)
    else:
        raise AssertionError("Combined assistant result without reply should be rejected.")


def test_rejects_silently_discarded_profile_keys() -> None:
    try:
        parse_assistant_result(
            '{"reply":"Great!","memory":{"facts":[],"goals":[],"preferences":{},'
            '"topics":["football"],"interests":["football"],"idol":"Ronaldo"}}'
        )
    except RuntimeError as exc:
        assert "expected keys" in str(exc)
    else:
        raise AssertionError("Unexpected profile keys must trigger an LLM repair attempt.")


def test_accepts_multiple_personal_details_as_facts() -> None:
    result = parse_assistant_result(
        '{"reply":"Football is a big part of your life.",'
        '"memory":{"facts":["The user loves playing football.",'
        '"The user considers Ronaldo an idol."],'
        '"goals":[],"preferences":{},"topics":["football","Ronaldo"]}}'
    )

    assert result.memory.facts == [
        "The user loves playing football.",
        "The user considers Ronaldo an idol.",
    ]


def test_llm_extraction_result_is_used_directly() -> None:
    expected = ExtractedMemory(
        facts=["User's name is Dmytro"],
        goals=["Build an AI assistant"],
        topics=["AI"],
    )

    class FakeLLMClient:
        async def extract_memory(self, user_message: str) -> ExtractedMemory:
            assert user_message == "My name is Dmytro and I want to build an AI assistant."
            return expected

    result = asyncio.run(
        _extract_memory_with_fallback(
            "My name is Dmytro and I want to build an AI assistant.",
            FakeLLMClient(),
        )
    )

    assert result == expected


def test_failed_llm_extraction_skips_automatic_memory() -> None:
    class BrokenLLMClient:
        async def extract_memory(self, user_message: str) -> ExtractedMemory:
            raise RuntimeError("OpenRouter unavailable")

    result = asyncio.run(_extract_memory_with_fallback("My name is Dmytro.", BrokenLLMClient()))

    assert result == ExtractedMemory()


def test_memory_update_does_not_fail_silently_when_user_document_is_missing() -> None:
    class MissingDocumentResult:
        matched_count = 0

    class MissingDocumentCollection:
        def update_one(self, *args: object, **kwargs: object) -> MissingDocumentResult:
            return MissingDocumentResult()

    store = object.__new__(UserMemoryStore)
    store._collection = MissingDocumentCollection()

    with pytest.raises(MemoryUnavailableError):
        store._apply_memory_sync(
            123,
            ExtractedMemory(facts=["The user lives in Ukraine."]),
        )
