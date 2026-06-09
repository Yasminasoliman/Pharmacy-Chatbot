from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from state import PharmacyState
from tools import medicine_lookup, disease_lookup, generic_name_lookup, drug_information
from config import LLM
from prompts import intent_agent_prompt
from pydantic import BaseModel
from typing import Literal

class IntendOutput(BaseModel):
    intent: Literal["need_search", "answer_directly"]


llm_with_structure_output = LLM.with_structured_output(IntendOutput)

def intent_node(state: PharmacyState):
    messages = state.get("messages", [])
    
    # Add user query as HumanMessage
    user_message = HumanMessage(content=state["user_query"])
    messages.append(user_message)
    
    # Invoke LLM
    response = llm_with_structure_output.invoke([
        SystemMessage(content=intent_agent_prompt),
        HumanMessage(content=state["user_query"])
    ])
    intent = response.intent # type: ignore
    
    if intent == "answer_directly":
        state["first_answer"] = state["user_query"]
    return response


def router_intent(state):

    response = state["intent"]

    if response == "need_search":
        return "search"

    return "answer"