from minify.models import Chunk, ReaderProfile
from minify.summarizer.langchain_summarizer import LangChainSummarizer


class _FakeAIMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChatModel:
    """Records every call and returns canned responses in order."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = iter(responses)
        self.calls: list[list] = []

    def invoke(self, messages):
        self.calls.append(list(messages))
        return _FakeAIMessage(next(self._responses))


class _FakeChatModelFactory:
    def __init__(self, model: _FakeChatModel) -> None:
        self._model = model

    def get_chat_model(self):
        return self._model


def _make_chunk(**overrides) -> Chunk:
    defaults = dict(
        id="chunk-1",
        book_id="book-1",
        index=0,
        heading="Chapter 1",
        raw_text="Cells are the basic unit of life.",
        status="processing",
    )
    defaults.update(overrides)
    return Chunk(**defaults)


def _make_profile(**overrides) -> ReaderProfile:
    defaults = dict(id="profile-1", background="Beginner in biology", intent="Casual reading")
    defaults.update(overrides)
    return ReaderProfile(**defaults)


def test_summarize_maps_responses_into_a_result():
    # Call order is content first, then short_summary.
    fake_model = _FakeChatModel(["CONTENT_RESPONSE", "SHORT_SUMMARY_RESPONSE"])
    summarizer = LangChainSummarizer(_FakeChatModelFactory(fake_model))

    result = summarizer.summarize(_make_chunk(), _make_profile(), prior_short_summary=None)

    assert result.content == "CONTENT_RESPONSE"
    assert result.short_summary == "SHORT_SUMMARY_RESPONSE"


def test_two_independent_single_turn_calls_are_made():
    fake_model = _FakeChatModel(["c", "s"])
    summarizer = LangChainSummarizer(_FakeChatModelFactory(fake_model))

    summarizer.summarize(_make_chunk(), _make_profile(), prior_short_summary=None)

    assert len(fake_model.calls) == 2
    # Each call is a fresh [system, human] pair, not a growing conversation.
    assert len(fake_model.calls[0]) == 2
    assert len(fake_model.calls[1]) == 2


def test_content_call_uses_raw_text_and_requests_markdown():
    fake_model = _FakeChatModel(["c", "s"])
    summarizer = LangChainSummarizer(_FakeChatModelFactory(fake_model))

    summarizer.summarize(_make_chunk(), _make_profile(), prior_short_summary=None)

    system_message, human_message = fake_model.calls[0]
    assert "Beginner in biology" in system_message.content
    assert "Casual reading" in system_message.content
    assert "Chapter 1" in human_message.content
    assert "Cells are the basic unit of life." in human_message.content
    assert "first section" in human_message.content.lower()
    assert "markdown" in human_message.content.lower()


def test_short_summary_call_uses_generated_content_not_raw_text():
    fake_model = _FakeChatModel(["THE GENERATED CONTENT", "s"])
    summarizer = LangChainSummarizer(_FakeChatModelFactory(fake_model))

    summarizer.summarize(_make_chunk(), _make_profile(), prior_short_summary=None)

    _, human_message = fake_model.calls[1]
    assert "THE GENERATED CONTENT" in human_message.content
    # The raw source text isn't resent on the second call — only the content is.
    assert "Cells are the basic unit of life." not in human_message.content


def test_prior_short_summary_included_in_both_calls_when_given():
    fake_model = _FakeChatModel(["c", "s"])
    summarizer = LangChainSummarizer(_FakeChatModelFactory(fake_model))

    summarizer.summarize(
        _make_chunk(), _make_profile(), prior_short_summary="Chapter 1 covered cells."
    )

    content_human = fake_model.calls[0][1]
    short_summary_human = fake_model.calls[1][1]
    assert "Chapter 1 covered cells." in content_human.content
    assert "Chapter 1 covered cells." in short_summary_human.content
    assert "first section" not in content_human.content.lower()
    assert "first section" not in short_summary_human.content.lower()


def test_both_calls_forbid_conversational_filler():
    fake_model = _FakeChatModel(["c", "s"])
    summarizer = LangChainSummarizer(_FakeChatModelFactory(fake_model))

    summarizer.summarize(_make_chunk(), _make_profile(), prior_short_summary=None)

    content_human = fake_model.calls[0][1]
    short_summary_human = fake_model.calls[1][1]
    assert "preamble" in content_human.content.lower()
    assert "preamble" in short_summary_human.content.lower()
