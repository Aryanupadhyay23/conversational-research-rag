import os
import logging
from dotenv import load_dotenv
from langchain_core.language_models import BaseChatModel

logger = logging.getLogger(__name__)

# Locate and load environment file (supports project root, current directory, or EC2 host paths)
_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_BACKEND_DIR)

candidate_env_paths = [
    os.getenv("ENV_FILE"),
    os.path.join(os.getcwd(), ".env.rag"),
    os.path.join(_PROJECT_ROOT, ".env.rag"),
    "/home/ubuntu/.env.rag",
    "/home/ubuntu/app/.env.rag",
    os.path.join(os.getcwd(), ".env"),
    os.path.join(_PROJECT_ROOT, ".env"),
    "/home/ubuntu/.env",
    "/home/ubuntu/app/.env",
]

_loaded = False
for _path in candidate_env_paths:
    if _path and os.path.isfile(_path):
        load_dotenv(_path, override=True)
        _loaded = True
        break

if not _loaded:
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
    "OLLAMA_API_KEY_TWO", "OLLAMA_API_KEY_2", "OLLAMA_API_KEY_SECOND",
    "OLLAMA_API_KEY_THREE", "OLLAMA_API_KEY_3", "OLLAMA_API_KEY_THIRD",
    "OLLAMA_API_KEY"
]
OLLAMA_API_KEYS = list(dict.fromkeys(
    _clean_env(os.getenv(k)) for k in OLLAMA_KEY_NAMES if _clean_env(os.getenv(k))
))
OLLAMA_API_KEY = OLLAMA_API_KEYS[0] if OLLAMA_API_KEYS else ""

OLLAMA_HOST = _clean_env(os.getenv("OLLAMA_HOST") or os.getenv("OLLAMA_BASE_URL") or "https://ollama.com")
DEFAULT_LLM_MODEL = _clean_env(os.getenv("OLLAMA_MODEL")) or "gpt-oss:120b"
OLLAMA_NUM_CTX = int(_clean_env(os.getenv("OLLAMA_NUM_CTX")) or "131072")

# --- Embeddings & Search ---
EMBEDDING_MODEL_KEY = _clean_env(os.getenv("EMBEDDING_MODEL_KEY"))
EMBEDDING_BASE_URL = _clean_env(os.getenv("EMBEDDING_BASE_URL")) or "https://nomicapi.duckdns.org/v1"
EMBEDDING_MODEL_NAME = _clean_env(os.getenv("EMBEDDING_MODEL_NAME")) or "nomic-embed-text-v1.5"
EMBEDDING_DIMENSION = int(_clean_env(os.getenv("EMBEDDING_DIMENSION")) or "768")
EMBEDDING_CHUNK_SIZE = int(_clean_env(os.getenv("EMBEDDING_CHUNK_SIZE")) or "10")
EMBEDDING_TIMEOUT = float(_clean_env(os.getenv("EMBEDDING_TIMEOUT")) or "60.0")
EMBEDDING_MAX_WORKERS = int(_clean_env(os.getenv("EMBEDDING_MAX_WORKERS")) or "1")
BASELINE_EMBEDDING_LATENCY = float(_clean_env(os.getenv("BASELINE_EMBEDDING_LATENCY")) or "1.07")
BASELINE_EMBEDDING_THROUGHPUT = float(_clean_env(os.getenv("BASELINE_EMBEDDING_THROUGHPUT")) or "0.93")

# Upload Limits
MAX_UPLOAD_FILES = int(_clean_env(os.getenv("MAX_UPLOAD_FILES")) or "10")
MAX_UPLOAD_MB_PER_FILE = int(_clean_env(os.getenv("MAX_UPLOAD_MB_PER_FILE")) or "25")

TAVILY_API_KEY = _clean_env(os.getenv("TAVILY_API_KEY"))

if TAVILY_API_KEY:
    os.environ["TAVILY_API_KEY"] = TAVILY_API_KEY

# --- Retrieval & Memory Settings ---
MAX_RETRIEVAL_ATTEMPTS = 3
MAX_QUERY_REWRITES = 1
RETRIEVER_K = int(_clean_env(os.getenv("RETRIEVER_K")) or "6")
CHUNK_SIZE = int(_clean_env(os.getenv("CHUNK_SIZE")) or "1200")
CHUNK_OVERLAP = int(_clean_env(os.getenv("CHUNK_OVERLAP")) or "200")
MAX_CHAT_HISTORY_MESSAGES = int(_clean_env(os.getenv("MAX_CHAT_HISTORY_MESSAGES")) or "20")
MAX_STORED_RETRIEVERS = int(_clean_env(os.getenv("MAX_STORED_RETRIEVERS")) or "20")

# --- Upstash Redis Checkpointer Settings ---
UPSTASH_REDIS_REST_URL = _clean_env(os.getenv("UPSTASH_REDIS_REST_URL"))
UPSTASH_REDIS_REST_TOKEN = _clean_env(os.getenv("UPSTASH_REDIS_REST_TOKEN"))


def _create_ollama_client(model_name: str, api_key: str, temperature: float, key_idx: int, total_keys: int):
    """Instantiate a ChatOllama instance with Authorization header, context window, and failure logging."""
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
        num_ctx=OLLAMA_NUM_CTX,
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
    """Return standard LangChain OpenAIEmbeddings directly."""
    from backend.ingestion.embeddings import get_nomic_embeddings
    api_key = EMBEDDING_MODEL_KEY or _clean_env(os.getenv("EMBEDDING_MODEL_KEY"))
    if not api_key:
        raise ValueError("EMBEDDING_MODEL_KEY is missing in your .env.rag file.")
    return get_nomic_embeddings(api_key=api_key)
