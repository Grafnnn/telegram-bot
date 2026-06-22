#!/usr/bin/env python3
"""Validate Track B provider-failure triage design."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DESIGN_MD = REPO_ROOT / "docs" / "experiments" / "crop_only_track_b_provider_failure_triage_design_012.md"
MANIFEST_JSON = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "fixtures"
    / "crop_only_track_b_provider_failure_triage_design_012.json"
)
PARENT_009 = REPO_ROOT / "docs" / "experiments" / "reports" / "crop_only_track_b_remaining_fixtures_009.json"
PARENT_010 = (
    REPO_ROOT / "docs" / "experiments" / "reports" / "crop_only_track_b_provider_failure_diagnostic_010.json"
)
PARENT_011 = REPO_ROOT / "docs" / "experiments" / "reports" / "crop_only_track_b_one_fixture_retry_011.json"

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
    if not DESIGN_MD.is_file():
        raise AssertionError(f"Missing design doc: {_relative(DESIGN_MD)}")
    design = DESIGN_MD.read_text(encoding="utf-8")
    manifest = _read_json(MANIFEST_JSON)
    parent_009 = _read_json(PARENT_009)
    parent_010 = _read_json(PARENT_010)
    parent_011 = _read_json(PARENT_011)

    if parent_009.get("decision") != "HOLD_REMAINING_FIXTURES_REVIEW":
        raise AssertionError("Parent 009 must remain HOLD.")
    if parent_009.get("stop_condition") != "provider_call_failed:ImageGenerationProviderError":
        raise AssertionError("Parent 009 stop condition mismatch.")
    if parent_009.get("actual_provider_http_requests") != 2:
        raise AssertionError("Parent 009 request count mismatch.")
    if parent_009.get("retry_count") != 1:
        raise AssertionError("Parent 009 retry count mismatch.")
    if parent_009.get("fixtures") != []:
        raise AssertionError("Parent 009 must have no completed fixtures.")

    if parent_010.get("decision") != "READY_FOR_ONE_FIXTURE_RETRY_PACKET_DESIGN":
        raise AssertionError("Parent 010 decision mismatch.")
    if parent_010.get("provider_openai_calls") != 0:
        raise AssertionError("Parent 010 provider calls must be zero.")
    if parent_010.get("network_calls") != 0:
        raise AssertionError("Parent 010 network calls must be zero.")
    if parent_010.get("failures") != []:
        raise AssertionError("Parent 010 failures must be empty.")

    if parent_011.get("decision") != "HOLD_ONE_FIXTURE_RETRY":
        raise AssertionError("Parent 011 must remain HOLD.")
    if parent_011.get("stop_condition") != "provider_call_failed:ImageGenerationProviderError":
        raise AssertionError("Parent 011 stop condition mismatch.")
    if parent_011.get("actual_provider_http_requests") != 1:
        raise AssertionError("Parent 011 request count mismatch.")
    if parent_011.get("retry_count") != 0:
        raise AssertionError("Parent 011 retry count mismatch.")
    if parent_011.get("fixtures") != []:
        raise AssertionError("Parent 011 must have no completed fixtures.")

    if manifest.get("manifest_id") != "crop-only-track-b-provider-failure-triage-design-012":
        raise AssertionError("Unexpected manifest id.")
    if manifest.get("status") != "provider_failure_triage_design_not_approved_for_provider_execution":
        raise AssertionError("Manifest status must remain not approved.")
    if manifest.get("baseline_commit") != "805f97c2e24c542c7edd5b631a6356b7f9b7eb2a":
        raise AssertionError("Baseline mismatch.")
    if manifest.get("decision") != "REQUEST_SHAPE_BLOCKED_PENDING_ZERO_CALL_COMPATIBILITY_MATRIX":
        raise AssertionError("Unexpected decision.")
    if "Repeated provider failure" not in manifest.get("repeated_failure_conclusion", ""):
        raise AssertionError("Manifest must record repeated failure conclusion.")

    for key in [
        "provider_openai_calls_allowed",
        "controlled_provider_execution_allowed",
        "future_provider_retry_allowed",
        "same_shape_provider_retry_allowed",
        "staging_prod_env_allowed",
        "runtime_bot_admin_user_facing_allowed",
        "user_facing_rollout_allowed",
        "real_user_photos_allowed",
        "imports_sql_direct_db_writes_allowed",
        "secret_or_raw_payload_exposure_allowed",
    ]:
        _assert_false(manifest, key)

    blocked_shape = manifest.get("blocked_request_shape")
    if not isinstance(blocked_shape, dict):
        raise AssertionError("Missing blocked request shape.")
    if blocked_shape.get("input_scope") != "crop_source + crop_mask + fabric_reference only":
        raise AssertionError("Blocked input scope mismatch.")
    if blocked_shape.get("full_scene_person_input_used") is not False:
        raise AssertionError("Blocked shape must forbid full-scene person input.")

    next_gate = manifest.get("next_gate")
    if not isinstance(next_gate, dict):
        raise AssertionError("Missing next gate.")
    if next_gate.get("type") != "zero_call_request_shape_compatibility_matrix":
        raise AssertionError("Next gate must be zero-call matrix.")
    if next_gate.get("provider_calls_allowed") is not False:
        raise AssertionError("Next gate must not allow provider calls.")
    if next_gate.get("call_count") != 0:
        raise AssertionError("Next gate call count must be zero.")
    for field in [
        "sanitized_request_shape",
        "full_scene_person_input_absent",
        "mask_used",
        "expected_preservation_risk",
        "visual_fidelity_risk",
        "future_provider_call_cap_if_selected",
        "fresh_go_required_before_execution",
    ]:
        if field not in next_gate.get("required_fields", []):
            raise AssertionError(f"Next gate missing field: {field}")

    variants = manifest.get("request_shape_variants_to_compare_zero_call")
    if not isinstance(variants, list) or len(variants) < 5:
        raise AssertionError("Expected at least five zero-call variants.")
    for variant in variants:
        if variant.get("provider_calls_now") != 0:
            raise AssertionError("All variants must remain zero-call now.")
        if variant.get("future_provider_call_cap_if_selected") != 1:
            raise AssertionError("Future variant call cap must be 1.")

    parent_evidence = manifest.get("parent_evidence")
    if not isinstance(parent_evidence, list) or len(parent_evidence) != 3:
        raise AssertionError("Manifest must record three parent evidence entries.")

    normalized_design = " ".join(design.split())
    required_text = [
        "Status: `PROVIDER_FAILURE_TRIAGE_DESIGN / NOT APPROVED FOR PROVIDER EXECUTION`",
        "The current crop-only Track B request shape is blocked.",
        "Do not spend more provider calls on the same request shape",
        "Provider/OpenAI calls: `BLOCKED`",
        "Create a zero-call request-shape compatibility matrix before any new provider call.",
        "This design does not approve provider/OpenAI execution.",
    ]
    missing = [phrase for phrase in required_text if phrase not in normalized_design]
    if missing:
        raise AssertionError(f"Design doc missing required text: {', '.join(missing)}")

    _reject_risky_text(DESIGN_MD, design)
    _reject_risky_text(MANIFEST_JSON, json.dumps(manifest, ensure_ascii=False, sort_keys=True))


def main() -> int:
    try:
        validate()
    except AssertionError as exc:
        print(f"validation failed: {exc}", file=sys.stderr)
        return 1
    print("crop-only Track B provider-failure triage design validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
