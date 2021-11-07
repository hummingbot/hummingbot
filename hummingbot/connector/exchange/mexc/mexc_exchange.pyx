import asyncio

import aiohttp
from libc.stdint cimport int64_t
import logging
import time
from typing import (
    Any,
    AsyncIterable,
    Dict,
    List,
    Optional,
)
import ujson
from hummingbot.core.clock cimport Clock
from hummingbot.connector.exchange.mexc import mexc_utils
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.core.data_type.order_book_tracker import OrderBookTrackerDataSourceType
from hummingbot.core.data_type.transaction_tracker import TransactionTracker
from hummingbot.core.event.events import (
    MarketEvent,
    BuyOrderCompletedEvent,
    SellOrderCompletedEvent,
    OrderFilledEvent,
    OrderCancelledEvent,
    BuyOrderCreatedEvent,
    SellOrderCreatedEvent,
    MarketTransactionFailureEvent,
    MarketOrderFailureEvent,
    OrderType,
    TradeType,
    TradeFee
)
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_call_scheduler import AsyncCallScheduler
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from urllib.parse import quote, urljoin

from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.mexc.mexc_auth import MexcAuth
from hummingbot.connector.exchange.mexc.mexc_in_flight_order import MexcInFlightOrder
from hummingbot.connector.exchange.mexc.mexc_order_book_tracker import MexcOrderBookTracker
from hummingbot.connector.trading_rule cimport TradingRule
from hummingbot.connector.exchange_base import (
    ExchangeBase,
    s_decimal_NaN
)
from hummingbot.connector.exchange.mexc.mexc_user_stream_tracker import MexcUserStreamTracker
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce
from hummingbot.core.utils.estimate_fee import estimate_fee

from hummingbot.connector.exchange.mexc.constants import *

from hummingbot.connector.exchange.mexc.mexc_utils import (
    convert_to_exchange_trading_pair,
    convert_from_exchange_trading_pair, ws_order_status_convert_to_str
)

from decimal import *

hm_logger = None
s_decimal_0 = Decimal(0)


class MexcAPIError(IOError):
    def __init__(self, error_payload: Dict[str, Any]):
        super().__init__(str(error_payload))
        self.error_payload = error_payload


cdef class MexcExchangeTransactionTracker(TransactionTracker):
    cdef:
        MexcExchange _owner

    def __init__(self, owner: MexcExchange):
        super().__init__()
        self._owner = owner

    cdef c_did_timeout_tx(self, str tx_id):
        TransactionTracker.c_did_timeout_tx(self, tx_id)
        self._owner.c_did_timeout_tx(tx_id)

