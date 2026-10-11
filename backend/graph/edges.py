from typing import Literal

from backend.schemas.state import GraphState
from backend.config import MAX_RETRIEVAL_ATTEMPTS, MAX_QUERY_REWRITES

def route_query(state: GraphState) -> Literal["agent_node", "claim_verification", "generate_answer"]:
    """B: Router edge determining which branch to take."""
    route = state.get("route", "retrieve")
    if route == "verify_claim":
        return "claim_verification"
    elif route == "direct_answer":
        return "generate_answer"
    return "agent_node"

def check_agent_tool_calls(state: GraphState) -> Literal["execute_tools", "generate_answer", "relevancy_check"]:
    """C -> E / J: Checks retrieval limit and tool calls."""
    if state.get("retrieval_attempts", 0) >= MAX_RETRIEVAL_ATTEMPTS:
        return "generate_answer"

    messages = state.get("messages", [])
    if messages:
        last_msg = messages[-1]
        tool_calls = getattr(last_msg, "tool_calls", None)
        if tool_calls and len(tool_calls) > 0:
            return "execute_tools"

    return "relevancy_check"

def check_relevancy(state: GraphState) -> Literal["generate_answer", "query_rewrite"]:
    """I -> K: Relevancy decision routing."""
    is_relevant = state.get("is_relevant", False)
    rewrite_count = state.get("rewrite_count", 0)

    if is_relevant:
        return "generate_answer"
    elif rewrite_count < MAX_QUERY_REWRITES:
        return "query_rewrite"
    return "generate_answer"
