# Crop/Composite Offline Rehearsal 001

## Status

Status: `offline_rehearsal_passed`

This is an offline deterministic rehearsal only.
It does not call OpenAI/provider.
It does not approve user-facing rollout.
It does not approve future provider calls.

## Scope

This report validates local crop/composite mechanics for the segmentation-first strategy:

- synthetic fixture + garment mask;
- mask-derived crop bounds;
- crop-local source/mask creation;
- deterministic fake crop edit;
- composite back through the transparent clothing mask;
- protected-region preservation check.

## Pipeline

```text
synthetic source + mask -> crop source/mask -> fake crop edit -> composite -> preservation guardrail
```

## Fixtures

| Fixture | Crop bounds | Crop padding | Composite output |
| --- | --- | ---: | --- |
| `pm001-solid-frontal` | `52,58,109,163` | 8 | `docs/experiments/assets/crop-composite-001/pm001-solid-frontal/composite_output.png` |
| `pm001-pattern-boundary` | `43,59,118,125` | 8 | `docs/experiments/assets/crop-composite-001/pm001-pattern-boundary/composite_output.png` |

## Metrics

| Fixture | Preservation | Mean delta | Changed protected pixels | Max delta |
| --- | --- | ---: | ---: | ---: |
| `pm001-solid-frontal` | pass | 0.0000 | 0.0000% | 0 |
| `pm001-pattern-boundary` | pass | 0.0000 | 0.0000% | 0 |

## Decision

Decision: `READY_FOR_CAPPED_PROVIDER_PACKET_DESIGN_ONLY`

The local crop/composite mechanics are ready for review as a candidate safer architecture.
A future provider test still requires a separate capped approval gate.

## Limitations

- This does not validate a real provider.
- This does not validate real user photos.
- This does not validate visual quality of provider outputs.
- This does not change runtime behavior.
- This does not approve rollout.

## Next Gate

Design a new capped provider approval packet that tests crop-only or garment-region-only provider editing,
followed by local composite and preservation guardrail.

Packet proposal:
[`docs/experiments/crop_only_provider_execution_packet_001.md`](../crop_only_provider_execution_packet_001.md).

That packet is not execution approval. Provider/OpenAI remains NO-GO until a
separate explicit approval gate confirms target, provider/model/config, call
cap, cost/risk, artifact handling, and stop conditions.

Readiness gate:
[`docs/experiments/crop_only_provider_readiness_001.md`](../crop_only_provider_readiness_001.md).

The readiness gate freezes the crop inputs, but still does not approve
provider/OpenAI execution.
