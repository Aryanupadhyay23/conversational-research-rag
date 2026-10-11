from backend.prompts.router import router_prompt
from backend.prompts.agent import agent_prompt
from backend.prompts.relevancy import relevancy_prompt
from backend.prompts.rewrite import query_rewrite_prompt
from backend.prompts.claim import claim_analysis_prompt
from backend.prompts.generation import answer_generation_prompt

__all__ = [
    "router_prompt",
    "agent_prompt",
    "relevancy_prompt",
    "query_rewrite_prompt",
    "claim_analysis_prompt",
    "answer_generation_prompt",
]
