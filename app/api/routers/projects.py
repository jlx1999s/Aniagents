import asyncio
from typing import List

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


def _should_advance_from_chat(message: str) -> bool:
    text = (message or "").strip()
    if not text:
        return False
    keywords = [
        "开始下一阶段",
        "开始分镜拆解",
        "开始角色生成",
        "开始分镜图生成",
        "开始视频生成",
        "执行当前阶段",
        "确认风格",
        "通过",
        "继续",
        "重做",
        "返修",
        "修改风格",
    ]
    return any(keyword in text for keyword in keywords)


def _should_auto_advance_after_prompt_update(runtime) -> bool:
    if runtime.awaiting_review:
        return False
    if runtime.current_index != 0:
        return False
    if not runtime.history:
        return False
    return runtime.history[-1] in {"chat_update_prompt", "chat_revise_script"}


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
def get_project(project_id: str) -> ProjectSnapshot:
    try:
        return ProjectSnapshot(**orchestrator.snapshot(project_id))
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
        runtime = orchestrator.chat_and_operate(
            project_id=project_id,
            message=payload.message,
            operator_id=payload.operator_id or "anonymous",
        )
        if _should_advance_from_chat(payload.message) or _should_auto_advance_after_prompt_update(runtime):
            orchestrator.advance(project_id, force=True)
        return ProjectSnapshot(**orchestrator.snapshot(project_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="project_not_found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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
