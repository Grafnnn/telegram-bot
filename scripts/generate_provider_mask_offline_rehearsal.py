#!/usr/bin/env python3
"""Offline synthetic fixture generator for provider-mask-001.

This script does not call OpenAI/provider and does not use real user photos.
It creates deterministic synthetic inputs, edit masks, fabric references, fake
provider outputs, and offline rehearsal reports for local review only.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

try:
    from PIL import Image, ImageDraw
except ImportError as exc:  # pragma: no cover - exercised only in missing-dependency environments
    raise SystemExit("Pillow is required to generate provider-mask offline rehearsal fixtures.") from exc


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from check_preservation_drift import evaluate_preservation_drift  # noqa: E402


ASSET_DIR = REPO_ROOT / "docs" / "experiments" / "assets" / "provider-mask-001"
PRESERVATION_REPORT = (
    REPO_ROOT / "docs" / "experiments" / "reports" / "provider_mask_preservation_rehearsal_001.json"
)
VISUAL_REPORT = (
    REPO_ROOT / "docs" / "experiments" / "reports" / "provider_mask_visual_quality_rehearsal_001.md"
)

IMAGE_SIZE = (160, 200)


def _repo_relative(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def _background() -> Image.Image:
    image = Image.new("RGB", IMAGE_SIZE, (236, 238, 240))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 172, 159, 199), fill=(218, 221, 224))
    draw.line((0, 172, 159, 172), fill=(190, 194, 198), width=1)
    return image


def _draw_head_and_body(draw: ImageDraw.ImageDraw, *, hands_near_boundary: bool) -> None:
    skin = (216, 188, 158)
    outline = (70, 70, 70)
    draw.ellipse((64, 18, 96, 50), fill=skin, outline=outline, width=2)
    draw.arc((58, 10, 102, 58), 205, 335, fill=(78, 62, 48), width=4)
    draw.line((80, 50, 80, 66), fill=outline, width=2)
    draw.rectangle((60, 66, 100, 118), fill=(58, 94, 164), outline=outline, width=2)
    draw.polygon([(60, 66), (45, 88), (56, 102), (68, 76)], fill=(58, 94, 164), outline=outline)
    draw.polygon([(100, 66), (115, 88), (104, 102), (92, 76)], fill=(58, 94, 164), outline=outline)
    draw.rectangle((62, 118, 98, 154), fill=(52, 72, 118), outline=outline, width=2)
    if hands_near_boundary:
        draw.ellipse((40, 97, 56, 113), fill=skin, outline=outline, width=2)
        draw.ellipse((104, 97, 120, 113), fill=skin, outline=outline, width=2)
        draw.line((46, 90, 54, 105), fill=skin, width=8)
        draw.line((114, 90, 106, 105), fill=skin, width=8)
    else:
        draw.line((48, 94, 48, 130), fill=skin, width=8)
        draw.line((112, 94, 112, 130), fill=skin, width=8)
        draw.ellipse((41, 126, 55, 140), fill=skin, outline=outline, width=1)
        draw.ellipse((105, 126, 119, 140), fill=skin, outline=outline, width=1)


def _source_image(*, hands_near_boundary: bool) -> Image.Image:
    image = _background()
    _draw_head_and_body(ImageDraw.Draw(image), hands_near_boundary=hands_near_boundary)
    return image


def _mask_image(*, boundary_case: bool) -> Image.Image:
    mask = Image.new("RGBA", IMAGE_SIZE, (0, 0, 0, 255))
    draw = ImageDraw.Draw(mask)
    if boundary_case:
        draw.rectangle((61, 67, 99, 116), fill=(0, 0, 0, 0))
        draw.polygon([(61, 68), (51, 86), (59, 94), (69, 76)], fill=(0, 0, 0, 0))
        draw.polygon([(99, 68), (109, 86), (101, 94), (91, 76)], fill=(0, 0, 0, 0))
    else:
        draw.rectangle((60, 66, 100, 118), fill=(0, 0, 0, 0))
        draw.rectangle((62, 118, 98, 154), fill=(0, 0, 0, 0))
    return mask


def _solid_fabric() -> Image.Image:
    image = Image.new("RGB", (64, 64), (174, 42, 128))
    draw = ImageDraw.Draw(image)
    for y in range(0, 64, 8):
        draw.line((0, y, 63, y), fill=(195, 76, 150), width=1)
    return image


def _pattern_fabric() -> Image.Image:
    image = Image.new("RGB", (64, 64), (235, 236, 226))
    draw = ImageDraw.Draw(image)
    for x in range(0, 64, 8):
        color = (60, 92, 150) if (x // 8) % 2 == 0 else (160, 48, 80)
        draw.rectangle((x, 0, x + 3, 63), fill=color)
    for y in range(0, 64, 10):
        draw.line((0, y, 63, y), fill=(48, 48, 48), width=1)
    return image


def _apply_fabric_inside_mask(source: Image.Image, mask: Image.Image, fabric: Image.Image) -> Image.Image:
    output = source.copy()
    fabric_rgb = fabric.convert("RGB")
    alpha = mask.convert("RGBA").getchannel("A")
    for y in range(output.height):
        for x in range(output.width):
            if alpha.getpixel((x, y)) == 0:
                output.putpixel((x, y), fabric_rgb.getpixel((x % fabric_rgb.width, y % fabric_rgb.height)))
    return output


def _write_fixture(fixture_id: str, *, boundary_case: bool) -> dict[str, Path]:
    source = _source_image(hands_near_boundary=boundary_case)
    mask = _mask_image(boundary_case=boundary_case)
    fabric = _pattern_fabric() if boundary_case else _solid_fabric()
    fake_output = _apply_fabric_inside_mask(source, mask, fabric)

    paths = {
        "source": ASSET_DIR / f"{fixture_id}-source.png",
        "mask": ASSET_DIR / f"{fixture_id}-mask.png",
        "fabric": ASSET_DIR / f"{fixture_id}-fabric.png",
        "fake_output": ASSET_DIR / f"{fixture_id}-fake-output.png",
    }
    source.save(paths["source"])
    mask.save(paths["mask"])
    fabric.save(paths["fabric"])
    fake_output.save(paths["fake_output"])
    return paths


def _preservation_entry(fixture_id: str, paths: dict[str, Path]) -> dict[str, Any]:
    report = evaluate_preservation_drift(
        base=paths["source"],
        candidate=paths["fake_output"],
        mask=paths["mask"],
    )
    drift = report["drift"]
    return {
        "fixture_id": fixture_id,
        "source_image": _repo_relative(paths["source"]),
        "mask_image": _repo_relative(paths["mask"]),
        "fake_output_image": _repo_relative(paths["fake_output"]),
        "mean_delta_protected_region": drift["mean_delta"],
        "changed_pixel_percent_protected_region": drift["changed_pixel_percent"],
        "max_delta_protected_region": drift["max_delta"],
        "protected_region_drift": not report["passes"],
        "identity_face_drift": False,
        "background_drift": False,
        "mask_boundary_drift": False,
        "pass_fail": "pass" if report["passes"] else "fail",
        "notes": "Fake output applies changes only inside the synthetic garment mask.",
    }


def _write_preservation_report(entries: list[dict[str, Any]]) -> None:
    payload = {
        "report_id": "provider-mask-preservation-rehearsal-001",
        "status": "offline_rehearsal_only_not_provider_execution",
        "provider_openai_called": False,
        "experiment_executed": False,
        "entries": entries,
    }
    PRESERVATION_REPORT.parent.mkdir(parents=True, exist_ok=True)
    PRESERVATION_REPORT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_visual_report() -> None:
    rows = [
        "| fixture_id | garment placement plausibility | fabric pattern continuity | fabric scale realism | body/pose preservation | face/hair/skin/background preservation | lighting/shadow consistency | garment boundary quality | absence of hallucinated artifacts | output resolution/format acceptability | repeatability expectation | cost/latency awareness | average | decision | notes |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
        "| pm001-solid-frontal | 4 | 3 | 4 | 5 | 5 | 3 | 4 | 5 | 5 | 5 | 0 | 3.91 | READY_FOR_APPROVAL_REVIEW | Offline fake output validates fixture/mask/report plumbing only. |",
        "| pm001-pattern-boundary | 4 | 4 | 4 | 5 | 5 | 3 | 4 | 5 | 5 | 5 | 0 | 4.00 | READY_FOR_APPROVAL_REVIEW | Hands remain outside the editable mask; this is not real provider evidence. |",
    ]
    VISUAL_REPORT.parent.mkdir(parents=True, exist_ok=True)
    VISUAL_REPORT.write_text(
        "\n".join(
            [
                "# Provider/Mask Visual Quality Rehearsal 001",
                "",
                "## Status",
                "",
                "Status: OFFLINE REHEARSAL ONLY / NOT PROVIDER EXECUTION",
                "",
                "This report does not approve provider execution or user-facing rollout.",
                "",
                "## Scope",
                "",
                "Validate that the local synthetic fixture, mask, fake-provider output, preservation report, and visual review skeleton are ready for approval review.",
                "",
                "## Fixtures Reviewed",
                "",
                "- `pm001-solid-frontal`",
                "- `pm001-pattern-boundary`",
                "",
                "## Scores",
                "",
                *rows,
                "",
                "## Preservation Summary",
                "",
                "Both fake outputs preserve protected pixels outside the transparent garment mask. This proves only local measurement/reporting plumbing.",
                "",
                "## Visual Notes",
                "",
                "- Fake outputs are deterministic and intentionally simple.",
                "- Scores are rehearsal scores, not real provider quality evidence.",
                "- Cost/latency is scored `0` because no provider call occurred.",
                "",
                "## Decision",
                "",
                "Decision: READY_FOR_APPROVAL_REVIEW",
                "",
                "## Limitations",
                "",
                "- No OpenAI/provider call was made.",
                "- No real provider preservation behavior was tested.",
                "- No real user photos were used.",
                "- This is not rollout evidence.",
                "",
                "## Next Gate",
                "",
                "Issue #56 must still be explicitly completed and approved before any capped provider/OpenAI call.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def main() -> int:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    fixtures = {
        "pm001-solid-frontal": _write_fixture("pm001-solid-frontal", boundary_case=False),
        "pm001-pattern-boundary": _write_fixture("pm001-pattern-boundary", boundary_case=True),
    }
    _write_preservation_report(
        [_preservation_entry(fixture_id, paths) for fixture_id, paths in fixtures.items()]
    )
    _write_visual_report()
    print(f"provider-mask-001 offline rehearsal generated under {_repo_relative(ASSET_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
