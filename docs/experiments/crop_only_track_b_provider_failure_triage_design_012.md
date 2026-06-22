# Crop-only Track B provider failure triage design 012

Status: `PROVIDER_FAILURE_TRIAGE_DESIGN / NOT APPROVED FOR PROVIDER EXECUTION`

Baseline: `main@805f97c2e24c542c7edd5b631a6356b7f9b7eb2a`

Parent evidence:

| Evidence | Decision | Provider HTTP requests | Retry count | Completed fixtures | Stop condition |
| --- | --- | ---: | ---: | ---: | --- |
| `crop_only_track_b_remaining_fixtures_009` | `HOLD_REMAINING_FIXTURES_REVIEW` | 2 | 1 | 0 | `provider_call_failed:ImageGenerationProviderError` |
| `crop_only_track_b_provider_failure_diagnostic_010` | `READY_FOR_ONE_FIXTURE_RETRY_PACKET_DESIGN` | 0 | 0 | 0 | zero-call diagnostics passed |
| `crop_only_track_b_one_fixture_retry_011` | `HOLD_ONE_FIXTURE_RETRY` | 1 | 0 | 0 | `provider_call_failed:ImageGenerationProviderError` |

## Decision

The current crop-only Track B request shape is blocked.

Do not spend more provider calls on the same request shape:

- model/endpoint: `gpt-image-1` through `/v1/images/edits`;
- input scope: `crop_source + crop_mask + fabric_reference only`;
- fixture focus: `pm001-pattern-boundary` and related remaining Track B fixtures;
- dimension strategy: `center_crop_to_crop_aspect_then_resize`;
- full-scene person input: not used.

The repeated provider failure is no longer best treated as a fixture-path or local validation issue. Zero-call diagnostics 010 passed, but the same request family still failed in 009 and again in 011. The next step must be a zero-call compatibility/design matrix, not another provider retry.

## Hard blocks

- Provider/OpenAI calls: `BLOCKED`
- Controlled provider execution: `BLOCKED`
- Staging/prod/env changes: `BLOCKED`
- Runtime/bot/admin behavior changes: `BLOCKED`
- User-facing rollout: `BLOCKED`
- Real user photos: `BLOCKED`
- Imports, SQL, direct DB writes: `BLOCKED`
- Raw provider payloads, base64, secrets, or local file internals in GitHub: `BLOCKED`

## Triage hypotheses

These are hypotheses only. They do not authorize provider execution.

1. API compatibility issue with multiple images plus a mask on small crop dimensions.
2. Provider mask semantics differ from local alpha-mask validation expectations.
3. Request shape or SDK serialization mismatch for `crop_source + fabric_reference + crop_mask`.
4. Prompt/config/model endpoint mismatch for using a texture reference as an edit input.
5. A transient provider problem is possible but less likely after repeated failures across 009 and 011.

## Required next gate

Create a zero-call request-shape compatibility matrix before any new provider call.

That matrix should compare candidate request shapes without network calls:

| Variant | Shape | Mask used | Crop-only semantics | Expected risk | Provider calls now |
| --- | --- | --- | --- | --- | --- |
| A | current crop source + fabric reference + crop mask | yes | strong if accepted | repeated provider failure | 0 |
| B | padded/normalized crop source and mask + fabric reference | yes | strong if accepted | may change crop boundary behavior | 0 |
| C | crop source + crop mask, fabric described in prompt only | yes | medium | weaker fabric fidelity | 0 |
| D | crop source + fabric reference without mask | no | weak | diagnostic only, not rollout-safe | 0 |
| E | alternate model/provider strategy | TBD | TBD | unknown integration work | 0 |

The matrix must record:

- sanitized request shape only;
- whether full-scene person input is absent;
- whether a mask is used;
- expected preservation risk;
- visual fidelity risk;
- future provider-call cap if the variant is later selected;
- explicit statement that selecting a variant still requires a fresh explicit GO.

## Future retry rule

A future provider retry is allowed only after a separate zero-call compatibility matrix is merged and a fresh explicit GO is posted.

If approved later, the first retry should be:

- one selected variant;
- one fixture;
- one provider HTTP request;
- zero retry;
- stop on first provider error, size mismatch, preservation threshold failure, or unsafe payload/logging concern.

This design does not approve provider/OpenAI execution.
