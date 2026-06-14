"""
FastAPI entrypoint – v2.2
Fixes:
  - Token events from eval_node and safety_node are suppressed from the stream
    so eval JSON never reaches the chat bubble
  - /chat/stream and /chat/prescription both use the same clean _stream_graph()
"""

import base64
import json
import logging
import uvicorn

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, cast
from pathlib import Path

from state import PharmacyState
from graph import graph as pharmacy_graph, ocr_graph
from evaluation.evaluator import eval_summary, load_recent_evals
from embeddings import load_embeding_model   # preload BGE
from config import LLM, VISION_LLM     
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

api = FastAPI(title="Pharmacy Chatbot API", version="2.2.0")
@api.on_event("startup")
async def startup_preload():
    """Preload heavy models so the first request doesn't time out."""
    import asyncio, logging
    logger = logging.getLogger(__name__)

    logger.info("⏳ Preloading BGE embedding model...")
    await asyncio.get_event_loop().run_in_executor(None, load_embeding_model)
    logger.info("✅ BGE model ready")

    logger.info("⏳ Warming up LLMs...")
    await asyncio.get_event_loop().run_in_executor(
        None, lambda: LLM.invoke("ping")
    )
    logger.info("✅ LLMs ready")

    logger.info("🚀 All models loaded — server ready")
api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

TICKETS_FILE = Path(__file__).parent.parent / "support_tickets" / "tickets.jsonl"

# Nodes whose LLM token stream must NOT reach the user chat bubble
_SUPPRESS_TOKEN_FROM_NODES = {"eval_node", "safety_node"}


class ChatRequest(BaseModel):
    message: str
    history: list = []


async def _stream_graph(initial_state: PharmacyState, use_ocr_graph: bool = False):
    selected_graph = ocr_graph if use_ocr_graph else pharmacy_graph

    async def event_generator():
        # track which node is currently active so we can suppress its tokens
        active_node: str = ""

        try:
            async for event in selected_graph.astream_events(
    initial_state,
    config={"recursion_limit": 10},  # 4 tools max = well within 10 steps
    version="v2"
):
                kind       = event["event"]
                event_name = event.get("name", "")
                data       = event.get("data", {})

                # track node entry/exit
                if kind == "on_chain_start":
                    active_node = event_name
                elif kind == "on_chain_end":
                    # ── node-specific output events ───────────────────── #
                    output = data.get("output", {})

                    if event_name == "ocr_node" and isinstance(output, dict):
                        meds = output.get("ocr_medicines", [])
                        if meds:
                            yield f"data: {json.dumps({'type': 'ocr_result', 'medicines': meds})}\n\n"

                    if event_name == "pharmacy_agent_node" and isinstance(output, dict):
                        avail = output.get("pharmacy_availability", {})
                        if avail:
                            yield f"data: {json.dumps({'type': 'availability', 'data': avail})}\n\n"

                    if event_name == "support_node" and isinstance(output, dict):
                        ticket = output.get("support_ticket")
                        if ticket:
                            yield f"data: {json.dumps({'type': 'support_ticket', 'ticket': ticket})}\n\n"

                    if event_name == "eval_node" and isinstance(output, dict):
                        scores = output.get("eval_scores")
                        if scores:
                            yield f"data: {json.dumps({'type': 'eval_scores', 'scores': scores})}\n\n"

                    if event_name == "safety_node" and isinstance(output, dict):
                        final_answer = output.get("final_safe_answer", "")
                        if final_answer:
                            yield f"data: {json.dumps({'type': 'final_answer', 'content': final_answer})}\n\n"

                    active_node = ""

                # ── streaming tokens – suppress from internal nodes ───── #
                elif kind == "on_chat_model_stream":
                    # suppress tokens from eval_node and safety_node
                    if active_node in _SUPPRESS_TOKEN_FROM_NODES:
                        continue
                    chunk = data.get("chunk")
                    if chunk:
                        content = chunk.content if hasattr(chunk, "content") else ""
                        if content:
                            yield f"data: {json.dumps({'type': 'token', 'content': content})}\n\n"

                elif kind == "on_tool_start":
                    yield f"data: {json.dumps({'type': 'tool_start', 'name': event_name})}\n\n"

                elif kind == "on_tool_end":
                    yield f"data: {json.dumps({'type': 'tool_end', 'name': event_name})}\n\n"

        except Exception as exc:
            logger.error("Stream error: %s", exc, exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


def _empty_state(message: str, history: list) -> PharmacyState:
    return cast(PharmacyState, {
        "user_query":            message,
        "messages":              history,
        "intent":                None,
        "llm_response":          None,
        "tool_result":           None,
        "tool_messages":         None,
        "first_answer":          None,
        "final_safe_answer":     "",
        "prescription_image":    None,
        "ocr_text":              None,
        "ocr_medicines":         None,
        "found_medicines":       None,
        "pharmacy_availability": None,
        "support_ticket":        None,
        "eval_scores":           None,
    })


@api.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    return await _stream_graph(_empty_state(request.message, request.history))


@api.post("/chat/prescription")
async def chat_prescription(
    file: UploadFile = File(...),
    message: str = Form(default=""),
    history: str = Form(default="[]"),
):
    raw_bytes = await file.read()
    b64 = base64.b64encode(raw_bytes).decode()
    try:
        history_list = json.loads(history)
    except Exception:
        history_list = []

    state = _empty_state(message or "Check my prescription", history_list)
    state["prescription_image"] = b64
    return await _stream_graph(state, use_ocr_graph=True)


@api.get("/support/tickets")
async def list_tickets(limit: int = 50):
    if not TICKETS_FILE.exists():
        return []
    lines = TICKETS_FILE.read_text(encoding="utf-8").splitlines()
    tickets = []
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            tickets.append(json.loads(line))
        except Exception:
            continue
        if len(tickets) >= limit:
            break
    return tickets


@api.get("/support/tickets/{ticket_id}")
async def get_ticket(ticket_id: str):
    if not TICKETS_FILE.exists():
        return JSONResponse({"error": "No tickets found"}, status_code=404)
    for line in TICKETS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            t = json.loads(line)
            if t.get("ticket_id") == ticket_id:
                return t
        except Exception:
            continue
    return JSONResponse({"error": "Ticket not found"}, status_code=404)


@api.get("/eval/summary")
async def get_eval_summary(n: int = 100):
    return eval_summary(n)


@api.get("/eval/recent")
async def get_recent_evals(n: int = 20):
    return load_recent_evals(n)


@api.get("/health")
async def health():
    return {"status": "ok", "version": "2.2.0"}


if __name__ == "__main__":
    uvicorn.run("main:api", host="127.0.0.1", port=8000, reload=True)
