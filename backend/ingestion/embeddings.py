import os
from langchain_openai import OpenAIEmbeddings

def get_nomic_embeddings(api_key: str | None = None) -> OpenAIEmbeddings:
    """Return standard LangChain OpenAIEmbeddings directly without class overrides."""
    key = api_key or os.environ.get("EMBEDDING_MODEL_KEY", "")
    chunk_size = int(os.getenv("EMBEDDING_CHUNK_SIZE", "10"))
    return OpenAIEmbeddings(
        model=os.getenv("EMBEDDING_MODEL_NAME", "nomic-embed-text-v1.5"),
        base_url=os.getenv("EMBEDDING_BASE_URL", "https://nomicapi.duckdns.org/v1"),
        api_key=key,
        chunk_size=chunk_size,
        check_embedding_ctx_length=False,
    )
