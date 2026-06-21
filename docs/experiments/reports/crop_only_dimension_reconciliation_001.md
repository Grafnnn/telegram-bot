# Crop-Only Dimension Reconciliation Rehearsal 001

## Status

Status: `offline_rehearsal_passed`

This is an offline deterministic rehearsal only.
It does not call OpenAI/provider.
It does not approve provider retry.
It does not approve user-facing rollout.

## Strategy

Strategy: `center_crop_to_crop_aspect_then_resize`

The rehearsal simulates an oversized provider output, center-crops it to
the target crop aspect ratio, resizes it to the exact crop box, composites
it locally, and runs full-image preservation.

This proves geometry and preservation mechanics only. It does not prove
provider visual quality or fabric scale quality.

## Metrics

| Fixture | Preservation | Oversized output | Reconciled crop | Mean delta | Changed protected pixels | Max delta |
| --- | --- | --- | --- | ---: | ---: | ---: |
| `pm001-solid-frontal` | pass | 1024x1536 | 57x105 | 0.0000 | 0.0000% | 0 |
| `pm001-pattern-boundary` | pass | 1024x1536 | 75x66 | 0.0000 | 0.0000% | 0 |

## Decision

Decision: `READY_FOR_RETRY_PACKET_DESIGN_ONLY`

A future provider retry still requires a new explicit approval packet.
The packet must state whether this reconciliation strategy is allowed
and must include visual review requirements for fabric scale and boundary quality.

## Non-Approvals

- No provider/OpenAI retry is approved.
- No runtime implementation is approved.
- No staging/prod/env change is approved.
- No user-facing rollout is approved.
