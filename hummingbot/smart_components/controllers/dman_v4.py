import time
from decimal import Decimal

import pandas_ta as ta  # noqa: F401

from hummingbot.core.data_type.common import TradeType
from hummingbot.smart_components.executors.position_executor.data_types import PositionExecutorConfig, TrailingStop
from hummingbot.smart_components.executors.position_executor.position_executor import PositionExecutor
from hummingbot.smart_components.order_level_distributions.order_level_builder import OrderLevel
from hummingbot.smart_components.strategy_frameworks.market_making.market_making_controller_base import (
    MarketMakingControllerBase,
    MarketMakingControllerConfigBase,
)


class DManV4Config(MarketMakingControllerConfigBase):
    strategy_name: str = "dman_v4"
    bb_length: int = 100
    bb_std: float = 2.0
    smart_activation: bool = False
    activation_threshold: Decimal = Decimal("0.001")
    price_band: bool = False
    price_band_long_filter: Decimal = Decimal("0.8")
    price_band_short_filter: Decimal = Decimal("0.8")
    dynamic_target_spread: bool = False
    dynamic_spread_factor: bool = True


class DManV4(MarketMakingControllerBase):
    """
    Directional Market Making Strategy making use of NATR indicator to make spreads dynamic and shift the mid price.
    """

    def __init__(self, config: DManV4Config):
        super().__init__(config)
        self.config = config

    def refresh_order_condition(self, executor: PositionExecutor, order_level: OrderLevel) -> bool:
        """
        Checks if the order needs to be refreshed.
        You can reimplement this method to add more conditions.
        """
        if executor.position_config.timestamp + order_level.order_refresh_time > time.time():
            return False
        return True

    def early_stop_condition(self, executor: PositionExecutor, order_level: OrderLevel) -> bool:
        """
        If an executor has an active position, should we close it based on a condition.
        """
        return False

    def cooldown_condition(self, executor: PositionExecutor, order_level: OrderLevel) -> bool:
        """
        After finishing an order, the executor will be in cooldown for a certain amount of time.
        This prevents the executor from creating a new order immediately after finishing one and execute a lot
        of orders in a short period of time from the same side.
        """
        if executor.close_timestamp and executor.close_timestamp + order_level.cooldown_time > time.time():
            return True
        return False

    def get_processed_data(self):
        """
        Gets the price and spread multiplier from the last candlestick.
        """
        candles_df = self.candles[0].candles_df
        bbp = ta.bbands(candles_df["close"], length=self.config.bb_length, std=self.config.bb_std)

        candles_df["price_multiplier"] = bbp[f"BBM_{self.config.bb_length}_{self.config.bb_std}"]
        candles_df["spread_multiplier"] = bbp[f"BBB_{self.config.bb_length}_{self.config.bb_std}"] / 200
        return candles_df

    def get_position_config(self, order_level: OrderLevel) -> PositionExecutorConfig:
        """
        Creates a PositionConfig object from an OrderLevel object.
        Here you can use technical indicators to determine the parameters of the position config.
        """
        close_price = self.get_close_price(self.close_price_trading_pair)

        bollinger_mid_price, spread_multiplier = self.get_price_and_spread_multiplier()
        max_buy_price = bollinger_mid_price * (1 + self.config.price_band_long_filter * spread_multiplier)
        min_sell_price = bollinger_mid_price * (1 - self.config.price_band_short_filter * spread_multiplier)
        if not self.config.dynamic_spread_factor:
            spread_multiplier = 1
        side_multiplier = -1 if order_level.side == TradeType.BUY else 1
        order_spread_multiplier = order_level.spread_factor * spread_multiplier * side_multiplier
        order_price = close_price * (1 + order_spread_multiplier)
        amount = order_level.order_amount_usd / order_price

        # Avoid placing the order from the opposite side
        price_band_condition = self.config.price_band and (
            (order_price > max_buy_price and order_level.side == TradeType.BUY) or
            (order_price < min_sell_price and order_level.side == TradeType.SELL))
        if price_band_condition:
            return

        # Smart activation of orders
        smart_activation_condition = self.config.smart_activation and (
            side_multiplier == 1 and (close_price < order_price * (1 + self.config.activation_threshold)) or
            (side_multiplier == -1 and (close_price > order_price * (1 - self.config.activation_threshold))))
        if smart_activation_condition:
            return

        target_spread = spread_multiplier if self.config.dynamic_target_spread else 1
        if order_level.triple_barrier_conf.trailing_stop_trailing_delta and order_level.triple_barrier_conf.trailing_stop_trailing_delta:
            trailing_stop = TrailingStop(
                activation_price=order_level.triple_barrier_conf.trailing_stop_activation_price * target_spread,
                trailing_delta=order_level.triple_barrier_conf.trailing_stop_trailing_delta * target_spread,
            )
        else:
            trailing_stop = None
        position_config = PositionExecutorConfig(
            timestamp=time.time(),
            trading_pair=self.config.trading_pair,
            exchange=self.config.exchange,
            side=order_level.side,
            amount=amount,
            take_profit=order_level.triple_barrier_conf.take_profit * target_spread,
            stop_loss=order_level.triple_barrier_conf.stop_loss * target_spread,
            time_limit=order_level.triple_barrier_conf.time_limit,
            entry_price=Decimal(order_price),
            open_order_type=order_level.triple_barrier_conf.open_order_type,
            take_profit_order_type=order_level.triple_barrier_conf.take_profit_order_type,
            trailing_stop=trailing_stop,
            leverage=self.config.leverage
        )
        return position_config
