# Controlled Provider/Mask Experiment Plan

This document is a planning gate for a future controlled provider/mask
experiment. It does not approve execution.

It also does not approve a provider strategy, a mask strategy, production or
staging rollout, or user-facing try-on behavior. Any provider execution requires
a separate explicit approval packet with named inputs, provider configuration,
mask strategy, call count, safety confirmations, and stop conditions.

This plan does not approve execution. Execution requires a separate explicit
approval packet.

## Purpose

The purpose of this plan is to define the minimum safe structure for a future
visual quality and preservation experiment. It prepares the evidence process
without running providers, touching staging or production, changing runtime
behavior, or adding real user photos.

This plan answers:

- what fixtures are eligible for future experiments;
- what provider and mask details must be named before execution;
- what safety checks block execution;
- what artifacts and reports must be produced;
- what conditions force NO-GO;
- how results should be recorded for product and engineering review.

## Current Baseline

Current baseline:

- `main@06c8ad5cd95acd698d770f0868cc60cf190dcaa9`;
- PR #52 merged;
- Issue #51 completed;
- Track A documentation gate completed.

Current project posture:

- preservation guardrails exist;
- route-level smoke exists;
- visual quality/provider strategy is documented;
- a visual quality experiment report template exists;
- provider/mask execution is not approved yet;
- user-facing try-on rollout is not approved.

## Decision Question

Can a controlled provider plus mask configuration produce visually useful
clothing/fabric try-on outputs while preserving protected regions and failing
closed when preservation checks fail?

The answer has two independent axes:

1. Preservation pass/fail.
2. Visual usefulness pass/fail.

Hard interpretation:

- preservation pass is necessary but not sufficient;
- visual quality cannot override preservation failure;
- a good-looking result with protected-region drift is NO-GO;
- a safe but visually useless result is also NO-GO for rollout.

## Experiment Non-Goals

The future experiment must not be treated as:

- user-facing rollout;
- provider strategy approval from a single result;
- production readiness approval;
- Telegram user exposure;
- automatic provider execution in CI;
- segmentation provider implementation;
- staging/prod env mutation.

The future experiment must not use or create:

- real user photos;
- production data;
- private images from production or staging storage;
- raw provider responses containing image bytes;
- base64 image payloads in logs, repo files, GitHub comments, PR bodies, or
  reports;
- persistent raw provider outputs unless a future execution packet explicitly
  approves storage policy and cleanup.

## Allowed Inputs

Allowed input fixtures:

- synthetic mannequin or synthetic person-like fixture generated for testing;
- sanitized non-real-person fixture;
- internal test-only image with no identifiable real person;
- synthetic clothing mask PNG;
- synthetic fabric/reference image;
- deterministic fake provider fixture.

Disallowed input fixtures:

- real customer photo;
- employee or operator personal photo;
- photo from a Telegram user;
- private image from production or staging storage;
- image containing an identifiable face unless explicitly synthetic and
  approved in the execution packet;
- raw unredacted provider output committed to the repo;
- base64 image payload in markdown, logs, reports, or comments.

## Fixture Pack Requirements

Every fixture must include:

```text
fixture_id:
source_image_type:
source_image_path_or_reference:
mask_path_or_reference:
fabric_reference_path_or_reference:
expected_edit_region:
protected_regions:
input_class:
allowed_target:
reviewer:
notes:
```

Future fixture packs should cover fabric, pose, and garment variety without
using real user photos.

Fabric categories:

- solid color;
- small pattern;
- large pattern;
- stripe/check;
- texture-heavy;
- high contrast.

Pose and garment categories:

- frontal top/dress;
- slight turn;
- hands near garment boundary;
- jacket/blazer or structured garment;
- loose garment;
- partial body if relevant.

Minimum future experiment pack:

- at least 2 fabric categories;
- at least 2 garment or pose categories;
- at least 1 hard boundary case;
- capped/manual/approved provider call count only.

Do not put a large or open-ended provider call count into the first execution
packet.

## Provider Strategy Under Test

A provider strategy may be selected only for the controlled experiment. It is
not a rollout decision.

Every execution packet must name:

```text
provider_name:
model_or_endpoint:
mode: image-edit | image-to-image | fake-provider | other
mask_support: explicit | provider-native | weak/unknown | none
expected_call_count:
network_required: yes/no
estimated_cost_if_known:
latency_if_known:
input_size_limits:
output_size_limits:
known_provider_risks:
```

Hard rule:

No provider call may be made unless the execution packet explicitly names the
provider, model/config, and capped call count.

## Mask Strategy Under Test

Allowed for controlled experiments:

- provided mask;
- provider-native mask if documented and testable;
- internal operator mask;
- deterministic fake mask.

Rejected by default:

- no-mask prompt-only mode for user-photo try-on;
- weak or unknown mask semantics for clothing-only UX unless classified as
  exploratory and not eligible for rollout.

Every execution packet must name:

```text
mask_strategy:
mask_source:
mask_format:
alpha_channel_required: yes/no
editable_region_description:
protected_region_description:
mask_validation_method:
known_mask_risks:
```

Hard gates:

- mask must not include face, hair, skin, or background;
- mask must not include hands unless the garment boundary makes it unavoidable
  and a reviewer approves it;
- invalid mask means NO-GO before provider call;
- no-mask mode cannot be used as evidence for clothing-only user-photo rollout.

## Safety Pre-Checks Before Any Future Execution

Complete this checklist before any provider run:

