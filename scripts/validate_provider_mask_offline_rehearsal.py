#!/usr/bin/env python3
"""Validate provider-mask-001 offline rehearsal artifacts.

The validator is offline-only. It never calls OpenAI, external providers,
databases, staging, production, or networks.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    from PIL import Image
except ImportError as exc:  # pragma: no cover - exercised only in missing-dependency environments
    raise SystemExit("Pillow is required to validate provider-mask offline rehearsal artifacts.") from exc


REPO_ROOT = Path(__file__).resolve().parents[1]
PACKET_PATH = REPO_ROOT / "docs" / "experiments" / "provider_mask_execution_packet_001.md"
MANIFEST_PATH = (
    REPO_ROOT / "docs" / "experiments" / "fixtures" / "provider_mask_fixture_manifest_001.json"
)
PRESERVATION_REPORT = (
    REPO_ROOT / "docs" / "experiments" / "reports" / "provider_mask_preservation_rehearsal_001.json"
)
VISUAL_REPORT = (
    REPO_ROOT / "docs" / "experiments" / "reports" / "provider_mask_visual_quality_rehearsal_001.md"
)

EXPECTED_FIXTURES = ["pm001-solid-frontal", "pm001-pattern-boundary"]
IMAGE_FIELDS = ["source_image_reference", "mask_reference", "fabric_reference", "fake_output_reference"]

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

SCAN_PATHS = [
    PACKET_PATH,
    MANIFEST_PATH,
    PRESERVATION_REPORT,
    VISUAL_REPORT,
    REPO_ROOT / "scripts" / "generate_provider_mask_offline_rehearsal.py",
    REPO_ROOT / "scripts" / "validate_provider_mask_offline_rehearsal.py",
]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate provider-mask-001 offline rehearsal artifacts.")
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--packet", type=Path, default=PACKET_PATH)
    parser.add_argument("--preservation-report", type=Path, default=PRESERVATION_REPORT)
    parser.add_argument("--visual-report", type=Path, default=VISUAL_REPORT)
    return parser.parse_args(argv)


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise AssertionError(f"Missing required file: {_relative(path)}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AssertionError(f"{_relative(path)} must contain a JSON object.")
    return payload


def _read_text(path: Path) -> str:
    if not path.is_file():
        raise AssertionError(f"Missing required file: {_relative(path)}")
    return path.read_text(encoding="utf-8")


def _repo_path(reference: str) -> Path:
    path = Path(reference)
    if path.is_absolute():
        raise AssertionError(f"Path must be repo-relative, not absolute: {reference}")
    if ".." in path.parts:
        raise AssertionError(f"Path must not traverse outside repo: {reference}")
    return REPO_ROOT / path


def _validate_png(path: Path) -> tuple[int, int, str]:
    if path.suffix.lower() != ".png":
        raise AssertionError(f"Expected PNG file: {_relative(path)}")
    if not path.is_file():
        raise AssertionError(f"Missing PNG file: {_relative(path)}")
    with Image.open(path) as image:
        if image.format != "PNG":
            raise AssertionError(f"Expected PNG image format: {_relative(path)}")
        return image.width, image.height, image.mode


def _validate_manifest(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if manifest.get("manifest_id") != "provider-mask-fixture-manifest-001":
        raise AssertionError("Unexpected manifest_id.")
    if manifest.get("status") != "offline_rehearsal_ready_not_approved_for_execution":
        raise AssertionError("Manifest status must be offline_rehearsal_ready_not_approved_for_execution.")
    if manifest.get("real_user_photos_allowed") is not False:
        raise AssertionError("real_user_photos_allowed must be false.")
    if manifest.get("provider_execution_allowed") is not False:
        raise AssertionError("provider_execution_allowed must be false.")
    fixtures = manifest.get("fixtures")
    if not isinstance(fixtures, list) or len(fixtures) != 2:
        raise AssertionError("Manifest must contain exactly 2 fixtures.")

    by_id: dict[str, dict[str, Any]] = {}
    for fixture in fixtures:
        if not isinstance(fixture, dict):
            raise AssertionError("Each fixture must be an object.")
        fixture_id = fixture.get("fixture_id")
        if fixture_id not in EXPECTED_FIXTURES:
            raise AssertionError(f"Unexpected fixture id: {fixture_id}")
        if fixture.get("source_image_type") != "synthetic":
            raise AssertionError(f"{fixture_id} must be synthetic.")
        if "real" in str(fixture.get("source_image_reference", "")).lower():
            raise AssertionError(f"{fixture_id} must not reference real photos.")
        dimensions: list[tuple[int, int]] = []
        for field in IMAGE_FIELDS:
            value = fixture.get(field)
            if not isinstance(value, str) or not value:
                raise AssertionError(f"{fixture_id} missing image field: {field}")
            image_path = _repo_path(value)
            width, height, mode = _validate_png(image_path)
            dimensions.append((width, height))
            if field == "mask_reference" and mode != "RGBA":
                raise AssertionError(f"{fixture_id} mask must be RGBA: {_relative(image_path)}")
        source_size, mask_size, _fabric_size, fake_output_size = dimensions
        if source_size != mask_size or source_size != fake_output_size:
            raise AssertionError(f"{fixture_id} source/mask/fake output dimensions must match.")
        by_id[str(fixture_id)] = fixture
    if sorted(by_id) != sorted(EXPECTED_FIXTURES):
        raise AssertionError("Manifest fixtures do not match expected fixture ids.")
    return by_id


def _validate_packet(packet: str) -> None:
    required = [
        "Status: DRAFT / NOT APPROVED FOR EXECUTION",
        "Execution approval: NOT APPROVED",
        "Issue: [#56](https://github.com/Grafnnn/telegram-bot/issues/56)",
        "Expected provider calls: 2",
        "Maximum allowed provider calls: 3",
        "Offline rehearsal artifacts:",
    ]
    missing = [phrase for phrase in required if phrase not in packet]
    if missing:
        raise AssertionError(f"Packet missing required offline rehearsal references: {', '.join(missing)}")


def _validate_preservation_report(report: dict[str, Any], fixture_ids: set[str]) -> None:
    if report.get("status") != "offline_rehearsal_only_not_provider_execution":
        raise AssertionError("Preservation report has unexpected status.")
    if report.get("provider_openai_called") is not False:
        raise AssertionError("Preservation report must state provider_openai_called=false.")
    if report.get("experiment_executed") is not False:
        raise AssertionError("Preservation report must state experiment_executed=false.")
    entries = report.get("entries")
    if not isinstance(entries, list) or len(entries) != 2:
        raise AssertionError("Preservation report must have exactly 2 entries.")
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise AssertionError("Preservation report entry must be an object.")
        fixture_id = entry.get("fixture_id")
        if fixture_id not in fixture_ids:
            raise AssertionError(f"Unexpected preservation fixture id: {fixture_id}")
        seen.add(str(fixture_id))
        if entry.get("protected_region_drift") is not False:
            raise AssertionError(f"{fixture_id} fake output must have no protected-region drift.")
        if entry.get("pass_fail") != "pass":
            raise AssertionError(f"{fixture_id} fake preservation rehearsal must pass.")
        if float(entry.get("mean_delta_protected_region", -1)) != 0.0:
            raise AssertionError(f"{fixture_id} protected mean delta must be 0.")
        if float(entry.get("changed_pixel_percent_protected_region", -1)) != 0.0:
            raise AssertionError(f"{fixture_id} protected changed pixel percent must be 0.")
        if int(entry.get("max_delta_protected_region", -1)) != 0:
            raise AssertionError(f"{fixture_id} protected max delta must be 0.")
    if seen != fixture_ids:
        raise AssertionError("Preservation report entries do not match manifest fixtures.")


def _validate_visual_report(text: str) -> None:
    required = [
        "Status: OFFLINE REHEARSAL ONLY / NOT PROVIDER EXECUTION",
        "This report does not approve provider execution or user-facing rollout.",
        "pm001-solid-frontal",
        "pm001-pattern-boundary",
        "READY_FOR_APPROVAL_REVIEW",
    ]
    missing = [phrase for phrase in required if phrase not in text]
    if missing:
        raise AssertionError(f"Visual rehearsal report missing required text: {', '.join(missing)}")


def _reject_risky_patterns(paths: list[Path]) -> None:
    for path in paths:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for line_number, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("re.compile("):
                continue
            for pattern in SECRET_PATTERNS:
                match = pattern.search(line)
                if match:
                    raise AssertionError(
                        f"{_relative(path)}:{line_number} contains risky pattern "
                        f"{pattern.pattern!r} near {match.group(0)!r}"
                    )


def validate(args: argparse.Namespace) -> None:
    manifest = _read_json(args.manifest)
    packet = _read_text(args.packet)
    preservation_report = _read_json(args.preservation_report)
    visual_report = _read_text(args.visual_report)

    fixtures = _validate_manifest(manifest)
    _validate_packet(packet)
    _validate_preservation_report(preservation_report, set(fixtures))
    _validate_visual_report(visual_report)
    _reject_risky_patterns(SCAN_PATHS)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        validate(args)
    except AssertionError as exc:
        print(f"validation failed: {exc}", file=sys.stderr)
        return 1
    print("provider-mask-001 offline rehearsal validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
