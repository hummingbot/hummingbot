from decimal import Decimal
from typing import Dict, List, Set, Union

from pydantic import Field, validator

from hummingbot.client.config.config_data_types import ClientFieldData
from hummingbot.core.data_type.common import OrderType, PositionMode, PriceType, TradeType
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy_v2.controllers import ControllerBase, ControllerConfigBase
from hummingbot.strategy_v2.executors.data_types import ConnectorPair
from hummingbot.strategy_v2.executors.grid_executor.data_types import GridExecutorConfig
from hummingbot.strategy_v2.executors.position_executor.data_types import TripleBarrierConfig
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, StopExecutorAction
from hummingbot.strategy_v2.models.executors_info import ExecutorInfo


class QGAConfig(ControllerConfigBase):
    controller_name: str = "quantum_grid_allocator"
    candles_config: List[CandlesConfig] = []

    # Portfolio allocation zones
    long_only_threshold: Decimal = Field(default=Decimal("0.2"), client_data=ClientFieldData(is_updatable=True))
    short_only_threshold: Decimal = Field(default=Decimal("0.2"), client_data=ClientFieldData(is_updatable=True))
    hedge_ratio: Decimal = Field(default=Decimal("2"), client_data=ClientFieldData(is_updatable=True))

    # Grid allocation multipliers
    base_grid_value_pct: Decimal = Field(default=Decimal("0.08"), client_data=ClientFieldData(is_updatable=True))
    max_grid_value_pct: Decimal = Field(default=Decimal("0.15"), client_data=ClientFieldData(is_updatable=True))

    # Order frequency settings
    safe_extra_spread: Decimal = Field(default=Decimal("0.0001"), client_data=ClientFieldData(is_updatable=True))
    favorable_order_frequency: int = Field(default=2, client_data=ClientFieldData(is_updatable=True))
    unfavorable_order_frequency: int = Field(default=5, client_data=ClientFieldData(is_updatable=True))
    max_orders_per_batch: int = Field(default=1, client_data=ClientFieldData(is_updatable=True))

    # Portfolio allocation
    portfolio_allocation: Dict[str, Decimal] = Field(
        default={
            "SOL": Decimal("0.50"),  # 50%
        },
        client_data=ClientFieldData(is_updatable=True)
    )
    # Grid parameters
    grid_range: Decimal = Field(default=Decimal("0.002"), client_data=ClientFieldData(is_updatable=True))
    tp_sl_ratio: Decimal = Field(default=Decimal("0.8"), client_data=ClientFieldData(is_updatable=True))
    min_order_amount: Decimal = Field(default=Decimal("5"), client_data=ClientFieldData(is_updatable=True))
    # Risk parameters
    max_deviation: Decimal = Field(default=Decimal("0.05"), client_data=ClientFieldData(is_updatable=True))
    max_open_orders: int = Field(default=2, client_data=ClientFieldData(is_updatable=True))
    # Exchange settings
    connector_name: str = "binance"
    leverage: int = 1
    position_mode: PositionMode = PositionMode.HEDGE
    quote_asset: str = "FDUSD"
    fee_asset: str = "BNB"
    # Grid price multipliers
    min_spread_between_orders: Decimal = Field(
        default=Decimal("0.0001"),  # 0.01% between orders
        client_data=ClientFieldData(is_updatable=True)
    )
    grid_tp_multiplier: Decimal = Field(
        default=Decimal("0.0001"),  # 0.2% take profit
        client_data=ClientFieldData(is_updatable=True)
    )
    # Grid safety parameters
    limit_price_spread: Decimal = Field(
        default=Decimal("0.001"),  # 0.1% spread for limit price
        client_data=ClientFieldData(is_updatable=True)
    )
    activation_bounds: Decimal = Field(
        default=Decimal("0.0002"),  # Activation bounds for orders
        client_data=ClientFieldData(is_updatable=True)
    )
    show_terminated_details: bool = False

    @property
    def quote_asset_allocation(self) -> Decimal:
        """Calculate the implicit quote asset (FDUSD) allocation"""
        return Decimal("1") - sum(self.portfolio_allocation.values())

    @validator("portfolio_allocation")
    def validate_allocation(cls, v):
        total = sum(v.values())
        if total >= Decimal("1"):
            raise ValueError(f"Total allocation {total} exceeds or equals 100%. Must leave room for FDUSD allocation.")
        if "FDUSD" in v:
            raise ValueError("FDUSD should not be explicitly allocated as it is the quote asset")
        return v

    def update_markets(self, markets: Dict[str, Set[str]]) -> Dict[str, Set[str]]:
        if self.connector_name not in markets:
            markets[self.connector_name] = set()
        for asset in self.portfolio_allocation:
            markets[self.connector_name].add(f"{asset}-{self.quote_asset}")
        return markets


