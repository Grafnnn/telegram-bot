# Crop-Only Provider Execution Packet 001

## Status

Status: `PROPOSAL_ONLY / NOT APPROVED FOR EXECUTION`

This packet defines the first capped provider experiment for the
segmentation-first crop/composite strategy. It is a planning and approval
artifact only.

This packet does not authorize provider/OpenAI calls.
This packet does not authorize staging/prod changes.
This packet does not authorize user-facing rollout.
This packet does not authorize Telegram/admin enablement.

## Metadata

Experiment ID: `crop-only-provider-001`

Parent strategy:
[`docs/segmentation_crop_composite_strategy.md`](../segmentation_crop_composite_strategy.md)

Prerequisite offline rehearsal:
[`docs/experiments/reports/crop_composite_offline_rehearsal_001.md`](reports/crop_composite_offline_rehearsal_001.md)

Fixture manifest:
[`docs/experiments/fixtures/crop_only_provider_fixture_manifest_001.json`](fixtures/crop_only_provider_fixture_manifest_001.json)

Baseline: `main@2e9778cdfb4530bf6f913fbba8d3b6de7a861390`

Target environment: `local/dev` only by default

Execution status: `not_run`

Approval status: `not_approved`

Execution allowed now: `no`

## Goal

Test whether a provider can edit only the garment crop while local code
composites the crop back into the original full image and preservation
guardrails verify protected regions.

The specific question is narrow:

```text
Can crop-only provider output, after local composite, preserve face/body/hands/background outside the clothing mask?
```

This is not a full visual-quality or rollout approval. A passing result would
only justify more controlled testing.

## Why This Differs From Provider/Mask 001

`provider-mask-001` sent the provider the full scene plus a mask. It failed
preservation on both controlled fixtures and remains NO-GO.

This packet changes the provider surface:

```text
full source + full mask -> crop source + crop mask -> provider edits crop only -> local composite -> full-image preservation guardrail
```

The provider must not receive the full original source image for this packet.
The provider output must not be exposed directly as a final result.
The final candidate must be created by local composite and then checked.

## Scope

Allowed after separate explicit GO only:

- local/dev target;
- synthetic fixtures only;
- garment crop image;
- crop-local mask;
- synthetic fabric reference;
- capped provider calls;
- local composite back into the original source;
- preservation drift report;
- visual review report.

Forbidden:

- provider/OpenAI execution without a separate explicit GO;
- full-scene provider input;
- no-mask prompt-only edit;
- real user photos;
- private storage images;
- staging/prod mutation;
- env mutation;
- Telegram/admin user-facing enablement;
- runtime behavior changes;
- imports;
- SQL/direct DB writes;
- secrets, base64 payloads, raw image bytes, or raw provider payload logging.

## Provider Candidate

provider_name: `OpenAI image editing provider`

model_or_endpoint: TBD from current project configuration and current approved
provider documentation before execution

mode: `crop-only image edit`

required inputs per fixture:

- crop source PNG;
- crop-local mask PNG;
- synthetic fabric reference PNG;
- strict crop-only garment/fabric prompt.

expected_provider_calls: `2`

max_allowed_provider_calls: `3`

retry_policy: at most one retry total, only for transient provider/network
failure, and only after execution approval.

network_required: yes, future execution only

cost_limit: TBD before execution

Execution is NO-GO if provider/model/config, mask semantics, cost, or privacy
terms are not explicitly confirmed.

## Fixture Plan

Exactly two synthetic fixtures are included in the first packet:

| Fixture | Crop source | Crop mask | Fabric reference |
| --- | --- | --- | --- |
| `pm001-solid-frontal` | `docs/experiments/assets/crop-composite-001/pm001-solid-frontal/crop_source.png` | `docs/experiments/assets/crop-composite-001/pm001-solid-frontal/crop_mask.png` | `docs/experiments/assets/provider-mask-001/pm001-solid-frontal-fabric.png` |
| `pm001-pattern-boundary` | `docs/experiments/assets/crop-composite-001/pm001-pattern-boundary/crop_source.png` | `docs/experiments/assets/crop-composite-001/pm001-pattern-boundary/crop_mask.png` | `docs/experiments/assets/provider-mask-001/pm001-pattern-boundary-fabric.png` |

