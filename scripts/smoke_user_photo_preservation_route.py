#!/usr/bin/env python3
"""Run a safe route-level preservation guardrail smoke for Issue #45.

This script exercises the FastAPI ``/api/generations/user-photo`` route through
``TestClient`` while replacing the user-photo provider call with deterministic
local fake outputs. It never calls OpenAI or another network provider.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from io import BytesIO
import json
import os
from pathlib import Path
import sys
from typing import Any, Callable, Iterator

from PIL import Image, ImageDraw


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


ALLOW_ENV_NAME = "ALLOW_ROUTE_PRESERVATION_SMOKE"
FORBIDDEN_APP_ENVS = {"prod", "production"}
SMOKE_CASES = ("good", "protected_drift", "size_mismatch")


class SmokeConfigurationError(RuntimeError):
    """Raised when the smoke command is not explicitly safe to run."""


@dataclass(frozen=True)
class SmokeCaseResult:
    """Non-secret route-level smoke result for one fake provider output."""

    case: str
    http_status: int
    generation_status: str | None
    result_image_url_present: bool
    mask_image_url_present: bool
    provider_calls: int
    passed: bool
    error_message_present: bool
    error_message_category: str | None


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Exercise /api/generations/user-photo with deterministic fake provider outputs. "
            "Requires explicit opt-in and refuses production APP_ENV."
        )
    )
    parser.add_argument("--fabric-id", required=True, help="Published AI-ready staging fabric UUID.")
    parser.add_argument(
        "--case",
        choices=[*SMOKE_CASES, "all"],
        default="all",
        help="Smoke case to run. Default: all.",
    )
    parser.add_argument("--json-output", type=Path, help="Optional path for a JSON summary report.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    return parser.parse_args(argv)


def ensure_smoke_allowed(*, app_env: str | None = None, allow_value: str | None = None) -> None:
    """Require explicit smoke opt-in and refuse production-like runtime names."""

    resolved_app_env = (app_env if app_env is not None else os.getenv("APP_ENV", "development")).strip().lower()
    if resolved_app_env in FORBIDDEN_APP_ENVS:
        raise SmokeConfigurationError("Route-level preservation smoke refuses to run in production APP_ENV.")

    resolved_allow = (allow_value if allow_value is not None else os.getenv(ALLOW_ENV_NAME, "")).strip().lower()
    if resolved_allow not in {"1", "true", "yes", "on"}:
        raise SmokeConfigurationError(f"Set {ALLOW_ENV_NAME}=true to run this explicit smoke command.")


def synthetic_user_photo_bytes(size: tuple[int, int] = (300, 300)) -> bytes:
    """Return a synthetic, non-user photo with protected face/background regions."""

    image = Image.new("RGB", size, (236, 238, 240))
    draw = ImageDraw.Draw(image)
    width, height = size
    draw.rectangle((0, int(height * 0.78), width, height), fill=(220, 222, 225))
    draw.ellipse(
        (int(width * 0.42), int(height * 0.08), int(width * 0.58), int(height * 0.24)),
        fill=(214, 178, 146),
        outline=(50, 50, 50),
    )
    draw.rectangle(
        (int(width * 0.35), int(height * 0.28), int(width * 0.65), int(height * 0.68)),
        fill=(44, 88, 168),
        outline=(40, 40, 40),
    )
    draw.rectangle(
        (int(width * 0.22), int(height * 0.32), int(width * 0.34), int(height * 0.62)),
        fill=(214, 178, 146),
        outline=(50, 50, 50),
    )
    draw.rectangle(
        (int(width * 0.66), int(height * 0.32), int(width * 0.78), int(height * 0.62)),
        fill=(214, 178, 146),
        outline=(50, 50, 50),
    )
    return _image_to_png_bytes(image)


def synthetic_mask_bytes(size: tuple[int, int] = (300, 300)) -> bytes:
    """Return a valid PNG alpha mask where transparent pixels are clothing."""

    width, height = size
    mask = Image.new("RGBA", size, (0, 0, 0, 255))
    draw = ImageDraw.Draw(mask)
    draw.rectangle(
        (int(width * 0.35), int(height * 0.28), int(width * 0.65), int(height * 0.68)),
        fill=(0, 0, 0, 0),
    )
    return _image_to_png_bytes(mask)


def _image_to_png_bytes(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _provider_output_changing_only_mask(user_photo_path: str, mask_image_path: str) -> bytes:
    with Image.open(user_photo_path) as base_image, Image.open(mask_image_path) as mask_image:
        candidate = base_image.convert("RGB")
        alpha = mask_image.convert("RGBA").getchannel("A")
        pixels = candidate.load()
        for y in range(candidate.height):
            for x in range(candidate.width):
                if alpha.getpixel((x, y)) < 128:
                    pixels[x, y] = (180, 30, 180)
    return _image_to_png_bytes(candidate)


def _provider_output_changing_protected_region(user_photo_path: str) -> bytes:
    with Image.open(user_photo_path) as base_image:
        candidate = base_image.convert("RGB")
    draw = ImageDraw.Draw(candidate)
    draw.rectangle((0, 0, candidate.width - 1, max(1, candidate.height // 5)), fill=(250, 20, 20))
    return _image_to_png_bytes(candidate)


def _provider_output_size_mismatch() -> bytes:
    return _image_to_png_bytes(Image.new("RGB", (1, 1), (20, 120, 180)))


def fake_provider_for_case(case: str) -> Callable[[str, str, str, str | None], bytes]:
    """Build a deterministic fake provider for one route-level smoke case."""

    if case not in SMOKE_CASES:
        raise ValueError(f"Unknown smoke case: {case}")

    def fake_generate(
        user_photo_path: str,
        fabric_reference_path: str,
        prompt: str,
        mask_image_path: str | None = None,
    ) -> bytes:
        if not Path(user_photo_path).is_file():
            raise RuntimeError("Synthetic user photo upload is missing.")
        if not Path(fabric_reference_path).is_file():
            raise RuntimeError("Selected fabric reference upload is missing.")
        if mask_image_path is None or not Path(mask_image_path).is_file():
            raise RuntimeError("Smoke fake provider requires a valid mask path.")
        if "A clothing edit mask is provided" not in prompt:
            raise RuntimeError("Route did not build a masked user-photo prompt.")
        if case == "good":
            return _provider_output_changing_only_mask(user_photo_path, mask_image_path)
        if case == "protected_drift":
            return _provider_output_changing_protected_region(user_photo_path)
        return _provider_output_size_mismatch()

    return fake_generate


def _error_category(payload: dict[str, Any]) -> str | None:
    message = payload.get("error_message")
    if not isinstance(message, str) or not message:
        return None
    if "сохранить исходное фото" in message:
        return "preservation_guardrail"
    return "other"


def _case_passes(case: str, response_status: int, payload: dict[str, Any], provider_calls: int) -> bool:
    if response_status != 201 or provider_calls != 1:
        return False
    generation_status = payload.get("status")
    result_present = bool(payload.get("result_image_url"))
    mask_present = bool(payload.get("mask_image_url"))
    if case == "good":
        return generation_status == "completed" and result_present and mask_present
    return generation_status == "failed" and not result_present and mask_present


@contextmanager
def _patched_user_photo_provider(fake_generate: Callable[[str, str, str, str | None], bytes]) -> Iterator[None]:
    from app.api.routes import generations as generation_routes

    original = generation_routes.image_generation_service.generate_fabric_on_user_photo
    generation_routes.image_generation_service.generate_fabric_on_user_photo = fake_generate
    try:
        yield
    finally:
        generation_routes.image_generation_service.generate_fabric_on_user_photo = original


def _run_case(client: Any, *, fabric_id: str, case: str, bot_internal_token: str) -> SmokeCaseResult:
    provider_calls = 0
    fake_generate = fake_provider_for_case(case)

    def counted_fake_generate(
        user_photo_path: str,
        fabric_reference_path: str,
        prompt: str,
        mask_image_path: str | None = None,
    ) -> bytes:
        nonlocal provider_calls
        provider_calls += 1
        return fake_generate(user_photo_path, fabric_reference_path, prompt, mask_image_path)

    with _patched_user_photo_provider(counted_fake_generate):
        response = client.post(
            "/api/generations/user-photo",
            headers={"X-Bot-Token": bot_internal_token},
            data={"fabric_id": fabric_id},
            files={
                "photo": ("issue45-source.png", synthetic_user_photo_bytes(), "image/png"),
                "mask": ("issue45-mask.png", synthetic_mask_bytes(), "image/png"),
            },
        )
    payload = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
    return SmokeCaseResult(
        case=case,
        http_status=response.status_code,
        generation_status=payload.get("status"),
        result_image_url_present=bool(payload.get("result_image_url")),
        mask_image_url_present=bool(payload.get("mask_image_url")),
        provider_calls=provider_calls,
        passed=_case_passes(case, response.status_code, payload, provider_calls),
        error_message_present=bool(payload.get("error_message")),
        error_message_category=_error_category(payload),
    )


def run_smoke(*, fabric_id: str, cases: list[str]) -> dict[str, Any]:
    """Run the safe route-level smoke against the configured backend app."""

    os.environ["USER_PHOTO_MASK_MODE"] = "provided"
    os.environ["USER_PHOTO_REQUIRE_MASK_FOR_STRICT_EDIT"] = "true"

    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.main import app

    get_settings.cache_clear()
    settings = get_settings()
    if not settings.is_bot_internal_token_configured:
        raise SmokeConfigurationError("BOT_INTERNAL_TOKEN must be configured for route-level smoke.")

    results: list[SmokeCaseResult] = []
    with TestClient(app) as client:
        for case in cases:
            results.append(
                _run_case(
                    client,
                    fabric_id=fabric_id,
                    case=case,
                    bot_internal_token=settings.bot_internal_token,
                )
            )

    return {
        "passes": all(result.passed for result in results),
        "provider": "deterministic_fake_in_process",
        "openai_invoked": False,
        "network_provider_invoked": False,
        "mask_mode": settings.user_photo_mask_mode,
        "preservation_check_enabled": settings.user_photo_preservation_check_enabled,
        "preservation_thresholds": {
            "max_mean_delta": settings.user_photo_preservation_max_mean_delta,
            "max_changed_pixel_percent": settings.user_photo_preservation_max_changed_pixel_percent,
            "pixel_delta_threshold": settings.user_photo_preservation_pixel_delta_threshold,
        },
        "app_level_mutations": ["generation_records", "synthetic_uploads", "successful_case_generated_upload"],
        "cases": [asdict(result) for result in results],
    }


def write_report(report: dict[str, Any], *, output: Path | None, pretty: bool) -> str:
    text = json.dumps(report, ensure_ascii=False, indent=2 if pretty else None, sort_keys=True)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
    return text


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        ensure_smoke_allowed()
        cases = list(SMOKE_CASES) if args.case == "all" else [args.case]
        report = run_smoke(fabric_id=args.fabric_id, cases=cases)
        print(write_report(report, output=args.json_output, pretty=args.pretty))
        return 0 if report["passes"] else 1
    except SmokeConfigurationError as exc:
        print(json.dumps({"passes": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
