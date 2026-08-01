"""The chat port: per-chunk grounded Q&A, independent of the summarizer.

`Chat` answers a reader's question about one chunk, grounded in that chunk's
`content` (the tailored writeup already generated for this reader — not
`raw_text`) and shaped by the reader's profile, the same way `content` and
`short_summary` already are. Pure function in spirit, like `Summarizer`: no
Storage dependency here. It takes the conversation history as a plain
argument and returns the answer text; persisting the new question/answer
pair as `ChatMessage` rows is the caller's job, not this module's.
"""

from typing import Protocol

from minify.models import ChatMessage, Chunk, ReaderProfile


class Chat(Protocol):
    """Answers one question about `chunk`, grounded in `chunk.content`.

    `history` is the chunk's prior `ChatMessage` rows, oldest first — the
    full history is sent every time, with no truncation/windowing (fine at
    this scale; a known limitation, not solved here).
    """

    def respond(
        self, chunk: Chunk, profile: ReaderProfile, history: list[ChatMessage], question: str
    ) -> str: ...
