# User Photo Masked Edit Flow

User-facing photo fabric try-on must be a true masked image edit of the
original user photo. It must not generate a standalone garment crop and paste it
back onto the source photo as a rectangular patch, sticker, collage, or product
mockup.

## Runtime Contract

The `/api/generations/user-photo` flow sends the provider:

- the original uploaded user photo as the base image;
- the selected fabric texture/reference image;
- a PNG edit mask with the same width and height as the original photo;
- a strict prompt that asks for a full-frame edit of the original photo only.

The provider output is accepted only as a full-frame edited image. Crop-only
provider outputs and local crop composites are not valid user-facing results.

## Mask Contract

The edit mask uses the OpenAI image-edit convention used by the backend:

- transparent pixels are editable clothing pixels;
- opaque pixels are protected pixels;
- face, hair, skin, hands, phone, background, objects, pose, and lighting must
  remain outside the editable region.

If the backend cannot prepare a usable mask, generation fails closed before the
provider call.

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
