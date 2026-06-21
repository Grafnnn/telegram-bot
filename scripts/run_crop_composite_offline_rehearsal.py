#!/usr/bin/env python3
"""Run an offline crop/composite rehearsal over synthetic fixtures.

This script is local/test-only. It does not call OpenAI, external providers,
networks, databases, staging, or production. It proves the deterministic
segmentation-first mechanics: mask-derived crop bounds, crop-local fake edit,
composite back through the mask, and full-image preservation checks.
"""

from __future__ import annotations

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

from app.services.crop_composite_service import (  # noqa: E402
    composite_edited_crop,
    prepare_crop_inputs,
)
from app.services.preservation_service import calculate_outside_mask_drift  # noqa: E402


REHEARSAL_ID = "crop-composite-offline-001"
EXPECTED_FIXTURE_IDS = ["pm001-solid-frontal", "pm001-pattern-boundary"]
MANIFEST_PATH = REPO_ROOT / "docs" / "experiments" / "fixtures" / "provider_mask_fixture_manifest_001.json"
ASSET_DIR = REPO_ROOT / "docs" / "experiments" / "assets" / "crop-composite-001"
REPORT_JSON = REPO_ROOT / "docs" / "experiments" / "reports" / "crop_composite_offline_rehearsal_001.json"
REPORT_MD = REPO_ROOT / "docs" / "experiments" / "reports" / "crop_composite_offline_rehearsal_001.md"
PADDING_PIXELS = 8
MAX_CHANGED_PIXEL_PERCENT = 1.0
MAX_MEAN_DELTA = 1.0


