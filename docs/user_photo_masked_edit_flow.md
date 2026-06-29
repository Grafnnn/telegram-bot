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
TRYON_INPUT_FIDELITY=high
TRYON_DEBUG_BUNDLE_ENABLED=false
```

`chatgpt_like_masked_edit` keeps the full original photo as the base image and
uses the full same-size mask as provider guidance. It does not crop the garment,
paste a generated patch, or send a standalone garment crop as the user-facing
result.

`local_texture_transfer` is a deterministic provider-free strategy for the same
full-photo and mask inputs. It tiles the selected fabric reference only through
the transparent clothing mask, transfers the original garment luminance so
folds, shadows, and broad lighting remain visible, feathers the inside edge of
the mask, and leaves hard protected pixels outside the mask unchanged. It calls
no OpenAI/provider endpoint and records `provider_called=false` /
`provider_attempts=0` in debug metadata.

This local strategy is intentionally narrower than a full AI edit. It does not
perform semantic garment reconstruction, perspective-perfect cloth simulation,
or realistic redesign of occluded clothing. It is best suited for visible,
flat-ish T-shirt or inner-garment areas where preserving the original person,
phone, hands, outer clothing, and background is more important than high-fashion
image synthesis. A later gate may add AI edge polish inside a very narrow
edge-only mask, but only after the local transfer path is stable.

For the OpenAI image edit request, the backend keeps a stable input order:

1. first image: the uploaded user photo, or the provider compatibility canvas
   containing that photo;
2. second image: the normalized square fabric reference swatch;
3. mask: the PNG edit mask aligned with the first image. Transparent pixels are
   editable clothing pixels; opaque pixels are protected.

For `gpt-image-1`, `TRYON_INPUT_FIDELITY=high` is sent as `input_fidelity=high`
to preserve the first input image details as much as the provider supports. If
the runtime model does not support that parameter, such as `gpt-image-2` where
high fidelity is automatic, the backend omits the parameter and records a
sanitized reason in debug metadata instead of failing the request.

The masked-edit prompt explicitly instructs the provider to treat opaque mask
pixels as locked source photography and to avoid repainting, relighting,
beautifying, denoising, recoloring, or reinterpreting protected regions. This is
provider guidance only; it does not replace the preservation guardrail.

When the selected provider/model only accepts fixed output sizes and the source
photo uses another aspect ratio, the backend uses the same compatibility-canvas
adapter as the vision-guided path: it centers the original photo on the closest
supported neutral canvas, adapts the edit mask onto that canvas, asks the
provider to return the full canvas, then extracts the original-photo frame
before running the preservation guardrail. Neutral padding is opaque in the mask
and must not be edited. This is not a crop/composite output path; the
user-facing candidate is still judged only against the original full-frame photo
and same-size mask.

`vision_guided_edit` is an alternative staging strategy for complex real-world
photos where a hard provider mask may hurt quality. It sends the original
full-frame photo and normalized fabric reference to the provider with a natural
ChatGPT-like instruction. It does not send a crop-local image, does not composite
locally, and does not send the preset mask to the provider. The preset mask is
still prepared and stored so the backend can run the same preservation
guardrail before exposing any result.

For full-frame edit strategies the backend chooses a per-request provider size
from the original image dimensions instead of blindly using `OPENAI_IMAGE_SIZE`.
For fixed-size `gpt-image-1` requests it uses the matching fixed aspect when the
original is square, 2:3 portrait, or 3:2 landscape. When the original aspect is
not one of those fixed legacy sizes, such as the 3:4 synthetic smoke fixture, it
uses a canvas adapter instead of `size=auto`: the original photo is centered on
the closest supported neutral provider canvas, for example a 3:4 photo is placed
inside a 2:3 `1024x1536` canvas. After the provider returns the edited canvas,
the backend extracts the known original-photo frame and runs the preservation
guardrail against the original image and mask. Models that support exact custom
sizes can request the original `WIDTHxHEIGHT` directly when the source
dimensions satisfy that model's documented size constraints.

This is only provider guidance. The preservation guardrail remains authoritative:
same-aspect different-size full-frame outputs may be normalized before drift
checks, but different-aspect outputs, crops, padding/extended canvases, standalone
garments, rectangular patches, or protected-region drift still fail closed and do
not expose `result_image_url`. Debug metadata records sanitized sizes/aspect
fields such as requested provider size/aspect, original size/aspect, provider
output size/aspect, aspect delta, whether a provider canvas adapter was used,
and whether normalization occurred.
Masked-edit debug metadata also records the provider model, endpoint method,
input image count and roles, whether the mask was applied to the first input,
and the `input_fidelity` requested/applied/support decision. It does not include
raw provider payloads, base64 image data, secrets, tokens, or absolute local
paths.

For the first staging experiment with this strategy, use:

```text
TRYON_PROVIDER_STRATEGY=vision_guided_edit
TRYON_MAX_PROVIDER_ATTEMPTS=1
```

Before spending a live provider call with the `visible_inner_tshirt` preset,
preflight the input photo locally:

```bash
PYTHONPATH=backend python3 scripts/preflight_user_photo_mask_preset.py \
  --write-synthetic-visible-inner-tshirt /tmp/visible-inner-tshirt-smoke.png \
  --preset visible_inner_tshirt
```

For an existing photo, replace the generated fixture option with the image path:

```bash
PYTHONPATH=backend python3 scripts/preflight_user_photo_mask_preset.py \
  /path/to/photo.png \
  --preset visible_inner_tshirt
```

The command creates and validates only the preset mask. It does not call
OpenAI/provider, does not create a generation record, and reports compact mask
metadata such as image size, mask size, coverage, readiness, and error code.
The preset is considered ready only when the transparent editable area is
non-empty and within the configured coverage range.

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
- protected pixels outside the mask remain structurally stable;
- the candidate does not look like a large hard-edged rectangular overlay;
- failed outputs do not get exposed as successful results.

The protected-region drift check is intentionally tolerant of small
provider-side photometric changes. It excludes a narrow boundary band around
the editable clothing mask, applies a small global color/brightness correction
before comparing protected pixels, and then scores only the strict protected
area. This reduces false failures from compression, resize normalization, edge
blending, or mild color correction. It does not allow structural changes to the
face, hands, phone, background, outer garments, pose, canvas, or framing.

On rejection, the user receives a safe retry message. Logs keep sanitized
failure reasons such as `size_mismatch`, `protected_region_drift`, or
`rectangular_overlay_detected`, plus numeric drift metadata only.

For `local_texture_transfer`, the preservation guardrail is still mandatory
before `result_image_url` is saved. Because the local compositor keeps protected
pixels unchanged by construction, any nonzero protected-region drift is treated
as a bug or unsafe input and remains fail-closed.

## Debug Artifacts

Local/test runs may store debug artifacts such as:

- `original.png`;
- `mask.png`;
- provider request metadata without secrets;
- provider output image;
- `guardrail_report.json`.

Do not store real user photos, raw provider payloads, base64 image data, API
keys, bot tokens, or filesystem paths in GitHub issues, PRs, logs, or docs.
Staging smoke results that include operational details, generation IDs, request
IDs, service IDs, or private environment posture should be kept in local or
private channels rather than public GitHub issues.

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
