from typing import Any, Dict, List, Literal, Optional, TypedDict
from uuid import uuid4

StageLiteral = Literal[
    "script",
    "style",
    "character",
    "storyboard",
    "animation",
    "audio",
    "compositor",
]

PriorityLiteral = Literal["low", "medium", "high"]


class FeedbackItem(TypedDict):
    stage: StageLiteral
    issue_type: str
    message: str
    target_node: str
    priority: PriorityLiteral
    round_id: int


class AssetMeta(TypedDict):
    asset_id: str
    uri: str
    version: int
    seed: Optional[int]
    model_name: str
    params: Dict[str, Any]
    qa_score: Optional[float]


class ManjuState(TypedDict):
    project_id: str
    user_prompt: str
    current_node: str
    route_reason: Optional[str]
    script_data: Dict[str, Any]
    script_history: List[Dict[str, Any]]
    global_style: Dict[str, Any]
    character_assets: Dict[str, AssetMeta]
    storyboard_frames: List[AssetMeta]
    video_clips: List[AssetMeta]
    audio_tracks: Dict[str, AssetMeta]
    final_video: Optional[AssetMeta]
    pending_feedback: List[FeedbackItem]
    approval_required: bool
    approval_stage: Optional[str]
    retry_count_by_node: Dict[str, int]
    max_retry_by_node: Dict[str, int]
    iteration_count: int
    max_iterations: int
    intent_router_policy: Dict[str, Any]
    cost_usage: Dict[str, float]
    timing_ms: Dict[str, int]
    timing_last_ms: Dict[str, int]
    errors: List[Dict[str, Any]]


def create_initial_state(user_prompt: str, project_id: Optional[str] = None) -> ManjuState:
    from app.services.intent_router_policy import get_intent_router_policy, normalize_intent_router_policy

    resolved_project_id = project_id or str(uuid4())
    return ManjuState(
        project_id=resolved_project_id,
        user_prompt=user_prompt,
        current_node="",
        route_reason=None,
        script_data={},
        script_history=[],
        global_style={},
        character_assets={},
        storyboard_frames=[],
        video_clips=[],
        audio_tracks={},
        final_video=None,
        pending_feedback=[],
        approval_required=False,
        approval_stage=None,
        retry_count_by_node={},
        max_retry_by_node={},
        iteration_count=0,
        max_iterations=20,
        intent_router_policy=normalize_intent_router_policy(get_intent_router_policy()),
        cost_usage={},
        timing_ms={},
        timing_last_ms={},
        errors=[],
    )
