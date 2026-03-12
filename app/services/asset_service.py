from typing import Any, Dict, Optional
from uuid import uuid4

from app.graph.state import AssetMeta


def create_asset_meta(
    uri: str,
    model_name: str,
    params: Dict[str, Any],
    seed: Optional[int] = None,
    version: int = 1,
    qa_score: Optional[float] = None,
) -> AssetMeta:
    return AssetMeta(
        asset_id=str(uuid4()),
        uri=uri,
        version=version,
        seed=seed,
        model_name=model_name,
        params=params,
        qa_score=qa_score,
    )
