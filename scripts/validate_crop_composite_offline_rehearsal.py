#!/usr/bin/env python3
"""Validate crop/composite offline rehearsal reports and artifacts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[1]
REPORT_JSON = REPO_ROOT / "docs" / "experiments" / "reports" / "crop_composite_offline_rehearsal_001.json"
REPORT_MD = REPO_ROOT / "docs" / "experiments" / "reports" / "crop_composite_offline_rehearsal_001.md"
EXPECTED_FIXTURE_IDS = ["pm001-solid-frontal", "pm001-pattern-boundary"]
MAX_CHANGED_PIXEL_PERCENT = 1.0

SECRET_PATTERNS = [
    re.compile(r"sk-(?:proj|svcacct|admin|org)-[A-Za-z0-9_-]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{40,}"),
    re.compile(r"\b(?:OPENAI_API_KEY|BOT_INTERNAL_TOKEN|TELEGRAM_BOT_TOKEN|DATABASE_URL)\s*="),
    re.compile("PRIVATE" + r"\s+KEY"),
    re.compile(r"data:image/[a-zA-Z0-9.+-]+;base64,"),
    re.compile(r"[A-Za-z0-9+/]{160,}={0,2}"),
]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate crop/composite offline rehearsal artifacts.")
    parser.add_argument("--json-report", type=Path, default=REPORT_JSON)
    parser.add_argument("--markdown-report", type=Path, default=REPORT_MD)
    return parser.parse_args(argv)


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


def _validate_png(reference: str) -> None:
    path = _safe_repo_path(reference)
    if not path.is_file():
        raise AssertionError(f"Referenced PNG does not exist: {reference}")
    if path.suffix.lower() != ".png":
        raise AssertionError(f"Referenced artifact must be PNG: {reference}")
    with Image.open(path) as image:
        if image.format != "PNG":
            raise AssertionError(f"Referenced artifact is not PNG: {reference}")


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
    crop_bounds = entry.get("crop_bounds")
    if not isinstance(crop_bounds, dict):
        raise AssertionError(f"{expected_id} missing crop_bounds.")
    for key in ["left", "top", "right", "bottom"]:
        if not isinstance(crop_bounds.get(key), int):
            raise AssertionError(f"{expected_id} crop_bounds.{key} must be an integer.")
    if crop_bounds["right"] <= crop_bounds["left"] or crop_bounds["bottom"] <= crop_bounds["top"]:
        raise AssertionError(f"{expected_id} crop bounds must have positive dimensions.")

    for field in ["source_image", "mask_image", "fabric_image", "crop_source", "crop_mask", "fake_crop_edit", "composite_output"]:
        value = entry.get(field)
        if not isinstance(value, str) or not value:
            raise AssertionError(f"{expected_id} missing artifact reference: {field}")
        _validate_png(value)

    if entry.get("pass_fail") != "pass":
        raise AssertionError(f"{expected_id} preservation must pass.")
    if entry.get("protected_region_drift") is not False:
        raise AssertionError(f"{expected_id} protected_region_drift must be false.")
    if float(entry.get("changed_pixel_percent_protected_region", 100.0)) > MAX_CHANGED_PIXEL_PERCENT:
        raise AssertionError(f"{expected_id} changed protected pixels exceed threshold.")


def validate(json_report: Path, markdown_report: Path) -> None:
    payload = _read_json(json_report)
    if not markdown_report.is_file():
        raise AssertionError(f"Missing Markdown report: {_relative(markdown_report)}")
    markdown = markdown_report.read_text(encoding="utf-8")

    if payload.get("rehearsal_id") != "crop-composite-offline-001":
        raise AssertionError("Unexpected rehearsal_id.")
    if payload.get("status") != "offline_rehearsal_passed":
        raise AssertionError("Rehearsal status must be offline_rehearsal_passed.")
    if payload.get("provider_openai_called") is not False:
        raise AssertionError("provider_openai_called must be false.")
    if payload.get("experiment_executed") is not False:
        raise AssertionError("experiment_executed must be false.")
    if payload.get("runtime_behavior_changed") is not False:
        raise AssertionError("runtime_behavior_changed must be false.")
    if payload.get("provider_calls_authorized") is not False:
        raise AssertionError("provider_calls_authorized must be false.")
    if payload.get("user_facing_rollout_approved") is not False:
        raise AssertionError("user_facing_rollout_approved must be false.")

    fixtures = payload.get("fixtures")
    if not isinstance(fixtures, list) or len(fixtures) != 2:
        raise AssertionError("Report must contain exactly 2 fixtures.")
    for entry, expected_id in zip(fixtures, EXPECTED_FIXTURE_IDS, strict=True):
        if not isinstance(entry, dict):
            raise AssertionError("Fixture entry must be an object.")
        _validate_fixture(entry, expected_id)

    if payload.get("decision") != "READY_FOR_CAPPED_PROVIDER_PACKET_DESIGN_ONLY":
        raise AssertionError("Decision must remain design-only.")

    required_markdown = [
        "This is an offline deterministic rehearsal only.",
        "It does not call OpenAI/provider.",
        "It does not approve user-facing rollout.",
        "It does not approve future provider calls.",
        "A future provider test still requires a separate capped approval gate.",
    ]
    missing = [phrase for phrase in required_markdown if phrase not in markdown]
    if missing:
        raise AssertionError(f"Markdown report missing required safety text: {', '.join(missing)}")

    _reject_risky_text(json_report, json.dumps(payload, ensure_ascii=False, sort_keys=True))
    _reject_risky_text(markdown_report, markdown)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        validate(args.json_report, args.markdown_report)
    except AssertionError as exc:
        print(f"validation failed: {exc}", file=sys.stderr)
        return 1
    print("crop/composite offline rehearsal validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
