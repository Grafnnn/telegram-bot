# Crop-Only Track B Provider Failure Diagnostic 010

## Status

Decision: `READY_FOR_ONE_FIXTURE_RETRY_PACKET_DESIGN`

Issue: #66

Baseline: `main@b825d06a32b8301de2e462690f83265a89b4494e`

This is a zero-call diagnostic report for the
`provider_call_failed:ImageGenerationProviderError` result from
`crop-only-track-b-remaining-fixtures-009`.

## Summary

| Field | Value |
| --- | --- |
| Provider/OpenAI calls | 0 |
| Network calls | 0 |
| Diagnostic provider calls allowed | no |
| Diagnostic network calls allowed | no |
| Parent stop condition | `provider_call_failed:ImageGenerationProviderError` |
| Failures | none |

The diagnostic did not reproduce a local fixture/input-shape failure. All three
remaining fixtures have readable crop sources, crop masks, fabric references,
matching crop source/mask dimensions, non-empty editable/protected mask regions,
and sanitized crop-only request-shape summaries.

## Fixture Checks

| Fixture | Crop source | Crop mask | Fabric ref | Mask editable | Mask protected | Dimensions match |
| --- | --- | --- | --- | ---: | ---: | --- |
| `pm001-pattern-boundary` | 75x66 RGB | 75x66 RGBA | 64x64 RGB | 44.97% | 55.03% | yes |
| `pm003-large-pattern-scale` | 86x116 RGB | 86x116 RGBA | 96x96 RGB | 76.70% | 23.30% | yes |
| `pm004-edge-boundary-stress` | 106x106 RGB | 106x106 RGBA | 80x80 RGB | 65.97% | 34.03% | yes |

## Request Shape

For every fixture:

- image count: 2
- mask present: yes
- input scope: `crop_source + crop_mask + fabric_reference only`
- full-scene provider input included: no
- raw payload included: no
- base64 included: no
- secret included: no

## Interpretation

The previous provider failure is not explained by missing fixture files,
unreadable images, crop source/mask dimension mismatch, empty mask regions, or
full-scene input selection.

The next safe design step may be a one-fixture retry packet for
`pm001-pattern-boundary`, capped at one provider HTTP request and zero retry.
That retry still requires a separate fresh explicit GO.

## Safety

- Staging/prod/env touched: no
- Runtime/bot/admin user-facing enabled: no
- Imports/SQL/direct DB writes: no
- Real user photos used: no
- Secrets/raw payloads exposed: no
- Raw image bytes/base64 committed: no
- User-facing rollout approved: no

## Decision

Decision: `READY_FOR_ONE_FIXTURE_RETRY_PACKET_DESIGN`

This report does not authorize provider/OpenAI execution. It only supports
designing a narrower, one-fixture/no-retry packet.
