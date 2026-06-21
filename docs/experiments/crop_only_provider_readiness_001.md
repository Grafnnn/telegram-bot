# Crop-Only Provider Readiness 001

## Status

Status: READYNESS REVIEW ONLY / NOT APPROVED FOR EXECUTION

This document prepares Issue #64 for a future explicit approval decision. It is
not approval to run provider/OpenAI calls and it is not evidence that the
strategy is ready for users.

## Baseline

Baseline: `main@eda0a4ffe0cae5c125c65d8f4a0327d9bc4ba9f0`

Current ladder:

- full-scene provider path: documented NO-GO;
- crop/composite offline mechanics: passed;
- crop-only provider packet proposal: merged;
- crop-only readiness: this document;
- provider execution: still blocked until Issue #64 receives explicit GO.

## Issue Gate

Issue: #64

Issue #64 is the approval gate, but this document does not itself approve execution.

## Execution Approval State

Execution approval: NOT APPROVED

Provider/OpenAI calls: BLOCKED

User-facing rollout: NOT APPROVED

Runtime enablement: NOT APPROVED

## Frozen Inputs

Frozen input manifest:
[`docs/experiments/fixtures/crop_only_provider_frozen_inputs_001.json`](fixtures/crop_only_provider_frozen_inputs_001.json)

Frozen fixtures:

| Fixture | Source | Full mask | Crop source | Crop mask | Fabric reference |
| --- | --- | --- | --- | --- | --- |
| `pm001-solid-frontal` | `docs/experiments/assets/provider-mask-001/pm001-solid-frontal-source.png` | `docs/experiments/assets/provider-mask-001/pm001-solid-frontal-mask.png` | `docs/experiments/assets/crop-composite-001/pm001-solid-frontal/crop_source.png` | `docs/experiments/assets/crop-composite-001/pm001-solid-frontal/crop_mask.png` | `docs/experiments/assets/provider-mask-001/pm001-solid-frontal-fabric.png` |
| `pm001-pattern-boundary` | `docs/experiments/assets/provider-mask-001/pm001-pattern-boundary-source.png` | `docs/experiments/assets/provider-mask-001/pm001-pattern-boundary-mask.png` | `docs/experiments/assets/crop-composite-001/pm001-pattern-boundary/crop_source.png` | `docs/experiments/assets/crop-composite-001/pm001-pattern-boundary/crop_mask.png` | `docs/experiments/assets/provider-mask-001/pm001-pattern-boundary-fabric.png` |

The provider input scope for this gate is crop-only:

```text
crop_source + crop_mask + fabric_reference only
```

The full source and full mask are local-only inputs for compositing and
preservation review. They are not provider inputs for this readiness gate.

## Provider Candidate

Provider candidate: OpenAI

Model candidate: `gpt-image-1`

Endpoint candidate: `/v1/images/edits`

Mode: crop-only / garment-region-only edit

Input scope: crop source + crop-local mask + synthetic fabric reference only

Full scene/person input: not allowed for this gate

Post-processing: local composite back into original source

Required guardrail: preservation check after composite

The previous full-scene use of `gpt-image-1` via `/v1/images/edits` is
documented NO-GO. This readiness gate tests a different input strategy:
crop-only provider input + local composite. This does not approve the
provider/model for rollout.

Provider/model/config must still be re-confirmed before execution. If current
provider documentation, cost, input limits, output limits, privacy terms, or
mask semantics are unclear, Issue #64 remains NO-GO.

## Call Cap

Expected calls: 2

Maximum calls: 3

Retry policy: max 1 retry total, only for transient/provider failure

Calls beyond cap: forbidden

Any call without explicit Issue #64 GO: forbidden

## Expected Artifacts

Future execution artifacts, if Issue #64 receives explicit GO:

```text
/tmp/crop-only-provider-001-execution/
  inputs/
  provider_outputs/
  composites/
  preservation/
  visual_review/
  execution_summary.json
  execution_summary.md
```

Policy:

