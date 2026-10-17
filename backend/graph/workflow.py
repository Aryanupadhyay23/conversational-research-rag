from typing import Optional
from langgraph.graph import StateGraph, START, END
from langchain_core.retrievers import BaseRetriever
from langgraph.checkpoint.base import BaseCheckpointSaver

from backend.schemas.state import GraphState
from backend.config import get_llm, get_eval_llm
from backend.tools.tools import retrieve_from_vectorstore, web_search

# Import separated nodes
from backend.graph.nodes import (
    router_node,
    agent_node,
    execute_tools_node,
    relevancy_node,
    query_rewrite_node,
    new_query_node,
    claim_verification_node,
    claim_web_search_node,
    claim_analysis_node,
    claim_verdict_node,
    generate_answer_node,
    format_answer_node,
    return_to_ui_node,
)

# Import routing edges
from backend.graph.edges import (
    route_query,
    check_agent_tool_calls,
    check_relevancy,
)

def build_graph(
    retriever: Optional[BaseRetriever] = None,
    checkpointer: Optional[BaseCheckpointSaver] = None,
    llm = None,
    eval_llm = None
):
    """
    Compile the Agent Workflow StateGraph in a single clean compilation file:
    User Query -> Router -> (Retrieve | Verify Claim | Direct Answer)
    """
    llm = llm or get_llm()
    eval_llm = eval_llm or get_eval_llm()

    try:
        agent_llm = llm.bind_tools([retrieve_from_vectorstore, web_search])
    except Exception:
        agent_llm = llm

    workflow = StateGraph(GraphState)

    # Async node bindings
    async def _router(state: GraphState) -> dict:
        return await router_node(state, eval_llm)

    async def _agent(state: GraphState) -> dict:
        return await agent_node(state, agent_llm, retriever, eval_llm=eval_llm)

    async def _tools(state: GraphState) -> dict:
        return await execute_tools_node(state, retriever)

    async def _relevancy(state: GraphState) -> dict:
        return await relevancy_node(state, eval_llm)

    async def _rewrite(state: GraphState) -> dict:
        return await query_rewrite_node(state, eval_llm)

    async def _claim_analysis(state: GraphState) -> dict:
        return await claim_analysis_node(state, eval_llm)

    async def _generate(state: GraphState) -> dict:
        return await generate_answer_node(state, llm, eval_llm)

    # 1. Register Nodes
    workflow.add_node("router", _router)
    workflow.add_node("agent_node", _agent)
    workflow.add_node("execute_tools", _tools)
    workflow.add_node("relevancy_check", _relevancy)
    workflow.add_node("query_rewrite", _rewrite)
    workflow.add_node("new_query_to_agent", new_query_node)

    workflow.add_node("claim_verification", claim_verification_node)
    workflow.add_node("claim_web_search", claim_web_search_node)
    workflow.add_node("claim_analysis", _claim_analysis)
    workflow.add_node("claim_verdict", claim_verdict_node)

    workflow.add_node("generate_answer", _generate)
    workflow.add_node("format_answer", format_answer_node)
    workflow.add_node("return_to_ui", return_to_ui_node)

    # 2. Wire Edges
    workflow.add_edge(START, "router")

    # Router Conditional Edge
    workflow.add_conditional_edges(
        "router",
        route_query,
        {
            "agent_node": "agent_node",
            "claim_verification": "claim_verification",
            "generate_answer": "generate_answer",
        }
    )

    # Agent Tool Loop
    workflow.add_conditional_edges(
        "agent_node",
        check_agent_tool_calls,
        {
            "execute_tools": "execute_tools",
            "relevancy_check": "relevancy_check",
            "generate_answer": "generate_answer",
        }
    )
    workflow.add_edge("execute_tools", "agent_node")

    # Relevancy & Query Rewrite Loop
    workflow.add_conditional_edges(
        "relevancy_check",
        check_relevancy,
        {
            "generate_answer": "generate_answer",
            "query_rewrite": "query_rewrite",
        }
    )
    workflow.add_edge("query_rewrite", "new_query_to_agent")
    workflow.add_edge("new_query_to_agent", "agent_node")

    # Claim Verification Pipeline
    workflow.add_edge("claim_verification", "claim_web_search")
    workflow.add_edge("claim_web_search", "claim_analysis")
    workflow.add_edge("claim_analysis", "claim_verdict")
    workflow.add_edge("claim_verdict", "generate_answer")

    # Output Pipeline
    workflow.add_edge("generate_answer", "format_answer")
    workflow.add_edge("format_answer", "return_to_ui")
    workflow.add_edge("return_to_ui", END)

    return workflow.compile(checkpointer=checkpointer)
