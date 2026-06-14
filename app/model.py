from typing import Type, Any
from langchain_core.language_models.chat_models import BaseChatModel

def get_llm(
    provider: str,
    model_name: str,
    api_key: str | None = None,
)-> BaseChatModel:
    # Map provider to (import_path, class_name, install_package)
    provider_config = {
        "ollama": ("langchain_ollama", "ChatOllama", "langchain-ollama"),
        "openai": ("langchain_openai", "ChatOpenAI", "langchain-openai"),
        "gemini": ("langchain_google_genai", "ChatGoogleGenerativeAI", "langchain-google-genai"),
        "grok": ("langchain_xai", "ChatXAI", "langchain-xai"),
        "groq":   ("langchain_groq", "ChatGroq", "langchain-groq"),
    }
    
    if provider not in provider_config:
        raise ValueError(f"Unsupported provider: {provider}")
    
    module_name, class_name, package_name = provider_config[provider]
    
    try:
        module = __import__(module_name, fromlist=[class_name])
        llm_class = getattr(module, class_name)
    except ImportError:
        raise ImportError(
            f"Provider '{provider}' requires {package_name}. "
            f"Install it with: pip install {package_name}"
        )
    
    # Provider-specific parameter handling
    if provider == "ollama":
        return llm_class(model=model_name, temperature=0)
    elif provider == "openai":
        return llm_class(model=model_name, api_key=api_key, temperature=0)
    elif provider == "gemini":
        return llm_class(model=model_name, google_api_key=api_key, temperature=0)
    else:  # grok
        return llm_class(model=model_name, api_key=api_key, temperature=0)