# Provider/Mask Execution Packet 001

## Status

Status: DRAFT / NOT APPROVED FOR EXECUTION

This packet does not authorize provider/OpenAI calls.
This packet does not authorize experiment execution.
This packet does not authorize provider strategy selection.
This packet does not authorize user-facing rollout.
A separate explicit approval is required before any provider call.

Until the Approval section is completed and approved, this packet is
documentation only.

## Metadata

Experiment ID: provider-mask-001

Issue: TBD - issue must be created and linked before execution.

PR: this PR

Baseline: main@1da72c98fa544ae5fc727c61c6f426cf1b462e41

Operator: TBD

Reviewer: TBD

Target environment: local/dev only by default

Execution status: not executed

Approval status: not approved

## Scope

Prepare the first controlled provider/mask experiment packet for future
approval. The future experiment is intended to answer:

Can a capped provider plus explicit mask configuration produce visually useful
clothing/fabric try-on outputs while preserving protected regions and failing
closed when preservation checks fail?

This packet separates the question into two axes:

1. Preservation correctness.
2. Visual usefulness.

Preservation pass is required before visual quality can be considered. Visual
quality cannot override preservation failure. A good-looking but unsafe result
is NO-GO. A safe but visually useless result is not rollout-ready.

## Non-Goals

- No provider/OpenAI execution in this PR.
- No automatic provider execution in CI.
- No staging/prod mutation.
- No env changes.
- No runtime behavior changes.
- No bot behavior changes.
- No real user photos.
- No Telegram user exposure.
- No provider strategy approval.
- No user-facing rollout approval.
- No persistence of raw provider image bytes.
- No base64 payloads in repo, logs, comments, or PR body.
- No imports.
- No SQL/direct DB writes.

## Baseline

Current safe baseline:

- main@1da72c98fa544ae5fc727c61c6f426cf1b462e41;
- PR #54 merged;
- Issue #53 closed / completed;
- controlled provider/mask experiment planning docs exist;
- provider/OpenAI execution is not approved;
- provider strategy is not approved;
- user-facing rollout is not approved.

## Provider Candidate

provider_name: OpenAI image editing provider

model_or_endpoint: TBD from existing project configuration and current official
provider documentation before execution

mode: image-edit

mask_support: explicit mask candidate, must be confirmed before execution

expected_call_count: 2

max_allowed_call_count: 3

network_required: yes, future execution only

estimated_cost: TBD before execution

latency_expectation: TBD before execution

input_size_limits: TBD from current official provider documentation and project
configuration before execution

output_size_limits: TBD from current official provider documentation and project
configuration before execution

known_provider_risks:

- provider may ignore or weaken mask semantics;
- provider may alter protected face, hair, skin, hands, body, pose, silhouette,
  background, or objects;
- provider may create visually pleasing but unsafe full-scene regeneration;
- provider output may pass visually for one sample and fail on nearby samples;
- provider latency and cost may exceed product constraints.

execution_allowed_now: no

Model/endpoint must be confirmed from current official provider documentation
and project configuration before execution. This packet proposes a candidate
path only and does not approve any provider call.

## Model / Endpoint Candidate

Model/endpoint candidate: TBD from existing project configuration and current
approved provider documentation

Repository evidence to confirm before execution:

- current image edit configuration names in runtime settings;
- mask support semantics for the selected endpoint;
- accepted input formats and size limits;
- output format and size behavior;
- expected cost and latency;
- any provider privacy/data handling constraints.

Do not infer endpoint behavior from this document. If the model, endpoint, or
mask semantics are unknown, execution is NO-GO.

## Mask Strategy

mask_strategy: provided explicit mask

mask_source: synthetic/operator-created test mask

mask_format: PNG with alpha or binary mask, exact format to match provider
requirements

alpha_channel_required: yes if provider requires alpha

editable_region: garment/fabric region only

protected_regions: face, hair, skin, hands, background, non-garment areas

mask_validation_method: offline metadata and visual review before execution

known_mask_risks:

- mask may include protected skin, hands, hair, or background;
- mask may be too small or too large to be meaningful;
- mask boundary may create artifacts even when provider follows it;
- provider mask convention may differ from local preservation convention;
- weak/unknown mask semantics cannot support clothing-only rollout.

execution_allowed_now: no

Hard gates:

- No-mask prompt-only mode is not allowed for this experiment.
- Mask must not include face/hair/skin/background.
- Mask must not include hands unless explicitly reviewed as unavoidable.
- Invalid mask means no provider call.
- Weak/unknown mask semantics cannot support clothing-only rollout.

