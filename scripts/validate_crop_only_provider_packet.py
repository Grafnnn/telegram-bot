#!/usr/bin/env python3
"""Validate the crop-only provider execution packet proposal."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[1]
PACKET_MD = REPO_ROOT / "docs" / "experiments" / "crop_only_provider_execution_packet_001.md"
MANIFEST_JSON = REPO_ROOT / "docs" / "experiments" / "fixtures" / "crop_only_provider_fixture_manifest_001.json"
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


def _safe_repo_path(reference: str) -> Path:
    path = Path(reference)
    if path.is_absolute() or ".." in path.parts:
        raise AssertionError(f"Path must be safe and repo-relative: {reference}")
    return REPO_ROOT / path


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


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise AssertionError(f"Missing JSON file: {_relative(path)}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AssertionError("Manifest must be a JSON object.")
    return payload


def _validate_png(reference: str) -> tuple[int, int]:
    path = _safe_repo_path(reference)
    if not path.is_file():
        raise AssertionError(f"Referenced image is missing: {reference}")
    if path.suffix.lower() != ".png":
        raise AssertionError(f"Referenced image must be PNG: {reference}")
    with Image.open(path) as image:
        if image.format != "PNG":
            raise AssertionError(f"Referenced image is not PNG: {reference}")
        return image.size


def _validate_crop_pair(fixture: dict[str, Any]) -> None:
    fixture_id = fixture["fixture_id"]
    crop_source_size = _validate_png(fixture["crop_source"])
    crop_mask_size = _validate_png(fixture["crop_mask"])
    if crop_source_size != crop_mask_size:
        raise AssertionError(f"{fixture_id} crop source and crop mask dimensions differ.")

    full_source_size = _validate_png(fixture["source_image"])
    full_mask_size = _validate_png(fixture["full_mask_image"])
    if full_source_size != full_mask_size:
        raise AssertionError(f"{fixture_id} full source and full mask dimensions differ.")

    _validate_png(fixture["fabric_image"])
    _validate_png(fixture["offline_fake_crop_edit"])
    _validate_png(fixture["offline_composite_output"])

    bounds = fixture.get("crop_bounds")
    if not isinstance(bounds, dict):
        raise AssertionError(f"{fixture_id} missing crop bounds.")
    for key in ["left", "top", "right", "bottom"]:
        if not isinstance(bounds.get(key), int):
            raise AssertionError(f"{fixture_id} crop_bounds.{key} must be an integer.")
    if bounds["right"] <= bounds["left"] or bounds["bottom"] <= bounds["top"]:
        raise AssertionError(f"{fixture_id} crop bounds must have positive area.")

    if fixture.get("full_scene_provider_input_allowed") is not False:
        raise AssertionError(f"{fixture_id} must forbid full-scene provider input.")
    if fixture.get("expected_provider_input") != "crop_source_plus_crop_mask_plus_fabric_image":
        raise AssertionError(f"{fixture_id} must declare crop-only provider inputs.")


def validate() -> None:
    packet = PACKET_MD.read_text(encoding="utf-8")
    manifest = _read_json(MANIFEST_JSON)

    if manifest.get("experiment_id") != "crop-only-provider-001":
        raise AssertionError("Unexpected experiment_id.")
    if manifest.get("status") != "packet_proposal_only":
        raise AssertionError("Manifest status must remain proposal-only.")
    for key in [
        "provider_calls_authorized",
        "execution_approved",
        "provider_openai_called",
        "runtime_behavior_changed",
        "user_facing_rollout_approved",
    ]:
        if manifest.get(key) is not False:
            raise AssertionError(f"{key} must be false.")

    call_cap = manifest.get("call_cap")
    if not isinstance(call_cap, dict):
        raise AssertionError("Missing call_cap.")
    if call_cap.get("expected_provider_calls") != 2:
        raise AssertionError("Expected provider calls must be 2.")
    if call_cap.get("max_allowed_provider_calls") != 3:
        raise AssertionError("Max provider calls must be capped at 3.")

    fixtures = manifest.get("fixtures")
    if not isinstance(fixtures, list) or len(fixtures) != 2:
        raise AssertionError("Manifest must contain exactly 2 fixtures.")
    if [entry.get("fixture_id") for entry in fixtures] != EXPECTED_FIXTURE_IDS:
        raise AssertionError("Unexpected fixture ids or order.")
    for fixture in fixtures:
        if not isinstance(fixture, dict):
            raise AssertionError("Fixture entry must be an object.")
        _validate_crop_pair(fixture)

    required_packet_text = [
        "Status: `PROPOSAL_ONLY / NOT APPROVED FOR EXECUTION`",
        "This packet does not authorize provider/OpenAI calls.",
        "The provider must not receive the full original source image for this packet.",
        "expected_provider_calls: `2`",
        "max_allowed_provider_calls: `3`",
        "full source image selected as provider input",
        "full-scene provider path remains rejected",
        "provider/OpenAI is still NO-GO until separate approval",
    ]
    missing = [phrase for phrase in required_packet_text if phrase not in packet]
    if missing:
        raise AssertionError(f"Packet missing required safety text: {', '.join(missing)}")

    _reject_risky_text(PACKET_MD, packet)
    _reject_risky_text(MANIFEST_JSON, json.dumps(manifest, ensure_ascii=False, sort_keys=True))


def main() -> int:
    try:
        validate()
    except AssertionError as exc:
        print(f"validation failed: {exc}", file=sys.stderr)
        return 1
    print("crop-only provider packet validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
