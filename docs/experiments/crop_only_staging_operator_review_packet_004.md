# Crop-Only Staging Operator Review Packet 004

## Status

Status: `PROPOSAL_ONLY / NOT APPROVED FOR EXECUTION`

This packet prepares the next safe gate after the successful
`crop-only-visual-quality-expansion-003` synthetic evidence run. It does not
approve provider/OpenAI calls, staging changes, runtime changes, bot changes,
admin enablement, or user-facing rollout.

## Context

Parent evidence:
[`docs/experiments/reports/crop_only_visual_quality_expansion_003.json`](reports/crop_only_visual_quality_expansion_003.json)

That run produced four successful crop-only provider generations with zero
protected-region drift and a passing visual review average. The decision was
`GO_FOR_MORE_CROP_ONLY_TESTING`, not rollout approval.

## Goal

Prepare an operator-only staging integration evidence gate while keeping the
crop-only safety boundary intact.

The next question is:

```text
Can the crop-only pipeline be exercised through a staging-like operator review
workflow without exposing user-facing Telegram/admin behavior or allowing
uncontrolled provider calls?
```

## Execution Approval State

Execution approval: `NOT APPROVED`

Provider/OpenAI calls: `BLOCKED`

Staging/prod/env changes: `BLOCKED`

Runtime/bot/admin behavior changes: `BLOCKED`

User-facing rollout: `BLOCKED`

## Proposed Target

Experiment ID: `crop-only-staging-operator-review-004`

Default target: `local/dev documentation and validation only`

Future target after explicit GO: `operator-only staging integration smoke`

Manifest:
[`docs/experiments/fixtures/crop_only_staging_operator_review_manifest_004.json`](fixtures/crop_only_staging_operator_review_manifest_004.json)

## Proposed Tracks

### Track A: fake-provider staging route smoke

Purpose: prove request routing, artifact handling, preservation validation,
operator review metadata, and stop conditions without real provider calls.

Provider/OpenAI calls: `0`

Allowed input scope:

```text
crop_source + crop_mask + fabric_reference only
```

Fake output source: deterministic local synthetic crop output or fixture copy.

### Track B: controlled provider operator review

Purpose: only after Track A passes and a fresh explicit GO is recorded, repeat a
small crop-only provider run through the operator review workflow.

Expected provider generations: `4`

Maximum provider HTTP requests: `5`

Retry policy: maximum one total retry, only for transient provider failure and
only after a separate explicit GO.

Track B must use only the four synthetic fixtures from
`crop-only-visual-quality-expansion-003` unless a new fixture PR is merged.

## Required Synthetic Fixtures

The packet reuses the concrete synthetic fixtures from:
[`docs/experiments/fixtures/crop_only_visual_quality_expansion_manifest_003.json`](fixtures/crop_only_visual_quality_expansion_manifest_003.json)

Required fixture ids:

1. `pm001-solid-frontal`
2. `pm001-pattern-boundary`
3. `pm003-large-pattern-scale`
4. `pm004-edge-boundary-stress`

Real user photos are forbidden.

## Required Preflight Before Any GO

- Fresh explicit GO recorded in Issue #66 or a follow-up issue.
- Exact track selected: Track A fake-provider or Track B controlled provider.
- Exact target selected: local/dev or operator-only staging.
- Output directory specified.
- Provider/model/config confirmed if Track B is selected.
- Cost/call cap restated immediately before execution if Track B is selected.
- All fixture assets resolve to real synthetic PNG assets.
- Full-scene provider input remains forbidden.
- No Telegram user-facing path is enabled.
- No admin public user-facing path is enabled.
- No production deploy, production env, imports, SQL, or direct DB writes.
- No secrets, base64 payloads, raw provider payloads, or raw image bytes are printed or committed.

## Required Artifact Plan

Future Track A artifacts, if separately approved:

```text
/tmp/crop-only-staging-operator-review-004-fake/
  requests/
  fake_provider_outputs/
  composites/
  preservation/
  operator_review/
  execution_summary.json
  execution_summary.md
```

Future Track B artifacts, if separately approved:

```text
/tmp/crop-only-staging-operator-review-004-provider/
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
```

For Track B, visual/operator review must also pass:

```text
average_visual_score >= 4.0
minimum_dimension_score >= 4
no critical operator note unresolved
```

## Stop Conditions

Stop immediately and record HOLD/NO-GO if any condition occurs:

- explicit GO missing;
- track is ambiguous;
- fixture assets missing;
- provider/model/config unknown for Track B;
- call cap would be exceeded;
- full source/person/scene selected as provider input;
- mask missing, invalid, or empty;
- no-mask prompt-only path selected;
- output cannot be tied to fixture id;
- output dimensions unreadable;
- explicit dimension reconciliation not applied;
- local composite fails;
- preservation report missing or failing;
- visual/operator review missing or failing;
- face/body/hands/background drift observed;
- secrets, base64, raw image bytes, or raw provider payloads would be exposed;
- production, public rollout, real user photo, imports, SQL, or direct DB writes would be involved.

## Non-Approvals

This packet does not approve:

- provider/OpenAI execution;
- fake-provider staging execution;
- controlled-provider staging execution;
- production rollout;
- user-facing try-on;
- Telegram/admin enablement;
- runtime route changes;
- staging/prod/env changes;
- no-mask fallback;
- use of real user photos.

## Next Gate

Before any execution, request a fresh explicit GO with selected track, exact
call cap, output directory, provider/model/config if applicable, artifact
policy, and stop conditions.
