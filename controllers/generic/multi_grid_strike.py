from decimal import Decimal
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from hummingbot.core.data_type.common import MarketDict, OrderType, PositionMode, PriceType, TradeType
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy_v2.controllers import ControllerBase, ControllerConfigBase
from hummingbot.strategy_v2.executors.data_types import ConnectorPair
from hummingbot.strategy_v2.executors.grid_executor.data_types import GridExecutorConfig
from hummingbot.strategy_v2.executors.position_executor.data_types import TripleBarrierConfig
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, ExecutorAction, StopExecutorAction
from hummingbot.strategy_v2.models.executors_info import ExecutorInfo


class GridConfig(BaseModel):
    """Configuration for an individual grid"""
    grid_id: str
    start_price: Decimal = Field(json_schema_extra={"is_updatable": True})
    end_price: Decimal = Field(json_schema_extra={"is_updatable": True})
    limit_price: Decimal = Field(json_schema_extra={"is_updatable": True})
    side: TradeType = Field(json_schema_extra={"is_updatable": True})
    amount_quote_pct: Decimal = Field(json_schema_extra={"is_updatable": True})  # Percentage of total amount (0.0 to 1.0)
    enabled: bool = Field(default=True, json_schema_extra={"is_updatable": True})


class MultiGridStrikeConfig(ControllerConfigBase):
    """
    Configuration for MultiGridStrike strategy supporting multiple grids
    """
    controller_type: str = "generic"
    controller_name: str = "multi_grid_strike"
    candles_config: List[CandlesConfig] = []

    # Account configuration
    leverage: int = 20
    position_mode: PositionMode = PositionMode.HEDGE

    # Common configuration
    connector_name: str = "binance_perpetual"
    trading_pair: str = "WLD-USDT"

    # Total capital allocation
    total_amount_quote: Decimal = Field(default=Decimal("1000"), json_schema_extra={"is_updatable": True})

    # Grid configurations
    grids: List[GridConfig] = Field(default_factory=list, json_schema_extra={"is_updatable": True})

    # Common grid parameters
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

    def update_markets(self, markets: MarketDict) -> MarketDict:
        return markets.add_or_update(self.connector_name, self.trading_pair)


