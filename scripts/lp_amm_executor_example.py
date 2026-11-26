import os
from decimal import Decimal
from typing import List, Optional

from pydantic import Field

from hummingbot.core.data_type.common import MarketDict
from hummingbot.strategy.strategy_v2_base import StrategyV2Base, StrategyV2ConfigBase
from hummingbot.strategy_v2.executors.lp_amm_executor.data_types import LPAmmExecutorConfig
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, ExecutorAction


class LPAmmExecutorExampleConfig(StrategyV2ConfigBase):
    """
    Minimal runner for LPAmmExecutor: opens one full-range AMM position and lets the
    executor's own exit triggers (min_fee_apr_pct / max_duration_seconds) close it.
    For production use, see the controllers/generic/lp_amm_rebalancer controller,
    which manages a reopening sequence of these executors. This script is the
    single-executor smoke test: the smallest way to exercise LPAmmExecutor end-to-end
    against a real Gateway connector and pool.
    """
    script_file_name: str = Field(default_factory=lambda: os.path.basename(__file__))

    connector_name: str = Field(
        default="solana-mainnet-beta",
        json_schema_extra={"prompt": "Network connector (e.g. solana-mainnet-beta)", "prompt_on_new": True},
    )
    lp_provider: str = Field(
        default="meteora/amm",
        json_schema_extra={"prompt": "LP provider as dex/trading_type (e.g. meteora/amm)", "prompt_on_new": True},
    )
    swap_provider: Optional[str] = Field(
        default=None,
        json_schema_extra={
            "prompt": "Swap provider for the close-out swap, dex/trading_type (blank = network default)",
            "prompt_on_new": True,
        },
    )
    trading_pair: str = Field(
        default="SOL-USDC",
        json_schema_extra={"prompt": "Trading pair (e.g. SOL-USDC)", "prompt_on_new": True},
    )
    pool_address: str = Field(
        default="",
        json_schema_extra={"prompt": "Pool address to deposit into", "prompt_on_new": True},
    )
    base_amount: Decimal = Field(
        default=Decimal("0"),
        json_schema_extra={"prompt": "Base token amount to deposit", "prompt_on_new": True},
    )
    quote_amount: Decimal = Field(
        default=Decimal("0"),
        json_schema_extra={"prompt": "Quote token amount to deposit", "prompt_on_new": True},
    )
    min_fee_apr_pct: Optional[Decimal] = Field(
        default=None,
        json_schema_extra={"prompt": "Close once realized fee APR falls below this % (blank = disabled)", "prompt_on_new": True},
    )
    min_fee_apr_window_seconds: float = Field(
        default=3600.0,
        json_schema_extra={"prompt": "Seconds the position must be open before min_fee_apr_pct applies", "prompt_on_new": True},
    )
    max_duration_seconds: Optional[float] = Field(
        default=None,
        json_schema_extra={"prompt": "Close after this many seconds regardless of fee APR (blank = disabled)", "prompt_on_new": True},
    )
    keep_position: bool = Field(
        default=False,
        json_schema_extra={"prompt": "Keep the net token change as a held position on exit instead of swapping back", "prompt_on_new": True},
    )
    slippage_pct: Decimal = Field(
        default=Decimal("0.05"),
        json_schema_extra={"prompt": "Starting slippage tolerance %", "prompt_on_new": True},
    )

    def update_markets(self, markets: MarketDict) -> MarketDict:
        markets[self.connector_name] = markets.get(self.connector_name, set()) | {self.trading_pair}
        return markets


class LPAmmExecutorExample(StrategyV2Base):
    """
    Creates a single LPAmmExecutor from the config above and logs its outcome once it
    finishes. See LPAmmExecutorExampleConfig's docstring for why this script exists.
    """

    def __init__(self, connectors, config: LPAmmExecutorExampleConfig):
        super().__init__(connectors, config)
        self.config = config
        self._executor_created = False
        self._report_logged = False

    def on_tick(self):
        """StrategyV2Base.on_tick only runs the control loop when self.controllers is
        non-empty - this example registers no controller, so the inherited tick would
        never call create_actions_proposal. Re-run the same control loop here without
        the controller-only steps (update_controllers_configs, per-controller report
        push), which executor orchestration itself doesn't require.
        """
        self.update_executors_info()
        if self.market_data_provider.ready and not self._is_stop_triggered:
            executor_actions: List[ExecutorAction] = self.determine_executor_actions()
            for action in executor_actions:
                self.executor_orchestrator.execute_action(action)

    def create_actions_proposal(self) -> List[CreateExecutorAction]:
        if self._executor_created:
            return []
        self._executor_created = True
        executor_config = LPAmmExecutorConfig(
            timestamp=self.current_timestamp,
            connector_name=self.config.connector_name,
            lp_provider=self.config.lp_provider,
            swap_provider=self.config.swap_provider,
            trading_pair=self.config.trading_pair,
            pool_address=self.config.pool_address,
            base_amount=self.config.base_amount,
            quote_amount=self.config.quote_amount,
            min_fee_apr_pct=self.config.min_fee_apr_pct,
            min_fee_apr_window_seconds=self.config.min_fee_apr_window_seconds,
            max_duration_seconds=self.config.max_duration_seconds,
            keep_position=self.config.keep_position,
            slippage_pct=self.config.slippage_pct,
        )
        self.logger().info(f"Creating LPAmmExecutor with config: {executor_config}")
        return [CreateExecutorAction(executor_config=executor_config)]

    def stop_actions_proposal(self) -> List:
        if self._executor_created and not self._report_logged:
            executors = self.get_all_executors()
            done = self.filter_executors(executors=executors, filter_func=lambda e: not e.is_active)
            if done:
                executor = done[0]
                self.logger().info(
                    f"LPAmmExecutor finished: {executor.id} | status: {executor.status} | "
                    f"close type: {executor.close_type} | net pnl (quote): {executor.net_pnl_quote} | "
                    f"filled amount (quote): {executor.filled_amount_quote}"
                )
                self._report_logged = True
        return []

    def format_status(self) -> str:
        """StrategyV2Base.format_status only prints executor tables inside its
        "if self.controllers" branch - this script registers no controller, so the
        inherited status would never show the one executor it runs. Append a line for
        it here instead.
        """
        base_status = super().format_status()
        if self.controllers or not self.ready_to_trade:
            return base_status
        executors = self.get_all_executors()
        if not executors:
            return base_status
        executor = max(executors, key=lambda e: e.timestamp)
        info = executor.custom_info
        lines = [
            base_status,
            "",
            "  LPAmmExecutor:",
            f"    id: {executor.id} | status: {executor.status.name} | state: {info.get('state')} | "
            f"pool: {info.get('pool_address')} | base amount: {info.get('base_amount')} | "
            f"quote amount: {info.get('quote_amount')} | fees earned (quote): {info.get('fees_earned_quote')} | "
            f"fee APR %: {info.get('fee_apr_pct')}",
        ]
        return "\n".join(lines)
