import logging
from langchain_core.output_parsers import StrOutputParser

from backend.schemas.state import GraphState
from backend.schemas.rewrite import QueryRewrite
from backend.prompts.rewrite import query_rewrite_prompt
from backend.config import MAX_CHAT_HISTORY_MESSAGES

from backend.utils.helpers import filter_clean_chat_history

logger = logging.getLogger(__name__)

async def rewrite_query_with_context(
    query: str,
    history: list,
    eval_llm
) -> tuple[str, str]:
    """
    Reformulate query using conversational context, resolving pronouns and enriching
    with academic keywords for Qdrant vector and BM25 lexical search.
    Returns (rewritten_query, rationale).
    """
    if not eval_llm:
        return query, "No eval_llm configured"

    # 1. Attempt structured output
    try:
        chain = query_rewrite_prompt | eval_llm.with_structured_output(QueryRewrite)
        res: QueryRewrite = await chain.ainvoke({
            "chat_history": history,
            "query": query
        })
        if res and res.rewritten_query and res.rewritten_query.strip():
            return res.rewritten_query.strip(), res.rationale
    except Exception as ex:
        logger.debug("Structured output query rewrite fallback triggered: %s", ex)

    # 2. Fallback to direct string output parser
    try:
        str_chain = query_rewrite_prompt | eval_llm | StrOutputParser()
        raw = await str_chain.ainvoke({
            "chat_history": history,
            "query": query
        })
        cleaned = raw.strip().replace('"', '').split("\n")[0].strip()
        if cleaned:
            return cleaned, "Direct LLM contextual reformulation"
    except Exception as ex2:
        logger.debug("Direct LLM reformulation fallback triggered: %s", ex2)

    # 3. Heuristic fallback
    return f"{query} research methodology", "Heuristic academic keyword fallback"

async def query_rewrite_node(state: GraphState, eval_llm) -> dict:
    """L: Query Rewrite LLM - Reformulates search query using academic nomenclature and chat history."""
    current_query = state.get("current_query", state["question"])
    messages = list(state.get("messages", []))
    rewrite_count = state.get("rewrite_count", 0) + 1
    logs = list(state.get("reflection_logs", []))

    # Extract conversation history cleanly without orchestration messages
    history = filter_clean_chat_history(messages, current_question=state.get("question", ""), max_messages=MAX_CHAT_HISTORY_MESSAGES)

    new_query, rationale = await rewrite_query_with_context(current_query, history, eval_llm)

    logs.append(f"[Query Rewrite LLM] Rewrote query to '{new_query}' ({rationale}). Attempt: {rewrite_count}.")
    return {
        "current_query": new_query,
        "rewrite_count": rewrite_count,
        "reflection_logs": logs
    }

async def new_query_node(state: GraphState) -> dict:
    """M: New Query → Agent Node - Sets up state to loop back to Agent Node with retrieval active."""
    new_q = state.get("current_query", state["question"])
    logs = list(state.get("reflection_logs", []))
    logs.append(f"[New Query → Agent Node] Resubmitting rewritten query: '{new_q}'.")
    return {
        "needs_retrieval": True,
        "reflection_logs": logs
    }


