from app.graph.routing import NODE_SCRIPTWRITER
from app.graph.state import ManjuState
from app.tools.mcp_client import generate_script_tool


def scriptwriter_agent(state: ManjuState) -> ManjuState:
    result = generate_script_tool(state["user_prompt"])
    state["script_data"] = {
        "scenes": [],
        "raw": result,
    }
    state["current_node"] = NODE_SCRIPTWRITER
    state["route_reason"] = NODE_SCRIPTWRITER
    return state
