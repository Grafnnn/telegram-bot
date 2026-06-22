# Crop-Only Track B Transport Retry 008

## Status

Decision: `TRANSPORT_RETRY_READY_FOR_OPERATOR_REVIEW`

Issue: #66

Baseline: `main@18a26cf62e8d68133551a28d3cf7a538636a9378`

This is a redacted execution report. It does not include provider bytes,
base64 payloads, raw provider responses, secrets, or real user photos.

## Scope

The approved transport retry input scope was:

```text
crop_source + crop_mask + fabric_reference only
```

Full source/person/scene provider input remained forbidden.

## Call Control

| Field | Value |
| --- | --- |
| Expected provider generations | 1 |
| Max provider HTTP requests | 2 |
| Actual provider HTTP requests | 1 |
| Retry count | 0 |
| Stop condition | none |

## Results

| Fixture | Preservation | Provider output | Reconciled crop | Mean delta | Changed protected pixels | Max delta |
| --- | --- | --- | --- | ---: | ---: | ---: |
| `pm001-solid-frontal` | pass | `1024x1536` | `57x105` | 0.0000 | 0.0000% | 0 |

## Safety

- Full-scene provider input used: no
- Real user photos used: no
- Staging/prod/env touched: no
- Runtime/bot/admin user-facing enabled: no
- Imports/SQL/direct DB writes: no
- Secrets/base64/raw image bytes printed: no
- Raw provider payloads committed: no
- Provider output binaries committed: no
- User-facing rollout approved: no

## Decision

Decision: `TRANSPORT_RETRY_READY_FOR_OPERATOR_REVIEW`

This result confirms that the one-fixture transport retry can complete a
crop-only provider request and pass protected-region preservation after local
dimension reconciliation and composite.

It does not approve user-facing Telegram/admin behavior, staging integration,
broader fixture execution, or rollout.

Any broader fixture run, staging route work, or rollout still requires a new
explicit gate.
