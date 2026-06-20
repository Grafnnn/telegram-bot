# Visual Quality Experiment Report

Use this template for controlled provider/mask experiments. Do not use it for
real customer photos or uncontrolled provider runs.

## Metadata

```text
Baseline commit:
Issue:
Experiment id:
Target: local/dev | staging-safe
Provider/model/config:
Mask strategy:
Fixture id:
Input class:
Reviewer:
Review date:
```

## Safety Confirmation

```text
Prod touched: yes/no
Staging env changed: yes/no
Real user photos used: yes/no
Provider invoked: yes/no
Network invoked: yes/no
No-mask fallback used: yes/no
Imports run: yes/no
SQL/direct DB writes: yes/no
Secrets/base64/raw bytes/raw paths exposed: yes/no
Storage/persistence used: yes/no
```

## Preservation Result

```text
Preservation report path:
Preservation pass: yes/no
mean_delta:
changed_pixel_percent:
max_delta:
Protected-region drift observed: yes/no
Identity/face drift observed: yes/no
Background drift observed: yes/no
```

If preservation fails, stop review and classify the output as `NO_GO`.

## Visual Quality Scores

Score each dimension from `1` to `5`.

| Dimension | Score | Notes |
| --- | --- | --- |
| Garment placement plausibility |  |  |
| Fabric pattern continuity |  |  |
| Fabric scale realism |  |  |
| Body/pose preservation |  |  |
| Face/hair/skin/background preservation |  |  |
| Lighting/shadow consistency |  |  |
| Garment boundary quality |  |  |
| Absence of hallucinated artifacts |  |  |
| Output resolution/format acceptability |  |  |
| Repeatability expectation |  |  |

```text
Average score:
Lowest critical score:
Any critical dimension below threshold: yes/no
```

## Reviewer Notes

```text
What improved:
What failed:
Most important artifact:
Mask quality notes:
Fabric/reference quality notes:
Cost/latency if known:
```

## Decision

Choose one:

```text
Decision: GO_FOR_MORE_TESTING | HOLD_PROVIDER_ADJUSTMENT | NO_GO
Reason:
Required follow-up:
```

This report does not approve user-facing rollout. User-facing rollout requires a
separate product and engineering approval gate.
