import aiohttp
import asyncio
from decimal import Decimal
from libc.stdint cimport int64_t
import logging
import pandas as pd
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
    TradeType
)
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_call_scheduler import AsyncCallScheduler
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.okex.okex_api_order_book_data_source import OkexAPIOrderBookDataSource
from hummingbot.connector.exchange.okex.okex_auth import OKExAuth
from hummingbot.connector.exchange.okex.okex_in_flight_order import OkexInFlightOrder
from hummingbot.connector.exchange.okex.okex_order_book_tracker import OkexOrderBookTracker
from hummingbot.connector.trading_rule cimport TradingRule
from hummingbot.connector.exchange_base import (
    ExchangeBase,
    s_decimal_NaN)
from hummingbot.connector.exchange.okex.okex_user_stream_tracker import OkexUserStreamTracker
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce
from hummingbot.core.utils.estimate_fee import estimate_fee

from hummingbot.connector.exchange.okex.constants import *


hm_logger = None
s_decimal_0 = Decimal(0)
TRADING_PAIR_SPLITTER = "-"
CLIENT_ID_PREFIX = "93027a12dac34fBC"


class OKExAPIError(IOError):
    def __init__(self, error_payload: Dict[str, Any]):
        super().__init__(str(error_payload))
        self.error_payload = error_payload


cdef class OkexExchangeTransactionTracker(TransactionTracker):
    cdef:
        OkexExchange _owner

    def __init__(self, owner: OkexExchange):
        super().__init__()
        self._owner = owner

    cdef c_did_timeout_tx(self, str tx_id):
        TransactionTracker.c_did_timeout_tx(self, tx_id)
        self._owner.c_did_timeout_tx(tx_id)


