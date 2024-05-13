import os
from decimal import Decimal
from typing import Dict, List

from pydantic import Field, validator

from hummingbot.client.config.config_data_types import ClientFieldData
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.clock import Clock
from hummingbot.core.data_type.common import OrderType, PositionMode, PriceType, TradeType
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy.strategy_v2_base import StrategyV2Base, StrategyV2ConfigBase
from hummingbot.strategy_v2.executors.position_executor.data_types import PositionExecutorConfig, TripleBarrierConfig
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, StopExecutorAction


class PMMWithPositionExecutorConfig(StrategyV2ConfigBase):
    script_file_name: str = Field(default_factory=lambda: os.path.basename(__file__))
    candles_config: List[CandlesConfig] = []
    controllers_config: List[str] = []
    order_amount_quote: Decimal = Field(
        default=30, gt=0,
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter the amount of quote asset to be used per order (e.g. 30): ",
            prompt_on_new=True))
    executor_refresh_time: int = Field(
        default=20, gt=0,
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter the time in seconds to refresh the executor (e.g. 20): ",
            prompt_on_new=True))
    spread: Decimal = Field(
        default=Decimal("0.003"), gt=0,
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter the spread (e.g. 0.003): ",
            prompt_on_new=True))
    leverage: int = Field(
        default=20, gt=0,
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter the leverage (e.g. 20): ",
            prompt_on_new=True))
    position_mode: PositionMode = Field(
        default="HEDGE",
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter the position mode (HEDGE/ONEWAY): ",
            prompt_on_new=True
        )
    )
    # Triple Barrier Configuration
    stop_loss: Decimal = Field(
        default=Decimal("0.03"), gt=0,
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter the stop loss (as a decimal, e.g., 0.03 for 3%): ",
            prompt_on_new=True))
    take_profit: Decimal = Field(
        default=Decimal("0.01"), gt=0,
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter the take profit (as a decimal, e.g., 0.01 for 1%): ",
            prompt_on_new=True))
    time_limit: int = Field(
        default=60 * 45, gt=0,
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter the time limit in seconds (e.g., 2700 for 45 minutes): ",
            prompt_on_new=True))
    take_profit_order_type: OrderType = Field(
        default="LIMIT",
        client_data=ClientFieldData(
            prompt=lambda mi: "Enter the order type for taking profit (LIMIT/MARKET): ",
            prompt_on_new=True))

    @validator('take_profit_order_type', pre=True, allow_reuse=True)
    def validate_order_type(cls, v) -> OrderType:
        if isinstance(v, OrderType):
            return v
        elif isinstance(v, str):
            if v.upper() in OrderType.__members__:
                return OrderType[v.upper()]
        elif isinstance(v, int):
            try:
                return OrderType(v)
            except ValueError:
                pass
        raise ValueError(f"Invalid order type: {v}. Valid options are: {', '.join(OrderType.__members__)}")

    @property
    def triple_barrier_config(self) -> TripleBarrierConfig:
        return TripleBarrierConfig(
            stop_loss=self.stop_loss,
            take_profit=self.take_profit,
            time_limit=self.time_limit,
            open_order_type=OrderType.LIMIT,
            take_profit_order_type=self.take_profit_order_type,
            stop_loss_order_type=OrderType.MARKET,  # Defaulting to MARKET as per requirement
            time_limit_order_type=OrderType.MARKET  # Defaulting to MARKET as per requirement
        )

    @validator('position_mode', pre=True, allow_reuse=True)
    def validate_position_mode(cls, v: str) -> PositionMode:
        if v.upper() in PositionMode.__members__:
            return PositionMode[v.upper()]
        raise ValueError(f"Invalid position mode: {v}. Valid options are: {', '.join(PositionMode.__members__)}")


