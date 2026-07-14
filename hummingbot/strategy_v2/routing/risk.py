from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Iterable, List

from hummingbot.strategy_v2.routing.config import RoutingConfig
from hummingbot.strategy_v2.routing.data_types import (
    AccountSnapshot,
    RouteTarget,
    StrategySleeve,
)


@dataclass(frozen=True)
class RiskAssessment:
    passed: bool
    blockers: List[str]
    total_equity_quote: float
    allocated_quote: float
    reserve_quote: float


class GlobalRiskGate:
    def __init__(self, config: RoutingConfig):
        self.config = config
        self.accounts = config.accounts_by_id
        self.settings = config.global_risk

    def assess(
        self,
        targets: Iterable[RouteTarget],
        snapshots: Dict[str, AccountSnapshot],
    ) -> RiskAssessment:
        targets = list(targets)
        blockers = []
        trading_ids = {
            account.id for account in self.config.accounts if account.trading_enabled
        }
        total_equity = sum(
            snapshot.equity_quote
            for account_id, snapshot in snapshots.items()
            if account_id in trading_ids
        )
        allocated = sum(target.target_capital_quote for target in targets)
        reserve = max(0.0, total_equity - allocated)
        if total_equity <= 0:
            blockers.append("global_equity_unavailable")
            return RiskAssessment(False, blockers, total_equity, allocated, reserve)

        if allocated > total_equity * self.settings.maximum_total_allocation_pct + 1e-9:
            blockers.append("global_allocation_limit")
        if reserve < total_equity * self.settings.minimum_reserve_quote_pct - 1e-9:
            blockers.append("global_reserve_limit")

        total_drawdown = sum(
            snapshot.drawdown_quote
            for account_id, snapshot in snapshots.items()
            if account_id in trading_ids
        )
        if total_drawdown > self.settings.maximum_global_drawdown_quote:
            blockers.append("global_drawdown_limit")

        by_exchange = defaultdict(float)
        by_sleeve = defaultdict(float)
        by_symbol_gross = defaultdict(float)
        by_symbol_net = defaultdict(float)
        by_account = defaultdict(float)
        for target in targets:
            account = self.accounts[target.account_id]
            by_exchange[account.exchange] += target.target_capital_quote
            by_sleeve[target.sleeve] += target.target_capital_quote
            by_symbol_gross[target.trading_pair] += target.target_capital_quote
            by_symbol_net[target.trading_pair] += _signed_capital(target)
            by_account[target.account_id] += target.target_capital_quote

        for exchange, value in by_exchange.items():
            if (
                value
                > total_equity * self.settings.maximum_exchange_allocation_pct + 1e-9
            ):
                blockers.append(f"exchange_allocation_limit:{exchange}")
        for symbol, value in by_symbol_gross.items():
            if (
                value
                > total_equity * self.settings.maximum_symbol_gross_exposure_pct + 1e-9
            ):
                blockers.append(f"symbol_gross_exposure_limit:{symbol}")
        for symbol, value in by_symbol_net.items():
            if (
                abs(value)
                > total_equity * self.settings.maximum_symbol_net_exposure_pct + 1e-9
            ):
                blockers.append(f"symbol_net_exposure_limit:{symbol}")
        for account_id, value in by_account.items():
            if (
                value
                > self.accounts[account_id].allocation.maximum_capital_quote + 1e-9
            ):
                blockers.append(f"account_allocation_limit:{account_id}")

        sleeve_limits = {
            StrategySleeve.DIRECTIONAL: self.settings.maximum_directional_sleeve_pct,
            StrategySleeve.MARKET_MAKING: self.settings.maximum_market_making_sleeve_pct,
            StrategySleeve.RELATIVE_VALUE: self.settings.maximum_relative_value_sleeve_pct,
            StrategySleeve.HEDGE: self.settings.maximum_hedge_sleeve_pct,
        }
        for sleeve, limit in sleeve_limits.items():
            if by_sleeve[sleeve] > total_equity * limit + 1e-9:
                blockers.append(f"sleeve_allocation_limit:{sleeve.value}")

        blockers = sorted(set(blockers))
        return RiskAssessment(not blockers, blockers, total_equity, allocated, reserve)


def _signed_capital(target: RouteTarget) -> float:
    side = target.position_side.upper()
    if side in {"LONG", "BUY"}:
        return target.target_capital_quote
    if side in {"SHORT", "SELL"}:
        return -target.target_capital_quote
    return 0.0
