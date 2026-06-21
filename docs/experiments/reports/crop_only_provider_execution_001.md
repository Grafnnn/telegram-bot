# Crop-Only Provider Execution 001

## Status

Status: `HOLD_PROVIDER_OUTPUT_SIZE_MISMATCH`

Issue: #64

Baseline: `main@b3a888937670a05bcc411dfc2d84f191341174fe`

This report records the first capped crop-only provider execution attempt. It
is a redacted report only. It does not include provider bytes, base64 payloads,
raw provider responses, secrets, or real user photos.

## Result

Execution stopped at the first stop condition.

Provider returned an output sized `1024x1536` for fixture
`pm001-solid-frontal`, while the expected crop dimensions were `57x105`.
Local composite was therefore blocked before any preservation report could be
computed.

The second fixture was not called.

## Call Control

| Field | Value |
| --- | --- |
| Expected provider calls | 2 |
| Max provider call cap | 3 |
| Actual provider calls | 1 |
| Retry count | 0 |
| Stopped before second fixture | yes |

## Fixture Results

| Fixture | Provider call | Result | Provider output dimensions | Expected crop dimensions |
| --- | --- | --- | --- | --- |
| `pm001-solid-frontal` | yes | size mismatch stop condition | `1024x1536` | `57x105` |
| `pm001-pattern-boundary` | no | skipped after stop condition | n/a | `75x66` |

## Safety

- Full-scene provider input used: no
- Real user photos used: no
- Staging/prod/env touched: no
- Runtime/bot behavior changed: no
- Imports/SQL/direct DB writes: no
- Secrets/base64/raw image bytes printed: no
- Raw provider payloads committed: no
- Provider output images committed: no
- User-facing rollout approved: no

## Decision

Decision: `HOLD_PROVIDER_OUTPUT_SIZE_MISMATCH`

Do not continue this execution packet as-is. A separate strategy gate must
decide how crop-only provider output dimensions should be handled before any
retry.

## Next Gate

See
[`docs/experiments/crop_only_output_dimension_strategy_001.md`](../crop_only_output_dimension_strategy_001.md).
