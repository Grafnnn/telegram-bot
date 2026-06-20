#!/usr/bin/env python3
"""Validate the segmentation-first crop/composite strategy document."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
STRATEGY_PATH = REPO_ROOT / "docs" / "segmentation_crop_composite_strategy.md"

REQUIRED_SECTIONS = [
    "## Status",
    "## Context",
    "## Decision Goal",
    "## High-Level Pipeline",
    "## Architecture Components",
    "## Segmentation Strategy Options",
    "## Crop Rules",
    "## Composite Rules",
    "## Prompt / Provider Rules",
    "## Evidence Gates",
    "## Stop Conditions",
    "## Runtime Safety Requirements",
    "## Suggested First PR Scope",
    "## Open Questions",
    "## Decision",
]

REQUIRED_PHRASES = [
    "Status: DESIGN GATE / NOT APPROVED FOR EXECUTION",
    "This document proposes the next architecture candidate after",
    "This document does not authorize provider/OpenAI calls",
    "segmentation-first -> crop/edit only garment region -> composite back -> preservation guardrail",
    "Provider output must never bypass the composite and preservation steps.",
    "Provider calls allowed only after a new explicit approval packet.",
    "The first implementation PR should stay local/test-only",
    "Do not run provider calls until that rehearsal passes and a new explicit execution packet is approved.",
]

FORBIDDEN_PHRASES = [
    "approved for user-facing rollout",
    "execution approved",
    "provider calls are approved",
    "production rollout approved",
]

SECRET_PATTERNS = [
    re.compile(r"sk-(?:proj|svcacct|admin|org)-[A-Za-z0-9_-]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{40,}"),
    re.compile(r"\b(?:OPENAI_API_KEY|BOT_INTERNAL_TOKEN|TELEGRAM_BOT_TOKEN|DATABASE_URL)\s*="),
    re.compile(r"data:image/[a-zA-Z0-9.+-]+;base64,"),
]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate segmentation-first crop/composite strategy docs.")
    parser.add_argument("--path", type=Path, default=STRATEGY_PATH)
    return parser.parse_args(argv)


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def validate(path: Path) -> None:
    if not path.is_file():
        raise AssertionError(f"Missing strategy document: {_relative(path)}")
    text = path.read_text(encoding="utf-8")
    normalized = " ".join(text.split())

    missing_sections = [section for section in REQUIRED_SECTIONS if section not in text]
    if missing_sections:
        raise AssertionError(f"Missing sections: {', '.join(missing_sections)}")

    missing_phrases = [phrase for phrase in REQUIRED_PHRASES if " ".join(phrase.split()) not in normalized]
    if missing_phrases:
        raise AssertionError(f"Missing required phrases: {', '.join(missing_phrases)}")

    lowered = text.lower()
    present_forbidden = [phrase for phrase in FORBIDDEN_PHRASES if phrase in lowered]
    if present_forbidden:
        raise AssertionError(f"Forbidden approval phrase present: {', '.join(present_forbidden)}")

    for line_number, line in enumerate(text.splitlines(), start=1):
        for pattern in SECRET_PATTERNS:
            match = pattern.search(line)
            if match:
                raise AssertionError(
                    f"{_relative(path)}:{line_number} contains forbidden pattern "
                    f"{pattern.pattern!r} near {match.group(0)!r}"
                )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        validate(args.path)
    except AssertionError as exc:
        print(f"validation failed: {exc}", file=sys.stderr)
        return 1
    print("segmentation crop/composite strategy validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
