from decimal import Decimal
from typing import Dict

from pydantic import Field

from hummingbot.client.config.config_data_types import BaseClientModel, ClientFieldData
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionSide
from hummingbot.data_feed.candles_feed.candles_factory import CandlesConfig
from hummingbot.smart_components.controllers.dman_v3 import DManV3, DManV3Config
from hummingbot.smart_components.strategy_frameworks.data_types import ExecutorHandlerStatus, TripleBarrierConf
from hummingbot.smart_components.strategy_frameworks.market_making.market_making_executor_handler import (
    MarketMakingExecutorHandler,
)
from hummingbot.smart_components.utils.distributions import Distributions
from hummingbot.smart_components.utils.order_level_builder import OrderLevelBuilder
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class DManV3ScriptConfig(BaseClientModel):
    exchange: str = Field("binance_perpetual",
                          client_data=ClientFieldData(prompt_on_new=True,
                                                      prompt=lambda mi: "The exchange to trade on"))
    trading_pairs: str = Field("DOGE-USDT,INJ-USDT",
                               client_data=ClientFieldData(prompt_on_new=True,
                                                           prompt=lambda mi: "The trading pairs to trade on separated by comma"))
    leverage: int = Field(1, client_data=ClientFieldData(prompt_on_new=True,
                                                         prompt=lambda mi: "The leverage to use for the perpetual market"))
    candles_exchange: str = Field("binance_perpetual",
                                  client_data=ClientFieldData(prompt_on_new=True,
                                                              prompt=lambda mi: "The exchange to get the candles from"))
    candles_interval: str = Field("30m",
                                  client_data=ClientFieldData(prompt_on_new=True,
                                                              prompt=lambda mi: "The interval of the candles"))
    candles_max_records: int = Field(500, client_data=ClientFieldData(prompt_on_new=False,
                                                                      prompt=lambda mi: "The max records of the candles"))
    bollinger_band_length: int = Field(200, client_data=ClientFieldData(prompt_on_new=True,
                                                                        prompt=lambda mi: "The length of the Bollinger Bands"))
    bollinger_band_std: float = Field(2.0, client_data=ClientFieldData(prompt_on_new=False,
                                                                       prompt=lambda mi: "The standard deviation of the Bollinger Bands"))
    order_amount: Decimal = Field(20, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "The order amount in quote asset"))
    n_levels: int = Field(5, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "The number of order levels"))
    start_spread: float = Field(1.0, client_data=ClientFieldData(
        prompt_on_new=True,
        prompt=lambda mi: "The spread of the first order based on the value of the bollinger band, 1.0 == upper/lower band"))
    step_between_orders: float = Field(0.1, client_data=ClientFieldData(
        prompt_on_new=True,
        prompt=lambda mi: "The step between orders based on the value of the bollinger band"))
    stop_loss: Decimal = Field(0.2, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "The stop loss"))
    take_profit: Decimal = Field(0.06, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "The take profit"))
    time_limit: int = Field(60 * 60 * 24 * 3, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "The time limit"))
    trailing_stop_activation_price_delta: Decimal = Field(0.01, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "The trailing stop activation price delta"))
    trailing_stop_trailing_delta: Decimal = Field(0.003, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "The trailing stop activation price delta"))
    side_filter: bool = Field(True, client_data=ClientFieldData(prompt_on_new=False, prompt=lambda mi: "The side filter"))
    dynamic_spread_factor: bool = Field(True, client_data=ClientFieldData(prompt_on_new=False, prompt=lambda mi: "The dynamic spread factor"))
    dynamic_target_spread: bool = Field(True, client_data=ClientFieldData(prompt_on_new=False, prompt=lambda mi: "The dynamic target spread"))
    smart_activation: bool = Field(True, client_data=ClientFieldData(prompt_on_new=False, prompt=lambda mi: "The smart activation"))
    activation_threshold: Decimal = Field(0.01, client_data=ClientFieldData(prompt_on_new=False, prompt=lambda mi: "The activation threshold"))


