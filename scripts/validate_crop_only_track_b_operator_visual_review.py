#!/usr/bin/env python3
"""Validate Track B operator visual review report."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
REPORT_JSON = REPO_ROOT / "docs" / "experiments" / "reports" / "crop_only_track_b_operator_visual_review_008.json"
REPORT_MD = REPO_ROOT / "docs" / "experiments" / "reports" / "crop_only_track_b_operator_visual_review_008.md"
INPUT_REPORT_JSON = REPO_ROOT / "docs" / "experiments" / "reports" / "crop_only_track_b_transport_retry_008.json"

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
    input_report = _read_json(INPUT_REPORT_JSON)
    if not REPORT_MD.is_file():
        raise AssertionError(f"Missing Markdown report: {_relative(REPORT_MD)}")
    report_md = REPORT_MD.read_text(encoding="utf-8")

    if input_report.get("decision") != "TRANSPORT_RETRY_READY_FOR_OPERATOR_REVIEW":
        raise AssertionError("Input transport retry report must be ready for operator review.")
    if input_report.get("fixture_scope") != ["pm001-solid-frontal"]:
        raise AssertionError("Input transport retry report must remain one fixture.")
    if input_report.get("provider_outputs_committed") is not False:
        raise AssertionError("Provider output binaries must not be committed.")

    if report.get("experiment_id") != "crop-only-track-b-operator-visual-review-008":
        raise AssertionError("Unexpected experiment id.")
    if report.get("baseline") != "main@293aac6508be987f7ae34c6dfa91d732b7192a58":
        raise AssertionError("Baseline mismatch.")
    if report.get("decision") != "PASS_FOR_MORE_LOCAL_CROP_ONLY_TESTING":
        raise AssertionError("Unexpected decision.")
    if report.get("fixture_id") != "pm001-solid-frontal":
        raise AssertionError("Unexpected fixture id.")
    if report.get("manual_operator_review_completed") is not True:
        raise AssertionError("Manual operator review must be completed.")
    if report.get("provider_output_binary_committed") is not False:
        raise AssertionError("Provider output binary must not be committed.")

    scores = report.get("scores")
    if not isinstance(scores, dict):
        raise AssertionError("Missing scores.")
    for key in [
        "fabric_resemblance",
        "pattern_scale_plausibility",
        "boundary_quality",
        "garment_only_localization",
        "artifact_absence",
    ]:
        value = scores.get(key)
        if not isinstance(value, int) or value < 1 or value > 5:
            raise AssertionError(f"{key} score must be an integer from 1 to 5.")
    if scores.get("overall_average") != 4.2:
        raise AssertionError("Overall average mismatch.")
    if min(scores[key] for key in scores if key != "overall_average") < 4:
        raise AssertionError("All visual dimensions must be at least 4 for this review.")

    safety = report.get("safety")
    if not isinstance(safety, dict):
        raise AssertionError("Missing safety object.")
    for key, value in safety.items():
        if value is not False:
            raise AssertionError(f"safety.{key} must be false.")

    required_md_text = [
        "Decision: `PASS_FOR_MORE_LOCAL_CROP_ONLY_TESTING`",
        "Provider crop output itself introduced a realistic torso and arms",
        "New provider/OpenAI calls: no",
        "Provider output binaries committed: no",
        "User-facing rollout approved: no",
        "does not approve broader fixture execution",
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
    print("crop-only Track B operator visual review validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
