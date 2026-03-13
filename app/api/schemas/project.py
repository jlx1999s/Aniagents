from typing import List, Literal, Optional

from pydantic import BaseModel


class CreateProjectRequest(BaseModel):
    user_prompt: str


class CreateProjectResponse(BaseModel):
    project_id: str


class ProjectStatsResponse(BaseModel):
    total: int
    running: int
    waiting_review: int
    completed: int
    rejected: int
    failed: int


class BatchDeleteProjectsRequest(BaseModel):
    project_ids: List[str]


class BatchDeleteProjectsResponse(BaseModel):
    deleted_count: int


class ReviewRequest(BaseModel):
    action: Literal["approve", "revise", "reject"]
    target_node: Optional[str] = None
    message: Optional[str] = None
    stage: Optional[str] = None
    issue_type: Optional[str] = None
    priority: Optional[Literal["low", "medium", "high"]] = "medium"
    operator_id: Optional[str] = "anonymous"


class ChatRequest(BaseModel):
    message: str
    operator_id: Optional[str] = "anonymous"


class ProjectSnapshot(BaseModel):
    projectId: str
    prompt: str
    stage: str
    mode: str
    status: str
    qualityPass: int
    qualityTotal: int
    renderCost: float
    eta: str
    approvalRequired: bool
    approvalStage: Optional[str]
    currentNode: str
    finalVideoUri: Optional[str]
    assets: dict
    assetGallery: dict
    storyboardTable: List[dict]
    nodeMetrics: List[dict]
    latestReview: Optional[dict]
    reviewLogs: List[dict]
    chatLogs: List[dict]
    activityLogs: List[dict]
    executionPlan: List[dict]
    executionPlanSummary: str
    suggestedCommands: List[str]
    targetNodeOptions: List[dict]
    conversationRound: Optional[int] = None
    roundHistory: Optional[List[dict]] = None
    intentRouterPolicy: Optional[dict] = None
    intentLogs: Optional[List[dict]] = None
    history: List[str]
    errors: List[dict]
