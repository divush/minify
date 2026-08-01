from langchain_core.messages import AIMessage, HumanMessage

from minify.chat.langchain_chat import LangChainChat
from minify.models import ChatMessage, Chunk, ReaderProfile


class _FakeAIMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChatModel:
    """Records every call and returns a single canned response."""

    def __init__(self, response: str) -> None:
        self._response = response
        self.calls: list[list] = []

    def invoke(self, messages):
        self.calls.append(list(messages))
        return _FakeAIMessage(self._response)


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
        page_start=1,
        page_end=1,
        content="Cells are tiny compartments that make up every living thing.",
        status="ready",
    )
    defaults.update(overrides)
    return Chunk(**defaults)


def _make_profile(**overrides) -> ReaderProfile:
    defaults = dict(id="profile-1", background="Beginner in biology", intent="Casual reading")
    defaults.update(overrides)
    return ReaderProfile(**defaults)


def _make_message(role: str, content: str) -> ChatMessage:
    return ChatMessage(id="msg-1", chunk_id="chunk-1", role=role, content=content)


def test_respond_returns_the_model_response():
    fake_model = _FakeChatModel("The answer is 42.")
    chat = LangChainChat(_FakeChatModelFactory(fake_model))

    answer = chat.respond(_make_chunk(), _make_profile(), history=[], question="What is it?")

    assert answer == "The answer is 42."


def test_system_message_grounds_in_content_not_raw_text():
    fake_model = _FakeChatModel("answer")
    chat = LangChainChat(_FakeChatModelFactory(fake_model))

    chat.respond(_make_chunk(), _make_profile(), history=[], question="What is it?")

    system_message = fake_model.calls[0][0]
    assert "Beginner in biology" in system_message.content
    assert "Casual reading" in system_message.content
    assert "Chapter 1" in system_message.content
    assert "Cells are tiny compartments that make up every living thing." in system_message.content
    # The raw source text isn't sent — grounding is content-only.
    assert "Cells are the basic unit of life." not in system_message.content


def test_empty_history_sends_only_system_and_question():
    fake_model = _FakeChatModel("answer")
    chat = LangChainChat(_FakeChatModelFactory(fake_model))

    chat.respond(_make_chunk(), _make_profile(), history=[], question="What is it?")

    messages = fake_model.calls[0]
    assert len(messages) == 2
    assert isinstance(messages[1], HumanMessage)
    assert messages[1].content == "What is it?"


def test_history_is_converted_in_order_and_question_is_last():
    fake_model = _FakeChatModel("answer")
    chat = LangChainChat(_FakeChatModelFactory(fake_model))
    history = [
        _make_message("user", "First question"),
        _make_message("assistant", "First answer"),
    ]

    chat.respond(_make_chunk(), _make_profile(), history=history, question="Follow-up question")

    messages = fake_model.calls[0]
    assert len(messages) == 4
    assert isinstance(messages[1], HumanMessage) and messages[1].content == "First question"
    assert isinstance(messages[2], AIMessage) and messages[2].content == "First answer"
    assert isinstance(messages[3], HumanMessage) and messages[3].content == "Follow-up question"
