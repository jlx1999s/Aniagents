import json
import os
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Optional

DEFAULT_ROUTES: Dict[str, Any] = {
    "version": 1,
    "updatedAt": "",
    "defaults": {"provider": "mock", "baseUrl": ""},
    "routes": {
        "scriptwriter": {"script": {"provider": "mock", "baseUrl": "", "model": "script-mock", "enabled": True, "params": {}}},
        "art-director": {"style": {"provider": "mock", "baseUrl": "", "model": "style-mock", "enabled": True, "params": {}}},
        "character": {"image": {"provider": "mock", "baseUrl": "", "model": "image-mock", "enabled": True, "params": {}}},
        "storyboard": {"image": {"provider": "mock", "baseUrl": "", "model": "image-mock", "enabled": True, "params": {}}},
        "animation": {"video": {"provider": "mock", "baseUrl": "", "model": "video-mock", "enabled": True, "params": {}}},
        "sound": {
            "tts": {"provider": "mock", "baseUrl": "", "model": "tts-mock", "enabled": True, "params": {}},
            "bgm": {"provider": "mock", "baseUrl": "", "model": "bgm-mock", "enabled": True, "params": {}},
        },
        "compositor": {"compose": {"provider": "mock", "baseUrl": "", "model": "compose-mock", "enabled": True, "params": {}}},
        "qa": {"qa": {"provider": "mock", "baseUrl": "", "model": "qa-mock", "enabled": True, "params": {}}},
    },
}

_LOCK = Lock()
_STATE: Dict[str, Any] = {}


def _routes_path() -> Path:
    configured = os.getenv("MODEL_ROUTES_PATH")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[1] / "static" / "config" / "model_routes.json"


def _deep_merge(defaults: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(defaults)
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def get_routes() -> Dict[str, Any]:
    with _LOCK:
        if not _STATE:
            loaded = load_routes()
            _STATE.update(loaded)
        return json.loads(json.dumps(_STATE))


def set_routes(payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized = _deep_merge(DEFAULT_ROUTES, payload or {})
    normalized["updatedAt"] = payload.get("updatedAt") or ""
    with _LOCK:
        _STATE.clear()
        _STATE.update(normalized)
        save_routes(normalized)
        return json.loads(json.dumps(_STATE))


def load_routes() -> Dict[str, Any]:
    path = _routes_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return _deep_merge(DEFAULT_ROUTES, data if isinstance(data, dict) else {})
    except Exception:
        fallback = json.loads(json.dumps(DEFAULT_ROUTES))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(fallback, ensure_ascii=False, indent=2), encoding="utf-8")
        return fallback


def save_routes(routes: Dict[str, Any]) -> None:
    path = _routes_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(routes, ensure_ascii=False, indent=2), encoding="utf-8")


def resolve_model_name(stage: str, task: str, fallback: str) -> str:
    routes = get_routes()
    stage_routes = routes.get("routes", {}).get(stage, {})
    entry = stage_routes.get(task) or {}
    if entry.get("enabled") is False:
        return fallback
    provider = entry.get("provider") or routes.get("defaults", {}).get("provider") or "mock"
    model = entry.get("model") or fallback
    return f"{provider}:{model}"


def resolve_params(stage: str, task: str) -> Dict[str, Any]:
    routes = get_routes()
    stage_routes = routes.get("routes", {}).get(stage, {})
    entry = stage_routes.get(task) or {}
    params = entry.get("params") if isinstance(entry.get("params"), dict) else {}
    base_url = entry.get("baseUrl") or routes.get("defaults", {}).get("baseUrl") or ""
    provider = entry.get("provider") or routes.get("defaults", {}).get("provider") or "mock"
    return {
        "route": {
            "stage": stage,
            "task": task,
            "provider": provider,
            "baseUrl": base_url,
            "model": entry.get("model") or "",
            "enabled": entry.get("enabled", True),
            "params": params,
        }
    }