class MultiGridStrike(ControllerBase):
    def __init__(self, config: MultiGridStrikeConfig, *args, **kwargs):
        super().__init__(config, *args, **kwargs)
        self.config = config
        self._last_config_hash = self._get_config_hash()
        self._grid_executor_mapping: Dict[str, str] = {}  # grid_id -> executor_id
        self.trading_rules = None
        self.initialize_rate_sources()

    def initialize_rate_sources(self):
        self.market_data_provider.initialize_rate_sources([ConnectorPair(connector_name=self.config.connector_name,
                                                                         trading_pair=self.config.trading_pair)])

    def _get_config_hash(self) -> str:
        """Generate a hash of the current grid configurations"""
        return str(hash(tuple(
            (g.grid_id, g.start_price, g.end_price, g.limit_price, g.side, g.amount_quote_pct, g.enabled)
            for g in self.config.grids
        )))

    def _has_config_changed(self) -> bool:
        """Check if configuration has changed"""
        current_hash = self._get_config_hash()
        changed = current_hash != self._last_config_hash
        if changed:
            self._last_config_hash = current_hash
        return changed

    def active_executors(self) -> List[ExecutorInfo]:
        return [
            executor for executor in self.executors_info
            if executor.is_active
        ]

    def get_executor_by_grid_id(self, grid_id: str) -> Optional[ExecutorInfo]:
        """Get executor associated with a specific grid"""
        executor_id = self._grid_executor_mapping.get(grid_id)
        if executor_id:
            for executor in self.executors_info:
                if executor.id == executor_id:
                    return executor
        return None

    def calculate_grid_amount(self, grid: GridConfig) -> Decimal:
        """Calculate the actual amount for a grid based on its percentage allocation"""
        return self.config.total_amount_quote * grid.amount_quote_pct

    def is_inside_bounds(self, price: Decimal, grid: GridConfig) -> bool:
        """Check if price is within grid bounds"""
        return grid.start_price <= price <= grid.end_price

    def determine_executor_actions(self) -> List[ExecutorAction]:
        actions = []
        mid_price = self.market_data_provider.get_price_by_type(
            self.config.connector_name, self.config.trading_pair, PriceType.MidPrice)

        # Check for config changes
        if self._has_config_changed():
            # Handle removed or disabled grids
            current_grid_ids = {g.grid_id for g in self.config.grids if g.enabled}
            for grid_id, executor_id in list(self._grid_executor_mapping.items()):
                if grid_id not in current_grid_ids:
                    # Stop executor for removed/disabled grid
                    actions.append(StopExecutorAction(
                        controller_id=self.config.id,
                        executor_id=executor_id
                    ))
                    del self._grid_executor_mapping[grid_id]

        # Process each enabled grid
        for grid in self.config.grids:
            if not grid.enabled:
                continue

            executor = self.get_executor_by_grid_id(grid.grid_id)

            # Create new executor if none exists and price is in bounds
            if executor is None and self.is_inside_bounds(mid_price, grid):
                executor_action = CreateExecutorAction(
                    controller_id=self.config.id,
                    executor_config=GridExecutorConfig(
                        timestamp=self.market_data_provider.time(),
                        connector_name=self.config.connector_name,
                        trading_pair=self.config.trading_pair,
                        start_price=grid.start_price,
                        end_price=grid.end_price,
                        leverage=self.config.leverage,
                        limit_price=grid.limit_price,
                        side=grid.side,
                        total_amount_quote=self.calculate_grid_amount(grid),
                        min_spread_between_orders=self.config.min_spread_between_orders,
                        min_order_amount_quote=self.config.min_order_amount_quote,
                        max_open_orders=self.config.max_open_orders,
                        max_orders_per_batch=self.config.max_orders_per_batch,
                        order_frequency=self.config.order_frequency,
                        activation_bounds=self.config.activation_bounds,
                        triple_barrier_config=self.config.triple_barrier_config,
                        level_id=grid.grid_id,  # Use grid_id as level_id for identification
                        keep_position=self.config.keep_position,
                    ))
                actions.append(executor_action)
                # Note: We'll update the mapping after executor is created

            # Update executor mapping if needed
            if executor is None and len(actions) > 0:
                # This will be handled in the next cycle after executor is created
                pass

        return actions

    async def update_processed_data(self):
        # Update executor mapping for newly created executors
        for executor in self.active_executors():
            if hasattr(executor.config, 'level_id') and executor.config.level_id:
                self._grid_executor_mapping[executor.config.level_id] = executor.id

    def to_format_status(self) -> List[str]:
        status = []
        mid_price = self.market_data_provider.get_price_by_type(
            self.config.connector_name, self.config.trading_pair, PriceType.MidPrice)

        # Define standard box width for consistency
        box_width = 114

        # Top Multi-Grid Configuration box
        status.append("┌" + "─" * box_width + "┐")

        # Header
        header = f"│ Multi-Grid Configuration - {self.config.connector_name} {self.config.trading_pair}"
        header += " " * (box_width - len(header) + 1) + "│"
        status.append(header)

        # Mid price, grid count, and total amount
        active_grids = len([g for g in self.config.grids if g.enabled])
        total_grids = len(self.config.grids)
        total_amount = self.config.total_amount_quote
        info_line = f"│ Mid Price: {mid_price:.4f} │ Active Grids: {active_grids}/{total_grids} │ Total Amount: {total_amount:.2f} │"
        info_line += " " * (box_width - len(info_line) + 1) + "│"
        status.append(info_line)

        status.append("└" + "─" * box_width + "┘")

        # Display each grid configuration
        for grid in self.config.grids:
            if not grid.enabled:
                continue

            executor = self.get_executor_by_grid_id(grid.grid_id)
            in_bounds = self.is_inside_bounds(mid_price, grid)

            # Grid header
            grid_status = "ACTIVE" if executor else ("READY" if in_bounds else "OUT_OF_BOUNDS")
            status_header = f"Grid {grid.grid_id}: {grid_status}"
            status_line = f"┌ {status_header}" + "─" * (box_width - len(status_header) - 2) + "┐"
            status.append(status_line)

            # Grid configuration
            grid_amount = self.calculate_grid_amount(grid)
            pct_display = f"{grid.amount_quote_pct * 100:.1f}%"
            config_line = f"│ Start: {grid.start_price:.4f} │ End: {grid.end_price:.4f} │ Side: {grid.side} │ Limit: {grid.limit_price:.4f} │ Amount: {grid_amount:.2f} ({pct_display}) │"
            config_line += " " * (box_width - len(config_line) + 1) + "│"
            status.append(config_line)

            if executor:
                # Display executor statistics
                col_width = box_width // 3

                # Column headers
                header_line = "│ Level Distribution" + " " * (col_width - 20) + "│"
                header_line += " Order Statistics" + " " * (col_width - 18) + "│"
                header_line += " Performance Metrics" + " " * (col_width - 21) + "│"
                status.append(header_line)

                # Data columns
                level_dist_data = [
                    f"NOT_ACTIVE: {len(executor.custom_info.get('levels_by_state', {}).get('NOT_ACTIVE', []))}",
                    f"OPEN_ORDER_PLACED: {len(executor.custom_info.get('levels_by_state', {}).get('OPEN_ORDER_PLACED', []))}",
                    f"OPEN_ORDER_FILLED: {len(executor.custom_info.get('levels_by_state', {}).get('OPEN_ORDER_FILLED', []))}",
                    f"CLOSE_ORDER_PLACED: {len(executor.custom_info.get('levels_by_state', {}).get('CLOSE_ORDER_PLACED', []))}",
                    f"COMPLETE: {len(executor.custom_info.get('levels_by_state', {}).get('COMPLETE', []))}"
                ]

                order_stats_data = [
                    f"Total: {sum(len(executor.custom_info.get(k, [])) for k in ['filled_orders', 'failed_orders', 'canceled_orders'])}",
                    f"Filled: {len(executor.custom_info.get('filled_orders', []))}",
                    f"Failed: {len(executor.custom_info.get('failed_orders', []))}",
                    f"Canceled: {len(executor.custom_info.get('canceled_orders', []))}"
                ]

                perf_metrics_data = [
                    f"Buy Vol: {executor.custom_info.get('realized_buy_size_quote', 0):.4f}",
                    f"Sell Vol: {executor.custom_info.get('realized_sell_size_quote', 0):.4f}",
                    f"R. PnL: {executor.custom_info.get('realized_pnl_quote', 0):.4f}",
                    f"R. Fees: {executor.custom_info.get('realized_fees_quote', 0):.4f}",
                    f"P. PnL: {executor.custom_info.get('position_pnl_quote', 0):.4f}",
                    f"Position: {executor.custom_info.get('position_size_quote', 0):.4f}"
                ]

                # Build rows
                max_rows = max(len(level_dist_data), len(order_stats_data), len(perf_metrics_data))
                for i in range(max_rows):
                    col1 = level_dist_data[i] if i < len(level_dist_data) else ""
                    col2 = order_stats_data[i] if i < len(order_stats_data) else ""
                    col3 = perf_metrics_data[i] if i < len(perf_metrics_data) else ""

                    row = "│ " + col1
                    row += " " * (col_width - len(col1) - 2)
                    row += "│ " + col2
                    row += " " * (col_width - len(col2) - 2)
                    row += "│ " + col3
                    row += " " * (col_width - len(col3) - 2)
                    row += "│"
                    status.append(row)

                # Liquidity line
                status.append("├" + "─" * box_width + "┤")
                liquidity_line = f"│ Open Liquidity: {executor.custom_info.get('open_liquidity_placed', 0):.4f} │ Close Liquidity: {executor.custom_info.get('close_liquidity_placed', 0):.4f} │"
                liquidity_line += " " * (box_width - len(liquidity_line) + 1) + "│"
                status.append(liquidity_line)

            status.append("└" + "─" * box_width + "┘")

        return status
