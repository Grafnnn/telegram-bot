#!/usr/bin/env python3
"""Validate crop-only provider output dimension strategy docs."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
REPORT_JSON = REPO_ROOT / "docs" / "experiments" / "reports" / "crop_only_provider_execution_001.json"
REPORT_MD = REPO_ROOT / "docs" / "experiments" / "reports" / "crop_only_provider_execution_001.md"
STRATEGY_MD = REPO_ROOT / "docs" / "experiments" / "crop_only_output_dimension_strategy_001.md"

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
        raise AssertionError("JSON report must contain an object.")
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
    payload = _read_json(REPORT_JSON)
    report_md = REPORT_MD.read_text(encoding="utf-8")
    strategy_md = STRATEGY_MD.read_text(encoding="utf-8")

    if payload.get("decision") != "HOLD_PROVIDER_OUTPUT_SIZE_MISMATCH":
        raise AssertionError("Execution report must remain HOLD on output size mismatch.")
    if payload.get("actual_provider_calls") != 1:
        raise AssertionError("Execution report must record exactly one provider call.")
    if payload.get("stopped_before_second_fixture") is not True:
        raise AssertionError("Execution report must record that the second fixture was skipped.")
    if payload.get("user_facing_rollout_approved") is not False:
        raise AssertionError("User-facing rollout must remain unapproved.")
    if payload.get("raw_provider_payloads_committed") is not False:
        raise AssertionError("Raw provider payloads must not be committed.")
    if payload.get("provider_output_images_committed") is not False:
        raise AssertionError("Provider output images must not be committed.")

    fixtures = payload.get("fixtures")
    if not isinstance(fixtures, list) or len(fixtures) != 2:
        raise AssertionError("Execution report must contain two fixture entries.")
    first, second = fixtures
    if first.get("fixture_id") != "pm001-solid-frontal":
        raise AssertionError("First fixture must be pm001-solid-frontal.")
    if first.get("provider_call_attempted") is not True:
        raise AssertionError("First fixture must record a provider call.")
    if first.get("provider_output_dimensions") != {"width": 1024, "height": 1536}:
        raise AssertionError("First fixture provider dimensions must be recorded.")
    if first.get("expected_crop_dimensions") != {"width": 57, "height": 105}:
        raise AssertionError("First fixture expected crop dimensions must be recorded.")
    if first.get("composite_created") is not False:
        raise AssertionError("Composite must not be created for size mismatch.")
    if second.get("fixture_id") != "pm001-pattern-boundary":
        raise AssertionError("Second fixture must be pm001-pattern-boundary.")
    if second.get("provider_call_attempted") is not False:
        raise AssertionError("Second fixture must not be called after stop condition.")

    required_report_text = [
        "Status: `HOLD_PROVIDER_OUTPUT_SIZE_MISMATCH`",
        "Actual provider calls | 1",
        "User-facing rollout approved: no",
        "Do not continue this execution packet as-is.",
    ]
    missing_report = [phrase for phrase in required_report_text if phrase not in report_md]
    if missing_report:
        raise AssertionError(f"Markdown report missing required text: {', '.join(missing_report)}")

    required_strategy_text = [
        "Status: STRATEGY GATE / NOT APPROVED FOR RETRY",
        "It does not approve another provider/OpenAI call.",
        "First add an offline-only rehearsal for dimension reconciliation",
        "No implicit resize happens inside execution code.",
        "This strategy document does not approve:",
    ]
    missing_strategy = [phrase for phrase in required_strategy_text if phrase not in strategy_md]
    if missing_strategy:
        raise AssertionError(f"Strategy doc missing required text: {', '.join(missing_strategy)}")

    _reject_risky_text(REPORT_JSON, json.dumps(payload, ensure_ascii=False, sort_keys=True))
    _reject_risky_text(REPORT_MD, report_md)
    _reject_risky_text(STRATEGY_MD, strategy_md)


def main() -> int:
    try:
        validate()
    except AssertionError as exc:
        print(f"validation failed: {exc}", file=sys.stderr)
        return 1
    print("crop-only dimension strategy validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
