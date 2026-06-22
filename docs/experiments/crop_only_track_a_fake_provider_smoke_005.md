# Crop-Only Track A Fake-Provider Smoke 005

## Status

Status: `IMPLEMENTATION_GATE / NOT EXECUTED`

This document records the implementation gate for Track A from
`crop-only-staging-operator-review-004`.

It does not approve execution, staging env changes, provider/OpenAI calls,
controlled-provider review, or user-facing rollout.

## Baseline

Baseline before this implementation gate:

```text
main@0b2173d416c3c59677a93b49cd567f29b314bd35
```

## Implemented Surface

Internal endpoint:

```text
POST /api/internal/crop-only/operator-review/track-a-smoke
```

Access boundary:

- requires `X-Bot-Token` via existing bot-internal token dependency;
- disabled by default behind `CROP_ONLY_OPERATOR_REVIEW_TRACK_A_ENABLED=false`;
- returns `403` when the feature flag is off;
- returns `401` without the bot-internal token;
- does not call OpenAI/provider;
- does not write database rows;
- does not persist files;
- does not expose user-facing Telegram/admin behavior.

## Track A Scope

Track A remains fake-provider only:

```text
provider/OpenAI calls = 0
controlled provider execution = false
real user photos = forbidden
```

The endpoint validates the committed Track A manifest, parent visual-quality
report, and the four concrete synthetic fixtures from
`crop-only-visual-quality-expansion-003`.

## Required Synthetic Fixtures

- `pm001-solid-frontal`
- `pm001-pattern-boundary`
- `pm003-large-pattern-scale`
- `pm004-edge-boundary-stress`

## Expected Report Shape

The response is a redacted operator-review smoke report containing:

- experiment id;
- track id;
- target;
- provider/OpenAI call count;
- controlled-provider execution flag;
- fake-provider execution flag;
- rollout/env/runtime/DB/user-photo safety flags;
- fixture count and fixture ids;
- preservation report shape;
- operator review shape;
- stop-condition status;
- decision.

## Non-Approvals

This implementation does not approve:

- Track A execution;
- Track B execution;
- OpenAI/provider calls;
- staging/prod/env changes;
- runtime rollout;
- Telegram/admin user-facing enablement;
- use of real user photos;
- imports, SQL, or direct DB writes.

## Next Gate

Before running this endpoint outside tests, record a fresh explicit Track A GO
with target, environment, output/report handling, and stop conditions.
