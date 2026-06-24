#!/usr/bin/env python3
"""Validate a user-photo preset mask locally without calling an image provider."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def create_visible_inner_tshirt_fixture(path: Path) -> None:
    """Create a synthetic open-overshirt photo that passes the narrow preset."""

    width, height = 768, 1024
    image = Image.new("RGB", (width, height), (38, 44, 50))
    draw = ImageDraw.Draw(image)

    # Mirror/selfie-like scene: background frame, face/skin, open overshirt,
    # central light inner T-shirt, phone, and hands. No real person/photo data.
    draw.rectangle((0, 820, width - 1, height - 1), fill=(56, 56, 58))
    draw.rectangle((90, 90, 678, 920), outline=(90, 95, 100), width=8)
    draw.ellipse((318, 92, 450, 224), fill=(198, 150, 120), outline=(40, 40, 40), width=3)
    draw.rectangle((300, 224, 468, 300), fill=(198, 150, 120))
    draw.polygon(
        [(292, 300), (476, 300), (540, 505), (492, 825), (276, 825), (228, 505)],
        fill=(232, 231, 224),
        outline=(120, 120, 115),
    )
    draw.polygon([(195, 290), (306, 260), (292, 825), (145, 815)], fill=(30, 126, 70), outline=(20, 85, 50))
    draw.polygon([(573, 290), (462, 260), (476, 825), (623, 815)], fill=(30, 126, 70), outline=(20, 85, 50))
    draw.ellipse((488, 640, 620, 755), fill=(198, 150, 120), outline=(40, 40, 40))
    draw.ellipse((140, 455, 235, 590), fill=(198, 150, 120), outline=(40, 40, 40))
    draw.rectangle((520, 438, 582, 625), fill=(18, 18, 20))

    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG")


def run_preflight(image_path: Path, preset: str) -> dict[str, object]:
    from app.config import get_settings
    from app.services.mask_service import (
        EDITABLE_ALPHA_THRESHOLD,
        _preset_mask_bytes,
        save_mask_image,
        validate_edit_mask,
    )
    from app.services.storage_service import resolve_upload_path

    with tempfile.TemporaryDirectory(prefix="tryon-mask-preflight-") as temp_dir:
        upload_root = Path(temp_dir)
        os.environ["UPLOAD_DIR"] = str(upload_root)
        get_settings.cache_clear()
        (upload_root / "user-photos").mkdir(parents=True, exist_ok=True)
        (upload_root / "user-photo-masks").mkdir(parents=True, exist_ok=True)

        copied_photo = upload_root / "user-photos" / "source.png"
        with Image.open(image_path) as source:
            source.convert("RGB").save(copied_photo, format="PNG")
            source_size = source.size

        mask_url = save_mask_image(_preset_mask_bytes(copied_photo, preset))
        mask_path = resolve_upload_path(mask_url)
        readiness = validate_edit_mask(mask_path, copied_photo)

        settings = get_settings()
        return {
            "ready": readiness.ready,
            "preset": preset,
            "image_name": image_path.name,
            "image_size": list(source_size),
            "mask_size": [readiness.width, readiness.height],
            "base_size": [readiness.base_width, readiness.base_height],
            "coverage_percent": readiness.coverage_percent,
            "min_coverage_percent": settings.user_photo_mask_min_coverage_percent,
            "max_coverage_percent": settings.user_photo_mask_max_coverage_percent,
            "editable_alpha_threshold": EDITABLE_ALPHA_THRESHOLD,
            "error_code": readiness.error_code,
            "error_message": readiness.error_message,
            "provider_called": False,
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preflight a user-photo mask preset without provider/OpenAI calls.",
    )
    parser.add_argument("image", nargs="?", type=Path, help="Photo path to validate.")
    parser.add_argument("--preset", default="visible_inner_tshirt", help="Mask preset to validate.")
    parser.add_argument(
        "--write-synthetic-visible-inner-tshirt",
        type=Path,
        help="Write a synthetic open-overshirt fixture to this path before validation.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    image_path = args.image
    if args.write_synthetic_visible_inner_tshirt:
        create_visible_inner_tshirt_fixture(args.write_synthetic_visible_inner_tshirt)
        image_path = args.write_synthetic_visible_inner_tshirt
    if image_path is None:
        raise SystemExit("image path is required unless --write-synthetic-visible-inner-tshirt is used")
    if not image_path.exists():
        raise SystemExit(f"image does not exist: {image_path}")

    report = run_preflight(image_path, args.preset)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
