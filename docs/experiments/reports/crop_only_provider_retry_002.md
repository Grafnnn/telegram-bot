# Crop-Only Provider Retry 002

## Status

Status: `GO_FOR_MORE_CROP_ONLY_TESTING`

Issue: #66

Baseline: `main@795fb3791edbceab7ae20e14813cb5fb56b0a537`

This is a redacted execution report. It does not include provider bytes,
base64 payloads, raw provider responses, secrets, or real user photos.

## Goal

Retry the crop-only provider path after the output dimension strategy gate.
The provider receives only:

```text
crop_source + crop_mask + fabric_reference
```

The full source/person/scene is used only for local composite and preservation
review. It is not sent to the provider.

## Call Control

| Field | Value |
| --- | --- |
| Successful provider generations | 2 |
| Total HTTP requests | 3 |
| Retry count | 0 |
| Max total HTTP requests | 3 |

The first HTTP request used duplicate `image` multipart fields and was rejected
before generation. The execution then used `image[]` array syntax and completed
two successful provider generations.

## Dimension Strategy

Strategy: `center_crop_to_crop_aspect_then_resize`

Both provider outputs returned `1024x1536` and were explicitly reconciled to
their fixture crop dimensions before local composite.

## Fixture Results

| Fixture | Provider output | Reconciled crop | Preservation | Mean delta | Changed protected pixels | Max delta |
| --- | --- | --- | --- | ---: | ---: | ---: |
| `pm001-solid-frontal` | `1024x1536` | `57x105` | pass | 0.0000 | 0.0000% | 0 |
| `pm001-pattern-boundary` | `1024x1536` | `75x66` | pass | 0.0000 | 0.0000% | 0 |

## Safety

- Full-scene provider input used: no
- Real user photos used: no
- Staging/prod/env touched: no
- Runtime/bot behavior changed: no
- Imports/SQL/direct DB writes: no
- Secrets/base64/raw image bytes printed: no
- Raw provider payloads committed: no
- User-facing rollout approved: no

## Decision

Decision: `GO_FOR_MORE_CROP_ONLY_TESTING`

The crop-only provider path plus explicit center-crop/resize reconciliation and
local composite passed protected-region preservation on both synthetic
fixtures. This supports more controlled crop-only testing.

It does not approve production rollout, user-facing Telegram/admin enablement,
or a visual-quality claim.

## Next Gate

Use this as positive technical evidence for crop-only mechanics.
Any next provider/model/prompt expansion still needs a separate capped packet
with explicit fixtures, call cap, safety boundaries, artifact policy, and stop
conditions.

A proposal-only visual-quality expansion packet is available at
[`docs/experiments/crop_only_visual_quality_expansion_packet_003.md`](../crop_only_visual_quality_expansion_packet_003.md).
It keeps provider/OpenAI execution blocked until the missing synthetic fixtures
are created and a fresh explicit GO is recorded.
