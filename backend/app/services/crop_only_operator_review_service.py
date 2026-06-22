"""Deterministic crop-only operator review smoke helpers.

Track A is intentionally fake-provider only. It reads already committed
synthetic fixture manifests and returns an operator-review shaped report without
calling OpenAI, touching storage, or writing database rows.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
TRACK_A_MANIFEST_PATH = (
    REPO_ROOT / "docs" / "experiments" / "fixtures" / "crop_only_staging_operator_review_manifest_004.json"
)
VISUAL_FIXTURE_MANIFEST_PATH = (
    REPO_ROOT / "docs" / "experiments" / "fixtures" / "crop_only_visual_quality_expansion_manifest_003.json"
)
PARENT_REPORT_PATH = REPO_ROOT / "docs" / "experiments" / "reports" / "crop_only_visual_quality_expansion_003.json"
EXPECTED_FIXTURE_IDS = [
    "pm001-solid-frontal",
    "pm001-pattern-boundary",
    "pm003-large-pattern-scale",
    "pm004-edge-boundary-stress",
]


@dataclass(frozen=True)
class CropOnlyTrackASmokeReport:
    """Redacted Track A smoke report for operator review route mechanics."""

    experiment_id: str
    track_id: str
    target: str
    provider_openai_calls: int
    controlled_provider_execution: bool
    fake_provider_execution: bool
    user_facing_rollout_approved: bool
    staging_prod_env_touched: bool
    runtime_bot_admin_user_facing_enabled: bool
    imports_sql_direct_db_writes: bool
    real_user_photos_used: bool
    raw_provider_payloads_committed: bool
    fixture_count: int
    fixture_ids: list[str]
    preservation_report_shape: str
    operator_review_shape: str
    stop_conditions_enforced: bool
    decision: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "track_id": self.track_id,
            "target": self.target,
            "provider_openai_calls": self.provider_openai_calls,
            "controlled_provider_execution": self.controlled_provider_execution,
            "fake_provider_execution": self.fake_provider_execution,
            "user_facing_rollout_approved": self.user_facing_rollout_approved,
            "staging_prod_env_touched": self.staging_prod_env_touched,
            "runtime_bot_admin_user_facing_enabled": self.runtime_bot_admin_user_facing_enabled,
            "imports_sql_direct_db_writes": self.imports_sql_direct_db_writes,
            "real_user_photos_used": self.real_user_photos_used,
            "raw_provider_payloads_committed": self.raw_provider_payloads_committed,
            "fixture_count": self.fixture_count,
            "fixture_ids": self.fixture_ids,
            "preservation_report_shape": self.preservation_report_shape,
            "operator_review_shape": self.operator_review_shape,
            "stop_conditions_enforced": self.stop_conditions_enforced,
            "decision": self.decision,
        }


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path.name} must contain a JSON object.")
    return payload


def _validate_repo_relative_png(path_value: str) -> None:
    path = Path(path_value)
    if path.is_absolute() or ".." in path.parts or path.suffix.lower() != ".png":
        raise ValueError(f"Unsafe fixture PNG path: {path_value}")
    if not (REPO_ROOT / path).is_file():
        raise ValueError(f"Fixture PNG path does not exist: {path_value}")


def build_track_a_fake_provider_smoke_report() -> dict[str, Any]:
    """Build a fake-provider operator review report and fail closed on drift.

    This function validates the committed Track A manifest and synthetic fixture
    manifest. It never calls providers and never opens user-uploaded files.
    """

    manifest = _read_json(TRACK_A_MANIFEST_PATH)
    fixture_manifest = _read_json(VISUAL_FIXTURE_MANIFEST_PATH)
    parent_report = _read_json(PARENT_REPORT_PATH)

    if manifest.get("status") != "proposal_only_not_approved_for_execution":
        raise ValueError("Track A manifest must remain proposal-only before explicit execution.")
    if manifest.get("provider_openai_calls_allowed") is not False:
        raise ValueError("Track A manifest must block provider/OpenAI calls.")
    if manifest.get("user_facing_rollout_allowed") is not False:
        raise ValueError("Track A manifest must block user-facing rollout.")
    if manifest.get("fixture_ids") != EXPECTED_FIXTURE_IDS:
        raise ValueError("Track A manifest fixture ids changed unexpectedly.")
    if parent_report.get("decision") != "GO_FOR_MORE_CROP_ONLY_TESTING":
        raise ValueError("Parent report must allow only more crop-only testing.")
    if parent_report.get("user_facing_rollout_approved") is not False:
        raise ValueError("Parent report must not approve rollout.")

    tracks = {track.get("track_id"): track for track in manifest.get("tracks", []) if isinstance(track, dict)}
    track_a = tracks.get("track_a_fake_provider_staging_route_smoke")
    if not isinstance(track_a, dict):
        raise ValueError("Track A manifest entry is missing.")
    if track_a.get("provider_openai_calls") != 0:
        raise ValueError("Track A must remain zero-provider-call smoke.")
    if track_a.get("requires_provider_secrets") is not False:
        raise ValueError("Track A must not require provider secrets.")

    fixtures = fixture_manifest.get("fixtures")
    if not isinstance(fixtures, list):
        raise ValueError("Fixture manifest must contain a fixtures list.")
    fixture_ids = [fixture.get("fixture_id") for fixture in fixtures if isinstance(fixture, dict)]
    if fixture_ids != EXPECTED_FIXTURE_IDS:
        raise ValueError("Fixture manifest ids changed unexpectedly.")
    for fixture in fixtures:
        if not isinstance(fixture, dict):
            raise ValueError("Fixture entries must be JSON objects.")
        for key in ["source_image", "full_mask", "crop_source", "crop_mask", "fabric_reference"]:
            _validate_repo_relative_png(str(fixture.get(key, "")))

    return CropOnlyTrackASmokeReport(
        experiment_id="crop-only-staging-operator-review-004",
        track_id="track_a_fake_provider_staging_route_smoke",
        target="operator-only staging route mechanics / fake provider",
        provider_openai_calls=0,
        controlled_provider_execution=False,
        fake_provider_execution=True,
        user_facing_rollout_approved=False,
        staging_prod_env_touched=False,
        runtime_bot_admin_user_facing_enabled=False,
        imports_sql_direct_db_writes=False,
        real_user_photos_used=False,
        raw_provider_payloads_committed=False,
        fixture_count=len(EXPECTED_FIXTURE_IDS),
        fixture_ids=EXPECTED_FIXTURE_IDS,
        preservation_report_shape="fixture_id + pass/fail + protected drift metrics",
        operator_review_shape="fixture_id + visual score placeholders + reviewer notes",
        stop_conditions_enforced=True,
        decision="TRACK_A_FAKE_PROVIDER_ROUTE_SMOKE_READY",
    ).as_dict()
