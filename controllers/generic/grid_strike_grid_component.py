from decimal import Decimal
from typing import Dict, List, Optional, Set

from pydantic import Field

from hummingbot.client.config.config_data_types import ClientFieldData
from hummingbot.core.data_type.common import OrderType, PositionMode, TradeType
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy_v2.controllers import ControllerBase, ControllerConfigBase
from hummingbot.strategy_v2.executors.grid_executor.data_types import GridExecutorConfig
from hummingbot.strategy_v2.executors.position_executor.data_types import TrailingStop, TripleBarrierConfig
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, ExecutorAction
from hummingbot.strategy_v2.models.executors_info import ExecutorInfo


class GridStrikeConfig(ControllerConfigBase):
    """
    Configuration required to run the GridStrike strategy for one connector and trading pair.
    """
    controller_type = "generic"
    controller_name: str = "grid_strike_grid_component"
    candles_config: List[CandlesConfig] = []

    # Account configuration
    leverage: int = 75
    position_mode: PositionMode = PositionMode.HEDGE

    # Boundaries
    connector_name: str = "binance_perpetual"
    trading_pair: str = "PNUT-USDT"
    side: TradeType = TradeType.BUY
    start_price: Decimal = Field(default=Decimal("1.04"), client_data=ClientFieldData(is_updatable=True))
    end_price: Decimal = Field(default=Decimal("1.17"), client_data=ClientFieldData(is_updatable=True))
    limit_price: Decimal = Field(default=Decimal("1.016"), client_data=ClientFieldData(is_updatable=True))

    # Profiling
    total_amount_quote: Decimal = Field(default=Decimal("1000"), client_data=ClientFieldData(is_updatable=True))
    min_spread_between_orders: Optional[Decimal] = Field(default=Decimal("0.001"),
                                                         client_data=ClientFieldData(is_updatable=True))
    min_order_amount_quote: Optional[Decimal] = Field(default=Decimal("5"),
                                                      client_data=ClientFieldData(is_updatable=True))

    # Execution
    max_open_orders: int = Field(default=5, client_data=ClientFieldData(is_updatable=True))
    max_orders_per_batch: Optional[int] = Field(default=1, client_data=ClientFieldData(is_updatable=True))
    order_frequency: int = Field(default=10, client_data=ClientFieldData(is_updatable=True))
    activation_bounds: Optional[Decimal] = Field(default=None, client_data=ClientFieldData(is_updatable=True))

    # Risk Management
    triple_barrier_config: TripleBarrierConfig = TripleBarrierConfig(
        take_profit=Decimal("0.001"),
        time_limit=60 * 60 * 6,
        open_order_type=OrderType.LIMIT_MAKER,
        take_profit_order_type=OrderType.LIMIT_MAKER,
        trailing_stop=TrailingStop(activation_price=Decimal("0.03"), trailing_delta=Decimal("0.005"))
    )
    time_limit: Optional[int] = Field(default=60 * 60 * 24 * 2, client_data=ClientFieldData(is_updatable=True))

    def update_markets(self, markets: Dict[str, Set[str]]) -> Dict[str, Set[str]]:
        if self.connector_name not in markets:
            markets[self.connector_name] = set()
        markets[self.connector_name].add(self.trading_pair)
        return markets


class GridStrike(ControllerBase):
    def __init__(self, config: GridStrikeConfig, *args, **kwargs):
        super().__init__(config, *args, **kwargs)
        self.config = config
        self._last_grid_levels_update = 0
        self.trading_rules = None
        self.grid_levels = []

    def active_executors(self) -> List[ExecutorInfo]:
        return [
            executor for executor in self.executors_info
            if executor.is_active
        ]

    def determine_executor_actions(self) -> List[ExecutorAction]:
        if len(self.active_executors()) == 0:
            return [CreateExecutorAction(
                controller_id=self.config.id,
                executor_config=GridExecutorConfig(
                    timestamp=self.market_data_provider.time(),
                    connector_name=self.config.connector_name,
                    trading_pair=self.config.trading_pair,
                    start_price=self.config.start_price,
                    end_price=self.config.end_price,
                    leverage=self.config.leverage,
                    limit_price=self.config.limit_price,
                    side=self.config.side,
                    total_amount_quote=self.config.total_amount_quote,
                    min_spread_between_orders=self.config.min_spread_between_orders,
                    min_order_amount_quote=self.config.min_order_amount_quote,
                    max_open_orders=self.config.max_open_orders,
                    max_orders_per_batch=self.config.max_orders_per_batch,
                    order_frequency=self.config.order_frequency,
                    activation_bounds=self.config.activation_bounds,
                    triple_barrier_config=self.config.triple_barrier_config,
                    level_id=None))]
        return []

    async def update_processed_data(self):
        pass

    def to_format_status(self) -> List[str]:
        status = []
        for level in self.active_executors():
            status.append(f"Grid {level.id}: {level.status}")
            levels_by_state = level.custom_info['levels_by_state']
            status.append("Levels by state:")
            for state in levels_by_state:
                n_levels = len(levels_by_state[state])
                status.append(f"  - {state}: {n_levels}")
            status.append(f"Filled orders: {len(level.custom_info['filled_orders'])}")
            status.append(f"Failed orders: {len(level.custom_info['failed_orders'])}")
            status.append(f"Canceled orders: {len(level.custom_info['canceled_orders'])}")
            status.append("Metrics:")
            status.append(f"Realized buy size: {level.custom_info['realized_buy_size_quote']} | Realized sell size: {level.custom_info['realized_sell_size_quote']} | Realized imbalance: {level.custom_info['realized_imbalance_quote']}")
            status.append(f"Realized fees: {level.custom_info['realized_fees_quote']} | Realized PnL: {level.custom_info['realized_pnl_quote']} | Realized PnL pct: {level.custom_info['realized_pnl_pct']}")
            status.append(f"Position size: {level.custom_info['position_size_quote']} | Position fees: {level.custom_info['position_fees_quote']} | Position PnL: {level.custom_info['position_pnl_quote']}")

        return status
