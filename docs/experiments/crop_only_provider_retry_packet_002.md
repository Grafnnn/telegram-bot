# Crop-Only Provider Retry Packet 002

## Status

Status: RETRY PACKET PROPOSAL ONLY / NOT APPROVED FOR EXECUTION

This packet proposes a retry after the Issue #64 output dimension mismatch.
It does not approve provider/OpenAI calls.
It does not approve user-facing rollout.
It does not change runtime behavior.

## Context

Previous execution:
[`docs/experiments/reports/crop_only_provider_execution_001.md`](reports/crop_only_provider_execution_001.md)

Issue #64 stopped after one provider call because the provider returned
`1024x1536` for a `57x105` crop. Issue #66 then added an offline reconciliation
strategy rehearsal.

Offline reconciliation rehearsal:
[`docs/experiments/reports/crop_only_dimension_reconciliation_001.md`](reports/crop_only_dimension_reconciliation_001.md)

## Issue Gate

Issue: #66

Issue #66 is the strategy gate for output dimension handling. This packet does
not itself approve retry execution.

## Execution Approval State

Execution approval: NOT APPROVED

Provider/OpenAI calls: BLOCKED

User-facing rollout: NOT APPROVED

Runtime enablement: NOT APPROVED

## Retry Target

Experiment ID: `crop-only-provider-retry-002`

Target: local/dev only by default

Provider: OpenAI

Model: `gpt-image-1`

Endpoint: `/v1/images/edits`

Provider input scope:

```text
crop_source + crop_mask + fabric_reference only
```

Full source/person/scene provider input is forbidden.

## Dimension Strategy

Allowed reconciliation strategy for this packet:

```text
center_crop_to_crop_aspect_then_resize
```

Required sequence:

1. Check provider output dimensions.
2. If provider output dimensions already match crop dimensions, composite
   directly.
3. If provider output dimensions differ, center-crop provider output to the
   target crop aspect ratio.
4. Resize the cropped provider output to exact crop dimensions.
5. Composite locally into the original source using the full mask.
6. Run full-image preservation.
7. Run visual review for fabric scale, pattern distortion, and boundary
   quality.

Implicit resizing is forbidden. Reconciliation must be explicit, recorded, and
reported per fixture.

## Fixtures

Retry manifest:
[`docs/experiments/fixtures/crop_only_provider_retry_manifest_002.json`](fixtures/crop_only_provider_retry_manifest_002.json)

Fixtures:

1. `pm001-solid-frontal`
2. `pm001-pattern-boundary`

Only synthetic fixture images are allowed.

## Call Cap

Expected calls: 2

Maximum calls: 3

Retry policy: maximum 1 retry total, only for transient/provider failure after
explicit GO.

Calls beyond cap: forbidden.

Any call without explicit Issue #66 GO: forbidden.

## Expected Artifacts

Future execution artifacts, if Issue #66 receives explicit GO:

```text
/tmp/crop-only-provider-002-execution/
  inputs/
  provider_outputs/
  reconciled_crops/
  composites/
  preservation/
  visual_review/
  execution_summary.json
  execution_summary.md
```

Artifact policy:

- raw provider bytes/base64 must not be posted to GitHub;
- raw provider response payloads must not be committed;
- provider output images remain local unless explicitly reviewed;
- redacted metrics and safe references may be committed later;
- real user photos are forbidden.

## Stop Conditions

Stop immediately and record HOLD/NO-GO if any condition occurs:

- Issue #66 explicit GO is missing;
- provider/model/config cannot be confirmed immediately before execution;
- call cap would be exceeded;
- full source/person/scene is selected as provider input;
- crop mask is missing or invalid;
- no-mask prompt-only path is selected;
- provider output cannot be tied to fixture id;
- provider output dimensions are missing or unreadable;
- reconciliation strategy is not applied exactly as approved;
- reconciled crop dimensions do not match crop box;
- local composite fails;
- preservation report is missing;
- protected-region drift fails threshold;
- face/body/hands/background drift is observed;
- fabric scale or boundary distortion is severe in visual review;
- secrets/tokens/base64/raw image bytes/raw provider payloads would be exposed;
- staging/prod/env/runtime/bot behavior would be touched unexpectedly.

## Safety Confirmations

- Provider/OpenAI retry was not run while preparing this packet.
- Runtime behavior was not changed.
- Bot behavior was not changed.
- Staging/prod/env were not touched.
- Imports, SQL, and direct DB writes were not performed.
- Real user photos were not added or used.
- Secrets, base64 payloads, raw image bytes, and raw provider payloads were not
  exposed.

## Non-Approvals

This packet does not approve:

- provider/OpenAI retry;
- production rollout;
- user-facing try-on;
- Telegram/admin enablement;
- runtime route changes;
- no-mask fallback;
- additional retries beyond the stated cap.

## Next Gate

After this packet is reviewed, Issue #66 may receive a separate explicit GO.
Only then may `crop-only-provider-retry-002` run within the stated constraints.
