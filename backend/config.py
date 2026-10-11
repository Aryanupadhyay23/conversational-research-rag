import os
import logging
from dotenv import load_dotenv
from langchain_core.language_models import BaseChatModel

logger = logging.getLogger(__name__)

# Load environment file (supports .env.rag, ENV_FILE path, or default .env)
env_file_path = os.getenv("ENV_FILE")
if env_file_path and os.path.exists(env_file_path):
    load_dotenv(env_file_path, override=True)
elif os.path.exists(".env.rag"):
    load_dotenv(".env.rag", override=True)
elif os.path.exists(".env"):
    load_dotenv(".env", override=True)
else:
    load_dotenv(override=True)

def _clean_env(val: str | None) -> str:
    """Strip whitespace and surrounding quotes."""
    if not val:
        return ""
    val = val.strip()
    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
        val = val[1:-1].strip()
    return val

# --- Ollama Cloud Configuration (Multi-Key Fallback) ---
OLLAMA_KEY_NAMES = [
    "OLLAMA_API_KEY_ONE", "OLLAMA_API_KEY_1",
    "OLLAMA_API_KEY_TWO", "OLLAMA_API_KEY_2",
    "OLLAMA_API_KEY_THREE", "OLLAMA_API_KEY_3",
    "OLLAMA_API_KEY"
]
OLLAMA_API_KEYS = list(dict.fromkeys(
    _clean_env(os.getenv(k)) for k in OLLAMA_KEY_NAMES if _clean_env(os.getenv(k))
))
OLLAMA_API_KEY = OLLAMA_API_KEYS[0] if OLLAMA_API_KEYS else ""

OLLAMA_HOST = _clean_env(os.getenv("OLLAMA_HOST") or os.getenv("OLLAMA_BASE_URL") or "https://ollama.com")
DEFAULT_LLM_MODEL = _clean_env(os.getenv("OLLAMA_MODEL")) or "gpt-oss:120b"

# --- Embeddings & Search ---
GOOGLE_API_KEY = _clean_env(os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"))
TAVILY_API_KEY = _clean_env(os.getenv("TAVILY_API_KEY"))

if GOOGLE_API_KEY:
    os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY
if TAVILY_API_KEY:
    os.environ["TAVILY_API_KEY"] = TAVILY_API_KEY

GEMINI_EMBEDDING_MODEL = _clean_env(os.getenv("GEMINI_EMBEDDING_MODEL")) or "gemini-embedding-2"
EMBEDDING_DIMENSION = int(_clean_env(os.getenv("EMBEDDING_DIMENSION")) or "768")

# --- Retrieval & Memory Settings ---
MAX_RETRIEVAL_ATTEMPTS = 3
MAX_QUERY_REWRITES = 1
RETRIEVER_K = 5
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
MAX_CHAT_HISTORY_MESSAGES = 10

def _create_ollama_client(model_name: str, api_key: str, temperature: float, key_idx: int, total_keys: int):
    """Instantiate a ChatOllama instance with Authorization header and failure logging."""
    from langchain_ollama import ChatOllama
    client_kwargs = (
        {"headers": {"Authorization": f"Bearer {api_key}"}}
        if api_key
        else {}
    )
    model = ChatOllama(
        model=model_name,
        base_url=OLLAMA_HOST,
        temperature=temperature,
        client_kwargs=client_kwargs,
    )

    def on_error(run):
        err = getattr(run, "error", "")
        masked = f"{api_key[:6]}...{api_key[-4:]}" if len(api_key) > 8 else "***"
        if key_idx < total_keys:
            logger.warning(
                f"Ollama request failed on API key #{key_idx} ({masked}): {err}. "
                f"Automatically failing over to key #{key_idx + 1}..."
            )
        else:
            logger.error(
                f"Ollama request failed on final API key #{key_idx} ({masked}): {err}. "
                "No more fallback keys available."
            )

    return model.with_listeners(on_error=on_error)

def get_llm(temperature: float = 0.2) -> BaseChatModel:
    """Return generation LLM using LangChain ChatOllama with multi-key fallback."""
    keys = OLLAMA_API_KEYS if OLLAMA_API_KEYS else ([OLLAMA_API_KEY] if OLLAMA_API_KEY else [""])
    total_keys = len(keys)

    models = [
        _create_ollama_client(DEFAULT_LLM_MODEL, key, temperature, idx + 1, total_keys)
        for idx, key in enumerate(keys)
    ]

    if len(models) == 1:
        return models[0]
    return models[0].with_fallbacks(models[1:])

def get_eval_llm() -> BaseChatModel:
    """Return deterministic evaluation LLM with multi-key fallback."""
    return get_llm(temperature=0.0)

def get_embeddings():
    """Return native Google Gemini Embeddings."""
    from langchain_google_genai import GoogleGenerativeAIEmbeddings
    return GoogleGenerativeAIEmbeddings(
        model=GEMINI_EMBEDDING_MODEL,
        google_api_key=GOOGLE_API_KEY,
        output_dimensionality=EMBEDDING_DIMENSION
    )
