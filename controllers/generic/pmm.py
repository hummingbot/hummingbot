from decimal import Decimal
from typing import Dict, List, Optional, Set, Tuple, Union

from pydantic import Field, field_validator
from pydantic_core.core_schema import ValidationInfo

from hummingbot.core.data_type.common import OrderType, PositionMode, PriceType, TradeType
from hummingbot.core.data_type.trade_fee import TokenAmount
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy_v2.controllers.controller_base import ControllerBase, ControllerConfigBase
from hummingbot.strategy_v2.executors.data_types import ConnectorPair
from hummingbot.strategy_v2.executors.order_executor.data_types import ExecutionStrategy, OrderExecutorConfig
from hummingbot.strategy_v2.executors.position_executor.data_types import PositionExecutorConfig, TripleBarrierConfig
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, ExecutorAction, StopExecutorAction
from hummingbot.strategy_v2.models.executors import CloseType


class PMMConfig(ControllerConfigBase):
    """
    This class represents the base configuration for a market making controller.
    """
    controller_type: str = "generic"
    controller_name: str = "pmm"
    candles_config: List[CandlesConfig] = []
    connector_name: str = Field(
        default="binance",
        json_schema_extra={
            "prompt_on_new": True,
            "prompt": "Enter the name of the connector to use (e.g., binance):",
        }
    )
    trading_pair: str = Field(
        default="BTC-FDUSD",
        json_schema_extra={
            "prompt_on_new": True,
            "prompt": "Enter the trading pair to trade on (e.g., BTC-FDUSD):",
        }
    )
    portfolio_allocation: Decimal = Field(
        default=Decimal("0.05"),
        json_schema_extra={
            "prompt_on_new": True,
            "prompt": "Enter the portfolio allocation (e.g., 0.05 for 5%):",
        }
    )
    target_base_pct: Decimal = Field(
        default=Decimal("0.2"),
        json_schema_extra={
            "prompt_on_new": True,
            "prompt": "Enter the target base percentage (e.g., 0.2 for 20%):",
        }
    )
    min_base_pct: Decimal = Field(
        default=Decimal("0.1"),
        json_schema_extra={
            "prompt_on_new": True,
            "prompt": "Enter the minimum base percentage (e.g., 0.1 for 10%):",
        }
    )
    max_base_pct: Decimal = Field(
        default=Decimal("0.4"),
        json_schema_extra={
            "prompt_on_new": True,
            "prompt": "Enter the maximum base percentage (e.g., 0.4 for 40%):",
        }
    )
    buy_spreads: List[float] = Field(
        default="0.01,0.02",
        json_schema_extra={
            "prompt_on_new": True, "is_updatable": True,
            "prompt": "Enter a comma-separated list of buy spreads (e.g., '0.01, 0.02'):",
        }
    )
    sell_spreads: List[float] = Field(
        default="0.01,0.02",
        json_schema_extra={
            "prompt_on_new": True, "is_updatable": True,
            "prompt": "Enter a comma-separated list of sell spreads (e.g., '0.01, 0.02'):",
        }
    )
    buy_amounts_pct: Union[List[Decimal], None] = Field(
        default=None,
        json_schema_extra={
            "prompt_on_new": True, "is_updatable": True,
            "prompt": "Enter a comma-separated list of buy amounts as percentages (e.g., '50, 50'), or leave blank to distribute equally:",
        }
    )
    sell_amounts_pct: Union[List[Decimal], None] = Field(
        default=None,
        json_schema_extra={
            "prompt_on_new": True, "is_updatable": True,
            "prompt": "Enter a comma-separated list of sell amounts as percentages (e.g., '50, 50'), or leave blank to distribute equally:",
        }
    )
    executor_refresh_time: int = Field(
        default=60 * 5,
        json_schema_extra={
            "prompt_on_new": True, "is_updatable": True,
            "prompt": "Enter the refresh time in seconds for executors (e.g., 300 for 5 minutes):",
        }
    )
    cooldown_time: int = Field(
        default=15,
        json_schema_extra={
            "prompt_on_new": True, "is_updatable": True,
            "prompt": "Enter the cooldown time in seconds between after replacing an executor that traded (e.g., 15):",
        }
    )
    leverage: int = Field(
        default=20,
        json_schema_extra={
            "prompt_on_new": True, "is_updatable": True,
            "prompt": "Enter the leverage to use for trading (e.g., 20 for 20x leverage). Set it to 1 for spot trading:",
        }
    )
    position_mode: PositionMode = Field(default="HEDGE")
    take_profit: Optional[Decimal] = Field(
        default=Decimal("0.02"), gt=0,
        json_schema_extra={
            "prompt_on_new": True, "is_updatable": True,
            "prompt": "Enter the take profit as a decimal (e.g., 0.02 for 2%):",
        }
    )
    take_profit_order_type: Optional[OrderType] = Field(
        default="LIMIT_MAKER",
        json_schema_extra={
            "prompt_on_new": True, "is_updatable": True,
            "prompt": "Enter the order type for take profit (e.g., LIMIT_MAKER):",
        }
    )
    max_skew: Decimal = Field(
        default=Decimal("1.0"),
        json_schema_extra={
            "prompt_on_new": True, "is_updatable": True,
            "prompt": "Enter the maximum skew factor (e.g., 1.0):",
        }
    )
    global_take_profit: Decimal = Decimal("0.02")

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
            open_order_type=OrderType.LIMIT_MAKER,  # Defaulting to LIMIT as is a Maker Controller
            take_profit_order_type=self.take_profit_order_type,
            stop_loss_order_type=OrderType.MARKET,  # Defaulting to MARKET as per requirement
            time_limit_order_type=OrderType.MARKET  # Defaulting to MARKET as per requirement
        )

    def update_parameters(self, trade_type: TradeType, new_spreads: Union[List[float], str], new_amounts_pct: Optional[Union[List[int], str]] = None):
        spreads_field = 'buy_spreads' if trade_type == TradeType.BUY else 'sell_spreads'
        amounts_pct_field = 'buy_amounts_pct' if trade_type == TradeType.BUY else 'sell_amounts_pct'

        setattr(self, spreads_field, self.parse_spreads(new_spreads))
        if new_amounts_pct is not None:
            setattr(self, amounts_pct_field, self.parse_and_validate_amounts(new_amounts_pct, self.__dict__, self.__fields__[amounts_pct_field]))
        else:
            setattr(self, amounts_pct_field, [1 for _ in getattr(self, spreads_field)])

    def get_spreads_and_amounts_in_quote(self, trade_type: TradeType) -> Tuple[List[float], List[float]]:
        buy_amounts_pct = getattr(self, 'buy_amounts_pct')
        sell_amounts_pct = getattr(self, 'sell_amounts_pct')

        # Calculate total percentages across buys and sells
        total_pct = sum(buy_amounts_pct) + sum(sell_amounts_pct)

        # Normalize amounts_pct based on total percentages
        if trade_type == TradeType.BUY:
            normalized_amounts_pct = [amt_pct / total_pct for amt_pct in buy_amounts_pct]
        else:  # TradeType.SELL
            normalized_amounts_pct = [amt_pct / total_pct for amt_pct in sell_amounts_pct]

        spreads = getattr(self, f'{trade_type.name.lower()}_spreads')
        return spreads, [amt_pct * self.total_amount_quote * self.portfolio_allocation for amt_pct in normalized_amounts_pct]

    def update_markets(self, markets: Dict[str, Set[str]]) -> Dict[str, Set[str]]:
        if self.connector_name not in markets:
            markets[self.connector_name] = set()
        markets[self.connector_name].add(self.trading_pair)
        return markets


