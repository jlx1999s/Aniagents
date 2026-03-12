import json
import os
from pathlib import Path
from threading import Lock
from typing import Any, Dict

DEFAULT_REVIEW_GATEWAY_POLICY: Dict[str, Any] = {
    "version": 1,
    "updatedAt": "",
    "rules": {
        "maxRenderCostBeforeApproval": None,
        "manualApprovalNodes": [],
        "minQaScoreByNode": {},
        "forceApprovalOnErrors": True,
    },
}

_LOCK = Lock()
_STATE: Dict[str, Any] = {}


def _policy_path() -> Path:
    configured = os.getenv("REVIEW_GATEWAY_POLICY_PATH")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[1] / "static" / "config" / "review_gateway_policy.json"


def _deep_merge(defaults: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(defaults)
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_policy() -> Dict[str, Any]:
    path = _policy_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return _deep_merge(DEFAULT_REVIEW_GATEWAY_POLICY, data if isinstance(data, dict) else {})
    except Exception:
        fallback = json.loads(json.dumps(DEFAULT_REVIEW_GATEWAY_POLICY))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(fallback, ensure_ascii=False, indent=2), encoding="utf-8")
        return fallback


def save_policy(policy: Dict[str, Any]) -> None:
    path = _policy_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(policy, ensure_ascii=False, indent=2), encoding="utf-8")


def get_review_gateway_policy() -> Dict[str, Any]:
    with _LOCK:
        if not _STATE:
            _STATE.update(load_policy())
        return json.loads(json.dumps(_STATE))


def set_review_gateway_policy(payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized = _deep_merge(DEFAULT_REVIEW_GATEWAY_POLICY, payload or {})
    normalized["updatedAt"] = payload.get("updatedAt") or ""
    with _LOCK:
        _STATE.clear()
        _STATE.update(normalized)
        save_policy(normalized)
        return json.loads(json.dumps(_STATE))
