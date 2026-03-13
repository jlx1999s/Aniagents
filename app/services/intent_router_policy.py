import json
import os
from pathlib import Path
from threading import Lock
from typing import Any, Dict

DEFAULT_INTENT_ROUTER_POLICY: Dict[str, Any] = {
    "version": 1,
    "updatedAt": "",
    "rules": {
        "mode": "hybrid",
        "llmMinConfidence": 0.75,
        "ruleHighConfidenceBypass": 0.91,
        "forceRuleWhenAwaitingReview": True,
    },
}

_LOCK = Lock()
_STATE: Dict[str, Any] = {}


def _policy_path() -> Path:
    configured = os.getenv("INTENT_ROUTER_POLICY_PATH")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[1] / "static" / "config" / "intent_router_policy.json"


def _deep_merge(defaults: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(defaults)
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _normalize_policy(payload: Dict[str, Any]) -> Dict[str, Any]:
    merged = _deep_merge(DEFAULT_INTENT_ROUTER_POLICY, payload or {})
    rules = merged.get("rules", {})
    mode = str(rules.get("mode", "hybrid")).strip()
    if mode not in {"rule_only", "hybrid", "model_first"}:
        mode = "hybrid"
    try:
        llm_min_confidence = float(rules.get("llmMinConfidence", 0.75))
    except Exception:
        llm_min_confidence = 0.75
    llm_min_confidence = max(0.0, min(llm_min_confidence, 1.0))
    try:
        rule_high_confidence_bypass = float(rules.get("ruleHighConfidenceBypass", 0.91))
    except Exception:
        rule_high_confidence_bypass = 0.91
    rule_high_confidence_bypass = max(0.0, min(rule_high_confidence_bypass, 1.0))
    merged["rules"] = {
        "mode": mode,
        "llmMinConfidence": llm_min_confidence,
        "ruleHighConfidenceBypass": rule_high_confidence_bypass,
        "forceRuleWhenAwaitingReview": bool(rules.get("forceRuleWhenAwaitingReview", True)),
    }
    merged["updatedAt"] = payload.get("updatedAt") if isinstance(payload, dict) else ""
    if not isinstance(merged["updatedAt"], str):
        merged["updatedAt"] = ""
    return merged


def normalize_intent_router_policy(payload: Dict[str, Any]) -> Dict[str, Any]:
    return _normalize_policy(payload if isinstance(payload, dict) else {})


def load_policy() -> Dict[str, Any]:
    path = _policy_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return normalize_intent_router_policy(data if isinstance(data, dict) else {})
    except Exception:
        fallback = normalize_intent_router_policy(DEFAULT_INTENT_ROUTER_POLICY)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(fallback, ensure_ascii=False, indent=2), encoding="utf-8")
        return fallback


def save_policy(policy: Dict[str, Any]) -> None:
    path = _policy_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(policy, ensure_ascii=False, indent=2), encoding="utf-8")


def get_intent_router_policy() -> Dict[str, Any]:
    with _LOCK:
        if not _STATE:
            _STATE.update(load_policy())
        return json.loads(json.dumps(_STATE))


def set_intent_router_policy(payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized = normalize_intent_router_policy(payload if isinstance(payload, dict) else {})
    with _LOCK:
        _STATE.clear()
        _STATE.update(normalized)
        save_policy(normalized)
        return json.loads(json.dumps(_STATE))
