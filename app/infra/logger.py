from typing import Dict


def build_log_context(project_id: str, node_name: str) -> Dict[str, str]:
    return {"project_id": project_id, "node": node_name}
