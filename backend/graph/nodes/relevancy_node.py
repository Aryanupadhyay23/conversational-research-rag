import asyncio
import logging
import re
from typing import List, Tuple
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser

from backend.schemas.state import GraphState
from backend.schemas.relevancy import DocumentRelevanceGrade
from backend.prompts.relevancy import relevancy_prompt

logger = logging.getLogger(__name__)

async def _grade_single_doc(doc: Document, query: str, eval_llm) -> Tuple[Document, bool, str]:
    """Grade a single document chunk for relevance to the user query."""
    try:
        # Try structured output first
        chain = relevancy_prompt | eval_llm.with_structured_output(DocumentRelevanceGrade)
        res: DocumentRelevanceGrade = await asyncio.wait_for(
            chain.ainvoke({"query": query, "document": doc.page_content}),
            timeout=5.0
        )
        is_rel = res.binary_score.strip().lower() == "yes"
        return doc, is_rel, res.reasoning
    except Exception:
        # Fallback to plain text output with regex matching
        try:
            str_chain = relevancy_prompt | eval_llm | StrOutputParser()
            raw_text = await asyncio.wait_for(
                str_chain.ainvoke({"query": query, "document": doc.page_content}),
                timeout=4.0
            )
            raw_lower = raw_text.lower()
            # Match "yes" or positive indicator
            is_rel = bool(re.search(r"\b(yes|relevant|supported)\b", raw_lower)) and not bool(re.search(r"\b(not relevant|binary_score\s*:\s*no)\b", raw_lower))
            return doc, is_rel, raw_text[:80]
        except Exception as e:
            # On network timeout, conservatively accept top chunk to prevent stall
            logger.debug(f"Relevancy grading fallback error: {e}")
            return doc, True, "Heuristic fallback"

async def relevancy_node(state: GraphState, eval_llm) -> dict:
    """
    CRAG / Self-RAG Relevancy Check:
    Evaluates retrieved chunks using eval_llm to filter out irrelevant noise.
    If no chunks are relevant, routes to query_rewrite_node for query expansion/reformulation.
    """
    docs: List[Document] = state.get("documents", [])
    current_query = state.get("current_query", state["question"])
    logs = list(state.get("reflection_logs", []))

    if not docs:
        logs.append(f"[Relevancy Check] No documents found to evaluate for query '{current_query}'.")
        return {"documents": [], "is_relevant": False, "reflection_logs": logs}

    candidates = docs[:4]
    
    # Run concurrent grading across candidate documents for minimal latency
    try:
        tasks = [_grade_single_doc(d, current_query, eval_llm) for d in candidates]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        relevant_docs = []
        graded_notes = []

        for r in results:
            if isinstance(r, Exception):
                continue
            doc, is_rel, reason = r
            if is_rel:
                relevant_docs.append(doc)
                graded_notes.append(f"KEEP ({reason})")
            else:
                graded_notes.append(f"DROP ({reason})")

        if relevant_docs:
            logs.append(
                f"[Relevancy Check] Evaluated {len(candidates)} passages: {len(relevant_docs)} deemed relevant. Proceeding."
            )
            return {
                "documents": relevant_docs,
                "is_relevant": True,
                "reflection_logs": logs
            }
        else:
            logs.append(
                f"[Relevancy Check] None of the {len(candidates)} passages answered '{current_query}'. Triggering Query Rewrite loop."
            )
            return {
                "documents": [],
                "is_relevant": False,
                "reflection_logs": logs
            }

    except Exception as e:
        logger.warning(f"Relevancy node encountered exception: {e}. Gracefully retaining top documents.")
        logs.append(f"[Relevancy Check] Heuristic fallback applied: {e}")
        return {
            "documents": candidates,
            "is_relevant": True,
            "reflection_logs": logs
        }
