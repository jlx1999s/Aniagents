from typing import Any


def build_memory_checkpointer() -> Any:
    try:
        from langgraph.checkpoint.memory import MemorySaver
    except Exception as exc:
        raise RuntimeError("LangGraph checkpoint backend unavailable") from exc
    return MemorySaver()
