from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List, Tuple

from hummingbot.strategy_v2.routing.compatibility import CompatibilityEngine
from hummingbot.strategy_v2.routing.config import RoutingConfig
from hummingbot.strategy_v2.routing.data_types import (
    AccountSnapshot,
    BlockedCandidate,
    CandidateEvaluation,
    LifecycleAction,
    RouteTarget,
)


class PortfolioAllocator:
    def __init__(self, config: RoutingConfig, compatibility: CompatibilityEngine):
        self.config = config
        self.compatibility = compatibility
        self.accounts = config.accounts_by_id

    def allocate(
        self,
        evaluations: Iterable[CandidateEvaluation],
        snapshots: Dict[str, AccountSnapshot],
        *,
        global_conditions: Iterable[str] = (),
    ) -> Tuple[List[RouteTarget], List[BlockedCandidate]]:
        selected: List[RouteTarget] = []
        blocked: List[BlockedCandidate] = []
        allocated_by_account = defaultdict(float)
        ranked = sorted(
            evaluations,
            key=lambda row: (row.final_score, row.strategy_id),
            reverse=True,
        )
        for row in ranked:
            if not row.eligible:
                blocked.append(
                    BlockedCandidate(
                        strategy_id=row.strategy_id,
                        trading_pair=row.trading_pair,
                        reason_codes=row.blockers or ["candidate_ineligible"],
                    )
                )
                continue
            if row.final_score < self.config.router.minimum_candidate_score:
                blocked.append(
                    BlockedCandidate(
                        strategy_id=row.strategy_id,
                        trading_pair=row.trading_pair,
                        reason_codes=["candidate_score_below_minimum"],
                    )
                )
                continue
            target, reasons = self._select_account(
                row,
                snapshots,
                selected,
                allocated_by_account,
                set(global_conditions),
            )
            if target is None:
                blocked.append(
                    BlockedCandidate(
                        strategy_id=row.strategy_id,
                        trading_pair=row.trading_pair,
                        reason_codes=reasons or ["no_account_capacity"],
                    )
                )
                continue
            selected.append(target)
            allocated_by_account[target.account_id] += target.target_capital_quote
        return selected, blocked

    def _select_account(
        self,
        row: CandidateEvaluation,
        snapshots: Dict[str, AccountSnapshot],
        selected: List[RouteTarget],
        allocated_by_account,
        global_conditions: set[str],
    ) -> tuple[RouteTarget | None, list[str]]:
        reasons = []
        candidates = []
        for account_id in row.account_ids:
            account = self.accounts[account_id]
            snapshot = snapshots[account_id]
            binding = self.config.bindings_by_id[row.strategy_id]
            instance_count = sum(
                target.account_id == account_id
                and target.strategy_id == row.strategy_id
                for target in selected
            )
            if instance_count >= binding.maximum_instances_per_account:
                reasons.append(f"strategy_instance_limit:{account_id}")
                continue
            headroom = min(
                account.allocation.maximum_capital_quote
                - allocated_by_account[account_id],
                snapshot.available_quote - account.allocation.minimum_reserve_quote,
            )
            if headroom <= 0:
                reasons.append(f"account_capacity_exhausted:{account_id}")
                continue
            conditions = set(row.conditions_met) | global_conditions
            compatibility_blockers = self.compatibility.assess(
                row.strategy_id,
                account_id,
                row.trading_pair,
                selected,
                supplied_conditions=conditions,
            )
            if compatibility_blockers:
                reasons.extend(compatibility_blockers)
                continue
            candidates.append((headroom, account_id, snapshot))
        if not candidates:
            return None, sorted(set(reasons))

        headroom, account_id, snapshot = max(
            candidates, key=lambda item: (item[0], item[1])
        )
        capital = min(row.requested_capital_quote, headroom)
        action = (
            LifecycleAction.CONTINUE
            if row.strategy_id in snapshot.active_strategy_ids
            else LifecycleAction.START
        )
        return (
            RouteTarget(
                account_id=account_id,
                sleeve=row.sleeve,
                strategy_id=row.strategy_id,
                candidate_id=row.candidate_id,
                config_hash=row.config_hash,
                trading_pair=row.trading_pair,
                target_capital_quote=capital,
                lifecycle_action=action,
                score=row.final_score,
                position_side=row.position_side,
            ),
            [],
        )
