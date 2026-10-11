from typing import Annotated, List, Sequence, Optional, Dict, Any, Literal
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage
from langchain_core.documents import Document
from langgraph.graph.message import add_messages

class GraphState(TypedDict):
    """LangGraph state schema for the agent workflow."""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    question: str
    current_query: str
    route: Literal["retrieve", "verify_claim", "direct_answer"]
    documents: List[Document]
    retrieval_attempts: int
    rewrite_count: int
    claim_analysis: Optional[Dict[str, Any]]
    is_relevant: bool
    generation: str
    formatted_response: Optional[Dict[str, Any]]
    metadata: Dict[str, Any]
    reflection_logs: List[str]