class PMM(ControllerBase):
    """
    This class represents the base class for a market making controller.
    """

    def __init__(self, config: PMMConfig, *args, **kwargs):
        super().__init__(config, *args, **kwargs)
        self.config = config
        self.market_data_provider.initialize_rate_sources([ConnectorPair(
            connector_name=config.connector_name, trading_pair=config.trading_pair)])

    def determine_executor_actions(self) -> List[ExecutorAction]:
        """
        Determine actions based on the provided executor handler report.
        """
        actions = []
        actions.extend(self.create_actions_proposal())
        actions.extend(self.stop_actions_proposal())
        return actions

    def create_actions_proposal(self) -> List[ExecutorAction]:
        """
        Create actions proposal based on the current state of the controller.
        """
        create_actions = []
        if self.processed_data["current_base_pct"] > self.config.target_base_pct and self.processed_data["unrealized_pnl_pct"] > self.config.global_take_profit:
            # Create a global take profit executor
            create_actions.append(CreateExecutorAction(
                controller_id=self.config.id,
                executor_config=OrderExecutorConfig(
                    timestamp=self.market_data_provider.time(),
                    connector_name=self.config.connector_name,
                    trading_pair=self.config.trading_pair,
                    side=TradeType.SELL,
                    amount=self.processed_data["position_amount"],
                    execution_strategy=ExecutionStrategy.MARKET,
                    price=self.processed_data["reference_price"],
                )
            ))
            return create_actions
        levels_to_execute = self.get_levels_to_execute()
        # Pre-calculate all spreads and amounts for buy and sell sides
        buy_spreads, buy_amounts_quote = self.config.get_spreads_and_amounts_in_quote(TradeType.BUY)
        sell_spreads, sell_amounts_quote = self.config.get_spreads_and_amounts_in_quote(TradeType.SELL)
        reference_price = Decimal(self.processed_data["reference_price"])
        # Get current position info for skew calculation
        current_pct = self.processed_data["current_base_pct"]
        min_pct = self.config.min_base_pct
        max_pct = self.config.max_base_pct
        # Calculate skew factors (0 to 1) - how much to scale orders
        if max_pct > min_pct:  # Prevent division by zero
            # For buys: full size at min_pct, decreasing as we approach max_pct
            buy_skew = (max_pct - current_pct) / (max_pct - min_pct)
            # For sells: full size at max_pct, decreasing as we approach min_pct
            sell_skew = (current_pct - min_pct) / (max_pct - min_pct)
            # Ensure values stay between 0.2 and 1.0 (never go below 20% of original size)
            buy_skew = max(min(buy_skew, Decimal("1.0")), self.config.max_skew)
            sell_skew = max(min(sell_skew, Decimal("1.0")), self.config.max_skew)
        else:
            buy_skew = sell_skew = Decimal("1.0")
        # Create executors for each level
        for level_id in levels_to_execute:
            trade_type = self.get_trade_type_from_level_id(level_id)
            level = self.get_level_from_level_id(level_id)
            if trade_type == TradeType.BUY:
                spread_in_pct = Decimal(buy_spreads[level]) * Decimal(self.processed_data["spread_multiplier"])
                amount_quote = Decimal(buy_amounts_quote[level])
                skew = buy_skew
            else:  # TradeType.SELL
                spread_in_pct = Decimal(sell_spreads[level]) * Decimal(self.processed_data["spread_multiplier"])
                amount_quote = Decimal(sell_amounts_quote[level])
                skew = sell_skew
            # Calculate price
            side_multiplier = Decimal("-1") if trade_type == TradeType.BUY else Decimal("1")
            price = reference_price * (Decimal("1") + side_multiplier * spread_in_pct)
            # Calculate amount with skew applied
            amount = self.market_data_provider.quantize_order_amount(self.config.connector_name,
                                                                     self.config.trading_pair,
                                                                     (amount_quote / price) * skew)
            if amount == Decimal("0"):
                self.logger().warning(f"The amount of the level {level_id} is 0. Skipping.")
            executor_config = self.get_executor_config(level_id, price, amount)
            if executor_config is not None:
                create_actions.append(CreateExecutorAction(
                    controller_id=self.config.id,
                    executor_config=executor_config
                ))
        return create_actions

    def get_levels_to_execute(self) -> List[str]:
        working_levels = self.filter_executors(
            executors=self.executors_info,
            filter_func=lambda x: x.is_active or (x.close_type == CloseType.STOP_LOSS and self.market_data_provider.time() - x.close_timestamp < self.config.cooldown_time)
        )
        working_levels_ids = [executor.custom_info["level_id"] for executor in working_levels]
        return self.get_not_active_levels_ids(working_levels_ids)

    def stop_actions_proposal(self) -> List[ExecutorAction]:
        """
        Create a list of actions to stop the executors based on order refresh and early stop conditions.
        """
        stop_actions = []
        stop_actions.extend(self.executors_to_refresh())
        stop_actions.extend(self.executors_to_early_stop())
        return stop_actions

    def executors_to_refresh(self) -> List[ExecutorAction]:
        executors_to_refresh = self.filter_executors(
            executors=self.executors_info,
            filter_func=lambda x: not x.is_trading and x.is_active and self.market_data_provider.time() - x.timestamp > self.config.executor_refresh_time)
        return [StopExecutorAction(
            controller_id=self.config.id,
            keep_position=True,
            executor_id=executor.id) for executor in executors_to_refresh]

    def executors_to_early_stop(self) -> List[ExecutorAction]:
        """
        Get the executors to early stop based on the current state of market data. This method can be overridden to
        implement custom behavior.
        """
        executors_to_early_stop = self.filter_executors(
            executors=self.executors_info,
            filter_func=lambda x: x.is_active and x.is_trading and self.market_data_provider.time() - x.custom_info["open_order_last_update"] > self.config.cooldown_time)
        return [StopExecutorAction(
            controller_id=self.config.id,
            keep_position=True,
            executor_id=executor.id) for executor in executors_to_early_stop]

    async def update_processed_data(self):
        """
        Update the processed data for the controller. This method should be reimplemented to modify the reference price
        and spread multiplier based on the market data. By default, it will update the reference price as mid price and
        the spread multiplier as 1.
        """
        reference_price = self.market_data_provider.get_price_by_type(self.config.connector_name,
                                                                      self.config.trading_pair, PriceType.MidPrice)
        position_held = next((position for position in self.positions_held if
                              (position.trading_pair == self.config.trading_pair) &
                              (position.connector_name == self.config.connector_name)), None)
        target_position = self.config.total_amount_quote * self.config.target_base_pct
        if position_held is not None:
            position_amount = position_held.amount
            current_base_pct = position_held.amount_quote / self.config.total_amount_quote
            deviation = (target_position - position_held.amount_quote) / target_position
            unrealized_pnl_pct = position_held.unrealized_pnl_quote / position_held.amount_quote if position_held.amount_quote != 0 else Decimal("0")
        else:
            position_amount = 0
            current_base_pct = 0
            deviation = 1
            unrealized_pnl_pct = 0

        self.processed_data = {"reference_price": Decimal(reference_price), "spread_multiplier": Decimal("1"),
                               "deviation": deviation, "current_base_pct": current_base_pct,
                               "unrealized_pnl_pct": unrealized_pnl_pct, "position_amount": position_amount}

    def get_executor_config(self, level_id: str, price: Decimal, amount: Decimal):
        """
        Get the executor config for a given level id.
        """
        trade_type = self.get_trade_type_from_level_id(level_id)
        level_multiplier = self.get_level_from_level_id(level_id) + 1
        return PositionExecutorConfig(
            timestamp=self.market_data_provider.time(),
            level_id=level_id,
            connector_name=self.config.connector_name,
            trading_pair=self.config.trading_pair,
            entry_price=price,
            amount=amount,
            triple_barrier_config=self.config.triple_barrier_config.new_instance_with_adjusted_volatility(level_multiplier),
            leverage=self.config.leverage,
            side=trade_type,
        )

    def get_level_id_from_side(self, trade_type: TradeType, level: int) -> str:
        """
        Get the level id based on the trade type and the level.
        """
        return f"{trade_type.name.lower()}_{level}"

    def get_trade_type_from_level_id(self, level_id: str) -> TradeType:
        return TradeType.BUY if level_id.startswith("buy") else TradeType.SELL

    def get_level_from_level_id(self, level_id: str) -> int:
        return int(level_id.split('_')[1])

    def get_not_active_levels_ids(self, active_levels_ids: List[str]) -> List[str]:
        """
        Get the levels to execute based on the current state of the controller.
        """
        buy_ids_missing = [self.get_level_id_from_side(TradeType.BUY, level) for level in range(len(self.config.buy_spreads))
                           if self.get_level_id_from_side(TradeType.BUY, level) not in active_levels_ids]
        sell_ids_missing = [self.get_level_id_from_side(TradeType.SELL, level) for level in range(len(self.config.sell_spreads))
                            if self.get_level_id_from_side(TradeType.SELL, level) not in active_levels_ids]
        if self.processed_data["current_base_pct"] < self.config.min_base_pct:
            return buy_ids_missing
        elif self.processed_data["current_base_pct"] > self.config.max_base_pct:
            return sell_ids_missing
        return buy_ids_missing + sell_ids_missing

    def get_balance_requirements(self) -> List[TokenAmount]:
        """
        Get the balance requirements for the controller.
        """
        base_asset, quote_asset = self.config.trading_pair.split("-")
        _, amounts_quote = self.config.get_spreads_and_amounts_in_quote(TradeType.BUY)
        _, amounts_base = self.config.get_spreads_and_amounts_in_quote(TradeType.SELL)
        return [TokenAmount(base_asset, Decimal(sum(amounts_base) / self.processed_data["reference_price"])),
                TokenAmount(quote_asset, Decimal(sum(amounts_quote)))]

    def to_format_status(self) -> List[str]:
        """
        Get the status of the controller in a formatted way with ASCII visualizations.
        """
        status = []
        status.append(f"Controller ID: {self.config.id}")
        status.append(f"Connector: {self.config.connector_name}")
        status.append(f"Trading Pair: {self.config.trading_pair}")
        status.append(f"Portfolio Allocation: {self.config.portfolio_allocation}")
        status.append(f"Reference Price: {self.processed_data['reference_price']}")
        status.append(f"Spread Multiplier: {self.processed_data['spread_multiplier']}")

        # Base percentage visualization
        base_pct = self.processed_data['current_base_pct']
        min_pct = self.config.min_base_pct
        max_pct = self.config.max_base_pct
        target_pct = self.config.target_base_pct
        # Create base percentage bar
        bar_width = 50
        filled_width = int(base_pct * bar_width)
        min_pos = int(min_pct * bar_width)
        max_pos = int(max_pct * bar_width)
        target_pos = int(target_pct * bar_width)
        base_bar = "Base %: ["
        for i in range(bar_width):
            if i == filled_width:
                base_bar += "O"  # Current position
            elif i == min_pos:
                base_bar += "m"  # Min threshold
            elif i == max_pos:
                base_bar += "M"  # Max threshold
            elif i == target_pos:
                base_bar += "T"  # Target threshold
            elif i < filled_width:
                base_bar += "="
            else:
                base_bar += " "
        base_bar += f"] {base_pct:.2%}"
        status.append(base_bar)
        status.append(f"Min: {min_pct:.2%} | Target: {target_pct:.2%} | Max: {max_pct:.2%}")
        # Skew visualization
        skew = base_pct - target_pct
        skew_pct = skew / target_pct if target_pct != 0 else Decimal('0')
        max_skew = getattr(self.config, 'max_skew', Decimal('0.0'))
        skew_bar_width = 30
        skew_bar = "Skew:    "
        center = skew_bar_width // 2
        skew_pos = center + int(skew_pct * center * 2)
        skew_pos = max(0, min(skew_bar_width, skew_pos))
        for i in range(skew_bar_width):
            if i == center:
                skew_bar += "|"  # Center line
            elif i == skew_pos:
                skew_bar += "*"  # Current skew
            else:
                skew_bar += "-"
        skew_bar += f" {skew_pct:+.2%} (max: {max_skew:.2%})"
        status.append(skew_bar)
        # Active executors summary
        status.append("\nActive Executors:")
        active_buy = sum(1 for info in self.executors_info if self.get_trade_type_from_level_id(info.custom_info["level_id"]) == TradeType.BUY)
        active_sell = sum(1 for info in self.executors_info if self.get_trade_type_from_level_id(info.custom_info["level_id"]) == TradeType.SELL)
        status.append(f"Total: {len(self.executors_info)} (Buy: {active_buy}, Sell: {active_sell})")
        # Deviation info
        if 'deviation' in self.processed_data:
            deviation = self.processed_data['deviation']
            status.append(f"Deviation: {deviation:.4f}")
        return status
