# Crop-Only Output Dimension Strategy 001

## Status

Status: STRATEGY GATE / NOT APPROVED FOR RETRY

This document responds to the Issue #64 stop condition:

```text
provider output dimensions cannot be reconciled with crop
```

Follow-up issue: #66

It does not approve another provider/OpenAI call.
It does not approve user-facing rollout.
It does not change runtime behavior.

## Context

The first crop-only provider attempt stopped after one provider call:

- fixture: `pm001-solid-frontal`
- expected crop dimensions: `57x105`
- provider output dimensions: `1024x1536`
- composite: not created
- preservation report: not created
- second fixture: not called

Recorded report:
[`docs/experiments/reports/crop_only_provider_execution_001.md`](reports/crop_only_provider_execution_001.md)

## Problem

The crop/composite pipeline requires provider crop output to align with the
crop box before local compositing.

If the provider returns a standard full-size image rather than crop-sized
output, the system needs an explicit, deterministic strategy before retrying.
Implicit resizing would be unsafe because it could hide boundary alignment
bugs, distort fabric scale, or create false preservation confidence.

## Candidate Strategies

| Strategy | Description | Pros | Risks | Current posture |
| --- | --- | --- | --- | --- |
| Provider crop-size request | Request output matching crop dimensions if provider supports it. | Cleanest geometry. | May be unsupported for small/nonstandard sizes. | Investigate docs/config before retry. |
| Deterministic downscale-to-crop | Resize provider output to exact crop dimensions before composite. | Allows using current provider output shape. | May distort fabric, lose detail, hide alignment artifacts. | Requires offline rehearsal before provider retry. |
| Deterministic center-crop then resize | Crop provider output to matching aspect ratio, then resize. | Can preserve more local composition than direct squeeze. | Adds arbitrary framing choice; may shift garment texture. | Requires synthetic rehearsal. |
| Larger crop canvas | Pad/upscale crop inputs to provider-friendly dimensions, then project back. | Gives provider more context and predictable output size. | More protected pixels may enter provider input; must keep full-scene out. | Candidate for next offline rehearsal. |
| Different provider/config | Choose provider or endpoint that preserves input dimensions. | Avoids reconciliation layer. | New provider risks/cost/semantics. | Separate provider strategy gate. |
| Mark this path unsuitable | Do not retry with this provider/config. | Safest if geometry cannot be controlled. | Ends this crop-only OpenAI path. | Valid NO-GO option. |

## Recommended Next Safe Step

Do not run another provider call yet.

First add an offline-only rehearsal for dimension reconciliation:

1. Use the saved dimensions from Issue #64 as the failing shape.
2. Generate a deterministic synthetic oversized crop-output fixture.
3. Test candidate reconciliation rules without calling a provider.
4. Composite reconciled output back into the full source.
5. Run preservation drift.
6. Manually review fabric scale and boundary distortion.
7. Only then decide whether a retry packet is justified.

Offline rehearsal 001 has been added for the candidate strategy:

```text
center-crop provider output to target crop aspect -> resize to crop dimensions
```

Report:
[`docs/experiments/reports/crop_only_dimension_reconciliation_001.md`](reports/crop_only_dimension_reconciliation_001.md)

This rehearsal validates geometry and preservation mechanics only. It does not
approve provider retry, runtime implementation, or user-facing rollout.

## Requirements Before Any Retry

- Issue #64 or follow-up issue records a new explicit GO.
- Reconciliation strategy is named.
- Reconciliation strategy has offline deterministic tests.
- Output dimensions are checked before composite.
- No implicit resize happens inside execution code.
- Visual report explicitly evaluates fabric scale and boundary quality.
- Provider call cap is reset in a new packet.
- Real user photos remain forbidden.
- User-facing rollout remains forbidden.

## Stop Conditions

Stop or remain NO-GO if:

- provider output size policy is unknown;
- reconciliation strategy is not documented;
- reconciliation strategy lacks offline tests;
- resized/reconciled output fails preservation;
- fabric scale is visibly distorted;
- boundary artifacts are severe;
- provider must receive the full original scene to work;
- any retry would exceed an approved call cap;
- raw provider bytes/base64/secrets would be exposed.

## Non-Approvals

This strategy document does not approve:

- provider/OpenAI retry;
- runtime implementation;
- staging/prod changes;
- Telegram/admin enablement;
- real user photo testing;
- user-facing rollout.