```text
Repo clean: yes/no
Branch name:
Baseline commit:
Execution packet approved: yes/no
Provider/model/config named: yes/no
Call count capped: yes/no
Provider cost accepted: yes/no
Network call expected: yes/no
Target local/dev only unless separately approved: yes/no
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

## Future Execution Packet Template

Use the standalone template:

- [`docs/templates/provider_mask_experiment_packet.md`](templates/provider_mask_experiment_packet.md)

The first concrete draft packet proposal is:

- [`docs/experiments/provider_mask_execution_packet_001.md`](experiments/provider_mask_execution_packet_001.md)

Offline rehearsal for `provider-mask-001` is available at:

- [`docs/experiments/assets/provider-mask-001/`](experiments/assets/provider-mask-001/)
- [`docs/experiments/reports/provider_mask_preservation_rehearsal_001.json`](experiments/reports/provider_mask_preservation_rehearsal_001.json)
- [`docs/experiments/reports/provider_mask_visual_quality_rehearsal_001.md`](experiments/reports/provider_mask_visual_quality_rehearsal_001.md)

This rehearsal validates synthetic fixtures, masks, fake-provider output, and
report plumbing only. It does not authorize provider/OpenAI calls.

Minimum packet fields:

```text
Experiment id:
Issue:
PR:
Baseline commit:
Operator:
Reviewers:
Target environment: local/dev | staging-safe
Why this experiment is needed:
What is being tested:
What is explicitly not being tested:
Provider:
Model/endpoint:
Mode:
Mask strategy:
Expected call count:
Max allowed call count:
Network required:
Cost estimate:
Latency estimate:
Input fixtures:
Output storage policy:
Log redaction policy:
Safety confirmations:
Commands to run:
Expected artifacts:
Preservation report path:
Visual quality report path:
Decision labels:
Rollback/cleanup plan:
Stop conditions:
Approval:
```

The packet authorizes planning only until approval is explicitly recorded.

## Execution Flow For Future Gate

Future execution sequence:

1. Create or confirm fixture pack.
2. Validate fixture metadata.
3. Validate masks.
4. Run fake provider or dry-run first if applicable.
5. Execute capped provider calls only after approval.
6. Run preservation drift analysis.
7. Fill visual quality report.
8. Classify each output:
   - `GO_FOR_MORE_TESTING`;
   - `HOLD_PROVIDER_ADJUSTMENT`;
   - `NO_GO`.
9. Summarize aggregate evidence.
10. Decide next gate.

The experiment may only recommend more testing. It cannot approve user-facing
rollout.

## Preservation Analysis Requirements

Future execution must produce a preservation report with:

```text
mean_delta:
changed_pixel_percent:
max_delta:
protected-region drift: yes/no
identity/face drift: yes/no
background drift: yes/no
mask boundary drift: yes/no
pass/fail:
```

Hard stops:

- preservation fail = NO_GO;
- protected-region drift = NO_GO;
- identity/face drift = NO_GO;
- background drift = NO_GO unless explicitly outside protected region and
  accepted by reviewer; default is NO_GO.

## Visual Quality Review Requirements

Use the rubric from
[`docs/visual_quality_provider_strategy.md`](visual_quality_provider_strategy.md).

Minimum dimensions:

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
- cost/latency awareness if known.

Scoring:

- `1`: severe failure;
- `2`: visible problem;
- `3`: marginal/internal only;
- `4`: good controlled review candidate;
- `5`: strong result for tested fixture.

Thresholds:

- average visual score must be at least `4.0` for `GO_FOR_MORE_TESTING`;
- no critical dimension below `4`;
- preservation must pass;
- reviewer notes are required;
- no single sample approves rollout.

## Stop Conditions / NO-GO Conditions

Mandatory NO-GO:

- provider call happened without approved packet;
- real user photo used;
- staging/prod/env mutated unexpectedly;
- provider/model/config unknown;
- call count exceeded;
- mask invalid or missing;
- no-mask prompt-only path used for clothing-only claim;
- preservation fails;
- identity/face drift;
- protected-region drift;
- fabric appears outside garment region;
- severe garment boundary artifacts;
- hallucinated body parts, objects, or text;
- raw/base64 image data exposed;
- secret/token exposed;
- output cannot be tied to fixture id and report.

## Artifact Policy

Allowed future artifacts:

- markdown reports;
- redacted metadata;
- preservation metrics;
- visual reviewer scores;
- small synthetic fixtures if approved;
- generated output references if safe and not raw/base64.

Disallowed artifacts:

- real user photos;
- provider raw response payloads containing image bytes;
- base64 image strings;
- private file paths from an operator machine;
- secrets or tokens;
- unredacted storage URLs;
- production or staging user data.

## Reporting Format

Future experiment summaries must include:

```text
Experiment id:
Baseline:
Provider/mask strategy:
Fixtures tested:
Calls attempted:
Calls succeeded:
Calls failed:
Preservation pass count:
Preservation fail count:
Average visual score:
Critical failures:
Decision:
Recommendation:
Next gate:
Safety incidents:
```

## Relationship To Existing Docs

This plan sits after the Track A visual quality/provider strategy gate:

- [`docs/visual_quality_provider_strategy.md`](visual_quality_provider_strategy.md)
- [`docs/templates/visual_quality_experiment_report.md`](templates/visual_quality_experiment_report.md)
- [`docs/preservation_drift_runner.md`](preservation_drift_runner.md)
- [`docs/route_preservation_smoke_workflow.md`](route_preservation_smoke_workflow.md)

Those documents define strategy and evaluation vocabulary. This document defines
the packet that must exist before any provider/mask experiment can run.
