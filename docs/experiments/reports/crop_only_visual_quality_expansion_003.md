# Crop-Only Visual Quality Expansion 003

## Status

Status: `GO_FOR_MORE_CROP_ONLY_TESTING`

Issue: #66

Baseline: `main@68d831bf30279271dc33d926b8af612fea866241`

This is a redacted execution report. It does not include provider bytes,
base64 payloads, raw provider responses, secrets, or real user photos.

## Scope

The provider received only:

```text
crop_source + crop_mask + fabric_reference
```

The full source/person/scene was used only for local composite and preservation
review. It was not sent to the provider.

## Call Control

| Field | Value |
| --- | --- |
| Successful provider generations | 4 |
| Total HTTP requests | 5 |
| Retry count | 1 |
| Max total HTTP requests | 5 |

One transient read timeout occurred on `pm004-edge-boundary-stress`. The single
allowed retry succeeded.

## Results

| Fixture | Preservation | Mean delta | Changed protected pixels | Visual avg | Min dimension |
| --- | --- | ---: | ---: | ---: | ---: |
| `pm001-solid-frontal` | pass | 0.0000 | 0.0000% | 4.0 | 4 |
| `pm001-pattern-boundary` | pass | 0.0000 | 0.0000% | 4.0 | 4 |
| `pm003-large-pattern-scale` | pass | 0.0000 | 0.0000% | 4.2 | 4 |
| `pm004-edge-boundary-stress` | pass | 0.0000 | 0.0000% | 4.2 | 4 |

## Visual Review Notes

- `pm001-solid-frontal`: localized garment edit, plausible controlled
  synthetic result, threshold pass.
- `pm001-pattern-boundary`: readable pattern and acceptable synthetic boundary
  behavior, threshold pass.
- `pm003-large-pattern-scale`: large-scale motif remains centered and localized,
  threshold pass.
- `pm004-edge-boundary-stress`: fabric remains inside jacket/garment area while
  nearby hands, object, trousers, face, and background are preserved by local
  composite, threshold pass.

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

The expanded crop-only visual-quality packet passed preservation and manual
visual thresholds on all four synthetic fixtures. This is positive evidence for
more controlled crop-only testing.

It does not approve production rollout, user-facing Telegram/admin enablement,
or staging/runtime changes.

## Next Gate

Any next provider/model/prompt expansion, staging route integration, or
user-facing workflow still needs a separate capped packet with explicit
fixtures, call cap, artifact policy, safety boundaries, and stop conditions.
