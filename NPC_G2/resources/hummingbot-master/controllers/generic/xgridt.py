import logging
from decimal import Decimal
from typing import Dict, List, Optional, Set

import pandas as pd
import pandas_ta as ta  # noqa: F401
from pydantic import BaseModel, Field
from scipy.signal import find_peaks

from hummingbot.client.config.config_data_types import ClientFieldData
from hummingbot.core.data_type.common import OrderType, PositionMode, PriceType, TradeType
from hummingbot.core.data_type.trade_fee import TokenAmount
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy_v2.controllers import ControllerBase, ControllerConfigBase
from hummingbot.strategy_v2.executors.position_executor.data_types import PositionExecutorConfig, TripleBarrierConfig
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, ExecutorAction, StopExecutorAction
from hummingbot.strategy_v2.models.executors import CloseType
from hummingbot.strategy_v2.models.executors_info import ExecutorInfo
from hummingbot.strategy_v2.utils.distributions import Distributions


class GridRangeConfig(BaseModel):
    id: str
    timestamp: int
    start_price: Decimal
    end_price: Decimal
    limit_price: Decimal
    total_amount_quote: Decimal
    stop_loss: Decimal = Decimal("0.1")
    time_limit: int = 60 * 60 * 2
    side: TradeType = TradeType.BUY
    min_order_amount: Decimal = Decimal("5")
    min_spread_between_orders: Decimal = Decimal("0.0005")
    open_order_type: OrderType = OrderType.LIMIT_MAKER
    take_profit_order_type: OrderType = OrderType.LIMIT_MAKER
    max_open_orders: int = 5
    max_orders_per_batch: Optional[int] = None
    order_frequency: int = 0
    executor_activation_bounds: Optional[Decimal] = None
    active: bool = True


class GridLevel(BaseModel):
    id: str
    price: Decimal
    amount_quote: Decimal
    step: Decimal
    side: TradeType
    stop_loss: Decimal
    open_order_type: OrderType
    take_profit_order_type: OrderType


