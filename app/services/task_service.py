from typing import Dict


def merge_timing(target: Dict[str, int], node_name: str, elapsed_ms: int) -> Dict[str, int]:
    target[node_name] = elapsed_ms
    return target
