import base64
import html
import math
import os
import shutil
import urllib.request
import wave
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

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


def generate_script_tool(prompt: str) -> Dict[str, Any]:
    file_name = f"script-{uuid4()}.txt"
    (ASSET_ROOT / file_name).write_text(prompt, encoding="utf-8")
    return _base_result("script-mock", {"prompt": prompt}, _asset_url(file_name))


def generate_image_tool(prompt: str, seed: Optional[int] = None) -> Dict[str, Any]:
    result_uri = _write_svg_asset("image", prompt)
    return _base_result("image-mock", {"prompt": prompt, "seed": seed}, result_uri)


def generate_video_tool(prompt: str, ref_uri: Optional[str] = None) -> Dict[str, Any]:
    result_uri = _write_video_asset(prompt)
    return _base_result("video-mock", {"prompt": prompt, "ref_uri": ref_uri}, result_uri)


def synthesize_tts_tool(text: str, voice: str = "default") -> Dict[str, Any]:
    result_uri = _write_wave_asset("tts", text)
    return _base_result("tts-mock", {"text": text, "voice": voice}, result_uri)


def generate_bgm_tool(style: str) -> Dict[str, Any]:
    result_uri = _write_wave_asset("bgm", style)
    return _base_result("bgm-mock", {"style": style}, result_uri)


def compose_timeline_tool(video_uris: list, audio_uris: list) -> Dict[str, Any]:
    if video_uris:
        return _base_result(
            "compose-mock",
            {"video_uris": video_uris, "audio_uris": audio_uris},
            video_uris[0],
        )
    result_uri = _write_video_asset("composited timeline")
    return _base_result("compose-mock", {"video_uris": video_uris, "audio_uris": audio_uris}, result_uri)


def quality_check_tool(asset_uri: str) -> Dict[str, Any]:
    return _base_result("qa-mock", {"asset_uri": asset_uri})
