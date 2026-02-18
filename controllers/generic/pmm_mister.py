from decimal import Decimal
from typing import Dict, List, Optional, Set, Tuple, Union

from pydantic import Field, field_validator
from pydantic_core.core_schema import ValidationInfo

from hummingbot.core.data_type.common import MarketDict, OrderType, PositionMode, PriceType, TradeType
from hummingbot.strategy_v2.controllers.controller_base import ControllerBase, ControllerConfigBase
from hummingbot.strategy_v2.executors.data_types import ConnectorPair
from hummingbot.strategy_v2.executors.position_executor.data_types import PositionExecutorConfig, TripleBarrierConfig
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, ExecutorAction, StopExecutorAction
from hummingbot.strategy_v2.utils.common import parse_comma_separated_list, parse_enum_value


class PMMisterConfig(ControllerConfigBase):
    """
    Advanced PMM (Pure Market Making) controller with sophisticated position management.
    Features hanging executors, price distance requirements, and breakeven awareness.
    """
    controller_type: str = "generic"
    controller_name: str = "pmm_mister"
    connector_name: str = Field(default="binance")
    trading_pair: str = Field(default="BTC-FDUSD")
    portfolio_allocation: Decimal = Field(default=Decimal("0.1"), json_schema_extra={"is_updatable": True})
    target_base_pct: Decimal = Field(default=Decimal("0.5"), json_schema_extra={"is_updatable": True})
    min_base_pct: Decimal = Field(default=Decimal("0.3"), json_schema_extra={"is_updatable": True})
    max_base_pct: Decimal = Field(default=Decimal("0.7"), json_schema_extra={"is_updatable": True})
    buy_spreads: List[float] = Field(default="0.0005", json_schema_extra={"is_updatable": True})
    sell_spreads: List[float] = Field(default="0.0005", json_schema_extra={"is_updatable": True})
    buy_amounts_pct: Union[List[Decimal], None] = Field(default="1", json_schema_extra={"is_updatable": True})
    sell_amounts_pct: Union[List[Decimal], None] = Field(default="1", json_schema_extra={"is_updatable": True})
    executor_refresh_time: int = Field(default=30, json_schema_extra={"is_updatable": True})

    # Enhanced timing parameters
    buy_cooldown_time: int = Field(default=60, json_schema_extra={"is_updatable": True})
    sell_cooldown_time: int = Field(default=60, json_schema_extra={"is_updatable": True})
    buy_position_effectivization_time: int = Field(default=120, json_schema_extra={"is_updatable": True})
    sell_position_effectivization_time: int = Field(default=120, json_schema_extra={"is_updatable": True})

    # Price distance requirements
    min_buy_price_distance_pct: Decimal = Field(default=Decimal("0.005"), json_schema_extra={"is_updatable": True})
    min_sell_price_distance_pct: Decimal = Field(default=Decimal("0.005"), json_schema_extra={"is_updatable": True})

    leverage: int = Field(default=20, json_schema_extra={"is_updatable": True})
    position_mode: PositionMode = Field(default="HEDGE")
    take_profit: Optional[Decimal] = Field(default=Decimal("0.0001"), gt=0, json_schema_extra={"is_updatable": True})
    take_profit_order_type: Optional[OrderType] = Field(default="LIMIT_MAKER", json_schema_extra={"is_updatable": True})
    open_order_type: Optional[OrderType] = Field(default="LIMIT_MAKER", json_schema_extra={"is_updatable": True})
    max_active_executors_by_level: Optional[int] = Field(default=4, json_schema_extra={"is_updatable": True})
    tick_mode: bool = Field(default=False, json_schema_extra={"is_updatable": True})
    position_profit_protection: bool = Field(default=False, json_schema_extra={"is_updatable": True})
    min_skew: Decimal = Field(default=Decimal("1.0"), json_schema_extra={"is_updatable": True})
    global_take_profit: Decimal = Field(default=Decimal("0.03"), json_schema_extra={"is_updatable": True})
    global_stop_loss: Decimal = Field(default=Decimal("0.05"), json_schema_extra={"is_updatable": True})

    @field_validator("take_profit", mode="before")
    @classmethod
    def validate_target(cls, v):
        if isinstance(v, str):
            if v == "":
                return None
            return Decimal(v)
        return v

    @field_validator('take_profit_order_type', mode="before")
    @classmethod
    def validate_order_type(cls, v) -> OrderType:
        if v is None:
            return OrderType.MARKET
        return parse_enum_value(OrderType, v, "take_profit_order_type")

    @field_validator('open_order_type', mode="before")
    @classmethod
    def validate_open_order_type(cls, v) -> OrderType:
        if v is None:
            return OrderType.MARKET
        return parse_enum_value(OrderType, v, "open_order_type")

    @field_validator('buy_spreads', 'sell_spreads', mode="before")
    @classmethod
    def parse_spreads(cls, v):
        return parse_comma_separated_list(v, "spreads")

    @field_validator('buy_amounts_pct', 'sell_amounts_pct', mode="before")
    @classmethod
    def parse_and_validate_amounts(cls, v, validation_info: ValidationInfo):
        field_name = validation_info.field_name
        if v is None or v == "":
            spread_field = field_name.replace('amounts_pct', 'spreads')
            return [1 for _ in validation_info.data[spread_field]]
        parsed = parse_comma_separated_list(v, field_name)
        if isinstance(parsed, list) and len(parsed) != len(validation_info.data[field_name.replace('amounts_pct', 'spreads')]):
            raise ValueError(
                f"The number of {field_name} must match the number of {field_name.replace('amounts_pct', 'spreads')}.")
        return parsed

    @field_validator('position_mode', mode="before")
    @classmethod
    def validate_position_mode(cls, v) -> PositionMode:
        return parse_enum_value(PositionMode, v, "position_mode")

    @property
    def triple_barrier_config(self) -> TripleBarrierConfig:
        return TripleBarrierConfig(
            take_profit=self.take_profit,
            trailing_stop=None,
            open_order_type=self.open_order_type,
            take_profit_order_type=self.take_profit_order_type,
            stop_loss_order_type=OrderType.MARKET,
            time_limit_order_type=OrderType.MARKET
        )

    def get_cooldown_time(self, trade_type: TradeType) -> int:
        """Get cooldown time for specific trade type"""
        return self.buy_cooldown_time if trade_type == TradeType.BUY else self.sell_cooldown_time

    def get_position_effectivization_time(self, trade_type: TradeType) -> int:
        """Get position effectivization time for specific trade type"""
        return self.buy_position_effectivization_time if trade_type == TradeType.BUY else self.sell_position_effectivization_time

    def update_parameters(self, trade_type: TradeType, new_spreads: Union[List[float], str],
                          new_amounts_pct: Optional[Union[List[int], str]] = None):
        spreads_field = 'buy_spreads' if trade_type == TradeType.BUY else 'sell_spreads'
        amounts_pct_field = 'buy_amounts_pct' if trade_type == TradeType.BUY else 'sell_amounts_pct'

        setattr(self, spreads_field, self.parse_spreads(new_spreads))
        if new_amounts_pct is not None:
            setattr(self, amounts_pct_field,
                    self.parse_and_validate_amounts(new_amounts_pct, self.__dict__, self.__fields__[amounts_pct_field]))
        else:
            setattr(self, amounts_pct_field, [1 for _ in getattr(self, spreads_field)])

    def get_spreads_and_amounts_in_quote(self, trade_type: TradeType) -> Tuple[List[float], List[float]]:
        buy_amounts_pct = getattr(self, 'buy_amounts_pct')
        sell_amounts_pct = getattr(self, 'sell_amounts_pct')

        total_pct = sum(buy_amounts_pct) + sum(sell_amounts_pct)

        if trade_type == TradeType.BUY:
            normalized_amounts_pct = [amt_pct / total_pct for amt_pct in buy_amounts_pct]
        else:
            normalized_amounts_pct = [amt_pct / total_pct for amt_pct in sell_amounts_pct]

        spreads = getattr(self, f'{trade_type.name.lower()}_spreads')
        return spreads, [amt_pct * self.total_amount_quote * self.portfolio_allocation for amt_pct in normalized_amounts_pct]

    def update_markets(self, markets: MarketDict) -> MarketDict:
        return markets.add_or_update(self.connector_name, self.trading_pair)


