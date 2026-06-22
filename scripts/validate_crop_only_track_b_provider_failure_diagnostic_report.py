#!/usr/bin/env python3
"""Validate Track B provider-failure diagnostic report."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
REPORT_JSON = (
    REPO_ROOT / "docs" / "experiments" / "reports" / "crop_only_track_b_provider_failure_diagnostic_010.json"
)
REPORT_MD = (
    REPO_ROOT / "docs" / "experiments" / "reports" / "crop_only_track_b_provider_failure_diagnostic_010.md"
)
PACKET_JSON = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "fixtures"
    / "crop_only_track_b_provider_failure_diagnostic_packet_010.json"
)

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


def validate() -> None:
    report = _read_json(REPORT_JSON)
    packet = _read_json(PACKET_JSON)
    if not REPORT_MD.is_file():
        raise AssertionError(f"Missing Markdown report: {_relative(REPORT_MD)}")
    report_md = REPORT_MD.read_text(encoding="utf-8")

    if report.get("experiment_id") != "crop-only-track-b-provider-failure-diagnostic-010":
        raise AssertionError("Unexpected experiment id.")
    if report.get("baseline") != "main@b825d06a32b8301de2e462690f83265a89b4494e":
        raise AssertionError("Baseline mismatch.")
    if report.get("decision") != "READY_FOR_ONE_FIXTURE_RETRY_PACKET_DESIGN":
        raise AssertionError("Unexpected decision.")
    if report.get("provider_openai_calls") != 0:
        raise AssertionError("Provider/OpenAI calls must be zero.")
    if report.get("network_calls") != 0:
        raise AssertionError("Network calls must be zero.")
    if report.get("diagnostic_provider_calls_allowed") is not False:
        raise AssertionError("Diagnostic provider calls must be disallowed.")
    if report.get("diagnostic_network_calls_allowed") is not False:
        raise AssertionError("Diagnostic network calls must be disallowed.")
    if report.get("failures") != []:
        raise AssertionError("Diagnostic failures must be empty.")
    if report.get("parent_stop_condition") != "provider_call_failed:ImageGenerationProviderError":
        raise AssertionError("Parent stop condition mismatch.")

    checks = report.get("checks")
    if not isinstance(checks, dict):
        raise AssertionError("Missing checks.")
    for check in packet.get("required_zero_call_checks", []):
        if checks.get(check) is not True:
            raise AssertionError(f"Missing or failed zero-call check: {check}")

    fixtures = report.get("fixtures")
    if not isinstance(fixtures, list):
        raise AssertionError("Missing fixtures.")
    if [fixture.get("fixture_id") for fixture in fixtures] != packet.get("diagnostic_fixture_ids"):
        raise AssertionError("Diagnostic fixture scope mismatch.")
    for fixture in fixtures:
        if fixture.get("crop_source_mask_dimensions_match") is not True:
            raise AssertionError("Crop source/mask dimensions must match.")
        mask = fixture.get("crop_mask")
        if not isinstance(mask, dict):
            raise AssertionError("Missing mask info.")
        if mask.get("has_alpha") is not True:
            raise AssertionError("Mask must have alpha.")
        if mask.get("has_editable_region") is not True:
            raise AssertionError("Mask must have editable region.")
        if mask.get("has_protected_region") is not True:
            raise AssertionError("Mask must have protected region.")
        request_shape = fixture.get("request_shape")
        if not isinstance(request_shape, dict):
            raise AssertionError("Missing request shape.")
        for key in ["full_scene_provider_input_included", "raw_payload_included", "base64_included", "secret_included"]:
            if request_shape.get(key) is not False:
                raise AssertionError(f"request_shape.{key} must be false.")

    if report.get("future_retry_candidate") != packet.get("future_retry_candidate_after_separate_go"):
        raise AssertionError("Future retry candidate must match packet.")

    safety = report.get("safety")
    if not isinstance(safety, dict):
        raise AssertionError("Missing safety object.")
    for key, value in safety.items():
        if value is not False:
            raise AssertionError(f"safety.{key} must be false.")

    normalized_md = " ".join(report_md.split())
    required_md_text = [
        "Decision: `READY_FOR_ONE_FIXTURE_RETRY_PACKET_DESIGN`",
        "Provider/OpenAI calls | 0",
        "Network calls | 0",
        "The diagnostic did not reproduce a local fixture/input-shape failure.",
        "That retry still requires a separate fresh explicit GO.",
        "This report does not authorize provider/OpenAI execution.",
    ]
    missing = [phrase for phrase in required_md_text if phrase not in normalized_md]
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
    print("crop-only Track B provider-failure diagnostic report validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