class PMMSingleLevel(StrategyV2Base):
    account_config_set = False

    def __init__(self, connectors: Dict[str, ConnectorBase], config: PMMWithPositionExecutorConfig):
        super().__init__(connectors, config)
        self.config = config  # Only for type checking

    def start(self, clock: Clock, timestamp: float) -> None:
        """
        Start the strategy.
        :param clock: Clock to use.
        :param timestamp: Current time.
        """
        self._last_timestamp = timestamp
        self.apply_initial_setting()

    def create_actions_proposal(self) -> List[CreateExecutorAction]:
        """
        Create actions proposal based on the current state of the executors.
        """
        create_actions = []

        all_executors = self.get_all_executors()
        active_buy_position_executors = self.filter_executors(
            executors=all_executors,
            filter_func=lambda x: x.side == TradeType.BUY and x.type == "position_executor" and x.is_active)

        active_sell_position_executors = self.filter_executors(
            executors=all_executors,
            filter_func=lambda x: x.side == TradeType.SELL and x.type == "position_executor" and x.is_active)

        for connector_name in self.connectors:
            for trading_pair in self.market_data_provider.get_trading_pairs(connector_name):
                # Get mid-price
                mid_price = self.market_data_provider.get_price_by_type(connector_name, trading_pair, PriceType.MidPrice)
                len_active_buys = len(self.filter_executors(
                    executors=active_buy_position_executors,
                    filter_func=lambda x: x.config.trading_pair == trading_pair))
                # Evaluate if we need to create new executors and create the actions
                if len_active_buys == 0:
                    order_price = mid_price * (1 - self.config.spread)
                    order_amount = self.config.order_amount_quote / order_price
                    create_actions.append(CreateExecutorAction(
                        executor_config=PositionExecutorConfig(
                            timestamp=self.current_timestamp,
                            trading_pair=trading_pair,
                            connector_name=connector_name,
                            side=TradeType.BUY,
                            amount=order_amount,
                            entry_price=order_price,
                            triple_barrier_config=self.config.triple_barrier_config,
                            leverage=self.config.leverage
                        )
                    ))
                len_active_sells = len(self.filter_executors(
                    executors=active_sell_position_executors,
                    filter_func=lambda x: x.config.trading_pair == trading_pair))
                if len_active_sells == 0:
                    order_price = mid_price * (1 + self.config.spread)
                    order_amount = self.config.order_amount_quote / order_price
                    create_actions.append(CreateExecutorAction(
                        executor_config=PositionExecutorConfig(
                            timestamp=self.current_timestamp,
                            trading_pair=trading_pair,
                            connector_name=connector_name,
                            side=TradeType.SELL,
                            amount=order_amount,
                            entry_price=order_price,
                            triple_barrier_config=self.config.triple_barrier_config,
                            leverage=self.config.leverage
                        )
                    ))
        return create_actions

    def stop_actions_proposal(self) -> List[StopExecutorAction]:
        """
        Create a list of actions to stop the executors based on order refresh and early stop conditions.
        """
        stop_actions = []
        stop_actions.extend(self.executors_to_refresh())
        stop_actions.extend(self.executors_to_early_stop())
        return stop_actions

    def executors_to_refresh(self) -> List[StopExecutorAction]:
        """
        Create a list of actions to stop the executors that need to be refreshed.
        """
        all_executors = self.get_all_executors()
        executors_to_refresh = self.filter_executors(
            executors=all_executors,
            filter_func=lambda x: not x.is_trading and x.is_active and self.current_timestamp - x.timestamp > self.config.executor_refresh_time)

        return [StopExecutorAction(executor_id=executor.id) for executor in executors_to_refresh]

    def executors_to_early_stop(self) -> List[StopExecutorAction]:
        """
        Create a list of actions to stop the executors that need to be early stopped based on signals.
        This is a simple example, in a real strategy you would use signals from the market data provider.
        """
        return []

    def apply_initial_setting(self):
        if not self.account_config_set:
            for connector_name, connector in self.connectors.items():
                if self.is_perpetual(connector_name):
                    connector.set_position_mode(self.config.position_mode)
                    for trading_pair in self.market_data_provider.get_trading_pairs(connector_name):
                        connector.set_leverage(trading_pair, self.config.leverage)
            self.account_config_set = True
