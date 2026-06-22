"""Internal AI readiness diagnostics routes.

These endpoints report sanitized configuration/readiness state only. They do not
call OpenAI, touch provider credentials, write database rows, or enable any
user-facing flow.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.api.deps import verify_bot_internal_token
from app.config import get_settings

router = APIRouter(prefix="/internal/ai-readiness", tags=["internal-ai-readiness"])


def build_image_generation_readiness() -> dict[str, Any]:
    """Return a redacted zero-call image generation readiness report."""

    settings = get_settings()
    openai_configured = settings.is_openai_configured
    return {
        "status": "ready_for_configured_runtime" if openai_configured else "blocked_missing_openai_api_key",
        "openai_configured": openai_configured,
        "provider": "OpenAI",
        "image_model": settings.openai_image_model,
        "endpoint": "/v1/images/edits",
        "provider_called": False,
        "provider_http_requests": 0,
        "secret_values_returned": False,
        "raw_provider_payloads_returned": False,
        "user_photo_mask_mode": settings.user_photo_mask_mode,
        "user_photo_preservation_check_enabled": settings.user_photo_preservation_check_enabled,
        "crop_only_operator_review_track_a_enabled": settings.crop_only_operator_review_track_a_enabled,
        "user_facing_rollout_approved": False,
        "diagnostic_scope": "configuration_only_no_provider_call",
    }


@router.get(
    "/image-generation",
    dependencies=[Depends(verify_bot_internal_token)],
)
def image_generation_readiness() -> dict[str, Any]:
    """Return sanitized image-generation readiness without making provider calls."""

    return build_image_generation_readiness()
