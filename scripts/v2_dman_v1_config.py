import os
from decimal import Decimal
from typing import Dict

from pydantic import Field

from hummingbot.client.config.config_data_types import BaseClientModel, ClientFieldData
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionSide
from hummingbot.data_feed.candles_feed.candles_factory import CandlesConfig
from hummingbot.smart_components.controllers.dman_v1 import DManV1, DManV1Config
from hummingbot.smart_components.executors.position_executor.data_types import TripleBarrierConf
from hummingbot.smart_components.models.base import SmartComponentStatus
from hummingbot.smart_components.order_level_distributions.distributions import Distributions
from hummingbot.smart_components.order_level_distributions.order_level_builder import OrderLevelBuilder
from hummingbot.smart_components.strategy_frameworks.market_making.market_making_executor_handler import (
    MarketMakingExecutorHandler,
)
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class DManV1ScriptConfig(BaseClientModel):
    script_file_name: str = Field(default_factory=lambda: os.path.basename(__file__))

    # Account configuration
    exchange: str = Field("binance_perpetual", client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Enter the name of the exchange where the bot will operate (e.g., binance_perpetual):"))
    trading_pairs: str = Field("DOGE-USDT", client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "List the trading pairs for the bot to trade on, separated by commas (e.g., BTC-USDT,ETH-USDT):"))
    leverage: int = Field(20, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Set the leverage to use for trading (e.g., 20 for 20x leverage):"))

    # Candles configuration
    candles_exchange: str = Field("binance_perpetual", client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Enter the exchange name to fetch candle data from (e.g., binance_perpetual):"))
    candles_interval: str = Field("3m", client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Set the time interval for candles (e.g., 1m, 5m, 1h):"))

    # Orders configuration
    order_amount: Decimal = Field(25, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Enter the base order amount in quote asset (e.g., 25 USDT):"))
    n_levels: int = Field(5, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Specify the number of order levels (e.g., 5):"))
    start_spread: float = Field(1.0, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Set the start spread as a multiple of the NATR (e.g., 1.0 for 1x NATR):"))
    step_between_orders: float = Field(0.8, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Define the step between orders as a multiple of the NATR (e.g., 0.8 for 0.8x NATR):"))
    order_refresh_time: int = Field(60 * 45, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Enter the refresh time in seconds for orders (e.g., 900 for 15 minutes):"))
    cooldown_time: int = Field(5, client_data=ClientFieldData(prompt_on_new=False, prompt=lambda mi: "Specify the cooldown time in seconds between order placements (e.g., 5):"))

    # Triple barrier configuration
    stop_loss: Decimal = Field(0.2, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Set the stop loss percentage (e.g., 0.2 for 20% loss):"))
    take_profit: Decimal = Field(0.06, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Enter the take profit percentage (e.g., 0.06 for 6% gain):"))
    time_limit: int = Field(60 * 60 * 12, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Set the time limit in seconds for the triple barrier (e.g., 43200 for 12 hours):"))
    trailing_stop_activation_price_delta: Decimal = Field(0.0045, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Enter the activation price delta for the trailing stop (e.g., 0.0045 for 0.45%):"))
    trailing_stop_trailing_delta: Decimal = Field(0.003, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Set the trailing delta for the trailing stop (e.g., 0.003 for 0.3%):"))

    # Advanced configurations
    natr_length: int = Field(100, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Enter the NATR (Normalized Average True Range) length (e.g., 100):"))


class DManV1MultiplePairs(ScriptStrategyBase):
    @classmethod
    def init_markets(cls, config: DManV1ScriptConfig):
        cls.markets = {config.exchange: set(config.trading_pairs.split(","))}

    def __init__(self, connectors: Dict[str, ConnectorBase], config: DManV1ScriptConfig):
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
                trailing_stop_activation_price=config.trailing_stop_activation_price_delta,
                trailing_stop_trailing_delta=config.trailing_stop_trailing_delta),
            order_refresh_time=config.order_refresh_time,
            cooldown_time=config.cooldown_time,
        )

        # Initialize controllers and executor handlers
        self.controllers = {}
        self.executor_handlers = {}
        self.markets = {}
        candles_max_records = config.natr_length + 100  # We need to get more candles than the indicators need

        for trading_pair in config.trading_pairs.split(","):
            # Configure the strategy for each trading pair
            dman_config = DManV1Config(
                exchange=config.exchange,
                trading_pair=trading_pair,
                order_levels=order_levels,
                candles_config=[
                    CandlesConfig(connector=config.candles_exchange, trading_pair=trading_pair,
                                  interval=config.candles_interval, max_records=candles_max_records),
                ],
                leverage=config.leverage,
                natr_length=config.natr_length,
            )

            # Instantiate the controller for each trading pair
            controller = DManV1(config=dman_config)
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
            if executor_handler.status == SmartComponentStatus.NOT_STARTED:
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
