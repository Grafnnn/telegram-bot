"""Unit tests for the safe fabric import preview helper."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "import_fabrics_from_viliamsk.py"

spec = importlib.util.spec_from_file_location("fabric_import_tool", SCRIPT_PATH)
fabric_import_tool = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = fabric_import_tool
spec.loader.exec_module(fabric_import_tool)


RawFabricItem = fabric_import_tool.RawFabricItem


def test_parse_price_handles_russian_price_text() -> None:
    assert fabric_import_tool.parse_price("2 500,50 ₽ / м") == 2500.5
    assert fabric_import_tool.parse_price("от 1200 RUB") == 1200.0
    assert fabric_import_tool.parse_price("price unknown") is None


def test_normalize_raw_item_keeps_missing_fields_empty_and_warns() -> None:
    item = RawFabricItem(
        title="  Шелк молочный  ",
        price_text="2 500 ₽",
        description_text=" Натуральный шелк. ",
        image_urls=["https://example.test/silk.jpg"],
        source_url="https://example.test/fabric/silk",
    )

    result = fabric_import_tool.normalize_raw_item(item)

    assert result["normalized"]["name"] == "Шелк молочный"
    assert result["normalized"]["sku"] is None
    assert result["normalized"]["category"] is None
    assert result["normalized"]["price_per_meter"] == 2500.0
    assert result["normalized"]["stock_status"] == "unknown"
    assert "missing sku" in result["warnings"]
    assert "missing category" in result["warnings"]


def test_build_preview_deduplicates_by_sku_and_preserves_source_url() -> None:
    first = RawFabricItem(
        title="Fabric A",
        price_text="1000",
        image_urls=["https://example.test/a.jpg"],
        source_url="https://example.test/a",
        sku="SKU-1",
        category="silk",
    )
    duplicate = RawFabricItem(
        title="Fabric A duplicate",
        price_text="1100",
        image_urls=["https://example.test/a2.jpg"],
        source_url="https://example.test/a2",
        sku="SKU-1",
        category="silk",
    )

    preview = fabric_import_tool.build_preview([first, duplicate], "https://example.test/", limit=10)

    assert preview["summary"]["raw_items"] == 2
    assert preview["summary"]["preview_items"] == 1
    assert preview["summary"]["duplicates_skipped"] == 1
    assert preview["items"][0]["source_url"] == "https://example.test/a"
    assert preview["items"][0]["images"][0]["image_type"] == "main"


def test_raw_items_from_json_supports_wrapper_items() -> None:
    data = {
        "items": [
            {
                "raw": {
                    "title": "Cotton",
                    "price_text": "900",
                    "source_url": "/product/cotton",
                    "image_urls": ["/uploads/cotton.jpg"],
                    "sku": "COT-1",
                    "category": "cotton",
                }
            }
        ]
    }

    items = fabric_import_tool.raw_items_from_json(data, "https://example.test/catalog/")

    assert len(items) == 1
    assert items[0].title == "Cotton"
    assert items[0].source_url == "https://example.test/product/cotton"
    assert items[0].image_urls == ["https://example.test/uploads/cotton.jpg"]


def test_raw_items_from_json_ld_product_extracts_offer_price_and_images() -> None:
    data = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": "Linen",
        "sku": "LIN-1",
        "category": "linen",
        "description": "Light linen.",
        "image": ["/linen.jpg"],
        "url": "/product/linen",
        "offers": {"price": "1900", "priceCurrency": "RUB"},
    }

    items = fabric_import_tool.raw_items_from_json(data, "https://example.test/catalog/")

    assert len(items) == 1
    assert items[0].title == "Linen"
    assert items[0].price_text == "1900 RUB"
    assert items[0].image_urls == ["https://example.test/linen.jpg"]


def test_fabric_payload_rejects_unapproved_unknown_stock_status() -> None:
    item = {
        "normalized": {
            "sku": "FAB-1",
            "name": "Fabric",
            "category": "silk",
            "stock_status": "unknown",
        }
    }

    try:
        fabric_import_tool.fabric_payload_from_approved(item, "draft")
    except fabric_import_tool.SafeImportError as exc:
        assert "invalid stock_status" in str(exc)
    else:
        raise AssertionError("unknown stock_status should require human approval before import")
