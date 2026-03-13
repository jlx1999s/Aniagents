import time
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Set, Tuple

from app.graph.state import ManjuState


@dataclass
class ToolExecutionResult:
    state: ManjuState
    metadata: Dict[str, Any]


class ToolizedAgentExecutor:
    def execute(
        self,
        *,
        node_name: str,
        handler: Callable[[ManjuState], ManjuState],
        state: ManjuState,
        allowed_write_fields: Optional[Set[str]] = None,
    ) -> ToolExecutionResult:
        started = time.time()
        before_state = deepcopy(state)
        next_state = handler(state)
        if allowed_write_fields is not None:
            keys = set(before_state.keys()) | set(next_state.keys())
            changed = {key for key in keys if before_state.get(key) != next_state.get(key)}
            unauthorized = sorted(key for key in changed if key not in allowed_write_fields)
            if unauthorized:
                raise ValueError(
                    f"unauthorized_state_write:{node_name}:{','.join(unauthorized)}"
                )
        elapsed_ms = int((time.time() - started) * 1000)
        return ToolExecutionResult(
            state=next_state,
            metadata={
                "node": node_name,
                "tool_type": "agent_handler",
                "latency_ms": elapsed_ms,
            },
        )
