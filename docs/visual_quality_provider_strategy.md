# Visual Quality And Provider Strategy Gate

This document starts the Track A workstream for user-photo try-on visual
quality and provider strategy. It is a product and engineering decision gate,
not a rollout plan.

## Current Baseline

Current baseline:

- `main@1d353f66b4bb05fcbb405706f5d0cb2d51ab6464`;
- Issue #45 completed: route-level preservation smoke gate;
- Issue #47 completed: manual recurring smoke runbook;
- Issue #49 completed: manual `workflow_dispatch` test-only smoke automation;
- PR #46 merged: safe route-level preservation smoke path;
- PR #48 merged: recurring manual runbook;
- PR #50 merged: manual GitHub Actions smoke automation.

Already completed:

- route-level preservation guardrail exists;
- route-level preservation smoke is repeatable without real OpenAI/provider
  calls;
- provider outputs that fail preservation are not treated as successful
  user-photo try-on results;
- no user-facing try-on rollout has been approved.

Current posture:

- safety infrastructure is in place;
- visual quality is not approved;
- provider strategy is not selected;
- mask strategy is not selected for user-facing use;
- controlled/internal mask UX is not implemented;
- staging/prod/OpenAI/provider behavior must remain unchanged unless a later
  execution gate explicitly approves it.

## Decision Problem

The decision question is:

> Can the system produce try-on results that are visually useful while
> preserving protected regions and avoiding unsafe drift?

This requires two independent answers:

1. Does the output pass preservation guardrails?
2. Is the garment/fabric transformation visually useful enough for the intended
   product experience?

Preservation safety is necessary, but it is not sufficient. A result can be
safe and still visually unusable. A result can look compelling and still be a
NO-GO if it changes face, body, hands, pose, background, or other protected
regions.

## Preservation Coupling

Hard rules:

- visual quality cannot be approved unless preservation passes;
- preservation pass alone is not product approval;
- good visual output with protected-region drift is NO-GO;
- safe but visually poor output is NO-GO for user-facing rollout;
- provider invocation status must be known before interpreting a result;
- no-mask or prompt-only generation is not acceptable for clothing-only
  user-photo try-on.

The preservation drift tooling and route-level smoke answer whether the system
fails closed. This document defines what evidence is needed before deciding that
a provider/mask path is worth more visual testing.

## Quality Dimensions

Review every candidate output against these dimensions.

| Dimension | What To Check | Critical Failure Examples |
| --- | --- | --- |
| Garment placement plausibility | Fabric appears on the intended garment area only. | Fabric appears on face, hands, background, or unrelated clothing. |
| Fabric pattern continuity | Pattern follows garment shape and remains coherent across seams. | Broken stripes, warped checks, random patches, pasted texture look. |
| Fabric scale realism | Pattern and texture scale are plausible for the garment and body size. | Huge fabric pattern on a small top, tiny pattern smeared into noise. |
| Body and pose preservation | Body shape, pose, silhouette, hands, and visible skin remain stable. | Changed arms, posture, body proportions, or hand placement. |
| Face, hair, skin, and background preservation | Protected non-clothing areas remain stable. | Identity drift, changed face, altered hair, new background objects. |
| Lighting and shadow consistency | New fabric respects source lighting and local shadows. | Flat pasted fabric, inconsistent highlights, missing folds/shadows. |
| Garment boundary quality | Edges near mask boundary are clean and natural. | Haloing, jagged mask edge, bleeding outside mask, abrupt cutouts. |
| Artifact absence | No hallucinated anatomy, extra garments, distorted objects, or text. | Extra limbs, new bag/object, implausible folds, visible generated text. |
| Output resolution and format | Output size/format are useful for Telegram and storage. | Wrong dimensions, unusable compression, unsupported format. |
| Latency/cost awareness | Provider path can plausibly fit product constraints. | Excessive latency/cost for routine usage. |
| Repeatability | Similar fixtures behave consistently. | One lucky pass followed by repeated failures. |

## Scoring Rubric

Use a 1-5 score for each visual dimension:

- `1`: severe failure, not useful;
- `2`: visible problem, likely unusable;
- `3`: marginal, internal-only exploration;
- `4`: good enough for controlled internal review;
- `5`: strong result for the tested fixture.

Hard gates:

- preservation guardrail must pass;
- provider invocation status must be known;
- no protected-region drift;
- no identity/face drift;
- no severe garment boundary artifacts;
- no obvious pattern scale failure;
- no prompt-only/no-mask fallback;
- no real user photos in repo, CI, or public artifacts.

Recommended rollout thresholds for future experiments:

- preservation result: pass;
- average visual score: at least `4.0`;
- no critical dimension below `4`;
- reviewer notes required for every fixture;
- at least two independent fixture categories pass before considering a new
  execution gate.

Decision labels:

- `GO_FOR_MORE_TESTING`: suitable for more controlled experiments only;
- `HOLD_PROVIDER_ADJUSTMENT`: promising but needs prompt/model/provider changes;
- `NO_GO`: unsafe, visually poor, or insufficiently evidenced.

No single sample can approve user-facing rollout.

## Provider Strategy Matrix

