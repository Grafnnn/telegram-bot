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

## Run All Manifest Cases

Use the experiment runner when you want an evidence pack across every case in a
fixture manifest:

```bash
python3 scripts/run_preservation_drift_experiments.py \
  --manifest /tmp/preservation-drift-fixtures/manifest.json \
  --fixtures-root /tmp/preservation-drift-fixtures \
  --output-dir /tmp/preservation-drift-reports \
  --summary /tmp/preservation-drift-reports/summary.json \
  --markdown-summary /tmp/preservation-drift-reports/summary.md
```

The runner reads every manifest case, runs the same drift calculation as
`scripts/check_preservation_drift.py`, writes one JSON report per case into
`--output-dir`, and writes an aggregate `summary.json`.

By default, the process exits with `0` only when every case result matches its
manifest `expected_pass` value. It exits non-zero when any expected outcome does
not match the actual runner result. `--allow-unexpected` can be used during
exploration when you still want the process to exit successfully while keeping
the unexpected results in the summary.

## Summary JSON

`summary.json` is the machine-readable evidence pack for prompt/model
experiments. It includes:

- `total_cases` - number of manifest cases;
- `passed_count` - cases whose measured drift passed their thresholds;
- `failed_count` - cases whose measured drift exceeded their thresholds;
- `expected_match_count` - cases where `actual_pass` matched `expected_pass`;
- `unexpected_result_count` - cases where actual and expected did not match;
- `all_expected` - true only when every case matched expectation;
- `cases` - per-case summaries with the report path, thresholds, drift metrics,
  and optional notes.

The per-case fields to compare across experiments are:

- `expected_pass` - the manifest's intended outcome for this fixture;
- `actual_pass` - the measured runner outcome;
- `expected_matches_actual` - whether this fixture behaved as expected;
- `drift.mean_delta`;
- `drift.changed_pixel_percent`;
- `drift.max_delta`.

## Markdown Summary

If `--markdown-summary` is provided, the runner writes a concise table with:

- case;
- expected;
- actual;
- match;
- mean_delta;
- changed_pixel_percent;
- max_delta;
- notes.

Use this Markdown file for human review notes. Keep `summary.json` as the source
of truth for scripts and CI.

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
4. Create or update a manifest case with explicit thresholds and `expected_pass`.
5. Run `scripts/run_preservation_drift_experiments.py`.
6. Store `summary.json`, `summary.md`, and per-case reports next to the experiment.
7. Compare reports across prompts/models before deciding whether another visual
   smoke is worth running.

Use the collected reports as evidence before deciding whether preservation
measurement should remain a developer-only harness, become an admin/internal
review metric, become a runtime flag/rejection path, or justify another
controlled OpenAI smoke with a synthetic/safe photo and a valid mask.

## Safety Boundaries

This workflow must stay developer/tooling-only until a separate product decision
sets stable thresholds and rollout behavior.

- Do not use real or sensitive user photos as fixtures.
- Do not call OpenAI from this runner.
- Do not connect it to Telegram delivery.
- Do not use it as a production rejection gate yet.
- Do not write to staging/prod databases from this workflow.
- Do not run imports, SQL, or direct DB writes from this workflow.
- Do not include secrets, base64 images, raw image bytes, raw provider traces, or
  prompt-only/no-mask fallback behavior in reports.
- Store only synthetic or explicitly sanitized fixtures and reports.
