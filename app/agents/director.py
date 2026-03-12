from app.graph.routing import NODE_DIRECTOR
from app.graph.state import ManjuState


def _interrupt_if_available() -> None:
    try:
        from langgraph.graph import interrupt
    except Exception as exc:
        raise RuntimeError("LangGraph interrupt unavailable") from exc
    interrupt("awaiting_human_review")


def director_agent(state: ManjuState) -> ManjuState:
    state["current_node"] = NODE_DIRECTOR
    state["route_reason"] = NODE_DIRECTOR
    state["iteration_count"] += 1
    max_iterations = state.get("max_iterations", 20)
    if state["iteration_count"] > max_iterations:
        state["errors"].append(
            {"node": NODE_DIRECTOR, "error": "max_iterations_exceeded"}
        )
        state["approval_required"] = False
        state["pending_feedback"] = []
        return state
    if state["approval_required"]:
        _interrupt_if_available()
    return state
