# Crop-Only Track B Provider Failure Diagnostic Packet 010

## Status

Status: `PROVIDER_FAILURE_DIAGNOSTIC_PACKET / NOT APPROVED FOR PROVIDER EXECUTION`

This packet responds to the `crop-only-track-b-remaining-fixtures-009` HOLD
result. It does not approve another provider/OpenAI attempt, staging changes,
production changes, runtime changes, bot/admin enablement, or user-facing
rollout.

## Baseline

Baseline before this packet:

```text
main@0a4b1d9d97f19458078b98493042606a6b298b70
```

## Parent Evidence

Remaining-fixtures execution 009:

- decision: `HOLD_REMAINING_FIXTURES_REVIEW`
- provider HTTP requests: `2`
- retry count: `1`
- completed fixtures: `0`
- stop condition: `provider_call_failed:ImageGenerationProviderError`
- full-scene provider input used: `false`
- provider output binaries committed: `false`
- raw provider payloads committed: `false`

The failure happened before any preservation or visual-quality result existed.
Therefore the next step must diagnose provider/request compatibility rather
than repeating the same remaining-fixtures execution.

## Goal

Prepare a safe diagnostic gate that answers:

```text
Was remaining-fixtures 009 blocked by local request-shape/input validation,
provider transport instability, or provider rejection of the crop/mask/fabric
combination?
```

This packet is not a retry approval and not visual-quality evidence.

## Execution Approval State

Provider/OpenAI calls: `BLOCKED`

Staging/prod/env changes: `BLOCKED`

Runtime/bot/admin behavior changes: `BLOCKED`

User-facing rollout: `BLOCKED`

## Required Diagnostic Order

Before any future provider call, run only zero-call diagnostics:

1. Revalidate the packet and parent report.
2. Revalidate all selected fixture file paths exist.
3. Revalidate `crop_source`, `crop_mask`, and `fabric_reference` open as PNG
   images.
4. Revalidate `crop_mask` has an editable transparent region and protected
   opaque region.
5. Revalidate crop source and crop mask dimensions match.
6. Revalidate fabric reference dimensions/content are non-empty.
7. Build a sanitized request-shape summary without opening network connections.
8. Confirm OpenAI config readiness status-only without printing values.
9. Confirm no full-scene/person/source image is selected as provider input.

Zero-call diagnostics may write only redacted summaries. They must not write
secrets, base64 payloads, raw image bytes, provider payloads, or real user
photos.

## Future Provider Retry Shape

Any future provider retry must be a new explicit gate after the zero-call
diagnostic result is recorded.

If a future retry is approved, the safest candidate shape is:

```text
target: local/dev
fixture: pm001-pattern-boundary only
expected provider generations: 1
max provider HTTP requests: 1
retry count: 0
input scope: crop_source + crop_mask + fabric_reference only
full-scene provider input: forbidden
```

The future retry should not attempt all remaining fixtures again until one
single-fixture diagnostic retry completes and produces either a provider output
or a clearer controlled provider failure category.

## Stop Conditions

Stop immediately and record HOLD/NO-GO if any condition occurs:

- zero-call diagnostics not recorded;
- request-shape summary would include secrets or raw payloads;
- fixture asset missing or unreadable;
- crop source and crop mask dimensions mismatch;
- crop mask lacks editable transparent region;
- crop mask lacks protected opaque region;
- fabric reference missing, unreadable, or empty;
- full source/person/scene selected as provider input;
- no-mask prompt-only path selected;
- provider/model/config unknown;
- call cap would be exceeded;
- retry would be attempted without a new explicit gate;
- staging, production, real user photo, imports, SQL, or direct DB writes would
  be involved.

## Non-Approvals

This packet does not approve:

- provider/OpenAI execution;
- rerunning remaining-fixtures 009;
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

Next safe gate:

```text
Run zero-call provider failure diagnostics and commit only redacted report
fields.
```

After that, decide whether a one-fixture/no-retry provider retry packet is
worth proposing. Any provider retry requires a new fresh explicit GO.
