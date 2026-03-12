import base64
import html
import json
import math
import os
import shutil
import urllib.parse
import urllib.request
import wave
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.services.model_routes import resolve_model_name, resolve_params

ASSET_ROOT = Path(__file__).resolve().parents[1] / "static" / "generated"
ASSET_ROOT.mkdir(parents=True, exist_ok=True)
ASSET_BASE_URL = os.getenv("ASSET_BASE_URL", "http://localhost:8000/assets/generated")
VIDEO_TEMPLATE_PATH = ASSET_ROOT / "_sample_video.mp4"
GIF_FALLBACK = base64.b64decode("R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==")


def _asset_url(file_name: str) -> str:
    return f"{ASSET_BASE_URL}/{file_name}"


def _write_svg_asset(kind: str, prompt: str) -> str:
    file_name = f"{kind}-{uuid4()}.svg"
    title = html.escape(prompt[:96] if prompt else kind)
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1280 720'>"
        "<defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'>"
        "<stop offset='0%' stop-color='#1b1735'/><stop offset='100%' stop-color='#2f0d19'/>"
        "</linearGradient></defs>"
        "<rect width='1280' height='720' fill='url(#g)'/>"
        "<circle cx='1040' cy='160' r='180' fill='rgba(255,220,130,0.28)'/>"
        "<circle cx='240' cy='560' r='220' fill='rgba(115,190,255,0.2)'/>"
        f"<text x='68' y='120' fill='#f7e8bf' font-size='40' font-family='PingFang SC'>{kind}</text>"
        f"<text x='68' y='200' fill='#ffffff' font-size='30' font-family='PingFang SC'>{title}</text>"
        "</svg>"
    )
    (ASSET_ROOT / file_name).write_text(svg, encoding="utf-8")
    return _asset_url(file_name)


def _write_wave_asset(prefix: str, _: str) -> str:
    file_name = f"{prefix}-{uuid4()}.wav"
    file_path = ASSET_ROOT / file_name
    frame_rate = 22050
    seconds = 2
    amplitude = 7000
    frequency = 440
    sample_count = frame_rate * seconds
    with wave.open(str(file_path), "w") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(frame_rate)
        frames = bytearray()
        for i in range(sample_count):
            t = i / frame_rate
            value = int(
                amplitude
                * (0.5 if "bgm" in prefix else 1.0)
                * math.sin(2 * math.pi * frequency * t)
            )
            frames += value.to_bytes(2, byteorder="little", signed=True)
        wav_file.writeframes(frames)
    return _asset_url(file_name)


def _ensure_video_template() -> Optional[Path]:
    if VIDEO_TEMPLATE_PATH.exists():
        return VIDEO_TEMPLATE_PATH
    try:
        with urllib.request.urlopen("https://samplelib.com/lib/preview/mp4/sample-5s.mp4", timeout=8) as response:
            VIDEO_TEMPLATE_PATH.write_bytes(response.read())
        return VIDEO_TEMPLATE_PATH
    except Exception:
        return None


def _write_video_asset(_: str) -> str:
    file_name = f"video-{uuid4()}.mp4"
    file_path = ASSET_ROOT / file_name
    template = _ensure_video_template()
    if template is not None:
        shutil.copyfile(template, file_path)
        return _asset_url(file_name)
    gif_name = f"video-{uuid4()}.gif"
    (ASSET_ROOT / gif_name).write_bytes(GIF_FALLBACK)
    return _asset_url(gif_name)


def _base_result(
    model_name: str,
    params: Optional[Dict[str, Any]] = None,
    result_uri: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "status": "ok",
        "result_uri": result_uri or f"mcp://asset/{uuid4()}",
        "metadata": {
            "model_name": model_name,
            "params": params or {},
        },
        "cost": 0.0,
        "latency_ms": 0,
        "error": None,
    }


