from typing import Literal
from pydantic import BaseModel, Field

class DocumentRelevanceGrade(BaseModel):
    """Document relevance evaluation score."""
    binary_score: Literal["yes", "no"] = Field(
        description="'yes' if document contains relevant concepts to answer query, 'no' otherwise."
    )
    reasoning: str = Field(description="Explanation of grading decision.")
