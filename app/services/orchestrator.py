from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Dict, List, Optional

from app.agents.animation_artist import animation_artist_agent
from app.agents.art_director import art_director_agent
from app.agents.character_designer import character_designer_agent
from app.agents.compositor import compositor_agent
from app.agents.scriptwriter import scriptwriter_agent
from app.agents.sound_director import sound_director_agent
from app.agents.storyboard_artist import storyboard_artist_agent
from app.graph.routing import (
    NODE_ANIMATION_ARTIST,
    NODE_ART_DIRECTOR,
    NODE_CHARACTER_DESIGNER,
    NODE_COMPOSITOR,
    NODE_SCRIPTWRITER,
    NODE_SOUND_DIRECTOR,
    NODE_STORYBOARD_ARTIST,
)
from app.graph.state import ManjuState, create_initial_state

AGENT_SEQUENCE = [
    (NODE_SCRIPTWRITER, scriptwriter_agent, "Scriptwriting"),
    (NODE_ART_DIRECTOR, art_director_agent, "Style Definition"),
    (NODE_CHARACTER_DESIGNER, character_designer_agent, "Character Review"),
    (NODE_STORYBOARD_ARTIST, storyboard_artist_agent, "Storyboard Review"),
    (NODE_ANIMATION_ARTIST, animation_artist_agent, "Animation Render"),
    (NODE_SOUND_DIRECTOR, sound_director_agent, "Audio Align"),
    (NODE_COMPOSITOR, compositor_agent, "Compositor"),
]

NODE_COST = {
    NODE_SCRIPTWRITER: 0.42,
    NODE_ART_DIRECTOR: 0.65,
    NODE_CHARACTER_DESIGNER: 2.8,
    NODE_STORYBOARD_ARTIST: 2.2,
    NODE_ANIMATION_ARTIST: 3.6,
    NODE_SOUND_DIRECTOR: 1.4,
    NODE_COMPOSITOR: 1.8,
}

NODE_ETA = {
    NODE_SCRIPTWRITER: "00:05:00",
    NODE_ART_DIRECTOR: "00:04:30",
    NODE_CHARACTER_DESIGNER: "00:04:10",
    NODE_STORYBOARD_ARTIST: "00:03:50",
    NODE_ANIMATION_ARTIST: "00:03:10",
    NODE_SOUND_DIRECTOR: "00:02:20",
    NODE_COMPOSITOR: "00:01:00",
}

STAGE_TO_INDEX = {stage[0]: idx for idx, stage in enumerate(AGENT_SEQUENCE)}


def _build_asset_preview(asset: Dict[str, object], kind: str) -> Dict[str, object]:
    source_uri = str(asset.get("uri") or "")
    asset_id = str(asset.get("asset_id") or "preview")
    if source_uri.startswith("http://") or source_uri.startswith("https://"):
        preview_uri = source_uri
    elif kind == "video":
        preview_uri = "https://samplelib.com/lib/preview/mp4/sample-5s.mp4"
    else:
        preview_uri = f"https://picsum.photos/seed/{asset_id}/960/540"
    return {
        "assetId": asset_id,
        "kind": kind,
        "sourceUri": source_uri,
        "previewUri": preview_uri,
    }


@dataclass
class ProjectRuntime:
    state: ManjuState
    current_index: int = 0
    status: str = "running"
    awaiting_review: bool = False
    step_count: int = 0
    last_advanced_at: float = 0.0
    history: List[str] = field(default_factory=list)
    review_logs: List[Dict[str, str]] = field(default_factory=list)


