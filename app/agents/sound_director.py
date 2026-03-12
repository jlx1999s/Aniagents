from app.graph.routing import NODE_SOUND_DIRECTOR
from app.graph.state import ManjuState
from app.services.asset_service import create_asset_meta
from app.tools.mcp_client import generate_bgm_tool, synthesize_tts_tool


def sound_director_agent(state: ManjuState) -> ManjuState:
    tts_result = synthesize_tts_tool(text="placeholder narration")
    bgm_result = generate_bgm_tool(style="cinematic")
    tts_asset = create_asset_meta(
        uri=tts_result["result_uri"],
        model_name=tts_result["metadata"]["model_name"],
        params=tts_result["metadata"]["params"],
    )
    bgm_asset = create_asset_meta(
        uri=bgm_result["result_uri"],
        model_name=bgm_result["metadata"]["model_name"],
        params=bgm_result["metadata"]["params"],
    )
    state["audio_tracks"] = {"tts": tts_asset, "bgm": bgm_asset}
    state["current_node"] = NODE_SOUND_DIRECTOR
    state["route_reason"] = NODE_SOUND_DIRECTOR
    return state
