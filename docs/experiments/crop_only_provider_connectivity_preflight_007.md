# Crop-Only Provider Connectivity Preflight 007

## Status

Status: `PREFLIGHT_PROPOSAL / NOT APPROVED FOR PROVIDER EXECUTION`

This gate follows the Track B HOLD result from
`crop-only-track-b-operator-review-006` and the observed bot user-facing failure
copy:

```text
AI-визуализация пока недоступна. Попробуйте еще раз чуть позже.
```

It does not approve provider/OpenAI execution, Track B retry, staging/prod/env
changes, runtime rollout, Telegram/admin user-facing enablement, imports, SQL,
direct DB writes, or use of real user photos.

## Baseline

```text
main@9dfed6ee88e257691e0bcc1fb76578df97cea165
```

## Parent Evidence

Track B operator review result:

- decision: `HOLD_TRACK_B_OPERATOR_REVIEW`
- stop condition: `provider_call_failed:URLError`
- provider HTTP requests: `2`
- retry count: `1`
- completed fixtures: `0`
- provider output images: none

The result is recorded in
[`docs/experiments/reports/crop_only_track_b_operator_review_006.md`](reports/crop_only_track_b_operator_review_006.md).

## Goal

Add a zero-provider-call readiness surface and bot-side failure classification so
operators can distinguish:

- OpenAI key/config missing;
- provider/transport failure;
- mask-required fail-closed behavior;
- unknown generation failure.

This is diagnostic only. It is not a generation attempt.

## Implemented Preflight Surface

Internal endpoint:

```text
GET /api/internal/ai-readiness/image-generation
```

Access boundary:

- requires `X-Bot-Token` through the existing bot-internal token dependency;
- returns sanitized readiness booleans and names only;
- performs `0` provider HTTP requests;
- does not instantiate an OpenAI request;
- does not return secrets, raw provider payloads, base64, or image bytes;
- does not write database rows or files.

Expected diagnostic fields include:

- `status`
- `openai_configured`
- `provider`
- `image_model`
- `endpoint`
- `provider_called`
- `provider_http_requests`
- `diagnostic_scope`

## Bot Failure Classification

The Telegram user-photo handler now classifies failed generation records into
redacted reasons:

- `openai_not_configured`
- `provider_unavailable`
- `mask_required`
- `unknown`

The log line records only the reason. It must not log provider payloads, image
bytes, base64, secrets, or raw user photo data.

## Stop Conditions

Stop and keep Track B retry as NO-GO if any of these occurs:

- preflight surface is missing or not protected by bot-internal token;
- preflight returns a secret, token, raw provider payload, base64, or image bytes;
- preflight attempts a provider/OpenAI call;
- preflight records nonzero provider HTTP requests;
- Track B retry is attempted without a fresh explicit GO packet;
- staging/prod/env changes or user-facing rollout are involved;
- real user photos, imports, SQL, or direct DB writes are involved.

## Non-Approvals

This gate does not approve:

- provider/OpenAI execution;
- Track B retry;
- controlled provider execution;
- staging/prod/env changes;
- runtime or bot/admin rollout;
- user-facing try-on approval;
- use of real user photos;
- imports, SQL, or direct DB writes.

## Next Gate

After this PR, the safe operational check is to call the internal readiness
endpoint in the intended target with `X-Bot-Token` and record only the sanitized
JSON fields. Any provider retry still requires a fresh explicit GO with target,
provider/model/config, call cap, output directory, artifact policy, cost/risk,
and stop conditions.
