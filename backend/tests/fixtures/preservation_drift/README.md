# Preservation drift fixtures

This directory contains a deterministic synthetic fixture generator for the
local preservation drift runner. It intentionally does not store real user
photos or provider outputs.

Generate the fixture pack into a disposable local directory:

```bash
python3 backend/tests/fixtures/preservation_drift/create_fixtures.py /tmp/preservation-drift-fixtures
```

The generator writes one subdirectory per case and a `manifest.json` file. Each
case contains:

- `base.png` - synthetic source/user image
- `candidate.png` - synthetic generated/result image
- `mask.png` - transparent pixels mark the editable clothing area

The fixture set covers:

- `clothing_only_pass` - changes only the editable clothing region
- `protected_region_fail` - changes protected face/background pixels
- `empty_mask_fail` - has no editable region, so the clothing change is protected
- `borderline_threshold_pass` - documents that equality with configured
  thresholds is accepted

These fixtures are for local regression experiments only. They must not be used
as production acceptance criteria without a separate threshold decision.
