from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from state import PharmacyState
from tools import medicine_lookup, disease_lookup, generic_name_lookup, drug_information
from config import LLM
from prompts import entry_agent_system_prompt

tools = [medicine_lookup, disease_lookup, generic_name_lookup, drug_information]
tools_by_name = {tool.name: tool for tool in tools}

llm_with_tools = LLM.bind_tools(tools, tool_choice="auto")

def search_node(state: PharmacyState):
    
    # Invoke LLM
    response = llm_with_tools.invoke([
        SystemMessage(content=entry_agent_system_prompt),
        HumanMessage(content=state["user_query"])
    ])

    return {"llm_response": response}

def tool_node(state: PharmacyState):
    """Performs the tool call"""
    messages = state.get("messages", [])
    result = []
    
    for tool_call in state["llm_response"].tool_calls:  # type: ignore
        tool = tools_by_name[tool_call["name"]]
        observation = tool.invoke(tool_call["args"])
        tool_message = ToolMessage(content=observation, tool_call_id=tool_call["id"])
        result.append(tool_message)
    
    # Add tool results to messages
    messages.extend(result)
    
    return {"messages": messages, "tool_result": result}

def should_call_tools(state):

    response = state["llm_response"]

    if response.tool_calls:
        return "tool_call"

    return "answer"