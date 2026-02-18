"""
PMM V1 Controller - Pure Market Making Controller

This controller replicates the legacy pure_market_making strategy with:
- Multi-level spread/amount configuration (list-based)
- Inventory skew calculation matching legacy algorithm
- Order refresh with timing controls and tolerance
- Static and moving price bands
- Minimum spread enforcement
"""

from decimal import Decimal
from typing import Dict, List, Optional, Tuple

import numpy as np
from pydantic import Field, field_validator

from hummingbot.core.data_type.common import MarketDict, PriceType, TradeType
from hummingbot.strategy_v2.controllers.controller_base import ControllerBase, ControllerConfigBase
from hummingbot.strategy_v2.executors.data_types import ConnectorPair
from hummingbot.strategy_v2.executors.order_executor.data_types import ExecutionStrategy, OrderExecutorConfig
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, ExecutorAction, StopExecutorAction
from hummingbot.strategy_v2.models.executors import CloseType


class PMMV1Config(ControllerConfigBase):
    """
    Configuration for the PMM V1 controller - a pure market making controller.

    Implements the core features from legacy pure_market_making strategy.
    """
    controller_type: str = "generic"
    controller_name: str = "pmm_v1"

    # === Core Market Settings ===
    connector_name: str = Field(
        default="binance",
        json_schema_extra={
            "prompt_on_new": True,
            "prompt": "Enter the connector name (e.g., binance):",
        }
    )
    trading_pair: str = Field(
        default="BTC-USDT",
        json_schema_extra={
            "prompt_on_new": True,
            "prompt": "Enter the trading pair (e.g., BTC-USDT):",
        }
    )

    # === Spread & Amount Configuration ===
    # Override inherited total_amount_quote — PMM V1 uses order_amount in base asset
    total_amount_quote: Decimal = Field(default=Decimal("0"), json_schema_extra={"prompt_on_new": False})

    order_amount: Decimal = Field(
        default=Decimal("1"),
        json_schema_extra={
            "prompt_on_new": True, "is_updatable": True,
            "prompt": "Enter the order amount in base asset (e.g., 0.01 for BTC):",
        }
    )
    buy_spreads: List[float] = Field(
        default="0.01",
        json_schema_extra={
            "prompt_on_new": True, "is_updatable": True,
            "prompt": "Enter comma-separated buy spreads as decimals (e.g., '0.01,0.02' for 1%, 2%):",
        }
    )
    sell_spreads: List[float] = Field(
        default="0.01",
        json_schema_extra={
            "prompt_on_new": True, "is_updatable": True,
            "prompt": "Enter comma-separated sell spreads as decimals (e.g., '0.01,0.02' for 1%, 2%):",
        }
    )

    # === Timing Configuration ===
    order_refresh_time: int = Field(
        default=30,
        json_schema_extra={
            "prompt_on_new": True, "is_updatable": True,
            "prompt": "Enter order refresh time in seconds (how often to refresh orders):",
        }
    )
    order_refresh_tolerance_pct: Decimal = Field(
        default=Decimal("-1"),
        json_schema_extra={
            "prompt_on_new": False, "is_updatable": True,
            "prompt": "Enter order refresh tolerance as decimal (e.g., 0.01 = 1%). -1 to disable:",
        }
    )
    filled_order_delay: int = Field(
        default=60,
        json_schema_extra={
            "prompt_on_new": False, "is_updatable": True,
            "prompt": "Enter delay in seconds after a fill before placing new orders:",
        }
    )

    # === Inventory Skew Configuration ===
    inventory_skew_enabled: bool = Field(
        default=False,
        json_schema_extra={
            "prompt_on_new": True, "is_updatable": True,
            "prompt": "Enable inventory skew? (adjusts order sizes based on inventory):",
        }
    )
    target_base_pct: Decimal = Field(
        default=Decimal("0.5"),
        json_schema_extra={
            "prompt_on_new": True, "is_updatable": True,
            "prompt": "Enter target base percentage (e.g., 0.5 for 50% base, 50% quote):",
        }
    )
    inventory_range_multiplier: Decimal = Field(
        default=Decimal("1.0"),
        json_schema_extra={
            "prompt_on_new": False, "is_updatable": True,
            "prompt": "Enter inventory range multiplier for skew calculation:",
        }
    )

    # === Static Price Band Configuration ===
    price_ceiling: Decimal = Field(
        default=Decimal("-1"),
        json_schema_extra={
            "prompt_on_new": False, "is_updatable": True,
            "prompt": "Enter static price ceiling (-1 to disable). Only sell orders above this price:",
        }
    )
    price_floor: Decimal = Field(
        default=Decimal("-1"),
        json_schema_extra={
            "prompt_on_new": False, "is_updatable": True,
            "prompt": "Enter static price floor (-1 to disable). Only buy orders below this price:",
        }
    )

    # === Validators ===
    @field_validator('buy_spreads', 'sell_spreads', mode="before")
    @classmethod
    def parse_spreads(cls, v):
        if v is None or v == "":
            return []
        if isinstance(v, str):
            return [float(x.strip()) for x in v.split(',')]
        return [float(x) for x in v]

    def get_spreads(self, trade_type: TradeType) -> List[float]:
        """Get spreads for a trade type. Each spread defines one order level."""
        if trade_type == TradeType.BUY:
            return self.buy_spreads
        return self.sell_spreads

    def update_markets(self, markets: MarketDict) -> MarketDict:
        return markets.add_or_update(self.connector_name, self.trading_pair)


