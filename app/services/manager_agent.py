from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.tools.mcp_client import generate_manager_decision_tool


@dataclass
class ManagerDecision:
    action: str
    next_node: Optional[str]
    reason: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class ManagerAgent:
    def _rule_decide(
        self,
        *,
        status: str,
        awaiting_review: bool,
        current_index: int,
        sequence: List[Tuple[str, Any, str]],
        preferred_node: Optional[str] = None,
    ) -> ManagerDecision:
        policy = "manager_policy_v1_rule"
        if status in {"rejected", "failed"}:
            return ManagerDecision(
                action="halt",
                next_node=None,
                reason="terminal_status",
                metadata={"status": status, "policy": policy},
            )
        if awaiting_review:
            return ManagerDecision(
                action="await_review",
                next_node=None,
                reason="review_gate_open",
                metadata={"policy": policy},
            )
        if current_index >= len(sequence):
            return ManagerDecision(
                action="complete",
                next_node=None,
                reason="all_nodes_done",
                metadata={"policy": policy},
            )
        nodes = {item[0] for item in sequence}
        if preferred_node and preferred_node in nodes:
            return ManagerDecision(
                action="execute",
                next_node=preferred_node,
                reason="preferred_node",
                metadata={"policy": policy},
            )
        return ManagerDecision(
            action="execute",
            next_node=sequence[current_index][0],
            reason="sequence_next",
            metadata={"policy": policy},
        )

    def decide(
        self,
        *,
        status: str,
        awaiting_review: bool,
        current_index: int,
        sequence: List[Tuple[str, Any, str]],
        preferred_node: Optional[str] = None,
        history_tail: Optional[List[str]] = None,
    ) -> ManagerDecision:
        rule_decision = self._rule_decide(
            status=status,
            awaiting_review=awaiting_review,
            current_index=current_index,
            sequence=sequence,
            preferred_node=preferred_node,
        )
        if rule_decision.action != "execute" or not rule_decision.next_node:
            return rule_decision
        available_nodes = [item[0] for item in sequence]
        llm_payload = generate_manager_decision_tool(
            available_nodes=available_nodes,
            preferred_node=rule_decision.next_node,
            status=status,
            awaiting_review=awaiting_review,
            current_index=current_index,
            history_tail=history_tail or [],
        )
        action = str(llm_payload.get("action") or "").strip()
        next_node = llm_payload.get("next_node")
        reason = str(llm_payload.get("reason") or "").strip()
        metadata = llm_payload.get("metadata") if isinstance(llm_payload.get("metadata"), dict) else {}
        if action not in {"execute", "await_review", "complete", "halt"}:
            return ManagerDecision(
                action=rule_decision.action,
                next_node=rule_decision.next_node,
                reason=rule_decision.reason,
                metadata={**rule_decision.metadata, "fallback": "invalid_llm_action"},
            )
        if action == "execute":
            if not isinstance(next_node, str) or next_node not in available_nodes:
                return ManagerDecision(
                    action=rule_decision.action,
                    next_node=rule_decision.next_node,
                    reason=rule_decision.reason,
                    metadata={**rule_decision.metadata, "fallback": "invalid_llm_node"},
                )
            return ManagerDecision(
                action="execute",
                next_node=next_node,
                reason=reason or "llm_execute",
                metadata={**metadata, "policy": "manager_policy_v2_llm"},
            )
        return ManagerDecision(
            action=action,
            next_node=None,
            reason=reason or "llm_non_execute",
            metadata={**metadata, "policy": "manager_policy_v2_llm"},
        )
