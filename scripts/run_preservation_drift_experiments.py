#!/usr/bin/env python3
"""Run manifest-driven preservation drift experiments over local fixtures.

This developer-only tool consumes the deterministic fixture manifest used for
Issue #36 preservation-quality experiments. It writes one JSON report per case,
one aggregate JSON summary, and optionally a concise Markdown table. It only
reads local files and never calls providers, services, databases, or networks.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import json
import re
import sys
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from check_preservation_drift import (  # noqa: E402
    DEFAULT_MAX_CHANGED_PIXEL_PERCENT,
    DEFAULT_MAX_MEAN_DELTA,
    DEFAULT_PIXEL_DELTA_THRESHOLD,
    evaluate_preservation_drift,
    write_json_report,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run preservation drift checks for every case in a local fixture manifest.",
    )
    parser.add_argument("--manifest", required=True, type=Path, help="Path to manifest.json.")
    parser.add_argument(
        "--fixtures-root",
        required=True,
        type=Path,
        help="Directory that relative manifest image paths resolve against.",
    )
    parser.add_argument("--output-dir", required=True, type=Path, help="Directory for per-case JSON reports.")
    parser.add_argument("--summary", required=True, type=Path, help="Path to aggregate summary JSON.")
    parser.add_argument("--markdown-summary", type=Path, help="Optional path for a Markdown summary table.")
    parser.add_argument(
        "--allow-unexpected",
        action="store_true",
        help="Exit 0 even when a case result does not match expected_pass.",
    )
    return parser.parse_args(argv)


def _load_manifest(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = payload.get("cases") if isinstance(payload, dict) else None
    if not isinstance(cases, list):
        raise ValueError("Manifest must be a JSON object with a list field named 'cases'.")
    return cases


def _thresholds(case: dict[str, Any]) -> dict[str, float | int]:
    raw = case.get("thresholds")
    raw = raw if isinstance(raw, dict) else {}
    return {
        "max_mean_delta": float(raw.get("max_mean_delta", DEFAULT_MAX_MEAN_DELTA)),
        "max_changed_pixel_percent": float(
            raw.get("max_changed_pixel_percent", DEFAULT_MAX_CHANGED_PIXEL_PERCENT)
        ),
        "pixel_delta_threshold": int(raw.get("pixel_delta_threshold", DEFAULT_PIXEL_DELTA_THRESHOLD)),
    }


def _required_string(case: dict[str, Any], field: str) -> str:
    value = case.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Manifest case is missing a non-empty string field: {field}")
    return value


def _expected_pass(case: dict[str, Any]) -> bool:
    value = case.get("expected_pass")
    if not isinstance(value, bool):
        raise ValueError("Manifest case is missing a boolean field: expected_pass")
    return value


def _safe_report_stem(name: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("._")
    if not stem:
        raise ValueError(f"Manifest case name cannot be converted to a safe report filename: {name!r}")
    return stem


def _case_paths(case: dict[str, Any], fixtures_root: Path) -> tuple[Path, Path, Path]:
    return (
        fixtures_root / _required_string(case, "base"),
        fixtures_root / _required_string(case, "candidate"),
        fixtures_root / _required_string(case, "mask"),
    )


def _case_summary(
    *,
    case: dict[str, Any],
    report: dict[str, Any],
    report_path: Path,
) -> dict[str, Any]:
    expected_pass = _expected_pass(case)
    actual_pass = bool(report["passes"])
    return {
        "name": _required_string(case, "name"),
        "expected_pass": expected_pass,
        "actual_pass": actual_pass,
        "expected_matches_actual": expected_pass == actual_pass,
        "report_path": str(report_path),
        "thresholds": report["thresholds"],
        "drift": report["drift"],
        "notes": case.get("notes") if isinstance(case.get("notes"), str) else None,
    }


def _write_summary(summary: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _format_bool(value: bool) -> str:
    return "yes" if value else "no"


def _write_markdown_summary(summary: dict[str, Any], path: Path) -> None:
    rows = [
        "| case | expected | actual | match | mean_delta | changed_pixel_percent | max_delta | notes |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | --- |",
    ]
    for case in summary["cases"]:
        drift = case["drift"]
        notes = str(case.get("notes") or "").replace("|", "\\|")
        rows.append(
            "| {name} | {expected} | {actual} | {match} | {mean_delta:.4f} | {changed:.4f} | {max_delta} | {notes} |".format(
                name=case["name"],
                expected=_format_bool(case["expected_pass"]),
                actual=_format_bool(case["actual_pass"]),
                match=_format_bool(case["expected_matches_actual"]),
                mean_delta=float(drift["mean_delta"]),
                changed=float(drift["changed_pixel_percent"]),
                max_delta=drift["max_delta"],
                notes=notes,
            )
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# Preservation Drift Experiment Summary\n\n" + "\n".join(rows) + "\n", encoding="utf-8")


def run_experiments(
    *,
    manifest: Path,
    fixtures_root: Path,
    output_dir: Path,
    summary_path: Path,
    markdown_summary_path: Path | None = None,
) -> dict[str, Any]:
    cases = _load_manifest(manifest)
    output_dir.mkdir(parents=True, exist_ok=True)

    seen_names: set[str] = set()
    case_summaries: list[dict[str, Any]] = []
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("Each manifest case must be a JSON object.")
        name = _required_string(case, "name")
        if name in seen_names:
            raise ValueError(f"Duplicate manifest case name: {name}")
        seen_names.add(name)

        thresholds = _thresholds(case)
        base_path, candidate_path, mask_path = _case_paths(case, fixtures_root)
        report = evaluate_preservation_drift(
            base=base_path,
            candidate=candidate_path,
            mask=mask_path,
            max_mean_delta=float(thresholds["max_mean_delta"]),
            max_changed_pixel_percent=float(thresholds["max_changed_pixel_percent"]),
            pixel_delta_threshold=int(thresholds["pixel_delta_threshold"]),
        )
        report_path = output_dir / f"{_safe_report_stem(name)}.json"
        write_json_report(report, output=report_path, pretty=True)
        case_summaries.append(_case_summary(case=case, report=report, report_path=report_path))

    expected_match_count = sum(1 for case in case_summaries if case["expected_matches_actual"])
    summary = {
        "total_cases": len(case_summaries),
        "passed_count": sum(1 for case in case_summaries if case["actual_pass"]),
        "failed_count": sum(1 for case in case_summaries if not case["actual_pass"]),
        "expected_match_count": expected_match_count,
        "unexpected_result_count": len(case_summaries) - expected_match_count,
        "all_expected": expected_match_count == len(case_summaries),
        "cases": case_summaries,
    }
    _write_summary(summary, summary_path)
    if markdown_summary_path:
        _write_markdown_summary(summary, markdown_summary_path)
    return summary


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    summary = run_experiments(
        manifest=args.manifest,
        fixtures_root=args.fixtures_root,
        output_dir=args.output_dir,
        summary_path=args.summary,
        markdown_summary_path=args.markdown_summary,
    )
    return 0 if summary["all_expected"] or args.allow_unexpected else 1


if __name__ == "__main__":
    raise SystemExit(main())
