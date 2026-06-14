"""
eval_node – LangGraph node that runs after safety_node.

Calls evaluate_response() asynchronously and stores results in state.
The node never blocks the main response path: if evaluation fails,
the graph continues normally with eval_scores set to None.
"""

import asyncio
import logging
from state import PharmacyState
from evaluation.evaluator import evaluate_response

logger = logging.getLogger(__name__)


def eval_node(state: PharmacyState) -> dict:
    """
    LangGraph node.  Reads final_safe_answer + tool_result from state,
    runs the evaluator, and writes eval_scores back to state.
    """
    query    = state.get("user_query", "")
    response = state.get("final_safe_answer", "")
    tool_result = state.get("tool_result")
    intent   = state.get("intent", "unknown")

    if not response:
        return {"eval_scores": None}

    try:
        # evaluate_response is async; run it inside the sync node
        loop = asyncio.new_event_loop()
        scores = loop.run_until_complete(
            evaluate_response(
                query=query,
                response=response,
                tool_result=tool_result,
                intent=intent,
            )
        )
        loop.close()
        return {"eval_scores": scores.to_dict()}
    except Exception as exc:
        logger.warning("eval_node failed silently: %s", exc)
        return {"eval_scores": None}
