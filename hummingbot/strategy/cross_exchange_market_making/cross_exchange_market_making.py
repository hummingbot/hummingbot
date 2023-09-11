import logging
from collections import defaultdict, deque
from decimal import Decimal
from enum import Enum
from functools import lru_cache
from math import ceil, floor
from typing import Dict, List, Tuple, cast

import pandas as pd
from bidict import bidict

from hummingbot.client.performance import PerformanceMetrics
from hummingbot.client.settings import AllConnectorSettings
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.core.clock import Clock
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.trade_fee import TokenAmount
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderExpiredEvent,
    OrderFilledEvent,
    SellOrderCompletedEvent,
)
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.strategy.cross_exchange_market_making.cross_exchange_market_making_config_map_pydantic import (
    CrossExchangeMarketMakingConfigMap,
    PassiveOrderRefreshMode,
)
from hummingbot.strategy.maker_taker_market_pair import MakerTakerMarketPair
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.strategy_py_base import StrategyPyBase

from .order_id_market_pair_tracker import OrderIDMarketPairTracker

s_float_nan = float("nan")
s_decimal_zero = Decimal(0)
s_decimal_nan = Decimal("nan")
s_logger = None


class LogOption(Enum):
    NULL_ORDER_SIZE = 0
    REMOVING_ORDER = 1
    ADJUST_ORDER = 2
    CREATE_ORDER = 3
    MAKER_ORDER_FILLED = 4
    STATUS_REPORT = 5
    MAKER_ORDER_HEDGED = 6


