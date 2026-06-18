# Preservation Drift Runner

The preservation drift runner is a developer-only tool for comparing a
before/result/mask fixture set during user-photo try-on experiments. It is part
of Issue #36 preservation-quality work and is not a production rejection path.

## What It Checks

The runner uses the same mask convention as the backend user-photo edit flow:

- transparent mask pixels are editable clothing pixels;
- opaque mask pixels are protected and should remain stable;
- RGB drift is measured only in protected pixels outside the editable region.

The report includes the thresholds used, the measured drift, and a boolean
`passes` value. The process exits with `0` when `passes=true` and non-zero when
the protected-region drift exceeds the configured thresholds.

## Generate Synthetic Fixtures

The repository includes deterministic synthetic fixtures so prompt/model
experiments do not need real user photos.

```bash
python3 backend/tests/fixtures/preservation_drift/create_fixtures.py /tmp/preservation-drift-fixtures
```

This writes a `manifest.json` plus one directory per case:

- `clothing_only_pass` - only the editable clothing area changes;
- `protected_region_fail` - protected face/background pixels change;
- `empty_mask_fail` - no editable region is present, so a clothing change fails;
- `borderline_threshold_pass` - equality with the configured threshold passes.

## Run One Fixture

```bash
python3 scripts/check_preservation_drift.py \
  --base /tmp/preservation-drift-fixtures/clothing_only_pass/base.png \
  --candidate /tmp/preservation-drift-fixtures/clothing_only_pass/candidate.png \
  --mask /tmp/preservation-drift-fixtures/clothing_only_pass/mask.png \
  --pretty
```

Example output:

```json
{
  "drift": {
    "changed_pixel_count": 0,
    "changed_pixel_percent": 0.0,
    "editable_pixel_count": 525,
    "max_delta": 0,
    "mean_delta": 0.0,
    "pixel_delta_threshold": 8,
    "protected_pixel_count": 3571
  },
  "passes": true,
  "thresholds": {
    "max_changed_pixel_percent": 1.0,
    "max_mean_delta": 1.0,
    "pixel_delta_threshold": 8
  }
}
```

## Tune Thresholds

```bash
python3 scripts/check_preservation_drift.py \
  --base /path/to/base.png \
  --candidate /path/to/result.png \
  --mask /path/to/mask.png \
  --max-mean-delta 1 \
  --max-changed-pixel-percent 1 \
  --pixel-delta-threshold 8 \
  --output /tmp/preservation-report.json
```

Threshold equality passes. For example, `mean_delta == --max-mean-delta` is
accepted. Tight thresholds are useful for deterministic fixtures; real provider
outputs need separate calibration before any runtime use.

## Experiment Protocol

For prompt or model comparisons:

1. Save the original synthetic or sanitized source image as `base.png`.
2. Save the candidate generated result as `candidate.png`.
3. Save the exact edit mask as `mask.png`.
4. Run the drift runner and store the JSON report next to the experiment.
5. Compare reports across prompts/models before deciding whether another visual
   smoke is worth running.

## Safety Boundaries

This workflow must stay developer/tooling-only until a separate product decision
sets stable thresholds and rollout behavior.

- Do not use real or sensitive user photos as fixtures.
- Do not call OpenAI from this runner.
- Do not connect it to Telegram delivery.
- Do not use it as a production rejection gate yet.
- Do not write to staging/prod databases from this workflow.
- Store only synthetic or explicitly sanitized fixtures and reports.
