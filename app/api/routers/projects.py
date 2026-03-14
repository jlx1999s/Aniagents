import asyncio
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.api.schemas.project import (
    BatchDeleteProjectsRequest,
    BatchDeleteProjectsResponse,
    ChatRequest,
    CreateProjectRequest,
    CreateProjectResponse,
    ProjectStatsResponse,
    ProjectSnapshot,
    ReviewRequest,
)
from app.services.orchestrator import orchestrator

router = APIRouter(prefix="/api/projects", tags=["projects"])
CHAT_AUTO_ADVANCE_INTENTS = {
    "continue_pipeline",
    "prompt_update",
    "revise_script",
    "revise_style",
    "revise_existing",
    "approve_review",
    "new_creation",
}
CHAT_AUTO_ADVANCE_MAX_STEPS = 6


@router.get("", response_model=List[str])
def list_projects() -> List[str]:
    return orchestrator.list_project_ids()


@router.get("/stats", response_model=ProjectStatsResponse)
def get_project_stats() -> ProjectStatsResponse:
    return ProjectStatsResponse(**orchestrator.project_stats())


@router.post("", response_model=CreateProjectResponse)
def create_project(payload: CreateProjectRequest) -> CreateProjectResponse:
    project_id = orchestrator.create_project(payload.user_prompt)
    return CreateProjectResponse(project_id=project_id)


@router.post("/delete-batch", response_model=BatchDeleteProjectsResponse)
def delete_projects(payload: BatchDeleteProjectsRequest) -> BatchDeleteProjectsResponse:
    normalized_ids = []
    seen = set()
    for project_id in payload.project_ids:
        value = (project_id or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        normalized_ids.append(value)
    deleted_count = orchestrator.delete_projects(normalized_ids)
    return BatchDeleteProjectsResponse(deleted_count=deleted_count)


@router.get("/{project_id}", response_model=ProjectSnapshot)
def get_project(project_id: str, compact: bool = False) -> ProjectSnapshot:
    try:
        return ProjectSnapshot(**orchestrator.snapshot(project_id, compact=compact))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="project_not_found") from exc


@router.delete("/{project_id}")
def delete_project(project_id: str) -> dict:
    deleted = orchestrator.delete_project(project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="project_not_found")
    return {"ok": True}


@router.post("/{project_id}/review", response_model=ProjectSnapshot)
def submit_review(project_id: str, payload: ReviewRequest) -> ProjectSnapshot:
    try:
        orchestrator.submit_review(
            project_id=project_id,
            action=payload.action,
            target_node=payload.target_node,
            message=payload.message,
            stage=payload.stage,
            issue_type=payload.issue_type,
            priority=payload.priority or "medium",
            operator_id=payload.operator_id or "anonymous",
        )
        orchestrator.advance(project_id, force=True)
        return ProjectSnapshot(**orchestrator.snapshot(project_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="project_not_found") from exc
    except ValueError as exc:
        if str(exc) == "review_not_required":
            return ProjectSnapshot(**orchestrator.snapshot(project_id))
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{project_id}/advance", response_model=ProjectSnapshot)
def advance_project(project_id: str) -> ProjectSnapshot:
    try:
        orchestrator.advance(project_id, force=True)
        return ProjectSnapshot(**orchestrator.snapshot(project_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="project_not_found") from exc


@router.post("/{project_id}/chat", response_model=ProjectSnapshot)
def chat_project(project_id: str, payload: ChatRequest) -> ProjectSnapshot:
    try:
        orchestrator.chat_and_operate(
            project_id=project_id,
            message=payload.message,
            operator_id=payload.operator_id or "anonymous",
            idempotency_key=payload.idempotency_key,
        )
        runtime = orchestrator.get_runtime(project_id)
        if runtime is not None:
            last_intent = str((runtime.state.get("last_chat_command") or {}).get("intent") or "")
            if last_intent in CHAT_AUTO_ADVANCE_INTENTS:
                for _ in range(CHAT_AUTO_ADVANCE_MAX_STEPS):
                    runtime = orchestrator.get_runtime(project_id)
                    if runtime is None:
                        break
                    if runtime.status != "running" or runtime.awaiting_review:
                        break
                    before_version = int(runtime.state.get("version") or 0)
                    before_index = int(runtime.current_index)
                    orchestrator.advance(project_id, force=True)
                    runtime = orchestrator.get_runtime(project_id)
                    if runtime is None:
                        break
                    after_version = int(runtime.state.get("version") or 0)
                    after_index = int(runtime.current_index)
                    if after_version <= before_version and after_index == before_index:
                        break
        return ProjectSnapshot(**orchestrator.snapshot(project_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="project_not_found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{project_id}/intent-router-policy")
def read_project_intent_router_policy(project_id: str) -> Dict[str, Any]:
    try:
        return orchestrator.get_project_intent_router_policy(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="project_not_found") from exc


@router.put("/{project_id}/intent-router-policy")
def update_project_intent_router_policy(project_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return orchestrator.set_project_intent_router_policy(project_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="project_not_found") from exc


@router.get("/{project_id}/stream")
async def stream_project(project_id: str, request: Request) -> StreamingResponse:
    try:
        orchestrator.snapshot(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="project_not_found") from exc

    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            yield orchestrator.sse_event(project_id)
            await asyncio.sleep(1.0)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
