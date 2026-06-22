#!/usr/bin/env python3
"""Validate Track A fake-provider smoke result report."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
REPORT_JSON = REPO_ROOT / "docs" / "experiments" / "reports" / "crop_only_track_a_fake_provider_smoke_005.json"
REPORT_MD = REPO_ROOT / "docs" / "experiments" / "reports" / "crop_only_track_a_fake_provider_smoke_005.md"
EXPECTED_FIXTURE_IDS = [
    "pm001-solid-frontal",
    "pm001-pattern-boundary",
    "pm003-large-pattern-scale",
    "pm004-edge-boundary-stress",
]

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
        raise AssertionError(f"Missing JSON report: {_relative(path)}")
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


def _assert_false(report: dict[str, Any], key: str) -> None:
    if report.get(key) is not False:
        raise AssertionError(f"{key} must be false.")


def validate() -> None:
    report = _read_json(REPORT_JSON)
    if not REPORT_MD.is_file():
        raise AssertionError(f"Missing Markdown report: {_relative(REPORT_MD)}")
    report_md = REPORT_MD.read_text(encoding="utf-8")

    if report.get("experiment_id") != "crop-only-track-a-fake-provider-smoke-005":
        raise AssertionError("Unexpected experiment id.")
    if report.get("baseline") != "main@6d9bb354a456e8bffccf5d49f8bf3610b8260dbd":
        raise AssertionError("Unexpected baseline.")
    if report.get("target") != "local/dev service-level smoke":
        raise AssertionError("Unexpected target.")
    if report.get("endpoint") != "/api/internal/crop-only/operator-review/track-a-smoke":
        raise AssertionError("Unexpected endpoint.")
    if report.get("decision") != "TRACK_A_FAKE_PROVIDER_ROUTE_SMOKE_READY":
        raise AssertionError("Unexpected decision.")
    if report.get("service_level_status") != "pass":
        raise AssertionError("Service-level smoke must pass.")
    if report.get("route_level_status") != "covered_by_ci_pr_75_not_executed_locally_due_missing_fastapi_dependency":
        raise AssertionError("Route-level limitation must remain explicit.")
    if report.get("openai_provider_calls") != 0:
        raise AssertionError("Track A report must record zero provider/OpenAI calls.")
    if report.get("fixture_count") != 4:
        raise AssertionError("Track A report must cover four fixtures.")
    if report.get("fixture_ids") != EXPECTED_FIXTURE_IDS:
        raise AssertionError("Unexpected fixture ids or order.")

    local_route = report.get("local_route_level_attempt")
    if not isinstance(local_route, dict):
        raise AssertionError("Missing local_route_level_attempt object.")
    if local_route.get("executed") is not False:
        raise AssertionError("Local route-level attempt must be false.")
    if local_route.get("reason") != "local FastAPI dependency unavailable":
        raise AssertionError("Local route-level limitation reason mismatch.")
    if local_route.get("route_behavior_covered_by") != "PR #75 CI route tests":
        raise AssertionError("Route coverage note mismatch.")

    for key in [
        "network_provider_invoked",
        "staging_prod_env_touched",
        "runtime_bot_admin_user_facing_enabled",
        "imports_sql_direct_db_writes",
        "real_user_photos_used",
        "secret_or_raw_payload_exposure",
        "raw_provider_payloads_committed",
        "user_facing_rollout_approved",
        "track_b_controlled_provider_execution",
    ]:
        _assert_false(report, key)

    required_md_text = [
        "Status: `SERVICE_LEVEL_PASS / ROUTE_LEVEL_COVERED_BY_CI`",
        "Provider/OpenAI calls | 0",
        "Route-level reason | local FastAPI dependency unavailable",
        "Decision: `TRACK_A_FAKE_PROVIDER_ROUTE_SMOKE_READY`",
        "does not approve Track B",
        "does not approve user-facing rollout",
    ]
    missing = [phrase for phrase in required_md_text if phrase not in report_md]
    if missing:
        raise AssertionError(f"Markdown report missing required text: {', '.join(missing)}")

    _reject_risky_text(REPORT_JSON, json.dumps(report, ensure_ascii=False, sort_keys=True))
    _reject_risky_text(REPORT_MD, report_md)


def main() -> int:
    try:
        validate()
    except AssertionError as exc:
        print(f"validation failed: {exc}", file=sys.stderr)
        return 1
    print("crop-only Track A fake-provider smoke report validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
