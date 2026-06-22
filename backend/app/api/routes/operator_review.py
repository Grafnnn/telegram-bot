"""Internal operator-review routes for crop-only experiment gates."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import verify_bot_internal_token
from app.config import get_settings
from app.services.crop_only_operator_review_service import build_track_a_fake_provider_smoke_report
from app.utils.redaction import safe_exception_summary

router = APIRouter(prefix="/internal/crop-only", tags=["internal-crop-only"])
logger = logging.getLogger(__name__)


@router.post(
    "/operator-review/track-a-smoke",
    dependencies=[Depends(verify_bot_internal_token)],
)
def run_track_a_fake_provider_smoke() -> dict[str, Any]:
    """Return a fake-provider Track A smoke report for internal review.

    The route is disabled by default and never calls OpenAI. It is intended for
    operator-only staging mechanics after a separate explicit GO.
    """

    settings = get_settings()
    if not settings.crop_only_operator_review_track_a_enabled:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Crop-only Track A operator review smoke is disabled.",
        )
    try:
        return build_track_a_fake_provider_smoke_report()
    except Exception as exc:
        logger.warning("Track A fake-provider smoke failed error=%s", safe_exception_summary(exc))
        raise HTTPException(status.HTTP_409_CONFLICT, "Track A fake-provider smoke failed closed.") from exc