class QuantumGridAllocator(ControllerBase):
    def __init__(self, config: QGAConfig, *args, **kwargs):
        super().__init__(config, *args, **kwargs)
        self.config = config
        self.metrics = {}
        # Track unfavorable grid IDs
        self.unfavorable_grid_ids = set()
        # Track held positions from unfavorable grids
        self.unfavorable_positions = {
            f"{asset}-{config.quote_asset}": {
                'long': {'size': Decimal('0'), 'value': Decimal('0'), 'weighted_price': Decimal('0')},
                'short': {'size': Decimal('0'), 'value': Decimal('0'), 'weighted_price': Decimal('0')}
            }
            for asset in config.portfolio_allocation
        }
        self.initialize_rate_sources()

    def initialize_rate_sources(self):
        fee_pair = ConnectorPair(connector_name=self.config.connector_name, trading_pair=f"{self.config.fee_asset}-{self.config.quote_asset}")
        self.market_data_provider.initialize_rate_sources([fee_pair])

    async def update_processed_data(self):
        pass

    def update_portfolio_metrics(self):
        """
        Calculate theoretical vs actual portfolio allocations
        """
        metrics = {
            "theoretical": {},
            "actual": {},
            "difference": {},
        }

        # Get real balances and calculate total portfolio value
        quote_balance = self.market_data_provider.get_balance(self.config.connector_name, self.config.quote_asset)
        total_value_quote = quote_balance

        # Calculate actual allocations including positions
        for asset in self.config.portfolio_allocation:
            trading_pair = f"{asset}-{self.config.quote_asset}"
            price = self.get_mid_price(trading_pair)
            # Get balance and add any position from active grid
            balance = self.market_data_provider.get_balance(self.config.connector_name, asset)
            value = balance * price
            total_value_quote += value
            metrics["actual"][asset] = value
        # Calculate theoretical allocations and differences
        for asset in self.config.portfolio_allocation:
            theoretical_value = total_value_quote * self.config.portfolio_allocation[asset]
            metrics["theoretical"][asset] = theoretical_value
            metrics["difference"][asset] = metrics["actual"][asset] - theoretical_value
        # Add quote asset metrics
        metrics["actual"][self.config.quote_asset] = quote_balance
        metrics["theoretical"][self.config.quote_asset] = total_value_quote * self.config.quote_asset_allocation
        metrics["difference"][self.config.quote_asset] = quote_balance - metrics["theoretical"][self.config.quote_asset]
        metrics["total_portfolio_value"] = total_value_quote
        self.metrics = metrics

    def get_active_grids_by_asset(self) -> Dict[str, List[ExecutorInfo]]:
        """Group active grids by asset using filter_executors"""
        active_grids = {}
        for asset in self.config.portfolio_allocation:
            if asset == self.config.quote_asset:
                continue
            trading_pair = f"{asset}-{self.config.quote_asset}"
            active_executors = self.filter_executors(
                executors=self.executors_info,
                filter_func=lambda e: (
                    e.is_active and
                    e.config.trading_pair == trading_pair
                )
            )
            if active_executors:
                active_grids[asset] = active_executors
        return active_grids

    def to_format_status(self) -> List[str]:
        """Generate a detailed status report with portfolio, grid, and position information"""
        status_lines = []
        total_value = self.metrics.get("total_portfolio_value", Decimal("0"))
        # Portfolio Status
        status_lines.append(f"Total Portfolio Value: ${total_value:,.2f}")
        status_lines.append("")
        status_lines.append("Portfolio Status:")
        status_lines.append("-" * 80)
        status_lines.append(
            f"{'Asset':<8} | "
            f"{'Actual':>10} | "
            f"{'Target':>10} | "
            f"{'Diff':>10} | "
            f"{'Dev %':>8}"
        )
        status_lines.append("-" * 80)
        # Show metrics for each asset
        for asset in self.config.portfolio_allocation:
            actual = self.metrics["actual"].get(asset, Decimal("0"))
            theoretical = self.metrics["theoretical"].get(asset, Decimal("0"))
            difference = self.metrics["difference"].get(asset, Decimal("0"))
            deviation_pct = (difference / theoretical * 100) if theoretical != Decimal("0") else Decimal("0")
            status_lines.append(
                f"{asset:<8} | "
                f"${actual:>9.2f} | "
                f"${theoretical:>9.2f} | "
                f"${difference:>+9.2f} | "
                f"{deviation_pct:>+7.1f}%"
            )
        # Add quote asset metrics
        quote_asset = self.config.quote_asset
        actual = self.metrics["actual"].get(quote_asset, Decimal("0"))
        theoretical = self.metrics["theoretical"].get(quote_asset, Decimal("0"))
        difference = self.metrics["difference"].get(quote_asset, Decimal("0"))
        deviation_pct = (difference / theoretical * 100) if theoretical != Decimal("0") else Decimal("0")
        status_lines.append("-" * 80)
        status_lines.append(
            f"{quote_asset:<8} | "
            f"${actual:>9.2f} | "
            f"${theoretical:>9.2f} | "
            f"${difference:>+9.2f} | "
            f"{deviation_pct:>+7.1f}%"
        )
        # Active Grids Summary
        active_grids = self.get_active_grids_by_asset()
        if active_grids:
            status_lines.append("")
            status_lines.append("Active Grids:")
            status_lines.append("-" * 140)
            status_lines.append(
                f"{'Asset':<8} {'Side':<6} | "
                f"{'Total ($)':<10} {'Position':<10} {'Volume':<10} | "
                f"{'PnL':<10} {'RPnL':<10} {'Fees':<10} | "
                f"{'Start':<10} {'Current':<10} {'End':<10} {'Limit':<10}"
            )
            status_lines.append("-" * 140)
            for asset, executors in active_grids.items():
                for executor in executors:
                    config = executor.config
                    custom_info = executor.custom_info
                    trading_pair = config.trading_pair
                    current_price = self.get_mid_price(trading_pair)
                    # Get grid metrics
                    total_amount = Decimal(str(config.total_amount_quote))
                    position_size = Decimal(str(custom_info.get('position_size_quote', '0')))
                    volume = executor.filled_amount_quote
                    pnl = executor.net_pnl_quote
                    realized_pnl_quote = custom_info.get('realized_pnl_quote', Decimal('0'))
                    fees = executor.cum_fees_quote
                    status_lines.append(
                        f"{asset:<8} {config.side.name:<6} | "
                        f"${total_amount:<9.2f} ${position_size:<9.2f} ${volume:<9.2f} | "
                        f"${pnl:>+9.2f} ${realized_pnl_quote:>+9.2f} ${fees:>9.2f} | "
                        f"{config.start_price:<10.4f} {current_price:<10.4f} {config.end_price:<10.4f} {config.limit_price:<10.4f}"
                    )

        status_lines.append("-" * 100 + "\n")
        return status_lines

    def tp_multiplier(self):
        return self.config.tp_sl_ratio

    def sl_multiplier(self):
        return 1 - self.config.tp_sl_ratio

    def determine_executor_actions(self) -> List[Union[CreateExecutorAction, StopExecutorAction]]:
        actions = []
        self.update_portfolio_metrics()
        active_grids_by_asset = self.get_active_grids_by_asset()
        for asset in self.config.portfolio_allocation:
            if asset == self.config.quote_asset:
                continue
            trading_pair = f"{asset}-{self.config.quote_asset}"
            # Check if there are any active grids for this asset
            if asset in active_grids_by_asset:
                self.logger().debug(f"Skipping {trading_pair} - Active grid exists")
                continue
            theoretical = self.metrics["theoretical"][asset]
            difference = self.metrics["difference"][asset]
            deviation = difference / theoretical if theoretical != Decimal("0") else Decimal("0")
            mid_price = self.get_mid_price(trading_pair)

            # Calculate dynamic grid value percentage based on deviation
            abs_deviation = abs(deviation)
            grid_value_pct = self.config.max_grid_value_pct if abs_deviation > self.config.max_deviation else self.config.base_grid_value_pct

            self.logger().info(
                f"{trading_pair} Grid Sizing - "
                f"Deviation: {deviation:+.1%}, "
                f"Grid Value %: {grid_value_pct:.1%}"
            )

            # Determine which zone we're in by normalizing the deviation over the theoretical allocation
            if deviation < -self.config.long_only_threshold:
                # Long-only zone - only create buy grids
                if difference < Decimal("0"):  # Only if we need to buy
                    grid_value = min(abs(difference), theoretical * grid_value_pct)
                    start_price = mid_price * (1 - self.config.grid_range * self.sl_multiplier())
                    end_price = mid_price * (1 + self.config.grid_range * self.tp_multiplier())
                    grid_action = self.create_grid_executor(
                        trading_pair=trading_pair,
                        side=TradeType.BUY,
                        start_price=start_price,
                        end_price=end_price,
                        grid_value=grid_value,
                        is_unfavorable=False
                    )
                    if grid_action is not None:
                        actions.append(grid_action)
            elif deviation > self.config.short_only_threshold:
                # Short-only zone - only create sell grids
                if difference > Decimal("0"):  # Only if we need to sell
                    grid_value = min(abs(difference), theoretical * grid_value_pct)
                    start_price = mid_price * (1 - self.config.grid_range * self.tp_multiplier())
                    end_price = mid_price * (1 + self.config.grid_range * self.sl_multiplier())
                    grid_action = self.create_grid_executor(
                        trading_pair=trading_pair,
                        side=TradeType.SELL,
                        start_price=start_price,
                        end_price=end_price,
                        grid_value=grid_value,
                        is_unfavorable=False
                    )
                    if grid_action is not None:
                        actions.append(grid_action)

        return actions

    def create_grid_executor(
        self,
        trading_pair: str,
        side: TradeType,
        start_price: Decimal,
        end_price: Decimal,
        grid_value: Decimal,
        is_unfavorable: bool = False
    ) -> CreateExecutorAction:
        """Creates a grid executor with dynamic sizing and range adjustments"""
        # Get trading rules and minimum notional
        trading_rules = self.market_data_provider.get_trading_rules(self.config.connector_name, trading_pair)
        min_notional = max(
            self.config.min_order_amount,
            trading_rules.min_notional_size if trading_rules else Decimal("5.0")
        )
        # Add safety margin and check if grid value is sufficient
        min_grid_value = min_notional * Decimal("5")  # Ensure room for at least 5 levels
        if grid_value < min_grid_value:
            self.logger().info(
                f"Grid value {grid_value} is too small for {trading_pair}. "
                f"Minimum required for viable grid: {min_grid_value}"
            )
            return None  # Skip grid creation if value is too small

        # Select order frequency based on grid favorability
        order_frequency = (
            self.config.unfavorable_order_frequency if is_unfavorable
            else self.config.favorable_order_frequency
        )
        # Calculate limit price to be more aggressive than grid boundaries
        if side == TradeType.BUY:
            # For buys, limit price should be lower than start price
            limit_price = start_price * (1 - self.config.limit_price_spread)
        else:
            # For sells, limit price should be higher than end price
            limit_price = end_price * (1 + self.config.limit_price_spread)
        # Create the executor action
        action = CreateExecutorAction(
            controller_id=self.config.id,
            executor_config=GridExecutorConfig(
                timestamp=self.market_data_provider.time(),
                connector_name=self.config.connector_name,
                trading_pair=trading_pair,
                side=side,
                start_price=start_price,
                end_price=end_price,
                limit_price=limit_price,
                leverage=self.config.leverage,
                total_amount_quote=grid_value,
                safe_extra_spread=self.config.safe_extra_spread,
                min_spread_between_orders=self.config.min_spread_between_orders,
                min_order_amount_quote=self.config.min_order_amount,
                max_open_orders=self.config.max_open_orders,
                order_frequency=order_frequency,  # Use dynamic order frequency
                max_orders_per_batch=self.config.max_orders_per_batch,
                activation_bounds=self.config.activation_bounds,
                keep_position=True,  # Always keep position for potential reversal
                coerce_tp_to_step=True,
                triple_barrier_config=TripleBarrierConfig(
                    take_profit=self.config.grid_tp_multiplier,
                    open_order_type=OrderType.LIMIT_MAKER,
                    take_profit_order_type=OrderType.LIMIT_MAKER,
                    stop_loss=None,
                    time_limit=None,
                    trailing_stop=None,
                )))
        # Track unfavorable grid configs
        if is_unfavorable:
            self.unfavorable_grid_ids.add(action.executor_config.id)
            self.logger().info(
                f"Created unfavorable grid for {trading_pair} - "
                f"Side: {side.name}, Value: ${grid_value:,.2f}, "
                f"Order Frequency: {order_frequency}s"
            )
        else:
            self.logger().info(
                f"Created favorable grid for {trading_pair} - "
                f"Side: {side.name}, Value: ${grid_value:,.2f}, "
                f"Order Frequency: {order_frequency}s"
            )

        return action

    def get_mid_price(self, trading_pair: str) -> Decimal:
        return self.market_data_provider.get_price_by_type(self.config.connector_name, trading_pair, PriceType.MidPrice)
