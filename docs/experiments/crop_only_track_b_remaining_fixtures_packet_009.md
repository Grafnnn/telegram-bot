# Crop-Only Track B Remaining Fixtures Packet 009

## Status

Status: `REMAINING_FIXTURES_PACKET / NOT APPROVED FOR EXECUTION`

This packet prepares the next possible local/dev crop-only provider gate after
the successful transport retry and operator visual review for
`pm001-solid-frontal`.

It does not approve provider/OpenAI execution, staging changes, production
changes, runtime changes, bot/admin enablement, or user-facing rollout.

## Baseline

Baseline before this packet:

```text
main@d5a77cf0328aee36413c7599a40d92916b61fea6
```

## Parent Evidence

Track B transport retry 008:

- decision: `TRANSPORT_RETRY_READY_FOR_OPERATOR_REVIEW`
- fixture completed: `pm001-solid-frontal`
- provider HTTP requests: `1`
- retry count: `0`
- preservation: pass
- protected-region drift: `0.0`

Track B operator visual review 008:

- decision: `PASS_FOR_MORE_LOCAL_CROP_ONLY_TESTING`
- fixture reviewed: `pm001-solid-frontal`
- overall score: `4.2`
- important risk: provider crop output itself introduced a realistic torso/arms,
  so provider restraint is not proven.

This means the next gate should remain local/dev, capped, fixture-limited, and
operator-reviewed before any broader claim.

## Goal

Prepare a capped local/dev provider packet for the remaining synthetic fixtures:

```text
pm001-pattern-boundary
pm003-large-pattern-scale
pm004-edge-boundary-stress
```

The gate should answer only this question after a future explicit GO:

```text
Can crop-only provider edits on the remaining synthetic fixtures be reconciled
and composited locally while preserving protected regions?
```

This packet is not rollout evidence and not a user-facing try-on approval.

## Execution Approval State

Execution approval: `NOT APPROVED`

Provider/OpenAI calls: `BLOCKED`

Staging/prod/env changes: `BLOCKED`

Runtime/bot/admin behavior changes: `BLOCKED`

User-facing rollout: `BLOCKED`

## Proposed Remaining-Fixtures Shape

Experiment ID: `crop-only-track-b-remaining-fixtures-009`

Future target after explicit GO: `local/dev crop-only provider remaining fixtures`

Provider/model/endpoint after explicit GO:

```text
provider: OpenAI
model: gpt-image-1
endpoint: /v1/images/edits
```

Allowed provider input scope:

```text
crop_source + crop_mask + fabric_reference only
```

Forbidden provider input:

```text
full source/person/scene
```

Fixture scope after explicit GO:

```text
pm001-pattern-boundary
pm003-large-pattern-scale
pm004-edge-boundary-stress
```

Expected provider generations after explicit GO: `3`

Maximum provider HTTP requests after explicit GO: `4`

Retry policy after explicit GO:

```text
maximum one total retry, only for transient transport/provider failure, and
only if the retry stays within the four-request cap.
```

Stop-on-failure policy after explicit GO:

```text
Stop immediately on the first preservation threshold failure, unreconciled
dimension mismatch, invalid output, provider payload exposure risk, or call-cap
risk.
```

## Required Fixtures

Use only committed synthetic fixtures from
`docs/experiments/fixtures/crop_only_visual_quality_expansion_manifest_003.json`.

Real user photos are forbidden.

## Required Preflight Before Any Future GO

- Fresh explicit GO recorded in Issue #66 or a follow-up issue.
- Exact target selected: local/dev.
- Output directory specified.
- Provider/model/endpoint restated immediately before execution.
- Call cap restated immediately before execution.
- Retry policy restated immediately before execution.
- Stop-on-failure policy restated immediately before execution.
- `OPENAI_API_KEY` presence confirmed without printing the value.
- Each selected fixture's `crop_source`, `crop_mask`, and `fabric_reference`
  resolve to committed synthetic PNG assets.
- Full-scene provider input remains forbidden.
- No Telegram user-facing path is enabled.
- No admin public user-facing path is enabled.
- No production deploy, production env, imports, SQL, or direct DB writes.
- No secrets, base64 payloads, raw provider payloads, or raw image bytes are
  printed or committed.

## Required Artifact Plan

Future artifacts, if separately approved:

```text
/tmp/crop-only-track-b-remaining-fixtures-009/
  requests/
  provider_outputs/
  reconciled_crops/
  composites/
  preservation/
  visual_review/
  execution_summary.json
  execution_summary.md
```

Allowed committed evidence after execution:

- redacted request/result status;
- fixture ids;
- provider call count;
- retry count;
- stop condition;
- output dimensions;
- dimension reconciliation summary;
- preservation summary;
- manual visual score summary.

Forbidden committed evidence:

- provider output binaries unless explicitly reviewed later;
- raw provider response payloads;
- base64 image strings;
- secrets or tokens;
- real user photos;
- private storage data.

## Required Gates If Provider Outputs Are Produced

Each completed fixture must pass:

```text
mean_delta <= 1.0
changed_pixel_percent <= 1.0
pixel_delta_threshold = 8
protected_region_drift = no
dimension_reconciliation_applied = yes
local_composite_created = yes
```

Manual visual review must remain conservative:

```text
minimum_average_score >= 4.0
minimum_dimension_score >= 4
user_facing_rollout_approved = no
```

## Stop Conditions

Stop immediately and record HOLD/NO-GO if any condition occurs:

- explicit GO missing;
- fixture assets missing;
- provider/model/config unknown;
- call cap would be exceeded;
- retry would exceed cap;
- full source/person/scene selected as provider input;
- mask missing, invalid, or empty;
- no-mask prompt-only path selected;
- provider output cannot be tied to fixture id;
- output dimensions unreadable;
- dimension reconciliation missing;
- local composite failed;
- preservation report missing or failing;
- manual visual score below threshold;
- secrets, base64, raw image bytes, or raw provider payloads would be exposed;
- production, public rollout, real user photo, imports, SQL, or direct DB writes
  would be involved.

## Non-Approvals

This packet does not approve:

- provider/OpenAI execution;
- staging execution;
- production rollout;
- user-facing try-on;
- Telegram/admin enablement;
- runtime route changes;
- staging/prod/env changes;
- no-mask fallback;
- use of real user photos;
- visual-quality approval;
- broader fixture execution beyond the listed three fixtures.

## Next Gate

Before any execution, request a fresh explicit GO with exact target, provider,
model, endpoint, call cap, retry cap, output directory, artifact policy, safety
boundaries, stop conditions, and visual review requirements.
