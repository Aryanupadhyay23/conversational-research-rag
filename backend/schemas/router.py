from typing import Literal
from pydantic import BaseModel, Field

class RouterDecision(BaseModel):
    """Router decision determining query execution path."""
    decision: Literal["retrieve", "verify_claim", "direct_answer"] = Field(
        description="Path: 'retrieve' for paper search, 'verify_claim' for fact checking, 'direct_answer' for general greetings/chit-chat."
    )
    reasoning: str = Field(description="Rationale for the classification.")
