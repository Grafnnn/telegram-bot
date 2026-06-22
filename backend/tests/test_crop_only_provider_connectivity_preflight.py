from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "scripts" / "validate_crop_only_provider_connectivity_preflight.py"
PACKET_MD = REPO_ROOT / "docs" / "experiments" / "crop_only_provider_connectivity_preflight_007.md"
MANIFEST_JSON = REPO_ROOT / "docs" / "experiments" / "fixtures" / "crop_only_provider_connectivity_preflight_007.json"


def test_crop_only_provider_connectivity_preflight_validator_passes() -> None:
    result = subprocess.run([sys.executable, str(VALIDATOR)], check=False, text=True, capture_output=True)

    assert result.returncode == 0, result.stderr or result.stdout
    assert "crop-only provider connectivity preflight validated" in result.stdout


def test_crop_only_provider_connectivity_preflight_is_not_execution_approval() -> None:
    packet = PACKET_MD.read_text(encoding="utf-8")
    manifest = json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))

    assert manifest["status"] == "proposal_only_not_approved_for_provider_execution"
    assert manifest["provider_openai_calls_allowed"] is False
    assert manifest["provider_http_requests_allowed"] == 0
    assert manifest["controlled_provider_execution_allowed"] is False
    assert manifest["track_b_retry_allowed"] is False
    assert manifest["user_facing_rollout_allowed"] is False
    assert "does not approve provider/OpenAI execution" in packet


def test_crop_only_provider_connectivity_preflight_requires_protected_zero_call_surface() -> None:
    manifest = json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))

    assert manifest["preflight_surface"] == "GET /api/internal/ai-readiness/image-generation"
    assert manifest["preflight_surface_requires_bot_token"] is True
    assert manifest["preflight_surface_provider_called"] is False
    assert manifest["next_track_b_retry_requires_fresh_explicit_go"] is True


def test_crop_only_provider_connectivity_preflight_forbids_secret_payload_and_user_photo_exposure() -> None:
    manifest = json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))

    assert manifest["secret_or_raw_payload_exposure_allowed"] is False
    assert manifest["real_user_photos_allowed"] is False
    assert "openai_api_key_value" in manifest["diagnostics_forbidden"]
    assert "raw_provider_payload" in manifest["diagnostics_forbidden"]
    assert "base64_image_data" in manifest["diagnostics_forbidden"]
