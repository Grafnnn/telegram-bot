#!/usr/bin/env python3
"""Run offline crop-only output dimension reconciliation rehearsal.

This script is local/test-only. It does not call OpenAI, external providers,
networks, databases, staging, or production. It rehearses how an oversized
provider-like crop output could be reconciled to the crop box before local
composite and preservation checks.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

from PIL import Image, ImageDraw


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.crop_composite_service import CropBox, composite_edited_crop  # noqa: E402
from app.services.preservation_service import calculate_outside_mask_drift  # noqa: E402


REHEARSAL_ID = "crop-only-dimension-reconciliation-001"
MANIFEST_PATH = REPO_ROOT / "docs" / "experiments" / "fixtures" / "crop_only_provider_frozen_inputs_001.json"
ASSET_DIR = REPO_ROOT / "docs" / "experiments" / "assets" / "crop-only-dimension-001"
REPORT_JSON = REPO_ROOT / "docs" / "experiments" / "reports" / "crop_only_dimension_reconciliation_001.json"
REPORT_MD = REPO_ROOT / "docs" / "experiments" / "reports" / "crop_only_dimension_reconciliation_001.md"
EXPECTED_FIXTURE_IDS = ["pm001-solid-frontal", "pm001-pattern-boundary"]
PROVIDER_OUTPUT_SIZE = (1024, 1536)
MAX_CHANGED_PIXEL_PERCENT = 1.0
MAX_MEAN_DELTA = 1.0


def _repo_relative(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def _safe_repo_path(reference: str) -> Path:
    path = Path(reference)
    if path.is_absolute() or ".." in path.parts:
        raise RuntimeError(f"Unsafe image reference: {reference}")
    resolved = REPO_ROOT / path
    if not resolved.is_file():
        raise RuntimeError(f"Missing image reference: {reference}")
    return resolved


def _load_image(reference: str) -> Image.Image:
    with Image.open(_safe_repo_path(reference)) as image:
        return image.copy()


def _save_png(image: Image.Image, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG")
    return _repo_relative(path)


def _tiled_fabric(fabric_image: Image.Image, size: tuple[int, int]) -> Image.Image:
    fabric = fabric_image.convert("RGB")
    tiled = Image.new("RGB", size)
    for top in range(0, size[1], fabric.height):
        for left in range(0, size[0], fabric.width):
            tiled.paste(fabric, (left, top))
    return tiled


def _fake_oversized_provider_output(fabric_image: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Create deterministic provider-like oversized crop output."""

    image = _tiled_fabric(fabric_image, size)
    draw = ImageDraw.Draw(image, "RGBA")
    width, height = size
    for index in range(-height, width, 96):
        draw.line([(index, 0), (index + height, height)], fill=(255, 255, 255, 28), width=18)
        draw.line([(index + 48, 0), (index + height + 48, height)], fill=(0, 0, 0, 20), width=10)
    draw.rectangle([0, 0, width - 1, height - 1], outline=(32, 32, 32, 120), width=8)
    return image


