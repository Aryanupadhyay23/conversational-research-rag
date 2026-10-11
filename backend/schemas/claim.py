from typing import Literal, List
from pydantic import BaseModel, Field

class SupersedingPaper(BaseModel):
    """Details of a scientific paper updating or counter-challenging a claim."""
    title: str = Field(description="Title of paper.")
    arxiv_id_or_url: str = Field(default="", description="Link or ArXiv ID.")
    finding: str = Field(description="Key finding regarding the claim.")

class ClaimAnalysisResult(BaseModel):
    """Structured fact-checking analysis of a claim."""
    claim: str = Field(description="Extracted core claim.")
    verdict: Literal["SUPPORTED", "REFUTED", "PARTIALLY_SUPPORTED", "UNVERIFIED"] = Field(
        description="Verdict based on literature."
    )
    confidence: float = Field(default=0.85, description="Confidence score between 0.0 and 1.0.")
    reasoning: str = Field(description="Analysis of evidence.")
    superseding_papers: List[SupersedingPaper] = Field(default_factory=list, description="Relevant counter/updating papers.")
