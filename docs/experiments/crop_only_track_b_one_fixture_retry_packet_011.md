# Crop-Only Track B One-Fixture Retry Packet 011

## Status

Status: `ONE_FIXTURE_RETRY_PACKET / NOT APPROVED FOR EXECUTION`

This packet is the narrow retry design that follows zero-call provider failure
diagnostics 010. It does not approve provider/OpenAI execution, staging changes,
production changes, runtime changes, bot/admin enablement, or user-facing
rollout.

## Baseline

Baseline before this packet:

```text
main@60030731c2c23048ce50ebd80916c89f58ddfcb5
```

## Parent Evidence

Provider failure diagnostics 010:

- decision: `READY_FOR_ONE_FIXTURE_RETRY_PACKET_DESIGN`
- provider/OpenAI calls: `0`
- network calls: `0`
- failures: `[]`
- fixture paths/readability: pass
- crop source/mask dimensions: pass
- editable/protected mask regions: pass
- fabric references: pass
- request shape sanitized: pass
- full-scene provider input absent: pass

Remaining-fixtures execution 009:

- decision: `HOLD_REMAINING_FIXTURES_REVIEW`
- provider HTTP requests: `2`
- retry count: `1`
- completed fixtures: `0`
- stop condition: `provider_call_failed:ImageGenerationProviderError`

The diagnostic result supports designing a narrower one-fixture retry packet,
not immediately retrying all remaining fixtures.

## Goal

Prepare a minimal one-fixture provider retry that answers only this question
after a future explicit GO:

```text
Can pm001-pattern-boundary complete one crop-only image edit request with the
same crop_source + crop_mask + fabric_reference request shape?
```

This packet is not visual-quality approval and not rollout evidence.

## Execution Approval State

Execution approval: `NOT APPROVED`

Provider/OpenAI calls: `BLOCKED`

Staging/prod/env changes: `BLOCKED`

Runtime/bot/admin behavior changes: `BLOCKED`

User-facing rollout: `BLOCKED`

## Proposed One-Fixture Retry Shape

Experiment ID: `crop-only-track-b-one-fixture-retry-011`

Future target after explicit GO: `local/dev crop-only one-fixture retry`

Provider/model/endpoint after explicit GO:

```text
provider: OpenAI
model: gpt-image-1
endpoint: /v1/images/edits
```

Allowed provider input scope:

```text
crop_source + crop_mask + fabric_reference only
```

Forbidden provider input:

```text
full source/person/scene
```

Fixture scope after explicit GO:

```text
pm001-pattern-boundary only
```

Expected provider generations after explicit GO: `1`

Maximum provider HTTP requests after explicit GO: `1`

Retry policy after explicit GO:

```text
retry count = 0
```

Stop-on-failure policy after explicit GO:

```text
Stop immediately on provider failure, invalid output, unreconciled dimension
mismatch, preservation threshold failure, provider payload exposure risk, or
call-cap risk.
```

## Required Fixture

Use only committed synthetic fixture:

```text
pm001-pattern-boundary
```

Real user photos are forbidden.

## Required Preflight Before Any Future GO

- Fresh explicit GO recorded in Issue #66 or a follow-up issue.
- Exact target selected: local/dev.
- Output directory specified.
- Provider/model/endpoint restated immediately before execution.
- Call cap restated immediately before execution: one request.
- Retry policy restated immediately before execution: zero retries.
- Stop-on-failure policy restated immediately before execution.
- `OPENAI_API_KEY` presence confirmed without printing the value.
- Selected fixture's `crop_source`, `crop_mask`, and `fabric_reference` resolve
  to committed synthetic PNG assets.
- Full-scene provider input remains forbidden.
- No Telegram user-facing path is enabled.
- No admin public user-facing path is enabled.
- No production deploy, production env, imports, SQL, or direct DB writes.
- No secrets, base64 payloads, raw provider payloads, or raw image bytes are
  printed or committed.

## Required Artifact Plan

Future artifacts, if separately approved:

```text
/tmp/crop-only-track-b-one-fixture-retry-011/
  requests/
  provider_outputs/
  reconciled_crops/
  composites/
  preservation/
  execution_summary.json
  execution_summary.md
```

Allowed committed evidence after execution:

- redacted request/result status;
- fixture id;
- provider call count;
- retry count;
- stop condition;
- output dimensions;
- dimension reconciliation summary;
- preservation summary.

Forbidden committed evidence:

- provider output binaries unless explicitly reviewed later;
- raw provider response payloads;
- base64 image strings;
- secrets or tokens;
- real user photos;
- private storage data.

## Required Gates If Provider Output Is Produced

The completed fixture must pass:

```text
mean_delta <= 1.0
changed_pixel_percent <= 1.0
pixel_delta_threshold = 8
protected_region_drift = no
dimension_reconciliation_applied = yes
local_composite_created = yes
```

Any visual claim still requires a later operator visual review report.

## Stop Conditions

Stop immediately and record HOLD/NO-GO if any condition occurs:

- explicit GO missing;
- fixture asset missing or unreadable;
- provider/model/config unknown;
- call cap would be exceeded;
- retry would be attempted;
- full source/person/scene selected as provider input;
- mask missing, invalid, or empty;
- no-mask prompt-only path selected;
- provider output cannot be tied to fixture id;
- output dimensions unreadable;
- dimension reconciliation missing;
- local composite failed;
- preservation report missing or failing;
- secrets, base64, raw image bytes, or raw provider payloads would be exposed;
- production, public rollout, real user photo, imports, SQL, or direct DB writes
  would be involved.

## Non-Approvals

This packet does not approve:

- provider/OpenAI execution;
- staging execution;
- production rollout;
- user-facing try-on;
- Telegram/admin enablement;
- runtime route changes;
- staging/prod/env changes;
- no-mask fallback;
- use of real user photos;
- visual-quality approval;
- retry count greater than zero;
- broader fixture execution beyond `pm001-pattern-boundary`.

## Next Gate

Before any execution, request a fresh explicit GO with exact target, provider,
model, endpoint, one-request cap, zero-retry cap, output directory, artifact
policy, safety boundaries, and stop conditions.
