from decimal import Decimal
from typing import Dict

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionSide
from hummingbot.data_feed.candles_feed.candles_factory import CandlesConfig
from hummingbot.smart_components.controllers.dman_v3 import DManV3, DManV3Config
from hummingbot.smart_components.executors.position_executor.data_types import TripleBarrierConf
from hummingbot.smart_components.models.base import SmartComponentStatus
from hummingbot.smart_components.order_level_distributions.distributions import Distributions
from hummingbot.smart_components.order_level_distributions.order_level_builder import OrderLevelBuilder
from hummingbot.smart_components.strategy_frameworks.market_making.market_making_executor_handler import (
    MarketMakingExecutorHandler,
)
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class DManV3MultiplePairs(ScriptStrategyBase):
    # Account and candles configuration
    markets_config = [
        {"exchange": "vega_perpetual",
         "trading_pair": "ETHUSDPERP-USDT",
         "leverage": 20,
         "candles_config": CandlesConfig(connector="binance_perpetual", trading_pair="ETH-USDT", interval="1h",
                                         max_records=300)},
        {"exchange": "vega_perpetual",
         "trading_pair": "BTCUSDPERP-USDT",
         "leverage": 20,
         "candles_config": CandlesConfig(connector="binance_perpetual", trading_pair="BTC-USDT", interval="1h",
                                         max_records=300)},
    ]
    # Indicators configuration
    bollinger_band_length = 200
    bollinger_band_std = 3.0

    # Orders configuration
    order_amount = Decimal("25")
    n_levels = 5
    start_spread = 0.5  # percentage of the bollinger band (0.5 means that the order will be between the bollinger mid-price and the upper band)
    step_between_orders = 0.3  # percentage of the bollinger band (0.1 means that the next order will be 10% of the bollinger band away from the previous order)

    # Triple barrier configuration
    stop_loss = Decimal("0.01")
    take_profit = Decimal("0.03")
    time_limit = 60 * 60 * 6
    trailing_stop_activation_price_delta = Decimal("0.008")
    trailing_stop_trailing_delta = Decimal("0.004")

    # Advanced configurations
    side_filter = True
    dynamic_spread_factor = True
    dynamic_target_spread = False
    smart_activation = False
    activation_threshold = Decimal("0.001")

    # Applying the configuration
    order_level_builder = OrderLevelBuilder(n_levels=n_levels)
    order_levels = order_level_builder.build_order_levels(
        amounts=order_amount,
        spreads=Distributions.arithmetic(n_levels=n_levels, start=start_spread, step=step_between_orders),
        triple_barrier_confs=TripleBarrierConf(
            stop_loss=stop_loss, take_profit=take_profit, time_limit=time_limit,
            trailing_stop_activation_price=trailing_stop_activation_price_delta,
            trailing_stop_trailing_delta=trailing_stop_trailing_delta),
    )
    controllers = {}
    markets = {}
    executor_handlers = {}

    for conf in markets_config:
        config = DManV3Config(
            exchange=conf["exchange"],
            trading_pair=conf["trading_pair"],
            order_levels=order_levels,
            close_price_trading_pair=conf["candles_config"].trading_pair,  # if this is None, the controller will use the default trading pair
            candles_config=[conf["candles_config"]],
            bb_length=bollinger_band_length,
            bb_std=bollinger_band_std,
            side_filter=side_filter,
            dynamic_spread_factor=dynamic_spread_factor,
            dynamic_target_spread=dynamic_target_spread,
            smart_activation=smart_activation,
            activation_threshold=activation_threshold,
            leverage=conf["leverage"],
        )
        controller = DManV3(config=config)
        markets = controller.update_strategy_markets_dict(markets)
        controllers[conf["trading_pair"]] = controller

    def __init__(self, connectors: Dict[str, ConnectorBase]):
        super().__init__(connectors)
        for trading_pair, controller in self.controllers.items():
            self.executor_handlers[trading_pair] = MarketMakingExecutorHandler(strategy=self, controller=controller)

    @staticmethod
    def is_perpetual(exchange):
        """
        Checks if the exchange is a perpetual market.
        """
        return "perpetual" in exchange

    def on_stop(self):
        self.close_open_positions()

    def close_open_positions(self):
        # we are going to close all the open positions when the bot stops
        for connector_name, connector in self.connectors.items():
            if self.is_perpetual(connector_name):
                for trading_pair, position in connector.account_positions.items():
                    if trading_pair in self.markets[connector_name]:
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
