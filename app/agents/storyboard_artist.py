from app.graph.routing import NODE_STORYBOARD_ARTIST
from app.graph.state import ManjuState
from app.services.asset_service import create_asset_meta
from app.tools.mcp_client import generate_image_tool, quality_check_tool


def storyboard_artist_agent(state: ManjuState) -> ManjuState:
    style_name = state.get("global_style", {}).get("style_name", "anime")
    prompt = f"{state['user_prompt']} storyboard frame, visual style={style_name}"
    image_result = generate_image_tool(prompt=prompt, seed=7, stage="storyboard")
    qa_result = quality_check_tool(image_result["result_uri"], stage="qa")
    frame = create_asset_meta(
        uri=image_result["result_uri"],
        model_name=image_result["metadata"]["model_name"],
        params=image_result["metadata"]["params"],
        seed=7,
        qa_score=None if qa_result["status"] != "ok" else 0.9,
    )
    state["storyboard_frames"] = [frame]
    state["approval_required"] = False
    state["approval_stage"] = None
    state["current_node"] = NODE_STORYBOARD_ARTIST
    state["route_reason"] = NODE_STORYBOARD_ARTIST
    return state
