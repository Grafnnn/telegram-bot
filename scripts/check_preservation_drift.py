#!/usr/bin/env python3
"""Evaluate outside-mask preservation drift for local image fixtures.

This is a local regression helper for controlled try-on experiments. It reads
three local image files, applies the same transparent-mask convention as the
backend edit flow, prints a JSON report, and exits non-zero when the drift
exceeds the configured thresholds.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
from typing import Any

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.preservation_service import (  # noqa: E402
    DEFAULT_PIXEL_DELTA_THRESHOLD,
    calculate_outside_mask_drift,
)

DEFAULT_MAX_MEAN_DELTA = 1.0
DEFAULT_MAX_CHANGED_PIXEL_PERCENT = 1.0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check RGB drift outside the transparent editable mask region for local fixtures.",
    )
    parser.add_argument("--base", required=True, type=Path, help="Original user-photo fixture.")
    parser.add_argument("--candidate", required=True, type=Path, help="Generated/result image fixture.")
    parser.add_argument("--mask", required=True, type=Path, help="PNG mask fixture; transparent pixels are editable.")
    parser.add_argument(
        "--max-mean-delta",
        type=float,
        default=DEFAULT_MAX_MEAN_DELTA,
        help=f"Maximum allowed mean protected-pixel RGB delta. Default: {DEFAULT_MAX_MEAN_DELTA}.",
    )
    parser.add_argument(
        "--max-changed-pixel-percent",
        type=float,
        default=DEFAULT_MAX_CHANGED_PIXEL_PERCENT,
        help=(
            "Maximum allowed percent of protected pixels above --pixel-delta-threshold. "
            f"Default: {DEFAULT_MAX_CHANGED_PIXEL_PERCENT}."
        ),
    )
    parser.add_argument(
        "--pixel-delta-threshold",
        type=int,
        default=DEFAULT_PIXEL_DELTA_THRESHOLD,
        help=f"Per-pixel RGB delta threshold for changed-pixel counting. Default: {DEFAULT_PIXEL_DELTA_THRESHOLD}.",
    )
    parser.add_argument("--output", type=Path, help="Optional path to write the JSON report.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    return parser.parse_args(argv)


def _load_image(path: Path) -> Image.Image:
    if not path.is_file():
        raise FileNotFoundError(f"Image file not found: {path}")
    with Image.open(path) as image:
        return image.copy()


def _report_payload(args: argparse.Namespace, passes: bool, drift: Any) -> dict[str, Any]:
    return {
        "passes": passes,
        "thresholds": {
            "max_mean_delta": args.max_mean_delta,
            "max_changed_pixel_percent": args.max_changed_pixel_percent,
            "pixel_delta_threshold": args.pixel_delta_threshold,
        },
        "drift": asdict(drift),
    }


def evaluate_preservation_drift(
    *,
    base: Path,
    candidate: Path,
    mask: Path,
    max_mean_delta: float = DEFAULT_MAX_MEAN_DELTA,
    max_changed_pixel_percent: float = DEFAULT_MAX_CHANGED_PIXEL_PERCENT,
    pixel_delta_threshold: int = DEFAULT_PIXEL_DELTA_THRESHOLD,
) -> dict[str, Any]:
    """Evaluate one local before/result/mask fixture set."""

    base_image = _load_image(base)
    candidate_image = _load_image(candidate)
    mask_image = _load_image(mask)

    drift = calculate_outside_mask_drift(
        base_image,
        candidate_image,
        mask_image,
        pixel_delta_threshold=pixel_delta_threshold,
    )
    passes = drift.passes(
        max_mean_delta=max_mean_delta,
        max_changed_pixel_percent=max_changed_pixel_percent,
    )
    args = argparse.Namespace(
        max_mean_delta=max_mean_delta,
        max_changed_pixel_percent=max_changed_pixel_percent,
        pixel_delta_threshold=pixel_delta_threshold,
    )
    return _report_payload(args, passes, drift)


def write_json_report(report: dict[str, Any], *, output: Path | None = None, pretty: bool = False) -> str:
    """Serialize a drift report and optionally write it to disk."""

    indent = 2 if pretty else None
    output_text = json.dumps(report, ensure_ascii=False, indent=indent, sort_keys=True)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(output_text + "\n", encoding="utf-8")
    return output_text


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    report = evaluate_preservation_drift(
        base=args.base,
        candidate=args.candidate,
        mask=args.mask,
        max_mean_delta=args.max_mean_delta,
        max_changed_pixel_percent=args.max_changed_pixel_percent,
        pixel_delta_threshold=args.pixel_delta_threshold,
    )

    output_text = write_json_report(report, output=args.output, pretty=args.pretty)
    print(output_text)
    return 0 if report["passes"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
