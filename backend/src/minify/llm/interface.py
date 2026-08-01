"""The LLM port: the only contract other modules depend on for chat models.

Unlike other ports in this codebase, this one is allowed to expose a
LangChain type (`BaseChatModel`) rather than a fully custom shape — LangChain
itself is the design's chosen, permanent provider-agnostic abstraction (see
design.md's tech stack), not something meant to be swapped out later. What
this module hides is the *provider SDK and config* underneath LangChain:
callers get a ready-to-use chat model without knowing or caring whether it's
backed by OpenAI, Anthropic, or anything else.
"""

from typing import Protocol

from langchain_core.language_models import BaseChatModel


class ChatModelFactory(Protocol):
    """Produces a configured chat model. Every other module that needs to
    talk to an LLM (summarizer, chat, chunk refiner) calls this instead of
    constructing a provider client directly.

    `model` optionally overrides `Settings.llm_model` for this one call —
    e.g. the chunk refiner deliberately uses a cheaper model than the
    Summarizer, without needing a second factory wired up alongside this one.
    """

    def get_chat_model(self, model: str | None = None) -> BaseChatModel: ...
