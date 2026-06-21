# Segmentation-First Crop/Composite Strategy

## Status

Status: DESIGN GATE / NOT APPROVED FOR EXECUTION

This document proposes the next architecture candidate after
`provider-mask-001` failed preservation on both controlled synthetic fixtures.
This document does not authorize provider/OpenAI calls, staging/prod changes,
runtime enablement, Telegram UX changes, or user-facing rollout.

## Context

The first controlled provider/mask execution showed that the direct path:

```text
gpt-image-1 + /v1/images/edits + provided explicit mask
```

can produce visually plausible outputs while still reconstructing protected
regions outside the mask. The result is documented in
[`docs/experiments/reports/provider_mask_execution_001.md`](experiments/reports/provider_mask_execution_001.md)
and remains NO-GO for user-facing try-on rollout.

The next strategy should reduce the provider's opportunity to regenerate the
entire scene. The proposed direction is:

```text
segmentation-first -> crop/edit only garment region -> composite back -> preservation guardrail
```

## Decision Goal

Determine whether a smaller, garment-focused editing surface can produce a
useful fabric try-on while preserving the original source image outside the
clothing region.

The goal is not to prove production readiness in one step. The goal is to
define a safer architecture and the gates required before any new capped
provider experiment.

## High-Level Pipeline

1. Accept a synthetic or user-safe source image.
2. Produce or accept a clothing segmentation mask.
3. Validate the mask before any provider call.
4. Compute a padded garment crop around the editable mask.
5. Build crop-local edit inputs:
   - crop image;
   - crop-local mask;
   - selected fabric reference;
   - strict clothing-only prompt.
6. Run a capped provider edit on the crop only, after explicit approval.
7. Composite the edited crop back into the original full image using the mask.
8. Run full-image outside-mask preservation checks.
9. Mark the result successful only if preservation and visual review pass.

Provider output must never bypass the composite and preservation steps.

## Architecture Components

| Component | Responsibility | Fail-Closed Behavior |
| --- | --- | --- |
| Segmentation source | Provides the editable clothing mask. | Missing/invalid mask blocks provider call. |
| Mask validator | Checks dimensions, alpha/coverage, protected-region exclusions. | Bad coverage or unsafe mask blocks provider call. |
| Crop builder | Expands garment mask into a bounded padded crop. | Empty/out-of-bounds crop blocks provider call. |
| Crop-local edit adapter | Sends only the crop and crop-local mask to provider. | No-mask or full-image edit path is forbidden. |
| Composite service | Places accepted edited clothing crop back onto original image. | Size/mask mismatch fails before persistence. |
| Preservation guardrail | Checks original full image vs composited result outside mask. | Drift marks generation failed and hides result URL. |
| Visual review | Scores garment realism and boundary quality. | Preservation pass alone cannot approve rollout. |

## Segmentation Strategy Options

| Option | Description | Pros | Risks | Posture |
| --- | --- | --- | --- | --- |
| Operator-provided mask | Internal operator supplies a reviewed PNG mask. | Fastest safe evidence path. | Not user-facing; manual overhead. | Recommended MVP for first crop/composite experiment. |
| Deterministic synthetic masks | Test fixtures provide masks. | Excellent for CI and local rehearsals. | Does not prove real-image segmentation. | Use for tooling and rehearsals. |
| Internal segmentation provider | Backend generates garment mask. | Better future UX. | Requires separate accuracy, privacy, cost, and failure gates. | Future dedicated PR/issue. |
| User-drawn mask | User supplies mask through UX. | Gives user control. | High UX complexity and variable mask quality. | Hold until internal evidence is strong. |

The recommended next MVP is operator-provided or deterministic synthetic mask
input only. Do not add automatic segmentation provider behavior in the first
crop/composite PR.

## Crop Rules

Crop creation must be deterministic and auditable:

- crop bounds are derived only from editable mask pixels;
- crop includes configurable padding around garment edges;
- crop is clamped to source image bounds;
- crop-local mask must align exactly with crop image dimensions;
- crop must include enough garment context for folds, seams, and shadows;
- crop must not include face or large protected areas unless unavoidable and
  explicitly reviewed;
- empty masks, tiny masks, or full-image masks are rejected.

Recommended initial crop controls:

- minimum editable area percent: reuse existing mask coverage settings;
- maximum editable area percent: reuse existing mask coverage settings;
- padding: explicit pixel or percent value recorded in experiment report;
- crop minimum size: reject if too small for provider input;
- crop maximum size: reject if it effectively becomes full-image editing.

## Composite Rules

Composite must preserve the original image outside the editable clothing mask:

- provider output is never used as the final full image directly;
- only crop pixels inside the editable mask are eligible for replacement;
- alpha feathering may be explored, but must be deterministic and reported;
- composited output dimensions must match the original source image;
- full-image preservation drift is computed after compositing;
- if compositing changes protected pixels beyond thresholds, result is failed.