class CrossExchangeMarketMakingStrategy(StrategyPyBase):

    OPTION_LOG_ALL = (
        LogOption.NULL_ORDER_SIZE,
        LogOption.REMOVING_ORDER,
        LogOption.ADJUST_ORDER,
        LogOption.CREATE_ORDER,
        LogOption.MAKER_ORDER_FILLED,
        LogOption.STATUS_REPORT,
        LogOption.MAKER_ORDER_HEDGED
    )

    ORDER_ADJUST_SAMPLE_INTERVAL = 5
    ORDER_ADJUST_SAMPLE_WINDOW = 12

    SHADOW_MAKER_ORDER_KEEP_ALIVE_DURATION = 60.0 * 15
    CANCEL_EXPIRY_DURATION = 60.0

    @classmethod
    def logger(cls):
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(__name__)
        return s_logger

    def init_params(self,
                    config_map: CrossExchangeMarketMakingConfigMap,
                    market_pairs: List[MakerTakerMarketPair],
                    status_report_interval: float = 900,
                    logging_options: int = OPTION_LOG_ALL,
                    hb_app_notification: bool = False
                    ):
        """
        Initializes a cross exchange market making strategy object.

        :param config_map: Strategy configuration map
        :param market_pairs: list of cross exchange market pairs
        :param logging_options: bit field for what types of logging to enable in this strategy object
        :param hb_app_notification:
        """
        self._config_map = config_map
        self._market_pairs = {
            (market_pair.maker.market, market_pair.maker.trading_pair): market_pair
            for market_pair in market_pairs
        }
        self._maker_markets = set([market_pair.maker.market for market_pair in market_pairs])
        self._taker_markets = set([market_pair.taker.market for market_pair in market_pairs])
        self._all_markets_ready = False
        self._conversions_ready = False

        self._anti_hysteresis_timers = {}
        self._order_fill_buy_events = {}
        self._order_fill_sell_events = {}
        self._suggested_price_samples = {}

        self._last_timestamp = 0
        self._status_report_interval = status_report_interval
        self._market_pair_tracker = OrderIDMarketPairTracker()

        # Holds ongoing hedging orders mapped to their respective maker fill trades
        self._ongoing_hedging = bidict()

        self._logging_options = logging_options

        self._last_taker_buy_price = None
        self._last_taker_sell_price = None

        self._main_task = None
        self._gateway_quotes_task = None
        self._cancel_outdated_orders_task = None
        self._hedge_maker_order_tasks = []

        self._last_conv_rates_logged = 0
        self._hb_app_notification = hb_app_notification

        # Holds active maker orders, all its taker orders ever created
        self._maker_to_taker_order_ids = {}
        # Holds active taker orders, and their respective maker orders
        self._taker_to_maker_order_ids = {}
        # Holds hedging trade ids for respective maker orders
        self._maker_to_hedging_trades = {}

        all_markets = list(self._maker_markets | self._taker_markets)

        self.add_markets(all_markets)

    @property
    def order_amount(self):
        return self._config_map.order_amount

    @property
    def min_profitability(self):
        return self._config_map.min_profitability / Decimal("100")

    @property
    def order_size_taker_volume_factor(self):
        return self._config_map.order_size_taker_volume_factor / Decimal("100")

    @property
    def order_size_taker_balance_factor(self):
        return self._config_map.order_size_taker_balance_factor / Decimal("100")

    @property
    def order_size_portfolio_ratio_limit(self):
        return self._config_map.order_size_portfolio_ratio_limit / Decimal("100")

    @property
    def top_depth_tolerance(self):
        return self._config_map.top_depth_tolerance

    @property
    def anti_hysteresis_duration(self):
        return self._config_map.anti_hysteresis_duration

    @property
    def limit_order_min_expiration(self):
        return self._config_map.limit_order_min_expiration

    @property
    def status_report_interval(self):
        return self._status_report_interval

    @property
    def adjust_order_enabled(self):
        return self._config_map.adjust_order_enabled

    @property
    def use_oracle_conversion_rate(self):
        return self._config_map.use_oracle_conversion_rate

    @property
    def taker_to_maker_base_conversion_rate(self):
        return self._config_map.conversion_rate_mode.taker_to_maker_base_conversion_rate

    @property
    def taker_to_maker_quote_conversion_rate(self):
        return self._config_map.taker_to_maker_quote_conversion_rate

    @property
    def slippage_buffer(self):
        return self._config_map.slippage_buffer / Decimal("100")

    @property
    def active_maker_limit_orders(self) -> List[Tuple[ExchangeBase, LimitOrder]]:
        return [(ex, order, order.client_order_id) for ex, order in self._sb_order_tracker.active_limit_orders
                if order.client_order_id in self._maker_to_taker_order_ids.keys()]

    @property
    def cached_limit_orders(self) -> List[Tuple[ExchangeBase, LimitOrder]]:
        return self._sb_order_tracker.shadow_limit_orders

    @property
    def active_maker_bids(self) -> List[Tuple[ExchangeBase, LimitOrder]]:
        return [(market, limit_order) for market, limit_order, order_id in self.active_maker_limit_orders
                if limit_order.is_buy]

    @property
    def active_maker_asks(self) -> List[Tuple[ExchangeBase, LimitOrder]]:
        return [(market, limit_order) for market, limit_order, order_id in self.active_maker_limit_orders
                if not limit_order.is_buy]

    @property
    def active_order_canceling(self):
        return self._config_map.active_order_canceling

    @property
    def adjust_orders_enabled(self):
        return self._config_map.adjust_orders_enabled

    @property
    def gas_to_maker_base_conversion_rate(self):
        return self._config_map.gas_to_maker_base_conversion_rate

    @property
    def gateway_transaction_cancel_interval(self):
        return self._config_map.gateway_transaction_cancel_interval

    @property
    def logging_options(self) -> int:
        return self._logging_options

    @logging_options.setter
    def logging_options(self, logging_options: Tuple):
        self._logging_options = logging_options

    @property
    def market_info_to_active_orders(self) -> Dict[MarketTradingPairTuple, List[LimitOrder]]:
        return self._sb_order_tracker.market_pair_to_active_orders

    @staticmethod
    @lru_cache(maxsize=10)
    def is_gateway_market(market_info: MarketTradingPairTuple) -> bool:
        return market_info.market.name in AllConnectorSettings.get_gateway_amm_connector_names()

    def get_conversion_rates(self, market_pair: MarketTradingPairTuple):
        quote_pair, quote_rate_source, quote_rate, base_pair, base_rate_source, base_rate, gas_pair, gas_rate_source, \
            gas_rate = self._config_map.conversion_rate_mode.get_conversion_rates(market_pair)
        if quote_rate is None:
            self.logger().warning(f"Can't find a conversion rate for {quote_pair}")
        if base_rate is None:
            self.logger().warning(f"Can't find a conversion rate for {base_pair}")
        if gas_rate is None:
            self.logger().warning(f"Can't find a conversion rate for {gas_pair}")
        return quote_pair, quote_rate_source, quote_rate, base_pair, base_rate_source, base_rate, gas_pair, \
            gas_rate_source, gas_rate

    def log_conversion_rates(self):
        for market_pair in self._market_pairs.values():
            quote_pair, quote_rate_source, quote_rate, base_pair, base_rate_source, base_rate, gas_pair, \
                gas_rate_source, gas_rate = self.get_conversion_rates(market_pair)
            if quote_pair.split("-")[0] != quote_pair.split("-")[1]:
                self.logger().info(f"{quote_pair} ({quote_rate_source}) conversion rate: {PerformanceMetrics.smart_round(quote_rate)}")
            if base_pair.split("-")[0] != base_pair.split("-")[1]:
                self.logger().info(f"{base_pair} ({base_rate_source}) conversion rate: {PerformanceMetrics.smart_round(base_rate)}")
            if self.is_gateway_market(market_pair.taker):
                if gas_pair is not None and gas_pair.split("-")[0] != gas_pair.split("-")[1]:
                    self.logger().info(f"{gas_pair} ({gas_rate_source}) conversion rate: {PerformanceMetrics.smart_round(gas_rate)}")

    def oracle_status_df(self):
        columns = ["Source", "Pair", "Rate"]
        data = []
        for market_pair in self._market_pairs.values():
            quote_pair, quote_rate_source, quote_rate, base_pair, base_rate_source, base_rate, gas_pair, \
                gas_rate_source, gas_rate = self.get_conversion_rates(market_pair)
            if quote_pair.split("-")[0] != quote_pair.split("-")[1]:
                data.extend([
                    [quote_rate_source, quote_pair, PerformanceMetrics.smart_round(quote_rate)],
                ])
            if base_pair.split("-")[0] != base_pair.split("-")[1]:
                data.extend([
                    [base_rate_source, base_pair, PerformanceMetrics.smart_round(base_rate)],
                ])
            if self.is_gateway_market(market_pair.taker):
                if gas_pair is not None and gas_pair.split("-")[0] != gas_pair.split("-")[1]:
                    data.extend([
                        [gas_rate_source, gas_pair, PerformanceMetrics.smart_round(gas_rate)],
                    ])
        return pd.DataFrame(data=data, columns=columns)

    def format_status(self) -> str:
        lines = []
        warning_lines = []
        tracked_maker_orders = {}

        # Go through the currently open limit orders, and group them by market pair.
        for market, limit_order, order_id in self.active_maker_limit_orders:
            typed_limit_order = limit_order
            market_pair = self._market_pair_tracker.get_market_pair_from_order_id(typed_limit_order.client_order_id)
            if market_pair not in tracked_maker_orders:
                tracked_maker_orders[market_pair] = {typed_limit_order.client_order_id: typed_limit_order}
            else:
                tracked_maker_orders[market_pair][typed_limit_order.client_order_id] = typed_limit_order

        for market_pair in self._market_pairs.values():
            warning_lines.extend(self.network_warning([market_pair.maker, market_pair.taker]))

            if not self.is_gateway_market(market_pair.taker):
                markets_df = self.market_status_data_frame([market_pair.maker, market_pair.taker])
            else:
                markets_df = self.market_status_data_frame([market_pair.maker])
                # Market status for gateway
                bid_price = "" if self._last_taker_buy_price is None else self._last_taker_buy_price
                ask_price = "" if self._last_taker_sell_price is None else self._last_taker_sell_price
                if self._last_taker_buy_price is not None and self._last_taker_sell_price is not None:
                    mid_price = (self._last_taker_buy_price + self._last_taker_sell_price) / 2
                else:
                    mid_price = ""
                taker_data = {
                    "Exchange": market_pair.taker.market.display_name,
                    "Market": market_pair.taker.trading_pair,
                    "Best Bid Price": bid_price,
                    "Best Ask Price": ask_price,
                    "Mid Price": mid_price
                }
                if markets_df is not None:
                    markets_df = markets_df.append(taker_data, ignore_index=True)
            lines.extend(["", "  Markets:"] +
                         ["    " + line for line in str(markets_df).split("\n")])

            oracle_df = self.oracle_status_df()
            if not oracle_df.empty:
                lines.extend(["", "  Rate conversion:"] +
                             ["    " + line for line in str(oracle_df).split("\n")])

            assets_df = self.wallet_balance_data_frame([market_pair.maker, market_pair.taker])
            lines.extend(["", "  Assets:"] +
                         ["    " + line for line in str(assets_df).split("\n")])

            # See if there're any open orders.
            if market_pair in tracked_maker_orders and len(tracked_maker_orders[market_pair]) > 0:
                limit_orders = list(tracked_maker_orders[market_pair].values())
                bid, ask = self.get_top_bid_ask(market_pair)
                mid_price = (bid + ask) / 2
                df = LimitOrder.to_pandas(limit_orders, float(mid_price))
                df_lines = str(df).split("\n")
                lines.extend(["", "  Active maker market orders:"] +
                             ["    " + line for line in df_lines])
            else:
                lines.extend(["", "  No active maker market orders."])

            warning_lines.extend(self.balance_warning([market_pair.maker, market_pair.taker]))

        if len(warning_lines) > 0:
            lines.extend(["", "  *** WARNINGS ***"] + warning_lines)

        return "\n".join(lines)

    def start(self, clock: Clock, timestamp: float):
        super().start(clock, timestamp)
        self._last_timestamp = timestamp

    def tick(self, timestamp: float):
        """
        Clock tick entry point.

        For cross exchange market making strategy, this function mostly just checks the readiness and connection
        status of markets, and then delegates the processing of each market pair to process_market_pair().

        :param timestamp: current tick timestamp
        """
        current_tick = (timestamp // self._status_report_interval)
        last_tick = (self._last_timestamp // self._status_report_interval)
        should_report_warnings = ((current_tick > last_tick) and
                                  (LogOption.STATUS_REPORT in self.logging_options)
                                  )

        # Perform clock tick with the market pair tracker.
        self._market_pair_tracker.tick(timestamp)

        if not self._all_markets_ready:
            self._all_markets_ready = all([market.ready for market in self.active_markets])
            if not self._all_markets_ready:
                # Markets not ready yet. Don't do anything.
                if should_report_warnings:
                    self.logger().warning("Markets are not ready. No market making trades are permitted.")
                return
            else:
                # Markets are ready, ok to proceed.
                if LogOption.STATUS_REPORT:
                    self.logger().info("Markets are ready.")

        if not self._conversions_ready:
            for market_pair in self._market_pairs.values():
                _, _, quote_rate, _, _, base_rate, _, _, _ = self.get_conversion_rates(market_pair)
                if not quote_rate or not base_rate:
                    if should_report_warnings:
                        self.logger().warning("Conversion rates are not ready. No market making trades are permitted.")
                    return

            # Conversion rates are ready, ok to proceed.
            self._conversions_ready = True
            if LogOption.STATUS_REPORT:
                self.logger().info("Conversion rates are ready. Trading started.")

        if should_report_warnings:
            # Check if all markets are still connected or not. If not, log a warning.
            if not all([market.network_status is NetworkStatus.CONNECTED for market in self.active_markets]):
                self.logger().warning("WARNING: Some markets are not connected or are down at the moment. Market "
                                      "making may be dangerous when markets or networks are unstable.")

        if self._gateway_quotes_task is None or self._gateway_quotes_task.done():
            self._gateway_quotes_task = safe_ensure_future(self.get_gateway_quotes())

        if self.ready_for_new_trades():
            if self._main_task is None or self._main_task.done():
                self._main_task = safe_ensure_future(self.main(timestamp))

        if self._cancel_outdated_orders_task is None or self._cancel_outdated_orders_task.done():
            self._cancel_outdated_orders_task = safe_ensure_future(self.apply_gateway_transaction_cancel_interval())

    async def main(self, timestamp: float):
        try:
            # Calculate a mapping from market pair to list of active limit orders on the market.
            market_pair_to_active_orders = defaultdict(list)

            for maker_market, limit_order, order_id in self.active_maker_limit_orders:
                market_pair = self._market_pairs.get((maker_market, limit_order.trading_pair))
                if market_pair is None:
                    self.log_with_clock(logging.WARNING,
                                        f"The in-flight maker order in for the trading pair '{limit_order.trading_pair}' "
                                        f"does not correspond to any whitelisted trading pairs. Skipping.")
                    continue

                if not self._sb_order_tracker.has_in_flight_cancel(limit_order.client_order_id) and \
                        limit_order.client_order_id in self._maker_to_taker_order_ids.keys():
                    market_pair_to_active_orders[market_pair].append(limit_order)

            # Process each market pair independently.
            for market_pair in self._market_pairs.values():
                await self.process_market_pair(timestamp, market_pair, market_pair_to_active_orders[market_pair])

            # log conversion rates every 5 minutes
            if self._last_conv_rates_logged + (60. * 5) < timestamp:
                self.log_conversion_rates()
                self._last_conv_rates_logged = timestamp
        finally:
            self._last_timestamp = timestamp

    async def get_gateway_quotes(self):
        for market_pair in self._market_pairs.values():
            if self.is_gateway_market(market_pair.taker):
                _, _, quote_rate, _, _, base_rate, _, _, _ = self.get_conversion_rates(market_pair)
                order_amount = self._config_map.order_amount * base_rate
                order_price = await market_pair.taker.market.get_order_price(
                    market_pair.taker.trading_pair,
                    True,
                    order_amount
                )
                self._last_taker_buy_price = order_price
                order_price = await market_pair.taker.market.get_order_price(
                    market_pair.taker.trading_pair,
                    False,
                    order_amount
                )
                self._last_taker_sell_price = order_price

    def ready_for_new_trades(self) -> bool:
        """
        Returns True if there is no outstanding unfilled order.
        """
        if len(self._ongoing_hedging.keys()) > 0:
            return False
        return True

    async def apply_gateway_transaction_cancel_interval(self):
        # XXX (martin_kou): Concurrent cancellations are not supported before the nonce architecture is fixed.
        # See: https://app.shortcut.com/coinalpha/story/24553/nonce-architecture-in-current-amm-trade-and-evm-approve-apis-is-incorrect-and-causes-trouble-with-concurrent-requests
        from hummingbot.connector.gateway.amm.gateway_evm_amm import GatewayEVMAMM
        gateway_connectors: List[GatewayEVMAMM] = []
        for market_pair in self._market_pairs.values():
            if self.is_gateway_market(market_pair.taker):
                gateway_connectors.append(cast(GatewayEVMAMM, market_pair.taker.market))

    def has_active_taker_order(self, market_pair: MarketTradingPairTuple):
        # Market orders are not being submitted as taker orders, limit orders are preferred at all times
        limit_orders = self._sb_order_tracker.get_limit_orders()
        limit_orders = limit_orders.get(market_pair, {})
        if len(limit_orders) > 0:
            if len(set(limit_orders.keys()).intersection(set(self._taker_to_maker_order_ids.keys()))) > 0:
                return True
        return False

    async def process_market_pair(self, timestamp: float, market_pair: MarketTradingPairTuple, active_orders: List):
        """
        For market pair being managed by this strategy object, do the following:

         1. Check whether any of the existing orders need to be canceled.
         2. Check if new orders should be created.

        For each market pair, only 1 active bid offer and 1 active ask offer is allowed at a time at maximum.

        If an active order is determined to be not needed at step 1, it would cancel the order within step 1.

        If there's no active order found in step 1, and condition allows (i.e. profitability, account balance, etc.),
        then a new limit order would be created at step 2.

        Combining step 1 and step 2 over time, means the offers made to the maker market side would be adjusted over
        time regularly.

        :param market_pair: cross exchange market pair
        :param active_orders: list of active maker limit orders associated with the market pair
        """
        has_active_bid = False
        has_active_ask = False
        need_adjust_order = False
        anti_hysteresis_timer = self._anti_hysteresis_timers.get(market_pair, 0)

        global s_decimal_zero

        self.take_suggested_price_sample(timestamp, market_pair)

        for active_order in active_orders:
            # Mark the has_active_bid and has_active_ask flags
            is_buy = active_order.is_buy
            if is_buy:
                has_active_bid = True
            else:
                has_active_ask = True

            # Suppose the active order is hedged on the taker market right now, what's the average price the hedge
            # would happen?
            current_hedging_price = await self.calculate_effective_hedging_price(
                market_pair,
                is_buy,
                active_order.quantity
            )

            # See if it's still profitable to keep the order on maker market. If not, remove it.
            if not await self.check_if_still_profitable(market_pair, active_order, current_hedging_price):
                continue

            if isinstance(self._config_map.order_refresh_mode, PassiveOrderRefreshMode):
                continue

            # See if I still have enough balance on my wallet to fill the order on maker market, and to hedge the
            # order on taker market. If not, adjust it.
            if not await self.check_if_sufficient_balance(market_pair, active_order):
                continue

            # If prices have moved, one side is still profitable, here cancel and
            # place at the next tick.
            if timestamp > anti_hysteresis_timer:
                if not await self.check_if_price_has_drifted(market_pair, active_order):
                    need_adjust_order = True
                    continue

        # If order adjustment is needed in the next tick, set the anti-hysteresis timer s.t. the next order adjustment
        # for the same pair wouldn't happen within the time limit.
        if need_adjust_order:
            self._anti_hysteresis_timers[market_pair] = timestamp + self._config_map.anti_hysteresis_duration

        # If there's both an active bid and ask, then there's no need to think about making new limit orders.
        if has_active_bid and has_active_ask:
            return

        # If there are pending taker orders, wait for them to complete
        if self.has_active_taker_order(market_pair):
            return

        # See if it's profitable to place a limit order on maker market.
        await self.check_and_create_new_orders(market_pair, has_active_bid, has_active_ask)

    async def hedge_filled_maker_order(self,
                                       maker_order_id: str,
                                       order_filled_event: OrderFilledEvent):
        """
        If a limit order previously made to the maker side has been filled, hedge it on the taker side.
        :param order_filled_event: event object
        """
        order_id = order_filled_event.order_id
        market_pair = self._market_pair_tracker.get_market_pair_from_order_id(order_id)

        # Make sure to only hedge limit orders.
        if market_pair is not None and order_id not in self._taker_to_maker_order_ids.keys():
            limit_order_record = self._sb_order_tracker.get_shadow_limit_order(order_id)
            order_fill_record = (limit_order_record, order_filled_event)

            # Store the limit order fill event in a map, s.t. it can be processed in check_and_hedge_orders()
            # later.
            if order_filled_event.trade_type is TradeType.BUY:
                if market_pair not in self._order_fill_buy_events:
                    self._order_fill_buy_events[market_pair] = [order_fill_record]
                else:
                    self._order_fill_buy_events[market_pair].append(order_fill_record)

                if LogOption.MAKER_ORDER_FILLED in self.logging_options:
                    self.log_with_clock(
                        logging.INFO,
                        f"({market_pair.maker.trading_pair}) Maker buy order of "
                        f"{order_filled_event.amount} {market_pair.maker.base_asset} filled."
                    )

            else:
                if market_pair not in self._order_fill_sell_events:
                    self._order_fill_sell_events[market_pair] = [order_fill_record]
                else:
                    self._order_fill_sell_events[market_pair].append(order_fill_record)

                if LogOption.MAKER_ORDER_FILLED in self.logging_options:
                    self.log_with_clock(
                        logging.INFO,
                        f"({market_pair.maker.trading_pair}) Maker sell order of "
                        f"{order_filled_event.amount} {market_pair.maker.base_asset} filled."
                    )

            # Call check_and_hedge_orders() to emit the orders on the taker side.
            try:
                await self.check_and_hedge_orders(maker_order_id, market_pair)
            except Exception:
                self.log_with_clock(logging.ERROR, "Unexpected error.", exc_info=True)

    def hedge_tasks_cleanup(self):
        hedge_maker_order_tasks = []
        for task in self._hedge_maker_order_tasks:
            if not task.done():
                hedge_maker_order_tasks += [task]
        self._hedge_maker_order_tasks = hedge_maker_order_tasks

    def handle_unfilled_taker_order(self, order_event):
        order_id = order_event.order_id
        market_pair = self._market_pair_tracker.get_market_pair_from_order_id(order_id)

        # Resubmit hedging order
        self.hedge_tasks_cleanup()
        self._hedge_maker_order_tasks += [safe_ensure_future(
            self.check_and_hedge_orders(order_id, market_pair)
        )]

        # Remove the cancelled, failed or expired taker order
        del self._taker_to_maker_order_ids[order_event.order_id]

    def did_fill_order(self, order_filled_event: OrderFilledEvent):
        maker_order_id = order_filled_event.order_id
        exchange_trade_id = order_filled_event.exchange_trade_id
        if maker_order_id in self._maker_to_taker_order_ids.keys():
            # Maker order filled
            # Check if this fill was already processed or not
            if maker_order_id not in self._maker_to_hedging_trades.keys():
                self._maker_to_hedging_trades[maker_order_id] = []
            if exchange_trade_id not in self._maker_to_hedging_trades[maker_order_id]:
                # This maker fill has not been processed yet, submit Taker hedge order
                # Values have to be unique in a bidict

                self._maker_to_hedging_trades[maker_order_id] += [exchange_trade_id]

                self.hedge_tasks_cleanup()
                self._hedge_maker_order_task = safe_ensure_future(
                    self.hedge_filled_maker_order(maker_order_id, order_filled_event)
                )

    def did_cancel_order(self, order_canceled_event: OrderCancelledEvent):
        if order_canceled_event.order_id in self._taker_to_maker_order_ids.keys():
            self.handle_unfilled_taker_order(order_canceled_event)

    def did_fail_order(self, order_failed_event: MarketOrderFailureEvent):
        if order_failed_event.order_id in self._taker_to_maker_order_ids.keys():
            self.handle_unfilled_taker_order(order_failed_event)

    def did_expire_order(self, order_expired_event: OrderExpiredEvent):
        if order_expired_event.order_id in self._taker_to_maker_order_ids.keys():
            self.handle_unfilled_taker_order(order_expired_event)

    def did_complete_buy_order(self, order_completed_event: BuyOrderCompletedEvent):
        """
        Output log message when a bid order (on maker side or taker side) is completely taken.
        :param order_completed_event: event object
        """
        order_id = order_completed_event.order_id
        market_pair = self._market_pair_tracker.get_market_pair_from_order_id(order_id)

        if market_pair is not None:
            if order_id in self._maker_to_taker_order_ids.keys():
                limit_order_record = self._sb_order_tracker.get_limit_order(market_pair.maker, order_id)
                self.log_with_clock(
                    logging.INFO,
                    f"({market_pair.maker.trading_pair}) Maker buy order {order_id} "
                    f"({limit_order_record.quantity} {limit_order_record.base_currency} @ "
                    f"{limit_order_record.price} {limit_order_record.quote_currency}) has been completely filled."
                )
                self.notify_hb_app_with_timestamp(
                    f"Maker BUY order ({limit_order_record.quantity} {limit_order_record.base_currency} @ "
                    f"{limit_order_record.price} {limit_order_record.quote_currency}) is filled."
                )
                # Leftover other side maker order will be left in the market until its expiration or potential fill
                # Since the buy side side was filled, the sell side maker order is unlikely to be filled, therefore
                # it'll likey expire
                # The others are left in the market to collect market making fees
                # Meanwhile new maker order may be placed
            if order_id in self._taker_to_maker_order_ids.keys():
                self.log_with_clock(
                    logging.INFO,
                    f"({market_pair.taker.trading_pair}) Taker buy order {order_id} for "
                    f"({order_completed_event.base_asset_amount} {order_completed_event.base_asset} has been completely filled."
                )
                self.notify_hb_app_with_timestamp(
                    f"Taker BUY order ({order_completed_event.base_asset_amount} {order_completed_event.base_asset} "
                    f"{order_completed_event.quote_asset}) is filled."
                )
                maker_order_id = self._taker_to_maker_order_ids[order_id]
                # Remove the completed taker order
                del self._taker_to_maker_order_ids[order_id]
                # Get all active taker order ids for the maker order id
                active_taker_ids = set(self._taker_to_maker_order_ids.keys()).intersection(set(
                    self._maker_to_taker_order_ids[maker_order_id]))
                if len(active_taker_ids) == 0:
                    # Was maker order fully filled?
                    maker_order_ids = list(order_id for market, limit_order, order_id in self.active_maker_limit_orders)
                    if maker_order_id not in maker_order_ids:
                        # Remove the completed fully hedged maker order
                        del self._maker_to_taker_order_ids[maker_order_id]
                        del self._maker_to_hedging_trades[maker_order_id]

                try:
                    self.del_order_from_ongoing_hedging(order_id)
                except KeyError:
                    self.logger().warning(f"Ongoing hedging not found for order id {order_id}")

                # Delete hedged maker fill event
                fill_events = []
                for fill_event in self._order_fill_sell_events[market_pair]:
                    if self.is_fill_event_in_ongoing_hedging(fill_event):
                        fill_events += [fill_event]
                self._order_fill_sell_events[market_pair] = fill_events

                # Cleanup maker fill events - no longer needed to create taker orders if all fills were hedged
                if len(self._order_fill_sell_events[market_pair]) == 0:
                    del self._order_fill_sell_events[market_pair]

    def did_complete_sell_order(self, order_completed_event: SellOrderCompletedEvent):
        """
        Output log message when a ask order (on maker side or taker side) is completely taken.
        :param order_completed_event: event object
        """
        order_id = order_completed_event.order_id
        market_pair = self._market_pair_tracker.get_market_pair_from_order_id(order_id)

        if market_pair is not None:
            if order_id in self._maker_to_taker_order_ids.keys():
                limit_order_record = self._sb_order_tracker.get_limit_order(market_pair.maker, order_id)
                self.log_with_clock(
                    logging.INFO,
                    f"({market_pair.maker.trading_pair}) Maker sell order {order_id} "
                    f"({limit_order_record.quantity} {limit_order_record.base_currency} @ "
                    f"{limit_order_record.price} {limit_order_record.quote_currency}) has been completely filled."
                )
                self.notify_hb_app_with_timestamp(
                    f"Maker sell order ({limit_order_record.quantity} {limit_order_record.base_currency} @ "
                    f"{limit_order_record.price} {limit_order_record.quote_currency}) is filled."
                )
                # Leftover other side maker order will be left in the market until its expiration or potential fill
                # Since the sell side side was filled, the buy side maker order is unlikely to be filled, therefore
                # it'll likey expire
                # The others are left in the market to collect market making fees
                # Meanwhile new maker order may be placed
            if order_id in self._taker_to_maker_order_ids.keys():
                self.log_with_clock(
                    logging.INFO,
                    f"({market_pair.taker.trading_pair}) Taker sell order {order_id} for "
                    f"({order_completed_event.base_asset_amount} {order_completed_event.base_asset} "
                    f"has been completely filled."
                )
                self.notify_hb_app_with_timestamp(
                    f"Taker SELL order ({order_completed_event.base_asset_amount} {order_completed_event.base_asset} "
                    f"{order_completed_event.quote_asset}) is filled."
                )
                maker_order_id = self._taker_to_maker_order_ids[order_id]
                # Remove the completed taker order
                del self._taker_to_maker_order_ids[order_id]
                # Get all active taker order ids for the maker order id
                active_taker_ids = set(self._taker_to_maker_order_ids.keys()).intersection(set(
                    self._maker_to_taker_order_ids[maker_order_id]))
                if len(active_taker_ids) == 0:
                    # Was maker order fully filled?
                    maker_order_ids = list(order_id for market, limit_order, order_id in self.active_maker_limit_orders)
                    if maker_order_id not in maker_order_ids:
                        # Remove the completed fully hedged maker order
                        del self._maker_to_taker_order_ids[maker_order_id]
                        del self._maker_to_hedging_trades[maker_order_id]

                try:
                    self.del_order_from_ongoing_hedging(order_id)
                except KeyError:
                    self.logger().warning(f"Ongoing hedging not found for order id {order_id}")

                # Delete hedged maker fill event
                fill_events = []
                for fill_event in self._order_fill_buy_events[market_pair]:
                    if self.is_fill_event_in_ongoing_hedging(fill_event):
                        fill_events += [fill_event]
                self._order_fill_buy_events[market_pair] = fill_events

                # Cleanup maker fill events - no longer needed to create taker orders if all fills were hedged
                if len(self._order_fill_buy_events[market_pair]) == 0:
                    del self._order_fill_buy_events[market_pair]

    async def check_if_price_has_drifted(self, market_pair: MakerTakerMarketPair, active_order: LimitOrder):
        """
        Given a currently active limit order on maker side, check if its current price is still valid, based on the
        current hedging price on taker market, depth tolerance, and transient orders on the maker market captured by
        recent suggested price samples.

        If the active order's price is no longer valid, the order will be canceled.

        This function is only used when active order cancelation is enabled.

        :param market_pair: cross exchange market pair
        :param active_order: a current active limit order in the market pair
        :return: True if the order stays, False if the order has been canceled and we need to re place the orders.
        """
        is_buy = active_order.is_buy
        order_price = active_order.price
        order_quantity = active_order.quantity
        suggested_price = await self.get_market_making_price(market_pair, is_buy, order_quantity)

        if suggested_price != order_price:
            if LogOption.ADJUST_ORDER in self.logging_options:
                self.log_with_clock(
                    logging.INFO,
                    f"({market_pair.maker.trading_pair}) The current limit {'bid' if is_buy else 'ask'} order for "
                    f"{active_order.quantity} {market_pair.maker.base_asset} at "
                    f"{order_price:.8g} {market_pair.maker.quote_asset} is now below the suggested order "
                    f"price at {suggested_price}. Going to cancel the old order and create a new one..."
                )
            self.cancel_maker_order(market_pair, active_order.client_order_id)
            self.log_with_clock(logging.DEBUG,
                                f"Current {'buy' if is_buy else 'sell'} order price={order_price}, "
                                f"suggested order price={suggested_price}")
            return False

        return True

    async def check_and_hedge_orders(self,
                                     maker_order_id: str,
                                     market_pair: MakerTakerMarketPair):
        """
        Look into the stored and un-hedged limit order fill events, and emit orders to hedge them, depending on
        availability of funds on the taker market.

        :param market_pair: cross exchange market pair
        """

        buy_fill_records = self.get_unhedged_buy_records(market_pair)
        sell_fill_records = self.get_unhedged_sell_records(market_pair)

        buy_fill_quantity = sum([fill_event.amount for _, fill_event in buy_fill_records])
        sell_fill_quantity = sum([fill_event.amount for _, fill_event in sell_fill_records])

        global s_decimal_zero

        taker_trading_pair = market_pair.taker.trading_pair
        taker_market = market_pair.taker.market

        # Convert maker order size (in maker base asset) to taker order size (in taker base asset)
        _, _, quote_rate, _, _, base_rate, _, _, _ = self.get_conversion_rates(market_pair)

        if buy_fill_quantity > 0:
            # Maker buy
            # Taker sell
            taker_slippage_adjustment_factor = Decimal("1") - self.slippage_buffer

            hedged_order_quantity = min(
                buy_fill_quantity / base_rate,
                taker_market.get_available_balance(market_pair.taker.base_asset) *
                self.order_size_taker_balance_factor
            )
            quantized_hedge_amount = taker_market.quantize_order_amount(taker_trading_pair, Decimal(hedged_order_quantity))

            avg_fill_price = (sum([r.price * r.amount for _, r in buy_fill_records]) /
                              sum([r.amount for _, r in buy_fill_records]))

            self.check_multiple_buy_orders(buy_fill_records)
            if self.is_gateway_market(market_pair.taker):
                order_price = await market_pair.taker.market.get_order_price(
                    taker_trading_pair,
                    False,
                    quantized_hedge_amount)
                if order_price is None:
                    self.logger().warning("Gateway: failed to obtain order price. No hedging order will be submitted.")
                    return
                taker_top = order_price
            else:
                taker_top = taker_market.get_price(taker_trading_pair, False)
                order_price = taker_market.get_price_for_volume(
                    taker_trading_pair, False, quantized_hedge_amount
                ).result_price

            self.log_with_clock(logging.INFO, f"Calculated by HB order_price: {order_price}")
            order_price *= taker_slippage_adjustment_factor
            order_price = taker_market.quantize_order_price(taker_trading_pair, order_price)
            self.log_with_clock(logging.INFO, f"Slippage buffer adjusted order_price: {order_price}")

            if quantized_hedge_amount > s_decimal_zero:
                self.place_order(
                    market_pair,
                    False,
                    False,
                    quantized_hedge_amount,
                    order_price,
                    maker_order_id,
                    buy_fill_records
                )

                if LogOption.MAKER_ORDER_HEDGED in self.logging_options:
                    self.log_with_clock(
                        logging.INFO,
                        f"({market_pair.maker.trading_pair}) Hedged maker buy order(s) of "
                        f"{buy_fill_quantity} {market_pair.maker.base_asset} on taker market to lock in profits. "
                        f"(maker avg price={avg_fill_price}, taker top={taker_top})"
                    )
            else:
                self.log_with_clock(
                    logging.INFO,
                    f"({market_pair.maker.trading_pair}) Current maker buy fill amount of "
                    f"{buy_fill_quantity} {market_pair.maker.base_asset} is less than the minimum order amount "
                    f"allowed on the taker market. No hedging possible yet."
                )

        if sell_fill_quantity > 0:
            # Maker sell
            # Taker buy
            taker_slippage_adjustment_factor = Decimal("1") + self.slippage_buffer

            if self.is_gateway_market(market_pair.taker):
                taker_price = await market_pair.taker.market.get_order_price(
                    taker_trading_pair,
                    True,
                    sell_fill_quantity / base_rate
                )
                if taker_price is None:
                    self.logger().warning("Gateway: failed to obtain order price. No hedging order will be submitted.")
                    return
            else:
                taker_price = taker_market.get_price_for_volume(
                    taker_trading_pair,
                    True,
                    sell_fill_quantity / base_rate
                ).result_price

            hedged_order_quantity = min(
                sell_fill_quantity / base_rate,
                taker_market.get_available_balance(market_pair.taker.quote_asset) /
                taker_price * self.order_size_taker_balance_factor
            )
            quantized_hedge_amount = taker_market.quantize_order_amount(
                taker_trading_pair,
                Decimal(hedged_order_quantity)
            )

            avg_fill_price = (sum([r.price * r.amount for _, r in sell_fill_records]) /
                              sum([r.amount for _, r in sell_fill_records]))

            self.check_multiple_sell_orders(sell_fill_records)
            if self.is_gateway_market(market_pair.taker):
                order_price = await market_pair.taker.market.get_order_price(
                    taker_trading_pair,
                    True,
                    quantized_hedge_amount)
                if order_price is None:
                    self.logger().warning("Gateway: failed to obtain order price. No hedging order will be submitted.")
                    return
                taker_top = order_price
            else:
                taker_top = taker_market.get_price(taker_trading_pair, True)
                order_price = taker_market.get_price_for_volume(
                    taker_trading_pair, True, quantized_hedge_amount
                ).result_price

            self.log_with_clock(logging.INFO, f"Calculated by HB order_price: {order_price}")
            order_price *= taker_slippage_adjustment_factor
            order_price = taker_market.quantize_order_price(taker_trading_pair, order_price)
            self.log_with_clock(logging.INFO, f"Slippage buffer adjusted order_price: {order_price}")

            if quantized_hedge_amount > s_decimal_zero:
                self.place_order(
                    market_pair,
                    True,
                    False,
                    quantized_hedge_amount,
                    order_price,
                    maker_order_id,
                    sell_fill_records,
                )

                if LogOption.MAKER_ORDER_HEDGED in self.logging_options:
                    self.log_with_clock(
                        logging.INFO,
                        f"({market_pair.maker.trading_pair}) Hedged maker sell order(s) of "
                        f"{sell_fill_quantity} {market_pair.maker.base_asset} on taker market to lock in profits. "
                        f"(maker avg price={avg_fill_price}, taker top={taker_top})"
                    )
            else:
                self.log_with_clock(
                    logging.INFO,
                    f"({market_pair.maker.trading_pair}) Current maker sell fill amount of "
                    f"{sell_fill_quantity} {market_pair.maker.base_asset} is less than the minimum order amount "
                    f"allowed on the taker market. No hedging possible yet."
                )

    def get_adjusted_limit_order_size(self, market_pair: MakerTakerMarketPair) -> Tuple[Decimal, Decimal]:
        """
        Given the proposed order size of a proposed limit order (regardless of bid or ask), adjust and refine the order
        sizing according to either the trade size override setting (if it exists), or the portfolio ratio limit (if
        no trade size override exists).

        Also, this function will convert the input order size proposal from floating point to Decimal by quantizing the
        order size.

        :param market_pair: cross exchange market pair
        :rtype: Decimal
        """
        maker_market = market_pair.maker.market
        trading_pair = market_pair.maker.trading_pair
        if self._config_map.order_amount and self._config_map.order_amount > 0:
            base_order_size = self._config_map.order_amount
            return maker_market.quantize_order_amount(trading_pair, Decimal(base_order_size))
        else:
            return self.get_order_size_after_portfolio_ratio_limit(market_pair)

    def get_order_size_after_portfolio_ratio_limit(self, market_pair: MakerTakerMarketPair) -> Decimal:
        """
        Given the proposed order size of a proposed limit order (regardless of bid or ask), adjust the order sizing
        according to the portfolio ratio limit.

        Also, this function will convert the input order size proposal from floating point to Decimal by quantizing the
        order size.

        :param market_pair: cross exchange market pair
        :rtype: Decimal
        """
        maker_market = market_pair.maker.market
        trading_pair = market_pair.maker.trading_pair
        base_balance = maker_market.get_balance(market_pair.maker.base_asset)
        quote_balance = maker_market.get_balance(market_pair.maker.quote_asset)
        current_price = (maker_market.get_price(trading_pair, True) +
                         maker_market.get_price(trading_pair, False)) * Decimal(0.5)
        maker_portfolio_value = base_balance + quote_balance / current_price
        adjusted_order_size = maker_portfolio_value * self.order_size_portfolio_ratio_limit

        return maker_market.quantize_order_amount(trading_pair, Decimal(adjusted_order_size))

    async def get_market_making_size(self,
                                     market_pair: MakerTakerMarketPair,
                                     is_bid: bool):
        """
        Get the ideal market making order size given a market pair and a side.

        This function does a few things:
         1. Calculate the largest order size possible given the current balances on both maker and taker markets.
         2. Calculate the largest order size possible that's still profitable after hedging.


        :param market_pair: The cross exchange market pair to calculate order price/size limits.
        :param is_bid: Whether the order to make will be bid or ask.
        :return: a Decimal which is the size of maker order.
        """
        taker_trading_pair = market_pair.taker.trading_pair
        maker_market = market_pair.maker.market
        taker_market = market_pair.taker.market

        # Maker order size (in base asset)
        size = self.get_adjusted_limit_order_size(market_pair)

        # Convert maker order size (in maker base asset) to taker order size (in taker base asset)
        _, _, quote_rate, _, _, base_rate, _, _, _ = self.get_conversion_rates(market_pair)
        taker_size = size / base_rate

        if is_bid:
            # Maker buy
            # Taker sell
            maker_balance_in_quote = maker_market.get_available_balance(market_pair.maker.quote_asset)
            taker_balance = taker_market.get_available_balance(market_pair.taker.base_asset) * \
                self.order_size_taker_balance_factor

            if self.is_gateway_market(market_pair.taker):
                taker_price = await taker_market.get_order_price(taker_trading_pair,
                                                                 False,
                                                                 taker_size)
                if taker_price is None:
                    self.logger().warning("Gateway: failed to obtain order price."
                                          "No market making order will be submitted.")
                    return s_decimal_zero
            else:
                try:
                    taker_price = taker_market.get_vwap_for_volume(
                        taker_trading_pair, False, taker_size
                    ).result_price
                except ZeroDivisionError:
                    assert size == s_decimal_zero
                    return s_decimal_zero

            if taker_price is None:
                self.logger().warning("Failed to obtain a taker sell order price. No order will be submitted.")
                order_amount = Decimal("0")
            else:
                maker_balance = maker_balance_in_quote / \
                    (taker_price * self.markettaker_to_maker_base_conversion_rate(market_pair))
                taker_balance *= base_rate
                order_amount = min(maker_balance, taker_balance, size)

            return maker_market.quantize_order_amount(market_pair.maker.trading_pair, Decimal(order_amount))

        else:
            # Maker sell
            # Taker buy
            maker_balance = maker_market.get_available_balance(market_pair.maker.base_asset)
            taker_balance_in_quote = taker_market.get_available_balance(market_pair.taker.quote_asset) * \
                self.order_size_taker_balance_factor

            if self.is_gateway_market(market_pair.taker):
                taker_price = await taker_market.get_order_price(taker_trading_pair,
                                                                 True,
                                                                 size)
                if taker_price is None:
                    self.logger().warning("Gateway: failed to obtain order price."
                                          "No market making order will be submitted.")
                    return s_decimal_zero
            else:
                try:
                    taker_price = taker_market.get_price_for_quote_volume(
                        taker_trading_pair, True, taker_balance_in_quote
                    ).result_price
                except ZeroDivisionError:
                    assert size == s_decimal_zero
                    return s_decimal_zero

            if taker_price is None:
                self.logger().warning("Failed to obtain a taker buy order price. No order will be submitted.")
                order_amount = Decimal("0")
            else:
                taker_slippage_adjustment_factor = Decimal("1") + self.slippage_buffer
                taker_balance = taker_balance_in_quote / (taker_price * taker_slippage_adjustment_factor)
                taker_balance *= base_rate
                order_amount = min(maker_balance, taker_balance, size)

            return maker_market.quantize_order_amount(market_pair.maker.trading_pair, Decimal(order_amount))

    async def get_market_making_price(self,
                                      market_pair: MarketTradingPairTuple,
                                      is_bid: bool,
                                      size: Decimal):
        """
        Get the ideal market making order price given a market pair, side and size.

        The price returned is calculated by adding the profitability to vwap of hedging it on the taker side.
        or if it's not possible to hedge the trade profitably, then the returned order price will be none.

        :param market_pair: The cross exchange market pair to calculate order price/size limits.
        :param is_bid: Whether the order to make will be bid or ask.
        :param size: size of the maker order.
        :return: a Decimal which is the price or None if order cannot be hedged on the taker market
        """
        taker_trading_pair = market_pair.taker.trading_pair
        maker_market = market_pair.maker.market
        taker_market = market_pair.taker.market
        top_bid_price = s_decimal_nan
        top_ask_price = s_decimal_nan
        next_price_below_top_ask = s_decimal_nan

        # Convert maker order size (in maker base asset) to taker order size (in taker base asset)
        _, _, quote_rate, base_pair, _, base_rate, _, _, _ = self.get_conversion_rates(market_pair)
        size /= base_rate

        top_bid_price, top_ask_price = self.get_top_bid_ask_from_price_samples(market_pair)

        if is_bid:
            # Maker buy
            # Taker sell
            if not Decimal.is_nan(top_bid_price):
                # Calculate the next price above top bid
                price_quantum = maker_market.get_order_price_quantum(
                    market_pair.maker.trading_pair,
                    top_bid_price
                )
                price_above_bid = (ceil(top_bid_price / price_quantum) + 1) * price_quantum

            if self.is_gateway_market(market_pair.taker):
                taker_price = await taker_market.get_order_price(taker_trading_pair,
                                                                 False,
                                                                 size)
                if taker_price is None:
                    self.logger().warning("Gateway: failed to obtain order price."
                                          "No market making order will be submitted.")
                    return s_decimal_nan
            else:
                try:
                    taker_price = taker_market.get_vwap_for_volume(taker_trading_pair, False, size).result_price
                except ZeroDivisionError:
                    return s_decimal_nan

            if taker_price is None:
                return

            # Convert them from taker's price to maker's price
            taker_price *= self.markettaker_to_maker_base_conversion_rate(market_pair)

            # you are buying on the maker market and selling on the taker market
            maker_price = taker_price / (1 + self.min_profitability)

            # # If your bid is higher than highest bid price, reduce it to one tick above the top bid price
            if self.adjust_order_enabled:
                # If maker bid order book is not empty
                if not Decimal.is_nan(price_above_bid):
                    maker_price = min(maker_price, price_above_bid)

            price_quantum = maker_market.get_order_price_quantum(
                market_pair.maker.trading_pair,
                maker_price
            )

            # Rounds down for ensuring profitability
            maker_price = (floor(maker_price / price_quantum)) * price_quantum

            return maker_price
        else:
            # Maker sell
            # Taker buy
            if not Decimal.is_nan(top_ask_price):
                # Calculate the next price below top ask
                price_quantum = maker_market.get_order_price_quantum(
                    market_pair.maker.trading_pair,
                    top_ask_price
                )
                next_price_below_top_ask = (floor(top_ask_price / price_quantum) - 1) * price_quantum

            if self.is_gateway_market(market_pair.taker):
                taker_price = await taker_market.get_order_price(taker_trading_pair,
                                                                 True,
                                                                 size)
                if taker_price is None:
                    self.logger().warning("Gateway: failed to obtain order price."
                                          "No market making order will be submitted.")
                    return s_decimal_nan
            else:
                try:
                    taker_price = taker_market.get_vwap_for_volume(taker_trading_pair, True, size).result_price
                except ZeroDivisionError:
                    return s_decimal_nan

            taker_price *= self.markettaker_to_maker_base_conversion_rate(market_pair)

            # You are selling on the maker market and buying on the taker market
            maker_price = taker_price * (1 + self.min_profitability)

            # If your ask is lower than the the top ask, increase it to just one tick below top ask
            if self.adjust_order_enabled:
                # If maker ask order book is not empty
                if not Decimal.is_nan(next_price_below_top_ask):
                    maker_price = max(maker_price, next_price_below_top_ask)

            price_quantum = maker_market.get_order_price_quantum(
                market_pair.maker.trading_pair,
                maker_price
            )

            # Rounds up for ensuring profitability
            maker_price = (ceil(maker_price / price_quantum)) * price_quantum

            return maker_price

    async def calculate_effective_hedging_price(self,
                                                market_pair: MarketTradingPairTuple,
                                                is_bid: bool,
                                                size: Decimal):
        """
        Returns current possible taker price expressed in units of the maker market quote asset
        :param market_pair: The cross exchange market pair to calculate order price/size limits.
        :param is_bid: Whether the order to make will be bid or ask.
        :param size: The size of the maker order.
        :return: a Decimal which is the hedging price on the maker market given the current taker market
        """
        taker_trading_pair = market_pair.taker.trading_pair
        taker_market = market_pair.taker.market

        # Convert maker order size (in maker base asset) to taker order size (in taker base asset)
        _, _, quote_rate, _, _, base_rate, _, _, gas_rate = self.get_conversion_rates(market_pair)
        size /= base_rate

        # Calculate the next price from the top, and the order size limit.
        if is_bid:
            # Maker buy
            # Taker sell
            if self.is_gateway_market(market_pair.taker):
                taker_price = await taker_market.get_order_price(taker_trading_pair,
                                                                 False,
                                                                 size)
                if taker_price is None:
                    self.logger().warning("Gateway: failed to obtain order price."
                                          "Failed to calculate effective hedging price.")
                    return s_decimal_nan
            else:
                try:
                    taker_price = taker_market.get_vwap_for_volume(taker_trading_pair, False, size).result_price
                except ZeroDivisionError:
                    return None

            # If quote assets are not same, convert them from taker's quote asset to maker's quote asset
            taker_price *= self.markettaker_to_maker_base_conversion_rate(market_pair)

            return taker_price
        else:
            # Maker sell
            # Taker buy
            if self.is_gateway_market(market_pair.taker):
                taker_price = await taker_market.get_order_price(taker_trading_pair,
                                                                 True,
                                                                 size)
                if taker_price is None:
                    self.logger().warning("Gateway: failed to obtain order price."
                                          "Failed to calculate effective hedging price.")
                    return s_decimal_nan
            else:
                try:
                    taker_price = taker_market.get_vwap_for_volume(taker_trading_pair, True, size).result_price
                except ZeroDivisionError:
                    return None

            # Convert them from taker's price to maker's price
            taker_price *= self.markettaker_to_maker_base_conversion_rate(market_pair)

            return taker_price

    def get_suggested_price_samples(self, market_pair: MakerTakerMarketPair):
        """
        Get the queues of order book price samples for a market pair.

        :param market_pair: The market pair under which samples were collected for.
        :return: (bid order price samples, ask order price samples)
        """
        if market_pair in self._suggested_price_samples:
            return self._suggested_price_samples[market_pair]
        return deque(), deque()

    def get_top_bid_ask(self, market_pair: MakerTakerMarketPair):
        """
        Calculate the top bid and ask using top depth tolerance in maker order book

        :param market_pair: cross exchange market pair
        :return: (top bid: Decimal, top ask: Decimal)
        """
        trading_pair = market_pair.maker.trading_pair
        maker_market = market_pair.maker.market

        if self._config_map.top_depth_tolerance == 0:
            top_bid_price = maker_market.get_price(trading_pair, False)
            top_ask_price = maker_market.get_price(trading_pair, True)

        else:
            # Use bid entries in maker order book
            top_bid_price = maker_market.get_price_for_volume(trading_pair,
                                                              False,
                                                              self._config_map.top_depth_tolerance).result_price

            # Use ask entries in maker order book
            top_ask_price = maker_market.get_price_for_volume(trading_pair,
                                                              True,
                                                              self._config_map.top_depth_tolerance).result_price

        return top_bid_price, top_ask_price

    def take_suggested_price_sample(self, timestamp: float, market_pair: MakerTakerMarketPair):
        """
        Record the bid and ask sample queues.

        These samples are later taken to check if price has drifted for new limit orders, s.t. new limit orders can
        properly take into account transient orders that appear and disappear frequently on the maker market.

        :param market_pair: cross exchange market pair
        """
        if ((self._last_timestamp // self.ORDER_ADJUST_SAMPLE_INTERVAL) <
                (timestamp // self.ORDER_ADJUST_SAMPLE_INTERVAL)):
            if market_pair not in self._suggested_price_samples:
                self._suggested_price_samples[market_pair] = (deque(), deque())

            top_bid_price, top_ask_price = self.get_top_bid_ask_from_price_samples(market_pair)

            bid_price_samples_deque, ask_price_samples_deque = self._suggested_price_samples[market_pair]
            bid_price_samples_deque.append(top_bid_price)
            ask_price_samples_deque.append(top_ask_price)
            while len(bid_price_samples_deque) > self.ORDER_ADJUST_SAMPLE_WINDOW:
                bid_price_samples_deque.popleft()
            while len(ask_price_samples_deque) > self.ORDER_ADJUST_SAMPLE_WINDOW:
                ask_price_samples_deque.popleft()

    def get_top_bid_ask_from_price_samples(self, market_pair: MakerTakerMarketPair):
        """
        Calculate the top bid and ask using earlier samples

        :param market_pair: cross exchange market pair
        :return: (top bid, top ask)
        """
        # Incorporate the past bid & ask price samples.
        current_top_bid_price, current_top_ask_price = self.get_top_bid_ask(market_pair)

        bid_price_samples, ask_price_samples = self.get_suggested_price_samples(market_pair)

        if not any(Decimal.is_nan(p) for p in bid_price_samples) and not Decimal.is_nan(current_top_bid_price):
            top_bid_price = max(list(bid_price_samples) + [current_top_bid_price])
        else:
            top_bid_price = current_top_bid_price

        if not any(Decimal.is_nan(p) for p in ask_price_samples) and not Decimal.is_nan(current_top_ask_price):
            top_ask_price = min(list(ask_price_samples) + [current_top_ask_price])
        else:
            top_ask_price = current_top_ask_price

        return top_bid_price, top_ask_price

    async def check_if_still_profitable(self,
                                        market_pair,
                                        active_order: LimitOrder,
                                        current_hedging_price: Decimal):
        """
        Check whether a currently active limit order should be canceled or not, according to profitability metric.

        If active order canceling is enabled (e.g. for centralized exchanges), then the min profitability config is
        used as the threshold. If it is disabled (e.g. for decentralized exchanges), then the cancel order threshold
        is used instead.

        :param market_pair: cross exchange market pair
        :param active_order: the currently active order to check for cancelation
        :param current_hedging_price: the current average hedging price on taker market for the limit order
        :return: True if the limit order stays, False if the limit order is being canceled.
        """
        is_buy = active_order.is_buy
        limit_order_type_str = "bid" if is_buy else "ask"
        order_price = active_order.price

        cancel_order_threshold = self._config_map.order_refresh_mode.get_cancel_order_threshold()
        if cancel_order_threshold.is_nan():
            cancel_order_threshold = self.min_profitability

        if current_hedging_price is None:
            if LogOption.REMOVING_ORDER in self.logging_options:
                self.log_with_clock(
                    logging.INFO,
                    f"({market_pair.maker.trading_pair}) Limit {limit_order_type_str} order at "
                    f"{order_price:.8g} {market_pair.maker.quote_asset} is no longer profitable. "
                    f"Removing the order."
                )
            self.cancel_maker_order(market_pair, active_order.client_order_id)
            return False

        transaction_fee = 0
        pl = 0
        if self.is_gateway_market(market_pair.taker):
            if hasattr(market_pair.taker.market, "network_transaction_fee"):
                _, _, quote_rate, _, _, base_rate, _, _, gas_rate = self.get_conversion_rates(market_pair)
                transaction_fee: TokenAmount = getattr(market_pair.taker.market, "network_transaction_fee")
                transaction_fee = transaction_fee.amount
                # Transaction fee in maker quote asset
                transaction_fee *= gas_rate

                # The remaining quantity of the maker order to potentially hedge against
                quantity_remaining = active_order.quantity
                if not active_order.filled_quantity.is_nan():
                    quantity_remaining = active_order.quantity - active_order.filled_quantity

                if active_order.is_buy:
                    # Maker buy
                    # Taker sell
                    hedged_order_quantity = min(
                        quantity_remaining * base_rate,
                        market_pair.taker.market.get_available_balance(market_pair.taker.base_asset) *
                        self.order_size_taker_balance_factor
                    )
                    # Convert from taker to maker order amount
                    hedged_order_quantity = hedged_order_quantity / base_rate
                    # Calculate P/L including potential gas fees (if gateway)
                    pl = hedged_order_quantity * current_hedging_price - \
                        quantity_remaining * active_order.price - \
                        transaction_fee
                else:
                    # Maker sell
                    # Taker buy
                    taker_price = await market_pair.taker.market.get_order_price(
                        market_pair.taker.trading_pair,
                        True,
                        quantity_remaining * base_rate
                    )
                    hedged_order_quantity = min(
                        quantity_remaining * base_rate,
                        market_pair.taker.market.get_available_balance(market_pair.taker.quote_asset) /
                        taker_price * self.order_size_taker_balance_factor
                    )
                    # Convert from taker to maker order amount
                    hedged_order_quantity = hedged_order_quantity / base_rate
                    # Calculate P/L including potential gas fees (if gateway)
                    pl = quantity_remaining * active_order.price - \
                        hedged_order_quantity * current_hedging_price - \
                        transaction_fee

        # Profitability based on a price multiplier (cancel_order_threshold)
        # Profitability based on absolute P/L including fees
        if ((is_buy and current_hedging_price < order_price * (1 + cancel_order_threshold)) or
                (not is_buy and order_price < current_hedging_price * (1 + cancel_order_threshold)) or
                pl < 0):

            if LogOption.REMOVING_ORDER in self.logging_options:
                self.log_with_clock(
                    logging.INFO,
                    f"({market_pair.maker.trading_pair}) Limit {limit_order_type_str} order at "
                    f"{order_price:.8g} {market_pair.maker.quote_asset} is no longer profitable. "
                    f"Removing the order."
                )
            self.cancel_maker_order(market_pair, active_order.client_order_id)
            return False
        return True

    async def check_if_sufficient_balance(self, market_pair: MakerTakerMarketPair, active_order: LimitOrder) -> bool:
        """
        Check whether there's enough asset balance for a currently active limit order. If there's not enough asset
        balance for the order (e.g. because the required asset has been moved), cancel the active order.

        This function is only used when active order canceled is enabled.

        :param market_pair: cross exchange market pair
        :param active_order: current maker limit order
        :return: True if there's sufficient balance for the limit order, False if there isn't and the order is being
                 canceled.
        """
        is_buy = active_order.is_buy
        order_price = active_order.price
        # Maker order size
        size = self.get_adjusted_limit_order_size(market_pair)
        maker_market = market_pair.maker.market
        taker_trading_pair = market_pair.taker.trading_pair

        # Convert maker order size (in maker base asset) to taker order size (in taker base asset)
        _, _, quote_rate, _, _, base_rate, _, _, gas_rate = self.get_conversion_rates(market_pair)
        size /= base_rate

        taker_market = market_pair.taker.market
        quote_pair, quote_rate_source, quote_rate, base_pair, base_rate_source, base_rate, gas_pair, gas_rate_source, gas_rate = \
            self.get_conversion_rates(market_pair)

        if is_buy:
            # Maker buy
            # Taker sell
            taker_slippage_adjustment_factor = Decimal("1") - self.slippage_buffer

            quote_asset_amount = maker_market.get_balance(market_pair.maker.quote_asset)
            base_asset_amount = taker_market.get_balance(market_pair.taker.base_asset) * base_rate

            order_size_limit = min(base_asset_amount, quote_asset_amount / order_price)
        else:
            # Maker sell
            # Taker buy
            taker_slippage_adjustment_factor = Decimal("1") + self.slippage_buffer

            base_asset_amount = maker_market.get_balance(market_pair.maker.base_asset)
            quote_asset_amount = taker_market.get_balance(market_pair.taker.quote_asset)

            if self.is_gateway_market(market_pair.taker):
                taker_price = await taker_market.get_order_price(taker_trading_pair,
                                                                 True,
                                                                 size)
                if taker_price is None:
                    self.logger().warning("Gateway: failed to obtain order price."
                                          "Failed to determine sufficient balance.")
                    return False
            else:
                taker_price = taker_market.get_price_for_quote_volume(
                    taker_trading_pair, True, quote_asset_amount
                ).result_price

            adjusted_taker_price = (taker_price / base_rate) * taker_slippage_adjustment_factor
            order_size_limit = min(base_asset_amount, quote_asset_amount / adjusted_taker_price)

        quantized_size_limit = maker_market.quantize_order_amount(active_order.trading_pair, order_size_limit)

        if active_order.quantity > quantized_size_limit:
            if LogOption.ADJUST_ORDER in self.logging_options:
                self.log_with_clock(
                    logging.INFO,
                    f"({market_pair.maker.trading_pair}) Order size limit ({order_size_limit:.8g}) "
                    f"is now less than the current active order amount ({active_order.quantity:.8g}). "
                    f"Going to adjust the order."
                )
            self.cancel_maker_order(market_pair, active_order.client_order_id)
            return False
        return True

    def markettaker_to_maker_base_conversion_rate(self, market_pair: MarketTradingPairTuple) -> Decimal:
        """
        Return price conversion rate for from taker quote asset to maker quote asset
        """
        _, _, quote_rate, _, _, base_rate, _, _, _ = self.get_conversion_rates(market_pair)
        return quote_rate / base_rate
        # else:
        #     market_pairs = list(self._market_pairs.values())[0]
        #     quote_pair = f"{market_pairs.taker.quote_asset}-{market_pairs.maker.quote_asset}"
        #     base_pair = f"{market_pairs.taker.base_asset}-{market_pairs.maker.base_asset}"
        #     quote_rate = RateOracle.get_instance().rate(quote_pair)
        #     base_rate = RateOracle.get_instance().rate(base_pair)
        #     return quote_rate / base_rate

    async def check_and_create_new_orders(self,
                                          market_pair: MarketTradingPairTuple,
                                          has_active_bid: bool,
                                          has_active_ask: bool):
        """
        Check and account for all applicable conditions for creating new limit orders (e.g. profitability, what's the
        right price given depth tolerance and transient orders on the market, account balances, etc.), and create new
        limit orders for market making.

        :param market_pair: cross exchange market pair
        :param has_active_bid: True if there's already an active bid on the maker side, False otherwise
        :param has_active_ask: True if there's already an active ask on the maker side, False otherwise
        """

        # if there is no active bid, place bid again
        if not has_active_bid:
            bid_size = await self.get_market_making_size(market_pair, True)

            if bid_size > s_decimal_zero:
                bid_price = await self.get_market_making_price(market_pair, True, bid_size)
                if not Decimal.is_nan(bid_price):
                    effective_hedging_price = await self.calculate_effective_hedging_price(
                        market_pair,
                        True,
                        bid_size
                    )
                    effective_hedging_price_adjusted = effective_hedging_price / \
                        self.markettaker_to_maker_base_conversion_rate(market_pair)
                    if LogOption.CREATE_ORDER in self.logging_options:
                        self.log_with_clock(
                            logging.INFO,
                            f"({market_pair.maker.trading_pair}) Creating limit bid order for "
                            f"{bid_size} {market_pair.maker.base_asset} at "
                            f"{bid_price} {market_pair.maker.quote_asset}. "
                            f"Current hedging price: {effective_hedging_price:.8f} {market_pair.maker.quote_asset} "
                            f"(Rate adjusted: {effective_hedging_price_adjusted:.8f} {market_pair.taker.quote_asset})."
                        )
                    self.place_order(market_pair, True, True, bid_size, bid_price)
                else:
                    if LogOption.NULL_ORDER_SIZE in self.logging_options:
                        self.log_with_clock(
                            logging.WARNING,
                            f"({market_pair.maker.trading_pair})"
                            f"Order book on taker is too thin to place order for size: {bid_size}"
                            f"Reduce order_size_portfolio_ratio_limit"
                        )
            else:
                if LogOption.NULL_ORDER_SIZE in self.logging_options:
                    self.log_with_clock(
                        logging.WARNING,
                        f"({market_pair.maker.trading_pair}) Attempting to place a limit bid but the "
                        f"bid size is 0. Skipping. Check available balance."
                    )
        # if there is no active ask, place ask again
        if not has_active_ask:
            ask_size = await self.get_market_making_size(market_pair, False)

            if ask_size > s_decimal_zero:
                ask_price = await self.get_market_making_price(market_pair, False, ask_size)
                if not Decimal.is_nan(ask_price):
                    effective_hedging_price = await self.calculate_effective_hedging_price(
                        market_pair,
                        False,
                        ask_size
                    )
                    effective_hedging_price_adjusted = effective_hedging_price / \
                        self.markettaker_to_maker_base_conversion_rate(market_pair)
                    if LogOption.CREATE_ORDER in self.logging_options:
                        self.log_with_clock(
                            logging.INFO,
                            f"({market_pair.maker.trading_pair}) Creating limit ask order for "
                            f"{ask_size} {market_pair.maker.base_asset} at "
                            f"{ask_price} {market_pair.maker.quote_asset}. "
                            f"Current hedging price: {effective_hedging_price:.8f} {market_pair.maker.quote_asset} "
                            f"(Rate adjusted: {effective_hedging_price_adjusted:.8f} {market_pair.taker.quote_asset})."
                        )
                    self.place_order(market_pair, False, True, ask_size, ask_price)
                else:
                    if LogOption.NULL_ORDER_SIZE in self.logging_options:
                        self.log_with_clock(
                            logging.WARNING,
                            f"({market_pair.maker.trading_pair})"
                            f"Order book on taker is too thin to place order for size: {ask_size}"
                            f"Reduce order_size_portfolio_ratio_limit"
                        )
            else:
                if LogOption.NULL_ORDER_SIZE in self.logging_options:
                    self.log_with_clock(
                        logging.WARNING,
                        f"({market_pair.maker.trading_pair}) Attempting to place a limit ask but the "
                        f"ask size is 0. Skipping. Check available balance."
                    )

    def place_order(
        self,
        market_pair: MakerTakerMarketPair,
        is_buy: bool,
        is_maker: bool,  # True for maker order, False for taker order
        amount: Decimal,
        price: Decimal,
        maker_order_id: str = None,
        fill_records: List[OrderFilledEvent] = None,
    ):
        expiration_seconds = s_float_nan
        market_info = market_pair.maker if is_maker else market_pair.taker
        # Market orders are not being submitted as taker orders, limit orders are preferred at all times
        order_type = market_info.market.get_maker_order_type() if is_maker else \
            OrderType.LIMIT
        if order_type is OrderType.MARKET:
            price = s_decimal_nan
        expiration_seconds = self._config_map.order_refresh_mode.get_expiration_seconds()
        order_id = None
        if is_buy:
            try:
                order_id = self.buy_with_specific_market(market_info, amount,
                                                         order_type=order_type, price=price,
                                                         expiration_seconds=expiration_seconds)
            except ValueError as e:
                self.logger().warning(f"Placing an order on market {str(market_info.market.name)} "
                                      f"failed with the following error: {str(e)}")
        else:
            try:
                order_id = self.sell_with_specific_market(market_info, amount,
                                                          order_type=order_type, price=price,
                                                          expiration_seconds=expiration_seconds)
            except ValueError as e:
                self.logger().warning(f"Placing an order on market {str(market_info.market.name)} "
                                      f"failed with the following error: {str(e)}")
        if order_id is None:
            return
        self._sb_order_tracker.add_create_order_pending(order_id)
        self._market_pair_tracker.start_tracking_order_id(order_id, market_info.market, market_pair)
        if is_maker:
            self._maker_to_taker_order_ids[order_id] = []
        else:
            self._taker_to_maker_order_ids[order_id] = maker_order_id
            self._maker_to_taker_order_ids[maker_order_id] += [order_id]
            self.set_ongoing_hedging(fill_records, order_id)
        return order_id

    def cancel_maker_order(self, market_pair: MakerTakerMarketPair, order_id: str):
        market_trading_pair_tuple = self._market_pair_tracker.get_market_pair_from_order_id(order_id)
        super().cancel_order(market_trading_pair_tuple.maker, order_id)
    # ----------------------------------------------------------------------------------------------------------
    # </editor-fold>

    # <editor-fold desc="+ Order tracking entry points">
    # Override the stop tracking entry points to include the market pair tracker as well.
    # ----------------------------------------------------------------------------------------------------------
    def stop_tracking_limit_order(self, market_trading_pair_tuple, order_id: str):
        self._market_pair_tracker.stop_tracking_order_id(order_id)
        self.stop_tracking_limit_order(self, market_trading_pair_tuple, order_id)

    def stop_tracking_market_order(self, market_trading_pair_tuple, order_id: str):
        self._market_pair_tracker.stop_tracking_order_id(order_id)
        self.stop_tracking_market_order(self, market_trading_pair_tuple, order_id)
    # ----------------------------------------------------------------------------------------------------------
    # </editor-fold>

    # Removes orders from pending_create
    def did_create_buy_order(self, order_created_event):
        order_id = order_created_event.order_id
        self._sb_order_tracker.remove_create_order_pending(order_id)

    def did_create_sell_order(self, order_created_event):
        order_id = order_created_event.order_id
        self._sb_order_tracker.remove_create_order_pending(order_id)

    def notify_hb_app(self, msg: str):
        if self._hb_app_notification:
            super().notify_hb_app(msg)

    # ----------------------------------------------------------------------------------------------------------
    # Helpers
    def check_multiple_buy_orders(self, fill_records: List[OrderFilledEvent]):
        maker_order_ids = [r.order_id for _, r in fill_records]
        if len(set(maker_order_ids)) != 1:
            self.logger().warning("Multiple buy maker orders")

    def check_multiple_sell_orders(self, fill_records: List[OrderFilledEvent]):
        maker_order_ids = [r.order_id for _, r in fill_records]
        if len(set(maker_order_ids)) != 1:
            self.logger().warning("Multiple sell maker orders")

    def get_unhedged_buy_records(self, market_pair: MakerTakerMarketPair) -> List[OrderFilledEvent]:
        buy_fill_records = self._order_fill_buy_events.get(market_pair, [])
        return self.get_unhedged_events(buy_fill_records)

    def get_unhedged_sell_records(self, market_pair: MakerTakerMarketPair) -> List[OrderFilledEvent]:
        sell_fill_records = self._order_fill_sell_events.get(market_pair, [])
        return self.get_unhedged_events(sell_fill_records)

    def get_unhedged_events(self, fill_records: List[OrderFilledEvent]) -> List[OrderFilledEvent]:
        return [
            fill_event for fill_event in fill_records if (
                not self.is_fill_event_in_ongoing_hedging(fill_event)
            )
        ]

    def is_fill_event_in_ongoing_hedging(self, fill_event: OrderFilledEvent) -> bool:
        trade_id = fill_event[1].exchange_trade_id
        for maker_exchange_trade_ids in self._ongoing_hedging:
            for id in maker_exchange_trade_ids:
                if trade_id is id:
                    return True
        return False

    def set_ongoing_hedging(self, fill_records: List[OrderFilledEvent], order_id: str):
        maker_exchange_trade_ids = tuple(r.exchange_trade_id for _, r in fill_records)
        self._ongoing_hedging[maker_exchange_trade_ids] = order_id

    def del_order_from_ongoing_hedging(self, taker_order_id: str):
        maker_exchange_trade_ids = self._ongoing_hedging.inverse[taker_order_id]
        del self._ongoing_hedging[maker_exchange_trade_ids]
