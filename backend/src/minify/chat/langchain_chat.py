"""`Chat` adapter: one call, grounded in `chunk.content`, profile-aware.

Unlike the Summarizer's prompts, no filler-suppression instruction is used
here — this output *is* a live chat turn, so a natural conversational tone
is correct, not something to strip out.
"""

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from minify.llm import ChatModelFactory
from minify.models import ChatMessage, Chunk, ReaderProfile
from minify.chat.interface import Chat


def _build_system_message(chunk: Chunk, profile: ReaderProfile) -> SystemMessage:
    heading = chunk.heading or "(untitled section)"
    return SystemMessage(
        content=(
            "You are answering a specific reader's questions about one section of a book.\n\n"
            f"Reader background: {profile.background}\n"
            f"Reader intent: {profile.intent}\n\n"
            f"Section heading: {heading}\n"
            "Section content (what the reader has already read):\n---\n"
            f"{chunk.content}\n---\n\n"
            "Answer only using this section's content above, tailored to this reader's "
            "background and intent. If the question can't be answered from it, say so plainly "
            "instead of guessing."
        )
    )


def _history_to_messages(history: list[ChatMessage]) -> list[HumanMessage | AIMessage]:
    return [
        HumanMessage(content=message.content) if message.role == "user" else AIMessage(content=message.content)
        for message in history
    ]


class LangChainChat:
    """`Chat` implementation built on a `ChatModelFactory`-provided model."""

    def __init__(self, chat_model_factory: ChatModelFactory) -> None:
        self._chat_model_factory = chat_model_factory

    def respond(
        self, chunk: Chunk, profile: ReaderProfile, history: list[ChatMessage], question: str
    ) -> str:
        model = self._chat_model_factory.get_chat_model()
        messages = [
            _build_system_message(chunk, profile),
            *_history_to_messages(history),
            HumanMessage(content=question),
        ]
        response = model.invoke(messages)
        return response.content
