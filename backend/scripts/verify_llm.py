"""Manual, one-off verification that the LLM layer actually talks to a real
provider — not run by pytest, since automated tests shouldn't need real
secrets or network access.

Usage: set LLM_API_KEY (and LLM_PROVIDER/LLM_MODEL if not using the OpenAI
default) in backend/.env, then run:

    uv run python scripts/verify_llm.py
"""

from minify.config import get_settings
from minify.llm.langchain_factory import LangChainChatModelFactory


def main() -> None:
    settings = get_settings()
    if not settings.llm_api_key:
        raise SystemExit(
            "LLM_API_KEY is not set in backend/.env — add a real key before running this script."
        )

    model = LangChainChatModelFactory(settings).get_chat_model()
    response = model.invoke("Reply with exactly one word: pong")
    print(f"Provider: {settings.llm_provider}, model: {settings.llm_model}")
    print(f"Response: {response.content}")


if __name__ == "__main__":
    main()
