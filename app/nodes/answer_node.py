from langchain_core.messages import SystemMessage, HumanMessage
from state import PharmacyState
from config import LLM


def answer_node(state: PharmacyState):

    if state["tool_result"] is None:
        
        return {
            **state,
            "first_answer": state["llm_response"]
        }

    final_response = LLM.invoke([
        SystemMessage(
            content="""
You are a pharmacy assistant.

Use the tool result below to answer the user.

Do not mention tools.

Provide a concise answer.
"""
        ),
        HumanMessage(
            content=f"""
User Question:
{state['user_query']}

Tool Result:
{state['tool_result']}
"""
        )
    ])

    return {
        **state,
        "first_answer": final_response.content
    }