class GridRange:
    _logger: Optional[HummingbotLogger] = None

    def __init__(self, config: GridRangeConfig):
        self.id = config.id
        self.start_time = config.timestamp
        self.close_time = None
        self.close_type = None
        self.start_price = config.start_price
        self.end_price = config.end_price
        self.limit_price = config.limit_price
        self.total_amount_quote = config.total_amount_quote
        self.stop_loss = config.stop_loss
        self.time_limit = config.time_limit
        self.side = config.side
        self.min_order_amount = config.min_order_amount
        self.min_spread_between_orders = config.min_spread_between_orders
        self.open_order_type = config.open_order_type
        self.take_profit_order_type = config.take_profit_order_type
        self.active = config.active
        self.order_frequency = config.order_frequency
        self.max_open_orders = config.max_open_orders
        self.executor_activation_bounds = config.executor_activation_bounds
        self.max_orders_per_batch = min(self.max_open_orders,
                                        config.max_orders_per_batch) if config.max_orders_per_batch else self.max_open_orders
        self.grid_levels = self._generate_grid_levels()

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def get_grid_levels_proposal_to_create(self, mid_price: Decimal, active_executors: List[ExecutorInfo],
                                           current_time: int):
        max_timestamp = max([executor.timestamp for executor in active_executors]) if len(active_executors) != 0 else 0
        max_executor_timestamp_condition = max_timestamp > current_time - self.order_frequency
        active_executors_order_placed = [executor for executor in active_executors if
                                         executor.is_active and executor.is_trading is False]
        max_open_orders_condition = len(active_executors_order_placed) >= self.max_open_orders
        if not self.active or max_executor_timestamp_condition or max_open_orders_condition:
            return []
        levels_allowed = self._filter_levels_by_activation_bounds(mid_price)
        active_executors_level_ids = [executor.custom_info["level_id"] for executor in active_executors]
        levels_allowed = [level for level in levels_allowed if level.id not in active_executors_level_ids]
        sorted_levels_by_proximity = self._sort_levels_by_proximity(mid_price, levels_allowed)
        return sorted_levels_by_proximity[:self.max_orders_per_batch]

    def stop_loss_condition(self, active_executors: List[ExecutorInfo], current_time: int):
        grid_level_ids = [level.id for level in self.grid_levels]
        active_executors_by_grid_range = [executor for executor in active_executors if executor.custom_info[
            "level_id"] in grid_level_ids]
        unrealized_pnl_pct = self.get_unrealized_pnl_pct(active_executors_by_grid_range)
        if unrealized_pnl_pct < -self.stop_loss:
            self.active = False
            self.close_type = CloseType.STOP_LOSS
            self.close_time = current_time
            self.logger().info(f"Grid Range {self.id} stopped by stop loss")

    def stop_loss_by_price_limit(self, mid_price: Decimal, current_time: int):
        if self.side == TradeType.BUY and mid_price < self.limit_price or \
                self.side == TradeType.SELL and mid_price > self.limit_price:
            self.active = False
            self.close_type = CloseType.STOP_LOSS
            self.close_time = current_time
            self.logger().info(f"Grid Range {self.id} stopped by price limit")

    def time_limit_condition(self, current_time: int):
        if self.start_time + self.time_limit < current_time:
            self.active = False
            self.close_type = CloseType.TIME_LIMIT
            self.close_time = current_time
            self.logger().info(f"Grid Range {self.id} stopped by time limit")

    def take_profit_condition(self, mid_price: Decimal, current_time: int):
        if self.side == TradeType.BUY and mid_price > self.end_price or \
                self.side == TradeType.SELL and mid_price < self.start_price:
            self.active = False
            self.close_type = CloseType.TAKE_PROFIT
            self.close_time = current_time
            self.logger().info(f"Grid Range {self.id} stopped by take profit")

    def get_unrealized_pnl_pct(self, active_executors: List[ExecutorInfo]):
        if active_executors:
            total_amount = sum([executor.filled_amount_quote for executor in active_executors])
            return sum([executor.net_pnl_quote for executor in active_executors]) / total_amount
        return Decimal("0")

    def _filter_levels_by_activation_bounds(self, mid_price: Decimal):
        if self.executor_activation_bounds:
            if self.side == TradeType.BUY:
                activation_bounds_price = mid_price * (1 - self.executor_activation_bounds)
                return [level for level in self.grid_levels if level.price >= activation_bounds_price]
            else:
                activation_bounds_price = mid_price * (1 + self.executor_activation_bounds)
                return [level for level in self.grid_levels if level.price <= activation_bounds_price]
        return self.grid_levels

    def _sort_levels_by_proximity(self, mid_price: Decimal, levels: List[GridLevel]):
        return sorted(levels, key=lambda level: abs(level.price - mid_price))

    def _generate_grid_levels(self):
        grid_levels = []
        step_proposed = self.min_spread_between_orders
        amount_proposed = self.min_order_amount
        total_amount = self.total_amount_quote
        grid_range = (self.end_price - self.start_price) / self.start_price
        theoretical_orders_by_step = grid_range / step_proposed
        theoretical_orders_by_amount = total_amount / amount_proposed
        orders = int(min(theoretical_orders_by_step, theoretical_orders_by_amount))
        prices = Distributions.linear(orders, float(self.start_price), float(self.end_price))
        step = (self.end_price - self.start_price) / self.end_price / orders
        amount_quote = total_amount / orders
        for i, price in enumerate(prices):
            grid_levels.append(GridLevel(id=f"{self.id}_P{i}",
                                         price=price,
                                         amount_quote=amount_quote,
                                         step=step, side=self.side,
                                         open_order_type=self.open_order_type,
                                         take_profit_order_type=self.take_profit_order_type,
                                         stop_loss=self.stop_loss
                                         ))
        return grid_levels

    def update_grid_level_prices(self, start_price: Decimal, end_price: Decimal, limit_price: Decimal):
        self.start_price = start_price
        self.end_price = end_price
        self.limit_price = limit_price
        prices = Distributions.linear(len(self.grid_levels), float(self.start_price), float(self.end_price))
        for grid_level, price in zip(self.grid_levels, prices):
            grid_level.price = price


