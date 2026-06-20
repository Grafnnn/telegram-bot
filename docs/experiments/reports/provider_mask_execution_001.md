# Provider Mask Execution 001 Result

## Status

Decision: **NO-GO for user-facing rollout**

Issue: [#56](https://github.com/Grafnnn/telegram-bot/issues/56)

Execution was approved once for the controlled `provider-mask-001` packet and
completed in a local/dev context. This report records the result without
storing provider output images, base64 payloads, raw image bytes, secrets, or
operator-local filesystem paths.

## Provider Path Tested

- Provider: OpenAI image editing provider
- Endpoint: `/v1/images/edits`
- Model: `gpt-image-1`
- Size: `1024x1536`
- Quality: `medium`
- Output format: `png`
- Expected provider calls: `2`
- Maximum allowed provider calls: `3`
- Actual provider calls: `2`
- Retry used: `no`

## Fixtures

The execution used the two planned synthetic fixtures from
[`docs/experiments/assets/provider-mask-001/`](../assets/provider-mask-001/):

1. `pm001-solid-frontal`
2. `pm001-pattern-boundary`

No real user photos, sensitive images, Telegram photos, staging photos, or
production images were used.

## Preservation Results

Thresholds:

- `max_mean_delta <= 1.0`
- `max_changed_pixel_percent <= 1.0`
- `pixel_delta_threshold = 8`

| Fixture | Provider status | Preservation | Mean delta | Changed protected pixels | Max delta |
|---|---:|---|---:|---:|---:|
| `pm001-solid-frontal` | 200 | fail | 115.8547 | 99.9975% | 255 |
| `pm001-pattern-boundary` | 200 | fail | 82.9435 | 99.9321% | 255 |

Both outputs failed the preservation gate by a very large margin. The failure
is not borderline: nearly all protected pixels changed in both controlled
synthetic samples.

## Visual Observation

The provider returned visually plausible fashion/person images, but the outputs
behaved like full-scene or full-person reconstructions rather than
preservation-safe edits of the synthetic source image outside the clothing mask.

Visual plausibility does not override preservation failure. A generated image
that changes protected regions cannot be treated as a successful
clothing-only try-on result.

## Safety Record

Confirmed:

- no production changes;
- no staging environment mutation;
- no real user photos;
- no sensitive images;
- no imports;
- no SQL or direct DB writes;
- no no-mask fallback;
- no Telegram or admin user-facing enablement;
- no secrets printed or committed;
- no base64 payloads, raw image bytes, or provider image payloads committed.

## Decision

The tested path:

```text
gpt-image-1 + /v1/images/edits + provided explicit mask
```

is **not approved** for user-facing try-on rollout.

Do not treat this provider/mask path as production-ready. Do not enable it in
Telegram or admin user-facing workflows based on this evidence.

## Next Gate

Any future work must use a new explicit gate. Reasonable next directions:

- test a different provider, model, endpoint, or configuration;
- design a stronger mask/edit strategy;
- collect more controlled synthetic evidence only after a new capped approval;
- keep runtime preservation guardrails fail-closed.

Additional provider/OpenAI calls are not authorized by this report.
