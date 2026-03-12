from app.graph.routing import NODE_CHARACTER_DESIGNER
from app.graph.state import ManjuState
from app.services.asset_service import create_asset_meta
from app.tools.mcp_client import generate_image_tool, quality_check_tool


def character_designer_agent(state: ManjuState) -> ManjuState:
    style = state.get("global_style") or {}
    style_feedback = style.get("user_feedback", "")
    if not style:
        style = {
            "style_name": "热血少年漫",
            "palette": "high contrast",
            "lens_language": "dynamic close-up",
        }
    prompt = (
        f"{state['user_prompt']} character design, style={style.get('style_name', 'anime')}, "
        f"palette={style.get('palette', 'vivid')}, feedback={style_feedback}"
    )
    image_result = generate_image_tool(prompt=prompt, seed=42, stage="character")
    qa_result = quality_check_tool(image_result["result_uri"], stage="qa")
    asset = create_asset_meta(
        uri=image_result["result_uri"],
        model_name=image_result["metadata"]["model_name"],
        params=image_result["metadata"]["params"],
        seed=42,
        qa_score=None if qa_result["status"] != "ok" else 0.9,
    )
    state["global_style"] = style
    state["character_assets"] = {"main_character": asset}
    state["approval_required"] = True
    state["approval_stage"] = "style"
    state["current_node"] = NODE_CHARACTER_DESIGNER
    state["route_reason"] = NODE_CHARACTER_DESIGNER
    return state
