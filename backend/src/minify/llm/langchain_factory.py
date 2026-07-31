"""`ChatModelFactory` adapter: builds a LangChain chat model from `Settings`.

The only place a provider-specific LangChain integration package
(`langchain_openai`, and whatever comes next) gets imported. Adding a new
provider means adding one more branch here plus one more dependency — not
touching any caller.
"""

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from minify.config import Settings, get_settings


class LangChainChatModelFactory:
    """`ChatModelFactory` implementation dispatching on `Settings.llm_provider`.

    Lazily constructs and caches the model instance. Construction itself
    never touches the network (LangChain doesn't authenticate until a call
    like `.invoke()` is actually made), so caching only avoids repeat object
    creation, not repeat auth — an invalid API key still won't surface until
    the model is actually used.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._model: BaseChatModel | None = None

    def get_chat_model(self) -> BaseChatModel:
        if self._model is None:
            self._model = self._build_model()
        return self._model

    def _build_model(self) -> BaseChatModel:
        provider = self._settings.llm_provider
        if provider == "openai":
            return ChatOpenAI(model=self._settings.llm_model, api_key=self._settings.llm_api_key)
        raise ValueError(f"Unsupported LLM provider: {provider!r}")