The full source and full mask are used only for local composite and
preservation review. They are not provider inputs for this packet.

## Execution Flow

Future execution, if separately approved:

1. Confirm repo baseline and clean working tree.
2. Validate this packet and fixture manifest.
3. Confirm provider/model/config and call cap.
4. For each fixture, send only crop source, crop mask, and fabric reference to
   the provider.
5. Save provider crop output in the approved local evidence directory.
6. Composite provider crop output into the full original source using local
   crop/composite helpers.
7. Run full-image preservation drift against the original source and full mask.
8. Run manual visual review.
9. Produce JSON and Markdown evidence reports.
10. Record GO/HOLD/NO-GO for more testing only.

No single run can approve user-facing rollout.

## Required Artifact Plan

Future execution must produce, under a local evidence directory:

- execution summary JSON;
- execution summary Markdown;
- per-fixture provider call metadata;
- per-fixture provider crop output reference;
- per-fixture composited full image reference;
- per-fixture preservation drift report;
- visual review notes;
- final decision label.

Allowed artifact content:

- synthetic fixture ids;
- repo-relative fixture paths;
- redacted local evidence paths;
- metrics, dimensions, latency, call count, and cost estimate;
- manual visual notes.

Forbidden artifact content:

- secrets/tokens;
- base64 image strings;
- raw provider response payloads;
- raw image bytes;
- real user photos;
- private storage images;
- production/staging data;
- unredacted provider traces.

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

Preservation failure is NO-GO.
Visual quality cannot override preservation failure.

## Visual Review Gates

Use the Track A rubric from
[`docs/visual_quality_provider_strategy.md`](../visual_quality_provider_strategy.md).

Minimum for more testing:

- preservation pass on every fixture;
- average visual score >= 4.0;
- no critical dimension below 4;
- reviewer notes for garment placement, boundary quality, fabric scale,
  lighting, and artifacts;
- no single result used as rollout approval.

## Stop Conditions

Stop immediately if any condition occurs:

- execution packet not explicitly approved;
- provider/model/config unknown;
- call cap would be exceeded;
- full source image selected as provider input;
- mask missing or invalid;
- no-mask prompt-only mode selected;
- provider crop output dimensions cannot be reconciled;
- composite fails;
- protected-region preservation fails;
- face/body/hands/background drift observed;
- fabric appears outside clothing mask;
- real user photo detected;
- staging/prod/env touched unexpectedly;
- secret/token/base64/raw image payload exposed;
- provider output cannot be tied to fixture id;
- preservation report missing;
- visual report missing.

If a stop condition occurs, record HOLD or NO-GO. Do not continue by trying
nearby prompts or alternate endpoints without a new packet.

## Future Commands

Do not run provider commands from this PR.

Safe validation commands:

```bash
python3 scripts/validate_crop_only_provider_packet.py
python3 -m pytest backend/tests/test_crop_only_provider_packet.py -q
```

Future provider execution command: TBD in a separate execution gate after
approval. This packet intentionally does not include a runnable provider
command.

## Decision Labels

Allowed decision labels after future execution:

- `GO_FOR_MORE_CROP_ONLY_TESTING`
- `HOLD_PROVIDER_OR_PROMPT_ADJUSTMENT`
- `NO_GO_USER_FACING_ROLLOUT`

Forbidden decision labels:

- `PRODUCTION_READY`
- `USER_FACING_READY`
- `ROLL_OUT`

## Final Boundary

This packet is a narrow experiment design. It does not change the project
posture:

- full-scene provider path remains rejected;
- crop/composite mechanics are locally rehearsed only;
- provider/OpenAI is still NO-GO until separate approval;
- user-facing rollout is still blocked;
- runtime/staging/prod remain untouched.
