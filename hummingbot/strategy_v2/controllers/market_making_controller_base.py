from decimal import Decimal
from typing import Dict, List, Optional, Set, Tuple, Union

from pydantic import Field, field_validator
from pydantic_core.core_schema import ValidationInfo

from hummingbot.core.data_type.common import OrderType, PositionMode, PriceType, TradeType
from hummingbot.core.data_type.trade_fee import TokenAmount
from hummingbot.strategy_v2.controllers.controller_base import ControllerBase, ControllerConfigBase
from hummingbot.strategy_v2.executors.data_types import ConnectorPair
from hummingbot.strategy_v2.executors.position_executor.data_types import TrailingStop, TripleBarrierConfig
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, ExecutorAction, StopExecutorAction
from hummingbot.strategy_v2.models.executors import CloseType


class MarketMakingControllerConfigBase(ControllerConfigBase):
    """
    This class represents the base configuration for a market making controller.
    """
    controller_type: str = "market_making"
    connector_name: str = Field(
        default="binance_perpetual",
        json_schema_extra={
            "prompt": "Enter the connector name (e.g., binance_perpetual): ",
            "prompt_on_new": True}
    )
    trading_pair: str = Field(
        default="WLD-USDT",
        json_schema_extra={
            "prompt": "Enter the trading pair to trade on (e.g., WLD-USDT): ",
            "prompt_on_new": True}
    )
    buy_spreads: List[float] = Field(
        default="0.01,0.02",
        json_schema_extra={
            "prompt": "Enter a comma-separated list of buy spreads (e.g., '0.01, 0.02'): ",
            "prompt_on_new": True, "is_updatable": True}
    )
    sell_spreads: List[float] = Field(
        default="0.01,0.02",
        json_schema_extra={
            "prompt": "Enter a comma-separated list of sell spreads (e.g., '0.01, 0.02'): ",
            "prompt_on_new": True, "is_updatable": True}
    )
    buy_amounts_pct: Union[List[Decimal], None] = Field(
        default=None,
        json_schema_extra={
            "prompt": "Enter a comma-separated list of buy amounts as percentages (e.g., '50, 50'), or leave blank to distribute equally: ",
            "prompt_on_new": True, "is_updatable": True}
    )
    sell_amounts_pct: Union[List[Decimal], None] = Field(
        default=None,
        json_schema_extra={
            "prompt": "Enter a comma-separated list of sell amounts as percentages (e.g., '50, 50'), or leave blank to distribute equally: ",
            "prompt_on_new": True, "is_updatable": True}
    )
    executor_refresh_time: int = Field(
        default=60 * 5,
        json_schema_extra={
            "prompt": "Enter the refresh time in seconds for executors (e.g., 300 for 5 minutes): ",
            "prompt_on_new": True, "is_updatable": True}
    )
    cooldown_time: int = Field(
        default=15,
        json_schema_extra={
            "prompt": "Enter the cooldown time in seconds between replacing an executor that traded (e.g., 15): ",
            "prompt_on_new": True, "is_updatable": True}
    )
    leverage: int = Field(
        default=20,
        json_schema_extra={
            "prompt": "Enter the leverage to use for trading (e.g., 20 for 20x leverage). Set it to 1 for spot trading: ",
            "prompt_on_new": True}
    )
    position_mode: PositionMode = Field(
        default="HEDGE",
        json_schema_extra={"prompt": "Enter the position mode (HEDGE/ONEWAY): "}
    )
    # Triple Barrier Configuration
    stop_loss: Optional[Decimal] = Field(
        default=Decimal("0.03"), gt=0,
        json_schema_extra={
            "prompt": "Enter the stop loss (as a decimal, e.g., 0.03 for 3%): ",
            "prompt_on_new": True, "is_updatable": True}
    )
    take_profit: Optional[Decimal] = Field(
        default=Decimal("0.02"), gt=0,
        json_schema_extra={
            "prompt": "Enter the take profit (as a decimal, e.g., 0.02 for 2%): ",
            "prompt_on_new": True, "is_updatable": True}
    )
    time_limit: Optional[int] = Field(
        default=60 * 45, gt=0,
        json_schema_extra={
            "prompt": "Enter the time limit in seconds (e.g., 2700 for 45 minutes): ",
            "prompt_on_new": True, "is_updatable": True}
    )
    take_profit_order_type: OrderType = Field(
        default=OrderType.LIMIT,
        json_schema_extra={
            "prompt": "Enter the order type for take profit (LIMIT/MARKET): ",
            "prompt_on_new": True, "is_updatable": True}
    )
    trailing_stop: Optional[TrailingStop] = Field(
        default=None,
        json_schema_extra={
            "prompt": "Enter the trailing stop as activation_price,trailing_delta (e.g., 0.015,0.003): ",
            "prompt_on_new": True, "is_updatable": True},
    )

    @field_validator("trailing_stop", mode="before")
    @classmethod
    def parse_trailing_stop(cls, v):
        if isinstance(v, str):
            if v == "":
                return None
            activation_price, trailing_delta = v.split(",")
            return TrailingStop(activation_price=Decimal(activation_price), trailing_delta=Decimal(trailing_delta))
        return v

    @field_validator("time_limit", "stop_loss", "take_profit", mode="before")
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
            cleaned_str = v.replace("OrderType.", "").upper()
            if cleaned_str in OrderType.__members__:
                return OrderType[cleaned_str]
        elif isinstance(v, int):
            try:
                return OrderType(v)
            except ValueError:
                pass
        raise ValueError(f"Invalid order type: {v}. Valid options are: {', '.join(OrderType.__members__)}")

    @field_validator('position_mode', mode="before")
    @classmethod
    def validate_position_mode(cls, v: str) -> PositionMode:
        if isinstance(v, str):
            if v.upper() in PositionMode.__members__:
                return PositionMode[v.upper()]
            raise ValueError(f"Invalid position mode: {v}. Valid options are: {', '.join(PositionMode.__members__)}")
        return v

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

    @property
    def triple_barrier_config(self) -> TripleBarrierConfig:
        return TripleBarrierConfig(
            stop_loss=self.stop_loss,
            take_profit=self.take_profit,
            time_limit=self.time_limit,
            trailing_stop=self.trailing_stop,
            open_order_type=OrderType.LIMIT,  # Defaulting to LIMIT as is a Maker Controller
            take_profit_order_type=self.take_profit_order_type,
            stop_loss_order_type=OrderType.MARKET,  # Defaulting to MARKET as per requirement
            time_limit_order_type=OrderType.MARKET  # Defaulting to MARKET as per requirement
        )

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
        return spreads, [amt_pct * self.total_amount_quote for amt_pct in normalized_amounts_pct]

    def update_markets(self, markets: Dict[str, Set[str]]) -> Dict[str, Set[str]]:
        if self.connector_name not in markets:
            markets[self.connector_name] = set()
        markets[self.connector_name].add(self.trading_pair)
        return markets


