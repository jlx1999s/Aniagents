import asyncio
from typing import List

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.api.schemas.project import (
    CreateProjectRequest,
    CreateProjectResponse,
    ProjectSnapshot,
    ReviewRequest,
)
from app.services.orchestrator import orchestrator

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=List[str])
def list_projects() -> List[str]:
    return orchestrator.list_project_ids()


@router.post("", response_model=CreateProjectResponse)
def create_project(payload: CreateProjectRequest) -> CreateProjectResponse:
    project_id = orchestrator.create_project(payload.user_prompt)
    orchestrator.advance(project_id, force=True)
    return CreateProjectResponse(project_id=project_id)


@router.get("/{project_id}", response_model=ProjectSnapshot)
def get_project(project_id: str) -> ProjectSnapshot:
    try:
        return ProjectSnapshot(**orchestrator.snapshot(project_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="project_not_found") from exc


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
            orchestrator.advance(project_id)
            yield orchestrator.sse_event(project_id)
            await asyncio.sleep(1.0)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