def reconcile_center_crop_resize(provider_output: Image.Image, target_size: tuple[int, int]) -> Image.Image:
    """Center-crop provider output to target aspect, then resize exactly to crop size."""

    if target_size[0] <= 0 or target_size[1] <= 0:
        raise ValueError("Target size must be positive.")
    source = provider_output.convert("RGB")
    source_width, source_height = source.size
    target_width, target_height = target_size
    source_aspect = source_width / source_height
    target_aspect = target_width / target_height

    if source_aspect > target_aspect:
        crop_width = round(source_height * target_aspect)
        left = max(0, (source_width - crop_width) // 2)
        box = (left, 0, left + crop_width, source_height)
    else:
        crop_height = round(source_width / target_aspect)
        top = max(0, (source_height - crop_height) // 2)
        box = (0, top, source_width, top + crop_height)

    return source.crop(box).resize(target_size, Image.Resampling.LANCZOS)


def _fixture_result(fixture: dict[str, Any]) -> dict[str, Any]:
    fixture_id = str(fixture["fixture_id"])
    source = _load_image(str(fixture["source_image"]))
    full_mask = _load_image(str(fixture["full_mask"]))
    crop_source = _load_image(str(fixture["crop_source"]))
    fabric = _load_image(str(fixture["fabric_reference"]))
    bounds = fixture["crop_bounds"]
    crop_box = CropBox(bounds["left"], bounds["top"], bounds["right"], bounds["bottom"])
    target_size = (crop_box.width, crop_box.height)

    oversized = _fake_oversized_provider_output(fabric, PROVIDER_OUTPUT_SIZE)
    reconciled = reconcile_center_crop_resize(oversized, target_size)
    composite = composite_edited_crop(source, reconciled, full_mask, crop_box)
    drift = calculate_outside_mask_drift(source, composite, full_mask)
    preservation_passes = drift.passes(
        max_mean_delta=MAX_MEAN_DELTA,
        max_changed_pixel_percent=MAX_CHANGED_PIXEL_PERCENT,
    )

    fixture_dir = ASSET_DIR / fixture_id
    oversized_ref = _save_png(oversized, fixture_dir / "fake_oversized_provider_output.png")
    reconciled_ref = _save_png(reconciled, fixture_dir / "reconciled_crop.png")
    composite_ref = _save_png(composite, fixture_dir / "composite_output.png")

    return {
        "fixture_id": fixture_id,
        "source_image": fixture["source_image"],
        "full_mask": fixture["full_mask"],
        "crop_source": fixture["crop_source"],
        "crop_mask": fixture["crop_mask"],
        "fabric_reference": fixture["fabric_reference"],
        "crop_bounds": bounds,
        "crop_source_dimensions": {"width": crop_source.width, "height": crop_source.height},
        "oversized_provider_output_dimensions": {
            "width": PROVIDER_OUTPUT_SIZE[0],
            "height": PROVIDER_OUTPUT_SIZE[1],
        },
        "reconciled_crop_dimensions": {"width": reconciled.width, "height": reconciled.height},
        "strategy": "center_crop_to_crop_aspect_then_resize",
        "fake_oversized_provider_output": oversized_ref,
        "reconciled_crop": reconciled_ref,
        "composite_output": composite_ref,
        "mean_delta_protected_region": drift.mean_delta,
        "changed_pixel_percent_protected_region": drift.changed_pixel_percent,
        "max_delta_protected_region": drift.max_delta,
        "protected_pixel_count": drift.protected_pixel_count,
        "editable_pixel_count": drift.editable_pixel_count,
        "protected_region_drift": not preservation_passes,
        "pass_fail": "pass" if preservation_passes else "fail",
    }


def _build_report() -> dict[str, Any]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest.get("provider_openai_calls_allowed") is not False:
        raise RuntimeError("Frozen inputs manifest must not allow provider calls for offline rehearsal.")
    fixtures = manifest.get("fixtures")
    if not isinstance(fixtures, list):
        raise RuntimeError("Frozen inputs manifest fixtures must be a list.")
    by_id = {str(fixture.get("fixture_id")): fixture for fixture in fixtures if isinstance(fixture, dict)}
    if list(by_id) != EXPECTED_FIXTURE_IDS:
        raise RuntimeError(f"Expected fixture ids {EXPECTED_FIXTURE_IDS}, got {list(by_id)}")

    entries = [_fixture_result(by_id[fixture_id]) for fixture_id in EXPECTED_FIXTURE_IDS]
    status = "offline_rehearsal_passed" if all(entry["pass_fail"] == "pass" for entry in entries) else "failed"
    return {
        "rehearsal_id": REHEARSAL_ID,
        "status": status,
        "strategy": "center_crop_to_crop_aspect_then_resize",
        "provider_openai_called": False,
        "provider_retry_authorized": False,
        "runtime_behavior_changed": False,
        "user_facing_rollout_approved": False,
        "source_execution_report": "docs/experiments/reports/crop_only_provider_execution_001.json",
        "frozen_inputs_manifest": _repo_relative(MANIFEST_PATH),
        "simulated_provider_output_size": {
            "width": PROVIDER_OUTPUT_SIZE[0],
            "height": PROVIDER_OUTPUT_SIZE[1],
        },
        "thresholds": {
            "max_mean_delta": MAX_MEAN_DELTA,
            "max_changed_pixel_percent": MAX_CHANGED_PIXEL_PERCENT,
            "pixel_delta_threshold": 8,
        },
        "fixtures": entries,
        "decision": (
            "READY_FOR_RETRY_PACKET_DESIGN_ONLY"
            if status == "offline_rehearsal_passed"
            else "NO_GO_DIMENSION_RECONCILIATION"
        ),
    }


def _write_markdown(report: dict[str, Any]) -> None:
    lines = [
        "# Crop-Only Dimension Reconciliation Rehearsal 001",
        "",
        "## Status",
        "",
        f"Status: `{report['status']}`",
        "",
        "This is an offline deterministic rehearsal only.",
        "It does not call OpenAI/provider.",
        "It does not approve provider retry.",
        "It does not approve user-facing rollout.",
        "",
        "## Strategy",
        "",
        "Strategy: `center_crop_to_crop_aspect_then_resize`",
        "",
        "The rehearsal simulates an oversized provider output, center-crops it to",
        "the target crop aspect ratio, resizes it to the exact crop box, composites",
        "it locally, and runs full-image preservation.",
        "",
        "This proves geometry and preservation mechanics only. It does not prove",
        "provider visual quality or fabric scale quality.",
        "",
        "## Metrics",
        "",
        "| Fixture | Preservation | Oversized output | Reconciled crop | Mean delta | Changed protected pixels | Max delta |",
        "| --- | --- | --- | --- | ---: | ---: | ---: |",
    ]
    for entry in report["fixtures"]:
        lines.append(
            "| `{fixture}` | {verdict} | {oversized_width}x{oversized_height} | {crop_width}x{crop_height} | "
            "{mean_delta:.4f} | {changed:.4f}% | {max_delta} |".format(
                fixture=entry["fixture_id"],
                verdict=entry["pass_fail"],
                oversized_width=entry["oversized_provider_output_dimensions"]["width"],
                oversized_height=entry["oversized_provider_output_dimensions"]["height"],
                crop_width=entry["reconciled_crop_dimensions"]["width"],
                crop_height=entry["reconciled_crop_dimensions"]["height"],
                mean_delta=entry["mean_delta_protected_region"],
                changed=entry["changed_pixel_percent_protected_region"],
                max_delta=entry["max_delta_protected_region"],
            )
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            f"Decision: `{report['decision']}`",
            "",
            "A future provider retry still requires a new explicit approval packet.",
            "The packet must state whether this reconciliation strategy is allowed",
            "and must include visual review requirements for fabric scale and boundary quality.",
            "",
            "## Non-Approvals",
            "",
            "- No provider/OpenAI retry is approved.",
            "- No runtime implementation is approved.",
            "- No staging/prod/env change is approved.",
            "- No user-facing rollout is approved.",
        ]
    )
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    report = _build_report()
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")
    _write_markdown(report)
    print(f"{REHEARSAL_ID}: {report['status']} / {report['decision']}")
    return 0 if report["status"] == "offline_rehearsal_passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
