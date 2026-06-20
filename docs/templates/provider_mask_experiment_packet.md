# Provider/Mask Experiment Packet

This packet authorizes planning only until explicitly approved for execution.
Do not call a provider unless approval is recorded in this packet.

## Metadata

```text
Experiment id:
Issue:
PR:
Baseline commit:
Operator:
Reviewers:
Created at:
Target environment: local/dev | staging-safe
```

## Scope

```text
Why this experiment is needed:
What is being tested:
What is explicitly not being tested:
Success definition:
```

## Non-Goals

- [ ] No user-facing rollout.
- [ ] No production changes.
- [ ] No real user photos.
- [ ] No provider strategy approval from one result.
- [ ] No staging mutation unless explicitly approved below.
- [ ] No prompt-only/no-mask clothing-only claim.

## Provider Configuration

```text
Provider:
Model/endpoint:
Mode: image-edit | image-to-image | fake-provider | other
Mask support: explicit | provider-native | weak/unknown | none
Expected call count:
Max allowed call count:
Network required: yes/no
Cost estimate:
Latency estimate:
Input size limits:
Output size limits:
Known provider risks:
```

## Mask Configuration

```text
Mask strategy:
Mask source:
Mask format:
Alpha channel required: yes/no
Editable region description:
Protected region description:
Mask validation method:
Known mask risks:
```

## Fixture Pack

For each fixture:

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

## Safety Checklist

- [ ] Repo clean.
- [ ] Baseline commit recorded.
- [ ] Provider/model/config named.
- [ ] Call count capped.
- [ ] Provider cost accepted.
- [ ] Network call expectation recorded.
- [ ] Target is local/dev unless staging-safe is separately approved.
- [ ] Staging/prod untouched unless explicitly approved.
- [ ] Env unchanged unless explicitly approved.
- [ ] No real user photos.
- [ ] No private storage images.
- [ ] No base64/raw image dumps.
- [ ] No secrets/tokens in logs, docs, comments, reports, or artifacts.
- [ ] Mask validated.
- [ ] Fixture metadata complete.
- [ ] Preservation command selected.
- [ ] Visual report template selected.
- [ ] Rollback/cleanup plan written.

## Commands

```bash
# Fill in exact future commands only after approval.
```

## Expected Artifacts

```text
Output directory:
Preservation report path:
Visual quality report path:
Aggregate summary path:
Manual review notes path:
Storage/persistence policy:
Log redaction policy:
```

## Stop Conditions

- [ ] Provider call attempted without approval.
- [ ] Real user photo detected.
- [ ] Staging/prod/env changed unexpectedly.
- [ ] Provider/model/config mismatch.
- [ ] Call count exceeded.
- [ ] Mask invalid or missing.
- [ ] No-mask prompt-only path used.
- [ ] Preservation failed.
- [ ] Identity/face drift detected.
- [ ] Protected-region drift detected.
- [ ] Background drift detected.
- [ ] Severe garment boundary artifact detected.
- [ ] Hallucinated body parts, objects, or text detected.
- [ ] Raw/base64 image data exposed.
- [ ] Secret/token exposed.
- [ ] Output cannot be tied to fixture id/report.

## Preservation Report Links

```text
Fixture id:
Report path:
Pass/fail:
mean_delta:
changed_pixel_percent:
max_delta:
```

## Visual Quality Report Links

```text
Fixture id:
Report path:
Average score:
Lowest critical score:
Decision:
Reviewer notes:
```

## Decision

Choose one:

```text
Decision: GO_FOR_MORE_TESTING | HOLD_PROVIDER_ADJUSTMENT | NO_GO
Reason:
Recommended next gate:
```

This decision cannot approve user-facing rollout.

## Approval

```text
Planning packet complete: yes/no
Execution approved: yes/no
Approver:
Approval timestamp:
Approval notes:
```
