import logging
import asyncio
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, AsyncGenerator
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.retrievers import BaseRetriever
from langgraph.checkpoint.base import BaseCheckpointSaver

from collections import OrderedDict
from backend.config import MAX_STORED_RETRIEVERS
from backend.database import get_checkpointer
from backend.graph.workflow import build_graph
from backend.utils.helpers import extract_sources_metadata

logger = logging.getLogger(__name__)


@dataclass
class QueryResult:
    """Standardized response from the Agent Workflow service."""
    answer: str
    route: str = "retrieve"
    reflection_logs: List[str] = field(default_factory=list)
    sources: List[Dict[str, Any]] = field(default_factory=list)
    claim_analysis: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

_service: Optional["AgentService"] = None

def get_agent_service() -> "AgentService":
    """Lazy initialize AgentService singleton."""
    global _service
    if _service is None:
        _service = AgentService()
    return _service

class AgentService:
    """Core business service managing LangGraph execution and conversational checkpointer."""

    def __init__(
        self,
        retriever: Optional[BaseRetriever] = None,
        checkpointer: Optional[BaseCheckpointSaver] = None
    ):
        self.retriever = retriever
        self.retrievers: OrderedDict[str, BaseRetriever] = OrderedDict()
        self.max_stored_retrievers = MAX_STORED_RETRIEVERS
        self.checkpointer = checkpointer or get_checkpointer()
        self.graph = None
        self._compile()

    def resolve_retriever(
        self,
        thread_id: Optional[str] = None,
        username: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Optional[BaseRetriever]:
        """
        Resolve the retriever for one conversation thread.

        Uploaded documents belong to their exact thread key. Falling back to a
        bare session ID or username would make documents from one chat available
        in another chat.
        """
        exact_thread = thread_id or (f"{username}:{session_id}" if username and session_id else None)
        if exact_thread and exact_thread in self.retrievers:
            self.retrievers.move_to_end(exact_thread)
            return self.retrievers[exact_thread]

        # A global retriever is only used when one was deliberately supplied to
        # the service; uploaded documents are never stored globally.
        return self.retriever

    def has_retriever(
        self,
        thread_id: Optional[str] = None,
        username: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> bool:
        """Check whether a retriever resolves for the given thread/session/user."""
        return self.resolve_retriever(thread_id=thread_id, username=username, session_id=session_id) is not None

    def _compile(self, custom_retriever: Optional[BaseRetriever] = None):
        """Compile the StateGraph with dynamic per-session retriever resolution."""
        def _resolve_active_retriever(config: Optional[RunnableConfig] = None) -> Optional[BaseRetriever]:
            if custom_retriever is not None:
                return custom_retriever
            if config and isinstance(config, dict):
                configurable = config.get("configurable", {})
                thread_id = configurable.get("thread_id")
                if thread_id:
                    return self.resolve_retriever(thread_id=thread_id)
            return self.retriever

        self.graph = build_graph(
            retriever=_resolve_active_retriever,
            checkpointer=self.checkpointer
        )

    def set_retriever(self, retriever: BaseRetriever, session_id: Optional[str] = None):
        """Update retriever for a session or globally without deleting indexed PDFs."""
        if session_id:
            self.retrievers[session_id] = retriever
            self.retrievers.move_to_end(session_id)

            # Enforce max stored retrievers cap (LRU eviction).
            while len(self.retrievers) > self.max_stored_retrievers:
                evicted_key, _ = self.retrievers.popitem(last=False)
                logger.info("Evicted LRU retriever for key '%s'", evicted_key)
        else:
            self.retriever = retriever

    def remove_session_retriever(self, session_id: str, username: Optional[str] = None):
        """Remove a session retriever while retaining its persistent documents."""
        if username:
            prefix = f"{username}:"
            keys_to_remove = [session_id if session_id.startswith(prefix) else f"{prefix}{session_id}"]
        else:
            keys_to_remove = [session_id]

        for key in keys_to_remove:
            if self.retrievers.pop(key, None) is not None:
                logger.info("Removed retriever for key '%s'", key)

    def clear_user_retrievers(self, username: str):
        """Remove all retrievers for a user's conversation threads."""
        prefix = f"{username}:"
        keys_to_remove = [k for k in list(self.retrievers.keys()) if k.startswith(prefix)]
        for key in keys_to_remove:
            self.retrievers.pop(key, None)
        logger.info("Cleared all stored retrievers for user '%s'", username)

    async def aclear_memory(self, session_id: Optional[str] = None, username: Optional[str] = None):
        """Reset conversation memory checkpointer asynchronously without blocking."""
        keys_to_delete = []
        if session_id:
            keys_to_delete.append(session_id)
            if username:
                keys_to_delete.append(f"{username}:{session_id}")

        if keys_to_delete:
            for k in keys_to_delete:
                if hasattr(self.checkpointer, "adelete_thread"):
                    try:
                        await self.checkpointer.adelete_thread(k)
                        logger.info("Cleared async conversation memory for thread '%s' in checkpointer.", k)
                    except Exception as e:
                        logger.warning("Failed to async delete thread '%s' from checkpointer: %s", k, e)
                elif hasattr(self.checkpointer, "delete_thread"):
                    try:
                        await asyncio.to_thread(self.checkpointer.delete_thread, k)
                        logger.info("Cleared conversation memory for thread '%s' via thread.", k)
                    except Exception as e:
                        logger.warning("Failed to delete thread '%s' from checkpointer: %s", k, e)
            return

        self.checkpointer = get_checkpointer()
        self._compile()

    def _build_initial_state(self, user_query: str) -> dict:
        """Create clean initial GraphState dictionary with groundedness and retrieval control."""
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
            "groundedness": None,
            "needs_retrieval": False,
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
        groundedness = final_state.get("groundedness") or metadata.get("groundedness")
        sources = metadata.get("sources") or extract_sources_metadata(final_state.get("documents", []))

        metadata["groundedness"] = groundedness
        return QueryResult(
            answer=answer,
            route=route,
            reflection_logs=logs,
            sources=sources,
            claim_analysis=claim_analysis,
            metadata=metadata
        )

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
        graph_started = False

        try:
            async for event in self.graph.astream_events(initial_state, config=config, version="v2"):
                kind = event.get("event")
                name = event.get("name", "")

                if kind == "on_chain_start":
                    graph_started = True
                    active_node = name
                    yield {"type": "status", "node": name}

                elif kind == "on_chat_model_stream":
                    metadata = event.get("metadata", {})
                    tags = event.get("tags", [])
                    # Stream tokens ONLY when generating main answer (tagged with "answer_stream")
                    # and ignore internal evaluation/grading chains that run in the same node
                    if (
                        metadata.get("langgraph_node") == "generate_answer"
                        or active_node == "generate_answer"
                    ):
                        if "eval_stream" in tags or "eval" in tags:
                            continue
                        if not tags or "answer_stream" in tags:
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
            groundedness = final_state.get("groundedness") or metadata.get("groundedness")
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
                "groundedness": groundedness,
                "reflection_logs": logs,
                "metadata": metadata
            }

        except Exception as stream_err:
            # Retrying on the same thread can append this user turn twice to the
            # checkpoint and repeat model/search work if streaming failed mid-run.
            # Only retry when no graph node started, so the original run had no
            # opportunity to mutate the conversation checkpoint.
            if graph_started:
                logger.exception("Streaming query failed after graph execution began")
                yield {"type": "error", "error": str(stream_err)}
                return

            try:
                res = await self.aexecute_query(user_query, session_id)
                yield {"type": "token", "content": res.answer}
                yield {
                    "type": "final",
                    "answer": res.answer,
                    "route": res.route,
                    "sources": res.sources,
                    "claim_analysis": res.claim_analysis,
                    "groundedness": res.metadata.get("groundedness"),
                    "reflection_logs": res.reflection_logs,
                    "metadata": res.metadata
                }
            except Exception as fallback_err:
                yield {"type": "error", "error": str(fallback_err)}
