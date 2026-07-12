from abc import ABC, abstractmethod
from typing import Dict

from hummingbot.strategy_v2.routers.promotion import (
    AdapterExecutionMode,
    PromotionAssessment,
    PromotionEngine,
    PromotionEvidence,
    StrategyAdapterSpec,
)


class StrategyAdapter(ABC):
    """Describes how one strategy enters the shared validation and release pipeline."""

    @property
    @abstractmethod
    def spec(self) -> StrategyAdapterSpec:
        raise NotImplementedError

    def assess(self, evidence: PromotionEvidence) -> PromotionAssessment:
        return PromotionEngine.assess(self.spec, evidence)


class SuperTrendAdapter(StrategyAdapter):
    @property
    def spec(self) -> StrategyAdapterSpec:
        return StrategyAdapterSpec(
            name="supertrend_adapter",
            candidate_name="supertrend_v1",
            target="controllers.directional_trading.supertrend_v1",
            execution_mode=AdapterExecutionMode.CONTROLLER_PROFILE,
            required_features=["supertrend_direction", "atr", "trend_strength"],
            risk_controls=["allow_short_gate", "stop_loss", "take_profit", "time_limit", "protect_stop"],
            intended_regimes=["trend_up", "trend_down", "breakout_up", "breakout_down"],
            minimum_paper_hours=24,
        )


class PMMMisterAdapter(StrategyAdapter):
    @property
    def spec(self) -> StrategyAdapterSpec:
        return StrategyAdapterSpec(
            name="pmm_mister_adapter",
            candidate_name="pmm_mister",
            target="controllers.generic.pmm_mister",
            execution_mode=AdapterExecutionMode.CONTROLLER_PROFILE,
            required_features=["mid_price", "spread", "inventory_pct", "realized_volatility"],
            risk_controls=[
                "maker_only",
                "portfolio_allocation_cap",
                "max_active_executors_by_level",
                "global_stop_loss",
                "protect_stop",
            ],
            intended_regimes=["range_low_vol", "range_high_vol"],
            minimum_paper_hours=72,
        )


class FundingRateArbitrageAdapter(StrategyAdapter):
    @property
    def spec(self) -> StrategyAdapterSpec:
        return StrategyAdapterSpec(
            name="funding_rate_arb_adapter",
            candidate_name="funding_rate_arb",
            target="scripts.v2_funding_rate_arb",
            execution_mode=AdapterExecutionMode.STRATEGY_SCRIPT,
            required_features=[
                "normalized_funding_rate",
                "executable_basis",
                "entry_fees",
                "exit_cost_buffer",
            ],
            risk_controls=[
                "two_leg_balance",
                "single_leg_timeout",
                "max_entry_basis_loss",
                "funding_stop_loss",
                "protect_unwind",
            ],
            intended_regimes=["arbitrage"],
            minimum_paper_hours=72,
        )


def default_adapter_registry() -> Dict[str, StrategyAdapter]:
    adapters = [SuperTrendAdapter(), PMMMisterAdapter(), FundingRateArbitrageAdapter()]
    return {adapter.spec.candidate_name: adapter for adapter in adapters}
