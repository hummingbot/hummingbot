from decimal import Decimal
from typing import Dict, List, Optional, Set, Union

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

    # Portfolio allocation
    portfolio_allocation: Dict[str, Decimal] = Field(
        default={
            "BTC": Decimal("0.50"),  # 50%
            "SOL": Decimal("0.20"),  # 20%
            # FDUSD implicitly gets remaining 30%
        },
        client_data=ClientFieldData(is_updatable=True)
    )
    # Grid parameters
    grid_value_pct: Decimal = Field(default=Decimal("0.10"), client_data=ClientFieldData(is_updatable=True))
    grid_range: Decimal = Field(default=Decimal("0.002"), client_data=ClientFieldData(is_updatable=True))
    tp_sl_ratio: Decimal = Field(default=Decimal("0.8"), client_data=ClientFieldData(is_updatable=True))
    min_order_amount: Decimal = Field(default=Decimal("5"), client_data=ClientFieldData(is_updatable=True))
    # Risk parameters
    max_deviation: Decimal = Field(default=Decimal("0.05"), client_data=ClientFieldData(is_updatable=True))
    max_concurrent_grids: int = Field(default=3, client_data=ClientFieldData(is_updatable=True))
    # Exchange settings
    connector_name: str = "binance"
    leverage: int = 1
    position_mode: PositionMode = PositionMode.HEDGE
    quote_asset: str = "FDUSD"
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
    keep_position: bool = Field(
        default=True,  # Always keep position when grid is stopped
        client_data=ClientFieldData(is_updatable=True)
    )
    fee_asset: str = "BNB"
    max_open_orders: int = Field(default=3, client_data=ClientFieldData(is_updatable=True))
    order_frequency: int = Field(default=1, client_data=ClientFieldData(is_updatable=True))
    max_orders_per_batch: int = Field(default=1, client_data=ClientFieldData(is_updatable=True))
    activation_bounds: Decimal = Field(Decimal("0.005"), client_data=ClientFieldData(is_updatable=True))

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
        # Initialize position_hold_grids with trading pairs
        self.position_hold_grids = {
            f"{asset}-{config.quote_asset}": []
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
        """
        Group active grids by asset and update position hold grids in a single pass
        """
        active_grids = {}
        # Reset position hold grids tracking (keep the keys)
        for trading_pair in self.position_hold_grids:
            self.position_hold_grids[trading_pair] = []
        # Process all executors in a single pass
        for executor in self.executors_info:
            trading_pair = executor.config.trading_pair
            asset = trading_pair.split("-")[0]
            position = executor.custom_info.get('position_size_quote', Decimal('0'))
            if executor.is_active:
                # Track active grid
                if asset not in active_grids:
                    active_grids[asset] = []
                active_grids[asset].append(executor)
            elif position != Decimal('0'):
                # Track inactive grid with position
                self.position_hold_grids[trading_pair].append(executor)
        return active_grids

    def get_grid_status_report(self) -> List[str]:
        """Generate a concise status report with directional position tracking"""
        status_lines = []
        # First show portfolio allocations
        status_lines.append("Portfolio Allocations:")
        status_lines.append("-" * 100)
        # Header for portfolio metrics
        status_lines.append(
            f"{'Asset':<8} | "
            f"{'Actual':>12} | "
            f"{'Theoretical':>12} | "
            f"{'Difference':>12} | "
            f"{'Deviation %':>12}"
        )
        status_lines.append("-" * 100)
        # Show metrics for each asset
        for asset in self.config.portfolio_allocation:
            actual = self.metrics["actual"].get(asset, Decimal("0"))
            theoretical = self.metrics["theoretical"].get(asset, Decimal("0"))
            difference = self.metrics["difference"].get(asset, Decimal("0"))
            # Calculate deviation percentage
            deviation_pct = (difference / theoretical * 100) if theoretical != Decimal("0") else Decimal("0")
            status_lines.append(
                f"{asset:<8} | "
                f"${actual:>11.2f} | "
                f"${theoretical:>11.2f} | "
                f"${difference:>+11.2f} | "
                f"{deviation_pct:>+11.1f}%"
            )
        # Add quote asset metrics
        quote_asset = self.config.quote_asset
        actual = self.metrics["actual"].get(quote_asset, Decimal("0"))
        theoretical = self.metrics["theoretical"].get(quote_asset, Decimal("0"))
        difference = self.metrics["difference"].get(quote_asset, Decimal("0"))
        deviation_pct = (difference / theoretical * 100) if theoretical != Decimal("0") else Decimal("0")
        status_lines.append("-" * 100)
        status_lines.append(
            f"{quote_asset:<8} | "
            f"${actual:>11.2f} | "
            f"${theoretical:>11.2f} | "
            f"${difference:>+11.2f} | "
            f"{deviation_pct:>+11.1f}%"
        )
        # Add total portfolio value
        status_lines.append("-" * 100)
        total_value = self.metrics.get("total_portfolio_value", Decimal("0"))
        status_lines.append(f"Total Portfolio Value: ${total_value:,.2f}")
        # Add the rest of the status report (positions and performance)
        status_lines.extend(self._get_position_status_lines())
        # Track all realized PnL from all executors (active, held, and terminated)
        total_realized_pnl = Decimal('0')
        total_unrealized_pnl = Decimal('0')
        total_fees = Decimal('0')
        total_held_value = Decimal('0')
        total_active_value = Decimal('0')
        for executor in self.executors_info:
            custom_info = executor.custom_info
            realized_pnl = custom_info.get('realized_pnl_quote', Decimal('0'))
            fees = custom_info.get('realized_fees_quote', Decimal('0'))
            total_realized_pnl += realized_pnl
            total_fees += fees
            # Track position values for active grids
            if executor.is_active:
                position = custom_info.get('position_size_quote', Decimal('0'))
                total_active_value += abs(position)
        # Add position status lines and track held values/unrealized PnL
        status_lines.append("")
        status_lines.append("Position Status:")
        status_lines.append("-" * 100)
        # Track held positions and calculate unrealized PnL
        for trading_pair, historical_grids in self.position_hold_grids.items():
            for grid in historical_grids:
                custom_info = grid.custom_info
                position = custom_info.get('held_position_value', Decimal('0'))
                if position == Decimal('0'):
                    continue
                total_held_value += abs(position)
                # Calculate unrealized PnL for held positions
                break_even = custom_info.get('break_even_price')
                if break_even != 'N/A' and break_even is not None:
                    break_even = Decimal(str(break_even))
                    current_price = self.get_mid_price(trading_pair)
                    price_diff_pct = (current_price - break_even) / break_even
                    # Determine if it's a buy or sell position
                    is_buy = any(
                        order.get("trade_type") == TradeType.BUY.name
                        for order in grid.custom_info.get("held_position_orders", []))
                    unrealized_pnl = position * price_diff_pct * (1 if is_buy else -1)
                    total_unrealized_pnl += unrealized_pnl
        # Add performance summary
        if total_active_value > 0 or total_held_value > 0:
            status_lines.append("")
            status_lines.append("Performance Summary:")
            status_lines.append("-" * 100)
            total_pnl = total_realized_pnl + total_unrealized_pnl
            total_value = total_active_value + total_held_value
            status_lines.append(
                f"Summary         {'':12} | "
                f"Total Value: ${total_value:>10.2f} | "
                f"Real.PnL: ${total_realized_pnl:>+10.2f} | "
                f"Unreal.PnL: ${total_unrealized_pnl:>+10.2f}"
            )
            status_lines.append(
                f"Performance     {'':12} | "
                f"Total PnL: ${total_pnl:>+10.2f} | "
                f"Total Fees: ${total_fees:>10.2f} | "
                f"Net: ${(total_pnl - total_fees):>+10.2f}"
            )
            if total_value > 0:
                active_pct = (total_active_value / total_value) * Decimal('100')
                held_pct = (total_held_value / total_value) * Decimal('100')
                pnl_pct = ((total_pnl - total_fees) / total_value * 100)
                status_lines.append(
                    f"Allocation      {'':12} | "
                    f"Active: {active_pct:>6.1f}% | "
                    f"Held: {held_pct:>6.1f}% | "
                    f"PnL%: {pnl_pct:>+6.1f}%"
                )
        return status_lines if status_lines else ["No positions"]

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
            if abs(deviation) < self.config.max_deviation:
                # Calculate total grid allocation
                total_grid_value = theoretical * self.config.grid_value_pct
                # Calculate imbalance ratio (-1 to 1)
                imbalance_ratio = difference / theoretical
                # Distribute grid values based on imbalance
                if difference < Decimal("0"):  # Need to buy more
                    buy_ratio = Decimal("0.5") + abs(imbalance_ratio) / Decimal("2")
                    sell_ratio = Decimal("1") - buy_ratio
                else:  # Need to sell more
                    sell_ratio = Decimal("0.5") + abs(imbalance_ratio) / Decimal("2")
                    buy_ratio = Decimal("1") - sell_ratio
                # Calculate grid values for each side
                buy_grid_value = total_grid_value * buy_ratio
                sell_grid_value = total_grid_value * sell_ratio
                self.logger().info(
                    f"{trading_pair} Grid Distribution - "
                    f"Imbalance: ${difference:,.2f} ({imbalance_ratio:+.1%}) | "
                    f"Buy Grid: ${buy_grid_value:,.2f} ({buy_ratio:.1%}) | "
                    f"Sell Grid: ${sell_grid_value:,.2f} ({sell_ratio:.1%})"
                )
                # Create buy grid
                if buy_grid_value > Decimal("0"):
                    buy_grid = self.create_grid_executor(
                        trading_pair=trading_pair,
                        side=TradeType.BUY,
                        current_price=mid_price,
                        grid_value=buy_grid_value,
                        range_adjustment=deviation
                    )
                    if buy_grid is not None:
                        actions.append(buy_grid)
                # Create sell grid
                if sell_grid_value > Decimal("0"):
                    sell_grid = self.create_grid_executor(
                        trading_pair=trading_pair,
                        side=TradeType.SELL,
                        current_price=mid_price,
                        grid_value=sell_grid_value,
                        range_adjustment=deviation
                    )
                    if sell_grid is not None:
                        actions.append(sell_grid)
            else:
                # For larger deviations, create single grid with size based on imbalance
                grid_value = min(
                    abs(difference),
                    theoretical * self.config.grid_value_pct
                )
                grid_action = self.create_grid_executor(
                    trading_pair=trading_pair,
                    side=TradeType.BUY if deviation < 0 else TradeType.SELL,
                    current_price=mid_price,
                    grid_value=grid_value
                )
                if grid_action is not None:
                    actions.append(grid_action)
        return actions

    def create_grid_executor(
        self,
        trading_pair: str,
        side: TradeType,
        current_price: Decimal,
        grid_value: Optional[Decimal] = None,
        range_adjustment: Decimal = Decimal("0")
    ) -> CreateExecutorAction:
        """Creates a grid executor with dynamic sizing and range adjustments"""
        asset = trading_pair.split("-")[0]
        # Use provided grid_value or calculate default
        if grid_value is None:
            allocation = self.metrics["theoretical"][asset]
            grid_value = allocation * self.config.grid_value_pct
        # Get trading rules and minimum notional
        trading_rules = self.market_data_provider.get_trading_rules(self.config.connector_name, trading_pair)
        min_notional = max(
            self.config.min_order_amount,
            trading_rules.min_notional_size if trading_rules else Decimal("5.0")
        )
        # Add safety margin and check if grid value is sufficient
        min_grid_value = min_notional * Decimal("3")  # Ensure room for at least 3 levels
        if grid_value < min_grid_value:
            self.logger().info(
                f"Grid value {grid_value} is too small for {trading_pair}. "
                f"Minimum required for viable grid: {min_grid_value}"
            )
            return None  # Skip grid creation if value is too small
        # Adjust grid boundaries based on current imbalance
        base_range = self.config.grid_range
        if side == TradeType.BUY:
            # For buy side:
            # - Reduce upward range if already holding too much
            # - Increase downward range to catch dips
            tp_multiplier = base_range * (self.config.tp_sl_ratio - abs(range_adjustment))
            sl_multiplier = base_range * (1 - self.config.tp_sl_ratio + abs(range_adjustment))
            start_price = current_price * (1 - sl_multiplier)
            end_price = current_price * (1 + tp_multiplier)
            limit_price = start_price * (1 - self.config.limit_price_spread)
        else:
            # For sell side:
            # - Reduce downward range if already holding too little
            # - Increase upward range to catch rallies
            tp_multiplier = base_range * (self.config.tp_sl_ratio - abs(range_adjustment))
            sl_multiplier = base_range * (1 - self.config.tp_sl_ratio + abs(range_adjustment))
            start_price = current_price * (1 - tp_multiplier)
            end_price = current_price * (1 + sl_multiplier)
            limit_price = end_price * (1 + self.config.limit_price_spread)
        return CreateExecutorAction(
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
                safe_extra_spread=Decimal("0.00002"),
                min_spread_between_orders=self.config.min_spread_between_orders,
                min_order_amount_quote=self.config.min_order_amount,
                max_open_orders=self.config.max_open_orders,
                order_frequency=self.config.order_frequency,
                max_orders_per_batch=self.config.max_orders_per_batch,
                activation_bounds=self.config.activation_bounds,
                keep_position=self.config.keep_position,
                triple_barrier_config=TripleBarrierConfig(
                    take_profit=self.config.grid_tp_multiplier,
                    open_order_type=OrderType.LIMIT_MAKER,
                    take_profit_order_type=OrderType.LIMIT_MAKER,
                    stop_loss=None,
                    time_limit=None,
                    trailing_stop=None,
                )))

    def get_mid_price(self, trading_pair: str) -> Decimal:
        return self.market_data_provider.get_price_by_type(self.config.connector_name, trading_pair, PriceType.MidPrice)

    def to_format_status(self) -> List[str]:
        return self.get_grid_status_report()

    def _get_position_status_lines(self) -> List[str]:
        """Generate status lines for active and held positions"""
        status_lines = []
        # Add header for position status
        status_lines.append("")
        status_lines.append("Position Status:")
        status_lines.append("-" * 100)
        # First report active grids
        for executor in self.executors_info:
            if executor.is_active:
                custom_info = executor.custom_info
                position = custom_info.get('position_size_quote', Decimal('0'))
                if position == Decimal('0'):
                    continue
                trading_pair = executor.config.trading_pair
                pnl = custom_info.get('realized_pnl_quote', Decimal('0'))
                break_even = custom_info.get('break_even_price', 'N/A')
                current_price = self.get_mid_price(trading_pair)
                # Round break-even price to same decimals as current price
                if break_even != 'N/A':
                    price_decimals = abs(Decimal(str(current_price)).as_tuple().exponent)
                    break_even = f"{Decimal(str(break_even)):.{price_decimals}f}"
                # Adjust position value based on side
                side_indicator = "[BUY]" if executor.config.side == TradeType.BUY else "[SELL]"
                position_value = position if executor.config.side == TradeType.BUY else -position
                status_lines.append(
                    f"{trading_pair:<12} {side_indicator:<8} | "
                    f"Pos: ${position_value:>+10.2f} | "
                    f"BE: {break_even:>10} | "
                    f"Price: {current_price:>10.2f} | "
                    f"PnL: ${pnl:>+10.2f}"
                )
        # Then report held positions
        for trading_pair, historical_grids in self.position_hold_grids.items():
            for grid in historical_grids:
                custom_info = grid.custom_info
                position = custom_info.get('held_position_value', Decimal('0'))
                if position == Decimal('0'):
                    continue
                # Determine if it's a buy or sell position
                is_buy = any(
                    order.get("trade_type") == TradeType.BUY.name
                    for order in grid.custom_info.get("held_position_orders", [])
                )
                side_indicator = "[H-BUY]" if is_buy else "[H-SELL]"
                position_value = position if is_buy else -position
                break_even = custom_info.get('break_even_price')
                current_price = self.get_mid_price(trading_pair)
                # Round break-even price
                if break_even != 'N/A' and break_even is not None:
                    price_decimals = abs(Decimal(str(current_price)).as_tuple().exponent)
                    break_even = f"{Decimal(str(break_even)):.{price_decimals}f}"
                    # Calculate unrealized PnL
                    break_even_dec = Decimal(str(break_even))
                    price_diff_pct = (current_price - break_even_dec) / break_even_dec
                    unrealized_pnl = position * price_diff_pct * (1 if is_buy else -1)
                else:
                    unrealized_pnl = Decimal('0')
                status_lines.append(
                    f"{trading_pair:<12} {side_indicator:<8} | "
                    f"Pos: ${position_value:>+10.2f} | "
                    f"BE: {break_even:>10} | "
                    f"Price: {current_price:>10.2f} | "
                    f"Unreal.PnL: ${unrealized_pnl:>+10.2f}"
                )
        return status_lines
