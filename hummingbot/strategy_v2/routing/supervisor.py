from __future__ import annotations

import hashlib
import json
from typing import Dict, Iterable

from hummingbot.strategy_v2.routing.account_registry import AccountRegistry
from hummingbot.strategy_v2.routing.allocator import PortfolioAllocator
from hummingbot.strategy_v2.routing.compatibility import CompatibilityEngine
from hummingbot.strategy_v2.routing.config import RoutingConfig
from hummingbot.strategy_v2.routing.data_types import (
    AIRoutingSignal,
    AccountSnapshot,
    BlockedCandidate,
    CandidateEvaluation,
    CandidateSignal,
    MarketState,
    RoutePlan,
)
from hummingbot.strategy_v2.routing.risk import GlobalRiskGate
from hummingbot.strategy_v2.routing.release import ReleaseManifest
from hummingbot.strategy_v2.routing.scoring import DeterministicScorer


class StrategyRoutingSupervisor:
    """Builds fail-closed RoutePlans without performing runtime side effects."""

    def __init__(self, config: RoutingConfig):
        self.config = config
        self.registry = AccountRegistry(config)
        self.scorer = DeterministicScorer(config.router.score_weights, config.ai)
        self.compatibility = CompatibilityEngine(config.compatibility)
        self.allocator = PortfolioAllocator(config, self.compatibility)
        self.risk = GlobalRiskGate(config)

    def plan(
        self,
        market: MarketState,
        snapshots: Dict[str, AccountSnapshot],
        candidates: Iterable[CandidateSignal],
        *,
        now: float,
        ai_signal: AIRoutingSignal | None = None,
        release_manifest: ReleaseManifest | None = None,
    ) -> RoutePlan:
        candidates = list(candidates)
        evaluations = [
            self._evaluate_candidate(
                candidate,
                snapshots,
                now,
                ai_signal,
                release_manifest,
            )
            for candidate in candidates
        ]
        conditions = self._global_conditions(snapshots)
        targets, blocked = self.allocator.allocate(
            evaluations,
            snapshots,
            global_conditions=conditions,
        )

        hard_risk_blockers = []
        if not market.data_fresh:
            hard_risk_blockers.append("market_state_stale")
        market_age = now - market.timestamp
        if (
            market_age < 0
            or market_age > self.config.global_risk.snapshot_stale_after_seconds
        ):
            hard_risk_blockers.append("market_state_stale")
        hard_risk_blockers.extend(f"market_risk:{flag}" for flag in market.risk_flags)
        risk = self.risk.assess(targets, snapshots)
        hard_risk_blockers.extend(risk.blockers)
        hard_risk_blockers = sorted(set(hard_risk_blockers))
        if hard_risk_blockers:
            for target in targets:
                blocked.append(
                    BlockedCandidate(
                        strategy_id=target.strategy_id,
                        trading_pair=target.trading_pair,
                        reason_codes=hard_risk_blockers,
                    )
                )
            targets = []

        input_hash = _input_hash(market, snapshots, candidates, ai_signal)
        ai_applied = any(evaluation.ai_adjustment != 0 for evaluation in evaluations)
        return RoutePlan(
            decision_id=f"route-{input_hash[:20]}",
            generated_at=now,
            effective_at=now,
            expires_at=now + self.config.router.route_interval_seconds,
            environment=self.config.environment,
            allocations=targets,
            reserve_quote=(
                risk.reserve_quote
                if not hard_risk_blockers
                else risk.total_equity_quote
            ),
            blocked_candidates=_merge_blocked(blocked),
            risk_blockers=hard_risk_blockers,
            ai_applied=ai_applied,
            input_hash=input_hash,
        )

    def _evaluate_candidate(
        self,
        candidate: CandidateSignal,
        snapshots: Dict[str, AccountSnapshot],
        now: float,
        ai_signal: AIRoutingSignal | None,
        release_manifest: ReleaseManifest | None,
    ) -> CandidateEvaluation:
        binding = self.config.bindings_by_id.get(candidate.strategy_id)
        if binding is None:
            return CandidateEvaluation(
                strategy_id=candidate.strategy_id,
                candidate_id=candidate.candidate_id,
                config_hash=candidate.config_hash,
                connector=candidate.connector,
                trading_pair=candidate.trading_pair,
                sleeve="reserve",
                eligible=False,
                blockers=["strategy_binding_missing"],
                requested_capital_quote=candidate.requested_capital_quote,
                position_side=candidate.position_side,
            )

        blockers = list(candidate.hard_blockers)
        evolution = self.config.integration.evolution
        if evolution.enabled:
            if release_manifest is None:
                if evolution.fail_closed_without_manifest:
                    blockers.append("release_manifest_missing")
            else:
                blockers.extend(
                    release_manifest.authorize(
                        candidate.strategy_id,
                        candidate.candidate_id,
                        candidate.config_hash,
                        self.config.environment,
                        now=now,
                    )
                )
        if candidate.trading_pair not in binding.allowed_pairs:
            blockers.append("binding_pair_not_allowed")
        eligible_accounts, account_blockers = self.registry.eligible_accounts(
            binding,
            candidate.trading_pair,
            snapshots,
            now=now,
            connector=candidate.connector,
        )
        if not eligible_accounts:
            blockers.extend(
                f"{account_id}:{reason}"
                for account_id, reasons in account_blockers.items()
                for reason in reasons
            )

        fixed, ai_adjustment, final, _ = self.scorer.score(
            candidate.strategy_id,
            candidate.score_components,
            now=now,
            ai_signal=ai_signal,
        )
        blockers = sorted(set(blockers))
        return CandidateEvaluation(
            strategy_id=candidate.strategy_id,
            candidate_id=candidate.candidate_id,
            config_hash=candidate.config_hash,
            connector=candidate.connector,
            trading_pair=candidate.trading_pair,
            sleeve=binding.sleeve,
            eligible=not blockers,
            blockers=blockers,
            fixed_score=fixed,
            ai_adjustment=ai_adjustment,
            final_score=final,
            requested_capital_quote=candidate.requested_capital_quote,
            account_ids=eligible_accounts,
            position_side=candidate.position_side,
            conditions_met=candidate.conditions_met,
        )

    def _global_conditions(self, snapshots: Dict[str, AccountSnapshot]) -> set[str]:
        trading_ids = {
            account.id for account in self.config.accounts if account.trading_enabled
        }
        equity = sum(
            snapshot.equity_quote
            for account_id, snapshot in snapshots.items()
            if account_id in trading_ids
        )
        net = sum(
            snapshot.net_exposure_quote
            for account_id, snapshot in snapshots.items()
            if account_id in trading_ids
        )
        if (
            equity
            and abs(net)
            <= equity * self.config.global_risk.maximum_symbol_net_exposure_pct
        ):
            return {"global_net_exposure_within_limit"}
        return set()


def _input_hash(market, snapshots, candidates, ai_signal) -> str:
    payload = {
        "market": market.model_dump(mode="json"),
        "snapshots": {
            key: value.model_dump(mode="json")
            for key, value in sorted(snapshots.items())
        },
        "candidates": [
            candidate.model_dump(mode="json")
            for candidate in sorted(
                candidates, key=lambda row: (row.strategy_id, row.trading_pair)
            )
        ],
        "ai": ai_signal.model_dump(mode="json") if ai_signal else None,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _merge_blocked(rows: Iterable[BlockedCandidate]) -> list[BlockedCandidate]:
    merged = {}
    for row in rows:
        key = (row.strategy_id, row.trading_pair)
        merged.setdefault(key, set()).update(row.reason_codes)
    return [
        BlockedCandidate(
            strategy_id=key[0],
            trading_pair=key[1],
            reason_codes=sorted(reasons),
        )
        for key, reasons in sorted(merged.items())
    ]
