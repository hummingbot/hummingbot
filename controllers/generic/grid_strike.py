from decimal import Decimal
from typing import Dict, List, Optional, Set

from pydantic import Field

from hummingbot.core.data_type.common import OrderType, PositionMode, PriceType, TradeType
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy_v2.controllers import ControllerBase, ControllerConfigBase
from hummingbot.strategy_v2.executors.data_types import ConnectorPair
from hummingbot.strategy_v2.executors.grid_executor.data_types import GridExecutorConfig
from hummingbot.strategy_v2.executors.position_executor.data_types import TripleBarrierConfig
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, ExecutorAction
from hummingbot.strategy_v2.models.executors_info import ExecutorInfo


class GridStrikeConfig(ControllerConfigBase):
    """
    Configuration required to run the GridStrike strategy for one connector and trading pair.
    """
    controller_type: str = "generic"
    controller_name: str = "grid_strike"
    candles_config: List[CandlesConfig] = []

    # Account configuration
    leverage: int = 20
    position_mode: PositionMode = PositionMode.HEDGE

    # Boundaries
    connector_name: str = "binance_perpetual"
    trading_pair: str = "WLD-USDT"
    side: TradeType = TradeType.BUY
    start_price: Decimal = Field(default=Decimal("0.58"), json_schema_extra={"is_updatable": True})
    end_price: Decimal = Field(default=Decimal("0.95"), json_schema_extra={"is_updatable": True})
    limit_price: Decimal = Field(default=Decimal("0.55"), json_schema_extra={"is_updatable": True})

    # Profiling
    total_amount_quote: Decimal = Field(default=Decimal("1000"), json_schema_extra={"is_updatable": True})
    min_spread_between_orders: Optional[Decimal] = Field(default=Decimal("0.001"), json_schema_extra={"is_updatable": True})
    min_order_amount_quote: Optional[Decimal] = Field(default=Decimal("5"), json_schema_extra={"is_updatable": True})

    # Execution
    max_open_orders: int = Field(default=2, json_schema_extra={"is_updatable": True})
    max_orders_per_batch: Optional[int] = Field(default=1, json_schema_extra={"is_updatable": True})
    order_frequency: int = Field(default=3, json_schema_extra={"is_updatable": True})
    activation_bounds: Optional[Decimal] = Field(default=None, json_schema_extra={"is_updatable": True})
    keep_position: bool = Field(default=False, json_schema_extra={"is_updatable": True})

    # Risk Management
    triple_barrier_config: TripleBarrierConfig = TripleBarrierConfig(
        take_profit=Decimal("0.001"),
        open_order_type=OrderType.LIMIT_MAKER,
        take_profit_order_type=OrderType.LIMIT_MAKER,
    )

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
        self.initialize_rate_sources()

    def initialize_rate_sources(self):
        self.market_data_provider.initialize_rate_sources([ConnectorPair(connector_name=self.config.connector_name,
                                                                         trading_pair=self.config.trading_pair)])

    def active_executors(self) -> List[ExecutorInfo]:
        return [
            executor for executor in self.executors_info
            if executor.is_active
        ]

    def is_inside_bounds(self, price: Decimal) -> bool:
        return self.config.start_price <= price <= self.config.end_price

    def determine_executor_actions(self) -> List[ExecutorAction]:
        mid_price = self.market_data_provider.get_price_by_type(
            self.config.connector_name, self.config.trading_pair, PriceType.MidPrice)
        if len(self.active_executors()) == 0 and self.is_inside_bounds(mid_price):
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
                    level_id=None,
                    keep_position=self.config.keep_position,
                ))]
        return []

    async def update_processed_data(self):
        pass

    def to_format_status(self) -> List[str]:
        status = []
        mid_price = self.market_data_provider.get_price_by_type(
            self.config.connector_name, self.config.trading_pair, PriceType.MidPrice)
        # Define standard box width for consistency
        box_width = 114
        # Top Grid Configuration box with simple borders
        status.append("┌" + "─" * box_width + "┐")
        # First line: Grid Configuration and Mid Price
        left_section = "Grid Configuration:"
        padding = box_width - len(left_section) - 4  # -4 for the border characters and spacing
        config_line1 = f"│ {left_section}{' ' * padding}"
        padding2 = box_width - len(config_line1) + 1  # +1 for correct right border alignment
        config_line1 += " " * padding2 + "│"
        status.append(config_line1)
        # Second line: Configuration parameters
        config_line2 = f"│ Start: {self.config.start_price:.4f} │ End: {self.config.end_price:.4f} │ Side: {self.config.side} │ Limit: {self.config.limit_price:.4f} │ Mid Price: {mid_price:.4f} │"
        padding = box_width - len(config_line2) + 1  # +1 for correct right border alignment
        config_line2 += " " * padding + "│"
        status.append(config_line2)
        # Third line: Max orders and Inside bounds
        config_line3 = f"│ Max Orders: {self.config.max_open_orders}   │ Inside bounds: {1 if self.is_inside_bounds(mid_price) else 0}"
        padding = box_width - len(config_line3) + 1  # +1 for correct right border alignment
        config_line3 += " " * padding + "│"
        status.append(config_line3)
        status.append("└" + "─" * box_width + "┘")
        for level in self.active_executors():
            # Define column widths for perfect alignment
            col_width = box_width // 3  # Dividing the total width by 3 for equal columns
            total_width = box_width
            # Grid Status header - use long line and running status
            status_header = f"Grid Status: {level.id} (RunnableStatus.RUNNING)"
            status_line = f"┌ {status_header}" + "─" * (total_width - len(status_header) - 2) + "┐"
            status.append(status_line)
            # Calculate exact column widths for perfect alignment
            col1_end = col_width
            # Column headers
            header_line = "│ Level Distribution" + " " * (col1_end - 20) + "│"
            header_line += " Order Statistics" + " " * (col_width - 18) + "│"
            header_line += " Performance Metrics" + " " * (col_width - 21) + "│"
            status.append(header_line)
            # Data for the three columns
            level_dist_data = [
                f"NOT_ACTIVE: {len(level.custom_info['levels_by_state'].get('NOT_ACTIVE', []))}",
                f"OPEN_ORDER_PLACED: {len(level.custom_info['levels_by_state'].get('OPEN_ORDER_PLACED', []))}",
                f"OPEN_ORDER_FILLED: {len(level.custom_info['levels_by_state'].get('OPEN_ORDER_FILLED', []))}",
                f"CLOSE_ORDER_PLACED: {len(level.custom_info['levels_by_state'].get('CLOSE_ORDER_PLACED', []))}",
                f"COMPLETE: {len(level.custom_info['levels_by_state'].get('COMPLETE', []))}"
            ]
            order_stats_data = [
                f"Total: {sum(len(level.custom_info[k]) for k in ['filled_orders', 'failed_orders', 'canceled_orders'])}",
                f"Filled: {len(level.custom_info['filled_orders'])}",
                f"Failed: {len(level.custom_info['failed_orders'])}",
                f"Canceled: {len(level.custom_info['canceled_orders'])}"
            ]
            perf_metrics_data = [
                f"Buy Vol: {level.custom_info['realized_buy_size_quote']:.4f}",
                f"Sell Vol: {level.custom_info['realized_sell_size_quote']:.4f}",
                f"R. PnL: {level.custom_info['realized_pnl_quote']:.4f}",
                f"R. Fees: {level.custom_info['realized_fees_quote']:.4f}",
                f"P. PnL: {level.custom_info['position_pnl_quote']:.4f}",
                f"Position: {level.custom_info['position_size_quote']:.4f}"
            ]
            # Build rows with perfect alignment
            max_rows = max(len(level_dist_data), len(order_stats_data), len(perf_metrics_data))
            for i in range(max_rows):
                col1 = level_dist_data[i] if i < len(level_dist_data) else ""
                col2 = order_stats_data[i] if i < len(order_stats_data) else ""
                col3 = perf_metrics_data[i] if i < len(perf_metrics_data) else ""
                row = "│ " + col1
                row += " " * (col1_end - len(col1) - 2)  # -2 for the "│ " at the start
                row += "│ " + col2
                row += " " * (col_width - len(col2) - 2)  # -2 for the "│ " before col2
                row += "│ " + col3
                row += " " * (col_width - len(col3) - 2)  # -2 for the "│ " before col3
                row += "│"
                status.append(row)
            # Liquidity line with perfect alignment
            status.append("├" + "─" * total_width + "┤")
            liquidity_line = f"│ Open Liquidity: {level.custom_info['open_liquidity_placed']:.4f} │ Close Liquidity: {level.custom_info['close_liquidity_placed']:.4f} │"
            liquidity_line += " " * (total_width - len(liquidity_line) + 1)  # +1 for correct right border alignment
            liquidity_line += "│"
            status.append(liquidity_line)
            status.append("└" + "─" * total_width + "┘")
        return status
