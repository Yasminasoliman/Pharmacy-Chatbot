"""
LangGraph pipeline – with support contact routing.

Flow:

  [text] ──────────────────────────────────────────────────┐
                                                            ▼
  [image] ──► ocr_node ──► intent_node ──► router_intent
                                                 │
               ┌── answer_directly ◄─────────────┤
               │                                 │
               ├── contact_support ──► support_node
               │                                 │
               └── need_search ──► search_node ──► tool_node (conditional)
                                        │
                                   answer_node
                                        │
                               pharmacy_agent_node
                                        │
                                   safety_node  ◄─── (answer_directly, contact_support also flow here)
                                        │
                                    eval_node
                                        │
                                       END
"""

from langgraph.graph import StateGraph, END

from state import PharmacyState
from nodes import (
    intent_node,
    router_intent,
    search_node,
    tool_node,
    should_call_tools,
    answer_node,
    safety_node,
)
from nodes.ocr_node import ocr_node
from nodes.pharmacy_agent_node import pharmacy_agent_node
from nodes.support_node import support_node
from evaluation.eval_node import eval_node


def _build(entry: str):
    builder = StateGraph(PharmacyState)

    # ── nodes ────────────────────────────────────────────────────────── #
    builder.add_node("ocr_node",            ocr_node)
    builder.add_node("intent_node",         intent_node)
    builder.add_node("search_node",         search_node)
    builder.add_node("tool_node",           tool_node)
    builder.add_node("answer_node",         answer_node)
    builder.add_node("pharmacy_agent_node", pharmacy_agent_node)
    builder.add_node("support_node",        support_node)
    builder.add_node("safety_node",         safety_node)
    builder.add_node("eval_node",           eval_node)

    builder.set_entry_point(entry)

    # ── OCR → intent ─────────────────────────────────────────────────── #
    if entry == "ocr_node":
        builder.add_edge("ocr_node", "intent_node")

    # ── intent routing ────────────────────────────────────────────────── #
    builder.add_conditional_edges(
        "intent_node",
        router_intent,
        {
            "need_search":     "search_node",
            "answer_directly": "safety_node",
            "contact_support": "support_node",
        },
    )

    # ── search / tool loop ────────────────────────────────────────────── #
    builder.add_conditional_edges(
        "search_node",
        should_call_tools,
        {
            "tools":       "tool_node",
            "answer_node": "answer_node",
        },
    )
    builder.add_edge("tool_node",            "answer_node")

    # ── answer → availability → safety ────────────────────────────────── #
    builder.add_edge("answer_node",          "pharmacy_agent_node")
    builder.add_edge("pharmacy_agent_node",  "safety_node")

    # ── support → safety (safety still checks the support response) ───── #
    builder.add_edge("support_node",         "safety_node")

    # ── safety → eval → END ───────────────────────────────────────────── #
    builder.add_edge("safety_node",          "eval_node")
    builder.add_edge("eval_node",            END)

    return builder.compile(checkpointer=None)


graph     = _build("intent_node")   # text queries
ocr_graph = _build("ocr_node")      # prescription image uploads
