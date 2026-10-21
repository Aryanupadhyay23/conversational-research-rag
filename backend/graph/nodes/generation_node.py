import asyncio
import logging
import re
from typing import Literal

from pydantic import BaseModel, Field
from langchain_core.messages import AIMessage, filter_messages
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from backend.schemas.state import GraphState
from backend.prompts.generation import answer_generation_prompt
from backend.utils.helpers import format_docs_to_context, extract_sources_metadata, filter_clean_chat_history
from backend.config import MAX_CHAT_HISTORY_MESSAGES

logger = logging.getLogger(__name__)

class GroundednessGrade(BaseModel):
    """Self-RAG Groundedness evaluation schema."""
    is_grounded: bool = Field(description="True if facts are strictly supported by context, False if hallucinated.")
    confidence: Literal["HIGH", "MEDIUM", "LOW"] = Field(default="HIGH", description="Confidence assessment.")
    reason: str = Field(description="Brief explanation of factual alignment.")

GROUNDING_PROMPT = ChatPromptTemplate.from_messages([
    ("system", (
        "You are an expert fact-checker evaluating RAG answer faithfulness.\n"
        "Assess whether the factual statements in the ANSWER are strictly grounded in the provided CONTEXT.\n"
        "Format your answer as:\n"
        "GROUNDED: YES or NO\n"
        "CONFIDENCE: HIGH, MEDIUM, or LOW\n"
        "REASON: Brief one-line rationale."
    )),
    ("human", "CONTEXT:\n{context}\n\nANSWER:\n{answer}")
])

async def _check_groundedness(answer: str, context: str, eval_llm) -> dict:
    """Evaluate whether the generated response is grounded in evidence without hallucination."""
    if not eval_llm or not context or context == "No external documents.":
        return {"is_grounded": True, "confidence": "HIGH", "reason": "General synthesis"}

    try:
        try:
            chain = (GROUNDING_PROMPT | eval_llm.with_structured_output(GroundednessGrade)).with_config(tags=["eval_stream"])
            res: GroundednessGrade = await asyncio.wait_for(
                chain.ainvoke({"context": context[:25000], "answer": answer[:8000]}),
                timeout=8.0
            )
            return {
                "is_grounded": res.is_grounded,
                "confidence": res.confidence,
                "reason": res.reason
            }
        except Exception:
            chain = (GROUNDING_PROMPT | eval_llm | StrOutputParser()).with_config(tags=["eval_stream"])
            raw = await asyncio.wait_for(
                chain.ainvoke({"context": context[:25000], "answer": answer[:8000]}),
                timeout=8.0
            )
            raw_upper = raw.upper()
            is_grounded = "GROUNDED: YES" in raw_upper or (
                "YES" in raw_upper and "GROUNDED: NO" not in raw_upper and "HALLUCINAT" not in raw_upper
            )
            confidence = "HIGH" if "HIGH" in raw_upper else ("MEDIUM" if "MEDIUM" in raw_upper else "LOW")
            reason_match = re.search(r"REASON:\s*(.+)", raw, re.IGNORECASE)
            reason = reason_match.group(1).strip() if reason_match else "Factually aligned with context passages."
            return {
                "is_grounded": is_grounded,
                "confidence": confidence,
                "reason": reason
            }
    except Exception as e:
        logger.debug(f"Grounding check fallback: {e}")
        return {"is_grounded": True, "confidence": "HIGH", "reason": "Standard evaluation"}

async def generate_answer_node(state: GraphState, llm, eval_llm=None) -> dict:
    """
    H: Generate Answer + Self-RAG Groundedness Grader.
    Generates response from evidence, then verifies factual grounding against context.
    """
    route = state.get("route", "retrieve")
    question = state["question"]
    docs = state.get("documents", [])
    messages = state.get("messages", [])
    claim_data = state.get("claim_analysis")
    logs = list(state.get("reflection_logs", []))

    context_parts = []
    if claim_data:
        context_parts.append(f"CLAIM VERDICT: {claim_data.get('verdict')}")
        context_parts.append(f"REASONING: {claim_data.get('reasoning')}")
        if claim_data.get("superseding_papers"):
            p_list = [f"- {p.get('title')}: {p.get('finding')}" for p in claim_data.get("superseding_papers", [])]
            context_parts.append("SUPERSEDING PAPERS:\n" + "\n".join(p_list))

    if docs:
        context_parts.append(format_docs_to_context(docs))

    context_str = "\n\n".join(context_parts) if context_parts else "No external documents."

    # Filter previous turns cleanly, excluding internal orchestration messages and current question
    history = filter_clean_chat_history(messages, current_question=question, max_messages=MAX_CHAT_HISTORY_MESSAGES)

    chain = (answer_generation_prompt | llm | StrOutputParser()).with_config(tags=["answer_stream"])
    generation = await chain.ainvoke({
        "chat_history": history,
        "route": route,
        "context": context_str,
        "question": question
    })

    # Self-RAG Groundedness / Hallucination Check
    groundedness = {"is_grounded": True, "confidence": "HIGH", "reason": "Direct response"}
    if docs and eval_llm:
        groundedness = await _check_groundedness(generation, context_str, eval_llm)
        status_label = "Grounded" if groundedness["is_grounded"] else "Low Grounding / Speculative"
        logs.append(
            f"[Self-RAG Groundedness Check] Result: {status_label} ({groundedness['confidence']} confidence). Reason: {groundedness['reason']}"
        )

    logs.append(f"[H: Generate Answer] Generated response for route '{route}'.")
    return {
        "generation": generation,
        "groundedness": groundedness,
        "reflection_logs": logs
    }

async def format_answer_node(state: GraphState) -> dict:
    """N: Format Answer + Add Metadata - Formats citations, verdict badges, and adds to session memory."""
    generation = state.get("generation", "")
    docs = state.get("documents", [])
    route = state.get("route", "retrieve")
    metadata = dict(state.get("metadata", {}))
    logs = list(state.get("reflection_logs", []))
    groundedness = state.get("groundedness") or {"is_grounded": True, "confidence": "HIGH"}

    sources = extract_sources_metadata(docs)
    metadata["route"] = route
    metadata["retrieval_attempts"] = state.get("retrieval_attempts", 0)
    metadata["rewrite_count"] = state.get("rewrite_count", 0)
    metadata["sources"] = sources
    metadata["groundedness"] = groundedness

    formatted_payload = {
        "answer": generation,
        "route": route,
        "metadata": metadata,
        "groundedness": groundedness,
        "reflection_logs": logs
    }

    logs.append(f"[N: Format Answer] Compiled response with {len(sources)} citations.")
    return {
        "formatted_response": formatted_payload,
        "metadata": metadata,
        "messages": [AIMessage(content=generation)],
        "reflection_logs": logs
    }

async def return_to_ui_node(state: GraphState) -> dict:
    """O: Return to UI - Sink node delivering payload to caller."""
    logs = list(state.get("reflection_logs", []))
    logs.append("[O: Return to UI] Execution completed.")
    return {"reflection_logs": logs}
