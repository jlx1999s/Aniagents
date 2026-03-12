from app.graph.routing import NODE_ART_DIRECTOR
from app.graph.state import ManjuState


def art_director_agent(state: ManjuState) -> ManjuState:
    state["global_style"] = {
        "palette": "morandi",
        "lens_language": "cinematic",
        "negative_prompt": "low quality, blurry, extra limbs",
    }
    state["current_node"] = NODE_ART_DIRECTOR
    state["route_reason"] = NODE_ART_DIRECTOR
    return state
