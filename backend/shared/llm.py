"""Single place to get an LLM client, so agents never hard-code a provider."""

from shared.config import settings


def get_chat_model():
    if settings.llm_provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=settings.llm_model, api_key=settings.llm_api_key)
    if settings.llm_provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=settings.llm_model, api_key=settings.llm_api_key)
    if settings.llm_provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(model=settings.llm_model)
    raise ValueError(f"Unknown LLM provider {settings.llm_provider}")
