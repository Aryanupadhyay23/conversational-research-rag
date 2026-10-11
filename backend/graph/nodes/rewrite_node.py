from langchain_core.messages import HumanMessage

from backend.schemas.state import GraphState
from backend.schemas.rewrite import QueryRewrite
from backend.prompts.rewrite import query_rewrite_prompt

async def query_rewrite_node(state: GraphState, eval_llm) -> dict:
    """L: Query Rewrite LLM - Reformulates search query using academic nomenclature."""
    current_query = state.get("current_query", state["question"])
    rewrite_count = state.get("rewrite_count", 0) + 1
    logs = list(state.get("reflection_logs", []))

    try:
        chain = query_rewrite_prompt | eval_llm.with_structured_output(QueryRewrite)
        res: QueryRewrite = await chain.ainvoke({"query": current_query})
        new_query = res.rewritten_query.strip()
        rationale = res.rationale
    except Exception as e:
        new_query = f"{current_query} research methodology"
        rationale = f"Heuristic fallback: {e}"

    logs.append(f"[Query Rewrite LLM] Rewrote query to '{new_query}' ({rationale}). Attempt: {rewrite_count}.")
    return {
        "current_query": new_query,
        "rewrite_count": rewrite_count,
        "reflection_logs": logs
    }

async def new_query_node(state: GraphState) -> dict:
    """M: New Query → Agent Node - Sets up state to loop back to Agent Node."""
    new_q = state.get("current_query", state["question"])
    logs = list(state.get("reflection_logs", []))
    logs.append(f"[New Query → Agent Node] Resubmitting rewritten query: '{new_q}'.")
    return {
        "messages": [HumanMessage(content=f"Searching again with reformulated query: {new_q}")],
        "reflection_logs": logs
    }
