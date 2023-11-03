import time
from decimal import Decimal

import pandas_ta as ta  # noqa: F401

from hummingbot.core.data_type.common import TradeType
from hummingbot.smart_components.executors.position_executor.data_types import PositionConfig, TrailingStop
from hummingbot.smart_components.executors.position_executor.position_executor import PositionExecutor
from hummingbot.smart_components.strategy_frameworks.data_types import OrderLevel
from hummingbot.smart_components.strategy_frameworks.market_making.market_making_controller_base import (
    MarketMakingControllerBase,
    MarketMakingControllerConfigBase,
)


class PriceFollowerV1Config(MarketMakingControllerConfigBase):
    strategy_name: str = "price_follower_v1"
    bb_length: int = 100
    bb_std: float = 2.0
    side_filter: bool = False
    smart_activation: bool = False
    debug_mode: bool = False
    activation_threshold: Decimal = Decimal("0.001")
    dynamic_target_spread: bool = False
    intra_spread_pct: float = 0.005
    min_price_pct_between_levels: float = 0.01
    liquidation_thold: bool = False


class PriceFollowerV1(MarketMakingControllerBase):
    def __init__(self, config: PriceFollowerV1Config):
        super().__init__(config)
        self.target_prices = {}
        self.config = config
        self.price_pct_between_levels: float = 0.0

    @property
    def order_levels_targets(self):
        return self.target_prices

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
        # TODO: Think about this
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

        # Bollinger mid-price. Used as reference starting point for target prices
        candles_df["price_multiplier"] = bbp[f"BBM_{self.config.bb_length}_{self.config.bb_std}"]

        # Used to get the price percentage over the bollinger mid-price
        candles_df["spread_multiplier"] = bbp[f"BBB_{self.config.bb_length}_{self.config.bb_std}"] / 200

        # Calculate estimated price pct between levels
        candles_df["price_pct_between_levels"] = candles_df["spread_multiplier"] * self.config.intra_spread_pct

        # Update intra spread pct
        self.price_pct_between_levels = Decimal(candles_df["price_pct_between_levels"].iloc[-1])
        return candles_df

    def get_position_config(self, order_level: OrderLevel) -> PositionConfig:
        """
        Creates a PositionConfig object from an OrderLevel object.
        Here you can use technical indicators to determine the parameters of the position config.
        """
        # Get the close price of the trading pair
        close_price = self.get_close_price(self.config.exchange, self.config.trading_pair)

        # Get base amount from order level
        amount = order_level.order_amount_usd / close_price

        # Get bollinger mid-price and spread multiplier
        bollinger_mid_price, spread_multiplier = self.get_price_and_spread_multiplier()

        # Get liquidation pct
        liquidation_pct = 1 / self.config.leverage

        # This side multiplier is only to get the correct bollingrid side
        bollinger_side_multiplier = 1 if order_level.side == TradeType.BUY else -1
        side_name = "UPPER" if order_level.side == TradeType.BUY else "LOWER"

        # Calculate order price
        order_price = bollinger_mid_price * (1 + order_level.spread_factor * spread_multiplier * bollinger_side_multiplier)

        # Calculate gap tolerance for the order (because we're using market orders)
        tolerance = self.config.activation_threshold * self.price_pct_between_levels
        order_upper_limit = order_price * (1 + tolerance)
        order_lower_limit = order_price * (1 - tolerance)

        # This side will replace the original order level side if the order is placed from the opposite side
        fixed_side = TradeType.BUY if close_price < order_price else TradeType.SELL
        fixed_side_multiplier = 1 if fixed_side == TradeType.BUY else -1

        # Get triple barrier pcts
        stop_loss_pct, take_profit_pct, trailing_stop_activation_pct, trailing_stop_trailing_pct = self.get_triple_barrier_pct(
            liquidation_pct, order_level)

        # Calculate target prices according to the fixed side
        take_profit_price = order_price * (1 + take_profit_pct * fixed_side_multiplier)
        stop_loss_price = order_price * (1 - stop_loss_pct * fixed_side_multiplier)
        trailing_stop_activation_price = order_price * (1 + trailing_stop_activation_pct * fixed_side_multiplier)
        trailing_stop_trailing_price = order_price * (1 + (trailing_stop_activation_pct - trailing_stop_trailing_pct) * fixed_side_multiplier)

        # Update target prices for format status
        self.target_prices[f"{order_level.level}_{side_name}_{fixed_side.name}"] = {
            "side": fixed_side.name,
            "close_price": close_price,
            "order_price": order_price,
            "lower_limit": order_lower_limit,
            "upper_limit": order_upper_limit,
            "take_profit_price": take_profit_price,
            "stop_loss_price": stop_loss_price,
            "stop_loss_pct": f"{100 * stop_loss_pct:.3f}%",
            "trailing_stop_activation_price": trailing_stop_activation_price,
            "trailing_stop_activation_pct": f"{100 * trailing_stop_activation_pct:.3f}%",
            "trailing_stop_trailing_price": trailing_stop_trailing_price,
            "trailing_stop_trailing_pct": f"{100 * trailing_stop_trailing_pct:.3f}%"
        }

        # Stop trading if the intra level price pct is too low
        if spread_multiplier * Decimal(str(self.config.intra_spread_pct)) < self.config.min_price_pct_between_levels:
            self.target_prices[f"{order_level.level}_{side_name}_{fixed_side.name}"]["status"] = "Spread too low"
            return

        self.target_prices[f"{order_level.level}_{side_name}_{fixed_side.name}"]["status"] = "Waiting"

        # Smart activation of orders
        smart_activation_condition = (self.config.smart_activation and (fixed_side == TradeType.BUY and
                                                                        order_lower_limit <= close_price <= order_price)
                                      or (fixed_side == TradeType.SELL and
                                          order_upper_limit >= close_price >= order_price)
                                      )
        if not smart_activation_condition:
            return

        # This option is set to avoid placing orders during debugging
        if self.config.debug_mode:
            return

        # Mark as active
        self.target_prices[f"{order_level.level}_{side_name}_{fixed_side.name}"]["status"] = "Active"

        # Set up trailing stop
        if order_level.triple_barrier_conf.trailing_stop_trailing_delta and order_level.triple_barrier_conf.trailing_stop_trailing_delta:
            trailing_stop = TrailingStop(
                activation_price_delta=trailing_stop_activation_pct,
                trailing_delta=trailing_stop_trailing_pct,
            )
        else:
            trailing_stop = None

        # Build position config
        position_config = PositionConfig(
            timestamp=time.time(),
            trading_pair=self.config.trading_pair,
            exchange=self.config.exchange,
            side=fixed_side,
            amount=amount,
            take_profit=take_profit_pct,
            stop_loss=stop_loss_pct,
            time_limit=order_level.triple_barrier_conf.time_limit,
            entry_price=Decimal(order_price),
            open_order_type=order_level.triple_barrier_conf.open_order_type,
            take_profit_order_type=order_level.triple_barrier_conf.take_profit_order_type,
            trailing_stop=trailing_stop,
            leverage=self.config.leverage
        )
        return position_config

    def get_triple_barrier_pct(self,
                               liquidation_pct: float,
                               order_level: OrderLevel):
        """
        Calculates the triple barrier percentages according to the order level and the liquidation percentage.

        Notes:
            - The percentage can't be higher than 100% of the position value due to high volatility.
            - It's a good idea to preserve triple barrier proportions to tune TPs or TSLs properly.

        :param liquidation_pct: Liquidation percentage of the position
        :param order_level: Order level object
        :return: stop_loss_pct, take_profit_pct, trailing_stop_activation_pct, trailing_stop_trailing_pct
        """
        liquidation_pct = Decimal(str(liquidation_pct))
        # Calculate dynamic percentages
        dynamic_stop_loss_pct = self.price_pct_between_levels * order_level.triple_barrier_conf.stop_loss
        dynamic_take_profit_pct = self.price_pct_between_levels * order_level.triple_barrier_conf.take_profit
        dynamic_trailing_stop_activation_pct = (self.price_pct_between_levels *
                                                order_level.triple_barrier_conf.trailing_stop_activation_price_delta)
        dynamic_trailing_stop_trailing_pct = (self.price_pct_between_levels *
                                              order_level.triple_barrier_conf.trailing_stop_trailing_delta)

        # Calculate max percentages
        max_take_profit_pct = (order_level.triple_barrier_conf.take_profit /
                               order_level.triple_barrier_conf.stop_loss) * liquidation_pct
        max_trailing_stop_activation_pct = (order_level.triple_barrier_conf.trailing_stop_activation_price_delta /
                                            order_level.triple_barrier_conf.stop_loss) * liquidation_pct
        max_trailing_stop_trailing_pct = (order_level.triple_barrier_conf.trailing_stop_trailing_delta /
                                          order_level.triple_barrier_conf.stop_loss) * liquidation_pct

        # Calculate final percentages, ensuring they don't exceed the liquidation percentage
        stop_loss_pct = min(dynamic_stop_loss_pct, liquidation_pct)
        take_profit_pct = min(dynamic_take_profit_pct, max_take_profit_pct)
        trailing_stop_activation_pct = min(dynamic_trailing_stop_activation_pct, max_trailing_stop_activation_pct)
        trailing_stop_trailing_pct = min(dynamic_trailing_stop_trailing_pct, max_trailing_stop_trailing_pct)
        if self.config.liquidation_thold:
            return stop_loss_pct, take_profit_pct, trailing_stop_activation_pct, trailing_stop_trailing_pct
        else:
            return dynamic_stop_loss_pct, dynamic_take_profit_pct, dynamic_trailing_stop_activation_pct, dynamic_trailing_stop_trailing_pct
