#!/usr/bin/env python3
"""Validate the recorded provider-mask-001 NO-GO decision."""

from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
REPORT_JSON = REPO_ROOT / "docs" / "experiments" / "reports" / "provider_mask_execution_001.json"
REPORT_MD = REPO_ROOT / "docs" / "experiments" / "reports" / "provider_mask_execution_001.md"


def validate() -> None:
    payload = json.loads(REPORT_JSON.read_text(encoding="utf-8"))
    markdown = REPORT_MD.read_text(encoding="utf-8")
    if payload.get("decision") != "NO_GO_USER_FACING_ROLLOUT":
        raise AssertionError("Provider-mask execution must remain NO-GO for user-facing rollout.")
    if payload.get("call_control", {}).get("actual_provider_calls") != 2:
        raise AssertionError("Provider-mask execution call count must remain exactly 2.")
    if payload.get("safety", {}).get("base64_or_raw_image_payloads_recorded") is not False:
        raise AssertionError("Provider-mask NO-GO report must not record raw image payloads.")
    if "is **not approved** for user-facing try-on rollout." not in markdown:
        raise AssertionError("Markdown report must explicitly reject user-facing rollout.")


def main() -> int:
    try:
        validate()
    except AssertionError as exc:
        print(f"validation failed: {exc}", file=sys.stderr)
        return 1
    print("provider-mask NO-GO decision validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
