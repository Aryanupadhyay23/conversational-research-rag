import os
import asyncio
import logging
from typing import List
from langchain_core.documents import Document
from langchain_core.tools import tool
from langchain_community.utilities.arxiv import ArxivAPIWrapper
from langchain_community.utilities.tavily_search import TavilySearchAPIWrapper

from backend.config import TAVILY_API_KEY

logger = logging.getLogger(__name__)

def search_arxiv(query: str, max_results: int = 4) -> List[Document]:
    """Search ArXiv public repository using LangChain's ArxivAPIWrapper returning individual documents."""
    try:
        wrapper = ArxivAPIWrapper(top_k_results=max_results, doc_content_chars_max=1200)
        # wrapper.load returns individual Document per paper with metadata
        if hasattr(wrapper, "load"):
            raw_docs = wrapper.load(query)
            docs = []
            for d in raw_docs:
                meta = dict(d.metadata or {})
                paper_title = meta.get("Title") or meta.get("title") or f"ArXiv Paper: {query}"
                entry_link = meta.get("Entry ID") or meta.get("link") or meta.get("id") or "https://arxiv.org"
                docs.append(Document(
                    page_content=d.page_content,
                    metadata={
                        "source": "arxiv",
                        "title": paper_title,
                        "link": entry_link,
                        "url": entry_link,
                        "doc_type": "academic_paper",
                        "authors": meta.get("Authors", "")
                    }
                ))
            if docs:
                return docs

        # Fallback to run() if load() is not available
        result_text = wrapper.run(query)
        if result_text and "No good Arxiv Result was found" not in result_text:
            return [Document(
                page_content=result_text,
                metadata={
                    "source": "arxiv",
                    "title": f"ArXiv Literature: {query}",
                    "link": "https://arxiv.org",
                    "url": "https://arxiv.org",
                    "doc_type": "academic_paper"
                }
            )]
    except Exception as e:
        logger.warning(f"ArXiv query failed: {e}")

    return []

async def search_arxiv_async(query: str, max_results: int = 4) -> List[Document]:
    """Asynchronously search ArXiv public repository without blocking the event loop."""
    return await asyncio.to_thread(search_arxiv, query, max_results)

def search_tavily(query: str, max_results: int = 4) -> List[Document]:
    """Search the web via LangChain TavilySearchAPIWrapper with automatic ArXiv fallback."""
    docs = []
    api_key = TAVILY_API_KEY or os.getenv("TAVILY_API_KEY", "").strip()

    if api_key:
        try:
            tavily = TavilySearchAPIWrapper(tavily_api_key=api_key)
            results = tavily.results(query=query, max_results=max_results)
            for res in results:
                docs.append(Document(
                    page_content=f"Title: {res.get('title')}\nURL: {res.get('url')}\nContent: {res.get('content')}",
                    metadata={
                        "source": "web",
                        "title": res.get("title", "Web Result"),
                        "url": res.get("url", ""),
                        "doc_type": "web"
                    }
                ))
            if docs:
                return docs
        except Exception as e:
            logger.warning(f"Tavily search failed ({e}), falling back to ArXiv.")

    # Graceful fallback to ArXiv
    fallback_docs = search_arxiv(query, max_results=max_results)
    if fallback_docs:
        return fallback_docs

    return []

async def search_tavily_async(query: str, max_results: int = 4) -> List[Document]:
    """Asynchronously search the web via Tavily or ArXiv without blocking the event loop."""
    return await asyncio.to_thread(search_tavily, query, max_results)

async def execute_retriever(retriever, query: str) -> List[Document]:
    """Query the LangChain retriever asynchronously and safely."""
    if retriever is None:
        return []
    # Prefix query for Nomic retrieval model if not already present
    search_query = query if query.startswith("search_query: ") else f"search_query: {query}"
    try:
        if hasattr(retriever, "ainvoke"):
            return await retriever.ainvoke(search_query)
        return await asyncio.to_thread(retriever.invoke, search_query)
    except Exception as e:
        logger.error(f"Retriever invocation failed: {e}")
        try:
            return await asyncio.to_thread(retriever.invoke, search_query)
        except Exception:
            return []

@tool
def retrieve_from_vectorstore(query: str) -> str:
    """Search indexed research papers and uploaded documents in the vector store."""
    return f"Search vector store for papers with query: {query}"

@tool
def web_search(query: str) -> str:
    """Search the web and scientific database via Tavily and ArXiv."""
    return f"Search web and literature via Tavily for query: {query}"
