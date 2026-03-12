from app.graph.routing import NODE_ANIMATION_ARTIST
from app.graph.state import ManjuState
from app.services.asset_service import create_asset_meta
from app.tools.mcp_client import generate_video_tool


def animation_artist_agent(state: ManjuState) -> ManjuState:
    ref_uri = None
    if state["storyboard_frames"]:
        ref_uri = state["storyboard_frames"][0]["uri"]
    result = generate_video_tool(prompt=state["user_prompt"], ref_uri=ref_uri, stage="animation")
    clip = create_asset_meta(
        uri=result["result_uri"],
        model_name=result["metadata"]["model_name"],
        params=result["metadata"]["params"],
        seed=None,
        qa_score=None,
    )
    state["video_clips"] = [clip]
    state["final_video"] = clip
    state["current_node"] = NODE_ANIMATION_ARTIST
    state["route_reason"] = NODE_ANIMATION_ARTIST
    return state
