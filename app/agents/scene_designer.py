from app.graph.routing import NODE_SCENE_DESIGNER
from app.graph.state import ManjuState
from app.services.asset_service import create_asset_meta
from app.tools.mcp_client import generate_image_tool, quality_check_tool


def scene_designer_agent(state: ManjuState) -> ManjuState:
    style = state.get("global_style") or {}
    style_name = style.get("style_name", "anime")
    lens_language = style.get("lens_language", "cinematic")
    prompt = (
        f"{state['user_prompt']} scene concept art, style={style_name}, "
        f"lens_language={lens_language}, cinematic environment design"
    )
    image_result = generate_image_tool(prompt=prompt, seed=19, stage="scene")
    qa_result = quality_check_tool(image_result["result_uri"], stage="qa")
    asset = create_asset_meta(
        uri=image_result["result_uri"],
        model_name=image_result["metadata"]["model_name"],
        params=image_result["metadata"]["params"],
        seed=19,
        qa_score=None if qa_result["status"] != "ok" else 0.9,
    )
    scene_assets = dict(state.get("scene_assets") or {})
    scene_assets[f"scene_{len(scene_assets) + 1}"] = asset
    state["scene_assets"] = scene_assets
    state["current_node"] = NODE_SCENE_DESIGNER
    state["route_reason"] = NODE_SCENE_DESIGNER
    return state
