from __future__ import annotations

from typing import Dict, List, Tuple

from hummingbot.strategy_v2.routing.config import (
    RoutingConfig,
    StrategyBinding,
    TradingAccountConfig,
)
from hummingbot.strategy_v2.routing.data_types import AccountSnapshot


class AccountRegistry:
    def __init__(self, config: RoutingConfig):
        self.config = config
        self.accounts = config.accounts_by_id

    def account(self, account_id: str) -> TradingAccountConfig:
        try:
            return self.accounts[account_id]
        except KeyError as exc:
            raise KeyError(f"unknown routing account: {account_id}") from exc

    def eligible_accounts(
        self,
        binding: StrategyBinding,
        trading_pair: str,
        snapshots: Dict[str, AccountSnapshot],
        *,
        now: float,
        connector: str | None = None,
    ) -> Tuple[List[str], Dict[str, List[str]]]:
        eligible = []
        blocked: Dict[str, List[str]] = {}
        for account_id in binding.account_selector.account_ids:
            account = self.accounts[account_id]
            snapshot = snapshots.get(account_id)
            reasons = self.account_blockers(
                account,
                snapshot,
                binding,
                trading_pair,
                now=now,
                connector=connector,
            )
            if reasons:
                blocked[account_id] = reasons
            else:
                eligible.append(account_id)
        return eligible, blocked

    @staticmethod
    def account_blockers(
        account: TradingAccountConfig,
        snapshot: AccountSnapshot | None,
        binding: StrategyBinding,
        trading_pair: str,
        *,
        now: float,
        connector: str | None = None,
    ) -> List[str]:
        reasons = []
        if not account.trading_enabled:
            reasons.append("account_trading_disabled")
        if connector and connector not in {account.connector, account.connector_alias}:
            reasons.append("connector_not_allowed")
        if binding.sleeve not in account.allowed_sleeves:
            reasons.append("sleeve_not_allowed")
        if (
            trading_pair not in binding.allowed_pairs
            or trading_pair not in account.allowed_pairs
        ):
            reasons.append("trading_pair_not_allowed")
        if snapshot is None:
            reasons.append("account_snapshot_missing")
            return reasons
        age = now - snapshot.observed_at
        if age < 0 or age > account.risk.market_data_stale_after_seconds:
            reasons.append("account_snapshot_stale")
        if not snapshot.worker_healthy:
            reasons.append("worker_unhealthy")
        if not snapshot.data_fresh:
            reasons.append("market_data_stale")
        if not snapshot.balances_fresh:
            reasons.append("balance_snapshot_stale")
        if not snapshot.positions_fresh:
            reasons.append("position_snapshot_stale")
        if snapshot.unreconciled_orders:
            reasons.append("orders_unreconciled")
        if not snapshot.runtime_managed:
            reasons.append("runtime_unmanaged")
        if snapshot.transfer_locked:
            reasons.append("account_transfer_locked")
        if snapshot.risk_halted:
            reasons.append("account_risk_halted")
        if snapshot.drawdown_quote > account.risk.maximum_drawdown_quote:
            reasons.append("account_drawdown_limit")
        if snapshot.open_orders > account.risk.maximum_open_orders:
            reasons.append("account_open_order_limit")
        if snapshot.gross_exposure_quote > account.risk.maximum_gross_exposure_quote:
            reasons.append("account_gross_exposure_limit")
        if snapshot.available_quote <= account.allocation.minimum_reserve_quote:
            reasons.append("account_reserve_only")
        return reasons
