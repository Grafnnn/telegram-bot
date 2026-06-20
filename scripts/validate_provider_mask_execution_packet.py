#!/usr/bin/env python3
"""Validate the provider/mask execution packet.

The validator is offline-only. It checks that packet 001 is either still a
draft approval packet or has a safely documented executed NO-GO result, that
the fixture manifest is synthetic-only metadata, and that the packet does not
contain obvious secrets or raw image payloads.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
PACKET_PATH = REPO_ROOT / "docs" / "experiments" / "provider_mask_execution_packet_001.md"
MANIFEST_PATH = (
    REPO_ROOT / "docs" / "experiments" / "fixtures" / "provider_mask_fixture_manifest_001.json"
)

PACKET_SECTIONS = [
    "## Status",
    "## Metadata",
    "## Scope",
    "## Non-Goals",
    "## Baseline",
    "## Provider Candidate",
    "## Model / Endpoint Candidate",
    "## Mask Strategy",
    "## Fixture Pack",
    "## Call Cap",
    "## Cost / Risk",
    "## Safety Checklist",
    "## Pre-Execution Checks",
    "## Future Execution Commands",
    "## Required Artifacts",
    "## Preservation Review",
    "## Visual Quality Review",
    "## Stop Conditions",
    "## Artifact / Logging Policy",
    "## Rollback / Cleanup",
    "## Approval",
    "## Final Decision",
]

REQUIRED_DRAFT_PACKET_PHRASES = [
    "Status: DRAFT / NOT APPROVED FOR EXECUTION",
    "This packet does not authorize provider/OpenAI calls.",
    "This packet does not authorize experiment execution.",
    "This packet does not authorize provider strategy selection.",
    "This packet does not authorize user-facing rollout.",
    "A separate explicit approval is required before any provider call.",
    "execution_allowed_now: no",
    "Expected provider calls: 2",
    "Maximum allowed provider calls: 3",
    "Execution approval: NOT APPROVED",
    "Until this section is completed and approved, this packet is documentation only.",
    "No-mask prompt-only mode is not allowed for this experiment.",
]

REQUIRED_EXECUTED_NO_GO_PACKET_PHRASES = [
    "Status: EXECUTED / NO-GO FOR USER-FACING ROLLOUT",
    "This packet was executed once after explicit approval in Issue #56.",
    "This result does not authorize provider strategy selection.",
    "This result does not authorize user-facing rollout.",
    "This result does not authorize additional provider/OpenAI calls.",
    "Execution status: executed",
    "Approval status: approved once for Issue #56 execution only",
    "Execution result: NO-GO for user-facing rollout",
    "Expected provider calls: 2",
    "Maximum allowed provider calls: 3",
    "No-mask prompt-only mode is not allowed for this experiment.",
]

FIXTURE_FIELDS = {
    "fixture_id",
    "source_image_type",
    "source_image_reference",
    "mask_reference",
    "fabric_reference",
    "fake_output_reference",
    "fabric_category",
    "pose_garment_category",
    "expected_edit_region",
    "protected_regions",
    "input_class",
    "allowed_target",
    "reviewer",
    "notes",
}

SECRET_PATTERNS = [
    re.compile(r"sk-(?:proj|svcacct|admin|org)-[A-Za-z0-9_-]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{40,}"),
    re.compile(r"OPENAI_API_KEY\s*="),
    re.compile(r"BOT_TOKEN\s*="),
    re.compile(r"TELEGRAM_BOT_TOKEN\s*="),
    re.compile(r"PRIVATE KEY"),
    re.compile(r"data:image/[a-zA-Z0-9.+-]+;base64,"),
    re.compile(r"[A-Za-z0-9+/]{120,}={0,2}"),
]

POLICY_REFERENCE_MARKERS = (
    "no base64",
    "base64 image",
    "base64/raw",
    "raw/base64",
    "forbidden",
    "not allowed",
    "disallowed",
    "exposed",
    "payload",
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate provider/mask execution packet proposal.")
    parser.add_argument("--packet", type=Path, default=PACKET_PATH, help="Packet markdown path.")
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH, help="Fixture manifest JSON path.")
    return parser.parse_args(argv)


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _read_text(path: Path) -> str:
    if not path.is_file():
        raise AssertionError(f"Missing required file: {_relative(path)}")
    return path.read_text(encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise AssertionError(f"Missing required file: {_relative(path)}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AssertionError(f"{_relative(path)} must contain a JSON object.")
    return payload


def _require_sections(text: str, sections: list[str], *, path: Path) -> None:
    missing = [section for section in sections if section not in text]
    if missing:
        raise AssertionError(f"{_relative(path)} is missing sections: {', '.join(missing)}")


def _require_phrases(text: str, phrases: list[str], *, path: Path) -> None:
    normalized_text = " ".join(text.split())
    missing = [phrase for phrase in phrases if " ".join(phrase.split()) not in normalized_text]
    if missing:
        raise AssertionError(f"{_relative(path)} is missing required phrases: {', '.join(missing)}")


def _require_supported_packet_state(text: str, *, path: Path) -> None:
    try:
        _require_phrases(text, REQUIRED_DRAFT_PACKET_PHRASES, path=path)
        return
    except AssertionError as draft_error:
        try:
            _require_phrases(text, REQUIRED_EXECUTED_NO_GO_PACKET_PHRASES, path=path)
            return
        except AssertionError as executed_error:
            raise AssertionError(
                f"{_relative(path)} is neither a valid draft packet nor a valid executed NO-GO packet. "
                f"Draft validation: {draft_error}. Executed NO-GO validation: {executed_error}."
            ) from executed_error


def _extract_max_call_cap(text: str) -> int:
    match = re.search(r"Maximum allowed provider calls:\s*(\d+)", text)
    if not match:
        raise AssertionError("Packet is missing 'Maximum allowed provider calls'.")
    return int(match.group(1))


def _is_policy_reference(line: str) -> bool:
    lowered = line.lower()
    return any(marker in lowered for marker in POLICY_REFERENCE_MARKERS)


def _reject_secret_patterns(path: Path, text: str) -> None:
    for line_number, line in enumerate(text.splitlines(), start=1):
        for pattern in SECRET_PATTERNS:
            match = pattern.search(line)
            if not match:
                continue
            if pattern.pattern.startswith("data:image") and _is_policy_reference(line):
                continue
            raise AssertionError(
                f"{_relative(path)}:{line_number} contains forbidden pattern {pattern.pattern!r} "
                f"near {match.group(0)!r}"
            )


def _validate_manifest(payload: dict[str, Any], *, path: Path) -> None:
    if payload.get("manifest_id") != "provider-mask-fixture-manifest-001":
        raise AssertionError("Manifest id must be provider-mask-fixture-manifest-001.")
    if payload.get("status") not in {
        "draft_not_approved_for_execution",
        "offline_rehearsal_ready_not_approved_for_execution",
    }:
        raise AssertionError("Manifest status must remain not approved for execution.")
    if payload.get("real_user_photos_allowed") is not False:
        raise AssertionError("Manifest must set real_user_photos_allowed to false.")
    if payload.get("provider_execution_allowed") is not False:
        raise AssertionError("Manifest must set provider_execution_allowed to false.")

    fixtures = payload.get("fixtures")
    if not isinstance(fixtures, list):
        raise AssertionError("Manifest fixtures must be a list.")
    if len(fixtures) != 2:
        raise AssertionError("Packet 001 fixture manifest must contain exactly 2 fixtures.")

    expected_ids = ["pm001-solid-frontal", "pm001-pattern-boundary"]
    actual_ids: list[str] = []
    for index, fixture in enumerate(fixtures, start=1):
        if not isinstance(fixture, dict):
            raise AssertionError(f"Fixture {index} must be a JSON object.")
        missing = sorted(FIXTURE_FIELDS - fixture.keys())
        if missing:
            raise AssertionError(f"Fixture {index} is missing fields: {', '.join(missing)}")
        actual_ids.append(str(fixture["fixture_id"]))
        if fixture.get("source_image_type") != "synthetic":
            raise AssertionError(f"Fixture {fixture['fixture_id']} must be synthetic.")
        if not isinstance(fixture.get("protected_regions"), list) or not fixture["protected_regions"]:
            raise AssertionError(f"Fixture {fixture['fixture_id']} must list protected regions.")
        notes = str(fixture.get("notes", "")).lower()
        if "no real user" not in notes and "hands must remain protected" not in notes:
            raise AssertionError(f"Fixture {fixture['fixture_id']} must include safety notes.")

    if actual_ids != expected_ids:
        raise AssertionError(f"Manifest fixture ids must be {expected_ids}, got {actual_ids}.")

    _reject_secret_patterns(path, json.dumps(payload, ensure_ascii=False, sort_keys=True))


def validate(packet_path: Path, manifest_path: Path) -> None:
    packet = _read_text(packet_path)
    manifest = _read_json(manifest_path)

    _require_sections(packet, PACKET_SECTIONS, path=packet_path)
    _require_supported_packet_state(packet, path=packet_path)
    if _extract_max_call_cap(packet) > 3:
        raise AssertionError("Maximum allowed provider call cap must be <= 3.")
    _reject_secret_patterns(packet_path, packet)
    _validate_manifest(manifest, path=manifest_path)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        validate(args.packet, args.manifest)
    except AssertionError as exc:
        print(f"validation failed: {exc}", file=sys.stderr)
        return 1
    print("provider/mask execution packet proposal validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
