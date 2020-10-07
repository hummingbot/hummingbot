import aiohttp
from aiohttp.test_utils import TestClient
import asyncio
from async_timeout import timeout
import conf
from datetime import datetime
from decimal import Decimal
from libc.stdint cimport int64_t
import logging
import pandas as pd
import re
import time
from typing import (
    Any,
    AsyncIterable,
    Coroutine,
    Dict,
    List,
    Optional,
    Tuple
)
import ujson

import hummingbot
from hummingbot.core.clock cimport Clock
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.core.data_type.order_book_tracker import OrderBookTrackerDataSourceType
from hummingbot.core.data_type.transaction_tracker import TransactionTracker
from hummingbot.core.event.events import (
    MarketEvent,
    MarketWithdrawAssetEvent,
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
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.okex.okex_api_order_book_data_source import OkexAPIOrderBookDataSource
from hummingbot.connector.exchange.okex.okex_auth import OKExAuth
from hummingbot.connector.exchange.okex.okex_in_flight_order import OKExInFlightOrder
from hummingbot.connector.exchange.okex.okex_order_book_tracker import OKExOrderBookTracker
from hummingbot.market.trading_rule cimport TradingRule
from hummingbot.connector.exchange_base import (
    ExchangeBase,
    NaN,
    s_decimal_NaN)
from hummingbot.connector.exchange.okex.okex_user_stream_tracker import OKExUserStreamTracker
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce
from hummingbot.client.config.fee_overrides_config_map import fee_overrides_config_map
from hummingbot.core.utils.estimate_fee import estimate_fee

from hummingbot.connector.exchange.okex.constants import *


hm_logger = None
s_decimal_0 = Decimal(0)
TRADING_PAIR_SPLITTER = "-"


class OKExAPIError(IOError):
    def __init__(self, error_payload: Dict[str, Any]):
        super().__init__(str(error_payload))
        self.error_payload = error_payload


cdef class OKExExchangeTransactionTracker(TransactionTracker):
    cdef:
        OKExExchange _owner

    def __init__(self, owner: OKExExchange):
        super().__init__()
        self._owner = owner

    cdef c_did_timeout_tx(self, str tx_id):
        TransactionTracker.c_did_timeout_tx(self, tx_id)
        self._owner.c_did_timeout_tx(tx_id)


cdef class OKExExchange(ExchangeBase):
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
        self._order_book_tracker = OKExOrderBookTracker(
            trading_pairs=trading_pairs
        )
        self._poll_notifier = asyncio.Event()
        self._poll_interval = poll_interval
        self._shared_client = None
        self._status_polling_task = None
        self._trading_required = trading_required
        self._trading_rules = {}
        self._trading_rules_polling_task = None
        self._tx_tracker = OKExExchangeTransactionTracker(self)

        self._user_stream_event_listener_task = None
        self._user_stream_tracker = OKExUserStreamTracker(okex_auth=self._okex_auth,
                                                          trading_pairs=trading_pairs)

    # @staticmethod
    # def split_trading_pair(trading_pair: str) -> Optional[Tuple[str, str]]:
    #     print("trading_pair is", trading_pair)
    #     return trading_pair.split(TRADING_PAIR_SPLITTER)

    # OKEx uses format BTC-USDT
    @staticmethod
    def convert_from_exchange_trading_pair(trading_pair: str) -> Optional[str]:
        return trading_pair

    @staticmethod
    def convert_to_exchange_trading_pair(trading_pair: str) -> str:
        return hokex_trading_pair

    @property
    def name(self) -> str:
        return "okex"

    @property
    def order_book_tracker(self) -> OKExOrderBookTracker:
        return self._order_book_tracker

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        return self._order_book_tracker.order_books

    @property
    def trading_rules(self) -> Dict[str, TradingRule]:
        return self._trading_rules

    @property
    def in_flight_orders(self) -> Dict[str, OKExInFlightOrder]:
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
            key: OKExInFlightOrder.from_json(value)
            for key, value in saved_states.items()
        })

    @property
    def shared_client(self) -> str:
        return self._shared_client

    @shared_client.setter
    def shared_client(self, client: aiohttp.ClientSession):
        self._shared_client = client

    async def get_active_exchange_markets(self) -> pd.DataFrame:
        return await OkexAPIOrderBookDataSource.get_active_exchange_markets()

    cdef c_start(self, Clock clock, double timestamp):
        print("started")
        self._tx_tracker.c_start(clock, timestamp)
        ExchangeBase.c_start(self, clock, timestamp)

    cdef c_stop(self, Clock clock):
        ExchangeBase.c_stop(self, clock)
        self._async_scheduler.stop()

    async def start_network(self):
        print("NETWORK STARTED!")
        self._stop_network()
        self._order_book_tracker.start()
        self._trading_rules_polling_task = safe_ensure_future(self._trading_rules_polling_loop())
        self._user_stream_event_listener_task = safe_ensure_future(self._user_stream_event_listener())

        if self._trading_required:
            # await self._update_account_id() # Couldn't find this on OKEx Docs
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())

    def _stop_network(self):
        self._order_book_tracker.stop()
        if self._status_polling_task is not None:
            self._status_polling_task.cancel()
            self._status_polling_task = None
        if self._trading_rules_polling_task is not None:
            self._trading_rules_polling_task.cancel()
            self._trading_rules_polling_task = None
        if self._user_stream_event_listener_task is not None:
            self._user_stream_event_listener_task.cancel()
            self._user_stream_event_listener_task = None

    async def stop_network(self):
        self._stop_network()

    async def check_network(self) -> NetworkStatus:
        try:
            await self._api_request(method="get", path_url=OKEX_SERVER_TIME)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    cdef c_tick(self, double timestamp):
        cdef:
            int64_t last_tick = <int64_t>(self._last_timestamp / self._poll_interval)
            int64_t current_tick = <int64_t>(timestamp / self._poll_interval)

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
                           method,
                           path_url,
                           params: Optional[Dict[str, Any]] = {},
                           data={},
                           is_auth_required: bool = False) -> Dict[str, Any]:

        content_type = "application/json"  # if method.lower() == "post" else "application/x-www-form-urlencoded"
        headers = {"Content-Type": content_type}

        url = urljoin(OKEX_BASE_URL, path_url)

        client = await self._http_client()
        text_data = ujson.dumps(data)

        if is_auth_required:
            headers.update(self._okex_auth.add_auth_to_params(method, '/' + path_url, text_data))

        # aiohttp TestClient requires path instead of url
        if isinstance(client, TestClient):
            response_coro = client.request(
                method=method.upper(),
                path=f"{path_url}",
                headers=headers,
                params=params,
                data=text_data,
                timeout=100
            )
        else:
            response_coro = client.request(
                method=method.upper(),
                url=url,
                headers=headers,
                params=params if params else None,  # FIX THIS
                data=text_data,  # FIX THIS
                timeout=100
            )

        async with response_coro as response:
            if response.status != 200:
                raise IOError(f"Error fetching data from {url}. HTTP status is {response.status}.")
            try:
                parsed_response = await response.json()
                return parsed_response
            except Exception:
                raise IOError(f"Error parsing data from {url}.")

    # Couldn't find this on OKEx Docs
    # async def _update_account_id(self) -> str:
    #     accounts = await self._api_request("get", path_url="/account/accounts", is_auth_required=True)
    #     try:
    #         for account in accounts:
    #             if account["state"] == "working" and account["type"] == "spot":
    #                 self._account_id = str(account["id"])
    #     except Exception as e:
    #         raise ValueError(f"Unable to retrieve account id: {e}")

    async def _update_balances(self):
        cdef:
            str path_url = OKEX_BALANCE_URL
            # list data
            list balances
            dict new_available_balances = {}
            dict new_balances = {}
            str asset_name
            object balance

        balances = await self._api_request("GET", path_url=path_url, is_auth_required=True)

        self._account_available_balances.clear()
        self._account_balances.clear()

        for balance in balances:
            self._account_balances['currency'] = Decimal(balance['balance'])
            self._account_available_balances['currency'] = Decimal(balance['available'])

    cdef object c_get_fee(self,
                          str base_currency,
                          str quote_currency,
                          object order_type,
                          object order_side,
                          object amount,
                          object price):
        """
        """
        # https://www.okex.com/fees.html
        # TODO - use API endpoint: GET/api/spot/v3/trade_fee
        is_maker = order_type is OrderType.LIMIT_MAKER
        return estimate_fee("okex", is_maker)

    async def _update_trading_rules(self):
        cdef:
            # The poll interval for trade rules is 60 seconds.
            int64_t last_tick = <int64_t>(self._last_timestamp / 60.0)
            int64_t current_tick = <int64_t>(self._current_timestamp / 60.0)
        if current_tick > last_tick or len(self._trading_rules) < 1:
            exchange_info = await self._api_request("GET", path_url=OKEX_INSTRUMENTS_URL)
            trading_rules_list = self._format_trading_rules(exchange_info)
            self._trading_rules.clear()
            for trading_rule in trading_rules_list:
                self._trading_rules[trading_rule.trading_pair] = trading_rule

    def _format_trading_rules(self, raw_trading_pair_info: List[Dict[str, Any]]) -> List[TradingRule]:
        cdef:
            list trading_rules = []

        for info in raw_trading_pair_info:
            try:
                trading_rules.append(
                    TradingRule(trading_pair=info["instrument_id"],
                                min_order_size=Decimal(info["min_size"]),
                                # max_order_size=Decimal(info["max-order-amt"]), # It's 100,000 USDT, How to model that?
                                min_price_increment=Decimal(info["tick_size"]),
                                min_base_amount_increment=Decimal(info["size_increment"]),
                                # min_quote_amount_increment=Decimal(info["1e-{info['value-precision']}"]),
                                # min_notional_size=Decimal(info["min-order-value"])
                                min_notional_size=s_decimal_0  # Couldn't find a value for this in the docs
                                )
                )
            except Exception:
                self.logger().error(f"Error parsing the trading pair rule {info}. Skipping.", exc_info=True)
        return trading_rules

    async def get_order_status(self, exchange_order_id: str) -> Dict[str, Any]:
        """
        Example:
        {
            "client_oid":"oktspot70",
            "created_at":"2019-03-15T02:52:56.000Z",
            "filled_notional":"3.8886",
            "filled_size":"0.001",
            "funds":"",
            "instrument_id":"ETH-USDT",
            "notional":"",
            "order_id":"2482659399697408",
            "order_type":"0",
            "price":"3927.3",
            "price_avg":"3927.3",
            "product_id":"ETH-USDT",
            "side":"buy",
            "size":"0.001",
            "status":"filled",
            "fee_currency":"BTC",
            "fee":"-0.01",
            "rebate_currency":"open",
            "rebate":"0.05",
            "state":"2",
            "timestamp":"2019-03-15T02:52:56.000Z",
            "type":"limit"
        }
        """
        path_url = '/' + OKEX_ORDER_DETAILS_URL.format(exchange_order_id=exchange_order_id)
        return await self._api_request("get", path_url=path_url, is_auth_required=True)

    async def _update_order_status(self):
        cdef:
            # The poll interval for order status is 10 seconds.
            int64_t last_tick = <int64_t>(self._last_poll_timestamp / self.UPDATE_ORDERS_INTERVAL)
            int64_t current_tick = <int64_t>(self._current_timestamp / self.UPDATE_ORDERS_INTERVAL)

        tracked_orders = list(self._in_flight_orders.values())
        for tracked_order in tracked_orders:
            exchange_order_id = await tracked_order.get_exchange_order_id()
            try:
                order_update = await self.get_order_status(exchange_order_id)
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
                    f"{order_update}.",
                    app_warning_msg=f"Could not fetch updates for the order {tracked_order.client_order_id}. "
                                    f"The order has either been filled or canceled."
                )
                continue

            # order_state = order_update
            # possible order states are "submitted", "partial-filled", "filled", "canceled"

            # if order_state not in ["submitted", "filled", "canceled"]:
            #     self.logger().debug(f"Unrecognized order update response - {order_update}")

            # Calculate the newly executed amount for this update.
            print("last_state is", order_update["state"])
            tracked_order.last_state = order_update["state"]
            new_confirmed_amount = Decimal(order_update["filled_size"])  # TODO filled_notional or filled_size?
            execute_amount_diff = new_confirmed_amount - tracked_order.executed_amount_base

            if execute_amount_diff > s_decimal_0:
                tracked_order.executed_amount_base = new_confirmed_amount
                tracked_order.executed_amount_quote = Decimal(order_update["filled_notional"])  # TODO filled_notional or filled_size?

                tracked_order.fee_paid = Decimal(order_update["fee"])
                execute_price = tracked_order.executed_amount_quote / new_confirmed_amount

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
                    # TODO check this for OKEx
                    # Unique exchange trade ID not available in client order status
                    # But can use validate an order using exchange order ID:
                    # https://huobiapi.github.io/docs/spot/v1/en/#query-order-by-order-id
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
                channel = stream_message.get("table", None)

                if channel not in OKEX_WS_CHANNELS:
                    continue

                # stream_message["data"] is a list
                for data in stream_message["data"]:
                    if channel == OKEX_WS_CHANNEL_SPOT_ACCOUNT:
                        asset_name = data["currency"]
                        balance = data["balance"]
                        available_balance = data["available"]

                        self._account_balances.update({asset_name: Decimal(balance)})
                        self._account_available_balances.update({asset_name: Decimal(available_balance)})
                        continue

                    elif channel == OKEX_WS_CHANNEL_SPOT_ORDER:
                        order_id = data["order_id"]
                        client_order_id = data["client_oid"]
                        trading_pair = data["instrument_id"]
                        order_status = data["state"]

                        if order_status not in ("-2", "-1", "0", "1", "2", "3", "4"):
                            self.logger().debug(f"Unrecognized order update response - {stream_message}")

                        tracked_order = self._in_flight_orders.get(client_order_id, None)

                        if tracked_order is None:
                            continue

                        execute_amount_diff = s_decimal_0
                        execute_price = Decimal(data["price"])
                        remaining_amount = Decimal(data["filled_size"])
                        order_type = data["type"]

                        new_confirmed_amount = Decimal(tracked_order.amount - remaining_amount)

                        execute_amount_diff = Decimal(new_confirmed_amount - tracked_order.executed_amount_base)
                        tracked_order.executed_amount_base = new_confirmed_amount
                        tracked_order.executed_amount_quote += Decimal(execute_amount_diff * execute_price)

                        if execute_amount_diff > s_decimal_0:
                            self.logger().info(f"Filed {execute_amount_diff} out of {tracked_order.amount} of order "
                                               f"{order_type.upper()}-{client_order_id}")
                            self.c_trigger_event(self.MARKET_ORDER_FILLED_EVENT_TAG,
                                                 OrderFilledEvent(self._current_timestamp,
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
                                                                  exchange_trade_id=order_id))

                        if order_status == "1":
                            tracked_order.last_state = order_status
                            if tracked_order.trade_type is TradeType.BUY:
                                self.logger().info(f"The LIMIT_BUY order {tracked_order.client_order_id} has completed "
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
                                self.logger().info(f"The LIMIT_SELL order {tracked_order.client_order_id} has completed "
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

                        if order_status == "-1":
                            tracked_order.last_state = order_status
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
            # "account_id_initialized": self._account_id != "" if self._trading_required else True, # Couldn't find this on OKEx Docs
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

        # order_type_str = "limit" if order_type is OrderType.LIMIT else "market"

        params = {
            'client_oid': order_id,
            'type': 'limit' if OrderType.LIMIT else 'market',  # what happens with OrderType.LIMIT_MAKER?
            'side': "buy" if is_buy else "sell",
            'instrument_id': trading_pair,
            'order_type': 0,  # TODO double check this
            # order_type, from OKEx docs:
            # Specify 0: Normal order (Unfilled and 0 imply normal limit order) 1: Post only 2: Fill or Kill 3: Immediate Or Cancel,
            'size': amount

        }

        if order_type != OrderType.MARKET:
            params["price"] = f"{price:f}"

        exchange_order_id = await self._api_request(
            "POST",
            path_url=OKEX_PLACE_ORDER,
            params={},
            data=params,
            is_auth_required=True
        )
        return str(exchange_order_id)

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

        if order_type is OrderType.LIMIT or order_type is OrderType.LIMIT_MAKER:
            quote_amount = self.c_get_quote_volume_for_base_amount(trading_pair, True, amount).result_volume
            # Quantize according to price rules, not base token amount rules.
            decimal_amount = self.c_quantize_order_price(trading_pair, Decimal(quote_amount))
            decimal_price = s_decimal_0
        else:
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
                self.logger().info(f"Created {order_type} buy order {order_id} for {decimal_amount} {trading_pair}.")
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
                f"{decimal_price if order_type is OrderType.LIMIT else ''}.",
                f"{decimal_price}.",
                exc_info=True,
                app_warning_msg=f"Failed to submit buy order to OKEx. Check API key and network connection."
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
            str order_id = f"buy-{trading_pair}-{tracking_nonce}"

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
                self.logger().info(f"Created {order_type} sell order {order_id} for {decimal_amount} {trading_pair}.")
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
            str order_id = f"sell-{trading_pair}-{tracking_nonce}"
        safe_ensure_future(self.execute_sell(order_id, trading_pair, amount, order_type, price))
        return order_id

    async def execute_cancel(self, trading_pair: str, order_id: str):
        try:
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is None:
                raise ValueError(f"Failed to cancel order - {order_id}. Order not found.")

            path_url = '/' + OKEX_ORDER_CANCEL.format(exchange_order_id=order_id)
            response = await self._api_request("post", path_url=path_url, is_auth_required=True)

            if not response['result']:
                raise OKExAPIError("Order could not be canceled")

        except OKExAPIError as e:
            self.logger().network(
                f"Failed to cancel order {order_id}: {str(e)}",
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
            if order.is_open:
                orders_by_trading_pair[order.trading_pair] = orders_by_trading_pair.get(order.trading_pair, [])
                orders_by_trading_pair[order.trading_pair].append(order)

        if len(orders_by_trading_pair) == 0:
            # do nothing if there are not orders to cancel
            return []

        # open_orders[0].trad

        for trading_pair in orders_by_trading_pair:

            cancel_order_ids = [o.exchange_order_id for o in orders_by_trading_pair[trading_pair]]

            self.logger().debug(f"cancel_order_ids {cancel_order_ids} orders_by_trading_pair[trading_pair]")

            # TODO order_ids or client_oids?
            data = {'client_oids': cancel_order_ids,
                    'instrument_id': trading_pair
                    }

            # TODO, check that only a max of 4 orders can be included per trading pair

            cancellation_results = []
            try:
                cancel_all_results = await self._api_request(
                    "post",
                    path_url='/' + OKEX_BATCH_ORDER_CANCELL,
                    data=data,
                    is_auth_required=True
                )

                for trading_pair in cancel_all_results:
                    for order in cancel_all_results[trading_pair]:
                        cancellation_results.append(CancellationResult(order, order['result']))

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
        self._in_flight_orders[client_order_id] = OKExInFlightOrder(
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
