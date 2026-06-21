#!/usr/bin/env python3
"""Validate crop-only provider readiness artifacts without provider calls."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[1]
READINESS_MD = REPO_ROOT / "docs" / "experiments" / "crop_only_provider_readiness_001.md"
FROZEN_INPUTS_JSON = (
    REPO_ROOT / "docs" / "experiments" / "fixtures" / "crop_only_provider_frozen_inputs_001.json"
)
PACKET_MD = REPO_ROOT / "docs" / "experiments" / "crop_only_provider_execution_packet_001.md"
EXPECTED_FIXTURE_IDS = ["pm001-solid-frontal", "pm001-pattern-boundary"]
OPTIONAL_VALIDATORS = [
    REPO_ROOT / "scripts" / "validate_provider_mask_no_go_decision.py",
    REPO_ROOT / "scripts" / "validate_crop_composite_offline_rehearsal.py",
]

SECRET_PATTERNS = [
    re.compile(r"sk-(?:proj|svcacct|admin|org)-[A-Za-z0-9_-]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{40,}"),
    re.compile(r"\b(?:OPENAI_API_KEY|BOT_INTERNAL_TOKEN|TELEGRAM_BOT_TOKEN|DATABASE_URL)\s*="),
    re.compile("PRIVATE" + r"\s+KEY"),
    re.compile(r"data:image/[a-zA-Z0-9.+-]+;base64,"),
    re.compile(r"[A-Za-z0-9+/]{160,}={0,2}"),
]
FORBIDDEN_MANIFEST_SUBSTRINGS = ["/Users/", "/tmp/", "/private/", "data:image", "base64"]


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
        raise AssertionError("JSON payload must be an object.")
    return payload


def _validate_png(reference: str) -> tuple[int, int]:
    path = _safe_repo_path(reference)
    if not path.is_file():
        raise AssertionError(f"Referenced PNG does not exist: {reference}")
    if path.suffix.lower() != ".png":
        raise AssertionError(f"Referenced file must be PNG: {reference}")
    with Image.open(path) as image:
        if image.format != "PNG":
            raise AssertionError(f"Referenced file is not PNG: {reference}")
        return image.size


def _validate_fixture(entry: dict[str, Any], expected_id: str) -> None:
    if entry.get("fixture_id") != expected_id:
        raise AssertionError(f"Expected fixture {expected_id}, got {entry.get('fixture_id')}")
    for field in ["source_image", "full_mask", "crop_source", "crop_mask", "fabric_reference"]:
        value = entry.get(field)
        if not isinstance(value, str) or not value:
            raise AssertionError(f"{expected_id} missing {field}.")
        _validate_png(value)
        for forbidden in FORBIDDEN_MANIFEST_SUBSTRINGS:
            if forbidden in value:
                raise AssertionError(f"{expected_id} {field} contains forbidden text: {forbidden}")

    source_size = _validate_png(entry["source_image"])
    full_mask_size = _validate_png(entry["full_mask"])
    crop_source_size = _validate_png(entry["crop_source"])
    crop_mask_size = _validate_png(entry["crop_mask"])
    if source_size != full_mask_size:
        raise AssertionError(f"{expected_id} source and full mask dimensions differ.")
    if crop_source_size != crop_mask_size:
        raise AssertionError(f"{expected_id} crop source and crop mask dimensions differ.")

    bounds = entry.get("crop_bounds")
    if not isinstance(bounds, dict):
        raise AssertionError(f"{expected_id} missing crop bounds.")
    for key in ["left", "top", "right", "bottom"]:
        if not isinstance(bounds.get(key), int):
            raise AssertionError(f"{expected_id} crop_bounds.{key} must be an integer.")
    if bounds["right"] <= bounds["left"] or bounds["bottom"] <= bounds["top"]:
        raise AssertionError(f"{expected_id} crop bounds must have positive area.")

    if entry.get("expected_provider_input") != "crop_source + crop_mask + fabric_reference only":
        raise AssertionError(f"{expected_id} expected_provider_input must be crop-only.")
    if entry.get("expected_composite_step") != "local composite back into source":
        raise AssertionError(f"{expected_id} expected_composite_step mismatch.")
    if entry.get("expected_preservation_check") != "full-image protected-region preservation after composite":
        raise AssertionError(f"{expected_id} expected_preservation_check mismatch.")
    if "No real user photo." not in entry.get("notes", ""):
        raise AssertionError(f"{expected_id} must explicitly reject real user photos.")


def _run_optional_validator(path: Path) -> None:
    if not path.is_file():
        return
    result = subprocess.run([sys.executable, str(path)], check=False, text=True, capture_output=True)
    if result.returncode != 0:
        raise AssertionError(f"{_relative(path)} failed: {result.stderr or result.stdout}")


def validate() -> None:
    if not READINESS_MD.is_file():
        raise AssertionError(f"Missing readiness doc: {_relative(READINESS_MD)}")
    if not PACKET_MD.is_file():
        raise AssertionError(f"Missing crop-only packet: {_relative(PACKET_MD)}")
    manifest = _read_json(FROZEN_INPUTS_JSON)
    readiness = READINESS_MD.read_text(encoding="utf-8")
    packet = PACKET_MD.read_text(encoding="utf-8")

    required_readiness_text = [
        "Status: READYNESS REVIEW ONLY / NOT APPROVED FOR EXECUTION",
        "Issue: #64",
        "Issue #64 is the approval gate, but this document does not itself approve execution.",
        "Execution approval: NOT APPROVED",
        "Provider/OpenAI calls: BLOCKED",
        "User-facing rollout: NOT APPROVED",
        "Runtime enablement: NOT APPROVED",
        "Provider candidate: OpenAI",
        "Model candidate: `gpt-image-1`",
        "Endpoint candidate: `/v1/images/edits`",
        "Expected calls: 2",
        "Maximum calls: 3",
        "Any call without explicit Issue #64 GO: forbidden",
    ]
    missing = [phrase for phrase in required_readiness_text if phrase not in readiness]
    if missing:
        raise AssertionError(f"Readiness doc missing required text: {', '.join(missing)}")

    if "crop_only_provider_readiness_001.md" not in packet:
        raise AssertionError("Crop-only packet must link to readiness doc.")
    if "crop_only_provider_frozen_inputs_001.json" not in packet:
        raise AssertionError("Crop-only packet must link to frozen inputs manifest.")

    if manifest.get("manifest_id") != "crop-only-provider-frozen-inputs-001":
        raise AssertionError("Unexpected manifest_id.")
    if manifest.get("status") != "readiness_only_not_approved_for_execution":
        raise AssertionError("Unexpected readiness manifest status.")
    if manifest.get("issue_gate") != 64:
        raise AssertionError("Issue gate must be 64.")
    if manifest.get("provider_openai_calls_allowed") is not False:
        raise AssertionError("provider_openai_calls_allowed must be false.")
    if manifest.get("user_facing_rollout_allowed") is not False:
        raise AssertionError("user_facing_rollout_allowed must be false.")
    if manifest.get("runtime_enablement_allowed") is not False:
        raise AssertionError("runtime_enablement_allowed must be false.")
    if manifest.get("expected_provider_calls") != 2:
        raise AssertionError("Expected future provider calls must be 2.")
    if manifest.get("max_provider_calls") != 3:
        raise AssertionError("Max future provider calls must be 3.")

    provider = manifest.get("provider_candidate")
    if not isinstance(provider, dict):
        raise AssertionError("Missing provider candidate block.")
    if provider.get("provider") != "OpenAI":
        raise AssertionError("Provider candidate must be OpenAI.")
    if provider.get("model") != "gpt-image-1":
        raise AssertionError("Model candidate must be gpt-image-1.")
    if provider.get("endpoint") != "/v1/images/edits":
        raise AssertionError("Endpoint candidate must be /v1/images/edits.")
    if provider.get("full_scene_person_input_allowed") is not False:
        raise AssertionError("Full-scene provider input must remain forbidden.")

    fixtures = manifest.get("fixtures")
    if not isinstance(fixtures, list) or len(fixtures) != 2:
        raise AssertionError("Frozen input manifest must contain exactly 2 fixtures.")
    if [entry.get("fixture_id") for entry in fixtures] != EXPECTED_FIXTURE_IDS:
        raise AssertionError("Unexpected frozen fixture ids or order.")
    for entry, expected_id in zip(fixtures, EXPECTED_FIXTURE_IDS, strict=True):
        if not isinstance(entry, dict):
            raise AssertionError("Fixture entry must be an object.")
        _validate_fixture(entry, expected_id)

    manifest_text = json.dumps(manifest, ensure_ascii=False, sort_keys=True)
    for forbidden in FORBIDDEN_MANIFEST_SUBSTRINGS:
        if forbidden in manifest_text:
            raise AssertionError(f"Frozen input manifest contains forbidden text: {forbidden}")

    _reject_risky_text(READINESS_MD, readiness)
    _reject_risky_text(FROZEN_INPUTS_JSON, manifest_text)
    _reject_risky_text(PACKET_MD, packet)

    for validator in OPTIONAL_VALIDATORS:
        _run_optional_validator(validator)


def main() -> int:
    try:
        validate()
    except AssertionError as exc:
        print(f"validation failed: {exc}", file=sys.stderr)
        return 1
    print("crop-only provider readiness validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
