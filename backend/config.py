import os

from dotenv import load_dotenv

load_dotenv()

TICKETMASTER_API_KEY = os.getenv("TICKETMASTER_API_KEY", "").strip()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq").strip().lower()
LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-oss-120b").strip()
ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",") if o.strip()
]
DEFAULT_TIMEZONE = os.getenv("DEFAULT_TIMEZONE", "UTC").strip()
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").strip().upper()


def active_llm_api_key() -> str:
    """
    Returns the active LLM API key based on the LLM_PROVIDER environment variable.
    """
    if LLM_PROVIDER == "groq":
        return GROQ_API_KEY
    elif LLM_PROVIDER == "openai":
        return OPENAI_API_KEY
    else:
        raise ValueError(f"Unsupported LLM provider: {LLM_PROVIDER}")


def validate_config():
    """
    Validates the configuration by checking if the necessary API keys are set.
    Raises ValueError if any required configuration is missing.
    """
    if not TICKETMASTER_API_KEY:
        raise ValueError(
            "Ticketmaster API Key is not set. "
            "Please set the TICKETMASTER_API_KEY environment variable."
        )

    if not active_llm_api_key():
        raise ValueError(
            f"API key for LLM provider '{LLM_PROVIDER}' is not set. "
            "Please set the matching GROQ_API_KEY or OPENAI_API_KEY."
        )
