#!/usr/bin/env python3
"""Safe fabric preview/import helper for viliamsk.ru.

Default mode is dry-run preview generation. Database writes are never performed
directly; approved imports use the existing admin API so auth, validation,
upload checks, and rate limits remain in the application path.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
import json
import mimetypes
import os
from pathlib import Path
import re
import sys
from typing import Any
from urllib import robotparser
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from uuid import uuid4


DEFAULT_SOURCE_URL = "https://viliamsk.ru/"
DEFAULT_LIMIT = 10
DEFAULT_OUTPUT = "/tmp/fabrics_preview.json"
DEFAULT_ADMIN_PASSWORD_ENV = "ADMIN_PASSWORD_FOR_IMPORT"
DEFAULT_GPT_MODEL = "gpt-4o-mini"
SAFE_USER_AGENT = "fashion-bot-fabric-preview/0.1"
REQUEST_TIMEOUT_SECONDS = 20
ALLOWED_STATUSES = {"draft", "published", "hidden", "archived"}
ALLOWED_STOCK_STATUSES = {"in_stock", "preorder", "out_of_stock"}

GPT_NORMALIZATION_SCHEMA: dict[str, Any] = {
    "name": "fabric_normalization",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "title": {"type": "string"},
            "category": {"type": "string"},
            "color": {"type": "string"},
            "composition": {"type": ["string", "null"]},
            "width_cm": {"type": ["number", "null"]},
            "density_g_m2": {"type": ["number", "null"]},
            "price": {"type": ["number", "null"]},
            "description_short": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}},
            "source_url": {"type": "string"},
        },
        "required": [
            "title",
            "category",
            "color",
            "composition",
            "width_cm",
            "density_g_m2",
            "price",
            "description_short",
            "tags",
            "source_url",
        ],
    },
}


class SafeImportError(RuntimeError):
    """Raised for expected safe-stop conditions."""


@dataclass
class RawFabricItem:
    title: str | None = None
    price_text: str | None = None
    description_text: str | None = None
    image_urls: list[str] = field(default_factory=list)
    source_url: str = ""
    sku: str | None = None
    category: str | None = None
    composition: str | None = None


class ProductHTMLParser(HTMLParser):
    """Extract JSON-LD product blocks from saved catalog/product HTML."""

    def __init__(self) -> None:
        super().__init__()
        self._in_json_ld = False
        self._script_chunks: list[str] = []
        self.json_ld_blocks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "script":
            return
        attrs_dict = {name.lower(): value for name, value in attrs}
        if (attrs_dict.get("type") or "").lower() == "application/ld+json":
            self._in_json_ld = True
            self._script_chunks = []

    def handle_data(self, data: str) -> None:
        if self._in_json_ld:
            self._script_chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script" and self._in_json_ld:
            self.json_ld_blocks.append("".join(self._script_chunks).strip())
            self._in_json_ld = False
            self._script_chunks = []


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def parse_price(value: str | int | float | Decimal | None) -> float | None:
    """Parse a Russian price string into a JSON-safe number."""

    if value is None:
        return None
    if isinstance(value, (int, float, Decimal)):
        return float(value)
    text = str(value).replace("\xa0", " ")
    match = re.search(r"(\d[\d\s]*(?:[,.]\d{1,2})?)", text)
    if not match:
        return None
    number = match.group(1).replace(" ", "").replace(",", ".")
    try:
        return float(Decimal(number))
    except InvalidOperation:
        return None


def normalize_url(value: str | None, base_url: str) -> str | None:
    if not value:
        return None
    return urljoin(base_url, value)


def is_js_cookie_gate(html: str) -> bool:
    lowered = html.lower()
    return "document.cookie" in lowered and "location.reload" in lowered


def check_robots_allowed(source_url: str) -> None:
    robots_url = urljoin(source_url, "/robots.txt")
    parser = robotparser.RobotFileParser()
    parser.set_url(robots_url)
    try:
        parser.read()
    except Exception as exc:  # pragma: no cover - depends on network
        raise SafeImportError(f"Could not read robots.txt before live fetch: {exc}") from exc
    if not parser.can_fetch(SAFE_USER_AGENT, source_url):
        raise SafeImportError(f"robots.txt disallows fetching {source_url}")


def fetch_text(source_url: str) -> str:
    check_robots_allowed(source_url)
    request = Request(
        source_url,
        headers={
            "User-Agent": SAFE_USER_AGENT,
            "Accept": "text/html,application/json;q=0.9,*/*;q=0.5",
        },
    )
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            content = response.read()
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise SafeImportError(f"Live source fetch failed safely: {type(exc).__name__}") from exc
    html = content.decode("utf-8", errors="replace")
    if is_js_cookie_gate(html):
        raise SafeImportError(
            "Live source appears to require a JavaScript/cookie reload gate; "
            "not bypassing it. Use --input-html or --input-json with an approved export."
        )
    return html


def iter_product_objects(value: Any) -> list[dict[str, Any]]:
    products: list[dict[str, Any]] = []
    if isinstance(value, dict):
        item_type = value.get("@type") or value.get("type")
        types = item_type if isinstance(item_type, list) else [item_type]
        if any(str(item).lower() == "product" for item in types):
            products.append(value)
        for nested in value.values():
            products.extend(iter_product_objects(nested))
    elif isinstance(value, list):
        for item in value:
            products.extend(iter_product_objects(item))
    return products


def images_from_product(product: dict[str, Any], base_url: str) -> list[str]:
    raw_images = product.get("image") or product.get("images") or []
    if isinstance(raw_images, str):
        raw_images = [raw_images]
    urls: list[str] = []
    if isinstance(raw_images, list):
        for image in raw_images:
            if isinstance(image, dict):
                image = image.get("url") or image.get("contentUrl")
            url = normalize_url(str(image), base_url) if image else None
            if url and url not in urls:
                urls.append(url)
    return urls


def price_text_from_product(product: dict[str, Any]) -> str | None:
    offers = product.get("offers")
    if isinstance(offers, list):
        offers = offers[0] if offers else None
    if isinstance(offers, dict):
        price = offers.get("price") or offers.get("lowPrice") or offers.get("highPrice")
        currency = offers.get("priceCurrency")
        if price and currency:
            return f"{price} {currency}"
        if price:
            return str(price)
    return clean_text(product.get("price"))


def raw_item_from_product(product: dict[str, Any], base_url: str) -> RawFabricItem:
    source_url = normalize_url(clean_text(product.get("url")), base_url) or base_url
    return RawFabricItem(
        title=clean_text(product.get("name")),
        price_text=price_text_from_product(product),
        description_text=clean_text(product.get("description")),
        image_urls=images_from_product(product, base_url),
        source_url=source_url,
        sku=clean_text(product.get("sku") or product.get("mpn")),
        category=clean_text(product.get("category")),
        composition=clean_text(product.get("material")),
    )


def raw_items_from_html(html: str, base_url: str) -> list[RawFabricItem]:
    parser = ProductHTMLParser()
    parser.feed(html)
    items: list[RawFabricItem] = []
    for block in parser.json_ld_blocks:
        try:
            parsed = json.loads(block)
        except json.JSONDecodeError:
            continue
        for product in iter_product_objects(parsed):
            items.append(raw_item_from_product(product, base_url))
    return items


def raw_item_from_mapping(data: dict[str, Any], base_url: str = DEFAULT_SOURCE_URL) -> RawFabricItem:
    raw = data.get("raw") if isinstance(data.get("raw"), dict) else data
    image_urls = raw.get("image_urls") or raw.get("images") or raw.get("image") or []
    if isinstance(image_urls, str):
        image_urls = [image_urls]
    return RawFabricItem(
        title=clean_text(raw.get("title") or raw.get("name")),
        price_text=clean_text(raw.get("price_text") or raw.get("price")),
        description_text=clean_text(raw.get("description_text") or raw.get("description")),
        image_urls=[
            url
            for url in (normalize_url(clean_text(image), base_url) for image in image_urls if image)
            if url
        ],
        source_url=normalize_url(clean_text(raw.get("source_url") or raw.get("url")), base_url) or base_url,
        sku=clean_text(raw.get("sku") or raw.get("article")),
        category=clean_text(raw.get("category")),
        composition=clean_text(raw.get("composition") or raw.get("material")),
    )


def raw_items_from_json(data: Any, base_url: str = DEFAULT_SOURCE_URL) -> list[RawFabricItem]:
    if isinstance(data, dict) and "items" in data:
        data = data["items"]
    if isinstance(data, dict):
        products = iter_product_objects(data)
        if products:
            return [raw_item_from_product(product, base_url) for product in products]
        return [raw_item_from_mapping(data, base_url)]
    if isinstance(data, list):
        return [raw_item_from_mapping(item, base_url) for item in data if isinstance(item, dict)]
    raise SafeImportError("Input JSON must be an object, an object with items, or a list of objects.")


def load_raw_items(args: argparse.Namespace) -> list[RawFabricItem]:
    if args.input_json:
        data = json.loads(Path(args.input_json).read_text(encoding="utf-8"))
        return raw_items_from_json(data, args.source_url)
    if args.input_html:
        html = Path(args.input_html).read_text(encoding="utf-8")
        return raw_items_from_html(html, args.source_url)
    html = fetch_text(args.source_url)
    return raw_items_from_html(html, args.source_url)


def duplicate_key(raw_item: RawFabricItem, normalized: dict[str, Any]) -> str:
    sku = normalized.get("sku") or raw_item.sku
    if sku:
        return f"sku:{sku.lower()}"
    if raw_item.source_url:
        return f"url:{raw_item.source_url.lower()}"
    name = normalized.get("name") or raw_item.title or ""
    return f"name:{name.lower()}"


def normalize_raw_item(raw_item: RawFabricItem, status: str = "draft") -> dict[str, Any]:
    name = clean_text(raw_item.title) or "Untitled fabric"
    description = clean_text(raw_item.description_text)
    price = parse_price(raw_item.price_text)
    warnings: list[str] = []
    if not raw_item.sku:
        warnings.append("missing sku")
    if not raw_item.category:
        warnings.append("missing category")
    if price is None:
        warnings.append("missing price_per_meter")
    if not raw_item.image_urls:
        warnings.append("missing images")
    normalized = {
        "sku": raw_item.sku,
        "name": name,
        "category": raw_item.category,
        "composition": raw_item.composition,
        "color": None,
        "shade": None,
        "pattern": None,
        "texture": None,
        "density": None,
        "stretch": None,
        "opacity": None,
        "shine": None,
        "season": None,
        "recommended_for": None,
        "not_recommended_for": None,
        "price_per_meter": price,
        "currency": "RUB",
        "stock_status": "unknown",
        "stock_quantity": None,
        "short_description": description[:1000] if description else None,
        "full_description": description,
        "description_for_gpt": description,
        "tags": [],
        "status": status,
    }
    return {"normalized": normalized, "warnings": warnings}


def image_entries(raw_item: RawFabricItem) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for index, image_url in enumerate(raw_item.image_urls):
        entries.append(
            {
                "image_url": image_url,
                "image_type": "main" if index == 0 else "extra",
                "sort_order": index,
            }
        )
    return entries


def raw_item_to_preview(raw_item: RawFabricItem, status: str = "draft") -> dict[str, Any]:
    normalized_result = normalize_raw_item(raw_item, status)
    return {
        "raw": {
            "title": raw_item.title,
            "price_text": raw_item.price_text,
            "description_text": raw_item.description_text,
            "image_urls": raw_item.image_urls,
            "source_url": raw_item.source_url,
        },
        "normalized": normalized_result["normalized"],
        "images": image_entries(raw_item),
        "source_url": raw_item.source_url,
        "warnings": normalized_result["warnings"],
    }


def merge_gpt_enrichment(item: dict[str, Any], enrichment: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(item["normalized"])
    if clean_text(enrichment.get("title")):
        normalized["name"] = clean_text(enrichment.get("title"))
    if clean_text(enrichment.get("category")):
        normalized["category"] = clean_text(enrichment.get("category"))
    if clean_text(enrichment.get("color")):
        normalized["color"] = clean_text(enrichment.get("color"))
    if clean_text(enrichment.get("description_short")):
        normalized["short_description"] = clean_text(enrichment.get("description_short"))
    if isinstance(enrichment.get("tags"), list):
        normalized["tags"] = [tag for tag in (clean_text(item) for item in enrichment["tags"]) if tag]
    updated = dict(item)
    updated["normalized"] = normalized
    return updated


def enrich_with_gpt(item: dict[str, Any], model: str) -> dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SafeImportError("OPENAI_API_KEY is required when --use-gpt is set.")
    payload = {
        "model": model,
        "temperature": 0,
        "response_format": {"type": "json_schema", "json_schema": GPT_NORMALIZATION_SCHEMA},
        "messages": [
            {
                "role": "system",
                "content": (
                    "Normalize fabric catalog text into JSON. Use only facts present in source text. "
                    "Do not invent composition, density, width, price, stock, or availability."
                ),
            },
            {"role": "user", "content": json.dumps(item["raw"], ensure_ascii=False)},
        ],
    }
    request = Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            response_data = json.loads(response.read().decode("utf-8"))
        content = response_data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
    except (HTTPError, URLError, TimeoutError, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise SafeImportError(f"GPT enrichment failed safely: {type(exc).__name__}") from exc
    return merge_gpt_enrichment(item, parsed)


def build_preview(
    raw_items: list[RawFabricItem],
    source: str,
    limit: int = DEFAULT_LIMIT,
    status: str = "draft",
    use_gpt: bool = False,
    gpt_model: str = DEFAULT_GPT_MODEL,
) -> dict[str, Any]:
    seen: set[str] = set()
    items: list[dict[str, Any]] = []
    duplicates = 0
    for raw_item in raw_items:
        preview_item = raw_item_to_preview(raw_item, status)
        key = duplicate_key(raw_item, preview_item["normalized"])
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        if use_gpt:
            preview_item = enrich_with_gpt(preview_item, gpt_model)
        items.append(preview_item)
        if len(items) >= limit:
            break
    return {
        "source": source,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "items": items,
        "summary": {
            "raw_items": len(raw_items),
            "preview_items": len(items),
            "duplicates_skipped": duplicates,
            "dry_run": True,
        },
    }


def write_preview(preview: dict[str, Any], output_path: str) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(preview, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def list_value(value: Any) -> list[str] | None:
    if value is None or value == "":
        return None
    if isinstance(value, list):
        return [item for item in (clean_text(item) for item in value) if item]
    if isinstance(value, str):
        return [item for item in (clean_text(part) for part in value.split(",")) if item]
    return None


def fabric_payload_from_approved(item: dict[str, Any], status: str) -> dict[str, Any]:
    normalized = item.get("normalized") if isinstance(item.get("normalized"), dict) else item
    required = ["sku", "name", "category"]
    missing = [field for field in required if not clean_text(normalized.get(field))]
    if missing:
        raise SafeImportError(f"Approved item missing required fields: {', '.join(missing)}")
    stock_status = normalized.get("stock_status") or "in_stock"
    if stock_status not in ALLOWED_STOCK_STATUSES:
        raise SafeImportError("Approved item has invalid stock_status; use in_stock, preorder, or out_of_stock.")
    payload: dict[str, Any] = {
        "sku": clean_text(normalized.get("sku")),
        "name": clean_text(normalized.get("name")),
        "category": clean_text(normalized.get("category")),
        "currency": clean_text(normalized.get("currency")) or "RUB",
        "stock_status": stock_status,
        "status": status,
    }
    passthrough_fields = [
        "composition",
        "color",
        "shade",
        "pattern",
        "texture",
        "density",
        "stretch",
        "opacity",
        "shine",
        "price_per_meter",
        "stock_quantity",
        "short_description",
        "full_description",
        "description_for_gpt",
        "tags",
    ]
    for field_name in passthrough_fields:
        value = normalized.get(field_name)
        if value not in (None, "", []):
            payload[field_name] = value
    for field_name in ["season", "recommended_for", "not_recommended_for"]:
        value = list_value(normalized.get(field_name))
        if value:
            payload[field_name] = value
    return payload


def api_request_json(
    base_url: str,
    path: str,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    token: str | None = None,
) -> dict[str, Any] | None:
    url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json", "User-Agent": SAFE_USER_AGENT}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else None
    except HTTPError as exc:
        raise SafeImportError(f"Admin API request failed with status {exc.code}") from exc
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise SafeImportError(f"Admin API request failed safely: {type(exc).__name__}") from exc


def login_admin(base_url: str, email: str, password_env_name: str) -> str:
    password = os.getenv(password_env_name)
    if not password:
        raise SafeImportError(f"{password_env_name} must be set for --import-approved.")
    response = api_request_json(base_url, "/auth/login", "POST", {"email": email, "password": password})
    token = response.get("access_token") if isinstance(response, dict) else None
    if not token:
        raise SafeImportError("Admin login did not return an access token.")
    return token


def read_approved_items(path: str) -> list[dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return [item for item in data["items"] if isinstance(item, dict)]
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    raise SafeImportError("Approved JSON must be a list or an object with an items list.")


def fetch_binary(url: str) -> tuple[bytes, str, str]:
    request = Request(url, headers={"User-Agent": SAFE_USER_AGENT})
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            content = response.read()
            content_type = response.headers.get("content-type") or mimetypes.guess_type(url)[0] or "application/octet-stream"
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise SafeImportError(f"Image download failed safely: {type(exc).__name__}") from exc
    filename = Path(urlparse(url).path).name or f"image-{uuid4().hex}"
    return content, filename, content_type


def multipart_body(fields: dict[str, str], file_field: str, filename: str, content_type: str, content: bytes) -> tuple[bytes, str]:
    boundary = f"----fabric-import-{uuid4().hex}"
    chunks: list[bytes] = []
    for key, value in fields.items():
        chunks.append(f"--{boundary}\r\n".encode())
        chunks.append(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode())
        chunks.append(str(value).encode())
        chunks.append(b"\r\n")
    chunks.append(f"--{boundary}\r\n".encode())
    chunks.append(
        f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'.encode()
    )
    chunks.append(f"Content-Type: {content_type}\r\n\r\n".encode())
    chunks.append(content)
    chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), boundary


def upload_image(base_url: str, token: str, fabric_id: str, image: dict[str, Any]) -> dict[str, Any] | None:
    if image.get("file_path"):
        path = Path(str(image["file_path"]))
        content = path.read_bytes()
        filename = path.name
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    elif image.get("image_url"):
        content, filename, content_type = fetch_binary(str(image["image_url"]))
    else:
        return None
    fields = {
        "image_type": str(image.get("image_type") or "extra"),
        "sort_order": str(image.get("sort_order") or 0),
    }
    body, boundary = multipart_body(fields, "file", filename, content_type, content)
    url = f"{base_url.rstrip('/')}/admin/fabrics/{fabric_id}/images"
    request = Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": SAFE_USER_AGENT,
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise SafeImportError(f"Image upload failed with status {exc.code}") from exc
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise SafeImportError(f"Image upload failed safely: {type(exc).__name__}") from exc


def import_approved(args: argparse.Namespace) -> int:
    if not args.approved_json:
        raise SafeImportError("--approved-json is required with --import-approved.")
    if not args.admin_api_base_url or not args.admin_email:
        raise SafeImportError("--admin-api-base-url and --admin-email are required with --import-approved.")
    token = login_admin(args.admin_api_base_url, args.admin_email, args.admin_password_env)
    items = read_approved_items(args.approved_json)
    created = 0
    skipped = 0
    for item in items:
        try:
            payload = fabric_payload_from_approved(item, args.status)
            fabric = api_request_json(args.admin_api_base_url, "/admin/fabrics", "POST", payload, token)
            fabric_id = str(fabric["id"])
            created += 1
            print(f"created fabric sku={payload['sku']} name={payload['name']} id={fabric_id}")
            for image in item.get("images") or []:
                if isinstance(image, dict):
                    upload_image(args.admin_api_base_url, token, fabric_id, image)
        except SafeImportError as exc:
            skipped += 1
            print(f"skipped approved item: {exc}", file=sys.stderr)
    print(f"approved import complete created={created} skipped={skipped}")
    return 0 if skipped == 0 else 1


def run_dry_run(args: argparse.Namespace) -> int:
    raw_items = load_raw_items(args)
    preview = build_preview(
        raw_items,
        source=args.source_url,
        limit=args.limit,
        status=args.status,
        use_gpt=args.use_gpt,
        gpt_model=args.gpt_model,
    )
    write_preview(preview, args.output)
    print(
        "dry-run preview written "
        f"output={args.output} items={len(preview['items'])} duplicates_skipped={preview['summary']['duplicates_skipped']}"
    )
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Safely preview/import fabrics from viliamsk.ru.")
    parser.add_argument("--source-url", default=DEFAULT_SOURCE_URL)
    parser.add_argument("--dry-run", action="store_true", help="Generate preview only. This is the default.")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--input-html")
    parser.add_argument("--input-json")
    parser.add_argument("--approved-json")
    parser.add_argument("--admin-api-base-url")
    parser.add_argument("--admin-email")
    parser.add_argument("--admin-password-env", default=DEFAULT_ADMIN_PASSWORD_ENV)
    parser.add_argument("--import-approved", action="store_true")
    parser.add_argument("--status", choices=sorted(ALLOWED_STATUSES), default="draft")
    parser.add_argument("--use-gpt", action="store_true")
    parser.add_argument("--gpt-model", default=DEFAULT_GPT_MODEL)
    args = parser.parse_args(argv)
    if args.limit < 1:
        parser.error("--limit must be at least 1")
    if args.import_approved and args.dry_run:
        parser.error("--dry-run and --import-approved cannot be combined")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.import_approved:
            return import_approved(args)
        return run_dry_run(args)
    except SafeImportError as exc:
        print(f"safe stop: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