class ProjectOrchestrator:
    def __init__(self) -> None:
        self._store: Dict[str, ProjectRuntime] = {}
        self._lock = Lock()

    def create_project(self, user_prompt: str) -> str:
        with self._lock:
            state = create_initial_state(user_prompt=user_prompt)
            runtime = ProjectRuntime(state=state)
            runtime.history.append("project_created")
            self._store[state["project_id"]] = runtime
            return state["project_id"]

    def get_runtime(self, project_id: str) -> Optional[ProjectRuntime]:
        with self._lock:
            return self._store.get(project_id)

    def list_project_ids(self) -> List[str]:
        with self._lock:
            return list(self._store.keys())

    def _mark_approval_resolved(self, runtime: ProjectRuntime) -> None:
        runtime.state["approval_required"] = False
        runtime.state["approval_stage"] = None
        runtime.state["pending_feedback"] = []
        runtime.awaiting_review = False

    def submit_review(
        self,
        project_id: str,
        action: str,
        target_node: Optional[str],
        message: Optional[str],
        stage: Optional[str] = None,
        issue_type: Optional[str] = None,
        priority: str = "medium",
        operator_id: str = "anonymous",
    ) -> ProjectRuntime:
        with self._lock:
            runtime = self._store.get(project_id)
            if runtime is None:
                raise KeyError(project_id)
            if action == "approve":
                resolved_stage = stage or runtime.state.get("approval_stage") or ""
                self._mark_approval_resolved(runtime)
                runtime.current_index = min(runtime.current_index + 1, len(AGENT_SEQUENCE))
                runtime.status = "running"
                runtime.review_logs.append(
                    {
                        "action": "approve",
                        "operator_id": operator_id,
                        "stage": resolved_stage,
                        "issue_type": issue_type or "manual_review",
                        "priority": priority,
                        "message": message or "",
                    }
                )
                runtime.history.append("review_approved")
            elif action == "revise":
                if not target_node or target_node not in STAGE_TO_INDEX:
                    raise ValueError("invalid_target_node")
                runtime.current_index = STAGE_TO_INDEX[target_node]
                self._mark_approval_resolved(runtime)
                runtime.status = "running"
                runtime.review_logs.append(
                    {
                        "action": "revise",
                        "operator_id": operator_id,
                        "stage": stage or runtime.state.get("approval_stage") or "",
                        "issue_type": issue_type or "manual_feedback",
                        "priority": priority,
                        "message": message or "",
                        "target_node": target_node,
                    }
                )
                runtime.history.append(f"review_revise:{target_node}")
            elif action == "reject":
                runtime.status = "rejected"
                runtime.awaiting_review = False
                runtime.state["approval_required"] = False
                runtime.state["approval_stage"] = None
                runtime.review_logs.append(
                    {
                        "action": "reject",
                        "operator_id": operator_id,
                        "stage": stage or "",
                        "issue_type": issue_type or "manual_reject",
                        "priority": priority,
                        "message": message or "rejected_by_user",
                    }
                )
                runtime.state["errors"].append(
                    {"node": "Director_Agent", "error": message or "rejected_by_user"}
                )
                runtime.history.append("review_rejected")
            else:
                raise ValueError("invalid_action")
            return runtime

    def advance(self, project_id: str, force: bool = False) -> ProjectRuntime:
        with self._lock:
            runtime = self._store.get(project_id)
            if runtime is None:
                raise KeyError(project_id)
            if runtime.status in {"completed", "rejected", "failed"}:
                return runtime
            now = time.time()
            if not force and now - runtime.last_advanced_at < 1.2:
                return runtime
            runtime.last_advanced_at = now
            if runtime.awaiting_review:
                return runtime
            if runtime.current_index >= len(AGENT_SEQUENCE):
                runtime.status = "completed"
                return runtime
            node_name, handler, _ = AGENT_SEQUENCE[runtime.current_index]
            runtime.state = handler(runtime.state)
            runtime.step_count += 1
            runtime.history.append(node_name)
            runtime.state["cost_usage"][node_name] = runtime.state["cost_usage"].get(
                node_name, 0.0
            ) + NODE_COST[node_name]
            if runtime.state["approval_required"]:
                runtime.awaiting_review = True
                runtime.status = "waiting_review"
            else:
                runtime.current_index += 1
            if node_name == NODE_COMPOSITOR and runtime.state.get("final_video"):
                runtime.current_index = len(AGENT_SEQUENCE)
                runtime.status = "completed"
                runtime.awaiting_review = False
            if runtime.state["iteration_count"] > runtime.state["max_iterations"]:
                runtime.status = "failed"
                runtime.state["errors"].append(
                    {"node": "Director_Agent", "error": "max_iterations_exceeded"}
                )
            return runtime

    def snapshot(self, project_id: str) -> Dict[str, object]:
        with self._lock:
            runtime = self._store.get(project_id)
            if runtime is None:
                raise KeyError(project_id)
            state = runtime.state
            current_node = state.get("current_node") or AGENT_SEQUENCE[0][0]
            current_stage_name = "Queued"
            if runtime.current_index < len(AGENT_SEQUENCE):
                current_stage_name = AGENT_SEQUENCE[runtime.current_index][2]
            if runtime.awaiting_review and state.get("approval_stage"):
                current_stage_name = f"{state['approval_stage'].title()} Review"
            quality_pass = 4 if runtime.status != "completed" else 5
            quality_total = 5
            render_cost = round(sum(state["cost_usage"].values()), 2)
            eta = NODE_ETA.get(current_node, "00:00:20")
            node_metrics = []
            for idx, (node_name, _, display_name) in enumerate(AGENT_SEQUENCE):
                run_count = runtime.history.count(node_name)
                if runtime.status == "completed":
                    node_status = "completed"
                elif runtime.awaiting_review and idx == runtime.current_index:
                    node_status = "review"
                elif idx < runtime.current_index:
                    node_status = "completed"
                elif idx == runtime.current_index:
                    node_status = "running"
                else:
                    node_status = "queued"
                node_metrics.append(
                    {
                        "node": node_name,
                        "label": display_name,
                        "status": node_status,
                        "runCount": run_count,
                        "cost": round(state["cost_usage"].get(node_name, 0.0), 2),
                    }
                )
            assets = {
                "scriptReady": bool(state.get("script_data")),
                "styleReady": bool(state.get("global_style")),
                "characterCount": len(state.get("character_assets", {})),
                "storyboardCount": len(state.get("storyboard_frames", [])),
                "videoCount": len(state.get("video_clips", [])),
                "audioCount": len(state.get("audio_tracks", {})),
                "finalVideoUri": (
                    state["final_video"]["uri"] if state.get("final_video") else None
                ),
            }
            character_gallery = [
                _build_asset_preview(asset, "character")
                for asset in state.get("character_assets", {}).values()
            ]
            storyboard_gallery = [
                _build_asset_preview(asset, "storyboard")
                for asset in state.get("storyboard_frames", [])
            ]
            video_gallery = [
                _build_asset_preview(asset, "video")
                for asset in state.get("video_clips", [])
            ]
            if state.get("final_video"):
                video_gallery.append(_build_asset_preview(state["final_video"], "video"))
            asset_gallery = {
                "characters": character_gallery,
                "storyboards": storyboard_gallery,
                "videos": video_gallery,
            }
            return {
                "projectId": state["project_id"],
                "prompt": state["user_prompt"],
                "stage": current_stage_name,
                "mode": "Human-in-the-loop",
                "status": runtime.status,
                "qualityPass": quality_pass,
                "qualityTotal": quality_total,
                "renderCost": render_cost,
                "eta": eta,
                "approvalRequired": runtime.awaiting_review,
                "approvalStage": state.get("approval_stage"),
                "currentNode": current_node,
                "finalVideoUri": (
                    state["final_video"]["uri"] if state.get("final_video") else None
                ),
                "assets": assets,
                "assetGallery": asset_gallery,
                "nodeMetrics": node_metrics,
                "latestReview": runtime.review_logs[-1] if runtime.review_logs else None,
                "reviewLogs": list(runtime.review_logs),
                "history": list(runtime.history),
                "errors": list(state["errors"]),
            }

    def sse_event(self, project_id: str) -> str:
        payload = self.snapshot(project_id)
        return f"event: snapshot\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


orchestrator = ProjectOrchestrator()