cdef class MexcExchange(ExchangeBase):
    def stop_tracking_order(self, order_id: str):
        pass

    MARKET_RECEIVED_ASSET_EVENT_TAG = MarketEvent.ReceivedAsset.value
    MARKET_BUY_ORDER_COMPLETED_EVENT_TAG = MarketEvent.BuyOrderCompleted.value
    MARKET_SELL_ORDER_COMPLETED_EVENT_TAG = MarketEvent.SellOrderCompleted.value
    MARKET_WITHDRAW_ASSET_EVENT_TAG = MarketEvent.WithdrawAsset.value
    MARKET_ORDER_CANCELLED_EVENT_TAG = MarketEvent.OrderCancelled.value
    MARKET_TRANSACTION_FAILURE_EVENT_TAG = MarketEvent.TransactionFailure.value
    MARKET_ORDER_FAILURE_EVENT_TAG = MarketEvent.OrderFailure.value
    MARKET_ORDER_FILLED_EVENT_TAG = MarketEvent.OrderFilled.value
    MARKET_BUY_ORDER_CREATED_EVENT_TAG = MarketEvent.BuyOrderCreated.value
    MARKET_SELL_ORDER_CREATED_EVENT_TAG = MarketEvent.SellOrderCreated.value
    API_CALL_TIMEOUT = 10.0
    UPDATE_ORDERS_INTERVAL = 10.0
    SHORT_POLL_INTERVAL = 5.0
    MORE_SHORT_POLL_INTERVAL = 2.0
    LONG_POLL_INTERVAL = 120.0

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global hm_logger
        if hm_logger is None:
            hm_logger = logging.getLogger(__name__)
        return hm_logger

    def __init__(self,
                 mexc_api_key: str,
                 mexc_secret_key: str,
                 poll_interval: float = 5.0,
                 order_book_tracker_data_source_type: OrderBookTrackerDataSourceType = OrderBookTrackerDataSourceType.EXCHANGE_API,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True):

        super().__init__()
        self._async_scheduler = AsyncCallScheduler(call_interval=0.5)
        self._data_source_type = order_book_tracker_data_source_type
        self._ev_loop = asyncio.get_event_loop()
        self._mexc_auth = MexcAuth(api_key=mexc_api_key, secret_key=mexc_secret_key)
        self._in_flight_orders = {}
        self._last_poll_timestamp = 0
        self._last_timestamp = 0
        self._order_book_tracker = MexcOrderBookTracker(trading_pairs=trading_pairs)
        self._poll_notifier = asyncio.Event()
        self._poll_interval = poll_interval
        self._shared_client = None
        self._status_polling_task = None
        self._trading_required = trading_required
        self._trading_rules = {}
        self._trading_rules_polling_task = None
        self._tx_tracker = MexcExchangeTransactionTracker(self)
        self._user_stream_tracker = MexcUserStreamTracker(mexc_auth=self._mexc_auth,
                                                          trading_pairs=trading_pairs)

    @property
    def name(self) -> str:
        return "mexc"

    @property
    def order_book_tracker(self) -> MexcOrderBookTracker:
        return self._order_book_tracker

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        return self._order_book_tracker.order_books

    @property
    def trading_rules(self) -> Dict[str, TradingRule]:
        return self._trading_rules

    @property
    def in_flight_orders(self) -> Dict[str, MexcInFlightOrder]:
        return self._in_flight_orders

    @property
    def limit_orders(self) -> List[LimitOrder]:
        return [
            in_flight_order.to_limit_order()
            for in_flight_order in self._in_flight_orders.values()
        ]

    @property
    def tracking_states(self) -> Dict[str, Any]:
        return {
            key: value.to_json()
            for key, value in self._in_flight_orders.items()
        }

    def restore_tracking_states(self, saved_states: Dict[str, Any]):
        self._in_flight_orders.update({
            key: MexcInFlightOrder.from_json(value)
            for key, value in saved_states.items()
        })

    @property
    def shared_client(self) -> str:
        return self._shared_client

    @property
    def user_stream_tracker(self) -> MexcUserStreamTracker:
        return self._user_stream_tracker

    @shared_client.setter
    def shared_client(self, client: aiohttp.ClientSession):
        self._shared_client = client

    cdef c_start(self, Clock clock, double timestamp):
        self._tx_tracker.c_start(clock, timestamp)
        ExchangeBase.c_start(self, clock, timestamp)

    cdef c_stop(self, Clock clock):
        ExchangeBase.c_stop(self, clock)
        self._async_scheduler.stop()

    async def start_network(self):
        self._stop_network()
        self._order_book_tracker.start()
        self._trading_rules_polling_task = safe_ensure_future(self._trading_rules_polling_loop())

        if self._trading_required:
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())
            self._user_stream_tracker_task = safe_ensure_future(self._user_stream_tracker.start())
            self._user_stream_event_listener_task = safe_ensure_future(self._user_stream_event_listener())
            await self._update_balances()

    def _stop_network(self):
        self._order_book_tracker.stop()
        if self._status_polling_task is not None:
            self._status_polling_task.cancel()
            self._status_polling_task = None
        if self._trading_rules_polling_task is not None:
            self._trading_rules_polling_task.cancel()
            self._trading_rules_polling_task = None
        if self._user_stream_tracker_task is not None:
            self._user_stream_tracker_task.cancel()
            self._user_stream_tracker_task = None
        if self._user_stream_event_listener_task is not None:
            self._user_stream_event_listener_task.cancel()
            self._user_stream_event_listener_task = None

    async def stop_network(self):
        self._stop_network()

    async def check_network(self) -> NetworkStatus:
        try:
            await self._api_request(method="GET", path_url=MEXC_PING_URL)
        except asyncio.CancelledError:
            raise
        except Exception as ex:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    cdef c_tick(self, double timestamp):
        """
        Is called automatically by the clock for each clock's tick (1 second by default).
        It checks if status polling task is due for execution.
        """
        cdef:
            double now = time.time()
            # double poll_interval = (self.SHORT_POLL_INTERVAL
            #                         if now - self.user_stream_tracker.last_recv_time > 60.0
            #                         else self.LONG_POLL_INTERVAL
            #                         )
            double poll_interval = self.MORE_SHORT_POLL_INTERVAL

            int64_t last_tick = <int64_t> (self._last_timestamp / poll_interval)
            int64_t current_tick = <int64_t> (timestamp / poll_interval)
        ExchangeBase.c_tick(self, timestamp)
        self._tx_tracker.c_tick(timestamp)
        if current_tick > last_tick:
            if not self._poll_notifier.is_set():
                self._poll_notifier.set()
        self._last_timestamp = timestamp

    async def _http_client(self) -> aiohttp.ClientSession:
        if self._shared_client is None:
            self._shared_client = aiohttp.ClientSession()
        return self._shared_client

    async def _api_request(self,
                           method: str,
                           path_url: str,
                           params: Optional[Dict[str, Any]] = {},
                           data={},
                           is_auth_required: bool = False) -> Dict[str, Any]:

        headers = {"Content-Type": "application/json"}
        client = await self._http_client()
        text_data = ujson.dumps(data) if data else None

        path_url = self._mexc_auth.add_auth_to_params(method, path_url, params, is_auth_required)
        url = urljoin(MEXC_BASE_URL, path_url)
        response_core = client.request(
            method=method.upper(),
            url=url,
            headers=headers,
            # params=params if params else None, #mexc`s params  is already in the url
            data=text_data,
        )

        async with response_core as response:
            if response.status != 200:
                raise IOError(f"Error request from {url}. Response: {await response.json()}.")
            try:
                parsed_response = await response.json()
                return parsed_response
            except Exception as ex:
                raise IOError(f"Error parsing data from {url}." + repr(ex))

    async def _update_balances(self):
        cdef:
            str path_url = MEXC_BALANCE_URL
            dict balances = {}
            dict new_available_balances = {}
            dict new_balances = {}
            str asset_name
            object balance
        msg = await self._api_request("GET", path_url=path_url, is_auth_required=True)
        if msg['code'] == 200:
            balances = msg['data']
        else:
            raise Exception(msg)
            self.logger().info(f" _update_balances error: {msg} ")
            return

        self._account_available_balances.clear()
        self._account_balances.clear()
        for k, balance in balances.items():
            # if Decimal(balance['frozen']) + Decimal(balance['available']) > Decimal(0.0001):
            self._account_balances[k] = Decimal(balance['frozen']) + Decimal(balance['available'])
            self._account_available_balances[k] = Decimal(balance['available'])

    cdef object c_get_fee(self,
                          str base_currency,
                          str quote_currency,
                          object order_type,
                          object order_side,
                          object amount,
                          object price):

        is_maker = order_type is OrderType.LIMIT_MAKER
        return estimate_fee("mexc", is_maker)

    async def _update_trading_rules(self):
        cdef:
            int64_t last_tick = 0
            int64_t current_tick = 0
        try:
            last_tick = <int64_t> (self._last_timestamp / 60.0)
            current_tick = <int64_t> (self._current_timestamp / 60.0)
            if current_tick > last_tick or len(self._trading_rules) < 1:
                exchange_info = await self._api_request("GET", path_url=MEXC_SYMBOL_URL)
                trading_rules_list = self._format_trading_rules(exchange_info['data'])
                self._trading_rules.clear()
                for trading_rule in trading_rules_list:
                    self._trading_rules[trading_rule.trading_pair] = trading_rule
        except Exception as ex:
            self.logger().error(f"Error _update_trading_rules:" + str(ex), exc_info=True)

    def _format_trading_rules(self, raw_trading_pair_info: List[Dict[str, Any]]) -> List[TradingRule]:
        cdef:
            list trading_rules = []

        for info in raw_trading_pair_info:
            try:
                trading_rules.append(
                    TradingRule(trading_pair=convert_from_exchange_trading_pair(info['symbol']),
                                # min_order_size=Decimal(info["min_amount"]),
                                # max_order_size=Decimal(info["max_amount"]),
                                min_price_increment=Decimal(mexc_utils.num_to_increment(info["price_scale"])),
                                min_base_amount_increment=Decimal(mexc_utils.num_to_increment(info["quantity_scale"])),
                                # min_quote_amount_increment=Decimal(info["1e-{info['value-precision']}"]),
                                # min_notional_size=Decimal(info["min-order-value"])
                                min_notional_size=Decimal(info["min_amount"]),
                                # max_notional_size=Decimal(info["max_amount"]),

                                )
                )
            except Exception:
                self.logger().error(f"Error parsing the trading pair rule {info}. Skipping.", exc_info=True)
        return trading_rules

    async def get_order_status(self, exchangge_order_id: str, trading_pair: str) -> Dict[str, Any]:
        params = {"order_ids": exchangge_order_id}
        msg = await self._api_request("GET",
                                      path_url=MEXC_ORDER_DETAILS_URL,
                                      params=params,
                                      is_auth_required=True)

        if msg["code"] == 200:
            return msg['data'][0]

    async def _update_order_status(self):
        cdef:
            int64_t last_tick = <int64_t> (self._last_poll_timestamp / self.UPDATE_ORDERS_INTERVAL)
            int64_t current_tick = <int64_t> (self._current_timestamp / self.UPDATE_ORDERS_INTERVAL)
        if current_tick > last_tick and len(self._in_flight_orders) > 0:
            tracked_orders = list(self._in_flight_orders.values())
            for tracked_order in tracked_orders:
                try:
                    exchange_order_id = await tracked_order.get_exchange_order_id()
                    try:
                        order_update = await self.get_order_status(exchange_order_id, tracked_order.trading_pair)
                    except MexcAPIError as ex:
                        err_code = ex.error_payload.get("error").get('err-code')
                        self.c_stop_tracking_order(tracked_order.client_order_id)
                        self.logger().info(f"The limit order {tracked_order.client_order_id} "
                                           f"has failed according to order status API. - {err_code}")
                        self.c_trigger_event(
                            self.MARKET_ORDER_FAILURE_EVENT_TAG,
                            MarketOrderFailureEvent(
                                self._current_timestamp,
                                tracked_order.client_order_id,
                                tracked_order.order_type
                            )
                        )
                        continue

                    if order_update is None:
                        self.logger().network(
                            f"Error fetching status update for the order {tracked_order.client_order_id}: "
                            f"{exchange_order_id}.",
                            app_warning_msg=f"Could not fetch updates for the order {tracked_order.client_order_id}. "
                                            f"The order has either been filled or canceled."
                        )
                        continue
                    tracked_order.last_state = order_update['state']
                    order_status = order_update['state']
                    new_confirmed_amount = Decimal(order_update['deal_quantity'])
                    execute_amount_diff = new_confirmed_amount - tracked_order.executed_amount_base

                    if execute_amount_diff > s_decimal_0:
                        execute_price = Decimal(
                            Decimal(order_update['deal_amount']) / Decimal(order_update['deal_quantity']))
                        tracked_order.executed_amount_base = Decimal(order_update['deal_quantity'])
                        tracked_order.executed_amount_quote = Decimal(order_update['deal_amount'])

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
                                execute_amount_diff,
                                execute_price,
                            ),
                            exchange_trade_id=exchange_order_id
                        )
                        self.logger().info(f"Filled {execute_amount_diff} out of {tracked_order.amount} of the "
                                           f"order {tracked_order.client_order_id}.")
                        self.c_trigger_event(self.MARKET_ORDER_FILLED_EVENT_TAG, order_filled_event)
                    if order_status == "FILLED":
                        client = await self._http_client()
                        fee_paid = await self.get_deal_detail_fee(client, tracked_order.exchange_order_id)
                        tracked_order.fee_paid = fee_paid
                        tracked_order.last_state = order_status
                        self.c_stop_tracking_order(tracked_order.client_order_id)
                        if tracked_order.trade_type is TradeType.BUY:
                            self.logger().info(
                                f"The BUY {tracked_order.order_type} order {tracked_order.client_order_id} has completed "
                                f"according to order delta restful API.")
                            self.c_trigger_event(self.MARKET_BUY_ORDER_COMPLETED_EVENT_TAG,
                                                 BuyOrderCompletedEvent(self._current_timestamp,
                                                                        tracked_order.client_order_id,
                                                                        tracked_order.base_asset,
                                                                        tracked_order.quote_asset,
                                                                        tracked_order.fee_asset or tracked_order.quote_asset,
                                                                        tracked_order.executed_amount_base,
                                                                        tracked_order.executed_amount_quote,
                                                                        tracked_order.fee_paid,
                                                                        tracked_order.order_type))
                        elif tracked_order.trade_type is TradeType.SELL:
                            self.logger().info(
                                f"The SELL {tracked_order.order_type} order {tracked_order.client_order_id} has completed "
                                f"according to order delta restful API.")
                            self.c_trigger_event(self.MARKET_SELL_ORDER_COMPLETED_EVENT_TAG,
                                                 SellOrderCompletedEvent(self._current_timestamp,
                                                                         tracked_order.client_order_id,
                                                                         tracked_order.base_asset,
                                                                         tracked_order.quote_asset,
                                                                         tracked_order.fee_asset or tracked_order.quote_asset,
                                                                         tracked_order.executed_amount_base,
                                                                         tracked_order.executed_amount_quote,
                                                                         tracked_order.fee_paid,
                                                                         tracked_order.order_type))
                        continue
                    if order_status == "CANCELED" or order_status == "PARTIALLY_CANCELED":
                        tracked_order.last_state = order_status
                        self.c_stop_tracking_order(tracked_order.client_order_id)
                        self.logger().info(f"Order {tracked_order.client_order_id} has been cancelled "
                                           f"according to order delta restful API.")
                        self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                             OrderCancelledEvent(self._current_timestamp,
                                                                 tracked_order.client_order_id))
                except Exception as ex:
                    self.logger().error("_update_order_status error ..." + repr(ex), exc_info=True)

    async def _status_polling_loop(self):
        while True:
            try:
                self._poll_notifier = asyncio.Event()
                await self._poll_notifier.wait()
                await safe_gather(
                    self._update_balances(),
                    self._update_order_status(),
                )
                self._last_poll_timestamp = self._current_timestamp
            except asyncio.CancelledError:
                raise
            except Exception as ex:
                self.logger().network("Unexpected error while fetching account updates." + repr(ex),
                                      exc_info=True,
                                      app_warning_msg="Could not fetch account updates from MEXC. "
                                                      "Check API key and network connection.")
                await asyncio.sleep(0.5)

    async def _trading_rules_polling_loop(self):
        while True:
            try:
                await self._update_trading_rules()
                await asyncio.sleep(60 * 5)
            except asyncio.CancelledError:
                raise
            except Exception as ex:
                self.logger().network("Unexpected error while fetching trading rules." + repr(ex),
                                      exc_info=True,
                                      app_warning_msg="Could not fetch new trading rules from MEXC. "
                                                      "Check network connection.")
                await asyncio.sleep(0.5)

    async def _iter_user_stream_queue(self) -> AsyncIterable[Dict[str, Any]]:
        while True:
            try:
                yield await self._user_stream_tracker.user_stream.get()
            except asyncio.CancelledError:
                raise
            except Exception as ex:
                self.logger().error(f"Unknown error. Retrying after 1 second. {ex}", exc_info=True)
                await asyncio.sleep(1.0)

    async def _user_stream_event_listener(self):
        async for stream_message in self._iter_user_stream_queue():
            try:

                if 'channel' in stream_message.keys() and stream_message['channel'] == 'push.personal.account':  # reserved,not use
                    continue
                elif 'channel' in stream_message.keys() and stream_message['channel'] == 'push.personal.order':  # order status
                    client_order_id = stream_message["data"]["clientOrderId"]
                    trading_pair = convert_from_exchange_trading_pair(stream_message["symbol"])
                    order_status = ws_order_status_convert_to_str(stream_message["data"]["status"])  # 1:NEW,2:FILLED,3:PARTIALLY_FILLED,4:CANCELED,5:PARTIALLY_CANCELED

                    tracked_order = self._in_flight_orders.get(client_order_id, None)

                    if tracked_order is None:
                        continue

                    if order_status in {"FILLED", "PARTIALLY_FILLED"}:
                        new_execute_amount_diff = s_decimal_0
                        executed_amount = Decimal(str(stream_message["data"]['quantity'])) - Decimal(
                            str(stream_message["data"]['remainQuantity']))
                        execute_price = Decimal(str(stream_message["data"]['price']))
                        execute_amount_diff = executed_amount - tracked_order.executed_amount_base
                        if execute_amount_diff > s_decimal_0:
                            tracked_order.executed_amount_base = executed_amount
                            tracked_order.executed_amount_quote = Decimal(str(stream_message["data"]['amount'])) - Decimal(
                                str(stream_message["data"]['remainAmount']))

                            current_fee = self.get_fee(tracked_order.base_asset,
                                                       tracked_order.quote_asset,
                                                       tracked_order.order_type,
                                                       tracked_order.trade_type,
                                                       execute_amount_diff,
                                                       execute_price)

                            self.logger().info(f"Filled {execute_amount_diff} out of {tracked_order.amount} of ")
                            self.c_trigger_event(self.MARKET_ORDER_FILLED_EVENT_TAG,
                                                 OrderFilledEvent(self._current_timestamp,
                                                                  tracked_order.client_order_id,
                                                                  tracked_order.trading_pair,
                                                                  tracked_order.trade_type,
                                                                  tracked_order.order_type,
                                                                  execute_price,
                                                                  execute_amount_diff,
                                                                  current_fee,
                                                                  exchange_trade_id=tracked_order.exchange_order_id))
                    if order_status == "FILLED":
                        client = await self._http_client()
                        fee_paid = await self.get_deal_detail_fee(client, tracked_order.exchange_order_id)
                        tracked_order.fee_paid = fee_paid
                        tracked_order.last_state = order_status
                        if tracked_order.trade_type is TradeType.BUY:
                            self.logger().info(
                                f"The BUY {tracked_order.order_type} order {tracked_order.client_order_id} has completed "
                                f"according to order delta websocket API.")
                            self.c_trigger_event(self.MARKET_BUY_ORDER_COMPLETED_EVENT_TAG,
                                                 BuyOrderCompletedEvent(self._current_timestamp,
                                                                        tracked_order.client_order_id,
                                                                        tracked_order.base_asset,
                                                                        tracked_order.quote_asset,
                                                                        tracked_order.fee_asset or tracked_order.quote_asset,
                                                                        tracked_order.executed_amount_base,
                                                                        tracked_order.executed_amount_quote,
                                                                        tracked_order.fee_paid,
                                                                        tracked_order.order_type))
                        elif tracked_order.trade_type is TradeType.SELL:
                            self.logger().info(
                                f"The SELL {tracked_order.order_type} order {tracked_order.client_order_id} has completed "
                                f"according to order delta websocket API.")
                            self.c_trigger_event(self.MARKET_SELL_ORDER_COMPLETED_EVENT_TAG,
                                                 SellOrderCompletedEvent(self._current_timestamp,
                                                                         tracked_order.client_order_id,
                                                                         tracked_order.base_asset,
                                                                         tracked_order.quote_asset,
                                                                         tracked_order.fee_asset or tracked_order.quote_asset,
                                                                         tracked_order.executed_amount_base,
                                                                         tracked_order.executed_amount_quote,
                                                                         tracked_order.fee_paid,
                                                                         tracked_order.order_type))
                        self.c_stop_tracking_order(tracked_order.client_order_id)
                        continue

                    if order_status == "CANCELED" or order_status == "PARTIALLY_CANCELED":
                        tracked_order.last_state = order_status
                        self.logger().info(f"Order {tracked_order.client_order_id} has been cancelled "
                                           f"according to order delta websocket API.")
                        self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                             OrderCancelledEvent(self._current_timestamp,
                                                                 tracked_order.client_order_id))
                        self.c_stop_tracking_order(tracked_order.client_order_id)

                else:
                    continue
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"Unexpected error in user stream listener lopp. {e}", exc_info=True)
                await asyncio.sleep(5.0)

    @property
    def status_dict(self) -> Dict[str, bool]:
        return {
            "order_books_initialized": self._order_book_tracker.ready,
            "acount_balance": len(self._account_balances) > 0 if self._trading_required else True,
            "trading_rule_initialized": len(self._trading_rules) > 0
        }

    def supported_order_types(self):
        return [OrderType.LIMIT, OrderType.MARKET]

    @property
    def ready(self) -> bool:
        return all(self.status_dict.values())

    async def place_order(self,
                          order_id: str,
                          trading_pair: str,
                          amount: Decimal,
                          is_buy: bool,
                          order_type: OrderType,
                          price: Decimal) -> str:

        if order_type is OrderType.LIMIT:
            order_type_str = "LIMIT_ORDER"
        elif order_type is OrderType.LIMIT_MAKER:
            order_type_str = "POST_ONLY"

        data = {
            'client_order_id': order_id,
            'order_type': order_type_str,
            'trade_type': "BID" if is_buy else "ASK",
            'symbol': convert_to_exchange_trading_pair(trading_pair),
            'quantity': str(amount),
            'price': str(price)
        }

        exchange_order_id = await self._api_request(
            "POST",
            path_url=MEXC_PLACE_ORDER,
            params={},
            data=data,
            is_auth_required=True
        )

        return str(exchange_order_id.get('data'))

    async def execute_buy(self,
                          order_id: str,
                          trading_pair: str,
                          amount: Decimal,
                          order_type: OrderType,
                          price: Optional[Decimal] = s_decimal_0):
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]
            object quote_amount
            object decimal_amount
            object decimal_price
            str exchange_order_id
            object tracked_order

        if not order_type.is_limit_type():
            self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                 MarketOrderFailureEvent(self._current_timestamp, order_id, order_type))
            raise Exception(f"Unsupported order type: {order_type}")

        decimal_price = self.c_quantize_order_price(trading_pair, price)
        decimal_amount = self.c_quantize_order_amount(trading_pair, amount, decimal_price)
        if decimal_price * decimal_amount < trading_rule.min_notional_size:
            self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                 MarketOrderFailureEvent(self._current_timestamp, order_id, order_type))
            raise ValueError(f"Buy order amount {decimal_amount} is lower than the notional size ")
        try:
            exchange_order_id = await self.place_order(order_id, trading_pair, decimal_amount, True, order_type,
                                                       decimal_price)
            self.c_start_tracking_order(
                client_order_id=order_id,
                exchange_order_id=exchange_order_id,
                trading_pair=trading_pair,
                order_type=order_type,
                trade_type=TradeType.BUY,
                price=decimal_price,
                amount=decimal_amount
            )
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(
                    f"Created {order_type.name.upper()} buy order {order_id} for {decimal_amount} {trading_pair}.")
            self.c_trigger_event(self.MARKET_BUY_ORDER_CREATED_EVENT_TAG,
                                 BuyOrderCreatedEvent(
                                     self._current_timestamp,
                                     order_type,
                                     trading_pair,
                                     decimal_amount,
                                     decimal_price,
                                     order_id
                                 ))
        except asyncio.CancelledError:
            raise
        except Exception as ex:
            self.c_stop_tracking_order(order_id)
            order_type_str = order_type.name.lower()

            self.logger().network(
                f"Error submitting buy {order_type_str} order to Mexc for "
                f"{decimal_amount} {trading_pair} "
                f"{decimal_price if order_type is OrderType.LIMIT else ''}."
                f"{decimal_price}." + repr(ex),
                exc_info=True,
                app_warning_msg="Failed to submit buy order to Mexc. Check API key and network connection."
            )
            self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                 MarketOrderFailureEvent(self._current_timestamp, order_id, order_type))

    cdef str c_buy(self,
                   str trading_pair,
                   object amount,
                   object order_type=OrderType.LIMIT,
                   object price=s_decimal_0,
                   dict kwargs={}):
        cdef:
            int64_t tracking_nonce = <int64_t> get_tracking_nonce()
            str order_id = str(f"buy-{trading_pair}-{tracking_nonce}")
        safe_ensure_future(self.execute_buy(order_id, trading_pair, amount, order_type, price))
        return order_id

    async def execute_sell(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           order_type: OrderType,
                           price: Optional[Decimal] = s_decimal_0):
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]
            object decimal_amount
            object decimal_price
            str exchange_order_id
            object tracked_order

        if not order_type.is_limit_type():
            self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                 MarketOrderFailureEvent(self._current_timestamp, order_id, order_type))
            raise Exception(f"Unsupported order type: {order_type}")

        decimal_price = self.c_quantize_order_price(trading_pair, price)
        decimal_amount = self.c_quantize_order_amount(trading_pair, amount, decimal_price)

        if decimal_price * decimal_amount < trading_rule.min_notional_size:
            self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                 MarketOrderFailureEvent(self._current_timestamp, order_id, order_type))
            raise ValueError(f"Sell order amount {decimal_amount} is lower than the notional size ")

        try:
            exchange_order_id = await self.place_order(order_id, trading_pair, decimal_amount, False, order_type,
                                                       decimal_price)
            self.c_start_tracking_order(
                client_order_id=order_id,
                exchange_order_id=exchange_order_id,
                trading_pair=trading_pair,
                order_type=order_type,
                trade_type=TradeType.SELL,
                price=decimal_price,
                amount=decimal_amount
            )
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(
                    f"Created {order_type.name.upper()} sell order {order_id} for {decimal_amount} {trading_pair}.")
            self.c_trigger_event(self.MARKET_SELL_ORDER_CREATED_EVENT_TAG,
                                 SellOrderCreatedEvent(
                                     self._current_timestamp,
                                     order_type,
                                     trading_pair,
                                     decimal_amount,
                                     decimal_price,
                                     order_id
                                 ))
        except asyncio.CancelledError:
            raise
        except Exception as ex:
            self.c_stop_tracking_order(order_id)
            order_type_str = order_type.name.lower()
            self.logger().network(
                f"Error submitting sell {order_type_str} order to Mexc for "
                f"{decimal_amount} {trading_pair} "
                f"{decimal_price if order_type is OrderType.LIMIT else ''}."
                f"{decimal_price}." + ",ex:" + repr(ex),
                exc_info=True,
                app_warning_msg=f"Failed to submit sell order to Mexc. Check API key and network connection."
            )
            self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                 MarketOrderFailureEvent(self._current_timestamp, order_id, order_type))

    cdef str c_sell(self,
                    str trading_pair,
                    object amount,
                    object order_type=OrderType.LIMIT,
                    object price=s_decimal_0,
                    dict kwargs={}):
        cdef:
            int64_t tracking_nonce = <int64_t> get_tracking_nonce()
            str order_id = str(f"sell-{trading_pair}-{tracking_nonce}")

        safe_ensure_future(self.execute_sell(order_id, trading_pair, amount, order_type, price))
        return order_id

    async def execute_cancel(self, trading_pair: str, client_order_id: str):
        try:
            tracked_order = self._in_flight_orders.get(client_order_id)
            if tracked_order is None:
                # raise ValueError(f"Failed to cancel order - {client_order_id}. Order not found.")
                self.logger().network(f"Failed to cancel order - {client_order_id}. Order not found.")
                return
            params = {
                "client_order_ids": client_order_id,
            }
            response = await self._api_request("DELETE", path_url=MEXC_ORDER_CANCEL, params=params,
                                               is_auth_required=True)

            if not response['code'] == 200:
                raise MexcAPIError("Order could not be canceled")

        except MexcAPIError as ex:
            self.logger().network(
                f"Failed to cancel order {client_order_id} : {repr(ex)}",
                exc_info=True,
                app_warning_msg=f"Failed to cancel the order {client_order_id} on Mexc. "
                                f"Check API key and network connection."
            )

    cdef c_cancel(self, str trading_pair, str order_id):
        safe_ensure_future(self.execute_cancel(trading_pair, order_id))
        return order_id

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        orders_by_trading_pair = {}

        for order in self._in_flight_orders.values():
            orders_by_trading_pair[order.trading_pair] = orders_by_trading_pair.get(order.trading_pair, [])
            orders_by_trading_pair[order.trading_pair].append(order)

        if len(orders_by_trading_pair) == 0:
            return []

        for trading_pair in orders_by_trading_pair:
            cancel_order_ids = [o.exchange_order_id for o in orders_by_trading_pair[trading_pair]]
            self.logger().debug(f"cancel_order_ids {cancel_order_ids} orders_by_trading_pair[trading_pair]")
            params = {
                'order_ids': quote(','.join([o for o in cancel_order_ids])),
            }

            cancellation_results = []
            try:
                cancel_all_results = await self._api_request(
                    "DELETE",
                    path_url=MEXC_ORDER_CANCEL,
                    params=params,
                    is_auth_required=True
                )

                for order_result_client_order_id, order_result_value in cancel_all_results['data'].items():
                    for o in orders_by_trading_pair[trading_pair]:
                        if o.client_order_id == order_result_client_order_id:
                            result_bool = True if order_result_value == "invalid order state" or order_result_value == "success" else False
                            cancellation_results.append(CancellationResult(o.exchange_order_id, result_bool))
                            if result_bool:
                                self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                                     OrderCancelledEvent(self._current_timestamp,
                                                                         None,
                                                                         exchange_order_id=o.exchange_order_id))

            except Exception as ex:

                self.logger().network(
                    f"Failed to cancel all orders: {cancel_order_ids}" + repr(ex),
                    exc_info=True,
                    app_warning_msg=f"Failed to cancel all orders on Mexc. Check API key and network connection."
                )

            return cancellation_results

    cdef OrderBook c_get_order_book(self, str trading_pair):
        cdef:
            dict order_books = self._order_book_tracker.order_books

        if trading_pair not in order_books:
            raise ValueError(f"No order book exists for '{trading_pair}'.")
        return order_books.get(trading_pair)

    cdef c_did_timeout_tx(self, str tracking_id):
        self.c_trigger_event(self.MARKET_TRANSACTION_FAILURE_EVENT_TAG,
                             MarketTransactionFailureEvent(self._current_timestamp, tracking_id))

    cdef c_start_tracking_order(self,
                                str client_order_id,
                                str exchange_order_id,
                                str trading_pair,
                                object order_type,
                                object trade_type,
                                object price,
                                object amount):
        self._in_flight_orders[client_order_id] = MexcInFlightOrder(
            client_order_id=client_order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=trading_pair,
            order_type=order_type,
            trade_type=trade_type,
            price=price,
            amount=amount
        )

    cdef c_stop_tracking_order(self, str order_id):
        if order_id in self._in_flight_orders:
            del self._in_flight_orders[order_id]

    cdef object c_get_order_price_quantum(self, str trading_pair, object price):
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]

        return trading_rule.min_price_increment

    cdef object c_get_order_size_quantum(self, str trading_pair, object price):
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]
        return Decimal(trading_rule.min_base_amount_increment)

    cdef object c_quantize_order_amount(self, str trading_pair, object amount, object price=s_decimal_0):
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]

            object quantized_amount = ExchangeBase.c_quantize_order_amount(self, trading_pair, amount)
            object current_price = self.c_get_price(trading_pair, False)
            object notional_size

        calc_price = current_price if price == s_decimal_0 else price

        notional_size = calc_price * quantized_amount

        if notional_size < trading_rule.min_notional_size * Decimal("1"):
            return s_decimal_0

        return quantized_amount

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

    async def get_deal_detail_fee(self, client: aiohttp.ClientSession, order_id: str) -> Dict[str, Any]:
        params = {
            'order_id': order_id,
        }
        msg = await self._api_request("GET", path_url=MEXC_DEAL_DETAIL, params=params, is_auth_required=True)
        balances: list = []
        fee = s_decimal_0
        if msg['code'] == 200:
            balances = msg['data']
        else:
            raise Exception(msg)
        for order in balances:
            fee += Decimal(order['fee'])
        return fee
