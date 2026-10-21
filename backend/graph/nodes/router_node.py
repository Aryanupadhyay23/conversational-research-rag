import logging
from langchain_core.output_parsers import StrOutputParser

from backend.schemas.state import GraphState
from backend.schemas.router import RouterDecision
from backend.prompts.router import router_prompt

import re

logger = logging.getLogger(__name__)

async def router_node(state: GraphState, eval_llm) -> dict:
    """Route user query to 'retrieve', 'verify_claim', or 'direct_answer' with high-performance routing."""
    question = state["question"]
    q_clean = question.strip().lower()
    logs = list(state.get("reflection_logs", []))

    # Fast-path 1: Conversational pleasantries & greetings
    greetings = ["hi", "hello", "hey", "good morning", "good evening", "how are you", "thanks", "thank you", "who are you", "help"]
    if any(q_clean == g or q_clean.startswith(g + " ") for g in greetings) and len(q_clean.split()) <= 6:
        decision = "direct_answer"
        reason = "Conversational greeting detected."

    # Fast-path 2: Explicit claim verification intent (word boundary check to avoid substrings like 'improve' or 'disclaimer')
    elif re.search(r"\b(verify|fact check|is it true|debunk|claim|claims|prove|proves|true or false)\b", q_clean):
        decision = "verify_claim"
        reason = "Claim verification keyword detected."

    # Fast-path 3: Paper specific queries
    elif any(kw in q_clean for kw in ["in this paper", "the paper", "uploaded pdf", "in the document", "the author", "authors conclude", "section", "abstract", "proposed", "benchmark", "loss function", "architecture", "dataset", "table"]):
        decision = "retrieve"
        reason = "Document/paper reference detected."

    # Fast-path 4: Explicit trivia/general knowledge queries that clearly do not pertain to research papers
    elif any(q_clean.startswith(p) for p in ["what is the capital of", "who is the president", "weather in", "tell me a joke"]):
        decision = "direct_answer"
        reason = "Direct general trivia/entertainment query."

    # LLM classification with LangChain structured output
    else:
        try:
            try:
                chain = router_prompt | eval_llm.with_structured_output(RouterDecision)
                res: RouterDecision = await chain.ainvoke({"question": question})
                decision = res.decision
                reason = res.reasoning
            except Exception:
                raw = await (router_prompt | eval_llm | StrOutputParser()).ainvoke({"question": question})
                raw_lower = raw.lower().strip()
                if "verify" in raw_lower:
                    decision = "verify_claim"
                elif "retrieve" in raw_lower or "paper" in raw_lower:
                    decision = "retrieve"
                else:
                    decision = "direct_answer"
                reason = "LLM parser fallback."
        except Exception:
            decision = "direct_answer"
            reason = "Fast default fallback."

    logs.append(f"[Router Decision] Categorized as `{decision}`: {reason}")
    return {
        "route": decision,
        "current_query": question,
        "reflection_logs": logs
    }