## Fixture Pack

Fixture manifest:

- [`docs/experiments/fixtures/provider_mask_fixture_manifest_001.json`](fixtures/provider_mask_fixture_manifest_001.json)

The first packet includes exactly two planned synthetic-only fixtures:

1. `pm001-solid-frontal`
2. `pm001-pattern-boundary`

No real image files are included in this PR. The manifest contains metadata
placeholders only. Before any future execution, source, mask, and fabric
references must be created or selected as synthetic/sanitized local/dev inputs
and reviewed against the manifest.

Fixture pack hard rules:

- real user photos are not allowed;
- customer, operator, employee, Telegram, staging, or production photos are not
  allowed;
- base64 image payloads are not allowed;
- raw provider output is not allowed in the repo or GitHub comments;
- every output must remain tied to a fixture id and report id.

## Call Cap

Expected provider calls: 2

Maximum allowed provider calls: 3

Retry policy: at most 1 retry total, only if failure is provider/network/
transient and no safety condition is violated

Calls beyond cap: forbidden

Execution without recorded approval: forbidden

Execution in CI: forbidden

Two calls are enough for the first controlled smoke because the fixture pack has
two planned cases. Three is a hard cap that permits at most one retry for a
transient provider/network failure. Any call beyond the cap is a stop condition.

If the call cap would be exceeded, stop immediately and record NO-GO / needs
new approval.

## Cost / Risk

Estimated cost: TBD before execution

Cost acceptance required: yes

Network required: yes

Provider terms/privacy review required: yes if not already covered

Data sent to provider: synthetic image + synthetic mask + synthetic fabric
reference only

Data not sent: real user photos, private storage images, secrets, production
data

Risks:

- provider may ignore mask;
- provider may alter protected regions;
- provider may hallucinate garment/body artifacts;
- provider may change face/hair/skin/background;
- provider output may be visually pleasing but unsafe;
- provider output may be safe but visually useless;
- provider latency/cost may be unacceptable.

## Safety Checklist

- [ ] Execution packet approved
- [ ] Linked issue exists
- [ ] Baseline commit confirmed
- [ ] Working tree clean
- [ ] Provider/model confirmed
- [ ] Call cap confirmed
- [ ] Cost accepted
- [ ] Local/dev target confirmed
- [ ] Staging/prod untouched
- [ ] Env unchanged
- [ ] No real user photos
- [ ] No private storage images
- [ ] No secrets
- [ ] No base64/raw image bytes
- [ ] No imports
- [ ] No SQL/direct DB writes
- [ ] Fixture manifest complete
- [ ] Synthetic fixtures reviewed
- [ ] Masks reviewed
- [ ] Preservation command selected
- [ ] Visual quality report template selected
- [ ] Stop conditions accepted
- [ ] Rollback/cleanup plan accepted

Any unchecked critical safety item blocks execution.

## Pre-Execution Checks

Before any future provider call, record:

```text
Repo clean: yes/no
Branch name:
Baseline commit:
Execution packet approved: yes/no
Linked issue exists: yes/no
Provider/model/config named: yes/no
Call cap confirmed: yes/no
Provider cost accepted: yes/no
Network call expected: yes/no
Target local/dev only: yes/no
Staging/prod untouched: yes/no
Env unchanged: yes/no
No real user photos: yes/no
No private storage images: yes/no
No base64/raw image dumps: yes/no
Mask validated: yes/no
Fixture metadata complete: yes/no
Preservation command selected: yes/no
Visual report template selected: yes/no
Rollback/cleanup plan written: yes/no
```

If any critical answer is `no`, execution must not start.

## Future Execution Commands

Do not execute these commands now. They are future commands only.

```bash
# Future only. Do not run until this packet is explicitly approved.
python3 scripts/validate_provider_mask_execution_packet.py

# Future only. Validate fixture metadata.
python3 scripts/validate_provider_mask_execution_packet.py \
  --manifest docs/experiments/fixtures/provider_mask_fixture_manifest_001.json

# Future only. Run provider/mask experiment command.
# Exact command TBD after confirming existing project runner/API.
# Must include experiment id, fixture manifest, max call cap, output dir,
# and no-raw-payload logging.
```

Existing local preservation drift tooling can be used after provider output is
available:

```bash
# Future only. Example preservation report command for one approved fixture.
python3 scripts/check_preservation_drift.py \
  --base TBD_SOURCE_IMAGE \
  --candidate TBD_PROVIDER_OUTPUT \
  --mask TBD_MASK_IMAGE \
  --output TBD_PRESERVATION_REPORT
```

