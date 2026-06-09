from langchain_core.messages import HumanMessage, SystemMessage
from state import PharmacyState
from prompts import get_safety_prompt
from config import LLM


def safety_node(state: PharmacyState):

    if state['intent'] == "answer_directly":
        response = LLM.invoke([
        SystemMessage(content="Check whether the answer is safe to provide"),

        HumanMessage(content=state["user_query"])
        ])
    else:
        prompt = get_safety_prompt(state['first_answer'])

        response = LLM.invoke([
            SystemMessage(content=prompt),
            HumanMessage(content=state["user_query"])
        ])

    return {
        "final_safe_answer": response.content
    }