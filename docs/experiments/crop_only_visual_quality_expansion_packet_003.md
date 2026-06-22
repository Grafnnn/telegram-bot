# Crop-Only Visual Quality Expansion Packet 003

## Status

Status: `PROPOSAL_ONLY / NOT APPROVED FOR EXECUTION`

This packet extends the positive technical evidence from
`crop-only-provider-retry-002` into a future visual-quality evidence gate. It
does not approve provider/OpenAI calls.

It does not approve production rollout, staging changes, runtime changes,
Telegram/admin enablement, or user-facing try-on.

## Context

Previous evidence:
[`docs/experiments/reports/crop_only_provider_retry_002.md`](reports/crop_only_provider_retry_002.md)

`crop-only-provider-retry-002` showed that crop-only provider output can be
reconciled and composited back with zero protected-region drift on two
synthetic fixtures. That proves a narrow technical property:

```text
crop-only provider output -> explicit dimension reconciliation -> local composite -> preservation pass
```

It does not prove visual quality, fabric realism, boundary quality, repeatable
prompt behavior, or user-facing readiness.

## Goal

Design the next capped experiment for visual-quality evidence while preserving
the crop-only safety boundary.

The next question is:

```text
Can crop-only output remain preservation-safe while producing useful garment
fabric placement, scale, boundaries, and lighting across a wider synthetic
fixture set?
```

## Execution Approval State

Execution approval: `NOT APPROVED`

Provider/OpenAI calls: `BLOCKED`

Runtime/staging/prod/env changes: `BLOCKED`

User-facing rollout: `BLOCKED`

## Proposed Target

Experiment ID: `crop-only-visual-quality-expansion-003`

Target: `local/dev` only by default

Provider: OpenAI

Model: `gpt-image-1`

Endpoint: `/v1/images/edits`

Provider input scope:

```text
crop_source + crop_mask + fabric_reference only
```

The provider must not receive the full source/person/scene.

## Fixture Plan

Manifest:
[`docs/experiments/fixtures/crop_only_visual_quality_expansion_manifest_003.json`](fixtures/crop_only_visual_quality_expansion_manifest_003.json)

Fixture categories:

1. `solid_frontal_baseline`
2. `pattern_boundary_baseline`
3. `large_scale_pattern`
4. `edge_boundary_stress`

The first two fixtures reuse the successful synthetic crop-only fixtures. The
last two are intentionally `TBD` in this proposal and must be created as
synthetic-only assets before execution can be approved.

## Call Cap

Expected provider generations: `4`

Maximum total HTTP requests: `5`

Retry policy: maximum one total retry, only for transient provider failure and
only after a separate explicit GO.

Any provider/OpenAI call without a fresh explicit GO is forbidden.

## Required Preflight Before Any GO

- All `TBD` fixture paths are replaced with real synthetic PNG assets.
- Source and mask dimensions match for every fixture.
- Crop source and crop mask dimensions match expected crop dimensions.
- Mask has a non-empty editable clothing region and non-empty protected region.
- Fabric references are synthetic and valid PNG images.
- Provider/model/config are confirmed without printing secrets.
- Cost/call cap is restated immediately before execution.
- Output directory is specified.
- No prod, staging env, runtime, bot, imports, SQL, direct DB writes, real user
  photos, or user-facing enablement are involved.

## Required Artifact Plan

Future execution artifacts, if separately approved:

```text
/tmp/crop-only-visual-quality-003-execution/
  provider_outputs/
  reconciled_crops/
  composites/
  preservation/
  visual_review/
  execution_summary.json
  execution_summary.md
```

Allowed committed evidence after execution:

- redacted metrics;
- fixture ids;
- repo-relative synthetic fixture paths;
- preservation summaries;
- visual review scores and notes;
- redacted local artifact references if useful.

Forbidden committed evidence:

- provider output binaries unless explicitly reviewed later;
- raw provider response payloads;
- base64 image strings;
- secrets or tokens;
- real user photos;
- private storage data.

## Preservation Gates

Every fixture must pass:

```text
mean_delta <= 1.0
changed_pixel_percent <= 1.0
pixel_delta_threshold = 8
protected_region_drift = no
face/body/hands/background drift = no
fabric outside clothing mask = no
```

Any preservation failure is `NO-GO`.

## Visual Review Gates

Use the Track A rubric from
[`docs/visual_quality_provider_strategy.md`](../visual_quality_provider_strategy.md).

Minimum for more testing:

- preservation pass on every fixture;
- average visual score >= `4.0`;
- no critical visual dimension below `4`;
- reviewer notes for fabric placement, boundary quality, fabric scale, lighting,
  folds, and artifacts;
- no result can approve rollout by itself.

## Stop Conditions

Stop immediately and record HOLD/NO-GO if any condition occurs:

- explicit GO missing;
- fixture assets missing or still marked `TBD`;
- provider/model/config unknown;
- call cap would be exceeded;
- full source/person/scene selected as provider input;
- mask missing, invalid, or empty;
- no-mask prompt-only path selected;
- provider output cannot be tied to fixture id;
- provider output dimensions unreadable;
- explicit dimension reconciliation not applied;
- reconciled crop dimensions mismatch crop box;
- local composite fails;
- preservation report missing or failing;
- face/body/hands/background drift observed;
- fabric scale, garment boundary, or pattern distortion is severe;
- secrets, base64, raw image bytes, or raw provider payloads would be exposed;
- staging/prod/env/runtime/bot behavior would be touched unexpectedly.

## Non-Approvals

This packet does not approve:

- provider/OpenAI execution;
- production rollout;
- user-facing try-on;
- Telegram/admin enablement;
- runtime route changes;
- staging/prod/env changes;
- no-mask fallback;
- use of real user photos.

## Next Gate

Before any execution, create or validate the two missing synthetic fixture
categories and update the manifest so it contains only concrete local assets.
Then request a fresh explicit GO with the exact call cap, output directory, and
stop conditions.
