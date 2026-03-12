import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Tuple

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
    ) -> ToolExecutionResult:
        started = time.time()
        next_state = handler(state)
        elapsed_ms = int((time.time() - started) * 1000)
        return ToolExecutionResult(
            state=next_state,
            metadata={
                "node": node_name,
                "tool_type": "agent_handler",
                "latency_ms": elapsed_ms,
            },
        )