class XGridTConfig(ControllerConfigBase):
    """
    Configuration required to run the Dneitor strategy for one connector and trading pair.
    """
    controller_name: str = "xgridt"
    candles_config: List[CandlesConfig] = []
    connector_name: str = "binance_perpetual"
    trading_pair: str = "WLD-USDT"
    candles_connector: str = "binance_perpetual"
    candles_trading_pair: str = "WLD-USDT"
    interval: str = "1m"
    # EMAs
    ema_short: int = 8
    ema_medium: int = 29
    ema_long: int = 31
    donchian_channel_length = 50
    natr_length = 100
    natr_multiplier = 2.0
    tp_default = 0.05
    prominence_pct_peaks = 0.05
    distance_between_peaks = 100

    total_amount_quote: Decimal = Field(default=Decimal("1000"), client_data=ClientFieldData(is_updatable=True))
    position_mode: PositionMode = PositionMode.HEDGE
    leverage: int = 1
    close_position_on_signal_change: bool = True
    grid_update_interval: Optional[int] = None
    take_profit_mode: str = "original"
    take_profit_step_multiplier: Decimal = Decimal("1")
    global_stop_loss: Decimal = Decimal("0.1")
    time_limit: Optional[int] = Field(default=60 * 60 * 2, client_data=ClientFieldData(is_updatable=True))
    executor_activation_bounds: Decimal = Field(default=Decimal("0.001"), client_data=ClientFieldData(is_updatable=True))
    general_activation_bounds: Decimal = Field(default=Decimal("0.001"), client_data=ClientFieldData(is_updatable=True))
    max_ranges_by_signal: int = Field(default=1, client_data=ClientFieldData(is_updatable=True))
    min_spread_between_orders: Optional[Decimal] = Field(default=Decimal("0.001"),
                                                         client_data=ClientFieldData(is_updatable=True))
    min_order_amount: Optional[Decimal] = Field(default=Decimal("1"),
                                                client_data=ClientFieldData(is_updatable=True))
    max_open_orders: int = Field(default=5, client_data=ClientFieldData(is_updatable=True))
    max_orders_per_batch: Optional[int] = Field(default=None, client_data=ClientFieldData(is_updatable=True))
    order_frequency: int = Field(default=0, client_data=ClientFieldData(is_updatable=True))
    extra_balance_base_usd: Decimal = Decimal("10")

    def update_markets(self, markets: Dict[str, Set[str]]) -> Dict[str, Set[str]]:
        if self.connector_name not in markets:
            markets[self.connector_name] = set()
        markets[self.connector_name].add(self.trading_pair)
        return markets