class MarketMakingControllerBase(ControllerBase):
    """
    This class represents the base class for a market making controller.
    """

    def __init__(self, config: MarketMakingControllerConfigBase, *args, **kwargs):
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
        levels_to_execute = self.get_levels_to_execute()
        for level_id in levels_to_execute:
            price, amount = self.get_price_and_amount(level_id)
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
            executor_id=executor.id) for executor in executors_to_refresh]

    def executors_to_early_stop(self) -> List[ExecutorAction]:
        """
        Get the executors to early stop based on the current state of market data. This method can be overridden to
        implement custom behavior.
        """
        return []

    async def update_processed_data(self):
        """
        Update the processed data for the controller. This method should be reimplemented to modify the reference price
        and spread multiplier based on the market data. By default, it will update the reference price as mid price and
        the spread multiplier as 1.
        """
        reference_price = self.market_data_provider.get_price_by_type(self.config.connector_name,
                                                                      self.config.trading_pair, PriceType.MidPrice)
        self.processed_data = {"reference_price": Decimal(reference_price), "spread_multiplier": Decimal("1")}

    def get_executor_config(self, level_id: str, price: Decimal, amount: Decimal):
        """
        Get the executor config for a given level id.
        """
        raise NotImplementedError

    def get_price_and_amount(self, level_id: str) -> Tuple[Decimal, Decimal]:
        """
        Get the spread and amount in quote for a given level id.
        """
        level = self.get_level_from_level_id(level_id)
        trade_type = self.get_trade_type_from_level_id(level_id)
        spreads, amounts_quote = self.config.get_spreads_and_amounts_in_quote(trade_type)
        reference_price = Decimal(self.processed_data["reference_price"])
        spread_in_pct = Decimal(spreads[int(level)]) * Decimal(self.processed_data["spread_multiplier"])
        side_multiplier = Decimal("-1") if trade_type == TradeType.BUY else Decimal("1")
        order_price = reference_price * (1 + side_multiplier * spread_in_pct)
        return order_price, Decimal(amounts_quote[int(level)]) / order_price

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
