from typing import Any, Dict

from fastapi import APIRouter

from app.services.model_routes import get_routes, set_routes
from app.services.review_gateway_policy import (
    get_review_gateway_policy,
    set_review_gateway_policy,
)

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/model-routes")
def read_model_routes() -> Dict[str, Any]:
    return get_routes()


@router.put("/model-routes")
def update_model_routes(payload: Dict[str, Any]) -> Dict[str, Any]:
    return set_routes(payload)


@router.get("/review-gateway-policy")
def read_review_gateway_policy() -> Dict[str, Any]:
    return get_review_gateway_policy()


@router.put("/review-gateway-policy")
def update_review_gateway_policy(payload: Dict[str, Any]) -> Dict[str, Any]:
    return set_review_gateway_policy(payload)
