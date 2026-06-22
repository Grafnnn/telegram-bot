#!/usr/bin/env python3
"""Generate synthetic crop-only visual-quality expansion fixtures.

This script is local/test-only. It creates deterministic synthetic PNG assets
for the crop-only visual-quality packet and does not call providers, networks,
databases, staging, or production.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw


REPO_ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = REPO_ROOT / "docs" / "experiments" / "assets" / "crop-only-visual-quality-003"
CANVAS_SIZE = (180, 220)


@dataclass(frozen=True)
class FixtureSpec:
    fixture_id: str
    crop_box: tuple[int, int, int, int]
    category: str


FIXTURES = [
    FixtureSpec("pm003-large-pattern-scale", (46, 58, 132, 174), "large_scale_pattern"),
    FixtureSpec("pm004-edge-boundary-stress", (34, 52, 140, 158), "edge_boundary_stress"),
]


def _save_png(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG")


def _background(draw: ImageDraw.ImageDraw) -> None:
    draw.rectangle([0, 0, 179, 219], fill=(232, 236, 238))
    draw.rectangle([0, 190, 179, 219], fill=(215, 219, 221))
    draw.line([0, 190, 179, 190], fill=(168, 174, 178), width=1)
    draw.rectangle([132, 28, 168, 84], outline=(185, 190, 194), width=2)
    draw.line([138, 58, 162, 58], fill=(185, 190, 194), width=1)


def _person_base() -> Image.Image:
    image = Image.new("RGB", CANVAS_SIZE, (232, 236, 238))
    draw = ImageDraw.Draw(image)
    _background(draw)

    skin = (222, 184, 144)
    outline = (45, 45, 48)
    hair = (54, 42, 34)
    trousers = (55, 67, 95)
    shoe = (38, 38, 42)

    draw.ellipse([72, 16, 108, 52], fill=skin, outline=outline, width=2)
    draw.arc([64, 8, 116, 44], 200, 340, fill=hair, width=4)
    draw.line([90, 52, 90, 66], fill=outline, width=4)
    draw.rectangle([74, 140, 88, 196], fill=trousers, outline=outline)
    draw.rectangle([92, 140, 106, 196], fill=trousers, outline=outline)
    draw.rectangle([70, 196, 90, 202], fill=shoe)
    draw.rectangle([90, 196, 110, 202], fill=shoe)
    return image


def _large_pattern_fixture() -> tuple[Image.Image, Image.Image, Image.Image]:
    image = _person_base()
    draw = ImageDraw.Draw(image)
    outline = (43, 45, 50)
    cloth = (70, 95, 170)
    skin = (222, 184, 144)

    shirt = [(58, 66), (122, 66), (133, 120), (116, 166), (64, 166), (47, 120)]
    left_sleeve = [(58, 70), (38, 102), (48, 120), (65, 86)]
    right_sleeve = [(122, 70), (142, 102), (132, 120), (115, 86)]
    draw.polygon(shirt, fill=cloth, outline=outline)
    draw.polygon(left_sleeve, fill=cloth, outline=outline)
    draw.polygon(right_sleeve, fill=cloth, outline=outline)
    draw.ellipse([31, 115, 49, 133], fill=skin, outline=outline)
    draw.ellipse([131, 115, 149, 133], fill=skin, outline=outline)

    # Coarse source garment marks create an obvious large-scale-pattern stress case.
    draw.ellipse([67, 80, 96, 109], outline=(118, 130, 185), width=3)
    draw.ellipse([90, 114, 122, 146], outline=(118, 130, 185), width=3)
    draw.line([59, 67, 121, 165], fill=(54, 72, 140), width=2)
    draw.line([121, 67, 59, 165], fill=(54, 72, 140), width=2)

    mask = Image.new("RGBA", CANVAS_SIZE, (255, 255, 255, 255))
    mask_draw = ImageDraw.Draw(mask)
    for polygon in [shirt, left_sleeve, right_sleeve]:
        mask_draw.polygon(polygon, fill=(255, 255, 255, 0))

    fabric = Image.new("RGB", (96, 96), (180, 205, 236))
    fabric_draw = ImageDraw.Draw(fabric)
    for offset in range(-96, 160, 40):
        fabric_draw.rectangle([offset, 0, offset + 20, 96], fill=(20, 74, 145))
    fabric_draw.ellipse([18, 18, 78, 78], outline=(230, 40, 70), width=8)
    fabric_draw.ellipse([34, 34, 62, 62], fill=(245, 225, 80))
    return image, mask, fabric


def _edge_boundary_fixture() -> tuple[Image.Image, Image.Image, Image.Image]:
    image = _person_base()
    draw = ImageDraw.Draw(image)
    outline = (43, 45, 50)
    cloth = (82, 124, 112)
    skin = (222, 184, 144)
    object_color = (112, 84, 62)

    # Hands and an object sit close to garment boundaries to stress bleeding.
    draw.rectangle([22, 92, 44, 138], fill=object_color, outline=outline)
    draw.ellipse([35, 132, 53, 151], fill=skin, outline=outline)
    draw.ellipse([127, 130, 145, 149], fill=skin, outline=outline)

    jacket = [
        (56, 64),
        (79, 60),
        (90, 78),
        (101, 60),
        (125, 66),
        (134, 118),
        (112, 154),
        (68, 154),
        (46, 118),
    ]
    left_sleeve = [(56, 69), (35, 96), (47, 126), (66, 88)]
    right_sleeve = [(124, 70), (144, 96), (134, 126), (114, 88)]
    for polygon in [jacket, left_sleeve, right_sleeve]:
        draw.polygon(polygon, fill=cloth, outline=outline)
    draw.line([90, 78, 90, 154], fill=(35, 60, 56), width=3)
    draw.line([70, 70, 86, 93], fill=(230, 235, 232), width=3)
    draw.line([110, 70, 94, 93], fill=(230, 235, 232), width=3)

    mask = Image.new("RGBA", CANVAS_SIZE, (255, 255, 255, 255))
    mask_draw = ImageDraw.Draw(mask)
    for polygon in [jacket, left_sleeve, right_sleeve]:
        mask_draw.polygon(polygon, fill=(255, 255, 255, 0))

    fabric = Image.new("RGB", (80, 80), (246, 242, 232))
    fabric_draw = ImageDraw.Draw(fabric)
    for x in range(0, 80, 10):
        fabric_draw.line([x, 0, x, 79], fill=(30, 95, 82), width=3)
    for y in range(0, 80, 16):
        fabric_draw.line([0, y, 79, y], fill=(178, 44, 52), width=2)
    fabric_draw.rectangle([0, 0, 79, 79], outline=(50, 50, 50), width=2)
    return image, mask, fabric


def _write_fixture(spec: FixtureSpec) -> None:
    if spec.fixture_id == "pm003-large-pattern-scale":
        source, mask, fabric = _large_pattern_fixture()
    elif spec.fixture_id == "pm004-edge-boundary-stress":
        source, mask, fabric = _edge_boundary_fixture()
    else:  # pragma: no cover - guarded by static fixture list
        raise ValueError(f"Unknown fixture id: {spec.fixture_id}")

    fixture_dir = ASSET_ROOT / spec.fixture_id
    left, top, right, bottom = spec.crop_box
    crop_box = (left, top, right, bottom)
    crop_source = source.crop(crop_box)
    crop_mask = mask.crop(crop_box)

    _save_png(source, fixture_dir / "source.png")
    _save_png(mask, fixture_dir / "full_mask.png")
    _save_png(crop_source, fixture_dir / "crop_source.png")
    _save_png(crop_mask, fixture_dir / "crop_mask.png")
    _save_png(fabric, fixture_dir / "fabric_reference.png")


def main() -> int:
    for fixture in FIXTURES:
        _write_fixture(fixture)
    print("crop-only visual quality fixtures generated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