| Strategy | Quality Upside | Preservation Risk | Mask Support | Operational Complexity | Cost/Latency Risk | Testability | Posture |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Current configured provider path | Known integration path and existing route plumbing. | Unknown or high until repeated evidence passes. | Depends on configured provider behavior. | Low because integration exists. | Existing provider cost/latency profile. | Good with route smoke and fixture reports. | Explore only under controlled gates. |
| OpenAI image editing path with explicit mask support | Potentially strong editing quality when mask semantics are honored. | Must prove protected regions remain stable. | Strong if provider respects mask input. | Medium: prompt/model/config tuning required. | Medium/high depending on model and image size. | Good with synthetic fixtures and drift reports. | Explore with strict evidence. |
| Provider with image-to-image but weak mask support | May produce visually attractive full-scene edits. | High risk of full-scene regeneration and identity drift. | Weak or indirect. | Medium. | Variable. | Poor unless mask behavior is observable. | Hold or reject for clothing-only UX. |
| Local/offline fake provider | Deterministic, safe, ideal for route contracts. | None for external provider behavior because it is not real. | Exact synthetic mask behavior. | Low. | None. | Excellent for CI and fail-closed checks. | Keep for tests only. |
| Manual/operator-assisted workflow | Human can curate source, mask, and outputs. | Lower if review rejects bad outputs before delivery. | Strong if operator supplies valid masks. | High operational overhead. | Human time plus provider cost. | Good for internal evidence packs. | Explore for internal-only validation. |
| Future segmentation-assisted workflow | Could reduce mask burden. | Depends on segmentation accuracy; wrong masks can be unsafe. | Generated mask, potentially previewable. | High: provider, validation, UX, safety review. | Medium/high. | Requires separate fixture and mask quality gates. | Future dedicated strategy issue. |

Provider strategy is not approved by this document. The default posture remains:
controlled exploration only.

## Mask Strategy Matrix

| Strategy | Quality Upside | Drift Risk | UX Complexity | Internal Tooling Complexity | Safety Risk | Posture |
| --- | --- | --- | --- | --- | --- | --- |
| No-mask mode | Lowest friction. | Very high for clothing-only edits. | Low. | Low. | High: prompt-only full-scene drift. | Reject for user-facing try-on. |
| Provided mask mode | Strongest immediate control over editable region. | Lower if mask is valid and provider respects it. | High for users, moderate for internal operators. | Medium. | Medium: invalid masks can break quality/safety. | Explore for controlled/internal experiments. |
| Provider-native mask | Potentially best alignment with provider API. | Medium; still must be measured. | Medium. | Medium. | Medium. | Explore if provider semantics are documented and testable. |
| Generated segmentation mask | Better UX if accurate. | Medium/high until segmentation quality is proven. | Low for user, high in backend. | High. | High if mask misses clothing or includes face/body. | Future dedicated gate. |
| Internal operator mask | Good for controlled experiments and evidence packs. | Lower with trained review. | Not user-facing. | Medium. | Lower for internal only. | Recommended MVP for evidence collection. |
| User-drawn mask | Gives user control. | Variable due to user skill. | High. | High UI/validation work. | Medium/high. | Hold until internal strategy is proven. |
| Hybrid mask with preview/validation | Best long-term safety posture. | Lower if validation is strong. | Medium/high. | High. | Medium. | Future product/UX gate. |

## Experiment Fixture Pack Plan

Future experiments should use synthetic, mannequin, or otherwise sanitized
non-real-person fixtures. Do not commit real customer/user photos to the repo or
public CI artifacts.

Recommended fixture axes:

Fabric categories:

- solid color;
- small pattern;
- large pattern;
- stripe or check;
- texture-heavy fabric;
- high-contrast fabric.

Pose categories:

- frontal;
- slight turn;
- arms or hands near garment boundary;
- seated or partial body only if relevant to the product experience.

Garment categories:

- dress;
- jacket or blazer;
- shirt or top;
- skirt or trousers if relevant.

Each fixture should include:

- fixture id;
- synthetic/sanitized source image;
- valid PNG mask with alpha channel;
- fabric/reference image;
- expected editable clothing region description;
- preservation report path;
- visual quality report path;
- manual reviewer notes.

## Safe Experiment Plan

Gate sequence:

1. Local/test-only evaluation framework merged.
2. Controlled provider experiment plan approved with exact inputs and call count.
3. Limited fixture-only provider run using synthetic/sanitized images.
4. Route-level preservation result plus visual quality review.
5. Internal-only UX/mask workflow, if evidence supports it.
6. User-facing rollout only after explicit product and engineering approval.

No gate should silently imply the next gate is approved.

Before any real provider experiment, require an execution packet:

- target: local/dev or exact staging-safe target;
- baseline commit;
- provider/model/config;
- mask strategy;
- fixture list;
- exact provider call count;
- output directory;
- cost/latency capture plan if available;
- confirmation of no prod, no real user photos, no secrets, no imports, no SQL,
  no direct DB writes, no no-mask fallback, and no user-facing enablement.

## Experiment Report Template

Use [`docs/templates/visual_quality_experiment_report.md`](templates/visual_quality_experiment_report.md)
for future provider/mask experiments.

Required report fields:

- baseline commit;
- provider/mode;
- mask mode;
- fixture id;
- input class;
- output status;
- preservation result;
- visual quality scores;
- reviewer notes;
- cost/latency if known;
- provider invoked yes/no;
- network invoked yes/no;
- storage/persistence yes/no;
- final decision.

## Safety Checklist

For this workstream:

- no production changes;
- no real user photos;
- no secrets or tokens in docs, logs, reports, or artifacts;
- no raw/base64 image dumps in GitHub comments or CI logs;
- no OpenAI/provider calls without an explicit execution packet;
- no staging env mutation unless explicitly approved;
- no imports;
- no SQL or direct DB writes;
- no user-facing enablement;
- no default runtime behavior changes;
- no weakening of preservation guardrails.

## Review Posture

This document can approve an experiment design, but it cannot approve product
rollout. A provider strategy becomes a candidate only after multiple controlled
fixture runs pass preservation and visual review. A mask strategy becomes a
candidate only after it is operationally safe and reviewable.

Until then, user-photo try-on remains internal/developer-only.
