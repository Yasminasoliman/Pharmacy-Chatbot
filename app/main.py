import json
import logging
import uvicorn
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import cast

from state import PharmacyState
from graph import app as pharmacy_graph

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

api = FastAPI()


class ChatRequest(BaseModel):
    message: str
    history: list = []


@api.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """Debug version that logs all events"""
    
    initial_state = cast(
        PharmacyState,
        {
            "user_query": request.message,
            "messages": request.history,
            "intend": None,
            "llm_response": None,
            "tool_result": None,
            "first_answer": None,
            "final_safe_answer": "",
        },
    )
    
    logger.info(f"Starting stream with query: {request.message}")
    logger.info(f"Initial state: {initial_state}")

    async def event_generator():
        event_count = 0
        
        try:
            logger.info("Starting astream_events...")
            
            async for event in pharmacy_graph.astream_events(initial_state, version="v2"):
                event_count += 1
                kind = event["event"]
                event_name = event.get("name", "unknown")
                data = event.get("data")
                output = data.get("output")
                
                # Log EVERY event type received
                # logger.info(f"Event #{event_count}: kind={kind}, name={event_name}")
                # logger.info(f"Full event: {json.dumps(event, default=str)[:500]}")
                
                # Send ALL events to the client for debugging
                # yield f"data: {json.dumps({'type': 'debug', 'event': str(event)[:200]})}\n\n"
                if kind == "on_chat_model_start":
                    input = event["data"].get("input", "")
                    logger.info(f"input content prompt: {input}")
                if kind == "on_chat_model_end":
                    output = event["data"].get("output", "")
                    logger.info(f"input content prompt: {output}")
                elif kind == "on_chat_model_stream":
                    chunk = event["data"].get("chunk")
                    if chunk:
                        content = chunk.content if hasattr(chunk, "content") else ""
                        if content:
                            # logger.info(f"Token: {content}")
                            yield f"data: {json.dumps({'type': 'token', 'content': content})}\n\n"

                elif kind == "on_tool_start":
                    tool_name = event["name"]
                    tool_input = event["data"].get("input", "")
                    logger.info(f"Tool start: {tool_name}, input: {tool_input}")
                    yield f"data: {json.dumps({'type': 'tool_start', 'name': tool_name, 'input': str(tool_input)})}\n\n"

                elif kind == "on_tool_end":
                    tool_name = event["name"]
                    tool_output = event["data"].get("output", "")
                    logger.info(f"Tool end: {tool_name}, output: {tool_output}")
                    yield f"data: {json.dumps({'type': 'tool_end', 'name': tool_name, 'output': str(tool_output)})}\n\n"

            logger.info(f"Stream complete. Total events: {event_count}")
            
        except Exception as e:
            logger.error(f"Error in event generator: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


if __name__ == "__main__":
    uvicorn.run("main:api", host="127.0.0.1", port=8000, reload=True)