#!/usr/bin/env python3
"""Validate the controlled provider/mask experiment planning docs.

The validator is offline-only. It checks that the planning document and packet
template keep the required safety gates visible before any future provider run.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = REPO_ROOT / "docs" / "controlled_provider_mask_experiment_plan.md"
PACKET_PATH = REPO_ROOT / "docs" / "templates" / "provider_mask_experiment_packet.md"

PLAN_SECTIONS = [
    "## Purpose",
    "## Current Baseline",
    "## Decision Question",
    "## Experiment Non-Goals",
    "## Allowed Inputs",
    "## Fixture Pack Requirements",
    "## Provider Strategy Under Test",
    "## Mask Strategy Under Test",
    "## Safety Pre-Checks Before Any Future Execution",
    "## Future Execution Packet Template",
    "## Execution Flow For Future Gate",
    "## Preservation Analysis Requirements",
    "## Visual Quality Review Requirements",
    "## Stop Conditions / NO-GO Conditions",
    "## Artifact Policy",
    "## Reporting Format",
    "## Relationship To Existing Docs",
]

PACKET_SECTIONS = [
    "## Metadata",
    "## Scope",
    "## Non-Goals",
    "## Provider Configuration",
    "## Mask Configuration",
    "## Fixture Pack",
    "## Safety Checklist",
    "## Commands",
    "## Expected Artifacts",
    "## Stop Conditions",
    "## Preservation Report Links",
    "## Visual Quality Report Links",
    "## Decision",
    "## Approval",
]

REQUIRED_PHRASES = [
    "this plan does not approve execution",
    "execution requires a separate explicit approval packet",
    "No provider call may be made unless the execution packet explicitly names",
    "no real user photos",
    "No-mask mode cannot be used as evidence",
    "provider call happened without approved packet",
    "raw/base64 image data exposed",
    "secret/token exposed",
]

SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]"),
    re.compile(r"OPENAI_API_KEY\s*="),
    re.compile(r"BOT_TOKEN\s*="),
    re.compile(r"TELEGRAM_BOT_TOKEN\s*="),
    re.compile(r"PRIVATE KEY"),
    re.compile(r"data:image/[a-zA-Z0-9.+-]+;base64,"),
    re.compile(r"[A-Za-z0-9+/]{120,}={0,2}"),
]


def _read(path: Path) -> str:
    if not path.is_file():
        raise AssertionError(f"Missing required file: {path.relative_to(REPO_ROOT)}")
    return path.read_text(encoding="utf-8")


def _require_sections(text: str, sections: list[str], *, path: Path) -> None:
    missing = [section for section in sections if section not in text]
    if missing:
        formatted = ", ".join(missing)
        raise AssertionError(f"{path.relative_to(REPO_ROOT)} is missing sections: {formatted}")


def _require_phrases(text: str) -> None:
    normalized_text = " ".join(text.lower().split())
    missing = [phrase for phrase in REQUIRED_PHRASES if " ".join(phrase.lower().split()) not in normalized_text]
    if missing:
        formatted = ", ".join(missing)
        raise AssertionError(f"Plan is missing required safety phrases: {formatted}")


def _reject_secret_patterns(path: Path, text: str) -> None:
    for pattern in SECRET_PATTERNS:
        match = pattern.search(text)
        if match:
            raise AssertionError(
                f"{path.relative_to(REPO_ROOT)} contains forbidden pattern {pattern.pattern!r} "
                f"near {match.group(0)!r}"
            )


def main() -> int:
    plan = _read(PLAN_PATH)
    packet = _read(PACKET_PATH)

    _require_sections(plan, PLAN_SECTIONS, path=PLAN_PATH)
    _require_sections(packet, PACKET_SECTIONS, path=PACKET_PATH)
    _require_phrases(plan)
    _reject_secret_patterns(PLAN_PATH, plan)
    _reject_secret_patterns(PACKET_PATH, packet)

    print("provider/mask experiment planning docs validated")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"validation failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
