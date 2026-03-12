from typing import Any, Dict

from fastapi import APIRouter

from app.services.model_routes import get_routes, set_routes

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/model-routes")
def read_model_routes() -> Dict[str, Any]:
    return get_routes()


@router.put("/model-routes")
def update_model_routes(payload: Dict[str, Any]) -> Dict[str, Any]:
    return set_routes(payload)

