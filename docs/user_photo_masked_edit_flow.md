# User Photo Masked Edit Flow

User-facing photo fabric try-on must be a true masked image edit of the
original user photo. It must not generate a standalone garment crop and paste it
back onto the source photo as a rectangular patch, sticker, collage, or product
mockup.

## Runtime Contract

The `/api/generations/user-photo` flow sends the provider:

- the original uploaded user photo as the base image;
- the selected fabric texture/reference image normalized into a square provider
  swatch;
- a PNG edit mask with the same width and height as the original photo;
- a strict prompt that asks for a full-frame edit of the original photo only.

The provider output is accepted only as a full-frame edited image. Crop-only
provider outputs and local crop composites are not valid user-facing results.

This follows the current OpenAI Images API contract for image edits: the edit
request modifies an existing image and may include image inputs plus an edit
mask. Use the Images API for this single-shot edit path; conversational or
multi-turn editing belongs in a separate Responses API design gate.

## Mask Contract

The edit mask uses the OpenAI image-edit convention used by the backend:

- transparent pixels are editable clothing pixels;
- opaque pixels are protected pixels;
- face, hair, skin, hands, phone, background, objects, pose, and lighting must
  remain outside the editable region.

If the backend cannot prepare a usable mask, generation fails closed before the
provider call.

The default Telegram preset is intentionally narrow: it targets a visible light
inner T-shirt under an open shirt/overshirt and protects saturated overshirts,
skin, phone, face, hands, and background. The older central upper-garment preset
is retained only for backward-compatible callbacks/tests.

## Provider Strategy

Default runtime strategy:

```text
TRYON_PROVIDER_STRATEGY=chatgpt_like_masked_edit
TRYON_MAX_PROVIDER_ATTEMPTS=1
TRYON_DEBUG_BUNDLE_ENABLED=false
```

The backend keeps the full original photo as the base image and uses the full
same-size mask. It does not crop the garment, paste a generated patch, or send a
standalone garment crop as the user-facing result.

`TRYON_MAX_PROVIDER_ATTEMPTS` is clamped to `1..3`. A retry is allowed only after
the previous provider output failed the preservation guardrail or provider call.
Retry prompts become more conservative; they do not disable preservation checks.
If all attempts fail, the generation remains `failed` and `result_image_url` is
not exposed.

When `TRYON_DEBUG_BUNDLE_ENABLED=true`, the backend may write a sanitized JSON
attempt report under `UPLOAD_DIR/tryon-debug/`. The report contains attempt
status and sanitized error summaries only; it must not include secrets, raw image
bytes, base64 payloads, provider request payloads, or absolute filesystem paths.

## Guardrails

Before saving `result_image_url`, the backend checks:

- provider output dimensions match the original photo and mask;
- protected pixels outside the mask remain visually stable;
- the candidate does not look like a large hard-edged rectangular overlay;
- failed outputs do not get exposed as successful results.

On rejection, the user receives a safe retry message. Logs keep sanitized
failure reasons such as `size_mismatch`, `protected_region_drift`, or
`rectangular_overlay_detected`.

## Debug Artifacts

Local/test runs may store debug artifacts such as:

- `original.png`;
- `mask.png`;
- provider request metadata without secrets;
- provider output image;
- `guardrail_report.json`.

Do not store real user photos, raw provider payloads, base64 image data, API
keys, bot tokens, or filesystem paths in GitHub issues, PRs, logs, or docs.

## Manual QA

Use synthetic or explicitly approved safe photos only. A valid result must:

- preserve the same person, face, hands, phone, pose, lighting, and background;
- change only the selected clothing area;
- avoid rectangular patch boundaries;
- keep `result_image_url` absent when guardrails fail.

Live provider testing still requires an explicit capped execution gate.

References:

- OpenAI image generation and editing guide:
  <https://developers.openai.com/api/docs/guides/image-generation>
