import asyncio
import logging
from langchain_core.messages import AIMessage, ToolMessage, filter_messages

from backend.schemas.state import GraphState
from backend.prompts.agent import agent_prompt
from backend.tools.tools import search_tavily_async, execute_retriever
from backend.config import MAX_CHAT_HISTORY_MESSAGES, MAX_RETRIEVAL_ATTEMPTS
from backend.graph.nodes.rewrite_node import rewrite_query_with_context

from backend.utils.helpers import filter_clean_chat_history

logger = logging.getLogger(__name__)

async def agent_node(state: GraphState, agent_llm, retriever, eval_llm=None) -> dict:
    """Agent evaluates current query and context to dispatch tools or conclude."""
    current_query = state.get("current_query", state["question"])
    messages = list(state.get("messages", []))
    logs = list(state.get("reflection_logs", []))
    retrieval_attempts = state.get("retrieval_attempts", 0)
    needs_retrieval = state.get("needs_retrieval", False)

    # Filter conversation history cleanly without orchestration messages
    history = filter_clean_chat_history(messages, current_question=state.get("question", ""), max_messages=MAX_CHAT_HISTORY_MESSAGES)

    # On first retrieval pass: Use LLM to contextualize & reformulate query using chat history
    if retrieval_attempts == 0 and not needs_retrieval and history and eval_llm:
        rewritten_q, rationale = await rewrite_query_with_context(current_query, history, eval_llm)
        if rewritten_q and rewritten_q.strip():
            logs.append(
                f"[Agent LLM Rewriter] Reformulated query using chat history: '{current_query}' -> '{rewritten_q}' ({rationale})."
            )
            current_query = rewritten_q

    ai_msg = None
    # Dispatch tools automatically on first pass OR when rewritten query requests new retrieval
    if retrieval_attempts == 0 or needs_retrieval:
        tool_calls = []
        if retriever is not None:
            tool_calls.append({
                "name": "retrieve_from_vectorstore",
                "args": {"query": current_query},
                "id": f"call_vec_{retrieval_attempts}"
            })
        tool_calls.append({
            "name": "web_search",
            "args": {"query": current_query},
            "id": f"call_web_{retrieval_attempts}"
        })
        ai_msg = AIMessage(content="Dispatching retrieval tools.", tool_calls=tool_calls)
    else:
        try:
            prompt_input = await agent_prompt.ainvoke({"history": history, "query": current_query})
            ai_msg = await agent_llm.ainvoke(prompt_input)
        except Exception:
            ai_msg = AIMessage(content="Retrieved context sufficient. Proceeding to relevancy check.")

    tool_call_names = [tc.get("name") for tc in getattr(ai_msg, "tool_calls", [])]
    logs.append(f"[Agent Node] Evaluated state. Tool calls: {tool_call_names}")
    return {
        "current_query": current_query,
        "needs_retrieval": False,
        "messages": [ai_msg],
        "reflection_logs": logs
    }

async def execute_tools_node(state: GraphState, retriever) -> dict:
    """Executes requested tool calls concurrently: F1 Vector Store + F2 Web Search."""
    last_msg = state["messages"][-1]
    tool_calls = getattr(last_msg, "tool_calls", [])
    logs = list(state.get("reflection_logs", []))
    docs = list(state.get("documents", []))
    metadata = dict(state.get("metadata", {}))
    tools_used = list(metadata.get("tools_used", []))
    tool_messages = []

    async def _execute_single_tool(tc):
        name = tc.get("name")
        args = tc.get("args", {})
        call_id = tc.get("id", f"call_{name}")
        q = args.get("query", state.get("current_query", state["question"]))

        if name == "retrieve_from_vectorstore":
            chunks = await execute_retriever(retriever, q)
            msg = ToolMessage(content=f"Retrieved {len(chunks)} chunks from vector store.", tool_call_id=call_id)
            log = f"[F1: Vector Store] Retrieved {len(chunks)} chunks for query: '{q}'."
            return "retrieve_from_vectorstore", chunks, msg, log
        elif name == "web_search":
            web_docs = await search_tavily_async(q, max_results=4)
            msg = ToolMessage(content=f"Retrieved {len(web_docs)} web / academic search results.", tool_call_id=call_id)
            log = f"[F2: Web Search] Retrieved {len(web_docs)} sources via Tavily/ArXiv for: '{q}'."
            return "web_search", web_docs, msg, log
        return None, [], None, None

    # Execute all requested tools concurrently in parallel
    results = await asyncio.gather(*[_execute_single_tool(tc) for tc in tool_calls])

    for tool_name, new_docs, msg, log in results:
        if tool_name:
            tools_used.append(tool_name)
            docs.extend(new_docs)
            tool_messages.append(msg)
            logs.append(log)

    metadata["tools_used"] = list(set(tools_used))
    retrieval_attempts = state.get("retrieval_attempts", 0) + 1
    logs.append(f"[G: Tool Results] Completed concurrent tool batch (Attempt {retrieval_attempts}/{MAX_RETRIEVAL_ATTEMPTS}).")

    return {
        "messages": tool_messages,
        "documents": docs,
        "retrieval_attempts": retrieval_attempts,
        "metadata": metadata,
        "reflection_logs": logs
    }
