from app.graph.routing import NODE_CHARACTER_DESIGNER
from app.graph.state import ManjuState
from app.services.asset_service import create_asset_meta
from app.tools.mcp_client import generate_image_tool, quality_check_tool


def character_designer_agent(state: ManjuState) -> ManjuState:
    prompt = f"{state['user_prompt']} character design"
    image_result = generate_image_tool(prompt=prompt, seed=42)
    qa_result = quality_check_tool(image_result["result_uri"])
    asset = create_asset_meta(
        uri=image_result["result_uri"],
        model_name=image_result["metadata"]["model_name"],
        params=image_result["metadata"]["params"],
        seed=42,
        qa_score=None if qa_result["status"] != "ok" else 0.9,
    )
    state["character_assets"] = {"main_character": asset}
    state["approval_required"] = True
    state["approval_stage"] = "character"
    state["current_node"] = NODE_CHARACTER_DESIGNER
    state["route_reason"] = NODE_CHARACTER_DESIGNER
    return state
