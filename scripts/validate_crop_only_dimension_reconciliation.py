#!/usr/bin/env python3
"""Validate crop-only dimension reconciliation offline rehearsal."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[1]
REPORT_JSON = REPO_ROOT / "docs" / "experiments" / "reports" / "crop_only_dimension_reconciliation_001.json"
REPORT_MD = REPO_ROOT / "docs" / "experiments" / "reports" / "crop_only_dimension_reconciliation_001.md"
EXPECTED_FIXTURE_IDS = ["pm001-solid-frontal", "pm001-pattern-boundary"]

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


def _safe_repo_path(reference: str) -> Path:
    path = Path(reference)
    if path.is_absolute() or ".." in path.parts:
        raise AssertionError(f"Artifact path must be repo-relative and safe: {reference}")
    return REPO_ROOT / path


def _validate_png(reference: str, expected_size: tuple[int, int] | None = None) -> tuple[int, int]:
    path = _safe_repo_path(reference)
    if not path.is_file():
        raise AssertionError(f"Referenced PNG does not exist: {reference}")
    if path.suffix.lower() != ".png":
        raise AssertionError(f"Referenced artifact must be PNG: {reference}")
    with Image.open(path) as image:
        if image.format != "PNG":
            raise AssertionError(f"Referenced artifact is not PNG: {reference}")
        if expected_size is not None and image.size != expected_size:
            raise AssertionError(f"{reference} has size {image.size}, expected {expected_size}")
        return image.size


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


def _validate_fixture(entry: dict[str, Any], expected_id: str) -> None:
    if entry.get("fixture_id") != expected_id:
        raise AssertionError(f"Expected fixture {expected_id}, got {entry.get('fixture_id')}")
    if entry.get("strategy") != "center_crop_to_crop_aspect_then_resize":
        raise AssertionError(f"{expected_id} unexpected reconciliation strategy.")
    if entry.get("pass_fail") != "pass":
        raise AssertionError(f"{expected_id} must pass offline preservation.")
    if entry.get("protected_region_drift") is not False:
        raise AssertionError(f"{expected_id} must not have protected-region drift.")

    oversized = entry.get("oversized_provider_output_dimensions")
    if oversized != {"width": 1024, "height": 1536}:
        raise AssertionError(f"{expected_id} oversized dimensions must be 1024x1536.")

    reconciled = entry.get("reconciled_crop_dimensions")
    crop_source = entry.get("crop_source_dimensions")
    if not isinstance(reconciled, dict) or not isinstance(crop_source, dict):
        raise AssertionError(f"{expected_id} missing dimensions.")
    expected_crop_size = (crop_source["width"], crop_source["height"])
    if (reconciled["width"], reconciled["height"]) != expected_crop_size:
        raise AssertionError(f"{expected_id} reconciled crop must match crop source dimensions.")

    _validate_png(entry["fake_oversized_provider_output"], expected_size=(1024, 1536))
    _validate_png(entry["reconciled_crop"], expected_size=expected_crop_size)
    _validate_png(entry["composite_output"])

    if float(entry.get("mean_delta_protected_region", 100.0)) > 1.0:
        raise AssertionError(f"{expected_id} mean delta exceeds threshold.")
    if float(entry.get("changed_pixel_percent_protected_region", 100.0)) > 1.0:
        raise AssertionError(f"{expected_id} changed protected pixels exceed threshold.")


def validate() -> None:
    payload = _read_json(REPORT_JSON)
    markdown = REPORT_MD.read_text(encoding="utf-8")

    if payload.get("rehearsal_id") != "crop-only-dimension-reconciliation-001":
        raise AssertionError("Unexpected rehearsal_id.")
    if payload.get("status") != "offline_rehearsal_passed":
        raise AssertionError("Dimension reconciliation rehearsal must pass offline.")
    if payload.get("strategy") != "center_crop_to_crop_aspect_then_resize":
        raise AssertionError("Unexpected strategy.")
    if payload.get("provider_openai_called") is not False:
        raise AssertionError("provider_openai_called must be false.")
    if payload.get("provider_retry_authorized") is not False:
        raise AssertionError("provider_retry_authorized must be false.")
    if payload.get("runtime_behavior_changed") is not False:
        raise AssertionError("runtime_behavior_changed must be false.")
    if payload.get("user_facing_rollout_approved") is not False:
        raise AssertionError("user_facing_rollout_approved must be false.")
    if payload.get("decision") != "READY_FOR_RETRY_PACKET_DESIGN_ONLY":
        raise AssertionError("Decision must remain design-only.")

    fixtures = payload.get("fixtures")
    if not isinstance(fixtures, list) or len(fixtures) != 2:
        raise AssertionError("Report must contain exactly 2 fixtures.")
    for entry, expected_id in zip(fixtures, EXPECTED_FIXTURE_IDS, strict=True):
        if not isinstance(entry, dict):
            raise AssertionError("Fixture entry must be an object.")
        _validate_fixture(entry, expected_id)

    required_markdown = [
        "It does not call OpenAI/provider.",
        "It does not approve provider retry.",
        "It does not approve user-facing rollout.",
        "Decision: `READY_FOR_RETRY_PACKET_DESIGN_ONLY`",
        "A future provider retry still requires a new explicit approval packet.",
    ]
    missing = [phrase for phrase in required_markdown if phrase not in markdown]
    if missing:
        raise AssertionError(f"Markdown report missing required text: {', '.join(missing)}")

    _reject_risky_text(REPORT_JSON, json.dumps(payload, ensure_ascii=False, sort_keys=True))
    _reject_risky_text(REPORT_MD, markdown)


def main() -> int:
    try:
        validate()
    except AssertionError as exc:
        print(f"validation failed: {exc}", file=sys.stderr)
        return 1
    print("crop-only dimension reconciliation validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
