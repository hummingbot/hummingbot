# -*- coding: utf-8 -*-

import asyncio
import logging
import json

from typing import Any, Dict, List, AsyncIterable, Optional, Tuple
from datetime import datetime, timedelta
from async_timeout import timeout
from decimal import Decimal
from libc.stdint cimport int64_t

import aiohttp
import pandas as pd

from aiohttp.client_exceptions import ContentTypeError

from hummingbot.logger import HummingbotLogger
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.clock cimport Clock
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce
from hummingbot.core.utils.estimate_fee import estimate_fee
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.connector.exchange_base cimport ExchangeBase
from hummingbot.connector.trading_rule cimport TradingRule
from hummingbot.core.event.events import MarketEvent, BuyOrderCompletedEvent, SellOrderCompletedEvent, \
    OrderFilledEvent, OrderCancelledEvent, BuyOrderCreatedEvent, OrderExpiredEvent, SellOrderCreatedEvent, \
    MarketTransactionFailureEvent, MarketOrderFailureEvent, OrderType, TradeType, TradeFee

from hummingbot.connector.exchange.beaxy.beaxy_api_order_book_data_source import BeaxyAPIOrderBookDataSource
from hummingbot.connector.exchange.beaxy.beaxy_constants import BeaxyConstants
from hummingbot.connector.exchange.beaxy.beaxy_auth import BeaxyAuth
from hummingbot.connector.exchange.beaxy.beaxy_order_book_tracker import BeaxyOrderBookTracker
from hummingbot.connector.exchange.beaxy.beaxy_in_flight_order import BeaxyInFlightOrder
from hummingbot.connector.exchange.beaxy.beaxy_user_stream_tracker import BeaxyUserStreamTracker
from hummingbot.connector.exchange.beaxy.beaxy_misc import split_trading_pair, trading_pair_to_symbol, BeaxyIOError

s_logger = None
s_decimal_0 = Decimal('0.0')
s_decimal_NaN = Decimal('NaN')

cdef class BeaxyExchangeTransactionTracker(TransactionTracker):
    cdef:
        BeaxyExchange _owner

    def __init__(self, owner: BeaxyExchange):
        super().__init__()
        self._owner = owner

    cdef c_did_timeout_tx(self, str tx_id):
        TransactionTracker.c_did_timeout_tx(self, tx_id)
        self._owner.c_did_timeout_tx(tx_id)

