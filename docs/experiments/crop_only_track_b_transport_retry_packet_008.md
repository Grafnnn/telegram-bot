# Crop-Only Track B Transport Retry Packet 008

## Status

Status: `TRANSPORT_RETRY_PACKET / NOT APPROVED FOR EXECUTION`

This packet narrows the next possible gate after connectivity preflight 007. It
does not approve provider/OpenAI execution, staging changes, runtime changes,
bot changes, admin enablement, or user-facing rollout.

## Baseline

Baseline before this packet:

```text
main@c343ca41f410f816dcfeeedc1575748317b81ffc
```

## Parent Evidence

Track B operator-review result:

- decision: `HOLD_TRACK_B_OPERATOR_REVIEW`
- stop condition: `provider_call_failed:URLError`
- provider HTTP requests: `2`
- retry count: `1`
- completed fixtures: `0`

Connectivity preflight 007:

- internal readiness endpoint returned sanitized HTTP 200;
- `status`: `ready_for_configured_runtime`;
- `openai_configured`: true;
- `provider_called`: false;
- `provider_http_requests`: 0;
- `secret_values_returned`: false;
- `raw_provider_payloads_returned`: false.

This means the next retry should be transport-focused, small, and diagnostic.

## Goal

Prepare a minimal provider transport retry that answers only this question
after a future explicit GO:

```text
Can the provider endpoint complete one crop-only image edit request from the
same local/dev fixture path after readiness has confirmed configuration?
```

This packet is not a visual-quality gate and not rollout evidence.

## Execution Approval State

Execution approval: `NOT APPROVED`

Provider/OpenAI calls: `BLOCKED`

Staging/prod/env changes: `BLOCKED`

Runtime/bot/admin behavior changes: `BLOCKED`

User-facing rollout: `BLOCKED`

## Proposed Transport Retry Shape

Experiment ID: `crop-only-track-b-transport-retry-008`

Future target after explicit GO: `local/dev provider transport retry`

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
pm001-solid-frontal only
```

Expected provider generations after explicit GO: `1`

Maximum provider HTTP requests after explicit GO: `2`

Retry policy after explicit GO:

```text
maximum one total retry, only for transient transport/provider failure, and
only if the retry stays within the two-request cap.
```

## Required Fixture

Use only:

```text
pm001-solid-frontal
```

Real user photos are forbidden.

## Required Preflight Before Any Future GO

- Fresh explicit GO recorded in Issue #66 or a follow-up issue.
- Exact target selected: local/dev.
- Output directory specified.
- Provider/model/endpoint restated immediately before execution.
- Call cap restated immediately before execution.
- Retry policy restated immediately before execution.
- `OPENAI_API_KEY` presence confirmed without printing the value.
- `crop_source`, `crop_mask`, and `fabric_reference` resolve to committed
  synthetic PNG assets.
- Full-scene provider input remains forbidden.
- No Telegram user-facing path is enabled.
- No admin public user-facing path is enabled.
- No production deploy, production env, imports, SQL, or direct DB writes.
- No secrets, base64 payloads, raw provider payloads, or raw image bytes are
  printed or committed.

## Required Artifact Plan

Future artifacts, if separately approved:

```text
/tmp/crop-only-track-b-transport-retry-008/
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
- preservation summary if a provider output is produced.

Forbidden committed evidence:

- provider output binaries unless explicitly reviewed later;
- raw provider response payloads;
- base64 image strings;
- secrets or tokens;
- real user photos;
- private storage data.

## Required Gates If Provider Output Is Produced

If the single fixture completes, the result must still pass:

```text
mean_delta <= 1.0
changed_pixel_percent <= 1.0
pixel_delta_threshold = 8
protected_region_drift = no
dimension_reconciliation_applied = yes
local_composite_created = yes
```

Manual visual/operator review is not required for this transport packet. Any
visual-quality claim requires a later dedicated gate.

## Stop Conditions

Stop immediately and record HOLD/NO-GO if any condition occurs:

- explicit GO missing;
- fixture assets missing;
- provider/model/config unknown;
- call cap would be exceeded;
- retry would exceed cap;
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
- visual-quality approval.

## Next Gate

Before any execution, request a fresh explicit GO with exact target, provider,
model, endpoint, call cap, retry cap, output directory, artifact policy, safety
boundaries, and stop conditions.