def _vectorengine_response(
    prompt: str,
    route: Dict[str, Any],
    system_instruction: str,
    timeout_seconds: int = 12,
) -> Dict[str, Any]:
    api_key = os.getenv("VECTORENGINE_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("缺少 VECTORENGINE_API_KEY，请在后端环境变量中配置")
    configured_base = str(route.get("baseUrl") or os.getenv("VECTORENGINE_BASE_URL") or "").strip()
    parsed = urllib.parse.urlparse(configured_base)
    if parsed.scheme and parsed.netloc:
        base_url = configured_base.rstrip("/")
    else:
        base_url = "https://api.vectorengine.ai"
    model = route.get("model") or "gemini-2.5-pro"
    endpoint = f"{base_url}/v1beta/models/{model}:generateContent"
    payload = {
        "systemInstruction": {"parts": [{"text": system_instruction}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7, "topP": 0.95},
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        text = response.read().decode("utf-8")
    return json.loads(text)


def _extract_vectorengine_text(response: Dict[str, Any]) -> str:
    candidates = response.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return ""
    content = candidates[0].get("content", {})
    parts = content.get("parts", []) if isinstance(content, dict) else []
    chunks = []
    for part in parts:
        if isinstance(part, dict) and isinstance(part.get("text"), str):
            chunks.append(part["text"])
    return "".join(chunks).strip()


def _safe_vectorengine_text(
    prompt: str,
    route: Dict[str, Any],
    system_instruction: str,
    timeout_seconds: int = 12,
) -> str:
    try:
        response = _vectorengine_response(prompt, route, system_instruction, timeout_seconds=timeout_seconds)
        text = _extract_vectorengine_text(response)
        return text or prompt
    except Exception:
        return prompt


def _route_info(stage: str, task: str, fallback_model: str) -> Dict[str, Any]:
    route_payload = resolve_params(stage, task)
    route = route_payload.get("route", {})
    model_name = resolve_model_name(stage, task, fallback_model)
    return {"route_payload": route_payload, "route": route, "model_name": model_name}


def generate_chat_reply_tool(user_message: str, context: str, stage: str = "scriptwriter") -> str:
    route_info = _route_info(stage, "script", "chat-mock")
    route = route_info["route"]
    fallback = f"{context}\n已收到你的需求：{user_message}\n我会按当前阶段继续执行。"
    if route.get("provider") == "vectorengine":
        prompt = (
            f"上下文：{context}\n"
            f"用户消息：{user_message}\n"
            "请基于上下文直接回复用户，语气自然、可执行，优先给出下一步动作，不要输出JSON。"
        )
        return _safe_vectorengine_text(
            prompt,
            route,
            "你是动画制作流程助手，需要结合当前项目状态给出简洁、明确、可执行的回复。",
            timeout_seconds=10,
        )
    return fallback


def generate_structured_role_reply_tool(
    *,
    role: str,
    user_message: str,
    target_label: str,
    target_actor: str,
    suggested_commands: List[str],
    context: str,
    stage: str = "scriptwriter",
) -> Dict[str, str]:
    route_info = _route_info(stage, "script", "chat-mock")
    route = route_info["route"]
    fallback = {
        "ack": f"收到，已确认需求：{user_message}。",
        "basis": f"当前状态允许推进到「{target_label}」。",
        "dispatch": f"我已将任务分发给{target_actor}。",
        "action": f"我将执行「{target_label}」并产出本阶段结果。",
        "next": " / ".join(suggested_commands[:3]),
    }
    if route.get("provider") != "vectorengine":
        return fallback
    prompt = (
        f"角色={role}\n"
        f"用户消息={user_message}\n"
        f"目标阶段={target_label}\n"
        f"目标执行者={target_actor}\n"
        f"建议指令={suggested_commands[:3]}\n"
        f"上下文={context}\n"
        "请输出JSON对象，字段必须包含：ack,basis,dispatch,action,next。"
    )
    text = _safe_vectorengine_text(
        prompt,
        route,
        "你是动画制作编排对话助手。输出严格JSON，中文简洁，禁止markdown。",
        timeout_seconds=12,
    )
    payload = _extract_json_payload(text)
    if not payload:
        return fallback
    ack = str(payload.get("ack") or "").strip() or fallback["ack"]
    basis = str(payload.get("basis") or "").strip() or fallback["basis"]
    dispatch = str(payload.get("dispatch") or "").strip() or fallback["dispatch"]
    action = str(payload.get("action") or "").strip() or fallback["action"]
    next_text = str(payload.get("next") or "").strip() or fallback["next"]
    return {
        "ack": ack,
        "basis": basis,
        "dispatch": dispatch,
        "action": action,
        "next": next_text,
    }


def generate_script_tool(prompt: str, stage: str = "scriptwriter") -> Dict[str, Any]:
    route_info = _route_info(stage, "script", "script-mock")
    route = route_info["route"]
    final_prompt = prompt
    if route.get("provider") == "vectorengine":
        final_prompt = _safe_vectorengine_text(prompt, route, "你是动画剧本策划助手，输出简明可执行的分镜脚本文本。")
    file_name = f"script-{uuid4()}.txt"
    (ASSET_ROOT / file_name).write_text(final_prompt, encoding="utf-8")
    params = {"prompt": prompt, "resolved_prompt": final_prompt}
    params.update(route_info["route_payload"])
    return _base_result(route_info["model_name"], params, _asset_url(file_name))


def generate_image_tool(prompt: str, seed: Optional[int] = None, stage: str = "character") -> Dict[str, Any]:
    route_info = _route_info(stage, "image", "image-mock")
    route = route_info["route"]
    final_prompt = prompt
    if route.get("provider") == "vectorengine":
        final_prompt = _safe_vectorengine_text(prompt, route, "你是视觉提示词助手，输出用于图像生成的高质量提示词。")
    result_uri = _write_svg_asset("image", final_prompt)
    params = {"prompt": prompt, "resolved_prompt": final_prompt, "seed": seed}
    params.update(route_info["route_payload"])
    return _base_result(route_info["model_name"], params, result_uri)


def generate_video_tool(prompt: str, ref_uri: Optional[str] = None, stage: str = "animation") -> Dict[str, Any]:
    route_info = _route_info(stage, "video", "video-mock")
    route = route_info["route"]
    final_prompt = prompt
    if route.get("provider") == "vectorengine":
        final_prompt = _safe_vectorengine_text(prompt, route, "你是动画分镜提示词助手，输出简洁的视频生成提示词。")
    result_uri = _write_video_asset(final_prompt)
    params = {"prompt": prompt, "resolved_prompt": final_prompt, "ref_uri": ref_uri}
    params.update(route_info["route_payload"])
    return _base_result(route_info["model_name"], params, result_uri)


def synthesize_tts_tool(text: str, voice: str = "default", stage: str = "sound") -> Dict[str, Any]:
    route_info = _route_info(stage, "tts", "tts-mock")
    route = route_info["route"]
    final_text = text
    if route.get("provider") == "vectorengine":
        final_text = _safe_vectorengine_text(text, route, "你是配音文本润色助手，保持原意并增强口语自然度。")
    result_uri = _write_wave_asset("tts", final_text)
    params = {"text": text, "resolved_text": final_text, "voice": voice}
    params.update(route_info["route_payload"])
    return _base_result(route_info["model_name"], params, result_uri)


def generate_bgm_tool(style: str, stage: str = "sound") -> Dict[str, Any]:
    route_info = _route_info(stage, "bgm", "bgm-mock")
    route = route_info["route"]
    final_style = style
    if route.get("provider") == "vectorengine":
        final_style = _safe_vectorengine_text(style, route, "你是配乐风格规划助手，输出简洁明确的音乐风格说明。")
    result_uri = _write_wave_asset("bgm", final_style)
    params = {"style": style, "resolved_style": final_style}
    params.update(route_info["route_payload"])
    return _base_result(route_info["model_name"], params, result_uri)


def compose_timeline_tool(video_uris: list, audio_uris: list, stage: str = "compositor") -> Dict[str, Any]:
    route_info = _route_info(stage, "compose", "compose-mock")
    if video_uris:
        params = {"video_uris": video_uris, "audio_uris": audio_uris}
        params.update(route_info["route_payload"])
        return _base_result(route_info["model_name"], params, video_uris[0])
    result_uri = _write_video_asset("composited timeline")
    params = {"video_uris": video_uris, "audio_uris": audio_uris}
    params.update(route_info["route_payload"])
    return _base_result(route_info["model_name"], params, result_uri)


def quality_check_tool(asset_uri: str, stage: str = "qa") -> Dict[str, Any]:
    route_info = _route_info(stage, "qa", "qa-mock")
    params = {"asset_uri": asset_uri}
    params.update(route_info["route_payload"])
    return _base_result(route_info["model_name"], params)


def _extract_json_payload(text: str) -> Dict[str, Any]:
    content = (text or "").strip()
    if not content:
        return {}
    if "```json" in content:
        start = content.find("```json")
        end = content.find("```", start + 7)
        if start >= 0 and end > start:
            content = content[start + 7 : end].strip()
    elif content.startswith("```") and content.endswith("```"):
        content = content[3:-3].strip()
    try:
        payload = json.loads(content)
    except Exception:
        start = content.find("{")
        end = content.rfind("}")
        if start < 0 or end <= start:
            return {}
        try:
            payload = json.loads(content[start : end + 1])
        except Exception:
            return {}
    return payload if isinstance(payload, dict) else {}


def generate_manager_decision_tool(
    *,
    available_nodes: List[str],
    preferred_node: str,
    status: str,
    awaiting_review: bool,
    current_index: int,
    history_tail: List[str],
) -> Dict[str, Any]:
    route_info = _route_info("manager", "decision", "manager-mock")
    route = route_info["route"]
    provider = route.get("provider") or "mock"
    model_name = route_info["model_name"]
    fallback = {
        "action": "execute",
        "next_node": preferred_node,
        "reason": "manager_fallback",
        "metadata": {"provider": provider, "model": model_name},
    }
    if provider != "vectorengine":
        return fallback
    prompt = (
        "你是流程调度Manager Agent。请根据输入状态做单步决策，只输出JSON对象，不要附加解释。\n"
        "输出格式：{\"action\":\"execute|await_review|complete|halt\","
        "\"next_node\":\"节点名或null\",\"reason\":\"简短原因\"}\n"
        f"available_nodes={available_nodes}\n"
        f"preferred_node={preferred_node}\n"
        f"status={status}\n"
        f"awaiting_review={awaiting_review}\n"
        f"current_index={current_index}\n"
        f"history_tail={history_tail}\n"
    )
    try:
        response = _vectorengine_response(
            prompt,
            route,
            "你是企业级流程调度决策器，必须稳定、保守，优先维持流程连续性。",
            timeout_seconds=15,
        )
        text = _extract_vectorengine_text(response)
    except Exception as exc:
        return {
            **fallback,
            "metadata": {
                **fallback["metadata"],
                "fallback_reason": "llm_request_failed",
                "error": str(exc)[:160],
            },
        }
    payload = _extract_json_payload(text)
    action = str(payload.get("action") or "").strip()
    next_node = payload.get("next_node")
    reason = str(payload.get("reason") or "").strip()
    if action not in {"execute", "await_review", "complete", "halt"}:
        return {
            **fallback,
            "metadata": {
                **fallback["metadata"],
                "fallback_reason": "invalid_llm_action",
            },
        }
    if action == "execute":
        if not isinstance(next_node, str) or next_node not in available_nodes:
            return {
                **fallback,
                "metadata": {
                    **fallback["metadata"],
                    "fallback_reason": "invalid_llm_node",
                },
            }
        return {
            "action": action,
            "next_node": next_node,
            "reason": reason or "llm_execute",
            "metadata": {"provider": provider, "model": model_name},
        }
    return {
        "action": action,
        "next_node": None,
        "reason": reason or "llm_non_execute",
        "metadata": {"provider": provider, "model": model_name},
    }
