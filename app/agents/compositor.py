from app.graph.routing import NODE_COMPOSITOR
from app.graph.state import ManjuState
from app.services.asset_service import create_asset_meta
from app.tools.mcp_client import compose_timeline_tool


def compositor_agent(state: ManjuState) -> ManjuState:
    video_uris = [clip["uri"] for clip in state["video_clips"]]
    audio_uris = [asset["uri"] for asset in state["audio_tracks"].values()]
    result = compose_timeline_tool(video_uris=video_uris, audio_uris=audio_uris, stage="compositor")
    final_asset = create_asset_meta(
        uri=result["result_uri"],
        model_name=result["metadata"]["model_name"],
        params=result["metadata"]["params"],
    )
    state["final_video"] = final_asset
    state["current_node"] = NODE_COMPOSITOR
    state["route_reason"] = NODE_COMPOSITOR
    return state