## Prompt / Provider Rules

The provider prompt should operate on the crop only and must still be strict:

- edit only the transparent garment mask region;
- use the selected fabric reference as the only texture source;
- preserve garment shape, seams, folds, lighting, and boundary;
- do not add people, text, logos, accessories, or scene elements;
- do not infer or regenerate face/body/background.

Even with crop inputs, prompt text is not a safety boundary. Mask validation,
compositing, and preservation checks are the safety boundary.

## Evidence Gates

### Gate 1: Offline crop/composite rehearsal

No provider calls.

Required evidence:

- synthetic source image;
- synthetic or operator-reviewed mask;
- deterministic crop metadata;
- fake crop edit;
- composited full image;
- preservation report;
- visual report focused on mask boundary and fabric placement.

### Gate 2: Route-level fake provider smoke

No real provider calls.

Required evidence:

- route/service orchestration uses crop/composite path;
- good fake crop output completes;
- protected drift fake output fails;
- size/crop mismatch fails;
- result URL absent on failed preservation;
- no full-image provider path reachable.

### Gate 3: Capped provider crop experiment

Provider calls allowed only after a new explicit approval packet.

Required evidence:

- exact target: local/dev or named staging-safe target;
- exact fixtures and masks;
- exact call cap;
- selected provider/model/config;
- crop metadata captured;
- provider output not committed;
- preservation reports;
- visual quality reports;
- no real user photos;
- no user-facing enablement.

### Gate 4: Internal review only

Only if Gate 3 produces repeatable preservation passes.

Required evidence:

- multiple fixture categories;
- manual visual review;
- failure cases documented;
- cost and latency captured;
- product decision remains separate.

## Stop Conditions

Mandatory NO-GO:

- no mask;
- invalid mask;
- mask includes face/hair/skin/hands/background beyond reviewed boundary;
- crop is empty, tiny, or effectively full-image;
- crop-local mask does not align with crop;
- provider receives the full original image instead of crop-only input;
- provider output is exposed directly as final result;
- composite dimensions differ from source dimensions;
- protected-region preservation fails after compositing;
- visual report missing;
- provider call count exceeds cap;
- real user photo used in repo/CI/public artifacts;
- secrets, base64, raw image bytes, or raw provider payloads logged or posted.

## Runtime Safety Requirements

Before any runtime implementation can be enabled:

- default behavior remains fail-closed;
- no-mask fallback remains disabled;
- existing preservation guardrail remains active;
- failed preservation output has no successful `result_image_url`;
- Telegram/admin user-facing flows do not show failed provider output;
- crop/composite path is behind explicit config or internal-only command;
- production enablement requires a separate approval gate.

## Suggested First PR Scope

The first implementation PR should stay local/test-only:

- crop bounds helper;
- crop-local mask helper;
- deterministic composite helper;
- unit tests for crop/mask/composite edge cases;
- offline fixture rehearsal;
- no provider/OpenAI calls;
- no route changes unless fake-provider smoke is included;
- no staging/prod/env changes.

Initial local/test-only helpers are expected to live under backend services and
tests without being wired into runtime routes. They should prove deterministic
geometry first: editable mask bounds, crop-local source/mask alignment,
compositing only through transparent mask pixels, and preservation pass outside
the editable clothing region.

Crop/composite offline rehearsal 001 validates the local mechanics of:

- mask-derived crop bounds;
- crop-local edit surface;
- compositing back through the mask;
- protected-region preservation check.

This does not validate any real provider.
This does not approve provider/OpenAI calls.
This does not approve rollout.

The next provider-facing test should prefer sending only the garment crop/edit
surface where possible, then compositing the result back locally, instead of
asking the provider to edit the full person/scene.

The first crop-only provider packet proposal is documented in
[`docs/experiments/crop_only_provider_execution_packet_001.md`](experiments/crop_only_provider_execution_packet_001.md).
It remains proposal-only: it does not approve provider/OpenAI calls, runtime
changes, staging/prod changes, or user-facing rollout.

## Open Questions

- Which segmentation source should be used for the first real provider crop
  experiment: operator-provided mask or deterministic synthetic mask only?
- What crop padding balances garment context with protected-region isolation?
- Should feathering be allowed, and how should it be measured?
- What is the minimum visual score required before testing more samples?
- Which provider/model should be tried next, if any, after crop/composite
  rehearsal passes?

## Decision

Recommended next architecture candidate:

```text
segmentation-first crop/composite
```

Recommended next action:

Create a local/test-only crop/composite rehearsal PR. Do not run provider calls
until that rehearsal passes and a new explicit execution packet is approved.