class XGridT(ControllerBase):
    def __init__(self, config: XGridTConfig, *args, **kwargs):
        self._last_grid_levels_update = 0
        self.grid_ranges: List[GridRange] = []
        self.config = config
        self.max_records = max(config.ema_short, config.ema_medium, config.ema_long, config.donchian_channel_length,
                               config.natr_length) + 500
        if len(self.config.candles_config) == 0:
            self.config.candles_config = [CandlesConfig(
                connector=config.candles_connector,
                trading_pair=config.candles_trading_pair,
                interval=config.interval,
                max_records=self.max_records
            )]
        super().__init__(config, *args, **kwargs)
        self.trading_rules = None

    def get_balance_requirements(self) -> List[TokenAmount]:
        if "perpetual" in self.config.connector_name:
            return []
        base_currency = self.config.trading_pair.split("-")[0]
        return [TokenAmount(base_currency, self.config.extra_balance_base_usd / self.get_mid_price())]

    def get_mid_price(self) -> Decimal:
        return self.market_data_provider.get_price_by_type(
            self.config.connector_name,
            self.config.trading_pair,
            PriceType.MidPrice
        )

    def active_executors(self, is_trading: bool) -> List[ExecutorInfo]:
        return [
            executor for executor in self.executors_info
            if executor.is_active and executor.is_trading == is_trading
        ]

    def get_all_active_executors(self) -> List:
        return [executor for executor in self.executors_info if executor.is_active]

    def get_allowed_grid_ranges_by_signal(self, signal: int) -> List[GridRange]:
        if signal == 0:
            return []
        side = TradeType.BUY if signal == 1 else TradeType.SELL
        return [grid_range for grid_range in self.active_grid_ranges() if grid_range.side == side]

    def update_grid_range_status_by_signal(self, signal: int):
        if signal == 0:
            return
        side = TradeType.BUY if signal == 1 else TradeType.SELL
        for grid_range in self.grid_ranges:
            if grid_range.side != side and grid_range.active:
                grid_range.active = False

    def get_grid_levels_proposal_to_create(self):
        active_executors = self.get_all_active_executors()
        levels_allowed = []
        for grid_range in self.active_grid_ranges():
            levels_allowed += grid_range.get_grid_levels_proposal_to_create(
                mid_price=self.get_mid_price(),
                active_executors=[executor for executor in active_executors if
                                  executor.custom_info["level_id"].split("_")[0] == grid_range.id],
                current_time=self.market_data_provider.time()
            )
        return levels_allowed

    def get_executor_actions_from_grid_levels(self, grid_levels_proposal: List[GridLevel]):
        executor_actions = []
        mid_price = self.get_mid_price()
        for grid_level in grid_levels_proposal:
            if self.config.take_profit_mode == "step_simple":
                take_profit = grid_level.step * self.config.take_profit_step_multiplier
            elif self.config.take_profit_mode == "trailing_stop":
                # TODO: Implement trailing stop for orders > than mid price and take profit limit for orders < than mid price
                raise ValueError("Trailing stop not implemented yet")
            else:
                step_multiplier = grid_level.step * self.config.take_profit_step_multiplier
                if grid_level.side == TradeType.BUY and grid_level.price > mid_price:
                    take_profit = (grid_level.price * (1 + step_multiplier) - mid_price) / mid_price
                    entry_price = mid_price
                elif grid_level.side == TradeType.SELL and grid_level.price < mid_price:
                    take_profit = (mid_price - grid_level.price * (1 - step_multiplier)) / mid_price
                    entry_price = mid_price
                else:
                    take_profit = step_multiplier
                    entry_price = grid_level.price
            executor_actions.append(
                CreateExecutorAction(controller_id=self.config.id,
                                     executor_config=PositionExecutorConfig(
                                         timestamp=self.market_data_provider.time(),
                                         connector_name=self.config.connector_name,
                                         trading_pair=self.config.trading_pair,
                                         entry_price=entry_price,
                                         amount=grid_level.amount_quote / grid_level.price,
                                         leverage=self.config.leverage,
                                         side=grid_level.side,
                                         level_id=grid_level.id,
                                         activation_bounds=[self.config.executor_activation_bounds,
                                                            self.config.executor_activation_bounds],
                                         triple_barrier_config=TripleBarrierConfig(
                                             take_profit=take_profit,
                                             time_limit=self.config.time_limit,
                                             open_order_type=grid_level.take_profit_order_type,
                                             take_profit_order_type=grid_level.take_profit_order_type,
                                         ))))
        return executor_actions

    def determine_executor_actions(self) -> List[ExecutorAction]:
        if self.trading_rules is None:
            self.trading_rules = self.market_data_provider.get_trading_rules(self.config.connector_name,
                                                                             self.config.trading_pair)
        self._check_and_update_grid_ranges()
        return self.determine_create_executor_actions() + self.determine_stop_executor_actions()

    @staticmethod
    def get_unbounded_tp(row, tp_default, side, high_peaks, low_peaks, criteria="latest"):
        timestamp = row.name
        close = row["close"]
        if side == TradeType.BUY:
            previous_peaks_higher_than_price = [price_peak for price_timestamp, price_peak in
                                                zip(high_peaks[0], high_peaks[1]) if
                                                price_timestamp < timestamp and price_peak > close]
            if previous_peaks_higher_than_price:
                if criteria == "latest":
                    return previous_peaks_higher_than_price[-1]
                elif criteria == "closest":
                    return min(previous_peaks_higher_than_price, key=lambda x: abs(x - row["close"]))
            else:
                return close * (1 + tp_default)
        else:
            previous_peaks_lower_than_price = [price_peak for price_timestamp, price_peak in
                                               zip(low_peaks[0], low_peaks[1]) if
                                               price_timestamp < timestamp and price_peak < close]
            if previous_peaks_lower_than_price:
                if criteria == "latest":
                    return previous_peaks_lower_than_price[-1]
                elif criteria == "closest":
                    return min(previous_peaks_lower_than_price, key=lambda x: abs(x - row["close"]))
            else:
                return close * (1 - tp_default)

    async def update_processed_data(self):
        df = self.market_data_provider.get_candles_df(connector_name=self.config.candles_connector,
                                                      trading_pair=self.config.candles_trading_pair,
                                                      interval=self.config.interval,
                                                      max_records=self.max_records)
        # Add indicators
        df.ta.ema(length=self.config.ema_short, append=True)
        df.ta.ema(length=self.config.ema_medium, append=True)
        df.ta.ema(length=self.config.ema_long, append=True)
        df.ta.donchian(lower_length=self.config.donchian_channel_length,
                       upper_length=self.config.donchian_channel_length, append=True)
        df.ta.natr(length=self.config.natr_length, append=True)

        short_ema = df[f"EMA_{self.config.ema_short}"]
        medium_ema = df[f"EMA_{self.config.ema_medium}"]
        long_ema = df[f"EMA_{self.config.ema_long}"]

        long_condition = (short_ema > medium_ema) & (medium_ema > long_ema) & (short_ema > long_ema)
        short_condition = (short_ema < medium_ema) & (medium_ema < long_ema) & (short_ema < long_ema)

        df["signal"] = 0
        df.loc[long_condition, "signal"] = 1
        df.loc[short_condition, "signal"] = -1

        peaks = self.get_peaks(df, prominence_percentage=self.config.prominence_pct_peaks, distance=self.config.distance_between_peaks,)

        high_peaks = peaks["high_peaks"]
        low_peaks = peaks["low_peaks"]
        df.loc[high_peaks[0], "TP_LONG"] = high_peaks[1]
        df.loc[low_peaks[0], "TP_SHORT"] = low_peaks[1]
        df["TP_LONG"].ffill(inplace=True)
        df["TP_SHORT"].ffill(inplace=True)

        # Apply the function to create the TP_LONG column
        df["TP_LONG"] = df.apply(
            lambda x: x.TP_LONG if pd.notna(x.TP_LONG) and x.TP_LONG > x.high else self.get_unbounded_tp(x,
                                                                                                         self.config.tp_default,
                                                                                                         TradeType.BUY,
                                                                                                         high_peaks,
                                                                                                         low_peaks),
            axis=1)
        df["TP_SHORT"] = df.apply(
            lambda x: x.TP_SHORT if pd.notna(x.TP_SHORT) and x.TP_SHORT < x.low else self.get_unbounded_tp(x,
                                                                                                           self.config.tp_default,
                                                                                                           TradeType.SELL,
                                                                                                           high_peaks,
                                                                                                           low_peaks),
            axis=1)

        df["SL_LONG"] = df[f"DCL_{self.config.donchian_channel_length}_{self.config.donchian_channel_length}"]
        df["SL_SHORT"] = df[f"DCU_{self.config.donchian_channel_length}_{self.config.donchian_channel_length}"]
        df["LIMIT_LONG"] = df[f"DCL_{self.config.donchian_channel_length}_{self.config.donchian_channel_length}"] * (
            1 - self.config.natr_multiplier * df[f"NATR_{self.config.natr_length}"] / 100)
        df["LIMIT_SHORT"] = df[f"DCU_{self.config.donchian_channel_length}_{self.config.donchian_channel_length}"] * (
            1 + self.config.natr_multiplier * df[f"NATR_{self.config.natr_length}"] / 100)
        # Update processed data
        self.processed_data.update(df.iloc[-1].to_dict())
        self.processed_data["features"] = df

    def _check_and_update_grid_ranges(self):
        long_start_price = self.processed_data["SL_LONG"]
        long_end_price = self.processed_data["TP_LONG"]
        long_limit_price = self.processed_data["LIMIT_LONG"]

        short_start_price = self.processed_data["TP_SHORT"]

        short_end_price = self.processed_data["SL_SHORT"]
        short_limit_price = self.processed_data["LIMIT_SHORT"]

        if self.config.grid_update_interval and self._last_grid_levels_update + self.config.grid_update_interval < self.market_data_provider.time():
            for grid_range in self.active_grid_ranges():
                if grid_range.side == TradeType.BUY:
                    grid_range.update_grid_level_prices(long_start_price, long_end_price, long_limit_price)
                else:
                    grid_range.update_grid_level_prices(short_start_price, short_end_price, short_limit_price)

        if len(self.get_allowed_grid_ranges_by_signal(1)) < self.config.max_ranges_by_signal and self.processed_data["signal"] == 1:
            trade_type = TradeType.BUY
            start_price = long_start_price
            end_price = long_end_price
            limit_price = long_limit_price

        elif len(self.get_allowed_grid_ranges_by_signal(-1)) < self.config.max_ranges_by_signal and self.processed_data["signal"] == -1:
            trade_type = TradeType.SELL
            start_price = short_start_price
            end_price = short_end_price
            limit_price = short_limit_price
        else:
            return
        grid_range = GridRangeConfig(id=f"R{len(self.grid_ranges)}",
                                     timestamp=self.market_data_provider.time(),
                                     start_price=start_price,
                                     end_price=end_price,
                                     limit_price=limit_price,
                                     time_limit=self.config.time_limit,
                                     total_amount_quote=self.config.total_amount_quote,
                                     stop_loss=self.config.global_stop_loss,
                                     side=trade_type,
                                     min_order_amount=max(self.config.min_order_amount,
                                                          self.trading_rules.min_notional_size),
                                     min_spread_between_orders=self.config.min_spread_between_orders,
                                     open_order_type=OrderType.LIMIT_MAKER,
                                     take_profit_order_type=OrderType.LIMIT_MAKER,
                                     executor_activation_bounds=self.config.executor_activation_bounds,
                                     max_open_orders=self.config.max_open_orders,
                                     order_frequency=self.config.order_frequency,
                                     max_orders_per_batch=self.config.max_orders_per_batch,
                                     active=True)
        self.logger().info(f"Adding new grid range {grid_range.id}, start price: {start_price}, end price: {end_price}")
        self.grid_ranges.append(GridRange(grid_range))

    def determine_create_executor_actions(self) -> List[ExecutorAction]:
        grid_levels_proposal = self.get_grid_levels_proposal_to_create()
        return self.get_executor_actions_from_grid_levels(grid_levels_proposal)

    def get_unrealized_pnl(self):
        return sum([executor.net_pnl_quote for executor in
                    self.active_executors(is_trading=True)]) / self.config.total_amount_quote

    def active_grid_ranges(self):
        return [grid_range for grid_range in self.grid_ranges if grid_range.active]

    def update_grid_range_by_triple_barrier(self):
        grid_range_to_stop = []
        current_time = self.market_data_provider.time()
        active_executors = self.active_executors(is_trading=True)
        for grid_range in self.active_grid_ranges():
            active_executors_by_grid = [executor for executor in active_executors if
                                        executor.custom_info["level_id"].split("_")[0] == grid_range.id]
            grid_range.stop_loss_condition(active_executors_by_grid, current_time)
            grid_range.stop_loss_by_price_limit(self.get_mid_price(), current_time)
            grid_range.time_limit_condition(current_time)
            grid_range.take_profit_condition(self.get_mid_price(), current_time)
        return grid_range_to_stop

    def get_executors_out_of_activation_bounds(self):
        mid_price = self.get_mid_price()
        long_activation_bounds = mid_price * (1 - self.config.general_activation_bounds)
        short_activation_bounds = mid_price * (1 + self.config.general_activation_bounds)
        active_executors_order_placed = self.active_executors(is_trading=False)
        long_executors_to_stop = [executor.id for executor in active_executors_order_placed if
                                  executor.side == TradeType.BUY and executor.config.entry_price <= long_activation_bounds]
        short_executors_to_stop = [executor.id for executor in active_executors_order_placed if
                                   executor.side == TradeType.SELL and executor.config.entry_price >= short_activation_bounds]
        executors_id_to_stop = set(long_executors_to_stop + short_executors_to_stop)
        return executors_id_to_stop

    def determine_stop_executor_actions(self) -> List[ExecutorAction]:
        if self.config.close_position_on_signal_change:
            self.update_grid_range_status_by_signal(self.processed_data["signal"])
        self.update_grid_range_by_triple_barrier()
        executors_id_to_stop = set()
        active_executors = self.get_all_active_executors()
        executors_id_to_stop.update(self.get_executors_out_of_activation_bounds())
        for grid_range in self.grid_ranges:
            if not grid_range.active:
                executors_id_to_stop.update([executor.id for executor in active_executors
                                             if executor.custom_info["level_id"].split("_")[0] == grid_range.id])
        return [StopExecutorAction(controller_id=self.config.id, executor_id=executor) for executor in
                list(executors_id_to_stop)]

    def get_peaks(self, candles, prominence_percentage: float = 0.01, distance: int = 5):
        prominence_nominal = self._calculate_prominence(candles, prominence_percentage)
        high_peaks, low_peaks = self._find_price_peaks(candles, prominence_nominal, distance)
        high_peak_prices = candles['high'].iloc[high_peaks]
        low_peak_prices = candles['low'].iloc[low_peaks]
        high_peaks_index = candles.iloc[high_peaks].index
        low_peaks_index = candles.iloc[low_peaks].index
        return {
            "high_peaks": [high_peaks_index, high_peak_prices],
            "low_peaks": [low_peaks_index, low_peak_prices],
        }

    def _calculate_prominence(self, candles, prominence_percentage: float) -> float:
        price_range = candles['high'].max() - candles['low'].min()
        return price_range * prominence_percentage

    def _find_price_peaks(self, candles, prominence_nominal: float, distance: int):
        high_peaks, _ = find_peaks(candles['high'], prominence=prominence_nominal, distance=distance)
        low_peaks, _ = find_peaks(-candles['low'], prominence=prominence_nominal, distance=distance)
        return high_peaks, low_peaks

    def to_format_status(self) -> List[str]:
        status = []
        for grid_range in self.grid_ranges:
            status.append(f"Grid Range {grid_range.id} active: {grid_range.active} start price: {grid_range.start_price:.4f} end price: {grid_range.end_price:.4f} limit price: {grid_range.limit_price:.4f}")
            for level in grid_range.grid_levels:
                executor_related = next((executor for executor in self.executors_info if executor.custom_info[
                    "level_id"] == level.id and executor.is_active), None)
                if executor_related:
                    status.append(
                        f"Grid Level {level.id} price: {level.price:.3f} amount: {level.amount_quote:.2f} status: {executor_related.status} pnl: {executor_related.net_pnl_quote:.2f}")
                else:
                    status.append(f"Grid Level {level.id} price: {level.price:.4f} amount: {level.amount_quote:.2f}")
            status.append(
                f"Unrealized PnL: {grid_range.get_unrealized_pnl_pct(self.active_executors(is_trading=True)):.2f}")
        status.append("\n\nSignal: " + str(self.processed_data["signal"]))
        status.append(f"LONG TARGETS: TP: {self.processed_data['TP_LONG']:.4f} SL: {self.processed_data['SL_LONG']:.4f} LIMIT: {self.processed_data['LIMIT_LONG']:.4f}")
        status.append(f"SHORT TARGETS: TP: {self.processed_data['TP_SHORT']:.4f} SL: {self.processed_data['SL_SHORT']:.4f} LIMIT: {self.processed_data['LIMIT_SHORT']:.4f}")
        return status