class PMMV1(ControllerBase):
    """
    PMM V1 Controller - Pure Market Making Controller.

    Replicates legacy pure_market_making strategy with simple limit orders.
    """

    def __init__(self, config: PMMV1Config, *args, **kwargs):
        super().__init__(config, *args, **kwargs)
        self.config = config
        self.market_data_provider.initialize_rate_sources([ConnectorPair(
            connector_name=config.connector_name, trading_pair=config.trading_pair)])

        # Track when each level can next create orders (for filled_order_delay)
        self._level_next_create_timestamps: Dict[str, float] = {}
        # Track last seen executor states to detect fills
        self._last_seen_executors: Dict[str, bool] = {}

    def _detect_filled_executors(self):
        """Detect executors that were filled (not cancelled)."""
        # Get current active executor IDs by level
        current_active_by_level = {}
        filled_levels = set()

        for executor in self.executors_info:
            level_id = executor.custom_info.get("level_id", "")

            if executor.is_active:
                current_active_by_level[level_id] = True
            elif executor.close_type == CloseType.POSITION_HOLD:
                # POSITION_HOLD means the order was filled
                filled_levels.add(level_id)

        # Check for levels that were active before but aren't now and were filled
        for level_id, was_active in self._last_seen_executors.items():
            if (was_active and
                level_id not in current_active_by_level and
                    level_id in filled_levels):
                # This level was active before, not now, and was filled
                self._handle_filled_executor(level_id)

        # Update last seen state
        self._last_seen_executors = current_active_by_level.copy()

    def _handle_filled_executor(self, level_id: str):
        """Set the next create timestamp for a level when its executor is filled."""
        current_time = self.market_data_provider.time()
        self._level_next_create_timestamps[level_id] = current_time + self.config.filled_order_delay

        # Log the filled order delay
        self.logger().debug(f"Order on level {level_id} filled. Next order for this level can be created after {self.config.filled_order_delay}s delay.")

    def _get_reference_price(self) -> Decimal:
        """Get reference price (mid price)."""
        try:
            price = self.market_data_provider.get_price_by_type(
                self.config.connector_name,
                self.config.trading_pair,
                PriceType.MidPrice
            )
            if price is None or (isinstance(price, float) and np.isnan(price)):
                return Decimal("0")
            return Decimal(str(price))
        except Exception:
            return Decimal("0")

    async def update_processed_data(self):
        """
        Update processed data with reference price, inventory info, and derived metrics.
        """
        # Detect filled executors (executors that disappeared since last check)
        self._detect_filled_executors()

        reference_price = self._get_reference_price()

        # Calculate inventory metrics for skew
        base_balance, quote_balance = self._get_balances()
        total_value_in_quote = base_balance * reference_price + quote_balance if reference_price > 0 else Decimal("0")

        if total_value_in_quote > 0:
            current_base_pct = (base_balance * reference_price) / total_value_in_quote
        else:
            current_base_pct = Decimal("0")

        # Calculate inventory skew multipliers using legacy algorithm
        buy_skew, sell_skew = self._calculate_inventory_skew_legacy(
            current_base_pct, base_balance, quote_balance, reference_price
        )

        # Determine effective price ceiling and floor
        effective_ceiling = self.config.price_ceiling if self.config.price_ceiling > 0 else None
        effective_floor = self.config.price_floor if self.config.price_floor > 0 else None

        # Calculate proposal prices for tolerance comparison
        buy_proposal_prices, sell_proposal_prices = self._calculate_proposal_prices(reference_price)

        self.processed_data = {
            "reference_price": reference_price,
            "current_base_pct": current_base_pct,
            "base_balance": base_balance,
            "quote_balance": quote_balance,
            "buy_skew": buy_skew,
            "sell_skew": sell_skew,
            "price_ceiling": effective_ceiling,
            "price_floor": effective_floor,
            "buy_proposal_prices": buy_proposal_prices,
            "sell_proposal_prices": sell_proposal_prices,
        }

    def _get_balances(self) -> Tuple[Decimal, Decimal]:
        """Get base and quote balances from the connector."""
        try:
            base, quote = self.config.trading_pair.split("-")
            base_balance = self.market_data_provider.get_balance(
                self.config.connector_name, base
            )
            quote_balance = self.market_data_provider.get_balance(
                self.config.connector_name, quote
            )
            return Decimal(str(base_balance)), Decimal(str(quote_balance))
        except Exception:
            return Decimal("0"), Decimal("0")

    def _calculate_inventory_skew_legacy(
        self,
        current_base_pct: Decimal,
        base_balance: Decimal,
        quote_balance: Decimal,
        reference_price: Decimal
    ) -> Tuple[Decimal, Decimal]:
        """
        Calculate inventory skew multipliers matching the legacy inventory_skew_calculator.pyx algorithm.

        The legacy algorithm:
        1. Uses total_order_size * inventory_range_multiplier for the range (in base asset)
        2. Calculates water marks around target
        3. Uses np.interp for smooth interpolation
        4. Returns bid/ask ratios from 0.0 to 2.0
        """
        if not self.config.inventory_skew_enabled:
            return Decimal("1"), Decimal("1")

        if reference_price <= 0:
            return Decimal("1"), Decimal("1")

        # Get total order size in base asset for range calculation
        num_buy_levels = len(self.config.get_spreads(TradeType.BUY))
        num_sell_levels = len(self.config.get_spreads(TradeType.SELL))
        total_order_size_base = float(self.config.order_amount) * (num_buy_levels + num_sell_levels)

        if total_order_size_base <= 0:
            return Decimal("1"), Decimal("1")

        # Calculate range in base asset (matching legacy)
        base_asset_range = total_order_size_base * float(self.config.inventory_range_multiplier)

        # Call the legacy calculation
        return self._c_calculate_bid_ask_ratios(
            float(base_balance),
            float(quote_balance),
            float(reference_price),
            float(self.config.target_base_pct),
            base_asset_range
        )

    def _c_calculate_bid_ask_ratios(
        self,
        base_asset_amount: float,
        quote_asset_amount: float,
        price: float,
        target_base_asset_ratio: float,
        base_asset_range: float
    ) -> Tuple[Decimal, Decimal]:
        """
        Exact port of legacy c_calculate_bid_ask_ratios_from_base_asset_ratio.
        """
        total_portfolio_value = base_asset_amount * price + quote_asset_amount

        if total_portfolio_value <= 0.0 or base_asset_range <= 0.0:
            return Decimal("1"), Decimal("1")

        base_asset_value = base_asset_amount * price
        base_asset_range_value = min(base_asset_range * price, total_portfolio_value * 0.5)
        target_base_asset_value = total_portfolio_value * target_base_asset_ratio
        left_base_asset_value_limit = max(target_base_asset_value - base_asset_range_value, 0.0)
        right_base_asset_value_limit = target_base_asset_value + base_asset_range_value

        # Use np.interp for smooth interpolation (matching legacy)
        left_inventory_ratio = float(np.interp(
            base_asset_value,
            [left_base_asset_value_limit, target_base_asset_value],
            [0.0, 0.5]
        ))
        right_inventory_ratio = float(np.interp(
            base_asset_value,
            [target_base_asset_value, right_base_asset_value_limit],
            [0.5, 1.0]
        ))

        if base_asset_value < target_base_asset_value:
            bid_adjustment = float(np.interp(left_inventory_ratio, [0, 0.5], [2.0, 1.0]))
        else:
            bid_adjustment = float(np.interp(right_inventory_ratio, [0.5, 1], [1.0, 0.0]))

        ask_adjustment = 2.0 - bid_adjustment

        return Decimal(str(bid_adjustment)), Decimal(str(ask_adjustment))

    def _calculate_proposal_prices(
        self, reference_price: Decimal
    ) -> Tuple[List[Decimal], List[Decimal]]:
        """Calculate what the proposal prices would be for tolerance comparison."""
        buy_spreads = self.config.get_spreads(TradeType.BUY)
        sell_spreads = self.config.get_spreads(TradeType.SELL)

        buy_prices = []
        for spread in buy_spreads:
            price = reference_price * (Decimal("1") - Decimal(str(spread)))
            buy_prices.append(price)

        sell_prices = []
        for spread in sell_spreads:
            price = reference_price * (Decimal("1") + Decimal(str(spread)))
            sell_prices.append(price)

        return buy_prices, sell_prices

    def determine_executor_actions(self) -> List[ExecutorAction]:
        """Determine actions based on current state."""
        # Don't create new actions if the controller is being stopped
        if self.status == RunnableStatus.TERMINATED:
            return []

        actions = []
        actions.extend(self.create_actions_proposal())
        actions.extend(self.stop_actions_proposal())
        return actions

    def create_actions_proposal(self) -> List[ExecutorAction]:
        """Create actions proposal for new executors."""
        create_actions = []

        # Get levels to execute
        levels_to_execute = self.get_levels_to_execute()

        buy_spreads = self.config.get_spreads(TradeType.BUY)
        sell_spreads = self.config.get_spreads(TradeType.SELL)

        reference_price = Decimal(self.processed_data["reference_price"])
        if reference_price <= 0:
            return []

        buy_skew = self.processed_data["buy_skew"]
        sell_skew = self.processed_data["sell_skew"]

        for level_id in levels_to_execute:
            trade_type = self.get_trade_type_from_level_id(level_id)
            level = self.get_level_from_level_id(level_id)

            # Get spread for this level
            if trade_type == TradeType.BUY:
                if level >= len(buy_spreads):
                    continue
                spread_in_pct = Decimal(str(buy_spreads[level]))
                skew = buy_skew
            else:
                if level >= len(sell_spreads):
                    continue
                spread_in_pct = Decimal(str(sell_spreads[level]))
                skew = sell_skew

            # Calculate order price
            side_multiplier = Decimal("-1") if trade_type == TradeType.BUY else Decimal("1")
            price = reference_price * (Decimal("1") + side_multiplier * spread_in_pct)

            # Apply inventory skew to order amount (already in base asset)
            amount = self.config.order_amount * skew
            amount = self.market_data_provider.quantize_order_amount(
                self.config.connector_name, self.config.trading_pair, amount
            )

            if amount == Decimal("0"):
                continue

            # Quantize price
            price = self.market_data_provider.quantize_order_price(
                self.config.connector_name, self.config.trading_pair, price
            )

            # Create executor config
            executor_config = self._get_executor_config(level_id, price, amount, trade_type)
            if executor_config is not None:
                create_actions.append(CreateExecutorAction(
                    controller_id=self.config.id,
                    executor_config=executor_config
                ))

        return create_actions

    def get_levels_to_execute(self) -> List[str]:
        """Get levels that need new executors.

        A level is considered "working" (and won't get a new executor) if:
        - It has an active executor, OR
        - Its filled_order_delay period hasn't expired yet
        """
        current_time = self.market_data_provider.time()

        # Get levels with active executors
        active_levels = self.filter_executors(
            executors=self.executors_info,
            filter_func=lambda x: x.is_active
        )
        active_level_ids = [executor.custom_info.get("level_id", "") for executor in active_levels]

        # Get missing levels
        missing_levels = self._get_not_active_levels_ids(active_level_ids)

        # Filter out levels still in filled_order_delay period
        missing_levels = [
            level_id for level_id in missing_levels
            if current_time >= self._level_next_create_timestamps.get(level_id, 0)
        ]

        # Apply price band filter
        missing_levels = self._apply_price_band_filter(missing_levels)

        return missing_levels

    def _get_not_active_levels_ids(self, active_level_ids: List[str]) -> List[str]:
        """Get level IDs that are not currently active."""
        buy_spreads = self.config.get_spreads(TradeType.BUY)
        sell_spreads = self.config.get_spreads(TradeType.SELL)

        num_buy_levels = len(buy_spreads)
        num_sell_levels = len(sell_spreads)

        buy_ids_missing = [
            self.get_level_id_from_side(TradeType.BUY, level)
            for level in range(num_buy_levels)
            if self.get_level_id_from_side(TradeType.BUY, level) not in active_level_ids
        ]
        sell_ids_missing = [
            self.get_level_id_from_side(TradeType.SELL, level)
            for level in range(num_sell_levels)
            if self.get_level_id_from_side(TradeType.SELL, level) not in active_level_ids
        ]
        return buy_ids_missing + sell_ids_missing

    def _apply_price_band_filter(self, level_ids: List[str]) -> List[str]:
        """Filter out levels that violate price band constraints.

        Price band logic (matching legacy pure_market_making):
        - If price >= ceiling: only sell orders (don't buy at high prices)
        - If price <= floor: only buy orders (don't sell at low prices)
        """
        reference_price = self.processed_data["reference_price"]
        ceiling = self.processed_data.get("price_ceiling")
        floor = self.processed_data.get("price_floor")

        filtered = []
        for level_id in level_ids:
            trade_type = self.get_trade_type_from_level_id(level_id)
            if trade_type == TradeType.BUY and ceiling is not None and reference_price >= ceiling:
                # Price at or above ceiling: only sell orders
                continue
            if trade_type == TradeType.SELL and floor is not None and reference_price <= floor:
                # Price at or below floor: only buy orders
                continue
            filtered.append(level_id)
        return filtered

    def stop_actions_proposal(self) -> List[ExecutorAction]:
        """Create actions to stop executors."""
        stop_actions = []
        stop_actions.extend(self._executors_to_refresh())
        return stop_actions

    def _executors_to_refresh(self) -> List[StopExecutorAction]:
        """Get executors that should be refreshed.

        Matching legacy behavior:
        - Compares current order prices to proposal prices (not just reference price)
        - If ALL orders on a side are within tolerance, don't refresh that side
        """
        current_time = self.market_data_provider.time()

        # Only consider refresh after refresh time
        executors_past_refresh = [
            e for e in self.executors_info
            if e.is_active and not e.is_trading
            and current_time - e.timestamp > self.config.order_refresh_time
        ]

        if not executors_past_refresh:
            return []

        # If tolerance is disabled, refresh all
        if self.config.order_refresh_tolerance_pct < 0:
            return [
                StopExecutorAction(
                    controller_id=self.config.id,
                    executor_id=executor.id,
                    keep_position=True
                )
                for executor in executors_past_refresh
            ]

        # Get current order prices and proposal prices
        buy_proposal_prices = self.processed_data.get("buy_proposal_prices", [])
        sell_proposal_prices = self.processed_data.get("sell_proposal_prices", [])

        # Get current buy/sell order prices
        current_buy_prices = []
        current_sell_prices = []
        for executor in executors_past_refresh:
            level_id = executor.custom_info.get("level_id", "")
            order_price = getattr(executor.config, 'price', None)
            if order_price is None:
                continue
            if level_id.startswith("buy"):
                current_buy_prices.append(order_price)
            elif level_id.startswith("sell"):
                current_sell_prices.append(order_price)

        # Check if within tolerance (matching legacy c_is_within_tolerance)
        buys_within_tolerance = self._is_within_tolerance(
            current_buy_prices, buy_proposal_prices
        )
        sells_within_tolerance = self._is_within_tolerance(
            current_sell_prices, sell_proposal_prices
        )

        # Log tolerance decisions
        if buys_within_tolerance and sells_within_tolerance:
            if executors_past_refresh:
                executor_level_ids = [e.custom_info.get("level_id", "unknown") for e in executors_past_refresh]
                self.logger().debug(f"Orders {executor_level_ids} will not be canceled because they are within the order tolerance ({self.config.order_refresh_tolerance_pct:.2%}).")
            return []

        # Log which orders are being refreshed due to tolerance
        if executors_past_refresh:
            executor_level_ids = [e.custom_info.get("level_id", "unknown") for e in executors_past_refresh]
            tolerance_reason = []
            if not buys_within_tolerance:
                tolerance_reason.append("buy orders outside tolerance")
            if not sells_within_tolerance:
                tolerance_reason.append("sell orders outside tolerance")
            reason = " and ".join(tolerance_reason)
            self.logger().debug(f"Refreshing orders {executor_level_ids} due to {reason} (tolerance: {self.config.order_refresh_tolerance_pct:.2%}).")

        # Otherwise, refresh all executors
        return [
            StopExecutorAction(
                controller_id=self.config.id,
                executor_id=executor.id,
                keep_position=True
            )
            for executor in executors_past_refresh
        ]

    def _is_within_tolerance(
        self, current_prices: List[Decimal], proposal_prices: List[Decimal]
    ) -> bool:
        """Check if current prices are within tolerance of proposal prices.

        Matching legacy c_is_within_tolerance behavior.
        """
        if len(current_prices) != len(proposal_prices):
            return False

        if not current_prices:
            return True

        current_sorted = sorted(current_prices)
        proposal_sorted = sorted(proposal_prices)

        for current, proposal in zip(current_sorted, proposal_sorted):
            if current == 0:
                return False
            diff_pct = abs(proposal - current) / current
            if diff_pct > self.config.order_refresh_tolerance_pct:
                return False

        return True

    def _get_executor_config(
        self, level_id: str, price: Decimal, amount: Decimal, trade_type: TradeType
    ) -> Optional[OrderExecutorConfig]:
        """Create executor config for a level (simple limit order like legacy PMM)."""
        return OrderExecutorConfig(
            timestamp=self.market_data_provider.time(),
            connector_name=self.config.connector_name,
            trading_pair=self.config.trading_pair,
            side=trade_type,
            amount=amount,
            execution_strategy=ExecutionStrategy.LIMIT,
            price=price,
            level_id=level_id,
        )

    def get_level_id_from_side(self, trade_type: TradeType, level: int) -> str:
        """Get level ID from trade type and level number."""
        return f"{trade_type.name.lower()}_{level}"

    def get_trade_type_from_level_id(self, level_id: str) -> TradeType:
        """Get trade type from level ID."""
        return TradeType.BUY if level_id.startswith("buy") else TradeType.SELL

    def get_level_from_level_id(self, level_id: str) -> int:
        """Get level number from level ID."""
        if "_" not in level_id:
            return 0
        return int(level_id.split('_')[1])

    def to_format_status(self) -> List[str]:
        """Get formatted status display."""
        from itertools import zip_longest

        status = []

        # Get data
        base_pct = self.processed_data.get('current_base_pct', Decimal('0'))
        target_pct = self.config.target_base_pct
        buy_skew = self.processed_data.get('buy_skew', Decimal('1'))
        sell_skew = self.processed_data.get('sell_skew', Decimal('1'))
        ref_price = self.processed_data.get('reference_price', Decimal('0'))
        ceiling = self.processed_data.get('price_ceiling')
        floor = self.processed_data.get('price_floor')

        active_buy = sum(1 for e in self.executors_info
                         if e.is_active and e.custom_info.get("level_id", "").startswith("buy"))
        active_sell = sum(1 for e in self.executors_info
                          if e.is_active and e.custom_info.get("level_id", "").startswith("sell"))

        # Layout
        w = 89  # total width including outer pipes
        hw = (w - 3) // 2  # half width for two-column rows (minus 3 for "| " + "|" + " |")

        def sep(char="-"):
            return char * w

        def row2(left, right):
            return f"| {left:<{hw}}| {right:<{hw}}|"

        def row1(content):
            return f"| {content:<{w - 4}} |"

        # Header
        status.append(sep("="))
        header = f"PMM V1 | {self.config.connector_name}:{self.config.trading_pair}"
        status.append(f"|{header:^{w - 2}}|")
        status.append(sep("="))

        # Inventory & Settings
        status.append(row2("INVENTORY", "SETTINGS"))
        status.append(sep())
        inv = [
            f"Base %: {base_pct:.2%} (target {target_pct:.2%})",
            f"Buy Skew: {buy_skew:.2f}x | Sell Skew: {sell_skew:.2f}x",
        ]
        settings = [
            f"Order Amount: {self.config.order_amount} base",
            f"Spreads B: {self.config.buy_spreads} S: {self.config.sell_spreads}",
        ]
        for left, right in zip_longest(inv, settings, fillvalue=""):
            status.append(row2(left, right))

        # Market & Price Bands
        status.append(sep())
        status.append(row2("MARKET", "PRICE BANDS"))
        status.append(sep())
        ceiling_str = f"{ceiling:.8g}" if ceiling else "None"
        floor_str = f"{floor:.8g}" if floor else "None"
        market = [
            f"Ref Price: {ref_price:.8g}",
            f"Active: Buy={active_buy} Sell={active_sell}",
        ]
        bands = [
            f"Ceiling: {ceiling_str}",
            f"Floor: {floor_str}",
        ]
        for left, right in zip_longest(market, bands, fillvalue=""):
            status.append(row2(left, right))

        # Inventory bar
        status.append(sep())
        bar_width = w - 17  # account for "| Inventory: [" + "] |"
        filled = int(float(base_pct) * bar_width)
        target_pos = int(float(target_pct) * bar_width)
        bar = ""
        for i in range(bar_width):
            if i == filled:
                bar += "X"
            elif i == target_pos:
                bar += ":"
            elif i < filled:
                bar += "#"
            else:
                bar += "."
        status.append(f"| Inventory: [{bar}] |")
        status.append(sep("="))

        return status
