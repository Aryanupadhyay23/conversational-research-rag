import asyncio
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, AsyncGenerator
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.retrievers import BaseRetriever
from langgraph.checkpoint.memory import MemorySaver

from backend.graph.workflow import build_graph
from backend.utils.helpers import run_async_safe, extract_sources_metadata

@dataclass
class QueryResult:
    """Standardized response from the Agent Workflow service."""
    answer: str
    route: str = "retrieve"
    reflection_logs: List[str] = field(default_factory=list)
    sources: List[Dict[str, Any]] = field(default_factory=list)
    claim_analysis: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

class AgentService:
    """Core business service managing LangGraph execution and conversational checkpointer."""

    def __init__(self, retriever: Optional[BaseRetriever] = None):
        self.retriever = retriever
        self.checkpointer = MemorySaver()
        self.graph = None
        self._compile()

    def _compile(self):
        """Compile the StateGraph."""
        self.graph = build_graph(
            retriever=self.retriever,
            checkpointer=self.checkpointer
        )

    def set_retriever(self, retriever: BaseRetriever):
        """Update retriever and recompile workflow."""
        self.retriever = retriever
        self._compile()

    def clear_memory(self):
        """Reset conversation memory checkpointer."""
        self.checkpointer = MemorySaver()
        self._compile()

    def _build_initial_state(self, user_query: str) -> dict:
        """Create clean initial GraphState dictionary."""
        return {
            "messages": [HumanMessage(content=user_query)],
            "question": user_query,
            "current_query": user_query,
            "route": "retrieve",
            "documents": [],
            "retrieval_attempts": 0,
            "rewrite_count": 0,
            "claim_analysis": None,
            "is_relevant": False,
            "generation": "",
            "formatted_response": None,
            "metadata": {},
            "reflection_logs": []
        }

    async def aexecute_query(self, user_query: str, session_id: str = "default_session") -> QueryResult:
        """Execute query asynchronously without blocking event loops."""
        if not self.graph:
            self._compile()

        config = RunnableConfig(configurable={"thread_id": session_id})
        initial_state = self._build_initial_state(user_query)

        final_state = await self.graph.ainvoke(initial_state, config=config)

        answer = final_state.get("generation", "No response generated.")
        route = final_state.get("route", "retrieve")
        logs = final_state.get("reflection_logs", [])
        metadata = final_state.get("metadata", {})
        claim_analysis = final_state.get("claim_analysis")
        sources = metadata.get("sources") or extract_sources_metadata(final_state.get("documents", []))

        return QueryResult(
            answer=answer,
            route=route,
            reflection_logs=logs,
            sources=sources,
            claim_analysis=claim_analysis,
            metadata=metadata
        )

    def execute_query(self, user_query: str, session_id: str = "default_session") -> QueryResult:
        """Synchronous wrapper for Streamlit or sync callers."""
        return run_async_safe(self.aexecute_query(user_query, session_id))

    async def astream_query(
        self,
        user_query: str,
        session_id: str = "default_session"
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream progress status, tokens, and final answer/citations asynchronously."""
        if not self.graph:
            self._compile()

        config = RunnableConfig(configurable={"thread_id": session_id})
        initial_state = self._build_initial_state(user_query)

        has_streamed_tokens = False
        active_node = ""

        try:
            async for event in self.graph.astream_events(initial_state, config=config, version="v2"):
                kind = event.get("event")
                name = event.get("name", "")

                if kind == "on_chain_start":
                    active_node = name
                    yield {"type": "status", "node": name}

                elif kind == "on_chat_model_stream":
                    metadata = event.get("metadata", {})
                    # Stream tokens when generating answer
                    if metadata.get("langgraph_node") == "generate_answer" or active_node == "generate_answer":
                        chunk = event.get("data", {}).get("chunk")
                        content = chunk.content if hasattr(chunk, "content") else str(chunk)
                        if content:
                            has_streamed_tokens = True
                            yield {"type": "token", "content": content}

            # Final State Resolution
            try:
                snapshot = await self.graph.aget_state(config)
                final_state = snapshot.values if snapshot else {}
            except Exception:
                final_state = {}

            answer = final_state.get("generation", "")
            route = final_state.get("route", "retrieve")
            logs = final_state.get("reflection_logs", [])
            metadata = final_state.get("metadata", {})
            claim_analysis = final_state.get("claim_analysis")
            sources = metadata.get("sources") or extract_sources_metadata(final_state.get("documents", []))

            # If tokens were not streamed by LLM, yield complete answer
            if not has_streamed_tokens and answer:
                yield {"type": "token", "content": answer}

            yield {
                "type": "final",
                "answer": answer,
                "route": route,
                "sources": sources,
                "claim_analysis": claim_analysis,
                "reflection_logs": logs,
                "metadata": metadata
            }

        except Exception:
            # Fallback to direct robust query execution if streaming events fail
            try:
                res = await self.aexecute_query(user_query, session_id)
                yield {"type": "token", "content": res.answer}
                yield {
                    "type": "final",
                    "answer": res.answer,
                    "route": res.route,
                    "sources": res.sources,
                    "claim_analysis": res.claim_analysis,
                    "reflection_logs": res.reflection_logs,
                    "metadata": res.metadata
                }
            except Exception as fallback_err:
                yield {"type": "error", "error": str(fallback_err)}
