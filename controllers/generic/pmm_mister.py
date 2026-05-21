from collections import defaultdict
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Union

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
    trading_pair: str = Field(default="BTC-USDT")
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

    # Price distance tolerance - prevents placing new orders when existing ones are too close to current price
    price_distance_tolerance: Decimal = Field(default=Decimal("0.0005"), json_schema_extra={"is_updatable": True})
    # Refresh tolerance - triggers replacing open orders when price deviates from theoretical level
    refresh_tolerance: Decimal = Field(default=Decimal("0.0005"), json_schema_extra={"is_updatable": True})
    tolerance_scaling: Decimal = Field(default=Decimal("1.2"), json_schema_extra={"is_updatable": True})

    leverage: int = Field(default=20, json_schema_extra={"is_updatable": True})
    position_mode: PositionMode = Field(default="ONEWAY")
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
        return parse_comma_separated_list(v)

    @field_validator('buy_amounts_pct', 'sell_amounts_pct', mode="before")
    @classmethod
    def parse_and_validate_amounts(cls, v, validation_info: ValidationInfo):
        field_name = validation_info.field_name
        if v is None or v == "":
            spread_field = field_name.replace('amounts_pct', 'spreads')
            return [1 for _ in validation_info.data[spread_field]]
        parsed = parse_comma_separated_list(v)
        if isinstance(parsed, list) and len(parsed) != len(validation_info.data[field_name.replace('amounts_pct', 'spreads')]):
            raise ValueError(
                f"The number of {field_name} must match the number of {field_name.replace('amounts_pct', 'spreads')}.")
        return parsed

    @field_validator('position_mode', mode="before")
    @classmethod
    def validate_position_mode(cls, v) -> PositionMode:
        return parse_enum_value(PositionMode, v, "position_mode")

    @field_validator('price_distance_tolerance', 'refresh_tolerance', 'tolerance_scaling', mode="before")
    @classmethod
    def validate_tolerance_fields(cls, v, validation_info: ValidationInfo):
        field_name = validation_info.field_name
        if isinstance(v, str):
            return Decimal(v)
        if field_name == 'tolerance_scaling' and Decimal(str(v)) <= 0:
            raise ValueError(f"{field_name} must be greater than 0")
        return v

    @property
    def triple_barrier_config(self) -> TripleBarrierConfig:
        # Ensure we're passing OrderType enum values, not strings
        open_order_type = self.open_order_type if isinstance(self.open_order_type, OrderType) else OrderType.LIMIT_MAKER
        take_profit_order_type = self.take_profit_order_type if isinstance(self.take_profit_order_type, OrderType) else OrderType.LIMIT_MAKER

        return TripleBarrierConfig(
            take_profit=self.take_profit,
            trailing_stop=None,
            open_order_type=open_order_type,
            take_profit_order_type=take_profit_order_type,
            stop_loss_order_type=OrderType.MARKET,
            time_limit_order_type=OrderType.MARKET
        )

    def get_cooldown_time(self, trade_type: TradeType) -> int:
        """Get cooldown time for specific trade type"""
        return self.buy_cooldown_time if trade_type == TradeType.BUY else self.sell_cooldown_time

    def get_position_effectivization_time(self, trade_type: TradeType) -> int:
        """Get position effectivization time for specific trade type"""
        return self.buy_position_effectivization_time if trade_type == TradeType.BUY else self.sell_position_effectivization_time

    def get_price_distance_level_tolerance(self, level: int) -> Decimal:
        """Get level-specific price distance tolerance (for new order placement).
        Prevents placing new orders when existing ones are too close to current price.
        """
        return self.price_distance_tolerance * (self.tolerance_scaling ** level)

    def get_refresh_level_tolerance(self, level: int) -> Decimal:
        """Get level-specific refresh tolerance (for order replacement).
        Triggers replacing open orders when price deviates from theoretical level.
        """
        return self.refresh_tolerance * (self.tolerance_scaling ** level)

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
        self.price_history = []
        self.max_price_history = 60
        self.order_history = []
        self.max_order_history = 20
        self.processed_data = {}

    # ── Market data (called by framework) ─────────────────────────────────

    async def update_processed_data(self):
        """Compute reference price and spread multiplier only. All executor analysis
        is done in _compute_executor_analysis called from determine_executor_actions."""
        try:
            reference_price = self.market_data_provider.get_price_by_type(
                self.config.connector_name, self.config.trading_pair, PriceType.MidPrice
            )
            if reference_price is None or reference_price <= 0:
                self.logger().warning("Invalid reference price received, using previous price if available")
                reference_price = self.processed_data.get("reference_price", Decimal("100"))
        except Exception as e:
            self.logger().warning(f"Error getting reference price: {e}, using previous price if available")
            reference_price = self.processed_data.get("reference_price", Decimal("100"))

        current_time = self.market_data_provider.time()

        self.price_history.append({'timestamp': current_time, 'price': Decimal(reference_price)})
        if len(self.price_history) > self.max_price_history:
            self.price_history.pop(0)

        if self.config.tick_mode:
            spread_multiplier = (self.market_data_provider.get_trading_rules(
                self.config.connector_name, self.config.trading_pair
            ).min_price_increment / reference_price)
        else:
            spread_multiplier = Decimal("1")

        self.processed_data = {
            "reference_price": Decimal(reference_price),
            "spread_multiplier": spread_multiplier,
        }

    # ── Executor actions (called by framework) ────────────────────────────

    def determine_executor_actions(self) -> List[ExecutorAction]:
        self._update_position_state()
        self._compute_executor_analysis()

        actions = []
        actions.extend(self.create_actions_proposal())
        actions.extend(self.stop_actions_proposal())
        return actions

    # ── Single-pass executor analysis ─────────────────────────────────────

    def _compute_executor_analysis(self):
        """Analyse every executor and level once per tick. Results are stored
        in self.processed_data and consumed by create/stop proposals and status display."""
        current_time = self.market_data_provider.time()
        reference_price = Decimal(str(self.processed_data.get("reference_price", 0)))
        if reference_price <= 0:
            return

        # -- 1. Group executors by level_id in a single pass -----------------
        executors_by_level: Dict[str, list] = defaultdict(list)
        for e in self.executors_info:
            level_id = e.custom_info.get("level_id")
            if level_id:
                executors_by_level[level_id].append(e)

        # All configured levels (may not have executors yet)
        all_level_ids = set()
        for i in range(len(self.config.buy_spreads)):
            all_level_ids.add(f"buy_{i}")
        for i in range(len(self.config.sell_spreads)):
            all_level_ids.add(f"sell_{i}")
        all_level_ids.update(executors_by_level.keys())

        # -- 2. Per-level analysis + blocking conditions ----------------------
        levels_analysis: Dict[str, Dict] = {}
        level_conditions: Dict[str, Dict] = {}
        working_levels = set()

        cooldown_status = {
            "buy": {"active": False, "remaining_time": 0, "progress_pct": Decimal("0")},
            "sell": {"active": False, "remaining_time": 0, "progress_pct": Decimal("0")},
        }

        current_pct = self.processed_data.get("current_base_pct", Decimal("0"))
        breakeven_price = self.processed_data.get("breakeven_price")

        for level_id in all_level_ids:
            executors = executors_by_level.get(level_id, [])
            active = [e for e in executors if e.is_active]
            active_not_trading = [e for e in active if not e.is_trading]
            active_trading = [e for e in active if e.is_trading]

            open_order_updates = [
                e.custom_info.get("open_order_last_update") for e in executors
                if e.custom_info.get("open_order_last_update") is not None
            ]
            latest_update = max(open_order_updates) if open_order_updates else None
            prices = [Decimal(str(e.config.entry_price)) for e in active if hasattr(e.config, 'entry_price')]

            analysis = {
                "active_not_trading": active_not_trading,
                "active_trading": active_trading,
                "total_active": len(active),
                "open_order_last_update": latest_update,
                "min_price": min(prices) if prices else None,
                "max_price": max(prices) if prices else None,
            }
            levels_analysis[level_id] = analysis

            trade_type = self.get_trade_type_from_level_id(level_id)
            is_buy = level_id.startswith("buy")
            level = self.get_level_from_level_id(level_id)

            blocking: List[str] = []

            # a) Has open (not yet filled) executors
            if active_not_trading:
                blocking.append("active_not_trading")

            # b) Max executor cap reached
            if analysis["total_active"] >= self.config.max_active_executors_by_level:
                blocking.append("max_active_executors")

            # c) Cooldown
            if latest_update is not None:
                cooldown_time = self.config.get_cooldown_time(trade_type)
                time_since = current_time - latest_update
                if time_since < cooldown_time:
                    blocking.append("cooldown")
                    # Track cooldown progress for display (keep the most recent)
                    side = "buy" if is_buy else "sell"
                    remaining = cooldown_time - time_since
                    progress = Decimal(str(time_since)) / Decimal(str(cooldown_time))
                    if not cooldown_status[side]["active"] or remaining > cooldown_status[side]["remaining_time"]:
                        cooldown_status[side].update(active=True, remaining_time=remaining, progress_pct=progress)

            # d) Price distance violation
            level_tolerance = self.config.get_price_distance_level_tolerance(level)
            if is_buy and analysis["min_price"] is not None:
                distance = (analysis["min_price"] - reference_price) / reference_price
                if distance < level_tolerance:
                    blocking.append("price_distance")
            elif not is_buy and analysis["max_price"] is not None:
                distance = (reference_price - analysis["max_price"]) / reference_price
                if distance < level_tolerance:
                    blocking.append("price_distance")

            # e) Position constraints
            if current_pct < self.config.min_base_pct and not is_buy:
                blocking.append("below_min_position")
            elif current_pct > self.config.max_base_pct and is_buy:
                blocking.append("above_max_position")

            # f) Position profit protection
            if (self.config.position_profit_protection and not is_buy
                    and breakeven_price and breakeven_price > 0 and reference_price < breakeven_price):
                blocking.append("position_profit_protection")

            # Execution-blocking conditions determine "working" levels
            execution_blocking = {"active_not_trading", "max_active_executors", "cooldown", "price_distance"}
            if any(b in execution_blocking for b in blocking):
                working_levels.add(level_id)

            level_conditions[level_id] = {
                "trade_type": trade_type.name,
                "can_execute": len(blocking) == 0,
                "blocking_conditions": blocking,
                "active_executors": len(active_not_trading),
                "hanging_executors": len(active_trading),
            }

        # -- 3. Levels to execute (position-aware) ----------------------------
        levels_to_execute = self._get_executable_levels(working_levels)

        # -- 4. Executors to refresh + refresh tracking -----------------------
        executors_to_refresh = []
        refresh_tracking = {
            "refresh_candidates": [], "near_refresh": 0,
            "refresh_ready": 0, "distance_violations": 0,
        }

        for e in self.executors_info:
            if not e.is_active or e.is_trading:
                continue

            age = current_time - e.timestamp
            time_based = age > self.config.executor_refresh_time
            distance_based = reference_price > 0 and self.should_refresh_executor_by_distance(e, reference_price)

            if time_based or distance_based:
                executors_to_refresh.append(e)

            # Tracking data for display
            time_to_refresh = max(0, self.config.executor_refresh_time - age)
            progress = min(Decimal("1"), Decimal(str(age)) / Decimal(str(self.config.executor_refresh_time)))
            ready = time_based or distance_based
            near = time_to_refresh <= self.config.executor_refresh_time * 0.2

            distance_deviation_pct = Decimal("0")
            e_level_id = e.custom_info.get("level_id", "")
            if e_level_id and hasattr(e.config, 'entry_price') and reference_price > 0:
                theoretical = self.calculate_theoretical_price(e_level_id, reference_price)
                if theoretical > 0:
                    distance_deviation_pct = abs(e.config.entry_price - theoretical) / theoretical

            if ready:
                refresh_tracking["refresh_ready"] += 1
            elif near:
                refresh_tracking["near_refresh"] += 1
            if distance_based:
                refresh_tracking["distance_violations"] += 1

            e_level = self.get_level_from_level_id(e_level_id) if e_level_id else 0
            refresh_tracking["refresh_candidates"].append({
                "executor_id": e.id,
                "level_id": e_level_id or "unknown",
                "level": e_level,
                "age": age,
                "time_to_refresh": time_to_refresh,
                "progress_pct": progress,
                "ready": ready,
                "ready_by_time": time_based,
                "ready_by_distance": distance_based,
                "distance_deviation_pct": distance_deviation_pct,
                "distance_violation": distance_based,
                "level_tolerance": self.config.get_refresh_level_tolerance(e_level),
                "near_refresh": near,
            })

        # -- 5. Hanging executors to effectivize + tracking -------------------
        executors_to_effectivize = []
        effectivization_tracking = {
            "hanging_executors": [], "total_hanging": 0, "ready_for_effectivization": 0,
        }

        for e in self.executors_info:
            if not (e.is_active and e.is_trading):
                continue

            e_level_id = e.custom_info.get("level_id", "")
            fill_time = e.custom_info.get("open_order_last_update")
            if not e_level_id or fill_time is None:
                continue

            trade_type = self.get_trade_type_from_level_id(e_level_id)
            eff_time = self.config.get_position_effectivization_time(trade_type)
            elapsed = current_time - fill_time
            remaining = max(0, eff_time - elapsed)
            progress = min(Decimal("1"), Decimal(str(elapsed)) / Decimal(str(eff_time)))
            ready = remaining == 0

            if ready:
                executors_to_effectivize.append(e)
                effectivization_tracking["ready_for_effectivization"] += 1

            effectivization_tracking["total_hanging"] += 1
            effectivization_tracking["hanging_executors"].append({
                "level_id": e_level_id,
                "trade_type": trade_type.name,
                "time_elapsed": elapsed,
                "remaining_time": remaining,
                "progress_pct": progress,
                "ready": ready,
                "executor_id": e.id,
            })

        # -- 6. Executor statistics -------------------------------------------
        active_all = [e for e in self.executors_info if e.is_active]
        total_trading = sum(1 for e in active_all if e.is_trading)
        executor_stats = {
            "total_active": len(active_all),
            "total_trading": total_trading,
            "total_not_trading": len(active_all) - total_trading,
        }

        # -- Store everything -------------------------------------------------
        self.processed_data.update({
            "levels_analysis": levels_analysis,
            "level_conditions": level_conditions,
            "levels_to_execute": levels_to_execute,
            "executors_to_refresh": executors_to_refresh,
            "executors_to_effectivize": executors_to_effectivize,
            "cooldown_status": cooldown_status,
            "effectivization_tracking": effectivization_tracking,
            "refresh_tracking": refresh_tracking,
            "executor_stats": executor_stats,
            "current_time": current_time,
        })

    # ── Position state ────────────────────────────────────────────────────

    def _update_position_state(self):
        """Recalculate position-derived fields (skews, deviation, breakeven) from positions_held."""
        reference_price = self.processed_data.get("reference_price")
        if reference_price is None:
            return

        position_held = next((p for p in self.positions_held if
                              p.trading_pair == self.config.trading_pair and
                              p.connector_name == self.config.connector_name), None)

        target_position = self.config.total_amount_quote * self.config.target_base_pct

        if position_held is not None:
            current_base_pct = position_held.amount_quote / self.config.total_amount_quote
            deviation = (target_position - position_held.amount_quote) / target_position
            unrealized_pnl_pct = (position_held.unrealized_pnl_quote / position_held.amount_quote
                                  if position_held.amount_quote != 0 else Decimal("0"))
            breakeven_price = position_held.breakeven_price
            position_amount = position_held.amount
        else:
            current_base_pct = Decimal("0")
            deviation = Decimal("1")
            unrealized_pnl_pct = Decimal("0")
            breakeven_price = None
            position_amount = Decimal("0")

        min_pct = self.config.min_base_pct
        max_pct = self.config.max_base_pct
        if max_pct > min_pct:
            buy_skew = (max_pct - current_base_pct) / (max_pct - min_pct)
            sell_skew = (current_base_pct - min_pct) / (max_pct - min_pct)
            buy_skew = max(min(buy_skew, Decimal("1.0")), self.config.min_skew)
            sell_skew = max(min(sell_skew, Decimal("1.0")), self.config.min_skew)
        else:
            buy_skew = sell_skew = Decimal("1.0")

        self.processed_data.update({
            "deviation": deviation,
            "current_base_pct": current_base_pct,
            "unrealized_pnl_pct": unrealized_pnl_pct,
            "breakeven_price": breakeven_price,
            "position_amount": position_amount,
            "buy_skew": buy_skew,
            "sell_skew": sell_skew,
        })

    # ── Create / stop proposals ───────────────────────────────────────────

    def create_actions_proposal(self) -> List[ExecutorAction]:
        create_actions = []

        levels_to_execute = self.processed_data.get("levels_to_execute", [])
        if not levels_to_execute:
            return create_actions

        buy_spreads, buy_amounts_quote = self.config.get_spreads_and_amounts_in_quote(TradeType.BUY)
        sell_spreads, sell_amounts_quote = self.config.get_spreads_and_amounts_in_quote(TradeType.SELL)
        reference_price = Decimal(self.processed_data["reference_price"])
        buy_skew = self.processed_data["buy_skew"]
        sell_skew = self.processed_data["sell_skew"]

        for level_id in levels_to_execute:
            trade_type = self.get_trade_type_from_level_id(level_id)
            level = self.get_level_from_level_id(level_id)

            if trade_type == TradeType.BUY:
                spread_in_pct = Decimal(buy_spreads[level]) * Decimal(self.processed_data["spread_multiplier"])
                amount_quote = Decimal(buy_amounts_quote[level])
            else:
                spread_in_pct = Decimal(sell_spreads[level]) * Decimal(self.processed_data["spread_multiplier"])
                amount_quote = Decimal(sell_amounts_quote[level])

            skew = buy_skew if trade_type == TradeType.BUY else sell_skew
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

    def stop_actions_proposal(self) -> List[ExecutorAction]:
        stop_actions = []

        for executor in self.processed_data.get("executors_to_refresh", []):
            stop_actions.append(StopExecutorAction(
                controller_id=self.config.id,
                keep_position=True,
                executor_id=executor.id
            ))

        for executor in self.processed_data.get("executors_to_effectivize", []):
            stop_actions.append(StopExecutorAction(
                controller_id=self.config.id,
                keep_position=True,
                executor_id=executor.id
            ))

        return stop_actions

    # ── Helpers ───────────────────────────────────────────────────────────

    def _get_executable_levels(self, working_levels: set) -> List[str]:
        """Get levels that should be executed, applying position constraints."""
        buy_missing = [
            f"buy_{i}" for i in range(len(self.config.buy_spreads))
            if f"buy_{i}" not in working_levels
        ]
        sell_missing = [
            f"sell_{i}" for i in range(len(self.config.sell_spreads))
            if f"sell_{i}" not in working_levels
        ]

        current_pct = self.processed_data.get("current_base_pct", Decimal("0"))

        if current_pct < self.config.min_base_pct:
            return buy_missing
        elif current_pct > self.config.max_base_pct:
            return sell_missing

        if self.config.position_profit_protection:
            breakeven_price = self.processed_data.get("breakeven_price")
            reference_price = self.processed_data["reference_price"]
            target_pct = self.config.target_base_pct

            if breakeven_price is not None and breakeven_price > 0:
                if current_pct < target_pct and reference_price < breakeven_price:
                    return buy_missing
                elif current_pct > target_pct and reference_price > breakeven_price:
                    return sell_missing

        return buy_missing + sell_missing

    def calculate_theoretical_price(self, level_id: str, reference_price: Decimal) -> Decimal:
        """Calculate the theoretical price for a given level"""
        trade_type = self.get_trade_type_from_level_id(level_id)
        level = self.get_level_from_level_id(level_id)

        spreads = self.config.buy_spreads if trade_type == TradeType.BUY else self.config.sell_spreads
        if level >= len(spreads):
            return reference_price

        spread_in_pct = Decimal(spreads[level]) * Decimal(self.processed_data.get("spread_multiplier", 1))
        side_multiplier = Decimal("-1") if trade_type == TradeType.BUY else Decimal("1")
        return reference_price * (Decimal("1") + side_multiplier * spread_in_pct)

    def should_refresh_executor_by_distance(self, executor_info, reference_price: Decimal) -> bool:
        """Check if executor should be refreshed due to price distance deviation"""
        level_id = executor_info.custom_info.get("level_id", "")
        if not level_id or not hasattr(executor_info.config, 'entry_price'):
            return False

        theoretical_price = self.calculate_theoretical_price(level_id, reference_price)
        if theoretical_price == 0:
            return False

        distance_deviation = abs(executor_info.config.entry_price - theoretical_price) / theoretical_price
        level = self.get_level_from_level_id(level_id)
        return distance_deviation > self.config.get_refresh_level_tolerance(level)

    def get_executor_config(self, level_id: str, price: Decimal, amount: Decimal):
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
        return f"{trade_type.name.lower()}_{level}"

    def get_trade_type_from_level_id(self, level_id: str) -> TradeType:
        return TradeType.BUY if level_id.startswith("buy") else TradeType.SELL

    def get_level_from_level_id(self, level_id: str) -> int:
        return int(level_id.split('_')[1])

    # ── Status display ────────────────────────────────────────────────────

    def to_format_status(self) -> List[str]:
        from decimal import Decimal
        from itertools import zip_longest

        status = []
        outer_width = 170
        inner_width = outer_width - 4

        if not hasattr(self, 'processed_data') or not self.processed_data:
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

        cooldown_status = self.processed_data.get('cooldown_status', {})
        effectivization = self.processed_data.get('effectivization_tracking', {})
        level_conditions = self.processed_data.get('level_conditions', {})
        executor_stats = self.processed_data.get('executor_stats', {})
        refresh_tracking = self.processed_data.get('refresh_tracking', {})
        levels_analysis = self.processed_data.get('levels_analysis', {})

        col1_width = 28
        col2_width = 35
        col3_width = 28
        col4_width = 25
        col5_width = inner_width - col1_width - col2_width - col3_width - col4_width - 4

        half_width = inner_width // 2 - 1
        bar_width = inner_width - 25

        # Header
        status.append("╒" + "═" * inner_width + "╕")

        header_line = (
            f"{self.config.connector_name}:{self.config.trading_pair} @ {current_price:.2f}  "
            f"Alloc: {self.config.portfolio_allocation:.1%}  "
            f"Spread×{self.processed_data.get('spread_multiplier', Decimal('1')):.3f}  "
            f"Dist: {self.config.price_distance_tolerance:.4%} Ref: {self.config.refresh_tolerance:.4%} (×{self.config.tolerance_scaling})  "
            f"Pos Protect: {'ON' if self.config.position_profit_protection else 'OFF'}"
        )
        status.append(f"│ {header_line:<{inner_width}} │")

        # REAL-TIME CONDITIONS DASHBOARD
        status.append(f"├{'─' * inner_width}┤")
        status.append(f"│ {'🔄 REAL-TIME CONDITIONS DASHBOARD':<{inner_width}} │")
        status.append(f"├{'─' * col1_width}┬{'─' * col2_width}┬{'─' * col3_width}┬{'─' * col4_width}┬{'─' * col5_width}┤")
        status.append(f"│ {'COOLDOWNS':<{col1_width}} │ {'PRICE DISTANCES':<{col2_width}} │ {'EFFECTIVIZATION':<{col3_width}} │ {'REFRESH TRACKING':<{col4_width}} │ {'EXECUTION':<{col5_width}} │")
        status.append(f"├{'─' * col1_width}┼{'─' * col2_width}┼{'─' * col3_width}┼{'─' * col4_width}┼{'─' * col5_width}┤")

        buy_cooldown = cooldown_status.get('buy', {})
        sell_cooldown = cooldown_status.get('sell', {})

        cooldown_info = [
            f"BUY: {self._format_cooldown_status(buy_cooldown)}",
            f"SELL: {self._format_cooldown_status(sell_cooldown)}",
            f"Times: {self.config.buy_cooldown_time}/{self.config.sell_cooldown_time}s",
            ""
        ]

        # Calculate actual distances from pre-computed levels_analysis
        current_buy_distance = ""
        current_sell_distance = ""
        for level_id, analysis in levels_analysis.items():
            is_buy = level_id.startswith("buy")
            if is_buy and analysis.get("min_price"):
                distance = (analysis["min_price"] - current_price) / current_price
                current_buy_distance = f"({distance:.3%})"
            elif not is_buy and analysis.get("max_price"):
                distance = (current_price - analysis["max_price"]) / current_price
                current_sell_distance = f"({distance:.3%})"

        violation_marker = " ⚠️" if (current_buy_distance and "(0.0" in current_buy_distance) or (current_sell_distance and "(0.0" in current_sell_distance) else ""

        dist_l0 = self.config.get_price_distance_level_tolerance(0)
        dist_l1 = self.config.get_price_distance_level_tolerance(1) if len(self.config.buy_spreads) > 1 else None

        price_info = [
            f"L0 Dist: {dist_l0:.4%}{violation_marker}",
            f"BUY Current: {current_buy_distance}",
            f"L1 Dist: {dist_l1:.4%}" if dist_l1 else "L1: N/A",
            f"SELL Current: {current_sell_distance}"
        ]

        total_hanging = effectivization.get('total_hanging', 0)
        ready_count = effectivization.get('ready_for_effectivization', 0)

        effect_info = [
            f"Hanging: {total_hanging}",
            f"Ready: {ready_count}",
            f"Times: {self.config.buy_position_effectivization_time}s/{self.config.sell_position_effectivization_time}s",
            ""
        ]

        near_refresh = refresh_tracking.get('near_refresh', 0)
        refresh_ready = refresh_tracking.get('refresh_ready', 0)
        distance_violations = refresh_tracking.get('distance_violations', 0)

        refresh_info = [
            f"Near Refresh: {near_refresh}",
            f"Ready: {refresh_ready}",
            f"Distance Violations: {distance_violations}",
            f"Threshold: {self.config.executor_refresh_time}s"
        ]

        can_execute_buy = len([lc for lc in level_conditions.values() if lc.get('trade_type') == 'BUY' and lc.get('can_execute')])
        can_execute_sell = len([lc for lc in level_conditions.values() if lc.get('trade_type') == 'SELL' and lc.get('can_execute')])
        total_buy_levels = len(self.config.buy_spreads)
        total_sell_levels = len(self.config.sell_spreads)

        execution_info = [
            f"BUY: {can_execute_buy}/{total_buy_levels}",
            f"SELL: {can_execute_sell}/{total_sell_levels}",
            f"Active: {executor_stats.get('total_active', 0)}",
            ""
        ]

        for cool_line, price_line, effect_line, refresh_line, exec_line in zip_longest(cooldown_info, price_info, effect_info, refresh_info, execution_info, fillvalue=""):
            status.append(f"│ {cool_line:<{col1_width}} │ {price_line:<{col2_width}} │ {effect_line:<{col3_width}} │ {refresh_line:<{col4_width}} │ {exec_line:<{col5_width}} │")

        # LEVEL-BY-LEVEL ANALYSIS
        status.append(f"├{'─' * inner_width}┤")
        status.append(f"│ {'📊 LEVEL-BY-LEVEL ANALYSIS':<{inner_width}} │")
        status.append(f"├{'─' * inner_width}┤")

        status.extend(self._format_level_conditions(level_conditions, inner_width))

        # VISUAL PROGRESS INDICATORS
        status.append(f"├{'─' * inner_width}┤")
        status.append(f"│ {'🔄 VISUAL PROGRESS INDICATORS':<{inner_width}} │")
        status.append(f"├{'─' * inner_width}┤")

        if buy_cooldown.get('active') or sell_cooldown.get('active'):
            status.extend(self._format_cooldown_bars(buy_cooldown, sell_cooldown, bar_width, inner_width))

        if total_hanging > 0:
            status.extend(self._format_effectivization_bars(effectivization, bar_width, inner_width))

        if refresh_tracking.get('refresh_candidates', []):
            status.extend(self._format_refresh_bars(refresh_tracking, bar_width, inner_width))

        # POSITION & PNL DASHBOARD
        status.append(f"├{'─' * half_width}┬{'─' * half_width}┤")
        status.append(f"│ {'📍 POSITION STATUS':<{half_width}} │ {'💰 PROFIT & LOSS':<{half_width}} │")
        status.append(f"├{'─' * half_width}┼{'─' * half_width}┤")

        skew = base_pct - target_pct
        skew_pct = skew / target_pct if target_pct != 0 else Decimal('0')
        position_info = [
            f"Current: {base_pct:.2%} (Target: {target_pct:.2%})",
            f"Range: {min_pct:.2%} - {max_pct:.2%}",
            f"Skew: {skew_pct:+.2%} (min {self.config.min_skew:.2%})",
            f"Buy Skew: {buy_skew:.2f} | Sell Skew: {sell_skew:.2f}"
        ]

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

        for pos_line, pnl_line in zip_longest(position_info, pnl_info, fillvalue=""):
            status.append(f"│ {pos_line:<{half_width}} │ {pnl_line:<{half_width}} │")

        status.append(f"├{'─' * inner_width}┤")
        status.extend(self._format_position_visualization(base_pct, target_pct, min_pct, max_pct, skew_pct, pnl, bar_width, inner_width))

        status.append(f"╘{'═' * inner_width}╛")

        return status

    # ── Display formatting helpers ────────────────────────────────────────

    def _format_cooldown_status(self, cooldown_data: Dict) -> str:
        if not cooldown_data.get('active'):
            return "READY ✓"
        remaining = cooldown_data.get('remaining_time', 0)
        progress = cooldown_data.get('progress_pct', Decimal('0'))
        return f"{remaining:.1f}s ({progress:.0%})"

    def _format_level_conditions(self, level_conditions: Dict, inner_width: int) -> List[str]:
        lines = []
        buy_levels = {k: v for k, v in level_conditions.items() if v.get('trade_type') == 'BUY'}
        sell_levels = {k: v for k, v in level_conditions.items() if v.get('trade_type') == 'SELL'}

        if not buy_levels and not sell_levels:
            lines.append(f"│ {'No levels configured':<{inner_width}} │")
            return lines

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
        lines = []
        if buy_cooldown.get('active'):
            progress = float(buy_cooldown.get('progress_pct', 0))
            remaining = buy_cooldown.get('remaining_time', 0)
            bar = self._create_progress_bar(progress, bar_width // 2)
            lines.append(f"│ BUY Cooldown:   [{bar}] {remaining:.1f}s remaining │")
        if sell_cooldown.get('active'):
            progress = float(sell_cooldown.get('progress_pct', 0))
            remaining = sell_cooldown.get('remaining_time', 0)
            bar = self._create_progress_bar(progress, bar_width // 2)
            lines.append(f"│ SELL Cooldown:  [{bar}] {remaining:.1f}s remaining │")
        return lines

    def _format_effectivization_bars(self, effectivization: Dict, bar_width: int, inner_width: int) -> List[str]:
        lines = []
        hanging_executors = effectivization.get('hanging_executors', [])
        if not hanging_executors:
            return lines

        lines.append(f"│ {'EFFECTIVIZATION PROGRESS:':<{inner_width}} │")

        for executor in hanging_executors[:5]:
            level_id = executor.get('level_id', 'unknown')
            trade_type = executor.get('trade_type', 'UNKNOWN')
            progress = float(executor.get('progress_pct', 0))
            remaining = executor.get('remaining_time', 0)
            ready = executor.get('ready', False)

            bar = self._create_progress_bar(progress, bar_width // 2)
            eff_status = "READY!" if ready else f"{remaining}s"
            icon = "✓" if ready else "🔄"
            lines.append(f"│ {icon} {level_id} ({trade_type}): [{bar}] {eff_status:<10} │")

        if len(hanging_executors) > 5:
            lines.append(f"│ {'... and ' + str(len(hanging_executors) - 5) + ' more':<{inner_width}} │")

        return lines

    def _format_refresh_bars(self, refresh_tracking: Dict, bar_width: int, inner_width: int) -> List[str]:
        lines = []
        refresh_candidates = refresh_tracking.get('refresh_candidates', [])
        if not refresh_candidates:
            return lines

        lines.append(f"│ {'REFRESH PROGRESS:':<{inner_width}} │")

        for candidate in refresh_candidates[:5]:
            level_id = candidate.get('level_id', 'unknown')
            time_to_refresh = candidate.get('time_to_refresh', 0)
            progress = float(candidate.get('progress_pct', 0))
            ready = candidate.get('ready', False)
            ready_by_distance = candidate.get('ready_by_distance', False)
            distance_deviation_pct = candidate.get('distance_deviation_pct', Decimal('0'))
            near_refresh = candidate.get('near_refresh', False)

            bar = self._create_progress_bar(progress, bar_width // 2)

            if ready:
                if ready_by_distance:
                    ref_status = f"DISTANCE! ({distance_deviation_pct:.1%})"
                    icon = "⚠️"
                else:
                    ref_status = "TIME REFRESH!"
                    icon = "🔄"
            elif near_refresh:
                ref_status = f"{time_to_refresh}s (Soon)"
                icon = "⏰"
            else:
                if distance_deviation_pct > 0:
                    ref_status = f"{time_to_refresh}s ({distance_deviation_pct:.1%})"
                else:
                    ref_status = f"{time_to_refresh}s"
                icon = "⏳"

            lines.append(f"│ {icon} {level_id}: [{bar}] {ref_status:<15} │")

        if len(refresh_candidates) > 5:
            lines.append(f"│ {'... and ' + str(len(refresh_candidates) - 5) + ' more':<{inner_width}} │")

        return lines

    def _format_position_visualization(self, base_pct: Decimal, target_pct: Decimal, min_pct: Decimal,
                                       max_pct: Decimal, skew_pct: Decimal, pnl: Decimal,
                                       bar_width: int, inner_width: int) -> List[str]:
        lines = []

        filled_width = int(float(base_pct) * bar_width)
        min_pos = int(float(min_pct) * bar_width)
        max_pos = int(float(max_pct) * bar_width)
        target_pos = int(float(target_pct) * bar_width)

        position_bar = ""
        for i in range(bar_width):
            if i == filled_width:
                position_bar += "◆"
            elif i == target_pos:
                position_bar += "┇"
            elif i == min_pos:
                position_bar += "┃"
            elif i == max_pos:
                position_bar += "┃"
            elif i < filled_width:
                position_bar += "█"
            else:
                position_bar += "░"

        lines.append(f"│ Position:   [{position_bar}] {base_pct:.2%} │")

        center = bar_width // 2
        skew_pos = center + int(float(skew_pct) * center)
        skew_pos = max(0, min(bar_width - 1, skew_pos))

        skew_bar = ""
        for i in range(bar_width):
            if i == center:
                skew_bar += "┃"
            elif i == skew_pos:
                skew_bar += "⬤"
            else:
                skew_bar += "─"

        skew_direction = "BULLISH" if skew_pct > 0 else "BEARISH" if skew_pct < 0 else "NEUTRAL"
        lines.append(f"│ Skew:       [{skew_bar}] {skew_direction} │")

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
                    pnl_bar += "│"
                elif i == pnl_pos:
                    pnl_bar += "⬤"
                elif i == take_profit_pos:
                    pnl_bar += "T"
                elif i == stop_loss_pos:
                    pnl_bar += "S"
                elif ((pnl >= 0 and center <= i < pnl_pos) or
                      (pnl < 0 and pnl_pos < i <= center)):
                    pnl_bar += "█" if pnl >= 0 else "▓"
                else:
                    pnl_bar += "─"
        else:
            pnl_bar = "─" * bar_width

        pnl_status = "PROFIT" if pnl > 0 else "LOSS" if pnl < 0 else "BREAK-EVEN"
        lines.append(f"│ PnL:        [{pnl_bar}] {pnl_status} │")

        return lines

    def _create_progress_bar(self, progress: float, width: int) -> str:
        progress = max(0, min(1, progress))
        filled = int(progress * width)
        bar = ""
        for i in range(width):
            if i < filled:
                bar += "█"
            elif i == filled and filled < width:
                bar += "▌"
            else:
                bar += "░"
        return bar

    def _format_price_graph(self, current_price: Decimal, breakeven_price: Optional[Decimal], inner_width: int) -> List[str]:
        lines = []

        if len(self.price_history) < 10:
            lines.append(f"│ {'Collecting price data...':<{inner_width}} │")
            return lines

        recent_prices = [p['price'] for p in self.price_history[-30:]]
        min_price = min(recent_prices)
        max_price = max(recent_prices)

        price_range = max_price - min_price
        if price_range == 0:
            price_range = current_price * Decimal('0.01')

        padding = price_range * Decimal('0.1')
        graph_min = min_price - padding
        graph_max = max_price + padding
        graph_range = graph_max - graph_min

        level_0_tolerance = self.config.get_price_distance_level_tolerance(0)
        buy_distance = current_price * level_0_tolerance
        sell_distance = current_price * level_0_tolerance
        buy_zone_price = current_price - buy_distance
        sell_zone_price = current_price + sell_distance

        graph_width = inner_width - 20
        graph_height = 8

        graph_lines = []
        for row in range(graph_height):
            price_level = graph_max - (Decimal(row) / Decimal(graph_height - 1)) * graph_range
            line = ""
            price_label = f"{float(price_level):6.2f}"
            line += price_label + " ┼"

            for col in range(graph_width):
                col_index = int((col / graph_width) * len(recent_prices))
                if col_index >= len(recent_prices):
                    col_index = len(recent_prices) - 1

                price_at_col = recent_prices[col_index]
                char = "─"

                if abs(float(price_at_col - price_level)) < float(graph_range) / (graph_height * 2):
                    if price_at_col == current_price:
                        char = "●"
                    else:
                        char = "·"

                if breakeven_price and abs(float(breakeven_price - price_level)) < float(graph_range) / (graph_height * 2):
                    char = "="

                if abs(float(buy_zone_price - price_level)) < float(graph_range) / (graph_height * 4):
                    char = "B"
                elif abs(float(sell_zone_price - price_level)) < float(graph_range) / (graph_height * 4):
                    char = "S"

                for order in self.order_history[-10:]:
                    order_price = order['price']
                    if abs(float(order_price - price_level)) < float(graph_range) / (graph_height * 3):
                        if order['side'] == 'BUY':
                            char = "b"
                        else:
                            char = "s"
                        break

                line += char

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

        for graph_line in graph_lines:
            lines.append(f"│ {graph_line:<{inner_width}} │")

        lines.append(f"│ {'Legend: ● Current price  = Breakeven  B/S Zone boundaries  b/s Recent orders':<{inner_width}} │")

        dist_l0 = self.config.get_price_distance_level_tolerance(0)
        ref_l0 = self.config.get_refresh_level_tolerance(0)
        metrics_line = f"Dist: L0 {dist_l0:.4%} | Refresh: L0 {ref_l0:.4%} | Scaling: ×{self.config.tolerance_scaling}"
        if breakeven_price:
            distance_to_breakeven = ((current_price - breakeven_price) / current_price) if breakeven_price > 0 else Decimal(0)
            metrics_line += f" | Breakeven gap: {distance_to_breakeven:+.2%}"

        lines.append(f"│ {metrics_line:<{inner_width}} │")

        return lines
