from typing import TypedDict, List, Optional
from langchain_core.messages import BaseMessage
from typing import Literal

class PharmacyState(TypedDict):
    messages: List[BaseMessage]

    intent: Literal["need_search", "answer_directly"]

    llm_response: Optional[BaseMessage]

    tool_result: Optional[str]

    user_query: str

    first_answer: Optional[str]

    final_safe_answer: str