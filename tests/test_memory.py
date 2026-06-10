import asyncio

from db import _entry_matches_query, is_name_related_query
from handlers import _extract_memory_with_fallback
from llm import parse_extracted_memory
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
        assert "expected schema" in str(exc)
    else:
        raise AssertionError("Invalid structured memory should be rejected.")


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
