from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional

from pydantic import Field, model_validator

from hummingbot.strategy_v2.routing.data_types import Environment, StrictModel


class StrategyRelease(StrictModel):
    strategy_id: str
    candidate_id: str
    config_hash: str = Field(min_length=8)
    artifact_ref: str
    stage: str
    allowed_environments: List[Environment]
    generated_at: float
    expires_at: Optional[float] = None
    evidence_refs: List[str] = Field(default_factory=list)
    start_command: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def expiry_after_generation(self):
        if self.expires_at is not None and self.expires_at <= self.generated_at:
            raise ValueError("release expiry must be later than generation time")
        return self


class ReleaseManifest(StrictModel):
    version: int = Field(ge=1)
    generated_at: float
    releases: List[StrategyRelease]

    @model_validator(mode="after")
    def unique_strategy_releases(self):
        strategy_ids = [release.strategy_id for release in self.releases]
        if len(strategy_ids) != len(set(strategy_ids)):
            raise ValueError("release manifest contains duplicate strategies")
        return self

    def authorize(
        self,
        strategy_id: str,
        candidate_id: str | None,
        config_hash: str | None,
        environment: Environment,
        *,
        now: float,
    ) -> list[str]:
        release = next(
            (row for row in self.releases if row.strategy_id == strategy_id),
            None,
        )
        if release is None:
            return ["release_missing"]
        blockers = []
        if not candidate_id or release.candidate_id != candidate_id:
            blockers.append("release_candidate_mismatch")
        if not config_hash or release.config_hash != config_hash:
            blockers.append("release_config_hash_mismatch")
        if environment not in release.allowed_environments:
            blockers.append("release_environment_not_allowed")
        if release.expires_at is not None and now > release.expires_at:
            blockers.append("release_expired")
        return blockers


class RollbackRecovery(StrictModel):
    reasons: List[str] = Field(min_length=1)
    evidence_collected_at: str
    runtime_candidate_id: str


class EvolutionPaperRelease(StrictModel):
    """On-disk contract emitted by the strategy Evolution loop."""

    version: int = Field(ge=1)
    deployment_id: str
    strategy_id: str
    candidate_id: str
    previous_deployment_id: Optional[str] = None
    controller_config: str
    script_config: str
    runtime_file: Optional[str] = None
    database_file: Optional[str] = None
    config_hash: str = Field(min_length=8)
    status: str
    paper_only: bool
    staged_at: str
    start_command: List[str]
    verified_at: Optional[str] = None
    promoted_at: Optional[str] = None
    start_attempted_at: Optional[str] = None
    startup_deadline_at: Optional[str] = None
    start_returncode: Optional[int] = None
    error: Optional[str] = None
    runtime_errors: List[str] = Field(default_factory=list)
    rollback_reasons: List[str] = Field(default_factory=list)
    rollback_requested_at: Optional[str] = None
    rollback_status: Optional[str] = None
    rollback_returncode: Optional[int] = None
    rolled_back_at: Optional[str] = None
    rollback_recovered_at: Optional[str] = None
    rollback_recovery: Optional[RollbackRecovery] = None

    @model_validator(mode="after")
    def enforce_paper_release(self):
        if not self.paper_only:
            raise ValueError("Evolution release must be explicitly paper-only")
        if self.status not in {
            "staged",
            "waiting_for_credentials",
            "waiting_for_flat_runtime",
            "waiting_for_valid_flat_runtime",
            "ready",
            "ready_to_start",
            "ready_for_manual_start",
            "startup_pending_runtime_verification",
            "active_verified",
            "paper_champion",
        }:
            raise ValueError(f"Evolution release status is not routable: {self.status}")
        if not self.start_command:
            raise ValueError("Evolution release has no start command")
        _parse_iso_timestamp(self.staged_at)
        if bool(self.rollback_recovered_at) != bool(self.rollback_recovery):
            raise ValueError("rollback recovery timestamp and evidence must be paired")
        if self.rollback_recovery:
            _parse_iso_timestamp(str(self.rollback_recovered_at))
            _parse_iso_timestamp(self.rollback_recovery.evidence_collected_at)
            if self.status not in {"active_verified", "paper_champion"}:
                raise ValueError("rollback recovery requires an active release")
            if self.rollback_recovery.runtime_candidate_id != self.candidate_id:
                raise ValueError("rollback recovery candidate does not match release")
        return self

    def as_strategy_release(self) -> StrategyRelease:
        return StrategyRelease(
            strategy_id=self.strategy_id,
            candidate_id=self.candidate_id,
            config_hash=self.config_hash,
            artifact_ref=self.script_config,
            stage=self.status,
            allowed_environments=[Environment.PAPER],
            generated_at=_parse_iso_timestamp(self.staged_at),
            evidence_refs=[
                value for value in (self.controller_config, self.runtime_file) if value
            ],
            start_command=self.start_command,
        )


def load_release_manifest(path: Path) -> ReleaseManifest:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"cannot read release manifest: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid release manifest JSON: {path}") from exc
    if isinstance(payload, dict) and "releases" in payload:
        return ReleaseManifest.model_validate(payload)
    release = EvolutionPaperRelease.model_validate(payload)
    return ReleaseManifest(
        version=release.version,
        generated_at=_parse_iso_timestamp(release.staged_at),
        releases=[release.as_strategy_release()],
    )


def load_evolution_release_manifests(root: Path, pattern: str) -> ReleaseManifest:
    paths = sorted(root.glob(pattern))
    if not paths:
        raise ValueError(f"no Evolution release manifests match: {pattern}")
    releases = []
    generated_at = 0.0
    version = 1
    for path in paths:
        manifest = load_release_manifest(path)
        releases.extend(manifest.releases)
        generated_at = max(generated_at, manifest.generated_at)
        version = max(version, manifest.version)
    return ReleaseManifest(
        version=version,
        generated_at=generated_at,
        releases=releases,
    )


def validate_evolution_single_writer(root: Path, config_path: str) -> None:
    path = root / config_path
    try:
        payload: Any = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"cannot read Evolution config: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid Evolution config JSON: {path}") from exc
    enabled = payload.get("policy", {}).get("auto_start_paper_candidates")
    if enabled is not False:
        raise ValueError(
            "Evolution auto_start_paper_candidates must be false before Routing is enabled"
        )


def _parse_iso_timestamp(value: str) -> float:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError as exc:
        raise ValueError(f"invalid ISO timestamp: {value}") from exc
