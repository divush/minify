import pytest
from langchain_openai import ChatOpenAI

from minify.config import Settings
from minify.llm.langchain_factory import LangChainChatModelFactory


def test_factory_builds_chat_openai_from_settings():
    settings = Settings(llm_provider="openai", llm_model="gpt-4.1-mini", llm_api_key="test-key")
    factory = LangChainChatModelFactory(settings)

    model = factory.get_chat_model()

    assert isinstance(model, ChatOpenAI)
    assert model.model_name == "gpt-4.1-mini"


def test_factory_caches_the_model_instance():
    settings = Settings(llm_provider="openai", llm_model="gpt-4.1-mini", llm_api_key="test-key")
    factory = LangChainChatModelFactory(settings)

    assert factory.get_chat_model() is factory.get_chat_model()


def test_factory_builds_a_distinct_cached_model_per_override():
    settings = Settings(llm_provider="openai", llm_model="gpt-4.1-mini", llm_api_key="test-key")
    factory = LangChainChatModelFactory(settings)

    default_model = factory.get_chat_model()
    cheap_model = factory.get_chat_model(model="gpt-4o-mini")

    assert default_model.model_name == "gpt-4.1-mini"
    assert cheap_model.model_name == "gpt-4o-mini"
    assert cheap_model is not default_model
    # Requesting the same override again returns the cached instance.
    assert factory.get_chat_model(model="gpt-4o-mini") is cheap_model


def test_factory_rejects_unsupported_provider():
    settings = Settings(llm_provider="not-a-real-provider", llm_api_key="test-key")
    factory = LangChainChatModelFactory(settings)

    with pytest.raises(ValueError, match="not-a-real-provider"):
        factory.get_chat_model()
