from decimal import Decimal
from typing import Dict, List, Optional, Set, Tuple, Union

from pydantic import Field, field_validator
from pydantic_core.core_schema import ValidationInfo

from hummingbot.core.data_type.common import MarketDict, OrderType, PositionMode, PriceType, TradeType
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy_v2.controllers.controller_base import ControllerBase, ControllerConfigBase
from hummingbot.strategy_v2.executors.data_types import ConnectorPair
from hummingbot.strategy_v2.executors.position_executor.data_types import PositionExecutorConfig, TripleBarrierConfig
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, ExecutorAction, StopExecutorAction


class PMMisterConfig(ControllerConfigBase):
    """
    Advanced PMM (Pure Market Making) controller with sophisticated position management.
    Features hanging executors, price distance requirements, and breakeven awareness.
    """
    controller_type: str = "generic"
    controller_name: str = "pmm_mister"
    candles_config: List[CandlesConfig] = []
    connector_name: str = Field(default="binance")
    trading_pair: str = Field(default="BTC-FDUSD")
    portfolio_allocation: Decimal = Field(default=Decimal("0.05"), json_schema_extra={"is_updatable": True})
    target_base_pct: Decimal = Field(default=Decimal("0.2"), json_schema_extra={"is_updatable": True})
    min_base_pct: Decimal = Field(default=Decimal("0.1"), json_schema_extra={"is_updatable": True})
    max_base_pct: Decimal = Field(default=Decimal("0.4"), json_schema_extra={"is_updatable": True})
    buy_spreads: List[float] = Field(default="0.01,0.02", json_schema_extra={"is_updatable": True})
    sell_spreads: List[float] = Field(default="0.01,0.02", json_schema_extra={"is_updatable": True})
    buy_amounts_pct: Union[List[Decimal], None] = Field(default="1,2", json_schema_extra={"is_updatable": True})
    sell_amounts_pct: Union[List[Decimal], None] = Field(default="1,2", json_schema_extra={"is_updatable": True})
    executor_refresh_time: int = Field(default=30, json_schema_extra={"is_updatable": True})

    # Enhanced timing parameters
    buy_cooldown_time: int = Field(default=15, json_schema_extra={"is_updatable": True})
    sell_cooldown_time: int = Field(default=15, json_schema_extra={"is_updatable": True})
    buy_position_effectivization_time: int = Field(default=60, json_schema_extra={"is_updatable": True})
    sell_position_effectivization_time: int = Field(default=60, json_schema_extra={"is_updatable": True})

    # Price distance requirements
    min_buy_price_distance_pct: Decimal = Field(default=Decimal("0.003"), json_schema_extra={"is_updatable": True})
    min_sell_price_distance_pct: Decimal = Field(default=Decimal("0.003"), json_schema_extra={"is_updatable": True})

    leverage: int = Field(default=20, json_schema_extra={"is_updatable": True})
    position_mode: PositionMode = Field(default="HEDGE")
    take_profit: Optional[Decimal] = Field(default=Decimal("0.0001"), gt=0, json_schema_extra={"is_updatable": True})
    take_profit_order_type: Optional[OrderType] = Field(default="LIMIT_MAKER", json_schema_extra={"is_updatable": True})
    max_active_executors_by_level: Optional[int] = Field(default=4, json_schema_extra={"is_updatable": True})
    tick_mode: bool = Field(default=False, json_schema_extra={"is_updatable": True})

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
        if isinstance(v, OrderType):
            return v
        elif v is None:
            return OrderType.MARKET
        elif isinstance(v, str):
            if v.upper() in OrderType.__members__:
                return OrderType[v.upper()]
        elif isinstance(v, int):
            try:
                return OrderType(v)
            except ValueError:
                pass
        raise ValueError(f"Invalid order type: {v}. Valid options are: {', '.join(OrderType.__members__)}")

    @field_validator('buy_spreads', 'sell_spreads', mode="before")
    @classmethod
    def parse_spreads(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            if v == "":
                return []
            return [float(x.strip()) for x in v.split(',')]
        return v

    @field_validator('buy_amounts_pct', 'sell_amounts_pct', mode="before")
    @classmethod
    def parse_and_validate_amounts(cls, v, validation_info: ValidationInfo):
        field_name = validation_info.field_name
        if v is None or v == "":
            spread_field = field_name.replace('amounts_pct', 'spreads')
            return [1 for _ in validation_info.data[spread_field]]
        if isinstance(v, str):
            return [float(x.strip()) for x in v.split(',')]
        elif isinstance(v, list) and len(v) != len(validation_info.data[field_name.replace('amounts_pct', 'spreads')]):
            raise ValueError(
                f"The number of {field_name} must match the number of {field_name.replace('amounts_pct', 'spreads')}.")
        return v

    @field_validator('position_mode', mode="before")
    @classmethod
    def validate_position_mode(cls, v) -> PositionMode:
        if isinstance(v, str):
            if v.upper() in PositionMode.__members__:
                return PositionMode[v.upper()]
            raise ValueError(f"Invalid position mode: {v}. Valid options are: {', '.join(PositionMode.__members__)}")
        return v

    @property
    def triple_barrier_config(self) -> TripleBarrierConfig:
        return TripleBarrierConfig(
            take_profit=self.take_profit,
            trailing_stop=None,
            open_order_type=OrderType.LIMIT_MAKER,
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

            # Calculate price and amount
            side_multiplier = Decimal("-1") if trade_type == TradeType.BUY else Decimal("1")
            price = reference_price * (Decimal("1") + side_multiplier * spread_in_pct)
            amount = self.market_data_provider.quantize_order_amount(
                self.config.connector_name,
                self.config.trading_pair,
                (amount_quote / price)
            )

            if amount == Decimal("0"):
                self.logger().warning(f"The amount of the level {level_id} is 0. Skipping.")
                continue

            executor_config = self.get_executor_config(level_id, price, amount)
            if executor_config is not None:
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
            # Level is working if:
            # - it has active executors not trading
            # - it has too many active executors for the level
            # - it has a cooldown that is still active
            # - not satisfied price distance requirements
            if (analysis["active_executors_not_trading"] or
                    analysis["total_active_executors"] >= self.config.max_active_executors_by_level or
                    (analysis["open_order_last_update"] and current_time - analysis["open_order_last_update"] < self.config.get_cooldown_time(trade_type)) or
                    (is_buy and analysis["min_price"] and analysis["min_price"] * (Decimal("1") - self.config.min_buy_price_distance_pct) < current_price) or
                    (not is_buy and analysis["max_price"] and analysis["max_price"] * (Decimal("1") + self.config.min_sell_price_distance_pct) > current_price)):
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

        # Find hanging executors that should be effectivized
        executors_to_effectivize = self.filter_executors(
            executors=self.executors_info,
            filter_func=lambda x: (
                x.is_trading and
                self.should_effectivize_executor(x, current_time)
            )
        )
        return [StopExecutorAction(
            controller_id=self.config.id,
            keep_position=True,
            executor_id=executor.id
        ) for executor in executors_to_effectivize]

    async def update_processed_data(self):
        """
        Update processed data with enhanced breakeven tracking.
        """
        reference_price = self.market_data_provider.get_price_by_type(
            self.config.connector_name, self.config.trading_pair, PriceType.MidPrice
        )

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

        self.processed_data = {
            "reference_price": Decimal(reference_price),
            "spread_multiplier": spread_multiplier,
            "deviation": deviation,
            "current_base_pct": current_base_pct,
            "unrealized_pnl_pct": unrealized_pnl_pct,
            "position_amount": position_amount,
            "breakeven_price": breakeven_price
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
        return buy_ids_missing + sell_ids_missing

    def analyze_all_levels(self) -> List[Dict]:
        """Analyze executors for all levels."""
        level_ids: Set[str] = {e.custom_info.get("level_id") for e in self.executors_info if "level_id" in e.custom_info}
        return [self._analyze_by_level_id(level_id) for level_id in level_ids]

    def _analyze_by_level_id(self, level_id: str) -> Dict:
        """Analyze executors for a specific level ID."""
        filtered_executors = [e for e in self.executors_info if e.custom_info.get("level_id") == level_id and e.is_active]

        active_not_trading = [e for e in filtered_executors if e.is_active and not e.is_trading]
        active_trading = [e for e in filtered_executors if e.is_active and e.is_trading]

        open_order_last_updates = [
            e.custom_info.get("open_order_last_update") for e in filtered_executors
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
        Simplified status display showing executors by level_id and trade type.
        """
        from decimal import Decimal

        status = []

        # Get all required data
        base_pct = self.processed_data.get('current_base_pct', Decimal("0"))
        pnl = self.processed_data.get('unrealized_pnl_pct', Decimal('0'))
        breakeven = self.processed_data.get('breakeven_price')
        breakeven_str = f"{breakeven:.2f}" if breakeven is not None else "N/A"
        current_price = self.processed_data['reference_price']

        # Layout dimensions
        outer_width = 100
        inner_width = outer_width - 4

        # Header
        status.append("╒" + "═" * inner_width + "╕")
        pnl_sign = "+" if pnl >= 0 else ""
        status.append(
            f"│ {self.config.connector_name}:{self.config.trading_pair} | Price: {current_price:.2f} | Position: {base_pct:.1%} ({self.config.min_base_pct:.1%}-{self.config.max_base_pct:.1%}) | PnL: {pnl_sign}{pnl:.2%} | Breakeven: {breakeven_str}{' ' * (inner_width - 80)} │")

        # Executors by Level
        status.append(f"├{'─' * inner_width}┤")
        status.append(f"│ {'Level':<12} │ {'Type':<6} │ {'State':<10} │ {'Price':<12} │ {'Amount':<12} │ {'Distance':<12} │ {'Age':<10} │")
        status.append(f"├{'─' * 12}┼{'─' * 6}┼{'─' * 10}┼{'─' * 12}┼{'─' * 12}┼{'─' * 12}┼{'─' * 10}┤")

        # Analyze all levels and display each executor
        all_levels = self.analyze_all_levels()
        current_time = self.market_data_provider.time()

        for level_analysis in sorted(all_levels, key=lambda x: (not x["level_id"].startswith("buy"), x["level_id"])):
            level_id = level_analysis["level_id"]
            trade_type = "BUY" if level_id.startswith("buy") else "SELL"

            # Get all executors for this level
            level_executors = [e for e in self.executors_info if e.custom_info.get("level_id") == level_id and e.is_active]

            if not level_executors:
                continue

            for executor in level_executors:
                # Determine state
                if executor.is_trading:
                    state = "HANGING"
                elif executor.is_active and not executor.is_trading:
                    state = "ACTIVE"
                else:
                    state = "UNKNOWN"

                # Get price and amount
                price = executor.config.entry_price if hasattr(executor.config, 'entry_price') else Decimal("0")
                amount = executor.config.amount if hasattr(executor.config, 'amount') else Decimal("0")

                # Calculate distance from current price
                if price > 0:
                    distance_pct = ((price - current_price) / current_price) * 100
                    distance_str = f"{distance_pct:+.2f}%"
                else:
                    distance_str = "N/A"

                # Calculate age
                age = current_time - executor.timestamp
                age_str = f"{int(age)}s"

                status.append(f"│ {level_id:<12} │ {trade_type:<6} │ {state:<10} │ {price:<12.2f} │ {amount:<12.4f} │ {distance_str:<12} │ {age_str:<10} │")

        # Bottom border
        status.append(f"╘{'═' * inner_width}╛")

        return status
