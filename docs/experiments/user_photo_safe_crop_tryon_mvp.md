# Safe User-Photo Crop Try-On MVP

## Why Full-Photo Try-On Is Blocked

The previous user-photo try-on path could send a full person photo to the image provider with generated or mock masks. Real Telegram testing showed that this can alter the person, face, pose, clothing shape, or background. That behavior is not safe for user-facing rollout.

Production-like runtime must continue to fail closed for full-photo try-on unless a real clothing mask, segmentation provider, or operator-provided mask workflow is explicitly approved.

## What The Crop-Only MVP Does

The safe MVP adds a separate garment-crop input mode:

- the Telegram bot asks for a close crop of clothing only;
- the backend receives `input_mode=garment_crop`;
- the upload is stored under `/uploads/user-garment-crops/`;
- the provider receives only that garment crop plus the selected fabric reference;
- the selected fabric reference remains strict to the chosen fabric;
- no generated/mock mask is used for this path;
- the result is returned as an edited garment crop, not composited onto the original person photo.

## What It Does Not Approve

This MVP does not approve:

- full-person photo editing without a real mask;
- prompt-only full-scene editing;
- generated/mock masks in staging or production;
- face/body/background preservation claims;
- automatic production rollout of visual quality;
- use of real user photos as fixtures.

## Rollout Boundary

The crop-only path is a limited user-facing recovery route while a real segmentation or provided-mask workflow is designed. Full-photo try-on must remain blocked until that strategy is implemented and separately validated.

Provider/OpenAI tests for this path must remain mocked unless a fresh explicit execution gate approves controlled provider calls with synthetic or user-safe inputs.
