"""The chat model of the style coach, from config.yaml `agent` (local Ollama by default, free and offline).

`provider: shared` uses backend/shared/llm.py instead (LLM_PROVIDER / LLM_MODEL of infra/.env), so the
agent can move to Claude / OpenAI without code changes.
"""

from langchain_core.language_models import BaseChatModel

from ..config import get_config

_override: BaseChatModel | None = None  # tests put a scripted model here


def set_model(model: BaseChatModel | None) -> None:
    global _override
    _override = model


def model_name() -> str:
    a = get_config().agent
    if _override is not None:
        return type(_override).__name__
    if a.provider == "shared":
        from shared.config import settings

        return f"{settings.llm_provider}:{settings.llm_model}"
    return f"{a.provider}:{a.model}"


def get_model() -> BaseChatModel:
    if _override is not None:
        return _override
    a = get_config().agent
    if a.provider == "ollama":
        from langchain_ollama import ChatOllama

        # reasoning=False: no <think> block, answers and tool calls come directly (much faster on 4 GB GPUs)
        return ChatOllama(
            model=a.model, base_url=a.base_url, temperature=a.temperature, num_ctx=a.num_ctx, reasoning=False
        )
    if a.provider == "shared":
        from shared.llm import get_chat_model

        return get_chat_model()
    raise ValueError(f"unknown agent provider {a.provider!r} (ollama | shared)")
