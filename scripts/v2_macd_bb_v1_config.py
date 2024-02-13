import os
from decimal import Decimal
from typing import Dict

from pydantic import Field

from hummingbot.client.config.config_data_types import BaseClientModel, ClientFieldData
from hummingbot.connector.connector_base import ConnectorBase, TradeType
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionSide
from hummingbot.data_feed.candles_feed.candles_factory import CandlesConfig
from hummingbot.smart_components.controllers.macd_bb_v1 import MACDBBV1, MACDBBV1Config
from hummingbot.smart_components.executors.position_executor.data_types import TripleBarrierConf
from hummingbot.smart_components.models.base import SmartComponentStatus
from hummingbot.smart_components.order_level_distributions.order_level_builder import OrderLevel
from hummingbot.smart_components.strategy_frameworks.directional_trading.directional_trading_executor_handler import (
    DirectionalTradingExecutorHandler,
)
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class DirectionalTradingMACDBBConfig(BaseClientModel):
    script_file_name: str = Field(default_factory=lambda: os.path.basename(__file__))

    # Trading pairs configuration
    exchange: str = Field("binance_perpetual", client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Enter the name of the exchange where the bot will operate (e.g., binance_perpetual):"))
    trading_pairs: str = Field("DOGE-USDT,INJ-USDT", client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "List the trading pairs for the bot to trade on, separated by commas (e.g., BTC-USDT,ETH-USDT):"))
    leverage: int = Field(20, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Set the leverage to use for trading (e.g., 20 for 20x leverage):"))

    # Triple barrier configuration
    stop_loss: Decimal = Field(0.01, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Set the stop loss percentage (e.g., 0.01 for 1% loss):"))
    take_profit: Decimal = Field(0.06, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Enter the take profit percentage (e.g., 0.03 for 3% gain):"))
    time_limit: int = Field(60 * 60 * 24, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Set the time limit in seconds for the triple barrier (e.g., 21600 for 6 hours):"))
    trailing_stop_activation_price_delta: Decimal = Field(0.01, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Enter the activation price delta for the trailing stop (e.g., 0.008 for 0.8%):"))
    trailing_stop_trailing_delta: Decimal = Field(0.004, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Set the trailing delta for the trailing stop (e.g., 0.004 for 0.4%):"))
    open_order_type: str = Field("MARKET", client_data=ClientFieldData(prompt_on_new=False, prompt=lambda mi: "Specify the type of order to open (e.g., MARKET or LIMIT):"))

    # Orders configuration
    order_amount_usd: Decimal = Field(15, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Enter the order amount in USD (e.g., 15):"))
    spread_factor: Decimal = Field(0, client_data=ClientFieldData(prompt_on_new=False, prompt=lambda mi: "Set the spread factor (e.g., 0.5):"))
    order_refresh_time: int = Field(60 * 5, client_data=ClientFieldData(prompt_on_new=False, prompt=lambda mi: "Enter the refresh time in seconds for orders (e.g., 300 for 5 minutes):"))
    cooldown_time: int = Field(15, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Specify the cooldown time in seconds between order placements (e.g., 15):"))

    # Candles configuration
    candles_exchange: str = Field("binance_perpetual", client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Enter the exchange name to fetch candle data from (e.g., binance_perpetual):"))
    candles_interval: str = Field("3m", client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Set the time interval for candles (e.g., 1m, 5m, 1h):"))

    # MACD and Bollinger Bands configuration
    macd_fast: int = Field(21, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Set the MACD fast length (e.g., 21):"))
    macd_slow: int = Field(42, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Specify the MACD slow length (e.g., 42):"))
    macd_signal: int = Field(9, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Define the MACD signal length (e.g., 9):"))
    bb_length: int = Field(100, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Enter the Bollinger Bands length (e.g., 100):"))
    bb_std: float = Field(2.0, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Set the standard deviation for the Bollinger Bands (e.g., 2.0):"))
    bb_long_threshold: float = Field(0.3, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Specify the long threshold for Bollinger Bands (e.g., 0.3):"))
    bb_short_threshold: float = Field(0.7, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Define the short threshold for Bollinger Bands (e.g., 0.7):"))


class DirectionalTradingMACDBB(ScriptStrategyBase):

    @classmethod
    def init_markets(cls, config: DirectionalTradingMACDBBConfig):
        cls.markets = {config.exchange: set(config.trading_pairs.split(","))}

    def __init__(self, connectors: Dict[str, ConnectorBase], config: DirectionalTradingMACDBBConfig):
        super().__init__(connectors)
        self.config = config

        triple_barrier_conf = TripleBarrierConf(
            stop_loss=config.stop_loss,
            take_profit=config.take_profit,
            time_limit=config.time_limit,
            trailing_stop_activation_price=config.trailing_stop_activation_price_delta,
            trailing_stop_trailing_delta=config.trailing_stop_trailing_delta,
            open_order_type=OrderType.MARKET if config.open_order_type == "MARKET" else OrderType.LIMIT,
        )

        order_levels = [
            OrderLevel(level=0, side=TradeType.BUY, order_amount_usd=config.order_amount_usd,
                       spread_factor=config.spread_factor, order_refresh_time=config.order_refresh_time,
                       cooldown_time=config.cooldown_time, triple_barrier_conf=triple_barrier_conf),
            OrderLevel(level=0, side=TradeType.SELL, order_amount_usd=config.order_amount_usd,
                       spread_factor=config.spread_factor, order_refresh_time=config.order_refresh_time,
                       cooldown_time=config.cooldown_time, triple_barrier_conf=triple_barrier_conf),
        ]

        self.controllers = {}
        self.executor_handlers = {}

        for trading_pair in config.trading_pairs.split(","):
            macd_bb_config = MACDBBV1Config(
                exchange=config.exchange,
                trading_pair=trading_pair,
                order_levels=order_levels,
                candles_config=[
                    CandlesConfig(connector=config.candles_exchange, trading_pair=trading_pair,
                                  interval=config.candles_interval,
                                  max_records=config.bb_length + 200),
                    # we need more candles to calculate the bollinger bands
                ],
                leverage=config.leverage,
                macd_fast=config.macd_fast, macd_slow=config.macd_slow, macd_signal=config.macd_signal,
                bb_length=config.bb_length, bb_std=config.bb_std, bb_long_threshold=config.bb_long_threshold, bb_short_threshold=config.bb_short_threshold,
            )
            controller = MACDBBV1(config=macd_bb_config)
            self.controllers[trading_pair] = controller
            self.executor_handlers[trading_pair] = DirectionalTradingExecutorHandler(strategy=self, controller=controller)

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
            if executor_handler.controller.all_candles_ready:
                lines.extend(
                    [f"Strategy: {executor_handler.controller.config.strategy_name} | Trading Pair: {trading_pair}",
                     executor_handler.to_format_status()])
        return "\n".join(lines)