class DManV3MultiplePairs(ScriptStrategyBase):
    @classmethod
    def init_markets(cls, config: DManV3ScriptConfig):
        cls.markets = {config.exchange: set(config.trading_pairs.split(","))}

    def __init__(self, connectors: Dict[str, ConnectorBase], config: DManV3ScriptConfig):
        super().__init__(connectors)
        self.config = config
        order_level_builder = OrderLevelBuilder(n_levels=config.n_levels)
        order_levels = order_level_builder.build_order_levels(
            amounts=config.order_amount,
            spreads=Distributions.arithmetic(n_levels=config.n_levels, start=config.start_spread,
                                             step=config.step_between_orders),
            triple_barrier_confs=TripleBarrierConf(
                stop_loss=config.stop_loss, take_profit=config.take_profit, time_limit=config.time_limit,
                trailing_stop_activation_price_delta=config.trailing_stop_activation_price_delta,
                trailing_stop_trailing_delta=config.trailing_stop_trailing_delta),
        )
        self.controllers = {}
        self.markets = {}
        self.executor_handlers = {}

        for trading_pair in config.trading_pairs.split(","):
            controller_config = DManV3Config(
                exchange=config.exchange,
                trading_pair=trading_pair,
                order_levels=order_levels,
                candles_config=[
                    CandlesConfig(connector=config.candles_exchange, trading_pair=trading_pair,
                                  interval=config.candles_interval, max_records=config.candles_max_records),
                ],
                bb_length=config.bollinger_band_length,
                bb_std=config.bollinger_band_std,
                side_filter=config.side_filter,
                dynamic_spread_factor=config.dynamic_spread_factor,
                dynamic_target_spread=config.dynamic_target_spread,
                smart_activation=config.smart_activation,
                activation_threshold=config.activation_threshold,
                leverage=config.leverage,
            )
            controller = DManV3(config=controller_config)
            self.controllers[trading_pair] = controller
            self.executor_handlers[trading_pair] = MarketMakingExecutorHandler(strategy=self, controller=controller)

    @property
    def is_perpetual(self):
        """
        Checks if the exchange is a perpetual market.
        """
        return "perpetual" in self.config.exchange

    def on_stop(self):
        if self.is_perpetual:
            self.close_open_positions()
        for executor_handler in self.executor_handlers.values():
            executor_handler.stop()

    def close_open_positions(self):
        # we are going to close all the open positions when the bot stops
        for connector_name, connector in self.connectors.items():
            for trading_pair, position in connector.account_positions.items():
                if trading_pair in connector.trading_pairs:
                    if position.position_side == PositionSide.LONG:
                        self.sell(connector_name=connector_name,
                                  trading_pair=position.trading_pair,
                                  amount=abs(position.amount),
                                  order_type=OrderType.MARKET,
                                  price=connector.get_mid_price(position.trading_pair),
                                  position_action=PositionAction.CLOSE)
                    elif position.position_side == PositionSide.SHORT:
                        self.buy(connector_name=connector_name,
                                 trading_pair=position.trading_pair,
                                 amount=abs(position.amount),
                                 order_type=OrderType.MARKET,
                                 price=connector.get_mid_price(position.trading_pair),
                                 position_action=PositionAction.CLOSE)

    def on_tick(self):
        """
        This shows you how you can start meta controllers. You can run more than one at the same time and based on the
        market conditions, you can orchestrate from this script when to stop or start them.
        """
        for executor_handler in self.executor_handlers.values():
            if executor_handler.status == ExecutorHandlerStatus.NOT_STARTED:
                executor_handler.start()

    def format_status(self) -> str:
        if not self.ready_to_trade:
            return "Market connectors are not ready."
        lines = []
        for trading_pair, executor_handler in self.executor_handlers.items():
            lines.extend(
                [f"Strategy: {executor_handler.controller.config.strategy_name} | Trading Pair: {trading_pair}",
                 executor_handler.to_format_status()])
        return "\n".join(lines)
