from app.graph.routing import NODE_STORYBOARD_ARTIST
from app.graph.state import ManjuState
from app.services.asset_service import create_asset_meta
from app.tools.mcp_client import generate_image_tool, quality_check_tool


def storyboard_artist_agent(state: ManjuState) -> ManjuState:
    prompt = f"{state['user_prompt']} storyboard frame"
    image_result = generate_image_tool(prompt=prompt, seed=7)
    qa_result = quality_check_tool(image_result["result_uri"])
    frame = create_asset_meta(
        uri=image_result["result_uri"],
        model_name=image_result["metadata"]["model_name"],
        params=image_result["metadata"]["params"],
        seed=7,
        qa_score=None if qa_result["status"] != "ok" else 0.9,
    )
    state["storyboard_frames"] = [frame]
    state["approval_required"] = True
    state["approval_stage"] = "storyboard"
    state["current_node"] = NODE_STORYBOARD_ARTIST
    state["route_reason"] = NODE_STORYBOARD_ARTIST
    return state