- raw provider bytes/base64 must not be posted to GitHub;
- only redacted metrics and safe references may be committed later;
- local artifacts may remain local unless explicitly reviewed;
- real user photos are forbidden.

## Preflight Checklist

- [ ] Issue #64 explicit GO recorded.
- [ ] Baseline commit confirmed.
- [ ] Working tree clean.
- [ ] Frozen input manifest validated.
- [ ] Provider/model/endpoint confirmed.
- [ ] Provider cost/risk accepted.
- [ ] Provider mask semantics confirmed.
- [ ] Expected calls confirmed as 2.
- [ ] Max call cap confirmed as 3.
- [ ] Output directory selected.
- [ ] Source images are synthetic.
- [ ] Crop-only provider input confirmed.
- [ ] Full scene/person provider input forbidden.
- [ ] No real user photos.
- [ ] No private storage images.
- [ ] No staging/prod/env changes.
- [ ] No imports.
- [ ] No SQL/direct DB writes.
- [ ] No secrets, base64 payloads, raw image bytes, or raw provider payloads.
- [ ] Stop conditions accepted.

Any unchecked critical item blocks execution.

## Execution Commands Draft

Safe readiness validation:

```bash
python3 scripts/validate_crop_only_provider_packet.py
python3 scripts/validate_crop_only_provider_readiness.py
python3 scripts/validate_crop_composite_offline_rehearsal.py
python3 scripts/validate_provider_mask_no_go_decision.py
```

Future provider execution command: TBD in a separate Issue #64 GO packet.

This readiness document intentionally does not define a runnable provider
command. The next packet must name the exact command, provider/model/config,
output directory, and call cap before execution starts.

## Stop Conditions

Stop immediately if any of these occurs:

- Issue #64 explicit GO is missing;
- provider/model/config is unknown;
- call cap would be exceeded;
- source image is not synthetic;
- full source image selected as provider input;
- crop mask missing or invalid;
- no-mask prompt-only path selected;
- provider output cannot be tied to fixture id;
- provider output dimensions cannot be reconciled with crop;
- local composite fails;
- preservation report missing;
- protected-region drift fails threshold;
- face/body/hands/background drift observed;
- fabric appears outside clothing mask;
- real user photo detected;
- staging/prod/env touched unexpectedly;
- secret/token/base64/raw image payload exposed;
- visual review missing.

If a stop condition occurs, record HOLD or NO-GO. Do not continue with nearby
prompts, alternate endpoints, or additional calls without a new packet.

## Safety Confirmations

- Provider/OpenAI calls were not run while preparing this readiness gate.
- Live crop-only provider execution was not run.
- Runtime behavior was not changed.
- Bot behavior was not changed.
- Staging/prod/env were not touched.
- Imports, SQL, and direct DB writes were not performed.
- Real user photos were not added or used.
- Secrets, base64 payloads, raw image bytes, and raw provider payloads were not
  exposed.

## Non-Approvals

This readiness gate does not approve:

- provider/OpenAI execution;
- production rollout;
- user-facing try-on;
- Telegram/admin enablement;
- runtime route changes;
- weakening preservation guardrails;
- no-mask fallback;
- additional provider retries beyond the stated cap.

## Issue #64 Comment Draft

```markdown
## Issue #64 Readiness Update

Readiness gate prepared for crop-only provider execution.

Current state:
- Full-scene provider path remains NO-GO.
- Crop/composite offline mechanics passed.
- Crop-only packet proposal is merged.
- Frozen crop inputs are defined.
- Expected calls: 2.
- Max call cap: 3.
- Provider/model candidate: OpenAI `gpt-image-1` via `/v1/images/edits`.
- Execution remains NOT APPROVED.
- User-facing rollout remains NOT APPROVED.

Provider/OpenAI calls remain blocked until this issue receives explicit GO.
```

## Next Gate

After this readiness gate is merged, Issue #64 may be reviewed for explicit GO.
Only then may the capped crop-only provider execution run, and only within the
approved packet constraints.
