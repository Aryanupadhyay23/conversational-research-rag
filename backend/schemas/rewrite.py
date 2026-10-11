from pydantic import BaseModel, Field

class QueryRewrite(BaseModel):
    """Rewritten search query expanded with technical terminology."""
    rewritten_query: str = Field(description="Optimized query with academic keywords and synonyms.")
    rationale: str = Field(description="Reasoning for query adjustment.")
