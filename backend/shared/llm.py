"""Single place to get an LLM client, so agents never hard-code a provider."""

from shared.config import settings


def get_chat_model():
    """The orchestrator's brain. LLM_PROVIDER: ollama (local) | groq (free API, fast, good at choosing tools) |
    openai (any OpenAI-compatible host through LLM_BASE_URL) | anthropic. Temperature 0: routing must not vary."""
    import os

    provider = (settings.llm_provider or "").lower()
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=settings.llm_model, api_key=settings.llm_api_key, temperature=0)
    if provider in ("openai", "groq"):
        from langchain_openai import ChatOpenAI

        base = os.environ.get("LLM_BASE_URL") or ("https://api.groq.com/openai/v1" if provider == "groq" else None)
        key = settings.llm_api_key or os.environ.get("GROQ_API_KEY") or ""
        model = settings.llm_model or ("llama-3.3-70b-versatile" if provider == "groq" else "gpt-4o-mini")
        return ChatOpenAI(model=model, api_key=key, base_url=base, temperature=0)
    if provider == "ollama":
        from langchain_ollama import ChatOllama

        host = (os.environ.get("OLLAMA_URL") or os.environ.get("LLM_BASE_URL") or "http://localhost:11434").replace("/v1", "")
        return ChatOllama(model=settings.llm_model or "llama3.1:8b", base_url=host.split("#")[0].strip(), temperature=0)
    raise ValueError(f"Unknown LLM provider {settings.llm_provider}")
