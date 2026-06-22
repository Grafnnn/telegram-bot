# Crop-Only Track B Operator Visual Review 008

## Status

Decision: `PASS_FOR_MORE_LOCAL_CROP_ONLY_TESTING`

Issue: #66

Baseline: `main@293aac6508be987f7ae34c6dfa91d732b7192a58`

This is a report-only manual visual review of existing local artifacts from
`crop-only-track-b-transport-retry-008`. It does not run provider/OpenAI and it
does not commit provider output binaries.

## Reviewed Artifacts

Local-only artifacts:

- `/tmp/crop-only-track-b-transport-retry-008/provider_outputs/pm001-solid-frontal.png`
- `/tmp/crop-only-track-b-transport-retry-008/reconciled_crops/pm001-solid-frontal.png`
- `/tmp/crop-only-track-b-transport-retry-008/composites/pm001-solid-frontal.png`
- `/tmp/crop-only-track-b-transport-retry-008/operator_review_contact_sheet.png`

Committed input report:

- [`docs/experiments/reports/crop_only_track_b_transport_retry_008.json`](crop_only_track_b_transport_retry_008.json)

## Visual Scores

| Dimension | Score |
| --- | ---: |
| Fabric resemblance | 4 |
| Pattern scale plausibility | 4 |
| Boundary quality | 4 |
| Garment-only localization | 5 |
| Artifact absence | 4 |
| Overall average | 4.2 |

## Review Notes

Positive:

- Final composite changes are localized to the editable garment region.
- Fabric color and stripe-like texture are visibly represented in the garment
  area.
- Protected face, hands, background and lower garment are preserved by the local
  composite path.

Risk notes:

- Provider crop output itself introduced a realistic torso and arms, so provider
  restraint is not proven.
- This review supports more local crop-only testing, not user-facing rollout.

Blocking notes:

- None for additional local crop-only testing.

## Safety

- New provider/OpenAI calls: no
- Provider output binaries committed: no
- Staging/prod/env touched: no
- Runtime/bot/admin user-facing enabled: no
- Imports/SQL/direct DB writes: no
- Real user photos used: no
- Secrets/base64/raw provider payloads exposed: no
- User-facing rollout approved: no

## Decision

Decision: `PASS_FOR_MORE_LOCAL_CROP_ONLY_TESTING`

The one-fixture result is acceptable as positive evidence for additional
local/dev crop-only testing. It does not approve broader fixture execution,
staging route work, Telegram/admin user-facing behavior, or rollout.

Any broader fixture run, staging route work, or rollout still requires a new
explicit gate.
