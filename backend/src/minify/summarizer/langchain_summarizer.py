"""`Summarizer` adapter: two calls, content first, short_summary derived from it.

`content` is generated from the chunk's `raw_text`. `short_summary` is then
generated from that *generated content*, not from `raw_text` again — a
deliberate cost saving: `raw_text` can be up to 5000 words for fallback
chunks, while `content` is generally much shorter, so the second call's
input is far cheaper than re-sending the whole section. The two calls still
don't share full conversation history (no `AIMessage` appended back) — the
second call just takes `content` as plain text input, one fresh
`[system, human]` pair each.

`content` is written in Markdown (the reader-facing view can render it).
Both prompts explicitly forbid conversational preamble/closing remarks
(e.g. "Sure!", "Would you like me to explain more?") — live testing surfaced
the model occasionally answering in "chat assistant" mode, which is wrong
for text that's stored and displayed directly rather than shown as a chat
turn.
"""

from langchain_core.messages import HumanMessage, SystemMessage

from minify.llm import ChatModelFactory
from minify.models import Chunk, ReaderProfile
from minify.summarizer.interface import SummaryResult

_NO_CHAT_FILLER_INSTRUCTION = (
    "Write only the requested text itself — no conversational preamble (e.g. \"Sure!\") "
    "and no closing remarks or questions (e.g. offering to explain more). This text is "
    "stored and shown directly to the reader, not part of a live conversation."
)


def _build_system_message(profile: ReaderProfile) -> SystemMessage:
    return SystemMessage(
        content=(
            "You are helping a specific reader work through a book, one section at a time.\n\n"
            f"Reader background: {profile.background}\n"
            f"Reader intent: {profile.intent}\n\n"
            "Tailor everything you write to this reader's background and intent."
        )
    )


def _prior_context_line(prior_short_summary: str | None) -> str:
    if prior_short_summary:
        return (
            "Context from earlier in the book (for your own continuity, not to repeat "
            f"verbatim): {prior_short_summary}"
        )
    return "This is the first section of the book."


def _build_content_request(chunk: Chunk, prior_short_summary: str | None) -> HumanMessage:
    heading = chunk.heading or "(untitled section)"
    return HumanMessage(
        content=(
            f"{_prior_context_line(prior_short_summary)}\n\n"
            f"Section heading: {heading}\n"
            "Section text:\n---\n"
            f"{chunk.raw_text}\n---\n\n"
            "Write a tailored writeup of this section for this reader: as detailed, "
            "technical, or example-driven as suits their background and intent. This is "
            "the actual text they will read, so make it genuinely useful for their stated "
            "intent, not just a compressed restatement of the source text.\n\n"
            "Format the writeup in Markdown (headings, bold, lists, etc. where they help "
            f"readability).\n\n{_NO_CHAT_FILLER_INSTRUCTION}"
        )
    )


def _build_short_summary_request(
    chunk: Chunk, content: str, prior_short_summary: str | None
) -> HumanMessage:
    heading = chunk.heading or "(untitled section)"
    return HumanMessage(
        content=(
            f"{_prior_context_line(prior_short_summary)}\n\n"
            f"Section heading: {heading}\n"
            "Here is the writeup already produced for this section:\n---\n"
            f"{content}\n---\n\n"
            "Write a short summary (2-4 sentences) of this section, from this reader's "
            "perspective, based on the writeup above. Skip examples and elaboration — this "
            "is only used to give the next section's summarization context for continuity, "
            f"and will never be shown to the reader.\n\n{_NO_CHAT_FILLER_INSTRUCTION}"
        )
    )


class LangChainSummarizer:
    """`Summarizer` implementation built on a `ChatModelFactory`-provided model."""

    def __init__(self, chat_model_factory: ChatModelFactory) -> None:
        self._chat_model_factory = chat_model_factory

    def summarize(
        self, chunk: Chunk, profile: ReaderProfile, prior_short_summary: str | None
    ) -> SummaryResult:
        model = self._chat_model_factory.get_chat_model()
        system_message = _build_system_message(profile)

        content_response = model.invoke(
            [system_message, _build_content_request(chunk, prior_short_summary)]
        )
        content = content_response.content

        short_summary_response = model.invoke(
            [system_message, _build_short_summary_request(chunk, content, prior_short_summary)]
        )

        return SummaryResult(content=content, short_summary=short_summary_response.content)
