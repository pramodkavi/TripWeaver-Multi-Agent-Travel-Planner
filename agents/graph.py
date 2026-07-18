"""LangGraph StateGraph wiring intent-based routing between agent nodes.

    START -> router --(intent)--> {hotel | flight | general} -> generate_response -> END

Routing is the graph's responsibility: the router interprets intent and the
conditional edge dispatches to the correct agent. The traveller never names an
agent.
"""

from langgraph.graph import END, START, StateGraph

from .entity import GraphState
from .nodes import (
    flight_node,
    general_qa_node,
    generate_response,
    hotel_node,
    route_after_router,
    router,
)


def build_graph() -> StateGraph:
    builder = StateGraph(GraphState)

    builder.add_node("router", router)
    builder.add_node("hotel", hotel_node)
    builder.add_node("flight", flight_node)
    builder.add_node("general", general_qa_node)
    builder.add_node("generate_response", generate_response)

    builder.add_edge(START, "router")
    builder.add_conditional_edges(
        "router",
        route_after_router,
        {
            "hotel": "hotel",
            "flight": "flight",
            "general": "general",
        },
    )
    builder.add_edge("hotel", "generate_response")
    builder.add_edge("flight", "generate_response")
    builder.add_edge("general", "generate_response")
    builder.add_edge("generate_response", END)

    return builder


graph = build_graph().compile()
