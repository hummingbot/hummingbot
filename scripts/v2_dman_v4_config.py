import os
from decimal import Decimal
from typing import Dict

from pydantic import Field

from hummingbot.client.config.config_data_types import BaseClientModel, ClientFieldData
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionSide, TradeType
from hummingbot.data_feed.candles_feed.candles_factory import CandlesConfig
from hummingbot.smart_components.controllers.dman_v4 import DManV4, DManV4Config
from hummingbot.smart_components.executors.position_executor.data_types import TrailingStop, TripleBarrierConf
from hummingbot.smart_components.models.base import SmartComponentStatus
from hummingbot.smart_components.order_level_distributions.distributions import Distributions
from hummingbot.smart_components.order_level_distributions.order_level_builder import OrderLevelBuilder
from hummingbot.smart_components.strategy_frameworks.market_making.market_making_executor_handler import (
    MarketMakingExecutorHandler,
)
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class DManV4ScriptConfig(BaseClientModel):
    script_file_name: str = Field(default_factory=lambda: os.path.basename(__file__))

    # Account configuration
    exchange: str = Field("binance_perpetual", client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Enter the name of the exchange where the bot will operate (e.g., binance_perpetual):"))
    trading_pairs: str = Field("DOGE-USDT,INJ-USDT", client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "List the trading pairs for the bot to trade on, separated by commas (e.g., BTC-USDT,ETH-USDT):"))
    leverage: int = Field(20, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Set the leverage to use for trading (e.g., 20 for 20x leverage):"))
    initial_auto_rebalance: bool = Field(False, client_data=ClientFieldData(prompt_on_new=False, prompt=lambda mi: "Enable initial auto rebalance (True/False):"))
    extra_inventory_pct: Decimal = Field(0.1, client_data=ClientFieldData(prompt_on_new=False, prompt=lambda mi: "Set the extra inventory percentage for rebalancing (e.g., 0.1 for 10%):"))
    asset_to_rebalance: str = Field("USDT", client_data=ClientFieldData(prompt_on_new=False, prompt=lambda mi: "Enter the asset to use for rebalancing (e.g., USDT):"))
    rebalanced: bool = Field(False, client_data=ClientFieldData(prompt_on_new=False, prompt=lambda mi: "Set the initial state of rebalancing to complete (True/False):"))

    # Candles configuration
    candles_exchange: str = Field("binance_perpetual", client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Enter the exchange name to fetch candle data from (e.g., binance_perpetual):"))
    candles_interval: str = Field("3m", client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Set the time interval for candles (e.g., 1m, 5m, 1h):"))
    bollinger_band_length: int = Field(200, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Enter the length of the Bollinger Bands (e.g., 200):"))
    bollinger_band_std: float = Field(3.0, client_data=ClientFieldData(prompt_on_new=False, prompt=lambda mi: "Set the standard deviation for the Bollinger Bands (e.g., 2.0):"))

    # Orders configuration
    order_amount: Decimal = Field(10, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Enter the base order amount in quote asset (e.g., 6 USDT):"))
    amount_ratio_increase: Decimal = Field(1.5, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Set the ratio to increase the amount for each subsequent level (e.g., 1.5):"))
    n_levels: int = Field(5, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Specify the number of order levels (e.g., 5):"))
    top_order_start_spread: Decimal = Field(0.0002, client_data=ClientFieldData(prompt_on_new=False, prompt=lambda mi: "Set the spread for the top order (e.g., 0.0002 for 0.02%):"))
    start_spread: Decimal = Field(0.03, client_data=ClientFieldData(prompt_on_new=False, prompt=lambda mi: "Enter the starting spread for orders (e.g., 0.02 for 2%):"))
    spread_ratio_increase: Decimal = Field(2.0, client_data=ClientFieldData(prompt_on_new=False, prompt=lambda mi: "Define the ratio to increase the spread for each subsequent level (e.g., 2.0):"))

    top_order_refresh_time: int = Field(60, client_data=ClientFieldData(prompt_on_new=False, prompt=lambda mi: "Set the refresh time in seconds for the top order (e.g., 60 for 1 minute):"))
    order_refresh_time: int = Field(60 * 60 * 12, client_data=ClientFieldData(prompt_on_new=False, prompt=lambda mi: "Enter the refresh time in seconds for all other orders (e.g., 7200 for 2 hours):"))
    cooldown_time: int = Field(60, client_data=ClientFieldData(prompt_on_new=False, prompt=lambda mi: "Specify the cooldown time in seconds between order placements (e.g., 30):"))

    # Triple barrier configuration
    stop_loss: Decimal = Field(0.5, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Set the stop loss percentage (e.g., 0.2 for 20%):"))
    take_profit: Decimal = Field(0.1, client_data=ClientFieldData(prompt_on_new=False, prompt=lambda mi: "Enter the take profit percentage (e.g., 0.06 for 6%):"))
    time_limit: int = Field(60 * 60 * 24 * 3, client_data=ClientFieldData(prompt_on_new=False, prompt=lambda mi: "Set the time limit in seconds for the triple barrier (e.g., 43200 for 12 hours):"))

    # Global Trailing Stop configuration
    global_trailing_stop_activation_price_delta: Decimal = Field(0.025, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Enter the activation price delta for the global trailing stop (e.g., 0.01 for 1%):"))
    global_trailing_stop_trailing_delta: Decimal = Field(0.005, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Set the trailing delta for the global trailing stop (e.g., 0.002 for 0.2%):"))

    # Advanced configurations
    dynamic_spread_factor: bool = Field(False, client_data=ClientFieldData(prompt_on_new=False, prompt=lambda mi: "Enable dynamic spread factor (True/False):"))
    dynamic_target_spread: bool = Field(False, client_data=ClientFieldData(prompt_on_new=False, prompt=lambda mi: "Activate dynamic target spread (True/False):"))
    smart_activation: bool = Field(False, client_data=ClientFieldData(prompt_on_new=False, prompt=lambda mi: "Enable smart activation for orders (True/False):"))
    activation_threshold: Decimal = Field(0.001, client_data=ClientFieldData(prompt_on_new=False, prompt=lambda mi: "Set the activation threshold (e.g., 0.001 for 0.1%):"))
    price_band: bool = Field(False, client_data=ClientFieldData(prompt_on_new=False, prompt=lambda mi: "Enable price band filtering (True/False):"))
    price_band_long_filter: Decimal = Field(0.8, client_data=ClientFieldData(prompt_on_new=False, prompt=lambda mi: "Set the long filter for price band (e.g., 0.8 for 80%):"))
    price_band_short_filter: Decimal = Field(0.8, client_data=ClientFieldData(prompt_on_new=False, prompt=lambda mi: "Specify the short filter for price band (e.g., 0.8 for 80%):"))


class DManV4MultiplePairs(ScriptStrategyBase):
    @classmethod
    def init_markets(cls, config: DManV4ScriptConfig):
        cls.markets = {config.exchange: set(config.trading_pairs.split(","))}

    def __init__(self, connectors: Dict[str, ConnectorBase], config: DManV4ScriptConfig):
        super().__init__(connectors)
        self.config = config

        # Building order levels based on the configuration
        order_level_builder = OrderLevelBuilder(n_levels=self.config.n_levels)
        order_levels = order_level_builder.build_order_levels(
            amounts=Distributions.geometric(n_levels=self.config.n_levels, start=float(self.config.order_amount),
                                            ratio=float(self.config.amount_ratio_increase)),
            spreads=[Decimal(self.config.top_order_start_spread)] + Distributions.geometric(
                n_levels=self.config.n_levels - 1, start=float(self.config.start_spread),
                ratio=float(self.config.spread_ratio_increase)),
            triple_barrier_confs=TripleBarrierConf(
                stop_loss=self.config.stop_loss, take_profit=self.config.take_profit, time_limit=self.config.time_limit,
            ),
            order_refresh_time=[self.config.top_order_refresh_time] + [self.config.order_refresh_time] * (self.config.n_levels - 1),
            cooldown_time=self.config.cooldown_time,
        )

        # Initialize controllers and executor handlers
        self.controllers = {}
        self.executor_handlers = {}
        self.markets = {}

        for trading_pair in config.trading_pairs.split(","):
            dman_config = DManV4Config(
                exchange=self.config.exchange,
                trading_pair=trading_pair,
                order_levels=order_levels,
                candles_config=[
                    CandlesConfig(connector=self.config.candles_exchange, trading_pair=trading_pair,
                                  interval=self.config.candles_interval,
                                  max_records=self.config.bollinger_band_length + 100),  # we need more candles to calculate the bollinger bands
                ],
                bb_length=self.config.bollinger_band_length,
                bb_std=self.config.bollinger_band_std,
                price_band=self.config.price_band,
                price_band_long_filter=self.config.price_band_long_filter,
                price_band_short_filter=self.config.price_band_short_filter,
                dynamic_spread_factor=self.config.dynamic_spread_factor,
                dynamic_target_spread=self.config.dynamic_target_spread,
                smart_activation=self.config.smart_activation,
                activation_threshold=self.config.activation_threshold,
                leverage=self.config.leverage,
                global_trailing_stop_config={
                    TradeType.BUY: TrailingStop(
                        activation_price=self.config.global_trailing_stop_activation_price_delta,
                        trailing_delta=self.config.global_trailing_stop_trailing_delta),
                    TradeType.SELL: TrailingStop(
                        activation_price=self.config.global_trailing_stop_activation_price_delta,
                        trailing_delta=self.config.global_trailing_stop_trailing_delta),
                }
            )
            controller = DManV4(config=dman_config)
            self.controllers[trading_pair] = controller
            self.executor_handlers[trading_pair] = MarketMakingExecutorHandler(strategy=self, controller=controller)
            self.markets = controller.update_strategy_markets_dict(self.markets)

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
