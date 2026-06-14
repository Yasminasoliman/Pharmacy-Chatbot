from typing import TypedDict, List, Optional, Dict, Any
from langchain_core.messages import BaseMessage
from typing import Literal


class PharmacyState(TypedDict):
    # ── core conversation ──────────────────────────────────────────────
    messages: List[BaseMessage]
    user_query: str

    # ── intent routing ─────────────────────────────────────────────────
    intent: Literal["need_search", "answer_directly", "contact_support"]

    # ── search / tool pipeline ─────────────────────────────────────────
    llm_response: Optional[BaseMessage]
    tool_result: Optional[str]
    tool_messages: Optional[List[BaseMessage]]

    # ── answer pipeline ────────────────────────────────────────────────
    first_answer: Optional[str]
    final_safe_answer: str

    # ── OCR ────────────────────────────────────────────────────────────
    prescription_image: Optional[str]
    ocr_text: Optional[str]
    ocr_medicines: Optional[List[str]]

    # ── pharmacy availability ──────────────────────────────────────────
    found_medicines: Optional[List[str]]
    pharmacy_availability: Optional[Dict[str, Any]]

    # ── support ────────────────────────────────────────────────────────
    support_ticket: Optional[Dict[str, Any]]

    # ── evaluation ────────────────────────────────────────────────────
    eval_scores: Optional[Dict[str, Any]]
