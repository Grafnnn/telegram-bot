# Crop-Only Track B Operator Review Readiness 006

## Status

Status: `READINESS_PACKET / NOT APPROVED FOR EXECUTION`

This packet narrows the next possible gate after Track A fake-provider evidence.
It does not approve provider/OpenAI calls, staging changes, runtime changes,
bot changes, admin enablement, or user-facing rollout.

## Baseline

Baseline before this readiness packet:

```text
main@787665fb05e19eb78ec25105f80a093c267ab91d
```

## Parent Evidence

Track A fake-provider evidence:

- [`docs/experiments/reports/crop_only_track_a_fake_provider_smoke_005.json`](reports/crop_only_track_a_fake_provider_smoke_005.json)
- [`docs/experiments/reports/crop_only_track_a_fake_provider_smoke_005.md`](reports/crop_only_track_a_fake_provider_smoke_005.md)

Track A result:

```text
Decision: TRACK_A_FAKE_PROVIDER_ROUTE_SMOKE_READY
Provider/OpenAI calls: 0
Network provider invoked: false
```

Important limitation: local route-level execution was not run because the local
FastAPI dependency was unavailable. Route-level behavior remains covered by
PR #75 CI tests.

## Goal

Prepare a controlled Track B operator-review execution packet while keeping the
provider call gate closed.

Track B should answer only this question after a future explicit GO:

```text
Can the crop-only provider path produce operator-reviewable outputs through the
same fixture and preservation contract without enabling any user-facing path?
```

## Execution Approval State

Execution approval: `NOT APPROVED`

Provider/OpenAI calls: `BLOCKED`

Staging/prod/env changes: `BLOCKED`

Runtime/bot/admin behavior changes: `BLOCKED`

User-facing rollout: `BLOCKED`

## Proposed Track B Execution Shape

Experiment ID: `crop-only-track-b-operator-review-readiness-006`

Future target after explicit GO: `local/dev controlled provider operator review`

Provider/model after explicit GO:

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

Expected provider generations after explicit GO: `4`

Maximum provider HTTP requests after explicit GO: `5`

Retry policy after explicit GO:

```text
maximum one total retry, only for transient provider failure, and only if the
retry stays within the maximum provider HTTP request cap.
```

## Required Synthetic Fixtures

Track B must use only the four committed synthetic fixtures from
`crop-only-visual-quality-expansion-003`:

1. `pm001-solid-frontal`
2. `pm001-pattern-boundary`
3. `pm003-large-pattern-scale`
4. `pm004-edge-boundary-stress`

Real user photos are forbidden.

## Required Preflight Before Any Future GO

- Fresh explicit GO recorded in Issue #66 or a follow-up issue.
- Exact target selected: local/dev only unless a new staging packet is merged.
- Output directory specified.
- Provider/model/endpoint restated immediately before execution.
- Call cap restated immediately before execution.
- Retry policy restated immediately before execution.
- All fixture assets resolve to real synthetic PNG assets.
- Full-scene provider input remains forbidden.
- No Telegram user-facing path is enabled.
- No admin public user-facing path is enabled.
- No production deploy, production env, imports, SQL, or direct DB writes.
- No secrets, base64 payloads, raw provider payloads, or raw image bytes are
  printed or committed.

## Required Artifact Plan

Future artifacts, if separately approved:

```text
/tmp/crop-only-track-b-operator-review-006/
  requests/
  provider_outputs/
  reconciled_crops/
  composites/
  preservation/
  operator_review/
  execution_summary.json
  execution_summary.md
```

Allowed committed evidence after execution:

- redacted metrics;
- fixture ids;
- repo-relative synthetic fixture paths;
- preservation summaries;
- visual/operator review scores and notes;
- redacted local artifact references if useful.

Forbidden committed evidence:

- provider output binaries unless explicitly reviewed later;
- raw provider response payloads;
- base64 image strings;
- secrets or tokens;
- real user photos;
- private storage data.

## Required Gates

Every future run must pass:

```text
mean_delta <= 1.0
changed_pixel_percent <= 1.0
pixel_delta_threshold = 8
protected_region_drift = no
face/body/hands/background drift = no
fabric outside clothing mask = no
operator_review_complete = yes
average_visual_score >= 4.0
minimum_dimension_score >= 4
no critical operator note unresolved
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
- output cannot be tied to fixture id;
- output dimensions unreadable;
- dimension reconciliation missing;
- local composite fails;
- preservation report missing or failing;
- visual/operator review missing or failing;
- face/body/hands/background drift observed;
- secrets, base64, raw image bytes, or raw provider payloads would be exposed;
- production, public rollout, real user photo, imports, SQL, or direct DB writes
  would be involved.

## Non-Approvals

This readiness packet does not approve:

- provider/OpenAI execution;
- staging execution;
- production rollout;
- user-facing try-on;
- Telegram/admin enablement;
- runtime route changes;
- staging/prod/env changes;
- no-mask fallback;
- use of real user photos.

## Next Gate

Before any execution, request a fresh explicit GO with exact target, provider,
model, endpoint, call cap, retry cap, output directory, artifact policy, safety
boundaries, and stop conditions.