class PMMister(ControllerBase):
    """
    Advanced PMM (Pure Market Making) controller with sophisticated position management.
    Features:
    - Hanging executors system for better position control
    - Price distance requirements to prevent over-accumulation
    - Breakeven awareness for dynamic parameter adjustment
    - Separate buy/sell cooldown and effectivization times
    """

    def __init__(self, config: PMMisterConfig, *args, **kwargs):
        super().__init__(config, *args, **kwargs)
        self.config = config
        self.market_data_provider.initialize_rate_sources(
            [ConnectorPair(connector_name=config.connector_name, trading_pair=config.trading_pair)]
        )
        # Price history for visualization (last 60 price points)
        self.price_history = []
        self.max_price_history = 60
        # Order history for visualization
        self.order_history = []
        self.max_order_history = 20
        # Initialize processed_data to prevent access errors
        self.processed_data = {}

    def determine_executor_actions(self) -> List[ExecutorAction]:
        """
        Determine actions based on the current state with advanced position management.
        """
        actions = []

        # Create new executors
        actions.extend(self.create_actions_proposal())

        # Stop executors (refresh and early stop)
        actions.extend(self.stop_actions_proposal())

        return actions

    def should_effectivize_executor(self, executor_info, current_time: int) -> bool:
        """Check if a hanging executor should be effectivized"""
        level_id = executor_info.custom_info.get("level_id", "")
        fill_time = executor_info.custom_info["open_order_last_update"]
        if not level_id or not fill_time:
            return False

        trade_type = self.get_trade_type_from_level_id(level_id)
        effectivization_time = self.config.get_position_effectivization_time(trade_type)

        return current_time - fill_time >= effectivization_time

    def create_actions_proposal(self) -> List[ExecutorAction]:
        """
        Create actions proposal with advanced position management logic.
        """
        create_actions = []

        # Get levels to execute with advanced logic
        levels_to_execute = self.get_levels_to_execute()

        # Pre-calculate spreads and amounts
        buy_spreads, buy_amounts_quote = self.config.get_spreads_and_amounts_in_quote(TradeType.BUY)
        sell_spreads, sell_amounts_quote = self.config.get_spreads_and_amounts_in_quote(TradeType.SELL)
        reference_price = Decimal(self.processed_data["reference_price"])

        # Use pre-calculated skew factors from processed_data
        buy_skew = self.processed_data["buy_skew"]
        sell_skew = self.processed_data["sell_skew"]

        # Create executors for each level
        for level_id in levels_to_execute:
            trade_type = self.get_trade_type_from_level_id(level_id)
            level = self.get_level_from_level_id(level_id)

            if trade_type == TradeType.BUY:
                spread_in_pct = Decimal(buy_spreads[level]) * Decimal(self.processed_data["spread_multiplier"])
                amount_quote = Decimal(buy_amounts_quote[level])
            else:
                spread_in_pct = Decimal(sell_spreads[level]) * Decimal(self.processed_data["spread_multiplier"])
                amount_quote = Decimal(sell_amounts_quote[level])

            # Apply skew to amount calculation
            skew = buy_skew if trade_type == TradeType.BUY else sell_skew

            # Calculate price and amount
            side_multiplier = Decimal("-1") if trade_type == TradeType.BUY else Decimal("1")
            price = reference_price * (Decimal("1") + side_multiplier * spread_in_pct)
            amount = self.market_data_provider.quantize_order_amount(
                self.config.connector_name,
                self.config.trading_pair,
                (amount_quote / price) * skew
            )

            if amount == Decimal("0"):
                self.logger().warning(f"The amount of the level {level_id} is 0. Skipping.")
                continue

            # Position profit protection: don't place sell orders below breakeven
            if self.config.position_profit_protection and trade_type == TradeType.SELL:
                breakeven_price = self.processed_data.get("breakeven_price")
                if breakeven_price is not None and breakeven_price > 0 and price < breakeven_price:
                    continue

            executor_config = self.get_executor_config(level_id, price, amount)
            if executor_config is not None:
                # Track order creation for visualization
                self.order_history.append({
                    'timestamp': self.market_data_provider.time(),
                    'price': price,
                    'side': trade_type.name,
                    'level_id': level_id,
                    'action': 'CREATE'
                })
                if len(self.order_history) > self.max_order_history:
                    self.order_history.pop(0)

                create_actions.append(CreateExecutorAction(
                    controller_id=self.config.id,
                    executor_config=executor_config
                ))

        return create_actions

    def get_levels_to_execute(self) -> List[str]:
        """
        Get levels to execute with advanced hanging executor logic using the analyzer.
        """
        current_time = self.market_data_provider.time()

        # Analyze all levels to understand executor states
        all_levels_analysis = self.analyze_all_levels()

        # Get working levels (active or hanging with cooldown)
        working_levels_ids = []

        for analysis in all_levels_analysis:
            level_id = analysis["level_id"]
            trade_type = self.get_trade_type_from_level_id(level_id)
            is_buy = level_id.startswith("buy")
            current_price = Decimal(self.processed_data["reference_price"])

            # Evaluate each condition separately for debugging
            has_active_not_trading = len(analysis["active_executors_not_trading"]) > 0
            has_too_many_executors = analysis["total_active_executors"] >= self.config.max_active_executors_by_level

            # Check cooldown condition
            has_active_cooldown = False
            if analysis["open_order_last_update"]:
                cooldown_time = self.config.get_cooldown_time(trade_type)
                has_active_cooldown = current_time - analysis["open_order_last_update"] < cooldown_time

            # Enhanced price distance logic
            price_distance_violated = False
            if is_buy and analysis["max_price"]:
                # For buy orders, ensure they're not too close to current price
                distance_from_current = (current_price - analysis["max_price"]) / current_price
                if distance_from_current < self.config.min_buy_price_distance_pct:
                    price_distance_violated = True
            elif not is_buy and analysis["min_price"]:
                # For sell orders, ensure they're not too close to current price
                distance_from_current = (analysis["min_price"] - current_price) / current_price
                if distance_from_current < self.config.min_sell_price_distance_pct:
                    price_distance_violated = True

            # Level is working if any condition is true
            if (has_active_not_trading or
                has_too_many_executors or
                has_active_cooldown or
                    price_distance_violated):
                working_levels_ids.append(level_id)
                continue
        return self.get_not_active_levels_ids(working_levels_ids)

    def stop_actions_proposal(self) -> List[ExecutorAction]:
        """
        Create stop actions with enhanced refresh logic.
        """
        stop_actions = []
        stop_actions.extend(self.executors_to_refresh())
        stop_actions.extend(self.process_hanging_executors())
        return stop_actions

    def executors_to_refresh(self) -> List[ExecutorAction]:
        """Refresh executors that have been active too long"""
        executors_to_refresh = self.filter_executors(
            executors=self.executors_info,
            filter_func=lambda x: (
                not x.is_trading and x.is_active and
                self.market_data_provider.time() - x.timestamp > self.config.executor_refresh_time
            )
        )
        return [StopExecutorAction(
            controller_id=self.config.id,
            keep_position=True,
            executor_id=executor.id
        ) for executor in executors_to_refresh]

    def process_hanging_executors(self) -> List[ExecutorAction]:
        """Process hanging executors and effectivize them when appropriate"""
        current_time = self.market_data_provider.time()
        # Find hanging executors that should be effectivized (only is_trading)
        executors_to_effectivize = self.filter_executors(
            executors=self.executors_info,
            filter_func=lambda x: x.is_trading and self.should_effectivize_executor(x, current_time)
        )

        # Create actions for effectivization (keep position)
        effectivize_actions = [StopExecutorAction(
            controller_id=self.config.id,
            keep_position=True,
            executor_id=executor.id
        ) for executor in executors_to_effectivize]

        return effectivize_actions

    async def update_processed_data(self):
        """
        Update processed data with enhanced condition tracking and analysis.
        """
        current_time = self.market_data_provider.time()

        # Safely get reference price with fallback
        try:
            reference_price = self.market_data_provider.get_price_by_type(
                self.config.connector_name, self.config.trading_pair, PriceType.MidPrice
            )
            if reference_price is None or reference_price <= 0:
                self.logger().warning("Invalid reference price received, using previous price if available")
                reference_price = self.processed_data.get("reference_price", Decimal("100"))  # Default fallback
        except Exception as e:
            self.logger().warning(f"Error getting reference price: {e}, using previous price if available")
            reference_price = self.processed_data.get("reference_price", Decimal("100"))  # Default fallback

        # Update price history for visualization
        self.price_history.append({
            'timestamp': current_time,
            'price': Decimal(reference_price)
        })
        if len(self.price_history) > self.max_price_history:
            self.price_history.pop(0)

        position_held = next((position for position in self.positions_held if
                              (position.trading_pair == self.config.trading_pair) &
                              (position.connector_name == self.config.connector_name)), None)

        target_position = self.config.total_amount_quote * self.config.target_base_pct

        if position_held is not None:
            position_amount = position_held.amount
            current_base_pct = position_held.amount_quote / self.config.total_amount_quote
            deviation = (target_position - position_held.amount_quote) / target_position
            unrealized_pnl_pct = position_held.unrealized_pnl_quote / position_held.amount_quote if position_held.amount_quote != 0 else Decimal(
                "0")
            breakeven_price = position_held.breakeven_price
        else:
            position_amount = 0
            current_base_pct = 0
            deviation = 1
            unrealized_pnl_pct = 0
            breakeven_price = None

        if self.config.tick_mode:
            spread_multiplier = (self.market_data_provider.get_trading_rules(self.config.connector_name,
                                                                             self.config.trading_pair).min_price_increment / reference_price)
        else:
            spread_multiplier = Decimal("1")

        # Calculate skew factors for position balancing
        min_pct = self.config.min_base_pct
        max_pct = self.config.max_base_pct

        if max_pct > min_pct:
            # Calculate skew factors based on position deviation
            buy_skew = (max_pct - current_base_pct) / (max_pct - min_pct)
            sell_skew = (current_base_pct - min_pct) / (max_pct - min_pct)
            # Apply minimum skew to prevent orders from becoming too small
            buy_skew = max(min(buy_skew, Decimal("1.0")), self.config.min_skew)
            sell_skew = max(min(sell_skew, Decimal("1.0")), self.config.min_skew)
        else:
            buy_skew = sell_skew = Decimal("1.0")

        # Enhanced condition tracking - only if we have valid data
        cooldown_status = self._calculate_cooldown_status(current_time)
        price_distance_analysis = self._calculate_price_distance_analysis(Decimal(reference_price))
        effectivization_tracking = self._calculate_effectivization_tracking(current_time)
        level_conditions = self._analyze_level_conditions(current_time, Decimal(reference_price))
        executor_stats = self._calculate_executor_statistics(current_time)
        refresh_tracking = self._calculate_refresh_tracking(current_time)

        self.processed_data = {
            "reference_price": Decimal(reference_price),
            "spread_multiplier": spread_multiplier,
            "deviation": deviation,
            "current_base_pct": current_base_pct,
            "unrealized_pnl_pct": unrealized_pnl_pct,
            "position_amount": position_amount,
            "breakeven_price": breakeven_price,
            "buy_skew": buy_skew,
            "sell_skew": sell_skew,
            # Enhanced tracking data
            "cooldown_status": cooldown_status,
            "price_distance_analysis": price_distance_analysis,
            "effectivization_tracking": effectivization_tracking,
            "level_conditions": level_conditions,
            "executor_stats": executor_stats,
            "refresh_tracking": refresh_tracking,
            "current_time": current_time
        }

    def get_executor_config(self, level_id: str, price: Decimal, amount: Decimal):
        """Get executor config for a given level"""
        trade_type = self.get_trade_type_from_level_id(level_id)
        return PositionExecutorConfig(
            timestamp=self.market_data_provider.time(),
            level_id=level_id,
            connector_name=self.config.connector_name,
            trading_pair=self.config.trading_pair,
            entry_price=price,
            amount=amount,
            triple_barrier_config=self.config.triple_barrier_config,
            leverage=self.config.leverage,
            side=trade_type,
        )

    def get_level_id_from_side(self, trade_type: TradeType, level: int) -> str:
        """Get level ID based on trade type and level"""
        return f"{trade_type.name.lower()}_{level}"

    def get_trade_type_from_level_id(self, level_id: str) -> TradeType:
        return TradeType.BUY if level_id.startswith("buy") else TradeType.SELL

    def get_level_from_level_id(self, level_id: str) -> int:
        return int(level_id.split('_')[1])

    def get_not_active_levels_ids(self, active_levels_ids: List[str]) -> List[str]:
        """Get levels that should be executed based on position constraints"""
        buy_ids_missing = [
            self.get_level_id_from_side(TradeType.BUY, level)
            for level in range(len(self.config.buy_spreads))
            if self.get_level_id_from_side(TradeType.BUY, level) not in active_levels_ids
        ]
        sell_ids_missing = [
            self.get_level_id_from_side(TradeType.SELL, level)
            for level in range(len(self.config.sell_spreads))
            if self.get_level_id_from_side(TradeType.SELL, level) not in active_levels_ids
        ]

        current_pct = self.processed_data["current_base_pct"]

        if current_pct < self.config.min_base_pct:
            return buy_ids_missing
        elif current_pct > self.config.max_base_pct:
            return sell_ids_missing

        # Position profit protection: filter based on breakeven
        if self.config.position_profit_protection:
            breakeven_price = self.processed_data.get("breakeven_price")
            reference_price = self.processed_data["reference_price"]
            target_pct = self.config.target_base_pct

            if breakeven_price is not None and breakeven_price > 0:
                if current_pct < target_pct and reference_price < breakeven_price:
                    return buy_ids_missing  # Don't sell at a loss when underweight
                elif current_pct > target_pct and reference_price > breakeven_price:
                    return sell_ids_missing  # Don't buy more when overweight and in profit

        return buy_ids_missing + sell_ids_missing

    def analyze_all_levels(self) -> List[Dict]:
        """Analyze executors for all levels."""
        level_ids: Set[str] = {e.custom_info.get("level_id") for e in self.executors_info if "level_id" in e.custom_info}
        return [self._analyze_by_level_id(level_id) for level_id in level_ids]

    def _analyze_by_level_id(self, level_id: str) -> Dict:
        """Analyze executors for a specific level ID."""
        # Get active executors for level calculations
        filtered_executors = [e for e in self.executors_info if e.custom_info.get("level_id") == level_id and e.is_active]

        active_not_trading = [e for e in filtered_executors if e.is_active and not e.is_trading]
        active_trading = [e for e in filtered_executors if e.is_active and e.is_trading]

        # For cooldown calculation, include both active and recently completed executors
        all_level_executors = [e for e in self.executors_info if e.custom_info.get("level_id") == level_id]
        open_order_last_updates = [
            e.custom_info.get("open_order_last_update") for e in all_level_executors
            if "open_order_last_update" in e.custom_info and e.custom_info["open_order_last_update"] is not None
        ]
        latest_open_order_update = max(open_order_last_updates) if open_order_last_updates else None

        prices = [e.config.entry_price for e in filtered_executors if hasattr(e.config, 'entry_price')]

        return {
            "level_id": level_id,
            "active_executors_not_trading": active_not_trading,
            "active_executors_trading": active_trading,
            "total_active_executors": len(active_not_trading) + len(active_trading),
            "open_order_last_update": latest_open_order_update,
            "min_price": min(prices) if prices else None,
            "max_price": max(prices) if prices else None,
        }

    def to_format_status(self) -> List[str]:
        """
        Comprehensive real-time trading conditions dashboard.
        """
        from decimal import Decimal
        from itertools import zip_longest

        status = []

        # Layout dimensions - set early for error cases
        outer_width = 170
        inner_width = outer_width - 4

        # Get all required data with safe fallbacks
        if not hasattr(self, 'processed_data') or not self.processed_data:
            # Return minimal status if processed_data is not available
            status.append("╒" + "═" * inner_width + "╕")
            status.append(f"│ {'Initializing controller... please wait':<{inner_width}} │")
            status.append(f"╘{'═' * inner_width}╛")
            return status

        base_pct = self.processed_data.get('current_base_pct', Decimal("0"))
        min_pct = self.config.min_base_pct
        max_pct = self.config.max_base_pct
        target_pct = self.config.target_base_pct
        pnl = self.processed_data.get('unrealized_pnl_pct', Decimal('0'))
        breakeven = self.processed_data.get('breakeven_price')
        current_price = self.processed_data.get('reference_price', Decimal("0"))
        buy_skew = self.processed_data.get('buy_skew', Decimal("1.0"))
        sell_skew = self.processed_data.get('sell_skew', Decimal("1.0"))

        # Enhanced condition data
        cooldown_status = self.processed_data.get('cooldown_status', {})
        effectivization = self.processed_data.get('effectivization_tracking', {})
        level_conditions = self.processed_data.get('level_conditions', {})
        executor_stats = self.processed_data.get('executor_stats', {})
        refresh_tracking = self.processed_data.get('refresh_tracking', {})

        # Layout dimensions already set above

        # Smart column distribution for 5 columns
        col1_width = 28  # Cooldowns
        col2_width = 35  # Price distances
        col3_width = 28  # Effectivization
        col4_width = 25  # Refresh tracking
        col5_width = inner_width - col1_width - col2_width - col3_width - col4_width - 4  # Execution status

        half_width = inner_width // 2 - 1
        bar_width = inner_width - 25

        # Header with enhanced info
        status.append("╒" + "═" * inner_width + "╕")

        header_line = (
            f"{self.config.connector_name}:{self.config.trading_pair} @ {current_price:.2f}  "
            f"Alloc: {self.config.portfolio_allocation:.1%}  "
            f"Spread×{self.processed_data['spread_multiplier']:.3f}  "
            f"Pos Protect: {'ON' if self.config.position_profit_protection else 'OFF'}"
        )
        status.append(f"│ {header_line:<{inner_width}} │")

        # REAL-TIME CONDITIONS DASHBOARD
        status.append(f"├{'─' * inner_width}┤")
        status.append(f"│ {'🔄 REAL-TIME CONDITIONS DASHBOARD':<{inner_width}} │")
        status.append(f"├{'─' * col1_width}┬{'─' * col2_width}┬{'─' * col3_width}┬{'─' * col4_width}┬{'─' * col5_width}┤")
        status.append(f"│ {'COOLDOWNS':<{col1_width}} │ {'PRICE DISTANCES':<{col2_width}} │ {'EFFECTIVIZATION':<{col3_width}} │ {'REFRESH TRACKING':<{col4_width}} │ {'EXECUTION':<{col5_width}} │")
        status.append(f"├{'─' * col1_width}┼{'─' * col2_width}┼{'─' * col3_width}┼{'─' * col4_width}┼{'─' * col5_width}┤")

        # Cooldown information
        buy_cooldown = cooldown_status.get('buy', {})
        sell_cooldown = cooldown_status.get('sell', {})

        cooldown_info = [
            f"BUY: {self._format_cooldown_status(buy_cooldown)}",
            f"SELL: {self._format_cooldown_status(sell_cooldown)}",
            f"Times: {self.config.buy_cooldown_time}/{self.config.sell_cooldown_time}s",
            ""
        ]

        # Calculate actual distances for current levels
        current_buy_distance = ""
        current_sell_distance = ""

        all_levels_analysis = self.analyze_all_levels()
        for analysis in all_levels_analysis:
            level_id = analysis["level_id"]
            is_buy = level_id.startswith("buy")

            if is_buy and analysis["max_price"]:
                distance = (current_price - analysis["max_price"]) / current_price
                current_buy_distance = f"({distance:.3%})"
            elif not is_buy and analysis["min_price"]:
                distance = (analysis["min_price"] - current_price) / current_price
                current_sell_distance = f"({distance:.3%})"

        # Enhanced price info with more details
        buy_violation_marker = " ⚠️" if current_buy_distance and "(0.0" in current_buy_distance else ""
        sell_violation_marker = " ⚠️" if current_sell_distance and "(0.0" in current_sell_distance else ""

        price_info = [
            f"BUY Min: {self.config.min_buy_price_distance_pct:.3%}{buy_violation_marker}",
            f"Current: {current_buy_distance}",
            f"SELL Min: {self.config.min_sell_price_distance_pct:.3%}{sell_violation_marker}",
            f"Current: {current_sell_distance}"
        ]

        # Effectivization information
        total_hanging = effectivization.get('total_hanging', 0)
        ready_count = effectivization.get('ready_for_effectivization', 0)

        effect_info = [
            f"Hanging: {total_hanging}",
            f"Ready: {ready_count}",
            f"Times: {self.config.buy_position_effectivization_time}s/{self.config.sell_position_effectivization_time}s",
            ""
        ]

        # Refresh tracking information
        near_refresh = refresh_tracking.get('near_refresh', 0)
        refresh_ready = refresh_tracking.get('refresh_ready', 0)

        refresh_info = [
            f"Near Refresh: {near_refresh}",
            f"Ready: {refresh_ready}",
            f"Threshold: {self.config.executor_refresh_time}s",
            ""
        ]

        # Execution status
        can_execute_buy = len([level for level in level_conditions.values() if level.get('trade_type') == 'BUY' and level.get('can_execute')])
        can_execute_sell = len([level for level in level_conditions.values() if level.get('trade_type') == 'SELL' and level.get('can_execute')])
        total_buy_levels = len(self.config.buy_spreads)
        total_sell_levels = len(self.config.sell_spreads)

        execution_info = [
            f"BUY: {can_execute_buy}/{total_buy_levels}",
            f"SELL: {can_execute_sell}/{total_sell_levels}",
            f"Active: {executor_stats.get('total_active', 0)}",
            ""
        ]

        # Display conditions in 5 columns
        for cool_line, price_line, effect_line, refresh_line, exec_line in zip_longest(cooldown_info, price_info, effect_info, refresh_info, execution_info, fillvalue=""):
            status.append(f"│ {cool_line:<{col1_width}} │ {price_line:<{col2_width}} │ {effect_line:<{col3_width}} │ {refresh_line:<{col4_width}} │ {exec_line:<{col5_width}} │")

        # LEVEL-BY-LEVEL ANALYSIS
        status.append(f"├{'─' * inner_width}┤")
        status.append(f"│ {'📊 LEVEL-BY-LEVEL ANALYSIS':<{inner_width}} │")
        status.append(f"├{'─' * inner_width}┤")

        # Show level conditions
        status.extend(self._format_level_conditions(level_conditions, inner_width))

        # VISUAL PROGRESS INDICATORS
        status.append(f"├{'─' * inner_width}┤")
        status.append(f"│ {'🔄 VISUAL PROGRESS INDICATORS':<{inner_width}} │")
        status.append(f"├{'─' * inner_width}┤")

        # Cooldown progress bars
        if buy_cooldown.get('active') or sell_cooldown.get('active'):
            status.extend(self._format_cooldown_bars(buy_cooldown, sell_cooldown, bar_width, inner_width))

        # Effectivization progress
        if total_hanging > 0:
            status.extend(self._format_effectivization_bars(effectivization, bar_width, inner_width))

        # Refresh progress bars
        if refresh_tracking.get('refresh_candidates', []):
            status.extend(self._format_refresh_bars(refresh_tracking, bar_width, inner_width))

        # POSITION & PNL DASHBOARD
        status.append(f"├{'─' * half_width}┬{'─' * half_width}┤")
        status.append(f"│ {'📍 POSITION STATUS':<{half_width}} │ {'💰 PROFIT & LOSS':<{half_width}} │")
        status.append(f"├{'─' * half_width}┼{'─' * half_width}┤")

        # Position data with enhanced skew info
        skew = base_pct - target_pct
        skew_pct = skew / target_pct if target_pct != 0 else Decimal('0')
        position_info = [
            f"Current: {base_pct:.2%} (Target: {target_pct:.2%})",
            f"Range: {min_pct:.2%} - {max_pct:.2%}",
            f"Skew: {skew_pct:+.2%} (min {self.config.min_skew:.2%})",
            f"Buy Skew: {buy_skew:.2f} | Sell Skew: {sell_skew:.2f}"
        ]

        # Enhanced PnL data
        breakeven_str = f"{breakeven:.2f}" if breakeven is not None else "N/A"
        pnl_sign = "+" if pnl >= 0 else ""
        distance_to_tp = self.config.global_take_profit - pnl if pnl < self.config.global_take_profit else Decimal('0')
        distance_to_sl = pnl + self.config.global_stop_loss if pnl > -self.config.global_stop_loss else Decimal('0')

        pnl_info = [
            f"Unrealized: {pnl_sign}{pnl:.2%}",
            f"Take Profit: {self.config.global_take_profit:.2%} (Δ{distance_to_tp:.2%})",
            f"Stop Loss: {-self.config.global_stop_loss:.2%} (Δ{distance_to_sl:.2%})",
            f"Breakeven: {breakeven_str}"
        ]

        # Display position and PnL info
        for pos_line, pnl_line in zip_longest(position_info, pnl_info, fillvalue=""):
            status.append(f"│ {pos_line:<{half_width}} │ {pnl_line:<{half_width}} │")

        # Position visualization with enhanced details
        status.append(f"├{'─' * inner_width}┤")
        status.extend(self._format_position_visualization(base_pct, target_pct, min_pct, max_pct, skew_pct, pnl, bar_width, inner_width))

        # Bottom border
        status.append(f"╘{'═' * inner_width}╛")

        return status

    def _is_executor_too_far_from_price(self, executor_info, current_price: Decimal) -> bool:
        """Check if hanging executor is too far from current price and should be stopped"""
        if not hasattr(executor_info.config, 'entry_price'):
            return False

        entry_price = executor_info.config.entry_price
        level_id = executor_info.custom_info.get("level_id", "")

        if not level_id:
            return False

        is_buy = level_id.startswith("buy")

        # Calculate price distance
        if is_buy:
            # For buy orders, stop if they're above current price (inverted)
            if entry_price >= current_price:
                return True
            distance = (current_price - entry_price) / current_price
            max_distance = Decimal("0.05")  # 5% maximum distance
        else:
            # For sell orders, stop if they're below current price
            if entry_price <= current_price:
                return True
            distance = (entry_price - current_price) / current_price
            max_distance = Decimal("0.05")  # 5% maximum distance

        return distance > max_distance

    def _format_cooldown_status(self, cooldown_data: Dict) -> str:
        """Format cooldown status for display"""
        if not cooldown_data.get('active'):
            return "READY ✓"

        remaining = cooldown_data.get('remaining_time', 0)
        progress = cooldown_data.get('progress_pct', Decimal('0'))
        return f"{remaining:.1f}s ({progress:.0%})"

    def _format_level_conditions(self, level_conditions: Dict, inner_width: int) -> List[str]:
        """Format level-by-level conditions analysis"""
        lines = []

        # Group by trade type
        buy_levels = {k: v for k, v in level_conditions.items() if v.get('trade_type') == 'BUY'}
        sell_levels = {k: v for k, v in level_conditions.items() if v.get('trade_type') == 'SELL'}

        if not buy_levels and not sell_levels:
            lines.append(f"│ {'No levels configured':<{inner_width}} │")
            return lines

        # BUY levels analysis
        if buy_levels:
            lines.append(f"│ {'BUY LEVELS:':<{inner_width}} │")
            for level_id, conditions in sorted(buy_levels.items()):
                status_icon = "✓" if conditions.get('can_execute') else "✗"
                blocking = ", ".join(conditions.get('blocking_conditions', []))
                active = conditions.get('active_executors', 0)
                hanging = conditions.get('hanging_executors', 0)

                level_line = f"  {level_id}: {status_icon} Active:{active} Hanging:{hanging}"
                if blocking:
                    level_line += f" | Blocked: {blocking}"

                lines.append(f"│ {level_line:<{inner_width}} │")

        # SELL levels analysis
        if sell_levels:
            lines.append(f"│ {'SELL LEVELS:':<{inner_width}} │")
            for level_id, conditions in sorted(sell_levels.items()):
                status_icon = "✓" if conditions.get('can_execute') else "✗"
                blocking = ", ".join(conditions.get('blocking_conditions', []))
                active = conditions.get('active_executors', 0)
                hanging = conditions.get('hanging_executors', 0)

                level_line = f"  {level_id}: {status_icon} Active:{active} Hanging:{hanging}"
                if blocking:
                    level_line += f" | Blocked: {blocking}"

                lines.append(f"│ {level_line:<{inner_width}} │")

        return lines

    def _format_cooldown_bars(self, buy_cooldown: Dict, sell_cooldown: Dict, bar_width: int, inner_width: int) -> List[str]:
        """Format cooldown progress bars"""
        lines = []

        if buy_cooldown.get('active'):
            progress = float(buy_cooldown.get('progress_pct', 0))
            remaining = buy_cooldown.get('remaining_time', 0)
            bar = self._create_progress_bar(progress, bar_width // 2)  # Same size as other bars
            lines.append(f"│ BUY Cooldown:   [{bar}] {remaining:.1f}s remaining │")

        if sell_cooldown.get('active'):
            progress = float(sell_cooldown.get('progress_pct', 0))
            remaining = sell_cooldown.get('remaining_time', 0)
            bar = self._create_progress_bar(progress, bar_width // 2)  # Same size as other bars
            lines.append(f"│ SELL Cooldown:  [{bar}] {remaining:.1f}s remaining │")

        return lines

    def _format_effectivization_bars(self, effectivization: Dict, bar_width: int, inner_width: int) -> List[str]:
        """Format effectivization progress bars"""
        lines = []

        hanging_executors = effectivization.get('hanging_executors', [])
        if not hanging_executors:
            return lines

        lines.append(f"│ {'EFFECTIVIZATION PROGRESS:':<{inner_width}} │")

        # Show up to 5 hanging executors with progress
        for executor in hanging_executors[:5]:
            level_id = executor.get('level_id', 'unknown')
            trade_type = executor.get('trade_type', 'UNKNOWN')
            progress = float(executor.get('progress_pct', 0))
            remaining = executor.get('remaining_time', 0)
            ready = executor.get('ready', False)

            bar = self._create_progress_bar(progress, bar_width // 2)
            status = "READY!" if ready else f"{remaining}s"
            icon = "🔄" if not ready else "✓"

            lines.append(f"│ {icon} {level_id} ({trade_type}): [{bar}] {status:<10} │")

        if len(hanging_executors) > 5:
            lines.append(f"│ {'... and ' + str(len(hanging_executors) - 5) + ' more':<{inner_width}} │")

        return lines

    def _format_position_visualization(self, base_pct: Decimal, target_pct: Decimal, min_pct: Decimal,
                                       max_pct: Decimal, skew_pct: Decimal, pnl: Decimal,
                                       bar_width: int, inner_width: int) -> List[str]:
        """Format enhanced position visualization"""
        lines = []

        # Position bar
        filled_width = int(float(base_pct) * bar_width)
        min_pos = int(float(min_pct) * bar_width)
        max_pos = int(float(max_pct) * bar_width)
        target_pos = int(float(target_pct) * bar_width)

        position_bar = ""
        for i in range(bar_width):
            if i == filled_width:
                position_bar += "◆"  # Current position marker
            elif i == target_pos:
                position_bar += "┇"  # Target line
            elif i == min_pos:
                position_bar += "┃"  # Min threshold
            elif i == max_pos:
                position_bar += "┃"  # Max threshold
            elif i < filled_width:
                position_bar += "█"  # Filled area
            else:
                position_bar += "░"  # Empty area

        lines.append(f"│ Position:   [{position_bar}] {base_pct:.2%} │")

        # Skew visualization
        center = bar_width // 2
        skew_pos = center + int(float(skew_pct) * center)
        skew_pos = max(0, min(bar_width - 1, skew_pos))

        skew_bar = ""
        for i in range(bar_width):
            if i == center:
                skew_bar += "┃"  # Center line (neutral)
            elif i == skew_pos:
                skew_bar += "⬤"  # Current skew position
            else:
                skew_bar += "─"

        skew_direction = "BULLISH" if skew_pct > 0 else "BEARISH" if skew_pct < 0 else "NEUTRAL"
        lines.append(f"│ Skew:       [{skew_bar}] {skew_direction} │")

        # PnL visualization with dynamic scaling
        max_range = max(abs(self.config.global_take_profit), abs(self.config.global_stop_loss), abs(pnl)) * Decimal("1.2")
        if max_range > 0:
            scale = (bar_width // 2) / float(max_range)
            pnl_pos = center + int(float(pnl) * scale)
            take_profit_pos = center + int(float(self.config.global_take_profit) * scale)
            stop_loss_pos = center + int(float(-self.config.global_stop_loss) * scale)

            pnl_pos = max(0, min(bar_width - 1, pnl_pos))
            take_profit_pos = max(0, min(bar_width - 1, take_profit_pos))
            stop_loss_pos = max(0, min(bar_width - 1, stop_loss_pos))

            pnl_bar = ""
            for i in range(bar_width):
                if i == center:
                    pnl_bar += "│"  # Zero line
                elif i == pnl_pos:
                    pnl_bar += "⬤"  # Current PnL
                elif i == take_profit_pos:
                    pnl_bar += "T"  # Take profit target
                elif i == stop_loss_pos:
                    pnl_bar += "S"  # Stop loss target
                elif ((pnl >= 0 and center <= i < pnl_pos) or
                      (pnl < 0 and pnl_pos < i <= center)):
                    pnl_bar += "█" if pnl >= 0 else "▓"  # Fill to current PnL
                else:
                    pnl_bar += "─"
        else:
            pnl_bar = "─" * bar_width

        pnl_status = "PROFIT" if pnl > 0 else "LOSS" if pnl < 0 else "BREAK-EVEN"
        lines.append(f"│ PnL:        [{pnl_bar}] {pnl_status} │")

        return lines

    def _create_progress_bar(self, progress: float, width: int) -> str:
        """Create a progress bar string"""
        progress = max(0, min(1, progress))  # Clamp between 0 and 1
        filled = int(progress * width)

        bar = ""
        for i in range(width):
            if i < filled:
                bar += "█"  # Filled
            elif i == filled and filled < width:
                bar += "▌"  # Partial fill
            else:
                bar += "░"  # Empty

        return bar

    def _calculate_cooldown_status(self, current_time: int) -> Dict:
        """Calculate cooldown status for buy and sell sides"""
        cooldown_status = {
            "buy": {"active": False, "remaining_time": 0, "progress_pct": Decimal("0")},
            "sell": {"active": False, "remaining_time": 0, "progress_pct": Decimal("0")}
        }

        # Get latest order timestamps for each trade type
        buy_executors = [e for e in self.executors_info if e.custom_info.get("level_id", "").startswith("buy")]
        sell_executors = [e for e in self.executors_info if e.custom_info.get("level_id", "").startswith("sell")]

        for trade_type, executors in [("buy", buy_executors), ("sell", sell_executors)]:
            if not executors:
                continue

            # Find most recent open order update
            latest_updates = [
                e.custom_info.get("open_order_last_update") for e in executors
                if "open_order_last_update" in e.custom_info and e.custom_info["open_order_last_update"] is not None
            ]

            if not latest_updates:
                continue

            latest_update = max(latest_updates)
            cooldown_time = (self.config.buy_cooldown_time if trade_type == "buy"
                             else self.config.sell_cooldown_time)

            time_since_update = current_time - latest_update
            remaining_time = max(0, cooldown_time - time_since_update)

            if remaining_time > 0:
                cooldown_status[trade_type]["active"] = True
                cooldown_status[trade_type]["remaining_time"] = remaining_time
                cooldown_status[trade_type]["progress_pct"] = Decimal(str(time_since_update)) / Decimal(str(cooldown_time))
            else:
                cooldown_status[trade_type]["progress_pct"] = Decimal("1")

        return cooldown_status

    def _calculate_price_distance_analysis(self, reference_price: Decimal) -> Dict:
        """Analyze price distance conditions for all levels"""
        price_analysis = {
            "buy": {"violations": [], "distances": [], "min_required": self.config.min_buy_price_distance_pct},
            "sell": {"violations": [], "distances": [], "min_required": self.config.min_sell_price_distance_pct}
        }

        # Analyze all levels for price distance violations
        all_levels_analysis = self.analyze_all_levels()

        for analysis in all_levels_analysis:
            level_id = analysis["level_id"]
            is_buy = level_id.startswith("buy")

            if is_buy and analysis["max_price"]:
                current_distance = (reference_price - analysis["max_price"]) / reference_price
                min_required = self.config.min_buy_price_distance_pct

                price_analysis["buy"]["distances"].append({
                    "level_id": level_id,
                    "current_distance": current_distance,
                    "distance_pct": current_distance,
                    "violates": current_distance < min_required
                })

                if current_distance < min_required:
                    price_analysis["buy"]["violations"].append(level_id)

            elif not is_buy and analysis["min_price"]:
                current_distance = (analysis["min_price"] - reference_price) / reference_price
                min_required = self.config.min_sell_price_distance_pct

                price_analysis["sell"]["distances"].append({
                    "level_id": level_id,
                    "current_distance": current_distance,
                    "distance_pct": current_distance,
                    "violates": current_distance < min_required
                })

                if current_distance < min_required:
                    price_analysis["sell"]["violations"].append(level_id)

        return price_analysis

    def _calculate_effectivization_tracking(self, current_time: int) -> Dict:
        """Track hanging executor effectivization progress"""
        effectivization_data = {
            "hanging_executors": [],
            "total_hanging": 0,
            "ready_for_effectivization": 0
        }

        hanging_executors = [e for e in self.executors_info if e.is_active and e.is_trading]
        effectivization_data["total_hanging"] = len(hanging_executors)

        for executor in hanging_executors:
            level_id = executor.custom_info.get("level_id", "")
            if not level_id:
                continue

            trade_type = self.get_trade_type_from_level_id(level_id)
            effectivization_time = self.config.get_position_effectivization_time(trade_type)
            fill_time = executor.custom_info.get("open_order_last_update", current_time)

            time_elapsed = current_time - fill_time
            remaining_time = max(0, effectivization_time - time_elapsed)
            progress_pct = min(Decimal("1"), Decimal(str(time_elapsed)) / Decimal(str(effectivization_time)))

            ready = remaining_time == 0
            if ready:
                effectivization_data["ready_for_effectivization"] += 1

            effectivization_data["hanging_executors"].append({
                "level_id": level_id,
                "trade_type": trade_type.name,
                "time_elapsed": time_elapsed,
                "remaining_time": remaining_time,
                "progress_pct": progress_pct,
                "ready": ready,
                "executor_id": executor.id
            })

        return effectivization_data

    def _analyze_level_conditions(self, current_time: int, reference_price: Decimal) -> Dict:
        """Analyze conditions preventing each level from executing"""
        level_conditions = {}

        # Get all possible levels
        all_buy_levels = [self.get_level_id_from_side(TradeType.BUY, i) for i in range(len(self.config.buy_spreads))]
        all_sell_levels = [self.get_level_id_from_side(TradeType.SELL, i) for i in range(len(self.config.sell_spreads))]
        all_levels = all_buy_levels + all_sell_levels

        # Cache level analysis to avoid redundant calculations
        level_analysis_cache = {}
        for level_id in all_levels:
            level_analysis_cache[level_id] = self._analyze_by_level_id(level_id)

        # Pre-calculate position constraints with safe defaults
        if hasattr(self, 'processed_data') and self.processed_data:
            current_pct = self.processed_data.get("current_base_pct", Decimal("0"))
            breakeven_price = self.processed_data.get("breakeven_price")
        else:
            current_pct = Decimal("0")
            breakeven_price = None

        below_min_position = current_pct < self.config.min_base_pct
        above_max_position = current_pct > self.config.max_base_pct

        # Analyze each level
        for level_id in all_levels:
            trade_type = self.get_trade_type_from_level_id(level_id)
            is_buy = level_id.startswith("buy")

            conditions = {
                "level_id": level_id,
                "trade_type": trade_type.name,
                "can_execute": True,
                "blocking_conditions": [],
                "active_executors": 0,
                "hanging_executors": 0
            }

            # Get cached level analysis
            level_analysis = level_analysis_cache[level_id]

            # Check various blocking conditions
            # 1. Active executor limit
            if level_analysis["total_active_executors"] >= self.config.max_active_executors_by_level:
                conditions["blocking_conditions"].append("max_active_executors_reached")
                conditions["can_execute"] = False

            # 2. Cooldown check
            cooldown_time = self.config.get_cooldown_time(trade_type)
            if level_analysis["open_order_last_update"]:
                time_since_update = current_time - level_analysis["open_order_last_update"]
                if time_since_update < cooldown_time:
                    conditions["blocking_conditions"].append("cooldown_active")
                    conditions["can_execute"] = False

            # 3. Price distance check
            if is_buy and level_analysis["max_price"]:
                distance = (reference_price - level_analysis["max_price"]) / reference_price
                if distance < self.config.min_buy_price_distance_pct:
                    conditions["blocking_conditions"].append("price_distance_violation")
                    conditions["can_execute"] = False
            elif not is_buy and level_analysis["min_price"]:
                distance = (level_analysis["min_price"] - reference_price) / reference_price
                if distance < self.config.min_sell_price_distance_pct:
                    conditions["blocking_conditions"].append("price_distance_violation")
                    conditions["can_execute"] = False

            # 4. Position constraints
            if below_min_position and not is_buy:
                conditions["blocking_conditions"].append("below_min_position")
                conditions["can_execute"] = False
            elif above_max_position and is_buy:
                conditions["blocking_conditions"].append("above_max_position")
                conditions["can_execute"] = False

            # 5. Position profit protection
            if (self.config.position_profit_protection and not is_buy and
                    breakeven_price and breakeven_price > 0 and reference_price < breakeven_price):
                conditions["blocking_conditions"].append("position_profit_protection")
                conditions["can_execute"] = False

            conditions["active_executors"] = len(level_analysis["active_executors_not_trading"])
            conditions["hanging_executors"] = len(level_analysis["active_executors_trading"])

            level_conditions[level_id] = conditions

        return level_conditions

    def _calculate_executor_statistics(self, current_time: int) -> Dict:
        """Calculate performance statistics for executors"""
        stats = {
            "total_active": len([e for e in self.executors_info if e.is_active]),
            "total_trading": len([e for e in self.executors_info if e.is_active and e.is_trading]),
            "total_not_trading": len([e for e in self.executors_info if e.is_active and not e.is_trading]),
            "avg_executor_age": Decimal("0"),
            "oldest_executor_age": 0,
            "refresh_candidates": 0
        }

        active_executors = [e for e in self.executors_info if e.is_active]

        if active_executors:
            ages = [current_time - e.timestamp for e in active_executors]
            stats["avg_executor_age"] = Decimal(str(sum(ages))) / Decimal(str(len(ages)))
            stats["oldest_executor_age"] = max(ages)

            # Count refresh candidates
            stats["refresh_candidates"] = len([
                e for e in active_executors
                if not e.is_trading and current_time - e.timestamp > self.config.executor_refresh_time
            ])

        return stats

    def _calculate_refresh_tracking(self, current_time: int) -> Dict:
        """Track executor refresh progress"""
        refresh_data = {
            "refresh_candidates": [],
            "near_refresh": 0,
            "refresh_ready": 0
        }

        # Get active non-trading executors
        active_not_trading = [e for e in self.executors_info if e.is_active and not e.is_trading]

        for executor in active_not_trading:
            age = current_time - executor.timestamp
            time_to_refresh = max(0, self.config.executor_refresh_time - age)
            progress_pct = min(Decimal("1"), Decimal(str(age)) / Decimal(str(self.config.executor_refresh_time)))

            ready = time_to_refresh == 0
            near_refresh = time_to_refresh <= (self.config.executor_refresh_time * 0.2)  # Within 20% of refresh time

            if ready:
                refresh_data["refresh_ready"] += 1
            elif near_refresh:
                refresh_data["near_refresh"] += 1

            level_id = executor.custom_info.get("level_id", "unknown")

            refresh_data["refresh_candidates"].append({
                "executor_id": executor.id,
                "level_id": level_id,
                "age": age,
                "time_to_refresh": time_to_refresh,
                "progress_pct": progress_pct,
                "ready": ready,
                "near_refresh": near_refresh
            })

        return refresh_data

    def _format_refresh_bars(self, refresh_tracking: Dict, bar_width: int, inner_width: int) -> List[str]:
        """Format refresh progress bars"""
        lines = []

        refresh_candidates = refresh_tracking.get('refresh_candidates', [])
        if not refresh_candidates:
            return lines

        lines.append(f"│ {'REFRESH PROGRESS:':<{inner_width}} │")

        # Show up to 5 executors approaching refresh
        for candidate in refresh_candidates[:5]:
            level_id = candidate.get('level_id', 'unknown')
            time_to_refresh = candidate.get('time_to_refresh', 0)
            progress = float(candidate.get('progress_pct', 0))
            ready = candidate.get('ready', False)
            near_refresh = candidate.get('near_refresh', False)

            bar = self._create_progress_bar(progress, bar_width // 2)

            if ready:
                status = "REFRESH NOW!"
                icon = "🔄"
            elif near_refresh:
                status = f"{time_to_refresh}s (Soon)"
                icon = "⏰"
            else:
                status = f"{time_to_refresh}s"
                icon = "⏳"

            lines.append(f"│ {icon} {level_id}: [{bar}] {status:<15} │")

        if len(refresh_candidates) > 5:
            lines.append(f"│ {'... and ' + str(len(refresh_candidates) - 5) + ' more':<{inner_width}} │")

        return lines

    def _format_price_graph(self, current_price: Decimal, breakeven_price: Optional[Decimal], inner_width: int) -> List[str]:
        """Format price graph with order zones and history"""
        lines = []

        if len(self.price_history) < 10:
            lines.append(f"│ {'Collecting price data...':<{inner_width}} │")
            return lines

        # Get last 30 price points for the graph
        recent_prices = [p['price'] for p in self.price_history[-30:]]
        min_price = min(recent_prices)
        max_price = max(recent_prices)

        # Calculate price range with some padding
        price_range = max_price - min_price
        if price_range == 0:
            price_range = current_price * Decimal('0.01')  # 1% range if no movement

        padding = price_range * Decimal('0.1')  # 10% padding
        graph_min = min_price - padding
        graph_max = max_price + padding
        graph_range = graph_max - graph_min

        # Calculate order zones
        buy_distance = current_price * self.config.min_buy_price_distance_pct
        sell_distance = current_price * self.config.min_sell_price_distance_pct
        buy_zone_price = current_price - buy_distance
        sell_zone_price = current_price + sell_distance

        # Graph dimensions
        graph_width = inner_width - 20  # Leave space for price labels and borders
        graph_height = 8

        # Create the graph
        graph_lines = []
        for row in range(graph_height):
            # Calculate price level for this row (top to bottom)
            price_level = graph_max - (Decimal(row) / Decimal(graph_height - 1)) * graph_range
            line = ""

            # Price label (left side)
            price_label = f"{float(price_level):6.2f}"
            line += price_label + " ┼"

            # Graph data
            for col in range(graph_width):
                # Calculate which price point this column represents
                col_index = int((col / graph_width) * len(recent_prices))
                if col_index >= len(recent_prices):
                    col_index = len(recent_prices) - 1

                price_at_col = recent_prices[col_index]

                # Determine what to show at this position
                char = "─"  # Default horizontal line

                # Check if current price line crosses this position
                if abs(float(price_at_col - price_level)) < float(graph_range) / (graph_height * 2):
                    if price_at_col == current_price:
                        char = "●"  # Current price marker
                    else:
                        char = "·"  # Price history point

                # Mark breakeven line
                if breakeven_price and abs(float(breakeven_price - price_level)) < float(graph_range) / (graph_height * 2):
                    char = "="  # Breakeven line

                # Mark order zones
                if abs(float(buy_zone_price - price_level)) < float(graph_range) / (graph_height * 4):
                    char = "B"  # Buy zone boundary
                elif abs(float(sell_zone_price - price_level)) < float(graph_range) / (graph_height * 4):
                    char = "S"  # Sell zone boundary

                # Mark recent orders
                for order in self.order_history[-10:]:  # Last 10 orders
                    order_price = order['price']
                    if abs(float(order_price - price_level)) < float(graph_range) / (graph_height * 3):
                        if order['side'] == 'BUY':
                            char = "b"  # Buy order
                        else:
                            char = "s"  # Sell order
                        break

                line += char

            # Add right border and annotations
            annotation = ""
            if abs(float(current_price - price_level)) < float(graph_range) / (graph_height * 2):
                annotation = " ← Current"
            elif breakeven_price and abs(float(breakeven_price - price_level)) < float(graph_range) / (graph_height * 2):
                annotation = " ← Breakeven"
            elif abs(float(sell_zone_price - price_level)) < float(graph_range) / (graph_height * 4):
                annotation = " ← Sell zone"
            elif abs(float(buy_zone_price - price_level)) < float(graph_range) / (graph_height * 4):
                annotation = " ← Buy zone"

            line += annotation
            graph_lines.append(line)

        # Format graph lines with proper padding
        for graph_line in graph_lines:
            lines.append(f"│ {graph_line:<{inner_width}} │")

        # Add legend
        lines.append(f"│ {'Legend: ● Current price  = Breakeven  B/S Zone boundaries  b/s Recent orders':<{inner_width}} │")

        # Add current metrics
        metrics_line = f"Distance req: Buy {self.config.min_buy_price_distance_pct:.3%} | Sell {self.config.min_sell_price_distance_pct:.3%}"
        if breakeven_price:
            distance_to_breakeven = ((current_price - breakeven_price) / current_price) if breakeven_price > 0 else Decimal(0)
            metrics_line += f" | Breakeven gap: {distance_to_breakeven:+.2%}"

        lines.append(f"│ {metrics_line:<{inner_width}} │")

        return lines
