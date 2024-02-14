import os
from decimal import Decimal
from typing import Dict

from pydantic import Field

from hummingbot.client.config.config_data_types import BaseClientModel, ClientFieldData
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.data_feed.candles_feed.candles_factory import CandlesConfig
from hummingbot.smart_components.controllers.dman_v6 import DManV6, DManV6Config
from hummingbot.smart_components.executors.position_executor.data_types import TrailingStop
from hummingbot.smart_components.models.base import SmartComponentStatus
from hummingbot.smart_components.strategy_frameworks.generic_strategy.generic_executor import GenericExecutor
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class DManV6ScriptConfig(BaseClientModel):
    script_file_name: str = Field(default_factory=lambda: os.path.basename(__file__))

    # Account configuration
    exchange: str = Field("binance_perpetual", client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Enter the name of the exchange where the bot will operate (e.g., binance_perpetual):"))
    trading_pairs: str = Field("DOGE-USDT,INJ-USDT", client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "List the trading pairs for the bot to trade on, separated by commas (e.g., BTC-USDT,ETH-USDT):"))
    leverage: int = Field(20, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Set the leverage to use for trading (e.g., 20 for 20x leverage):"))

    # Candles configuration
    candles_exchange: str = Field("binance_perpetual", client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Enter the exchange name to fetch candle data from (e.g., binance_perpetual):"))
    candles_interval: str = Field("3m", client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Set the time interval for candles (e.g., 1m, 5m, 1h):"))

    # Orders configuration
    order_amount: Decimal = Field(10, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Enter the base order amount in quote asset (e.g., 6 USDT):"))
    dca_refresh_time: int = Field(60, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Set the refresh time for DCA orders in seconds (e.g., 60):"))
    max_dca_per_side: int = Field(3, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Set the maximum number of DCA orders per side (e.g., 3):"))
    min_distance_between_dca: float = Field(0.02, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Set the minimum distance between DCA orders (e.g., 0.03):"))
    amount_ratio_increase: float = Field(1.5, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Set the ratio to increase the amount for each subsequent level (e.g., 1.5):"))
    n_levels: int = Field(5, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Specify the number of order levels (e.g., 5):"))
    top_order_start_spread: float = Field(0.0002, client_data=ClientFieldData(prompt_on_new=False, prompt=lambda mi: "Set the spread for the top order (e.g., 0.0002 for 0.02%):"))
    start_spread: float = Field(0.03, client_data=ClientFieldData(prompt_on_new=False, prompt=lambda mi: "Enter the starting spread for orders (e.g., 0.02 for 2%):"))
    spread_ratio_increase: float = Field(2.0, client_data=ClientFieldData(prompt_on_new=False, prompt=lambda mi: "Define the ratio to increase the spread for each subsequent level (e.g., 2.0):"))

    # Triple barrier configuration
    stop_loss: Decimal = Field(0.2, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Set the stop loss percentage (e.g., 0.2 for 20%):"))
    take_profit: Decimal = Field(0.1, client_data=ClientFieldData(prompt_on_new=False, prompt=lambda mi: "Enter the take profit percentage (e.g., 0.06 for 6%):"))
    time_limit: int = Field(60 * 60 * 24 * 3, client_data=ClientFieldData(prompt_on_new=False, prompt=lambda mi: "Set the time limit in seconds for the triple barrier (e.g., 43200 for 12 hours):"))

    # Global Trailing Stop configuration
    trailing_stop_activation_price_delta: Decimal = Field(0.025, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Enter the activation price delta for the global trailing stop (e.g., 0.01 for 1%):"))
    trailing_stop_trailing_delta: Decimal = Field(0.005, client_data=ClientFieldData(prompt_on_new=True, prompt=lambda mi: "Set the trailing delta for the global trailing stop (e.g., 0.002 for 0.2%):"))
    activation_bounds: Decimal = Field(0.05, client_data=ClientFieldData(prompt_on_new=False, prompt=lambda mi: "Set the activation threshold for the global trailing stop (e.g., 0.01 for 1%):"))


class DManV6MultiplePairs(ScriptStrategyBase):
    @classmethod
    def init_markets(cls, config: DManV6ScriptConfig):
        cls.markets = {config.exchange: set(config.trading_pairs.split(","))}

    def __init__(self, connectors: Dict[str, ConnectorBase], config: DManV6ScriptConfig):
        super().__init__(connectors)
        self.config = config

        # Initialize controllers and executor handlers
        self.controllers = {}
        self.executor_handlers = {}

        for trading_pair in config.trading_pairs.split(","):
            dman_config = DManV6Config(
                id="dca_maker_strategy",
                exchange=self.config.exchange,
                trading_pair=trading_pair,
                candles_config=[
                    CandlesConfig(connector=self.config.candles_exchange, trading_pair=trading_pair,
                                  interval=self.config.candles_interval,
                                  max_records=100),
                ],
                max_dca_per_side=config.max_dca_per_side,
                min_distance_between_dca=config.min_distance_between_dca,
                order_amount_quote=config.order_amount,
                dca_refresh_time=config.dca_refresh_time,
                amount_ratio_increase=config.amount_ratio_increase,
                n_levels=config.n_levels,
                top_order_start_spread=config.top_order_start_spread,
                start_spread=config.start_spread,
                spread_ratio_increase=config.spread_ratio_increase,
                take_profit=config.take_profit,
                stop_loss=config.stop_loss,
                trailing_stop=TrailingStop(activation_price=config.trailing_stop_activation_price_delta,
                                           trailing_delta=config.trailing_stop_trailing_delta),
                activation_bounds=[config.activation_bounds],
                time_limit=config.time_limit,
                leverage=self.config.leverage,
            )
            controller = DManV6(config=dman_config)
            self.controllers[trading_pair] = controller
            self.executor_handlers[trading_pair] = GenericExecutor(strategy=self, controller=controller)

    @property
    def is_perpetual(self):
        """
        Checks if the exchange is a perpetual market.
        """
        return "perpetual" in self.config.exchange

    def on_stop(self):
        for executor_handler in self.executor_handlers.values():
            executor_handler.stop()

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
                 executor_handler.to_format_status(), "-" * 50, ""])
        return "\n".join(lines)
