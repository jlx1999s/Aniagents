import re
from typing import Any, Dict, List

from app.graph.routing import NODE_SCRIPTWRITER
from app.graph.state import ManjuState
from app.tools.mcp_client import generate_script_tool


def _split_storyboard_lines(text: str) -> List[str]:
    lines = [item.strip() for item in text.splitlines() if item.strip()]
    cleaned: List[str] = []
    for line in lines:
        normalized = re.sub(r"^[\-\*\d\.\)\s、镜头场景第]+", "", line).strip()
        if normalized:
            cleaned.append(normalized)
    if len(cleaned) >= 2:
        return cleaned
    parts = [item.strip() for item in re.split(r"[。！？；;]", text) if item.strip()]
    return parts


def _fallback_scenes(prompt: str) -> List[Dict[str, Any]]:
    seed = prompt.strip() or "主角踏上未知旅程"
    core = seed[:36]
    return [
        {"index": 1, "summary": f"开场设定：{core}", "visual": "交代时间地点与人物关系", "duration": "4s"},
        {"index": 2, "summary": f"冲突出现：{core}", "visual": "主要矛盾爆发，动作节奏拉高", "duration": "5s"},
        {"index": 3, "summary": f"局势升级：{core}", "visual": "角色做出关键选择", "duration": "5s"},
        {"index": 4, "summary": f"悬念收束：{core}", "visual": "留下下一段剧情钩子", "duration": "4s"},
    ]


def _build_scenes(result: Dict[str, Any], user_prompt: str) -> List[Dict[str, Any]]:
    resolved_prompt = ""
    metadata = result.get("metadata")
    if isinstance(metadata, dict):
        params = metadata.get("params")
        if isinstance(params, dict):
            resolved_prompt = str(params.get("resolved_prompt") or "")
    source_text = resolved_prompt.strip() or user_prompt.strip()
    pieces = _split_storyboard_lines(source_text)
    scenes: List[Dict[str, Any]] = []
    for index, piece in enumerate(pieces[:10], start=1):
        scenes.append(
            {
                "index": index,
                "summary": piece[:120],
                "visual": piece[:120],
                "duration": "3s",
                "source": user_prompt[:120],
            }
        )
    if len(scenes) >= 2:
        return scenes
    return _fallback_scenes(user_prompt)


def scriptwriter_agent(state: ManjuState) -> ManjuState:
    result = generate_script_tool(
        f"请基于以下小说文本做分镜拆解并输出镜头段落：{state['user_prompt']}",
        stage="scriptwriter",
    )
    state["script_data"] = {
        "scenes": _build_scenes(result, state["user_prompt"]),
        "raw": result,
    }
    state["current_node"] = NODE_SCRIPTWRITER
    state["route_reason"] = NODE_SCRIPTWRITER
    return state
