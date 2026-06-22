#!/usr/bin/env python3
"""Validate crop-only visual-quality expansion packet proposal."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[1]
PACKET_MD = REPO_ROOT / "docs" / "experiments" / "crop_only_visual_quality_expansion_packet_003.md"
MANIFEST_JSON = (
    REPO_ROOT / "docs" / "experiments" / "fixtures" / "crop_only_visual_quality_expansion_manifest_003.json"
)
PARENT_REPORT_JSON = REPO_ROOT / "docs" / "experiments" / "reports" / "crop_only_provider_retry_002.json"
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
        raise AssertionError(f"Missing JSON file: {_relative(path)}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AssertionError(f"{_relative(path)} must contain a JSON object.")
    return payload


def _safe_repo_path(reference: str) -> Path:
    path = Path(reference)
    if path.is_absolute() or ".." in path.parts:
        raise AssertionError(f"Path must be safe and repo-relative: {reference}")
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


def _validate_concrete_fixture(entry: dict[str, Any]) -> None:
    expected_dimensions = entry.get("expected_crop_dimensions")
    if not isinstance(expected_dimensions, dict):
        raise AssertionError(f"{entry.get('fixture_id')} missing expected crop dimensions.")
    expected_size = (expected_dimensions["width"], expected_dimensions["height"])
    crop_source_size = _validate_png(entry["crop_source"])
    _validate_png(entry["crop_mask"], expected_size=crop_source_size)
    _validate_png(entry["fabric_reference"])
    _validate_png(entry["source_image"])
    _validate_png(entry["full_mask"])
    if crop_source_size != expected_size:
        raise AssertionError(f"{entry.get('fixture_id')} expected dimensions must match crop source.")


def validate() -> None:
    packet = PACKET_MD.read_text(encoding="utf-8")
    manifest = _read_json(MANIFEST_JSON)
    parent_report = _read_json(PARENT_REPORT_JSON)

    if parent_report.get("decision") != "GO_FOR_MORE_CROP_ONLY_TESTING":
        raise AssertionError("Parent crop-only retry evidence must be positive technical evidence.")
    if parent_report.get("user_facing_rollout_approved") is not False:
        raise AssertionError("Parent evidence must not approve rollout.")

    if manifest.get("manifest_id") != "crop-only-visual-quality-expansion-003":
        raise AssertionError("Unexpected manifest id.")
    if manifest.get("status") != "proposal_only_not_approved_for_execution":
        raise AssertionError("Manifest must remain proposal-only.")
    for key in [
        "provider_openai_calls_allowed",
        "user_facing_rollout_allowed",
        "runtime_enablement_allowed",
        "staging_prod_env_allowed",
    ]:
        if manifest.get(key) is not False:
            raise AssertionError(f"{key} must be false.")
    if manifest.get("expected_provider_generations") != 4:
        raise AssertionError("Expected provider generations must be 4.")
    if manifest.get("max_total_http_requests") != 5:
        raise AssertionError("Max total HTTP requests must be 5.")

    strategy = manifest.get("dimension_strategy")
    if not isinstance(strategy, dict):
        raise AssertionError("Missing dimension strategy.")
    if strategy.get("name") != "center_crop_to_crop_aspect_then_resize":
        raise AssertionError("Unexpected dimension strategy.")
    if strategy.get("implicit_resize_allowed") is not False:
        raise AssertionError("Implicit resize must remain forbidden.")

    visual = manifest.get("visual_quality_thresholds")
    if not isinstance(visual, dict):
        raise AssertionError("Missing visual quality thresholds.")
    if visual.get("minimum_average_score") != 4.0:
        raise AssertionError("Visual average threshold must be 4.0.")
    if visual.get("minimum_dimension_score") != 4:
        raise AssertionError("Minimum dimension score must be 4.")
    if visual.get("rollout_approval_from_this_packet") is not False:
        raise AssertionError("This packet must not approve rollout.")

    fixtures = manifest.get("fixtures")
    if not isinstance(fixtures, list) or [entry.get("fixture_id") for entry in fixtures] != EXPECTED_FIXTURE_IDS:
        raise AssertionError("Unexpected fixture ids or order.")
    for entry in fixtures[:2]:
        _validate_concrete_fixture(entry)
    for entry in fixtures[2:]:
        for key in ["source_image", "full_mask", "crop_source", "crop_mask", "fabric_reference"]:
            if not str(entry.get(key, "")).startswith("TBD_SYNTHETIC_"):
                raise AssertionError(f"{entry.get('fixture_id')} must remain explicitly TBD before execution.")
        if entry.get("crop_bounds") != "TBD" or entry.get("expected_crop_dimensions") != "TBD":
            raise AssertionError(f"{entry.get('fixture_id')} bounds/dimensions must remain TBD before execution.")

    required_packet_text = [
        "Status: `PROPOSAL_ONLY / NOT APPROVED FOR EXECUTION`",
        "Provider/OpenAI calls: `BLOCKED`",
        "Runtime/staging/prod/env changes: `BLOCKED`",
        "User-facing rollout: `BLOCKED`",
        "Any provider/OpenAI call without a fresh explicit GO is forbidden.",
        "Before any execution, create or validate the two missing synthetic fixture",
    ]
    missing = [phrase for phrase in required_packet_text if phrase not in packet]
    if missing:
        raise AssertionError(f"Packet missing required text: {', '.join(missing)}")

    _reject_risky_text(PACKET_MD, packet)
    _reject_risky_text(MANIFEST_JSON, json.dumps(manifest, ensure_ascii=False, sort_keys=True))


def main() -> int:
    try:
        validate()
    except AssertionError as exc:
        print(f"validation failed: {exc}", file=sys.stderr)
        return 1
    print("crop-only visual quality expansion packet validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