def _repo_relative(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def _load_manifest() -> dict[str, Any]:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if payload.get("provider_execution_allowed") is not False:
        raise RuntimeError("Fixture manifest must not allow provider execution for offline rehearsal.")
    if payload.get("real_user_photos_allowed") is not False:
        raise RuntimeError("Fixture manifest must not allow real user photos.")
    return payload


def _load_image(reference: str) -> Image.Image:
    reference_path = Path(reference)
    if reference_path.is_absolute() or ".." in reference_path.parts:
        raise RuntimeError(f"Unsafe image reference: {reference}")
    path = REPO_ROOT / reference_path
    with Image.open(path) as image:
        return image.copy()


def _tiled_fabric(fabric_image: Image.Image, size: tuple[int, int]) -> Image.Image:
    fabric = fabric_image.convert("RGB")
    tiled = Image.new("RGB", size)
    for top in range(0, size[1], fabric.height):
        for left in range(0, size[0], fabric.width):
            tiled.paste(fabric, (left, top))
    return tiled


def _fake_crop_edit(source_crop: Image.Image, mask_crop: Image.Image, fabric_image: Image.Image) -> Image.Image:
    """Apply fabric only inside transparent/editable pixels of the crop mask."""

    source = source_crop.convert("RGB")
    fabric = _tiled_fabric(fabric_image, source.size)
    alpha = mask_crop.convert("RGBA").getchannel("A")
    editable = alpha.point(lambda value: 255 if value < 128 else 0, mode="L")
    edited = source.copy()
    edited.paste(fabric, (0, 0), editable)
    return edited


def _save_png(image: Image.Image, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG")
    return _repo_relative(path)


def _fixture_result(fixture: dict[str, Any]) -> dict[str, Any]:
    fixture_id = str(fixture["fixture_id"])
    source = _load_image(str(fixture["source_image_reference"]))
    mask = _load_image(str(fixture["mask_reference"]))
    fabric = _load_image(str(fixture["fabric_reference"]))

    crop_inputs = prepare_crop_inputs(source, mask, padding_pixels=PADDING_PIXELS)
    fake_crop_edit = _fake_crop_edit(crop_inputs.source_crop, crop_inputs.mask_crop, fabric)
    composite = composite_edited_crop(source, fake_crop_edit, mask, crop_inputs.crop_box)
    drift = calculate_outside_mask_drift(source, composite, mask)
    preservation_passes = drift.passes(
        max_mean_delta=MAX_MEAN_DELTA,
        max_changed_pixel_percent=MAX_CHANGED_PIXEL_PERCENT,
    )

    fixture_dir = ASSET_DIR / fixture_id
    crop_source = _save_png(crop_inputs.source_crop, fixture_dir / "crop_source.png")
    crop_mask = _save_png(crop_inputs.mask_crop, fixture_dir / "crop_mask.png")
    fake_edit = _save_png(fake_crop_edit, fixture_dir / "fake_crop_edit.png")
    composite_output = _save_png(composite, fixture_dir / "composite_output.png")

    return {
        "fixture_id": fixture_id,
        "source_image": fixture["source_image_reference"],
        "mask_image": fixture["mask_reference"],
        "fabric_image": fixture["fabric_reference"],
        "crop_bounds": {
            "left": crop_inputs.crop_box.left,
            "top": crop_inputs.crop_box.top,
            "right": crop_inputs.crop_box.right,
            "bottom": crop_inputs.crop_box.bottom,
        },
        "crop_padding_pixels": PADDING_PIXELS,
        "crop_source": crop_source,
        "crop_mask": crop_mask,
        "fake_crop_edit": fake_edit,
        "composite_output": composite_output,
        "mean_delta_protected_region": drift.mean_delta,
        "changed_pixel_percent_protected_region": drift.changed_pixel_percent,
        "max_delta_protected_region": drift.max_delta,
        "protected_pixel_count": drift.protected_pixel_count,
        "editable_pixel_count": drift.editable_pixel_count,
        "protected_region_drift": not preservation_passes,
        "pass_fail": "pass" if preservation_passes else "fail",
    }


def _build_report() -> dict[str, Any]:
    manifest = _load_manifest()
    fixtures = manifest.get("fixtures")
    if not isinstance(fixtures, list):
        raise RuntimeError("Manifest fixtures must be a list.")
    by_id = {str(fixture.get("fixture_id")): fixture for fixture in fixtures if isinstance(fixture, dict)}
    if list(by_id) != EXPECTED_FIXTURE_IDS:
        raise RuntimeError(f"Expected fixture ids {EXPECTED_FIXTURE_IDS}, got {list(by_id)}")

    entries = [_fixture_result(by_id[fixture_id]) for fixture_id in EXPECTED_FIXTURE_IDS]
    status = "offline_rehearsal_passed" if all(entry["pass_fail"] == "pass" for entry in entries) else "failed"
    return {
        "rehearsal_id": REHEARSAL_ID,
        "status": status,
        "provider_openai_called": False,
        "experiment_executed": False,
        "runtime_behavior_changed": False,
        "provider_calls_authorized": False,
        "user_facing_rollout_approved": False,
        "fixture_manifest": _repo_relative(MANIFEST_PATH),
        "thresholds": {
            "max_mean_delta": MAX_MEAN_DELTA,
            "max_changed_pixel_percent": MAX_CHANGED_PIXEL_PERCENT,
            "pixel_delta_threshold": 8,
        },
        "fixtures": entries,
        "decision": "READY_FOR_CAPPED_PROVIDER_PACKET_DESIGN_ONLY" if status == "offline_rehearsal_passed" else "NO_GO",
    }


def _write_markdown(report: dict[str, Any]) -> None:
    lines = [
        "# Crop/Composite Offline Rehearsal 001",
        "",
        "## Status",
        "",
        f"Status: `{report['status']}`",
        "",
        "This is an offline deterministic rehearsal only.",
        "It does not call OpenAI/provider.",
        "It does not approve user-facing rollout.",
        "It does not approve future provider calls.",
        "",
        "## Scope",
        "",
        "This report validates local crop/composite mechanics for the segmentation-first strategy:",
        "",
        "- synthetic fixture + garment mask;",
        "- mask-derived crop bounds;",
        "- crop-local source/mask creation;",
        "- deterministic fake crop edit;",
        "- composite back through the transparent clothing mask;",
        "- protected-region preservation check.",
        "",
        "## Pipeline",
        "",
        "```text",
        "synthetic source + mask -> crop source/mask -> fake crop edit -> composite -> preservation guardrail",
        "```",
        "",
        "## Fixtures",
        "",
        "| Fixture | Crop bounds | Crop padding | Composite output |",
        "| --- | --- | ---: | --- |",
    ]
    for entry in report["fixtures"]:
        bounds = entry["crop_bounds"]
        lines.append(
            "| `{fixture}` | `{left},{top},{right},{bottom}` | {padding} | `{output}` |".format(
                fixture=entry["fixture_id"],
                left=bounds["left"],
                top=bounds["top"],
                right=bounds["right"],
                bottom=bounds["bottom"],
                padding=entry["crop_padding_pixels"],
                output=entry["composite_output"],
            )
        )
    lines.extend(
        [
            "",
            "## Metrics",
            "",
            "| Fixture | Preservation | Mean delta | Changed protected pixels | Max delta |",
            "| --- | --- | ---: | ---: | ---: |",
        ]
    )
    for entry in report["fixtures"]:
        lines.append(
            "| `{fixture}` | {verdict} | {mean_delta:.4f} | {changed:.4f}% | {max_delta} |".format(
                fixture=entry["fixture_id"],
                verdict=entry["pass_fail"],
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
            "The local crop/composite mechanics are ready for review as a candidate safer architecture.",
            "A future provider test still requires a separate capped approval gate.",
            "",
            "## Limitations",
            "",
            "- This does not validate a real provider.",
            "- This does not validate real user photos.",
            "- This does not validate visual quality of provider outputs.",
            "- This does not change runtime behavior.",
            "- This does not approve rollout.",
            "",
            "## Next Gate",
            "",
            "Design a new capped provider approval packet that tests crop-only or garment-region-only provider editing,",
            "followed by local composite and preservation guardrail.",
        ]
    )
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    report = _build_report()
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_markdown(report)
    print(f"wrote {_repo_relative(REPORT_JSON)}")
    print(f"wrote {_repo_relative(REPORT_MD)}")
    return 0 if report["status"] == "offline_rehearsal_passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
