# Fabric Import Runbook

This importer is intentionally conservative. It creates preview files first and
only writes approved rows through the existing admin API. It does not write
directly to the database.

## Safety Model

- Default mode is dry-run preview.
- Live fetch checks `robots.txt` before requesting a source URL.
- The script does not bypass authorization, JavaScript cookie gates, or anti-bot
  controls.
- The script does not print passwords, tokens, JWTs, database URLs, or OpenAI
  keys.
- Imported fabrics are created as `draft` by default.
- `source_url` is kept in preview/approved JSON only. The current database schema
  has no `source_url` column.
- GPT enrichment is optional and disabled by default.

## Dry-Run Preview

```bash
python3 scripts/import_fabrics_from_viliamsk.py \
  --source-url https://viliamsk.ru/ \
  --dry-run \
  --limit 10 \
  --output /tmp/fabrics_preview.json
```

If the live site requires a JavaScript/cookie reload gate, the script stops
safely. Use local file mode with an approved export instead.

## Local HTML Mode

```bash
python3 scripts/import_fabrics_from_viliamsk.py \
  --input-html /tmp/viliamsk_catalog.html \
  --dry-run \
  --limit 10 \
  --output /tmp/fabrics_preview.json
```

## Local JSON Mode

```bash
python3 scripts/import_fabrics_from_viliamsk.py \
  --input-json /tmp/viliamsk_raw_export.json \
  --dry-run \
  --limit 10 \
  --output /tmp/fabrics_preview.json
```

## Preview Review

Review `/tmp/fabrics_preview.json` manually before import. Required fields for a
draft admin API create are:

- `sku`
- `name`
- `category`

For later publication in the admin UI, the card also needs:

- `price_per_meter`
- valid `stock_status`: `in_stock`, `preorder`, or `out_of_stock`
- `description_for_gpt`
- main image
- texture image

The preview may contain `"stock_status": "unknown"` when the source does not
provide availability. Change this to a valid admin API value in the approved JSON
before import.

## Approved Import To Staging

Do not run this until an operator has reviewed and approved the JSON file.

```bash
ADMIN_PASSWORD_FOR_IMPORT='<password-not-committed>' \
python3 scripts/import_fabrics_from_viliamsk.py \
  --approved-json /tmp/fabrics_approved.json \
  --import-approved \
  --status draft \
  --admin-api-base-url https://telegram-bot-backend-staging.onrender.com/api \
  --admin-email '<admin-email>'
```

The script authenticates with:

```text
POST /api/auth/login
```

Then it creates fabrics through:

```text
POST /api/admin/fabrics
```

If approved image entries contain `image_url` or `file_path`, images are uploaded
through:

```text
POST /api/admin/fabrics/{fabric_id}/images
```

## Optional GPT Enrichment

GPT enrichment is optional:

```bash
OPENAI_API_KEY='<key-in-env-only>' \
python3 scripts/import_fabrics_from_viliamsk.py \
  --input-json /tmp/viliamsk_raw_export.json \
  --dry-run \
  --use-gpt \
  --gpt-model gpt-4o-mini \
  --output /tmp/fabrics_preview.json
```

GPT may clean title/category/color/tags/short description from extracted source
text. It must not invent composition, density, width, price, stock, or
availability if they are absent from the source data.

## Post-Import Checks

After importing approved rows to staging:

1. Open the admin frontend.
2. Check the imported fabrics are `draft`.
3. Upload or verify main/texture images.
4. Run the existing card check in the admin UI.
5. Publish only reviewed complete cards.
6. Verify public catalog and bot catalog/search after publication.