cdef class OkexExchange(ExchangeBase):
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
    LONG_POLL_INTERVAL = 120.0

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global hm_logger
        if hm_logger is None:
            hm_logger = logging.getLogger(__name__)
        return hm_logger

    def __init__(self,
                 okex_api_key: str,
                 okex_secret_key: str,
                 okex_passphrase: str,
                 poll_interval: float = 5.0,
                 order_book_tracker_data_source_type: OrderBookTrackerDataSourceType = OrderBookTrackerDataSourceType.EXCHANGE_API,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True):

        super().__init__()
        # self._account_id = ""
        self._async_scheduler = AsyncCallScheduler(call_interval=0.5)
        self._data_source_type = order_book_tracker_data_source_type
        self._ev_loop = asyncio.get_event_loop()
        self._okex_auth = OKExAuth(api_key=okex_api_key, secret_key=okex_secret_key, passphrase=okex_passphrase)
        self._in_flight_orders = {}
        self._last_poll_timestamp = 0
        self._last_timestamp = 0
        self._order_book_tracker = OkexOrderBookTracker(
            trading_pairs=trading_pairs
        )
        self._poll_notifier = asyncio.Event()
        self._poll_interval = poll_interval
        self._shared_client = None
        self._status_polling_task = None
        self._trading_required = trading_required
        self._trading_rules = {}
        self._trading_rules_polling_task = None
        self._tx_tracker = OkexExchangeTransactionTracker(self)
        self._user_stream_tracker = OkexUserStreamTracker(okex_auth=self._okex_auth,
                                                          trading_pairs=trading_pairs)

    @property
    def name(self) -> str:
        return "okex"

    @property
    def order_book_tracker(self) -> OkexOrderBookTracker:
        return self._order_book_tracker

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        return self._order_book_tracker.order_books

    @property
    def trading_rules(self) -> Dict[str, TradingRule]:
        return self._trading_rules

    @property
    def in_flight_orders(self) -> Dict[str, OkexInFlightOrder]:
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
            key: OkexInFlightOrder.from_json(value)
            for key, value in saved_states.items()
        })

    @property
    def shared_client(self) -> str:
        return self._shared_client

    @property
    def user_stream_tracker(self) -> OkexUserStreamTracker:
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

    async def stop_network(self):
        self._stop_network()

    async def check_network(self) -> NetworkStatus:
        try:
            await self._api_request(method="GET", path_url=OKEX_SERVER_TIME)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    cdef c_tick(self, double timestamp):
        cdef:
            double now = time.time()
            double poll_interval = (self.SHORT_POLL_INTERVAL
                                    if now - self.user_stream_tracker.last_recv_time > 60.0
                                    else self.LONG_POLL_INTERVAL)
            int64_t last_tick = <int64_t>(self._last_timestamp / poll_interval)
            int64_t current_tick = <int64_t>(timestamp / poll_interval)

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
        url = urljoin(OKEX_BASE_URL, path_url)
        client = await self._http_client()
        text_data = ujson.dumps(data) if data else None

        if is_auth_required:
            headers.update(self._okex_auth.add_auth_to_params(method, '/' + path_url, text_data))

        response_coro = client.request(
            method=method.upper(),
            url=url,
            headers=headers,
            params=params if params else None,
            data=text_data
        )

        async with response_coro as response:
            if response.status != 200:
                raise IOError(f"Error fetching data from {url}. Response: {await response.json()}.")
            try:
                parsed_response = await response.json()
                return parsed_response
            except Exception:
                raise IOError(f"Error parsing data from {url}.")

    async def _update_balances(self):
        cdef:
            str path_url = OKEX_BALANCE_URL
            # list data
            list balances
            dict new_available_balances = {}
            dict new_balances = {}
            str asset_name
            object balance

        msg = await self._api_request("GET", path_url=path_url, is_auth_required=True)

        if msg['code'] == '0':
            balances = msg['data'][0]['details']
        else:
            raise Exception(msg['msg'])

        self._account_available_balances.clear()
        self._account_balances.clear()

        for balance in balances:
            self._account_balances[balance['ccy']] = Decimal(balance['cashBal'])
            self._account_available_balances[balance['ccy']] = Decimal(balance['availBal'])

    cdef object c_get_fee(self,
                          str base_currency,
                          str quote_currency,
                          object order_type,
                          object order_side,
                          object amount,
                          object price,
                          object is_maker = None):
        # https://www.okex.com/fees.html
        is_maker = order_type is OrderType.LIMIT_MAKER
        return estimate_fee("okex", is_maker)

    async def _update_trading_rules(self):
        cdef:
            # The poll interval for trade rules is 60 seconds.
            int64_t last_tick = <int64_t>(self._last_timestamp / 60.0)
            int64_t current_tick = <int64_t>(self._current_timestamp / 60.0)
        if current_tick > last_tick or len(self._trading_rules) < 1:
            exchange_info = await self._api_request("GET", path_url=OKEX_INSTRUMENTS_URL)
            trading_rules_list = self._format_trading_rules(exchange_info["data"])
            self._trading_rules.clear()
            for trading_rule in trading_rules_list:
                self._trading_rules[trading_rule.trading_pair] = trading_rule

    def _format_trading_rules(self, raw_trading_pair_info: List[Dict[str, Any]]) -> List[TradingRule]:
        cdef:
            list trading_rules = []

        for info in raw_trading_pair_info:
            try:
                trading_rules.append(
                    TradingRule(trading_pair=info["instId"],
                                min_order_size=Decimal(info["minSz"]),
                                # max_order_size=Decimal(info["max-order-amt"]), # It's 100,000 USDT, How to model that?
                                min_price_increment=Decimal(info["tickSz"]),
                                min_base_amount_increment=Decimal(info["lotSz"]),
                                # min_quote_amount_increment=Decimal(info["1e-{info['value-precision']}"]),
                                # min_notional_size=Decimal(info["min-order-value"])
                                # min_notional_size=s_decimal_0  # Couldn't find a value for this in the docs
                                )
                )
            except Exception:
                self.logger().error(f"Error parsing the trading pair rule {info}. Skipping.", exc_info=True)
        return trading_rules

    async def get_order_status(self, exchange_order_id: str, trading_pair: str) -> Dict[str, Any]:
        msg = await self._api_request("GET",
                                      path_url=OKEX_ORDER_DETAILS_URL.format(ordId=exchange_order_id,
                                                                             trading_pair=trading_pair),
                                      is_auth_required=True)
        if msg['data']:
            return msg['data'][0]

    async def _update_order_status(self):
        cdef:
            # The poll interval for order status is 10 seconds.
            int64_t last_tick = <int64_t>(self._last_poll_timestamp / self.UPDATE_ORDERS_INTERVAL)
            int64_t current_tick = <int64_t>(self._current_timestamp / self.UPDATE_ORDERS_INTERVAL)

        tracked_orders = list(self._in_flight_orders.values())
        for tracked_order in tracked_orders:
            exchange_order_id = await tracked_order.get_exchange_order_id()
            try:
                order_update = await self.get_order_status(exchange_order_id, tracked_order.trading_pair)
            except OKExAPIError as e:
                err_code = e.error_payload.get("error").get("err-code")
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

            # Calculate the newly executed amount for this update.
            tracked_order.last_state = order_update["state"]
            new_confirmed_amount = Decimal(order_update["fillSz"])
            execute_amount_diff = new_confirmed_amount

            if execute_amount_diff > s_decimal_0:
                execute_price = Decimal(order_update["avgPx"])
                tracked_order.executed_amount_base = new_confirmed_amount
                tracked_order.executed_amount_quote = new_confirmed_amount * execute_price
                tracked_order.fee_paid = Decimal(order_update["fee"])

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

            if tracked_order.is_open:
                continue

            if tracked_order.is_done:
                if not tracked_order.is_cancelled:  # Handles "filled" order
                    self.c_stop_tracking_order(tracked_order.client_order_id)
                    if tracked_order.trade_type is TradeType.BUY:
                        self.logger().info(f"The market buy order {tracked_order.client_order_id} has completed "
                                           f"according to order status API.")
                        self.c_trigger_event(self.MARKET_BUY_ORDER_COMPLETED_EVENT_TAG,
                                             BuyOrderCompletedEvent(self._current_timestamp,
                                                                    tracked_order.client_order_id,
                                                                    tracked_order.base_asset,
                                                                    tracked_order.quote_asset,
                                                                    tracked_order.fee_asset or tracked_order.base_asset,
                                                                    tracked_order.executed_amount_base,
                                                                    tracked_order.executed_amount_quote,
                                                                    tracked_order.fee_paid,
                                                                    tracked_order.order_type))
                    else:
                        self.logger().info(f"The market sell order {tracked_order.client_order_id} has completed "
                                           f"according to order status API.")
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
                else:  # Handles "canceled" or "partial-canceled" order
                    self.c_stop_tracking_order(tracked_order.client_order_id)
                    self.logger().info(f"The market order {tracked_order.client_order_id} "
                                       f"has been cancelled according to order status API.")
                    self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                         OrderCancelledEvent(self._current_timestamp,
                                                             tracked_order.client_order_id))

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
            except Exception:
                self.logger().network("Unexpected error while fetching account updates.",
                                      exc_info=True,
                                      app_warning_msg="Could not fetch account updates from OKEx. "
                                                      "Check API key and network connection.")
                await asyncio.sleep(0.5)

    async def _trading_rules_polling_loop(self):
        while True:
            try:
                await self._update_trading_rules()
                await asyncio.sleep(60 * 5)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network("Unexpected error while fetching trading rules.",
                                      exc_info=True,
                                      app_warning_msg="Could not fetch new trading rules from OkEx. "
                                                      "Check network connection.")
                await asyncio.sleep(0.5)

    async def _iter_user_stream_queue(self) -> AsyncIterable[Dict[str, Any]]:
        while True:
            try:
                yield await self._user_stream_tracker.user_stream.get()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"Unknown error. Retrying after 1 second. {e}", exc_info=True)
                await asyncio.sleep(1.0)

    async def _user_stream_event_listener(self):
        async for stream_message in self._iter_user_stream_queue():
            try:
                args = stream_message.get("arg", None)
                if args:
                    channel = args.get("channel", None)
                if channel not in OKEX_WS_CHANNELS:
                    continue
                if "data" not in stream_message:
                    continue

                # stream_message["data"] is a list
                for data in stream_message["data"]:
                    if channel == OKEX_WS_CHANNEL_ACCOUNT:
                        details = data["details"]
                        if details:
                            details=details[0]
                            asset_name = details["ccy"]
                            balance = details["cashBal"]
                            available_balance = details["availBal"]

                            self._account_balances.update({asset_name: Decimal(balance)})
                            self._account_available_balances.update({asset_name: Decimal(available_balance)})
                        continue

                    elif channel == OKEX_WS_CHANNEL_ORDERS:
                        order_id = data["ordId"]
                        client_order_id = data["clOrdId"]
                        trading_pair = data["instId"]
                        order_status = data["state"]

                        if order_status not in ("canceled", "live", "partially_filled", "filled"):
                            self.logger().debug(f"Unrecognized order update response - {stream_message}")

                        tracked_order = self._in_flight_orders.get(client_order_id, None)

                        if tracked_order is None:
                            continue

                        execute_amount_diff = s_decimal_0
                        execute_amount_diff = Decimal(data["fillSz"])

                        if execute_amount_diff > s_decimal_0:
                            execute_price = Decimal(data["fillPx"])
                            order_type = data["ordType"]
                            tracked_order.executed_amount_base += execute_amount_diff
                            tracked_order.executed_amount_quote += Decimal(execute_amount_diff * execute_price)

                            current_fee = self.get_fee(tracked_order.base_asset,
                                                       tracked_order.quote_asset,
                                                       tracked_order.order_type,
                                                       tracked_order.trade_type,
                                                       execute_amount_diff,
                                                       execute_price)
                            self.logger().info(f"Filled {execute_amount_diff} out of {tracked_order.amount} of "
                                               f"{order_type.upper()} order {client_order_id}")
                            self.c_trigger_event(self.MARKET_ORDER_FILLED_EVENT_TAG,
                                                 OrderFilledEvent(self._current_timestamp,
                                                                  tracked_order.client_order_id,
                                                                  tracked_order.trading_pair,
                                                                  tracked_order.trade_type,
                                                                  tracked_order.order_type,
                                                                  execute_price,
                                                                  execute_amount_diff,
                                                                  current_fee,
                                                                  exchange_trade_id=order_id))

                        if order_status == "filled":
                            tracked_order.last_state = order_status
                            if tracked_order.trade_type is TradeType.BUY:
                                self.logger().info(f"The BUY {tracked_order.order_type} order {tracked_order.client_order_id} has completed "
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
                                self.logger().info(f"The SELL {tracked_order.order_type} order {tracked_order.client_order_id} has completed "
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

                        if order_status == "canceled":
                            tracked_order.last_state = order_status
                            self.logger().info(f"Order {tracked_order.client_order_id} has been cancelled "
                                               f"according to order delta websocket API.")
                            self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                                 OrderCancelledEvent(self._current_timestamp,
                                                                     tracked_order.client_order_id))
                            self.c_stop_tracking_order(tracked_order.client_order_id)

                    else:
                        # Ignore all other user stream message types
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
            "account_balance": len(self._account_balances) > 0 if self._trading_required else True,
            "trading_rule_initialized": len(self._trading_rules) > 0
        }

    def supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER]

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
        data = {
            'clOrdId': order_id,
            'tdMode': 'cash',
            'ordType': 'limit',
            'side': "buy" if is_buy else "sell",
            'instId': trading_pair,
            'sz': str(amount),
            'px': str(price)
        }

        exchange_order_id = await self._api_request(
            "POST",
            path_url=OKEX_PLACE_ORDER,
            params={},
            data=data,
            is_auth_required=True
        )
        return str(exchange_order_id['data'][0]['ordId'])

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

        decimal_amount = self.c_quantize_order_amount(trading_pair, amount)
        decimal_price = self.c_quantize_order_price(trading_pair, price)
        if decimal_amount < trading_rule.min_order_size:
            raise ValueError(f"Buy order amount {decimal_amount} is lower than the minimum order size "
                             f"{trading_rule.min_order_size}.")

        try:
            exchange_order_id = await self.place_order(order_id, trading_pair, decimal_amount, True, order_type, decimal_price)
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
                self.logger().info(f"Created {order_type.name.upper()} buy order {order_id} for {decimal_amount} {trading_pair}.")
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
        except Exception:
            self.c_stop_tracking_order(order_id)
            order_type_str = order_type.name.lower()

            self.logger().network(
                f"Error submitting buy {order_type_str} order to OKEx for "
                f"{decimal_amount} {trading_pair} "
                f"{decimal_price if order_type is OrderType.LIMIT else ''}."
                f"{decimal_price}.",
                exc_info=True,
                app_warning_msg="Failed to submit buy order to OKEx. Check API key and network connection."
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
            str order_id = f"{CLIENT_ID_PREFIX}{tracking_nonce}"  # OKEx doesn't permits special characters

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

        decimal_amount = self.quantize_order_amount(trading_pair, amount)
        decimal_price = self.c_quantize_order_price(trading_pair, price)

        if decimal_amount < trading_rule.min_order_size:
            raise ValueError(f"Sell order amount {decimal_amount} is lower than the minimum order size "
                             f"{trading_rule.min_order_size}.")

        try:
            exchange_order_id = await self.place_order(order_id, trading_pair, decimal_amount, False, order_type, decimal_price)
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
                self.logger().info(f"Created {order_type.name.upper()} sell order {order_id} for {decimal_amount} {trading_pair}.")
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
        except Exception:
            self.c_stop_tracking_order(order_id)
            order_type_str = order_type.name.lower()
            self.logger().network(
                f"Error submitting sell {order_type_str} order to OKEx for "
                f"{decimal_amount} {trading_pair} "
                f"{decimal_price if order_type is OrderType.LIMIT else ''}.",
                f"{decimal_price}.",
                exc_info=True,
                app_warning_msg=f"Failed to submit sell order to OKEx. Check API key and network connection."
            )
            self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                 MarketOrderFailureEvent(self._current_timestamp, order_id, order_type))

    cdef str c_sell(self,
                    str trading_pair,
                    object amount,
                    object order_type=OrderType.LIMIT, object price=s_decimal_0,
                    dict kwargs={}):
        cdef:
            int64_t tracking_nonce = <int64_t> get_tracking_nonce()
            str order_id = f"{CLIENT_ID_PREFIX}{tracking_nonce}"  # OKEx doesn't permits special characters

        safe_ensure_future(self.execute_sell(order_id, trading_pair, amount, order_type, price))
        return order_id

    async def execute_cancel(self, trading_pair: str, order_id: str):
        try:
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is None:
                raise ValueError(f"Failed to cancel order - {order_id}. Order not found.")

            params = {
                "clOrdId": order_id,
                "instId": trading_pair
            }
            response = await self._api_request("POST", path_url=OKEX_ORDER_CANCEL, data=params, is_auth_required=True)

            if not response['code']=='0':
                raise OKExAPIError("Order could not be canceled")

        except OKExAPIError as e:
            self.logger().network(
                f"Failed to cancel order {order_id} : {str(e)}",
                exc_info=True,
                app_warning_msg=f"Failed to cancel the order {order_id} on OKEx. "
                                f"Check API key and network connection."
            )
            self.logger().network(
                f"Failed to cancel order {order_id}: {str(e)}",
                exc_info=True,
                app_warning_msg=f"Failed to cancel the order {order_id} on OKEx. "
                                f"Check API key and network connection."
            )

        except Exception as e:
            self.logger().network(
                f"Failed to cancel order {order_id}: {str(e)}",
                exc_info=True,
                app_warning_msg=f"Failed to cancel the order {order_id} on OKEx. "
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
            # do nothing if there are not orders to cancel
            return []

        for trading_pair in orders_by_trading_pair:
            cancel_order_ids = [o.exchange_order_id for o in orders_by_trading_pair[trading_pair]]
            self.logger().debug(f"cancel_order_ids {cancel_order_ids} orders_by_trading_pair[trading_pair]")

            data = [{'ordId': cancel_order_id,
                    'instId': trading_pair} for cancel_order_id in cancel_order_ids]
            # TODO, check that only a max of 4 orders can be included per trading pair

            cancellation_results = []
            try:
                cancel_all_results = await self._api_request(
                    "POST",
                    path_url=OKEX_BATCH_ORDER_CANCEL,
                    data=data,
                    is_auth_required=True
                )

                for order_result in cancel_all_results['data']:
                    cancellation_results.append(CancellationResult(order_result["clOrdId"], order_result["sCode"]))
                    if order_result["sCode"]=='0':
                        self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                             OrderCancelledEvent(self._current_timestamp,
                                                                 order_result["clOrdId"],
                                                                 exchange_order_id=order_result["ordId"]))

            except Exception as e:
                self.logger().network(
                    f"Failed to cancel all orders: {cancel_order_ids}",
                    exc_info=True,
                    app_warning_msg=f"Failed to cancel all orders on OKEx. Check API key and network connection."
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
        self._in_flight_orders[client_order_id] = OkexInFlightOrder(
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

    cdef object c_get_order_size_quantum(self, str trading_pair, object order_size):
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]
        return Decimal(trading_rule.min_base_amount_increment)

    cdef object c_quantize_order_amount(self, str trading_pair, object amount, object price=s_decimal_0):
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]
            object quantized_amount = ExchangeBase.c_quantize_order_amount(self, trading_pair, amount)
            object current_price = self.c_get_price(trading_pair, False)
            object notional_size

        # Check against min_order_size. If not passing check, return 0.
        if quantized_amount < trading_rule.min_order_size:
            return s_decimal_0

        # Check against max_order_size. If not passing check, return maximum.
        if quantized_amount > trading_rule.max_order_size:
            return trading_rule.max_order_size

        if price == s_decimal_0:
            notional_size = current_price * quantized_amount
        else:
            notional_size = price * quantized_amount
        # Add 1% as a safety factor in case the prices changed while making the order.

        if notional_size < trading_rule.min_notional_size * Decimal("1.01"):
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
                price: Decimal = s_decimal_NaN,
                is_maker: Optional[bool] = None) -> AddedToCostTradeFee:
        return self.c_get_fee(base_currency, quote_currency, order_type, order_side, amount, price, is_maker)

    def get_order_book(self, trading_pair: str) -> OrderBook:
        return self.c_get_order_book(trading_pair)
