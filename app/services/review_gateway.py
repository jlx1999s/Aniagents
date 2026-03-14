from dataclasses import dataclass
from typing import Any, Dict

from app.graph.routing import (
    NODE_ANIMATION_ARTIST,
    NODE_ART_DIRECTOR,
    NODE_COMPOSITOR,
    NODE_SCENE_DESIGNER,
    NODE_STORYBOARD_ARTIST,
)
from app.graph.state import ManjuState
from app.services.review_gateway_policy import get_review_gateway_policy


@dataclass
class ReviewGatewayDecision:
    status: str
    awaiting_review: bool
    next_index: int
    reason: str
    metadata: Dict[str, Any]


class ReviewGateway:
    def _latest_qa_score(self, node_name: str, state: ManjuState) -> Any:
        if node_name == "Art_Director_Agent":
            style = state.get("global_style") or {}
            if not isinstance(style, dict):
                return None
            return style.get("qa_score")
        if node_name == "Character_Designer_Agent":
            assets = list((state.get("character_assets") or {}).values())
            if not assets:
                return None
            return assets[-1].get("qa_score")
        if node_name == "Scene_Designer_Agent":
            assets = list((state.get("scene_assets") or {}).values())
            if not assets:
                return None
            return assets[-1].get("qa_score")
        if node_name == "Storyboard_Artist_Agent":
            frames = state.get("storyboard_frames") or []
            if not frames:
                return None
            return frames[-1].get("qa_score")
        if node_name == "Animation_Artist_Agent":
            clips = state.get("video_clips") or []
            if not clips:
                return None
            return clips[-1].get("qa_score")
        return None

    def _require_approval(
        self,
        *,
        state: ManjuState,
        current_index: int,
        reason: str,
        approval_stage: str,
        metadata: Dict[str, Any],
    ) -> ReviewGatewayDecision:
        state["approval_required"] = True
        state["approval_stage"] = approval_stage
        return ReviewGatewayDecision(
            status="waiting_review",
            awaiting_review=True,
            next_index=current_index,
            reason=reason,
            metadata=metadata,
        )

    def evaluate_after_execute(
        self,
        *,
        node_name: str,
        current_index: int,
        total_nodes: int,
        state: ManjuState,
    ) -> ReviewGatewayDecision:
        policy = get_review_gateway_policy()
        rules = policy.get("rules", {}) if isinstance(policy, dict) else {}
        if state.get("approval_required"):
            return ReviewGatewayDecision(
                status="waiting_review",
                awaiting_review=True,
                next_index=current_index,
                reason="approval_required",
                metadata={"approval_stage": state.get("approval_stage"), "policy_version": policy.get("version")},
            )
        if node_name == NODE_ART_DIRECTOR:
            return self._require_approval(
                state=state,
                current_index=current_index,
                reason="style_mandatory_review",
                approval_stage="style",
                metadata={"node": node_name, "policy_version": policy.get("version")},
            )
        if node_name == NODE_STORYBOARD_ARTIST:
            return self._require_approval(
                state=state,
                current_index=current_index,
                reason="storyboard_mandatory_review",
                approval_stage="storyboard",
                metadata={"node": node_name, "policy_version": policy.get("version")},
            )
        if node_name == NODE_SCENE_DESIGNER:
            return self._require_approval(
                state=state,
                current_index=current_index,
                reason="scene_mandatory_review",
                approval_stage="scene",
                metadata={"node": node_name, "policy_version": policy.get("version")},
            )
        manual_nodes = rules.get("manualApprovalNodes")
        if isinstance(manual_nodes, list) and node_name in manual_nodes:
            return self._require_approval(
                state=state,
                current_index=current_index,
                reason="manual_approval_node",
                approval_stage="manual",
                metadata={"node": node_name, "policy_version": policy.get("version")},
            )
        if bool(rules.get("forceApprovalOnErrors")) and state.get("errors"):
            return self._require_approval(
                state=state,
                current_index=current_index,
                reason="error_gate",
                approval_stage="risk",
                metadata={"error_count": len(state.get("errors", [])), "policy_version": policy.get("version")},
            )
        cost_threshold = rules.get("maxRenderCostBeforeApproval")
        render_cost = sum((state.get("cost_usage") or {}).values())
        if isinstance(cost_threshold, (int, float)) and cost_threshold > 0 and render_cost >= float(cost_threshold):
            return self._require_approval(
                state=state,
                current_index=current_index,
                reason="cost_gate",
                approval_stage="cost",
                metadata={
                    "render_cost": round(render_cost, 3),
                    "threshold": float(cost_threshold),
                    "policy_version": policy.get("version"),
                },
            )
        min_qa = rules.get("minQaScoreByNode")
        if isinstance(min_qa, dict):
            threshold = min_qa.get(node_name)
            qa_score = self._latest_qa_score(node_name, state)
            if isinstance(threshold, (int, float)) and threshold > 0 and isinstance(qa_score, (int, float)):
                if qa_score < float(threshold):
                    return self._require_approval(
                        state=state,
                        current_index=current_index,
                        reason="quality_gate",
                        approval_stage="quality",
                        metadata={
                            "node": node_name,
                            "qa_score": float(qa_score),
                            "threshold": float(threshold),
                            "policy_version": policy.get("version"),
                        },
                    )
        if node_name == NODE_COMPOSITOR and state.get("final_video"):
            state["approval_required"] = False
            state["approval_stage"] = None
            return ReviewGatewayDecision(
                status="completed",
                awaiting_review=False,
                next_index=total_nodes,
                reason="final_video_ready",
                metadata={"policy_version": policy.get("version")},
            )
        state["approval_required"] = False
        state["approval_stage"] = None
        return ReviewGatewayDecision(
            status="running",
            awaiting_review=False,
            next_index=current_index + 1,
            reason="auto_progress",
            metadata={"policy_version": policy.get("version")},
        )