cdef class BeaxyExchange(ExchangeBase):
    MARKET_BUY_ORDER_COMPLETED_EVENT_TAG = MarketEvent.BuyOrderCompleted.value
    MARKET_SELL_ORDER_COMPLETED_EVENT_TAG = MarketEvent.SellOrderCompleted.value
    MARKET_ORDER_CANCELLED_EVENT_TAG = MarketEvent.OrderCancelled.value
    MARKET_ORDER_FAILURE_EVENT_TAG = MarketEvent.OrderFailure.value
    MARKET_ORDER_EXPIRED_EVENT_TAG = MarketEvent.OrderExpired.value
    MARKET_ORDER_FILLED_EVENT_TAG = MarketEvent.OrderFilled.value
    MARKET_BUY_ORDER_CREATED_EVENT_TAG = MarketEvent.BuyOrderCreated.value
    MARKET_SELL_ORDER_CREATED_EVENT_TAG = MarketEvent.SellOrderCreated.value

    API_CALL_TIMEOUT = 60.0
    UPDATE_ORDERS_INTERVAL = 15.0
    UPDATE_FEE_PERCENTAGE_INTERVAL = 60.0
    ORDER_NOT_EXIST_CONFIRMATION_COUNT = 3

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(__name__)
        return s_logger

    def __init__(
        self,
        beaxy_api_key: str,
        beaxy_secret_key: str,
        poll_interval: float = 5.0,  # interval which the class periodically pulls status from the rest API
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True
    ):
        super().__init__()
        self._trading_required = trading_required
        self._beaxy_auth = BeaxyAuth(beaxy_api_key, beaxy_secret_key)
        self._order_book_tracker = BeaxyOrderBookTracker(trading_pairs=trading_pairs)
        self._order_not_found_records = {}
        self._user_stream_tracker = BeaxyUserStreamTracker(beaxy_auth=self._beaxy_auth)
        self._ev_loop = asyncio.get_event_loop()
        self._poll_notifier = asyncio.Event()
        self._last_timestamp = 0
        self._last_order_update_timestamp = 0
        self._last_fee_percentage_update_timestamp = 0
        self._poll_interval = poll_interval
        self._in_flight_orders: Dict[str, BeaxyInFlightOrder] = {}
        self._tx_tracker = BeaxyExchangeTransactionTracker(self)
        self._trading_rules = {}
        self._auth_polling_task = None
        self._status_polling_task = None
        self._user_stream_tracker_task = None
        self._user_stream_event_listener_task = None
        self._trading_rules_polling_task = None
        self._shared_client = None
        self._maker_fee_percentage = {}
        self._taker_fee_percentage = {}

    @staticmethod
    def split_trading_pair(trading_pair: str) -> Optional[Tuple[str, str]]:
        return split_trading_pair(trading_pair)

    @staticmethod
    def convert_from_exchange_trading_pair(exchange_trading_pair: str) -> Optional[str]:
        if BeaxyExchange.split_trading_pair(exchange_trading_pair) is None:
            return None
        base_asset, quote_asset = BeaxyExchange.split_trading_pair(exchange_trading_pair)
        return f'{base_asset}-{quote_asset}'

    @staticmethod
    def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
        return hb_trading_pair

    @property
    def name(self) -> str:
        """
        *required
        :return: A lowercase name / id for the market. Must stay consistent with market name in global settings.
        """
        return 'beaxy'

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        """
        *required
        Get mapping of all the order books that are being tracked.
        :return: Dict[trading_pair : OrderBook]
        """
        return self._order_book_tracker.order_books

    @property
    def beaxy_auth(self) -> BeaxyAuth:
        """
        :return: BeaxyAuth class
        """
        return self._beaxy_auth

    @property
    def trading_rules(self) -> Dict[str, Any]:
        return self._trading_rules

    @property
    def status_dict(self) -> Dict[str, bool]:
        """
        *required
        :return: a dictionary of relevant status checks.
        This is used by `ready` method below to determine if a market is ready for trading.
        """
        return {
            'order_books_initialized': self._order_book_tracker.ready,
            'account_balance': len(self._account_balances) > 0 if self._trading_required else True,
            'trading_rule_initialized': len(self._trading_rules) > 0 if self._trading_required else True
        }

    @property
    def ready(self) -> bool:
        """
        *required
        :return: a boolean value that indicates if the market is ready for trading
        """
        return all(self.status_dict.values())

    @property
    def limit_orders(self) -> List[LimitOrder]:
        """
        *required
        :return: list of active limit orders
        """
        return [
            in_flight_order.to_limit_order()
            for in_flight_order in self._in_flight_orders.values()
        ]

    @property
    def in_flight_orders(self) -> Dict[str, BeaxyInFlightOrder]:
        return self._in_flight_orders

    @property
    def tracking_states(self) -> Dict[str, any]:
        """
        *required
        :return: Dict[client_order_id: InFlightOrder]
        This is used by the MarketsRecorder class to orchestrate market classes at a higher level.
        """
        return {
            key: value.to_json()
            for key, value in self._in_flight_orders.items()
        }

    def restore_tracking_states(self, saved_states: Dict[str, any]):
        """
        *required
        Updates inflight order statuses from API results
        This is used by the MarketsRecorder class to orchestrate market classes at a higher level.
        """
        self._in_flight_orders.update({
            key: BeaxyInFlightOrder.from_json(value)
            for key, value in saved_states.items()
        })

    async def get_active_exchange_markets(self) -> pd.DataFrame:
        """
        *required
        Used by the discovery strategy to read order books of all actively trading markets,
        and find opportunities to profit
        """
        return await BeaxyAPIOrderBookDataSource.get_active_exchange_markets()

    cdef c_start(self, Clock clock, double timestamp):
        """
        *required
        c_start function used by top level Clock to orchestrate components of the bot
        """
        self._tx_tracker.c_start(clock, timestamp)
        ExchangeBase.c_start(self, clock, timestamp)

    async def start_network(self):
        """
        *required
        Async function used by NetworkBase class to handle when a single market goes online
        """
        self.logger().debug(f'Starting beaxy network. Trading required is {self._trading_required}')
        self._stop_network()
        self._order_book_tracker.start()
        self.logger().debug('OrderBookTracker started, starting polling tasks.')
        if self._trading_required:
            self._auth_polling_task = safe_ensure_future(self._beaxy_auth._auth_token_polling_loop())
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())
            self._trading_rules_polling_task = safe_ensure_future(self._trading_rules_polling_loop())
            self._user_stream_tracker_task = safe_ensure_future(self._user_stream_tracker.start())
            self._user_stream_event_listener_task = safe_ensure_future(self._user_stream_event_listener())

    async def check_network(self) -> NetworkStatus:
        try:
            res = await self._api_request(http_method='GET', path_url=BeaxyConstants.TradingApi.HEALTH_ENDPOINT, is_auth_required=False)
            if res['trading_server'] != 200 and res['historical_data_server'] != 200:
                return NetworkStatus.STOPPED
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().network('Error fetching Beaxy network status.', exc_info=True)
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    cdef c_tick(self, double timestamp):
        """
        *required
        Used by top level Clock to orchestrate components of the bot.
        This function is called frequently with every clock tick
        """
        cdef:
            int64_t last_tick = <int64_t>(self._last_timestamp / self._poll_interval)
            int64_t current_tick = <int64_t>(timestamp / self._poll_interval)

        ExchangeBase.c_tick(self, timestamp)
        if current_tick > last_tick:
            if not self._poll_notifier.is_set():
                self._poll_notifier.set()
        self._last_timestamp = timestamp

    def _stop_network(self):
        """
        Synchronous function that handles when a single market goes offline
        """
        self._order_book_tracker.stop()
        if self._status_polling_task is not None:
            self._status_polling_task.cancel()
        if self._user_stream_tracker_task is not None:
            self._user_stream_tracker_task.cancel()
        if self._user_stream_event_listener_task is not None:
            self._user_stream_event_listener_task.cancel()
        if self._trading_rules_polling_task is not None:
            self._trading_rules_polling_task.cancel()
        self._status_polling_task = self._user_stream_tracker_task = \
            self._user_stream_event_listener_task = None

    async def list_orders(self) -> List[Any]:
        """
        Gets a list of the user's active orders via rest API
        :returns: json response
        """

        if self._in_flight_orders:
            from_date = min(order.created_at for order in self._in_flight_orders.values())
        else:
            from_date = datetime.utcnow() - timedelta(minutes=5)

        result = await safe_gather(
            self._api_request('get', path_url=BeaxyConstants.TradingApi.OPEN_ORDERS_ENDPOINT),
            self._api_request('get', path_url=BeaxyConstants.TradingApi.CLOSED_ORDERS_ENDPOINT.format(
                from_date=from_date.strftime('%Y-%m-%dT%H:%M:%SZ')
            )),
        )
        return result

    async def _update_order_status(self):
        """
        Pulls the rest API for for latest order statuses and update local order statuses.
        """
        cdef:
            double current_timestamp = self._current_timestamp

        if current_timestamp - self._last_order_update_timestamp <= self.UPDATE_ORDERS_INTERVAL:
            return

        tracked_orders = list(self._in_flight_orders.values())
        open_orders, closed_orders = await self.list_orders()
        open_order_dict = {entry['order_id']: entry for entry in open_orders}
        close_order_dict = {entry['order_id']: entry for entry in closed_orders}

        for tracked_order in tracked_orders:
            client_order_id = tracked_order.client_order_id

            # Do nothing, if the order has already been cancelled or has failed
            if client_order_id not in self._in_flight_orders:
                continue

            # get last exchange_order_id with no blocking
            exchange_order_id = self._in_flight_orders[client_order_id].exchange_order_id

            if exchange_order_id is None:
                continue

            open_order = open_order_dict.get(exchange_order_id)
            closed_order = close_order_dict.get(exchange_order_id)

            order_update = closed_order or open_order

            if not open_order and not closed_order:

                self._order_not_found_records[client_order_id] = self._order_not_found_records.get(client_order_id, 0) + 1

                if self._order_not_found_records[client_order_id] < self.ORDER_NOT_EXIST_CONFIRMATION_COUNT:
                    # Wait until the order not found error have repeated for a few times before actually treating
                    continue

                self.logger().info(
                    f'The tracked order {client_order_id} does not exist on Beaxy for last day. '
                    f'(retried {self._order_not_found_records[client_order_id]}) Removing from tracking.'
                )
                tracked_order.last_state = 'CLOSED'
                self.c_trigger_event(
                    self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                    OrderCancelledEvent(self._current_timestamp, client_order_id)
                )
                self.c_stop_tracking_order(client_order_id)
                del self._order_not_found_records[client_order_id]
                continue

            # Update the tracked order
            tracked_order.last_state = order_update['order_status']

            if order_update['filled_size']:
                execute_price = Decimal(str(order_update['limit_price'] if order_update['limit_price'] else order_update['average_price']))
                execute_amount_diff = Decimal(str(order_update['filled_size'])) - tracked_order.executed_amount_base

                # Emit event if executed amount is greater than 0.
                if execute_amount_diff > s_decimal_0:

                    tracked_order.executed_amount_base = execute_amount_diff
                    tracked_order.executed_amount_quote += execute_amount_diff * execute_price

                    order_type_description = tracked_order.order_type_description
                    order_filled_event = OrderFilledEvent(
                        self._current_timestamp,
                        tracked_order.client_order_id,
                        tracked_order.trading_pair,
                        tracked_order.trade_type,
                        tracked_order.order_type,
                        execute_price,
                        execute_amount_diff,
                        self.c_get_fee(
                            tracked_order.base_asset,
                            tracked_order.quote_asset,
                            tracked_order.order_type,
                            tracked_order.trade_type,
                            execute_price,
                            execute_amount_diff,
                        ),
                        exchange_trade_id=exchange_order_id,
                    )
                    self.logger().info(f'Filled {execute_amount_diff} out of {tracked_order.amount} of the '
                                       f'{order_type_description} order {client_order_id}.')
                    self.c_trigger_event(self.MARKET_ORDER_FILLED_EVENT_TAG, order_filled_event)

            if tracked_order.is_done:
                if not tracked_order.is_failure and not tracked_order.is_cancelled:

                    new_confirmed_amount = Decimal(str(order_update['size']))
                    execute_amount_diff = new_confirmed_amount - tracked_order.executed_amount_base
                    execute_price = Decimal(str(order_update['limit_price'] if order_update['limit_price'] else order_update['average_price']))

                    # Emit event if executed amount is greater than 0.
                    if execute_amount_diff > s_decimal_0:

                        tracked_order.executed_amount_base = execute_amount_diff
                        tracked_order.executed_amount_quote += execute_amount_diff * execute_price

                        order_type_description = tracked_order.order_type_description
                        order_filled_event = OrderFilledEvent(
                            self._current_timestamp,
                            tracked_order.client_order_id,
                            tracked_order.trading_pair,
                            tracked_order.trade_type,
                            tracked_order.order_type,
                            execute_price,
                            execute_amount_diff,
                            self.c_get_fee(
                                tracked_order.base_asset,
                                tracked_order.quote_asset,
                                tracked_order.order_type,
                                tracked_order.trade_type,
                                execute_price,
                                execute_amount_diff,
                            ),
                            exchange_trade_id=exchange_order_id,
                        )
                        self.logger().info(f'Filled {execute_amount_diff} out of {tracked_order.amount} of the '
                                           f'{order_type_description} order {client_order_id}.')
                        self.c_trigger_event(self.MARKET_ORDER_FILLED_EVENT_TAG, order_filled_event)

                    if tracked_order.trade_type == TradeType.BUY:
                        self.logger().info(f'The market buy order {tracked_order.client_order_id} has completed '
                                           f'according to order status API.')
                        self.c_trigger_event(self.MARKET_BUY_ORDER_COMPLETED_EVENT_TAG,
                                             BuyOrderCompletedEvent(self._current_timestamp,
                                                                    tracked_order.client_order_id,
                                                                    tracked_order.base_asset,
                                                                    tracked_order.quote_asset,
                                                                    (tracked_order.fee_asset
                                                                     or tracked_order.base_asset),
                                                                    tracked_order.executed_amount_base,
                                                                    tracked_order.executed_amount_quote,
                                                                    tracked_order.fee_paid,
                                                                    tracked_order.order_type))
                    else:
                        self.logger().info(f'The market sell order {tracked_order.client_order_id} has completed '
                                           f'according to order status API.')
                        self.c_trigger_event(self.MARKET_SELL_ORDER_COMPLETED_EVENT_TAG,
                                             SellOrderCompletedEvent(self._current_timestamp,
                                                                     tracked_order.client_order_id,
                                                                     tracked_order.base_asset,
                                                                     tracked_order.quote_asset,
                                                                     (tracked_order.fee_asset
                                                                      or tracked_order.quote_asset),
                                                                     tracked_order.executed_amount_base,
                                                                     tracked_order.executed_amount_quote,
                                                                     tracked_order.fee_paid,
                                                                     tracked_order.order_type))
                else:
                    self.logger().info(f'The market order {tracked_order.client_order_id} has failed/been cancelled '
                                       f'according to order status API.')
                    tracked_order.last_state = 'cancelled'
                    self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                         OrderCancelledEvent(
                                             self._current_timestamp,
                                             tracked_order.client_order_id
                                         ))
                self.c_stop_tracking_order(tracked_order.client_order_id)
        self._last_order_update_timestamp = current_timestamp

    async def place_order(self, order_id: str, trading_pair: str, amount: Decimal, is_buy: bool, order_type: OrderType,
                          price: Decimal):
        """
        Async wrapper for placing orders through the rest API.
        :returns: json response from the API
        """
        path_url = BeaxyConstants.TradingApi.CREATE_ORDER_ENDPOINT
        trading_pair = trading_pair_to_symbol(trading_pair)  # at Beaxy all pairs listed without splitter
        is_limit_type = order_type.is_limit_type()

        data = {
            'comment': order_id,
            'symbol': trading_pair,
            'order_type': 'limit' if is_limit_type else 'market',
            'side': 'buy' if is_buy else 'sell',
            'size': f'{amount:f}',
            'destination': 'MAXI',
        }
        if is_limit_type:
            data['price'] = f'{price:f}'
        order_result = await self._api_request('POST', path_url=path_url, data=data)
        self.logger().debug(f'Set order result {order_result}')
        return order_result

    cdef object c_get_fee(
        self,
        str base_currency,
        str quote_currency,
        object order_type,
        object order_side,
        object amount,
        object price
    ):
        """
        *required
        function to calculate fees for a particular order
        :returns: TradeFee class that includes fee percentage and flat fees
        """

        cdef:
            object maker_fee = self._maker_fee_percentage
            object taker_fee = self._taker_fee_percentage

        is_maker = order_type is OrderType.LIMIT_MAKER
        pair = f'{base_currency}-{quote_currency}'
        fees = maker_fee if is_maker else taker_fee

        if pair not in fees:
            self.logger().info(f'Fee for {pair} is not in fee cache')
            return estimate_fee('beaxy', is_maker)

        return TradeFee(percent=fees[pair] / Decimal(100))

    async def execute_buy(
        self,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        order_type: OrderType,
        price: Optional[Decimal] = s_decimal_0
    ):
        """
        Function that takes strategy inputs, auto corrects itself with trading rule,
        and submit an API request to place a buy order
        """
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]

        decimal_amount = self.quantize_order_amount(trading_pair, amount)
        decimal_price = self.quantize_order_price(trading_pair, price)
        if decimal_amount < trading_rule.min_order_size:
            raise ValueError(f'Buy order amount {decimal_amount} is lower than the minimum order size '
                             f'{trading_rule.min_order_size}.')

        try:
            self.c_start_tracking_order(order_id, trading_pair, order_type, TradeType.BUY, decimal_price, decimal_amount)
            order_result = await self.place_order(order_id, trading_pair, decimal_amount, True, order_type, decimal_price)
            exchange_order_id = order_result['order_id']
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(f'Created {order_type} buy order {order_id} for {decimal_amount} {trading_pair}.')
                tracked_order.update_exchange_order_id(exchange_order_id)

            self.c_trigger_event(self.MARKET_BUY_ORDER_CREATED_EVENT_TAG,
                                 BuyOrderCreatedEvent(self._current_timestamp,
                                                      order_type,
                                                      trading_pair,
                                                      decimal_amount,
                                                      decimal_price,
                                                      order_id))
        except asyncio.CancelledError:
            raise
        except Exception:
            tracked_order = self._in_flight_orders.get(order_id)
            tracked_order.last_state = 'FAILURE'
            self.c_stop_tracking_order(order_id)
            order_type_str = order_type.name.lower()
            self.logger().network(
                f'Error submitting buy {order_type_str} order to Beaxy for '
                f'{decimal_amount} {trading_pair} '
                f'{decimal_price}.',
                exc_info=True,
                app_warning_msg='Failed to submit buy order to Beaxy. Check API key and network connection.'
            )
            self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                 MarketOrderFailureEvent(
                                     self._current_timestamp,
                                     order_id,
                                     order_type
                                 ))

    cdef str c_buy(self, str trading_pair, object amount, object order_type=OrderType.MARKET, object price=s_decimal_0,
                   dict kwargs={}):
        """
        *required
        Synchronous wrapper that generates a client-side order ID and schedules the buy order.
        """
        cdef:
            int64_t tracking_nonce = <int64_t> get_tracking_nonce()
            str order_id = str(f'HBOT-buy-{trading_pair}-{tracking_nonce}')

        safe_ensure_future(self.execute_buy(order_id, trading_pair, amount, order_type, price))
        return order_id

    async def execute_sell(
        self,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        order_type: OrderType,
        price: Optional[Decimal] = s_decimal_0
    ):
        """
        Function that takes strategy inputs, auto corrects itself with trading rule,
        and submit an API request to place a sell order
        """
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]

        decimal_amount = self.quantize_order_amount(trading_pair, amount)
        decimal_price = self.quantize_order_price(trading_pair, price)
        if decimal_amount < trading_rule.min_order_size:
            raise ValueError(f'Sell order amount {decimal_amount} is lower than the minimum order size '
                             f'{trading_rule.min_order_size}.')

        try:
            self.c_start_tracking_order(order_id, trading_pair, order_type, TradeType.SELL, decimal_price, decimal_amount)
            order_result = await self.place_order(order_id, trading_pair, decimal_amount, False, order_type, decimal_price)

            exchange_order_id = order_result['order_id']
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(f'Created {order_type} sell order {order_id} for {decimal_amount} {trading_pair}.')
                tracked_order.update_exchange_order_id(exchange_order_id)

            self.c_trigger_event(self.MARKET_SELL_ORDER_CREATED_EVENT_TAG,
                                 SellOrderCreatedEvent(self._current_timestamp,
                                                       order_type,
                                                       trading_pair,
                                                       decimal_amount,
                                                       decimal_price,
                                                       order_id))
        except asyncio.CancelledError:
            raise
        except Exception:
            tracked_order = self._in_flight_orders.get(order_id)
            tracked_order.last_state = 'FAILURE'
            self.c_stop_tracking_order(order_id)
            order_type_str = order_type.name.lower()
            self.logger().network(
                f'Error submitting sell {order_type_str} order to Beaxy for '
                f'{decimal_amount} {trading_pair} '
                f'{decimal_price if order_type is OrderType.LIMIT else ""}.',
                exc_info=True,
                app_warning_msg='Failed to submit sell order to Beaxy. Check API key and network connection.'
            )
            self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                 MarketOrderFailureEvent(self._current_timestamp, order_id, order_type))

    cdef str c_sell(
        self,
        str trading_pair,
        object amount,
        object order_type=OrderType.MARKET,
        object price=s_decimal_0,
        dict kwargs={}
    ):
        """
        *required
        Synchronous wrapper that generates a client-side order ID and schedules the sell order.
        """
        cdef:
            int64_t tracking_nonce = <int64_t> get_tracking_nonce()
            str order_id = str(f'HBOT-sell-{trading_pair}-{tracking_nonce}')
        safe_ensure_future(self.execute_sell(order_id, trading_pair, amount, order_type, price))
        return order_id

    async def execute_cancel(self, trading_pair: str, order_id: str):
        """
        Function that makes API request to cancel an active order
        """
        try:
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is None:
                raise ValueError(f'Failed to cancel order - {order_id}. Order not found.')
            path_url = BeaxyConstants.TradingApi.DELETE_ORDER_ENDPOINT.format(id=tracked_order.exchange_order_id)
            cancel_result = await self._api_request('delete', path_url=path_url)
            return order_id
        except asyncio.CancelledError:
            raise
        except BeaxyIOError as e:
            if e.result and 'Active order not found or already cancelled.' in e.result['items']:
                # The order was never there to begin with. So cancelling it is a no-op but semantically successful.
                self.c_stop_tracking_order(order_id)
                self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                     OrderCancelledEvent(self._current_timestamp, order_id))
                return order_id
        except IOError as ioe:
            self.logger().warning(ioe)
        except Exception as e:
            self.logger().network(
                f'Failed to cancel order {order_id}: ',
                exc_info=True,
                app_warning_msg=f'Failed to cancel the order {order_id} on Beaxy. '
                                f'Check API key and network connection.'
            )
        return None

    cdef c_cancel(self, str trading_pair, str order_id):
        """
        *required
        Synchronous wrapper that schedules cancelling an order.
        """
        safe_ensure_future(self.execute_cancel(trading_pair, order_id))
        return order_id

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        """
        *required
        Async function that cancels all active orders.
        Used by bot's top level stop and exit commands (cancelling outstanding orders on exit)
        :returns: List of CancellationResult which indicates whether each order is successfully cancelled.
        """
        incomplete_orders = [o for o in self._in_flight_orders.values() if not o.is_done]
        tasks = [self.execute_cancel(o.trading_pair, o.client_order_id) for o in incomplete_orders]
        order_id_set = set([o.client_order_id for o in incomplete_orders])
        successful_cancellations = []

        try:
            async with timeout(timeout_seconds):
                results = await safe_gather(*tasks, return_exceptions=True)
                for client_order_id in results:
                    if client_order_id:
                        order_id_set.remove(client_order_id)
                        successful_cancellations.append(CancellationResult(client_order_id, True))
        except Exception as e:
            self.logger().network(
                'Unexpected error cancelling orders.',
                exc_info=True,
                app_warning_msg='Failed to cancel order on Beaxy exchange. Check API key and network connection.'
            )

        failed_cancellations = [CancellationResult(oid, False) for oid in order_id_set]
        return successful_cancellations + failed_cancellations

    async def _update_trade_fees(self):

        cdef:
            double current_timestamp = self._current_timestamp

        if current_timestamp - self._last_fee_percentage_update_timestamp <= self.UPDATE_FEE_PERCENTAGE_INTERVAL:
            return

        try:
            res = await self._api_request('get', BeaxyConstants.TradingApi.TRADE_SETTINGS_ENDPOINT)
            for symbol_data in res['symbols']:
                symbol = self.convert_from_exchange_trading_pair(symbol_data['name'])
                self._maker_fee_percentage[symbol] = Decimal(str(symbol_data['maker_fee']))
                self._taker_fee_percentage[symbol] = Decimal(str(symbol_data['taker_fee']))

            self._last_fee_percentage_update_timestamp = current_timestamp
        except asyncio.CancelledError:
            self.logger().warning('Got cancelled error fetching beaxy fees.')
            raise
        except Exception:
            self.logger().network('Error fetching Beaxy trade fees.', exc_info=True,
                                  app_warning_msg='Could not fetch Beaxy trading fees. '
                                  'Check network connection.')
            raise

    async def _update_balances(self):
        cdef:
            dict account_info
            list balances
            str asset_name
            set local_asset_names = set(self._account_balances.keys())
            set remote_asset_names = set()
            set asset_names_to_remove

        account_balances = await self._api_request('get', path_url=BeaxyConstants.TradingApi.WALLETS_ENDPOINT)

        for balance_entry in account_balances:
            asset_name = balance_entry['currency']
            available_balance = Decimal(str(balance_entry['available_balance']))
            total_balance = Decimal(str(balance_entry['total_balance']))
            self._account_available_balances[asset_name] = available_balance
            self._account_balances[asset_name] = total_balance
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    async def _update_trading_rules(self):
        """
        Pulls the API for trading rules (min / max order size, etc)
        """
        cdef:
            int64_t last_tick = <int64_t>(self._last_timestamp / 60.0)
            int64_t current_tick = <int64_t>(self._current_timestamp / 60.0)

        try:
            if current_tick > last_tick or len(self._trading_rules) <= 0:
                product_info = await self._api_request(http_method='get', url=BeaxyConstants.PublicApi.SYMBOLS_URL, is_auth_required=False)
                trading_rules_list = self._format_trading_rules(product_info)
                self._trading_rules.clear()
                for trading_rule in trading_rules_list:

                    # at Beaxy all pairs listed without splitter, so there is need to convert it
                    trading_pair = '{}-{}'.format(*BeaxyExchange.split_trading_pair(trading_rule.trading_pair))

                    self._trading_rules[trading_pair] = trading_rule
        except Exception:
            self.logger().warning('Got exception while updating trading rules.', exc_info=True)

    def _format_trading_rules(self, market_dict: Dict[str, Any]) -> List[TradingRule]:
        """
        Turns json data from API into TradingRule instances
        :returns: List of TradingRule
        """
        cdef:
            list retval = []

        for rule in market_dict:
            try:
                trading_pair = rule.get('symbol')
                # Parsing from string doesn't mess up the precision
                retval.append(TradingRule(trading_pair,
                                          min_price_increment=Decimal(str(rule.get('tickSize'))),
                                          min_order_size=Decimal(str(rule.get('minimumQuantity'))),
                                          max_order_size=Decimal(str(rule.get('maximumQuantity'))),
                                          min_base_amount_increment=Decimal(str(rule.get('quantityIncrement'))),
                                          min_quote_amount_increment=Decimal(str(rule.get('quantityIncrement'))),
                                          max_price_significant_digits=Decimal(str(rule.get('pricePrecision')))))
            except Exception:
                self.logger().error(f'Error parsing the trading_pair rule {rule}. Skipping.', exc_info=True)
        return retval

    async def _iter_user_event_queue(self) -> AsyncIterable[Dict[str, Any]]:
        while True:
            try:
                yield await self._user_stream_tracker.user_stream.get()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    'Unknown error. Retrying after 1 seconds.',
                    exc_info=True,
                    app_warning_msg='Could not fetch user events from Beaxy. Check API key and network connection.'
                )
                await asyncio.sleep(1.0)

    async def _user_stream_event_listener(self):
        async for msg_type, event_message in self._iter_user_event_queue():
            try:
                if msg_type == BeaxyConstants.UserStream.BALANCE_MESSAGE:
                    if event_message['type'] == 'update':
                        msgs = [event_message['data']]
                    elif event_message['type'] == 'snapshot':
                        msgs = event_message['data']

                    for msg in msgs:
                        asset_name = msg['currency']
                        available_balance = Decimal(str(msg['available_balance']))
                        total_balance = Decimal(str(msg['total_balance']))
                        self._account_available_balances[asset_name] = available_balance
                        self._account_balances[asset_name] = total_balance

                elif msg_type == BeaxyConstants.UserStream.ORDER_MESSAGE:
                    order = event_message['data']
                    exchange_order_id = order['order_id']
                    client_order_id = order['comment']
                    order_status = order['order_status']

                    if client_order_id is None:
                        continue

                    tracked_order = self._in_flight_orders.get(client_order_id)

                    if tracked_order is None:
                        self.logger().debug(f'Didn`rt find order with id {client_order_id}')
                        continue

                    if not tracked_order.exchange_order_id:
                        tracked_order.exchange_order_id = exchange_order_id

                    execute_price = s_decimal_0
                    execute_amount_diff = s_decimal_0

                    if order_status == 'partially_filled':
                        order_filled_size = Decimal(str(order['trade_size']))
                        execute_price = Decimal(str(order['trade_price']))

                        execute_amount_diff = order_filled_size - tracked_order.executed_amount_base

                        if execute_amount_diff > s_decimal_0:

                            tracked_order.executed_amount_base = order_filled_size
                            tracked_order.executed_amount_quote += Decimal(execute_amount_diff * execute_price)

                            self.logger().info(f'Filled {execute_amount_diff} out of {tracked_order.amount} of the '
                                               f'{tracked_order.order_type_description} order {tracked_order.client_order_id}')

                            self.c_trigger_event(self.MARKET_ORDER_FILLED_EVENT_TAG,
                                                 OrderFilledEvent(
                                                     self._current_timestamp,
                                                     tracked_order.client_order_id,
                                                     tracked_order.trading_pair,
                                                     tracked_order.trade_type,
                                                     tracked_order.order_type,
                                                     execute_price,
                                                     execute_amount_diff,
                                                     self.c_get_fee(
                                                         tracked_order.base_asset,
                                                         tracked_order.quote_asset,
                                                         tracked_order.order_type,
                                                         tracked_order.trade_type,
                                                         execute_price,
                                                         execute_amount_diff,
                                                     ),
                                                     exchange_trade_id=exchange_order_id
                                                 ))

                    elif order_status == 'completely_filled':

                        new_confirmed_amount = Decimal(str(order['size']))
                        execute_amount_diff = new_confirmed_amount - tracked_order.executed_amount_base
                        execute_price = Decimal(str(order['limit_price'] if order['limit_price'] else order['average_price']))

                        # Emit event if executed amount is greater than 0.
                        if execute_amount_diff > s_decimal_0:

                            tracked_order.executed_amount_base = execute_amount_diff
                            tracked_order.executed_amount_quote += execute_amount_diff * execute_price

                            order_type_description = tracked_order.order_type_description
                            order_filled_event = OrderFilledEvent(
                                self._current_timestamp,
                                tracked_order.client_order_id,
                                tracked_order.trading_pair,
                                tracked_order.trade_type,
                                tracked_order.order_type,
                                execute_price,
                                execute_amount_diff,
                                self.c_get_fee(
                                    tracked_order.base_asset,
                                    tracked_order.quote_asset,
                                    tracked_order.order_type,
                                    tracked_order.trade_type,
                                    execute_price,
                                    execute_amount_diff,
                                ),
                                exchange_trade_id=exchange_order_id,
                            )
                            self.logger().info(f'Filled {execute_amount_diff} out of {tracked_order.amount} of the '
                                               f'{order_type_description} order {client_order_id}.')
                            self.c_trigger_event(self.MARKET_ORDER_FILLED_EVENT_TAG, order_filled_event)

                        if tracked_order.trade_type == TradeType.BUY:
                            self.logger().info(f'The market buy order {tracked_order.client_order_id} has completed '
                                               f'according to Beaxy user stream.')
                            self.c_trigger_event(self.MARKET_BUY_ORDER_COMPLETED_EVENT_TAG,
                                                 BuyOrderCompletedEvent(self._current_timestamp,
                                                                        tracked_order.client_order_id,
                                                                        tracked_order.base_asset,
                                                                        tracked_order.quote_asset,
                                                                        (tracked_order.fee_asset
                                                                         or tracked_order.base_asset),
                                                                        tracked_order.executed_amount_base,
                                                                        tracked_order.executed_amount_quote,
                                                                        tracked_order.fee_paid,
                                                                        tracked_order.order_type))
                        else:
                            self.logger().info(f'The market sell order {tracked_order.client_order_id} has completed '
                                               f'according to Beaxy user stream.')
                            self.c_trigger_event(self.MARKET_SELL_ORDER_COMPLETED_EVENT_TAG,
                                                 SellOrderCompletedEvent(self._current_timestamp,
                                                                         tracked_order.client_order_id,
                                                                         tracked_order.base_asset,
                                                                         tracked_order.quote_asset,
                                                                         (tracked_order.fee_asset
                                                                          or tracked_order.quote_asset),
                                                                         tracked_order.executed_amount_base,
                                                                         tracked_order.executed_amount_quote,
                                                                         tracked_order.fee_paid,
                                                                         tracked_order.order_type))

                        self.c_stop_tracking_order(tracked_order.client_order_id)

                    elif order_status == 'canceled':
                        tracked_order.last_state = 'canceled'
                        self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                             OrderCancelledEvent(self._current_timestamp, tracked_order.client_order_id))
                        self.c_stop_tracking_order(tracked_order.client_order_id)
                    elif order_status in ['rejected', 'replaced', 'suspended']:
                        tracked_order.last_state = order_status
                        self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                             MarketOrderFailureEvent(self._current_timestamp, tracked_order.client_order_id, tracked_order.order_type))
                        self.c_stop_tracking_order(tracked_order.client_order_id)
                    elif order_status == 'expired':
                        tracked_order.last_state = 'expired'
                        self.c_trigger_event(self.MARKET_ORDER_EXPIRED_EVENT_TAG,
                                             OrderExpiredEvent(self._current_timestamp, tracked_order.client_order_id))
                        self.c_stop_tracking_order(tracked_order.client_order_id)

            except Exception:
                self.logger().error('Unexpected error in user stream listener loop.', exc_info=True)
                await asyncio.sleep(5.0)

    async def _http_client(self) -> aiohttp.ClientSession:
        """
        :returns: Shared client session instance
        """
        if self._shared_client is None:
            self._shared_client = aiohttp.ClientSession()
        return self._shared_client

    async def _api_request(
        self,
        http_method: str,
        path_url: str = None,
        url: str = None,
        is_auth_required: bool = True,
        data: Optional[Dict[str, Any]] = None,
        custom_headers: [Optional[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        A wrapper for submitting API requests to Beaxy
        :returns: json data from the endpoints
        """
        try:
            assert path_url is not None or url is not None

            url = f'{BeaxyConstants.TradingApi.BASE_URL}{path_url}' if url is None else url

            data_str = '' if data is None else json.dumps(data, separators=(',', ':'))

            if is_auth_required:
                headers = await self.beaxy_auth.generate_auth_dict(http_method, path_url, data_str)
            else:
                headers = {'Content-Type': 'application/json'}

            if custom_headers:
                headers = {**custom_headers, **headers}

            if http_method.upper() == 'POST':
                headers['Content-Type'] = 'application/json; charset=utf-8'

            if path_url == BeaxyConstants.TradingApi.TRADE_SETTINGS_ENDPOINT:
                auth_token = await self._beaxy_auth.get_token()
                headers['Authorization'] = f'Bearer {auth_token}'

            self.logger().debug(f'Submitting {http_method} request to {url} with headers {headers}')

            client = await self._http_client()
            async with client.request(http_method.upper(), url=url, timeout=self.API_CALL_TIMEOUT, data=data_str, headers=headers) as response:
                result = None
                try:
                    result = await response.json()
                except ContentTypeError:
                    pass

                if response.status not in [200, 204]:

                    if response.status == 401:
                        self.logger().error(f'Beaxy auth error, token timings: {self._beaxy_auth.token_timings_str()}')
                        self._beaxy_auth.invalidate_token()

                    raise BeaxyIOError(
                        f'Error during api request with body {data_str}. HTTP status is {response.status}. Response - {await response.text()} - Request {response.request_info}',
                        response=response,
                        result=result,
                    )
                self.logger().debug(f'Got response status {response.status}')
                self.logger().debug(f'Got response {result}')
                return result
        except BeaxyIOError:
            raise
        except Exception:
            self.logger().warning('Exception while making api request.', exc_info=True)
            raise

    async def _status_polling_loop(self):
        """
        Background process that periodically pulls for changes from the rest API
        """
        while True:
            try:

                self._poll_notifier = asyncio.Event()
                await self._poll_notifier.wait()

                await safe_gather(
                    # self._update_balances(),  # due to balance polling inconsistency, we use only ws balance update
                    self._update_trade_fees(),
                    self._update_order_status(),
                )

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    'Unexpected error while fetching account updates.',
                    exc_info=True,
                    app_warning_msg='Could not fetch account updates on Beaxy.'
                                    'Check API key and network connection.'
                )
                await asyncio.sleep(0.5)

    async def _trading_rules_polling_loop(self):
        """
        Separate background process that periodically pulls for trading rule changes
        (Since trading rules don't get updated often, it is pulled less often.)
        """
        while True:
            try:
                await safe_gather(self._update_trading_rules())
                await asyncio.sleep(6000)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    'Unexpected error while fetching trading rules.',
                    exc_info=True,
                    app_warning_msg='Could not fetch trading rule updates on Beaxy. '
                                    'Check network connection.'
                )
                await asyncio.sleep(0.5)

    cdef OrderBook c_get_order_book(self, str trading_pair):
        """
        :returns: OrderBook for a specific trading pair
        """
        cdef:
            dict order_books = self._order_book_tracker.order_books

        if trading_pair not in order_books:
            raise ValueError(f'No order book exists for "{trading_pair}".')
        return order_books[trading_pair]

    cdef c_start_tracking_order(self,
                                str client_order_id,
                                str trading_pair,
                                object order_type,
                                object trade_type,
                                object price,
                                object amount):
        """
        Add new order to self._in_flight_orders mapping
        """
        self._in_flight_orders[client_order_id] = BeaxyInFlightOrder(
            client_order_id,
            None,
            trading_pair,
            order_type,
            trade_type,
            price,
            amount,
            created_at=datetime.utcnow()
        )

    cdef c_did_timeout_tx(self, str tracking_id):
        self.c_trigger_event(
            self.MARKET_TRANSACTION_FAILURE_EVENT_TAG,
            MarketTransactionFailureEvent(self._current_timestamp, tracking_id)
        )

    cdef object c_get_order_price_quantum(self, str trading_pair, object price):
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]

        return trading_rule.min_price_increment

    cdef object c_get_order_size_quantum(self, str trading_pair, object order_size):
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]
        return Decimal(trading_rule.min_base_amount_increment)

    cdef object c_quantize_order_amount(self, str trading_pair, object amount, object price=s_decimal_0):
        """
        *required
        Check current order amount against trading rule, and correct any rule violations
        :return: Valid order amount in Decimal format
        """
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]
            object quantized_amount = ExchangeBase.c_quantize_order_amount(self, trading_pair, amount)

        # Check against min_order_size. If not passing either check, return 0.
        if quantized_amount < trading_rule.min_order_size:
            return s_decimal_0

        # Check against max_order_size. If not passing either check, return 0.
        if quantized_amount > trading_rule.max_order_size:
            return s_decimal_0

        return quantized_amount

    def supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    cdef c_stop_tracking_order(self, str order_id):
        """
        Delete an order from self._in_flight_orders mapping
        """
        if order_id in self._in_flight_orders:
            del self._in_flight_orders[order_id]

    def get_price(self, trading_pair: str, is_buy: bool) -> Decimal:
        return self.c_get_price(trading_pair, is_buy)

    def buy(self, trading_pair: str, amount: Decimal, order_type=OrderType.MARKET,
            price: Decimal = s_decimal_NaN, **kwargs) -> str:
        return self.c_buy(trading_pair, amount, order_type, price, kwargs)

    def sell(self, trading_pair: str, amount: Decimal, order_type=OrderType.MARKET,
             price: Decimal = s_decimal_NaN, **kwargs) -> str:
        return self.c_sell(trading_pair, amount, order_type, price, kwargs)

    def cancel(self, trading_pair: str, client_order_id: str):
        return self.c_cancel(trading_pair, client_order_id)

    def get_fee(self,
                base_currency: str,
                quote_currency: str,
                order_type: OrderType,
                order_side: TradeType,
                amount: Decimal,
                price: Decimal = s_decimal_NaN) -> TradeFee:
        return self.c_get_fee(base_currency, quote_currency, order_type, order_side, amount, price)

    def get_order_book(self, trading_pair: str) -> OrderBook:
        return self.c_get_order_book(trading_pair)
