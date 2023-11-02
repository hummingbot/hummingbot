from decimal import Decimal
from typing import Dict

import pandas as pd

from hummingbot.client.ui.interface_utils import format_df_for_printout
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionSide
from hummingbot.data_feed.candles_feed.candles_factory import CandlesConfig
from hummingbot.smart_components.controllers.price_follower_v1 import PriceFollowerV1, PriceFollowerV1Config
from hummingbot.smart_components.strategy_frameworks.data_types import ExecutorHandlerStatus, TripleBarrierConf
from hummingbot.smart_components.strategy_frameworks.market_making.market_making_executor_handler import (
    MarketMakingExecutorHandler,
)
from hummingbot.smart_components.utils.distributions import Distributions
from hummingbot.smart_components.utils.order_level_builder import OrderLevelBuilder
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class PriceFollowerV1MultiplePairs(ScriptStrategyBase):
    debug_mode = False
    # Define trading pairs where you will be trading
    trading_pairs = ["GALA-USDT"]

    # Select your favourite exchange
    exchange = "binance_perpetual"

    # Select base amount per level. You can pass a list with different amounts to play with expected break even prices
    single_amount = Decimal("20")

    # Select interval
    interval = "1m"

    # Set up technical indicators config
    bb_length = 200
    bb_std = 2.0

    # Set up leverage for each trading pair, if the exchange supports it
    leverage_by_trading_pair = {
        "HBAR-USDT": 25,
        "CYBER-USDT": 20,
        "ETH-USDT": 100,
        "LPT-USDT": 10,
        "UNFI-USDT": 20,
        "BAKE-USDT": 20,
        "YGG-USDT": 20,
        "SUI-USDT": 50,
        "TOMO-USDT": 25,
        "RUNE-USDT": 25,
        "STX-USDT": 25,
        "API3-USDT": 20,
        "LIT-USDT": 20,
        "PERP-USDT": 16,
        "HOOK-USDT": 20,
        "AMB-USDT": 20,
        "ARKM-USDT": 20,
        "TRB-USDT": 10,
        "OMG-USDT": 25,
        "WLD-USDT": 50,
        "PEOPLE-USDT": 25,
        "AGLD-USDT": 20,
        "BAT-USDT": 20,
        "AVAX-USDT": 50,
        "JOE-USDT": 20,
        "BNX-USDT": 20,
        "COTI-USDT": 25,
        "JASMY-USDT": 20,
        "LOOM-USDT": 20,
        "IOTA-USDT": 25,
        "BNT-USDT": 20,
        "BLUR-USDT": 50,
        "FRONT-USDT": 25,
        "GALA-USDT": 25
    }

    # TODO: Allow to set different order levels for each trading pair
    # Set up spreads grid
    n_levels = 8
    start_value = 0.1
    end_value = 1.5
    spreads = Distributions.linear(n_levels=n_levels, start=Decimal(str(start_value)), end=Decimal(str(end_value)))

    # Set up the side filter. This is used to operate only on one side of the bollinger bands
    side_filter = False

    # Set up activation threshold for smart activation. As this strategy uses market orders we need this
    smart_activation = True
    activation_threshold = Decimal("0.1")

    # Set up cooldown time. This is the time that the executor will wait before creating a new order after finishing one
    cooldown_time = 10

    # Enable dynamic target spread. This will make the target spread to be a % of the current spread
    dynamic_target_spread = True

    # This value should be multiplied by the spread_multiplier to get the price % distance between levels
    intra_spread_pct = end_value / n_levels

    # This is the threshold that will be used to determine if the spread multiplier should be used or not
    min_price_pct_between_levels = Decimal("0.0008")

    # Set up triple barrier confs. Should be coefficients that will be multiplied by the spread multiplier to get the target prices
    take_profit = Decimal("10.0")
    stop_loss = Decimal("99.0")
    trailing_stop_activation_price_delta_factor = Decimal("5.0")
    trailing_stop_trailing_delta_factor = Decimal("0.5")
    time_limit = 60 * 60 * 24 * 1

    # Build triple barrier confs for every spread
    triple_barrier_confs = []
    for spread in spreads:
        triple_barrier_confs.append(
            TripleBarrierConf(stop_loss=stop_loss,
                              take_profit=take_profit,
                              time_limit=time_limit,
                              trailing_stop_activation_price_delta=trailing_stop_activation_price_delta_factor,
                              trailing_stop_trailing_delta=trailing_stop_trailing_delta_factor)
        )

    # Build order levels
    order_level_builder = OrderLevelBuilder(n_levels=n_levels)
    order_levels = order_level_builder.build_order_levels(
        amounts=single_amount,
        spreads=spreads,
        triple_barrier_confs=triple_barrier_confs,
        cooldown_time=cooldown_time,
    )

    # Wrapping up everything into a controller
    controllers = {}
    markets = {}
    executor_handlers = {}

    for trading_pair in trading_pairs:
        config = PriceFollowerV1Config(
            exchange=exchange,
            trading_pair=trading_pair,
            order_levels=order_levels,
            debug_mode=debug_mode,
            candles_config=[
                CandlesConfig(connector=exchange, trading_pair=trading_pair, interval=interval, max_records=300),
            ],
            bb_length=bb_length,
            bb_std=bb_std,
            side_filter=side_filter,
            smart_activation=smart_activation,
            dynamic_target_spread=dynamic_target_spread,
            activation_threshold=activation_threshold,
            leverage=leverage_by_trading_pair.get(trading_pair, 1),
            intra_spread_pct=intra_spread_pct,
            min_price_pct_between_levels=min_price_pct_between_levels,
        )
        controller = PriceFollowerV1(config=config)
        markets = controller.update_strategy_markets_dict(markets)
        controllers[trading_pair] = controller

    def __init__(self, connectors: Dict[str, ConnectorBase]):
        super().__init__(connectors)
        for trading_pair, controller in self.controllers.items():
            self.executor_handlers[trading_pair] = MarketMakingExecutorHandler(strategy=self, controller=controller)

    @property
    def is_perpetual(self):
        """
        Checks if the exchange is a perpetual market.
        """
        return "perpetual" in self.exchange

    def on_stop(self):
        if self.is_perpetual:
            self.close_open_positions()
        for executor_handler in self.executor_handlers.values():
            executor_handler.stop()

    def close_open_positions(self):
        # we are going to close all the open positions when the bot stops
        for connector_name, connector in self.connectors.items():
            for trading_pair, position in connector.account_positions.items():
                if trading_pair in self.trading_pairs:
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
        """
        This is a method that will be called by the UI to show the status of the strategy.

        Shows a table with the target prices for each level and the estimated stop loss and trailing stop prices.

        Every table has the following metrics:
        - Side: Fixed side of the order
        - Status: Status of the order. Can be Pending or Active
        - Close Price: Current close price
        - Upper Limit: Upper limit of the order
        - Order Price: Order price
        - Lower Limit: Lower limit of the order
        - Stop Loss: Estimated stop loss price
        - Trailing Stop Activation: Estimated trailing stop activation price
        - Trailing Stop Delta: Estimated trailing stop delta

        As the strategy uses market orders, the orders will be activated when the close price is between the lower and
        upper limits. Once they are active, the status will change to Active and the other metrics will be freezed.

        """
        if not self.ready_to_trade:
            return "Market connectors are not ready."
        lines = []
        for trading_pair, executor_handler in self.executor_handlers.items():
            lines.extend([""])
            if executor_handler.controller.target_prices:
                lines.extend(
                    [f"Strategy: {executor_handler.controller.config.strategy_name} | Trading Pair: {trading_pair} | Price Pct Between Levels: {executor_handler.controller.price_pct_between_levels:.3%}",
                     ""])

                closed_executors_info = executor_handler.closed_executors_info()
                active_executors_info = executor_handler.active_executors_info()
                unrealized_pnl = float(active_executors_info["net_pnl"])
                realized_pnl = closed_executors_info["net_pnl"]
                total_pnl = unrealized_pnl + realized_pnl
                total_volume = closed_executors_info["total_volume"] + float(active_executors_info["total_volume"])
                total_long = closed_executors_info["total_long"] + float(active_executors_info["total_long"])
                total_short = closed_executors_info["total_short"] + float(active_executors_info["total_short"])
                accuracy_long = closed_executors_info["accuracy_long"]
                accuracy_short = closed_executors_info["accuracy_short"]
                total_accuracy = ((accuracy_long * total_long + accuracy_short * total_short) /
                                  (total_long + total_short)) if (total_long + total_short) > 0 else 0
                lines.extend([f"Unrealized PNL: {unrealized_pnl * 100:.2f} % | Realized PNL: {realized_pnl * 100:.2f} % | Total PNL: {total_pnl * 100:.2f} % | Total Volume: {total_volume} | Total positions: {total_short + total_long} --> Accuracy: {total_accuracy:.2%} ",
                              "",
                              f"Long: {total_long} --> Accuracy: {accuracy_long:.2%} | Short: {total_short} --> Accuracy: {accuracy_short:.2%}"])
                df = pd.DataFrame(executor_handler.controller.target_prices).T
                df["level"] = df.index
                df.insert(0, "level", df.pop("level"))
                df.drop(columns=["side"], inplace=True)
                levels_str = format_df_for_printout(df.sort_values(by=["order_price"], ascending=False), table_format="psql")
                lines.extend([f"{levels_str}"])
                lines.extend([""])
        return "\n".join(lines)
