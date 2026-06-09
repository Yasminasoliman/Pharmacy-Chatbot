from langgraph.graph import StateGraph, END
from state import PharmacyState
from nodes import intent_node, safety_node, tool_node, should_call_tools, answer_node, search_node, router_intent

graph = StateGraph(PharmacyState)

graph.add_node("intent", intent_node)
graph.add_node("search", search_node)
graph.add_node("tool", tool_node)
graph.add_node("answer", answer_node)
graph.add_node("safety", safety_node)


graph.set_entry_point("intent")


graph.add_conditional_edges(
    "intent",
    router_intent,
    {
        "search": "search",
        "answer": "safety",
    }
)

graph.add_conditional_edges(
    "search",
    should_call_tools,
    {
        "tool_call": "tool",
        "answer": "answer",
    }
)

graph.add_edge("tool", "answer")

graph.add_edge("safety", END)

app = graph.compile()

if __name__ == "__main__":
    with open("workflow_diagram.png", "wb") as f:
        f.write(app.get_graph(xray=True).draw_mermaid_png())
