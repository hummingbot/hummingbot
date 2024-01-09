import os
from decimal import Decimal
from typing import Dict

from pydantic import Field

from hummingbot.client.config.config_data_types import BaseClientModel, ClientFieldData
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionSide
from hummingbot.data_feed.candles_feed.candles_factory import CandlesConfig
from hummingbot.smart_components.controllers.dman_v2 import DManV2, DManV2Config
from hummingbot.smart_components.strategy_frameworks.data_types import ExecutorHandlerStatus, TripleBarrierConf
from hummingbot.smart_components.strategy_frameworks.market_making.market_making_executor_handler import (
    MarketMakingExecutorHandler,
)
from hummingbot.smart_components.utils.distributions import Distributions
from hummingbot.smart_components.utils.order_level_builder import OrderLevelBuilder
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class DManV2ScriptConfig(BaseClientModel):
    script_file_name: str = Field(default_factory=lambda: os.path.basename(__file__))  # This has to be defined to be able to filter the configs for this script
    # Account configuration
    exchange: str = Field("binance_perpetual",
                          client_data=ClientFieldData(prompt_on_new=True,
                                                      prompt=lambda mi: "The exchange to trade on"))
    trading_pairs: str = Field("ETH-USDT",
                               client_data=ClientFieldData(prompt_on_new=True,
                                                           prompt=lambda mi: "The trading pairs to trade on separated by comma"))
    leverage: int = Field(20, client_data=ClientFieldData(prompt_on_new=True,
                                                          prompt=lambda mi: "The leverage to use"))

    # Candles configuration
    candles_exchange: str = Field("binance_perpetual",
                                  client_data=ClientFieldData(prompt_on_new=True,
                                                              prompt=lambda mi: "The exchange to get the candles from"))
    candles_interval: str = Field("3m",
                                  client_data=ClientFieldData(prompt_on_new=True,
                                                              prompt=lambda mi: "The interval of the candles"))
    candles_max_records: int = Field(300, client_data=ClientFieldData(prompt_on_new=False,
                                                                      prompt=lambda mi: "The max records of the candles"))

    # Orders configuration
    order_amount: Decimal = Field(25, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "The order amount in quote asset"))
    n_levels: int = Field(5, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "The number of order levels"))
    start_spread: float = Field(0.0006, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "The start spread"))
    step_between_orders: float = Field(0.009, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "The step between orders"))
    order_refresh_time: int = Field(60 * 15, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "The order refresh time in seconds"))
    cooldown_time: int = Field(5, client_data=ClientFieldData(prompt_on_new=False, prompt=lambda mi: "The cooldown time in seconds"))

    # Triple barrier configuration
    stop_loss: Decimal = Field(0.2, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "The stop loss"))
    take_profit: Decimal = Field(0.06, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "The take profit"))
    time_limit: int = Field(60 * 60 * 12, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "The time limit"))
    trailing_stop_activation_price_delta: Decimal = Field(0.0045, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "The trailing stop activation price delta"))
    trailing_stop_trailing_delta: Decimal = Field(0.003, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "The trailing stop activation price delta"))

    # Advanced configurations
    natr_length: int = Field(100, client_data=ClientFieldData(prompt_on_new=False, prompt=lambda mi: "The NATR length"))
    macd_fast: int = Field(12, client_data=ClientFieldData(prompt_on_new=False, prompt=lambda mi: "The MACD fast length"))
    macd_slow: int = Field(26, client_data=ClientFieldData(prompt_on_new=False, prompt=lambda mi: "The MACD slow length"))
    macd_signal: int = Field(9, client_data=ClientFieldData(prompt_on_new=False, prompt=lambda mi: "The MACD signal length"))


class DManV2MultiplePairs(ScriptStrategyBase):
    @classmethod
    def init_markets(cls, config: DManV2ScriptConfig):
        cls.markets = {config.exchange: set(config.trading_pairs.split(","))}

    def __init__(self, connectors: Dict[str, ConnectorBase], config: DManV2ScriptConfig):
        super().__init__(connectors)
        self.config = config

        # Initialize order level builder
        order_level_builder = OrderLevelBuilder(n_levels=config.n_levels)
        order_levels = order_level_builder.build_order_levels(
            amounts=config.order_amount,
            spreads=Distributions.arithmetic(n_levels=config.n_levels, start=config.start_spread,
                                             step=config.step_between_orders),
            triple_barrier_confs=TripleBarrierConf(
                stop_loss=config.stop_loss,
                take_profit=config.take_profit,
                time_limit=config.time_limit,
                trailing_stop_activation_price_delta=config.trailing_stop_activation_price_delta,
                trailing_stop_trailing_delta=config.trailing_stop_trailing_delta),
            order_refresh_time=config.order_refresh_time,
            cooldown_time=config.cooldown_time,
        )

        # Initialize controllers and executor handlers
        self.controllers = {}
        self.executor_handlers = {}
        self.markets = {}

        for trading_pair in config.trading_pairs.split(","):
            # Configure the strategy for each trading pair
            dman_config = DManV2Config(
                exchange=config.exchange,
                trading_pair=trading_pair,
                order_levels=order_levels,
                candles_config=[
                    CandlesConfig(connector=config.candles_exchange, trading_pair=trading_pair,
                                  interval=config.candles_interval, max_records=config.candles_max_records),
                ],
                leverage=config.leverage,
                natr_length=config.natr_length,
                macd_fast=config.macd_fast,
                macd_slow=config.macd_slow,
                macd_signal=config.macd_signal,
            )

            # Instantiate the controller for each trading pair
            controller = DManV2(config=dman_config)
            self.markets = controller.update_strategy_markets_dict(self.markets)
            self.controllers[trading_pair] = controller

            # Create and store the executor handler for each trading pair
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
