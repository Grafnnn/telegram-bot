#!/usr/bin/env python3
"""Validate crop-only provider connectivity preflight gate."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
PACKET_MD = REPO_ROOT / "docs" / "experiments" / "crop_only_provider_connectivity_preflight_007.md"
MANIFEST_JSON = REPO_ROOT / "docs" / "experiments" / "fixtures" / "crop_only_provider_connectivity_preflight_007.json"
PARENT_REPORT_JSON = REPO_ROOT / "docs" / "experiments" / "reports" / "crop_only_track_b_operator_review_006.json"
AI_READINESS_ROUTE = REPO_ROOT / "backend" / "app" / "api" / "routes" / "ai_readiness.py"
BOT_USER_PHOTO_HANDLER = REPO_ROOT / "bot" / "app" / "handlers" / "user_photo.py"

SECRET_PATTERNS = [
    re.compile(r"sk-(?:proj|svcacct|admin|org)-[A-Za-z0-9_-]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{40,}"),
    re.compile(r"\b(?:OPENAI_API_KEY|BOT_INTERNAL_TOKEN|TELEGRAM_BOT_TOKEN|DATABASE_URL)\s*="),
    re.compile("PRIVATE" + r"\s+KEY"),
    re.compile(r"data:image/[a-zA-Z0-9.+-]+;base64,"),
    re.compile(r"[A-Za-z0-9+/]{160,}={0,2}"),
]


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise AssertionError(f"Missing JSON file: {_relative(path)}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AssertionError(f"{_relative(path)} must contain a JSON object.")
    return payload


def _reject_risky_text(path: Path, text: str) -> None:
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("re.compile("):
            continue
        for pattern in SECRET_PATTERNS:
            match = pattern.search(line)
            if match:
                raise AssertionError(
                    f"{_relative(path)}:{line_number} contains forbidden pattern "
                    f"{pattern.pattern!r} near {match.group(0)!r}"
                )


def _assert_false(manifest: dict[str, Any], key: str) -> None:
    if manifest.get(key) is not False:
        raise AssertionError(f"{key} must be false.")


def validate() -> None:
    if not PACKET_MD.is_file():
        raise AssertionError(f"Missing packet: {_relative(PACKET_MD)}")
    if not AI_READINESS_ROUTE.is_file():
        raise AssertionError(f"Missing readiness route: {_relative(AI_READINESS_ROUTE)}")
    if not BOT_USER_PHOTO_HANDLER.is_file():
        raise AssertionError(f"Missing bot handler: {_relative(BOT_USER_PHOTO_HANDLER)}")

    packet = PACKET_MD.read_text(encoding="utf-8")
    manifest = _read_json(MANIFEST_JSON)
    parent = _read_json(PARENT_REPORT_JSON)
    route = AI_READINESS_ROUTE.read_text(encoding="utf-8")
    bot_handler = BOT_USER_PHOTO_HANDLER.read_text(encoding="utf-8")

    if parent.get("decision") != "HOLD_TRACK_B_OPERATOR_REVIEW":
        raise AssertionError("Parent Track B report must remain HOLD.")
    if parent.get("stop_condition") != "provider_call_failed:URLError":
        raise AssertionError("Parent Track B stop condition must remain URLError.")
    if parent.get("actual_provider_http_requests") != 2:
        raise AssertionError("Parent Track B report must record exactly 2 provider HTTP requests.")

    if manifest.get("manifest_id") != "crop-only-provider-connectivity-preflight-007":
        raise AssertionError("Unexpected manifest id.")
    if manifest.get("status") != "proposal_only_not_approved_for_provider_execution":
        raise AssertionError("Manifest must remain proposal-only.")
    if manifest.get("baseline_commit") != "9dfed6ee88e257691e0bcc1fb76578df97cea165":
        raise AssertionError("Baseline mismatch.")
    if manifest.get("parent_decision_required") != "HOLD_TRACK_B_OPERATOR_REVIEW":
        raise AssertionError("Parent decision requirement mismatch.")
    if manifest.get("observed_track_b_stop_condition") != "provider_call_failed:URLError":
        raise AssertionError("Observed Track B stop condition mismatch.")
    if manifest.get("preflight_surface") != "GET /api/internal/ai-readiness/image-generation":
        raise AssertionError("Unexpected preflight surface.")
    if manifest.get("preflight_surface_requires_bot_token") is not True:
        raise AssertionError("Preflight surface must require bot token.")
    if manifest.get("preflight_surface_provider_called") is not False:
        raise AssertionError("Preflight surface must not call provider.")
    if manifest.get("provider_http_requests_allowed") != 0:
        raise AssertionError("Preflight provider HTTP request allowance must be zero.")
    if manifest.get("next_track_b_retry_requires_fresh_explicit_go") is not True:
        raise AssertionError("Track B retry must require a fresh explicit GO.")

    for key in [
        "provider_openai_calls_allowed",
        "controlled_provider_execution_allowed",
        "track_b_retry_allowed",
        "staging_prod_env_allowed",
        "runtime_user_facing_enablement_allowed",
        "telegram_bot_rollout_allowed",
        "admin_user_facing_enablement_allowed",
        "user_facing_rollout_allowed",
        "real_user_photos_allowed",
        "imports_sql_direct_db_writes_allowed",
        "secret_or_raw_payload_exposure_allowed",
    ]:
        _assert_false(manifest, key)

    required_packet_text = [
        "Status: `PREFLIGHT_PROPOSAL / NOT APPROVED FOR PROVIDER EXECUTION`",
        "provider HTTP requests: `2`",
        "GET /api/internal/ai-readiness/image-generation",
        "performs `0` provider HTTP requests",
        "Track B retry is attempted without a fresh explicit GO packet",
        "This gate does not approve:",
    ]
    missing_packet = [phrase for phrase in required_packet_text if phrase not in packet]
    if missing_packet:
        raise AssertionError(f"Packet missing required text: {', '.join(missing_packet)}")

    required_route_text = [
        "verify_bot_internal_token",
        "provider_called",
        "provider_http_requests",
        "secret_values_returned",
        "configuration_only_no_provider_call",
    ]
    missing_route = [phrase for phrase in required_route_text if phrase not in route]
    if missing_route:
        raise AssertionError(f"Readiness route missing required text: {', '.join(missing_route)}")

    required_bot_text = [
        "GENERATION_FAILURE_OPENAI_NOT_CONFIGURED",
        "GENERATION_FAILURE_PROVIDER_UNAVAILABLE",
        "GENERATION_FAILURE_MASK_REQUIRED",
        "User photo try-on returned failed status reason=%s",
    ]
    missing_bot = [phrase for phrase in required_bot_text if phrase not in bot_handler]
    if missing_bot:
        raise AssertionError(f"Bot handler missing required text: {', '.join(missing_bot)}")

    for path, text in [
        (PACKET_MD, packet),
        (MANIFEST_JSON, json.dumps(manifest, ensure_ascii=False, sort_keys=True)),
        (AI_READINESS_ROUTE, route),
        (BOT_USER_PHOTO_HANDLER, bot_handler),
    ]:
        _reject_risky_text(path, text)


def main() -> int:
    try:
        validate()
    except AssertionError as exc:
        print(f"validation failed: {exc}", file=sys.stderr)
        return 1
    print("crop-only provider connectivity preflight validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