No provider execution command is approved or finalized by this packet.

## Required Artifacts

Future execution must produce:

- execution log with no secrets/base64/raw image bytes;
- fixture manifest snapshot;
- provider call summary;
- preservation metrics report;
- visual quality review report;
- decision summary;
- cleanup confirmation.

Allowed artifacts:

- markdown summary;
- JSON metrics;
- synthetic fixture references;
- redacted output references;
- visual reviewer score table.

Disallowed artifacts:

- real user photos;
- raw provider response payloads;
- base64 image strings;
- secrets/tokens;
- private local file paths;
- production/staging user data;
- unredacted storage URLs.

## Preservation Review

Future execution must record:

```text
fixture_id:
output_id:
mean_delta:
changed_pixel_percent:
max_delta:
protected_region_drift: yes/no
identity_face_drift: yes/no
background_drift: yes/no
mask_boundary_drift: yes/no
pass_fail:
reviewer_notes:
```

Hard rules:

- Preservation fail = NO-GO.
- Protected-region drift = NO-GO.
- Identity/face drift = NO-GO.
- Background drift = NO-GO unless explicitly outside protected region and
  reviewer-approved.
- Fabric outside garment region = NO-GO.

## Visual Quality Review

Use the Track A rubric from
[`docs/visual_quality_provider_strategy.md`](../visual_quality_provider_strategy.md).

Score dimensions:

- garment placement plausibility;
- fabric pattern continuity;
- fabric scale realism;
- body/pose preservation;
- face/hair/skin/background preservation;
- lighting/shadow consistency;
- garment boundary quality;
- absence of hallucinated artifacts;
- output resolution/format acceptability;
- repeatability expectation;
- cost/latency awareness.

Scoring:

- `1` = severe failure
- `2` = visible problem
- `3` = marginal/internal only
- `4` = good controlled review candidate
- `5` = strong result for tested fixture

Threshold for future `GO_FOR_MORE_TESTING`:

- preservation pass required;
- average visual score >= 4.0;
- no critical dimension below 4;
- reviewer notes required;
- no single result can approve rollout.

Decision labels:

- `GO_FOR_MORE_TESTING`
- `HOLD_PROVIDER_ADJUSTMENT`
- `NO_GO`

## Stop Conditions

Mandatory stop conditions:

- Provider call attempted without approval
- Provider/model/config unknown
- Call cap exceeded
- Real user photo detected
- Private storage image detected
- Staging/prod/env touched unexpectedly
- Secret/token exposed
- Base64/raw image payload exposed
- Mask missing
- Mask invalid
- No-mask prompt-only mode used
- Provider ignores mask
- Protected-region drift detected
- Face/identity drift detected
- Background drift detected
- Fabric appears outside garment region
- Severe garment boundary artifacts
- Hallucinated body parts/objects/text
- Output cannot be tied to fixture_id
- Preservation report missing
- Visual quality report missing

If any stop condition occurs:

Stop immediately.
Do not retry unless retry is explicitly allowed and does not violate safety.
Record NO-GO or HOLD.
Do not proceed to rollout.

## Artifact / Logging Policy

Logs and artifacts must be safe to review in GitHub and CI.

Allowed:

- redacted markdown summaries;
- JSON metrics without raw image payloads;
- synthetic fixture references;
- provider call count, latency, cost estimate, and status metadata;
- visual reviewer score tables.

Forbidden:

- secrets or tokens;
- real user photos;
- raw provider responses containing image bytes;
- base64 image strings;
- raw local filesystem paths from operator machines;
- private storage images or storage URLs;
- production or staging user data;
- unredacted provider traces.

## Rollback / Cleanup

Future execution cleanup must record:

- output directory path or artifact location;
- generated files retained or deleted;
- reason for retaining any artifact;
- confirmation that no raw/base64 payloads were stored;
- confirmation that no staging/prod/env changes occurred;
- confirmation that no imports, SQL, or direct DB writes occurred.

If a safety incident occurs, stop, preserve only redacted evidence, and create a
new safety follow-up before any additional provider call.

## Approval

Execution approval: NOT APPROVED

Approver:

Date:

Approved provider/model:

Approved mask strategy:

Approved fixture manifest:

Approved max call count:

Approved cost ceiling:

Approved target environment:

Additional constraints:

Until this section is completed and approved, this packet is documentation
only.

## Final Decision

Final decision: NOT EXECUTED / NO DECISION

Reviewer:

Date:

Preservation decision:

Visual quality decision:

Recommended next gate:

Rollout allowed: no
