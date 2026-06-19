from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

from PIL import Image
import pytest

from app.config import get_settings
from app.database import SessionLocal
from app.models.fabric import Fabric
from app.models.fabric_image import FabricImage


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "smoke_user_photo_preservation_route.py"
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

import smoke_user_photo_preservation_route as smoke_script  # noqa: E402


def test_route_smoke_requires_explicit_opt_in() -> None:
    with pytest.raises(smoke_script.SmokeConfigurationError, match="ALLOW_ROUTE_PRESERVATION_SMOKE"):
        smoke_script.ensure_smoke_allowed(app_env="staging", allow_value="")


@pytest.mark.parametrize("app_env", ["prod", "production", " PRODUCTION "])
def test_route_smoke_refuses_production_app_env(app_env: str) -> None:
    with pytest.raises(smoke_script.SmokeConfigurationError, match="production APP_ENV"):
        smoke_script.ensure_smoke_allowed(app_env=app_env, allow_value="true")


def test_route_smoke_allows_explicit_non_production_opt_in() -> None:
    smoke_script.ensure_smoke_allowed(app_env="staging", allow_value="true")
    smoke_script.ensure_smoke_allowed(app_env="development", allow_value="1")


def test_route_smoke_fake_provider_outputs_match_expected_preservation_cases(tmp_path: Path) -> None:
    user_photo_path = tmp_path / "source.png"
    mask_path = tmp_path / "mask.png"
    reference_path = tmp_path / "fabric.png"
    user_photo_path.write_bytes(smoke_script.synthetic_user_photo_bytes())
    mask_path.write_bytes(smoke_script.synthetic_mask_bytes())
    reference_path.write_bytes(smoke_script.synthetic_user_photo_bytes())

    good = smoke_script.fake_provider_for_case("good")(
        str(user_photo_path),
        str(reference_path),
        "A clothing edit mask is provided",
        str(mask_path),
    )
    protected_drift = smoke_script.fake_provider_for_case("protected_drift")(
        str(user_photo_path), str(reference_path), "A clothing edit mask is provided", str(mask_path)
    )
    size_mismatch = smoke_script.fake_provider_for_case("size_mismatch")(
        str(user_photo_path), str(reference_path), "A clothing edit mask is provided", str(mask_path)
    )

    good_path = _write_bytes(tmp_path / "good.png", good)
    protected_path = _write_bytes(tmp_path / "protected.png", protected_drift)
    mismatch_path = _write_bytes(tmp_path / "mismatch.png", size_mismatch)

    with (
        Image.open(user_photo_path) as source,
        Image.open(mask_path) as mask,
        Image.open(good_path) as good_image,
        Image.open(protected_path) as protected_image,
        Image.open(mismatch_path) as mismatch_image,
    ):
        assert good_image.size == source.size
        assert protected_image.size == source.size
        assert mismatch_image.size != source.size
        assert mask.mode == "RGBA"
        assert mask.getchannel("A").getextrema()[0] == 0


def test_route_smoke_fake_provider_requires_mask_path(tmp_path: Path) -> None:
    user_photo_path = tmp_path / "source.png"
    reference_path = tmp_path / "fabric.png"
    user_photo_path.write_bytes(smoke_script.synthetic_user_photo_bytes())
    reference_path.write_bytes(smoke_script.synthetic_user_photo_bytes())

    with pytest.raises(RuntimeError, match="requires a valid mask path"):
        smoke_script.fake_provider_for_case("good")(
            str(user_photo_path), str(reference_path), "A clothing edit mask is provided", None
        )


def test_route_smoke_script_prints_non_secret_error_when_not_opted_in() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--fabric-id", "00000000-0000-0000-0000-000000000000"],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 2
    payload = json.loads(result.stderr)
    assert payload["passes"] is False
    assert "ALLOW_ROUTE_PRESERVATION_SMOKE" in payload["error"]
    assert "BOT_INTERNAL_TOKEN" not in result.stderr
    assert "OPENAI_API_KEY" not in result.stderr


def test_route_smoke_run_smoke_all_cases_exercises_generation_route(client) -> None:
    fabric_id = _create_published_fabric_with_reference()

    report = smoke_script.run_smoke(fabric_id=fabric_id, cases=list(smoke_script.SMOKE_CASES))

    assert report["passes"] is True
    assert report["provider"] == "deterministic_fake_in_process"
    assert report["openai_invoked"] is False
    assert report["network_provider_invoked"] is False

    cases = {case["case"]: case for case in report["cases"]}
    assert set(cases) == {"good", "protected_drift", "size_mismatch"}
    assert cases["good"]["http_status"] == 201
    assert cases["good"]["generation_status"] == "completed"
    assert cases["good"]["result_image_url_present"] is True
    assert cases["good"]["mask_image_url_present"] is True
    assert cases["good"]["provider_calls"] == 1
    assert cases["good"]["passed"] is True
    for case_name in ["protected_drift", "size_mismatch"]:
        assert cases[case_name]["http_status"] == 201
        assert cases[case_name]["generation_status"] == "failed"
        assert cases[case_name]["result_image_url_present"] is False
        assert cases[case_name]["mask_image_url_present"] is True
        assert cases[case_name]["provider_calls"] == 1
        assert cases[case_name]["passed"] is True
        assert cases[case_name]["error_message_category"] == "preservation_guardrail"


def _create_published_fabric_with_reference() -> str:
    image_url = f"/uploads/fabrics/{uuid4().hex}-texture.png"
    upload_path = get_settings().upload_dir / image_url.removeprefix("/uploads/")
    upload_path.parent.mkdir(parents=True, exist_ok=True)
    upload_path.write_bytes(smoke_script.synthetic_user_photo_bytes())

    with SessionLocal() as db:
        fabric = Fabric(
            sku=f"ROUTE-SMOKE-{uuid4().hex[:10]}",
            name="Route smoke fabric",
            category="test",
            price_per_meter=100,
            stock_status="in_stock",
            description_for_gpt="Synthetic route-level smoke fabric.",
            status="published",
        )
        db.add(fabric)
        db.commit()
        db.refresh(fabric)
        db.add(FabricImage(fabric_id=fabric.id, image_url=image_url, image_type="texture", sort_order=0))
        db.commit()
        return str(fabric.id)


def _write_bytes(path: Path, content: bytes) -> Path:
    path.write_bytes(content)
    return path
