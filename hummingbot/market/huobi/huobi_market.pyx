from collections import defaultdict

import aiohttp
from aiokafka import (
    AIOKafkaConsumer,
    ConsumerRecord
)
import asyncio
from async_timeout import timeout
from decimal import Decimal
from functools import partial
import math
import logging
import pandas as pd
import re
import time
from typing import (
    Any,
    Dict,
    List,
    AsyncIterable,
    Optional,
    Coroutine,
    Tuple,
)

from libc.stdint cimport int64_t

import conf
import hummingbot
from hummingbot.core.utils.async_call_scheduler import AsyncCallScheduler
from hummingbot.core.clock cimport Clock
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.market.huobi.huobi_api_order_book_data_source import HuobiAPIOrderBookDataSource
from hummingbot.logger import HummingbotLogger
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
from hummingbot.market.market_base import (
    MarketBase,
    NaN
)
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.data_type.order_book_tracker import OrderBookTrackerDataSourceType
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.market.huobi.huobi_auth import HuobiAuth
from hummingbot.market.huobi.huobi_order_book_tracker import HuobiOrderBookTracker
from hummingbot.market.huobi.huobi_user_stream_tracker import HuobiUserStreamTracker
from hummingbot.market.huobi.huobi_in_flight_order import HuobiInFlightOrder
from hummingbot.market.deposit_info import DepositInfo
from hummingbot.core.data_type.user_stream_tracker import UserStreamTrackerDataSourceType
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.transaction_tracker import TransactionTracker
from hummingbot.market.trading_rule cimport TradingRule

s_logger = None
s_decimal_0 = Decimal(0)
SYMBOL_SPLITTER = re.compile(r"^(\w+)(BTC|ETH|BNB|XRP|USDT|USDC|USDS|TUSD|PAX)$")
HUOBI_ROOT_API = "https://api.huobi.pro"
HUOBI_ACCOUNT_ID = "/v1/account/accounts"
HUOBI_SYMBOLS_INFO = "/v1/common/symbols"


cdef class HuobiMarketTransactionTracker(TransactionTracker):
    cdef:
        HuobiMarket _owners

    def __init__(self, owner: HuobiMarket):
        super().__init__()
        self._owner = owner

    cdef c_did_timeout_tx(self, str tx_id):
        TransactionTracker.c_did_timeout_tx(self, tx_id)
        self._owner.c_did_timeout_tx(tx_id)


cdef class InFlightDeposit:
    cdef:
        public str tracking_id
        public int64_t timestamp_ms
        public str tx_hash
        public str from_address
        public str to_address
        public bint has_tx_receipt

    def __init__(self, tracking_id: str, timestamp_ms: int, tx_hash: str, from_address: str, to_address: str):
        self.tracking_id = tracking_id
        self.timestamp_ms = timestamp_ms
        self.tx_hash = tx_hash
        self.from_address = from_address
        self.to_address = to_address
        self.has_tx_receipt = False

    def __repr__(self) -> str:
        return f"InFlightDeposit(tracking_id='{self.tracking_id}', timestamp_ms={self.timestamp_ms}, " \
        f"tx_hash='{self.tx_hash}', has_tx_receipt={self.has_tx_receipt})"


cdef class WithdrawRule:
    cdef:
        public str asset_name
        public double min_withdraw_amount
        public double withdraw_fee

    def __init__(self, asset_name: str, min_withdraw_amount: float, withdraw_fee: float):
        self.asset_name = asset_name
        self.min_withdraw_amount = min_withdraw_amount
        self.withdraw_fee = withdraw_fee

    def __repr__(self) -> str:
        return f"WithdrawRule(asset_name='{self.asset_name}', min_withdraw_amount={self.min_withdraw_amount}, " \
               f"withdraw_fee={self.withdraw_fee})"


cdef class HuobiMarket(MarketBase):
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

    DEPOSIT_TIMEOUT = 1800.0
    API_CALL_TIMEOUT = 10.0
    HUOBI_API_ENDPOINT = "https://api.huobi.pro/v1/order/"

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(__name__)
        return s_logger

    def __init__(self,
                 huobi_api_key: str,
                 huobi_secret_key: str,
                 poll_interval: float = 5.0,
                 order_book_tracker_data_source_type: OrderBookTrackerDataSourceType =
                    OrderBookTrackerDataSourceType.EXCHANGE_API,
                 user_stream_tracker_data_source_type: UserStreamTrackerDataSourceType =
                    UserStreamTrackerDataSourceType.EXCHANGE_API,
                 symbols: Optional[List[str]] = None,
                 trading_required: bool = True):

        super().__init__()
        self._trading_required = trading_required
        self._huobi_auth = HuobiAuth(huobi_api_key, huobi_secret_key)
        self._order_book_tracker = HuobiOrderBookTracker(data_source_type=order_book_tracker_data_source_type,
                                                           symbols=symbols)
        self._user_stream_tracker = HuobiUserStreamTracker(huobi_auth=self._huobi_auth,
            data_source_type=user_stream_tracker_data_source_type)

        self._account_balances = {}
        self._account_available_balances = {}
        self._ev_loop = asyncio.get_event_loop()
        self._poll_notifier = asyncio.Event()
        self._last_timestamp = 0
        self._poll_interval = poll_interval
        self._in_flight_orders = {}
        self._tx_tracker = HuobiMarketTransactionTracker(self)
        self._trading_rules = {}
        self._data_source_type = order_book_tracker_data_source_type
        self._status_polling_task = None
        self._user_stream_tracker_task = None
        self._user_stream_event_listener_task = None
        self._order_tracker_task = None
        self._trading_rules_polling_task = None
        self._async_scheduler = AsyncCallScheduler(call_interval=0.5)
        self._last_pull_timestamp = 0

    @staticmethod
    def split_symbol(symbol: str) -> Tuple[str, str]:
        try:
            m = SYMBOL_SPLITTER.match(symbol)
            return m.group(1), m.group(2)
        except Exception as e:
            raise ValueError(f"Error parsing symbol {symbol}: {str(e)}")

    @property
    def name(self) -> str:
        return "huobi"

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        return self._order_book_tracker.order_books

    @property
    def withdraw_rules(self) -> Dict[str, WithdrawRule]:
        return self._withdraw_rules

    @property
    def trading_rules(self) -> Dict[str, TradingRule]:
        return self._trading_rules

    @property
    def in_flight_orders(self) -> Dict[str, HuobiInFlightOrder]:
        return self._in_flight_orders

    @property
    def limit_orders(self) -> List[LimitOrder]:
        return [
            in_flight_order.to_limit_order()
            for in_flight_order in self._in_flight_orders.values()
        ]

    @property
    def tracking_states(self) -> Dict[str, any]:
        return {
            key: value.to_json()
            for key, value in self._in_flight_orders.items()
        }

    def restore_tracking_states(self, saved_states: Dict[str, any]):
        self._in_flight_orders.update({
            key: HuobiInFlightOrder.from_json(value)
            for key, value in saved_states.items()
        })

    async def get_active_exchange_markets(self) -> pd.DataFrame:
        return await HuobiAPIOrderBookDataSource.get_active_exchange_markets()

    cdef c_start(self, Clock clock, double timestamp):
        self._tx_tracker.c_start(clock, timestamp)
        MarketBase.c_start(self, clock, timestamp)

    cdef c_stop(self, Clock clock):
        MarketBase.c_stop(self, clock)
        self._async_scheduler.stop()

    async def start_network(self):
        if self._order_tracker_task is not None:
            self._stop_network()

        self._order_tracker_task = asyncio.ensure_future(self._order_book_tracker.start())
        if self._trading_required:
            self._status_polling_task = asyncio.ensure_future(self._status_polling_loop())
            self._trading_rules_polling_task = asyncio.ensure_future(self._trading_rules_polling_loop())
            self._user_stream_tracker_task = asyncio.ensure_future(self._user_stream_tracker.start())
            self._user_stream_event_listener_task = asyncio.ensure_future(self._user_stream_event_listener())

    def _stop_network(self):
        if self._order_tracker_task is not None:
            self._order_tracker_task.cancel()
        if self._status_polling_task is not None:
            self._status_polling_task.cancel()
        if self._user_stream_tracker_task is not None:
            self._user_stream_tracker_task.cancel()
        if self._user_stream_event_listener_task is not None:
            self._user_stream_event_listener_task.cancel()
        if self._trading_rules_polling_task is not None:
            self._trading_rules_polling_task.cancel()
        self._order_tracker_task = self._status_polling_task = self._user_stream_tracker_task = \
            self._user_stream_event_listener_task = None

    async def stop_network(self):
        self._stop_network()

    async def check_network(self) -> NetworkStatus:
        try:
            await self.query_url(HUOBI_ROOT_API + "/v1/common/timestamp", new Dict[str, any])
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    cdef c_tick(self, double timestamp):
        cdef:
            int64_t last_tick = <int64_t>(self._last_timestamp / self._poll_interval)
            int64_t current_tick = <int64_t>(timestamp / self._poll_interval)
        MarketBase.c_tick(self, timestamp)
        self._tx_tracker.c_tick(timestamp)
        if current_tick > last_tick:
            if not self._poll_notifier.is_set():
                self._poll_notifier.set()
        self._last_timestamp = timestamp

    async def _http_client(self) -> aiohttp.ClientSession:
        if self._shared_client is None:
            self._shared_client = aiohttp.ClientSession()
        return self._shared_client

    async def query_auth_url(self, method, root_url, path_url, body: Dict[str, any]) -> Dict[str, any]:
        params = self._huobi_auth(method, root_url, path_url, body)
        client = await self._http_client()
        async with client.request(method,
                                  url=root_url + path_url, params=params, timeout=self.API_CALL_TIMEOUT) as response:
                if response.status != 200:
                    raise IOError(f"Error fetching data from {root_url + path_url}. HTTP status is {response.status}.")
                data = await response.json()
                return data

    async def query_url(self, method, url, params: Dict[str, any]) -> Dict[str, any]:
        client = await self._http_client()
        async with client.get(url=url, params=params, timeout=self.API_CALL_TIMEOUT) as response:
                if response.status != 200:
                    raise IOError(f"Error fetching data from {url}. HTTP status is {response.status}.")
                data = await response.json()
                return data

    async def get_account_id(self) -> int:
        account_info = await self.query_auth_url("get", HUOBI_ROOT_API, HUOBI_ACCOUNT_ID, new Dict[str, any])
        return account_info["id"]

    async def _update_balances(self):
        cdef:
            dict account_info
            list balances
            str asset_name
            set local_asset_names = set(self._account_balances.keys())
            set remote_asset_names = set()
            set asset_names_to_remove

        account_id = self._get_account_id()
        path_url = HUOBI_ACCOUNT_ID + f"/{account_id}/balance",
        account_info = await self.query_auth_url("get", HUOBI_ROOT_API, path_url, new Dict[str, any])

        balances = account_info["list"]
        for balance_entry in balances:
            asset_name = balance_entry["currency"]
            if balance_entry["type"] == "trade":
                free_balance = Decimal(balance_entry["balance"])
                self._account_available_balances[asset_name] = free_balance
            else:
                total_balance = Decimal(balance_entry["balance"]) + self._account_available_balances[asset_name]
                self._account_balances[asset_name] = total_balance
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    cdef object c_get_fee(self,
                          str base_currency,
                          str quote_currency,
                          object order_type,
                          object order_side,
                          double amount,
                          double price):
        # Should update to connect to Huobi fees API
        # Fee info from https://www.hbg.com/en-us/about/fee/
        cdef:
            double trade_fee = 0.002

        return TradeFee(percent=trade_fee)

    async def _update_trading_rules(self):
        cdef:
            # The poll interval for trade rules is 60 seconds.
            int64_t last_tick = <int64_t>(self._last_timestamp / 60.0)
            int64_t current_tick = <int64_t>(self._current_timestamp / 60.0)
        if current_tick > last_tick or len(self._trading_rules) < 1:
            exchange_info = await self.query_url("get", HUOBI_ROOT_API + HUOBI_SYMBOLS_INFO, new Dict[str, any])
            trading_rules_list = self._format_trading_rules(exchange_info["data"])
            self._trading_rules.clear()
            for trading_rule in trading_rules_list:
                self._trading_rules[trading_rule.symbol] = trading_rule

    def _format_trading_rules(self, raw_symbol_info: List[Dict[str, Any]]) -> List[TradingRule]:
        cdef:
            list retval = []
            double price_min = 0.000000000000001
            double price_increment
            double base_min = 0.000000000000001
            double base_increment

        for rule in raw_symbol_info:
            try:
                symbol = rule["symbol"]
                min_order_size = rule["min-order-amt"]
                max_order_size = rule["max-order-amt"]
                price_min = 0.000000000000001
                price_increment = (math.ceil(price_min * (10**rule["price-precision"]))) / (10**rule["price-precision"])
                base_min = 0.000000000000001
                base_increment = (math.ceil(price_min * (10**rule["amount-precision"]))) / (10**rule["amount-precision"])

                retval.append(
                    TradingRule(symbol,
                                min_order_size=min_order_size,
                                max_order_size=max_order_size,
                                min_price_increment=price_increment,
                                min_base_amount_increment=base_increment))

            except Exception:
                self.logger().error(f"Error parsing the symbol rule {rule}. Skipping.", exc_info=True)
        return retval

    async def _update_order_fills_from_trades(self):
        cdef:
            # This is intended to be a backup measure to get filled events with trade ID for orders,
            # in case Huobi's user stream events are not working.
            # This is separated from _update_order_status which only updates the order status without producing filled
            # events, since Huobi's get order endpoint does not return trade IDs.
            # The poll interval for order status is 10 seconds.
            int64_t last_tick = <int64_t>(self._last_pull_timestamp / 10.0)
            int64_t current_tick = <int64_t>(self._current_timestamp / 10.0)

        if current_tick > last_tick and len(self._in_flight_orders) > 0:
            trading_pairs_to_order_map = defaultdict(lambda: {})
            for o in self._in_flight_orders.values():
                trading_pairs_to_order_map[o.symbol][o.exchange_order_id] = o

            trading_pairs = list(trading_pairs_to_order_map.keys())
            tasks = [self.query_api(self._huobi_client.get_my_trades, symbol=trading_pair)
                     for trading_pair in trading_pairs]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for trades, trading_pair in zip(results, trading_pairs):
                order_map = trading_pairs_to_order_map[trading_pair]
                if isinstance(trades, Exception):
                    self.logger().network(
                        f"Error fetching trades update for the order {trading_pair}: {trades}.",
                        app_warning_msg=f"Failed to fetch trade update for {trading_pair}."
                    )
                    continue
                for trade in trades:
                    order_id = str(trade["orderId"])
                    if order_id in order_map:
                        tracked_order = order_map[order_id]
                        order_type = OrderType.LIMIT if trade["isMaker"] else OrderType.MARKET
                        applied_trade = order_map[order_id].update_with_trade_update(trade)
                        if applied_trade:
                            self.c_trigger_event(self.MARKET_ORDER_FILLED_EVENT_TAG,
                                                 OrderFilledEvent(
                                                    self._current_timestamp,
                                                    tracked_order.client_order_id,
                                                    tracked_order.symbol,
                                                    tracked_order.trade_type,
                                                    order_type,
                                                    float(trade["price"]),
                                                    float(trade["qty"]),
                                                    self.c_get_fee(
                                                        tracked_order.base_asset,
                                                        tracked_order.quote_asset,
                                                        order_type,
                                                        tracked_order.trade_type,
                                                        float(trade["price"]),
                                                        float(trade["qty"])),
                                                    exchange_trade_id=trade["id"]
                                                 ))

    async def list_orders(self, symbol_set) -> List[Any]:
        cdef:
            list result

        path_url = "/v1/order/openOrders"
        account_id = self._get_account_id()
        for symbol in symbol_set:
            params = {
                "account-id": account_id,
                "symbol": symbol
            }
            order_info = await self._query_auth_url("get", HUOBI_ROOT_API, path_url=path_url, params)
            for item in order_info["data"]:
                result.add(item)
        return result

    async def _update_order_status(self):
        cdef:
            # The poll interval for order status is 10 seconds.
            int64_t last_tick = <int64_t>(self._last_pull_timestamp / 10.0)
            int64_t current_tick = <int64_t>(self._current_timestamp / 10.0)
            set symbol_set

        if current_tick > last_tick and len(self._in_flight_orders) > 0:
            tracked_orders = list(self._in_flight_orders.values())
            for order in tracked_orders:
                symbol_set.add(order.symbol)
            results = self._list_orders(symbol_set)
            order_dict = dict((result["id"], result) for result in results)

            for tracked_order in tracked_orders:
                exchange_order_id = await tracked_order.get_exchange_order_id()
                order_update = order_dict.get(exchange_order_id)
                if order_update is None:
                    self.logger().network(
                        f"Error fetching status update for the order {tracked_order.client_order_id}: "
                        f"{order_update}.",
                        app_warning_msg=f"Could not fetch updates for the order {tracked_order.client_order_id}. "
                                        f"Check API key and network connection."
                    )
                    continue

            done_reason = order_update.get("done_reason")
            # Calculate the newly executed amount for this update.
            new_confirmed_amount = Decimal(order_update["filled_size"])
            execute_amount_diff = new_confirmed_amount - tracked_order.executed_amount_base
            execute_price = s_decimal_0 if new_confirmed_amount == s_decimal_0 \
                            else Decimal(order_update["executed_value"]) / new_confirmed_amount

            client_order_id = tracked_order.client_order_id
            order_type_description = tracked_order.order_type_description
            order_type = OrderType.MARKET if tracked_order.order_type == OrderType.MARKET else OrderType.LIMIT
            # Emit event if executed amount is greater than 0.
            if execute_amount_diff > s_decimal_0:
                order_filled_event = OrderFilledEvent(
                    self._current_timestamp,
                    tracked_order.client_order_id,
                    tracked_order.symbol,
                    tracked_order.trade_type,
                    order_type,
                    float(execute_price),
                    float(execute_amount_diff),
                    self.c_get_fee(
                          tracked_order.base_asset,
                          tracked_order.quote_asset,
                          order_type,
                          tracked_order.trade_type,
                          float(execute_price),
                          float(execute_amount_diff),
                    )
                )
                self.logger().info(f"Filled {execute_amount_diff} out of {tracked_order.amount} of the "
                                   f"{order_type_description} order {client_order_id}.")
                self.c_trigger_event(self.MARKET_ORDER_FILLED_EVENT_TAG, order_filled_event)

            for order_update, tracked_order in zip(results, tracked_orders):
                client_order_id = tracked_order.client_order_id
                if isinstance(order_update, Exception):
                    if order_update.code == 2013 or order_update.message == "Order does not exist.":
                        self.c_trigger_event(
                            self.MARKET_ORDER_FAILURE_EVENT_TAG,
                            MarketOrderFailureEvent(self._current_timestamp, client_order_id, tracked_order.order_type)
                         )
                        self.c_stop_tracking_order(client_order_id)
                    else:
                        self.logger().network(
                            f"Error fetching status update for the order {client_order_id}: {order_update}.",
                            app_warning_msg=f"Failed to fetch status update for the order {client_order_id}."
                        )
                    continue
                tracked_order.last_state = order_update["status"]
                order_type = OrderType.LIMIT if order_update["type"] == "LIMIT" else OrderType.MARKET
                if tracked_order.is_done:
                    if not tracked_order.is_failure:
                        if tracked_order.trade_type is TradeType.BUY:
                            self.logger().info(f"The market buy order {tracked_order.client_order_id} has completed "
                                               f"according to order status API.")
                            self.c_trigger_event(self.MARKET_BUY_ORDER_COMPLETED_EVENT_TAG,
                                                 BuyOrderCompletedEvent(self._current_timestamp,
                                                                        client_order_id,
                                                                        tracked_order.base_asset,
                                                                        tracked_order.quote_asset,
                                                                        (tracked_order.fee_asset
                                                                         or tracked_order.base_asset),
                                                                        float(tracked_order.executed_amount_base),
                                                                        float(tracked_order.executed_amount_quote),
                                                                        float(tracked_order.fee_paid),
                                                                        order_type))
                        else:
                            self.logger().info(f"The market sell order {client_order_id} has completed "
                                               f"according to order status API.")
                            self.c_trigger_event(self.MARKET_SELL_ORDER_COMPLETED_EVENT_TAG,
                                                 SellOrderCompletedEvent(self._current_timestamp,
                                                                         client_order_id,
                                                                         tracked_order.base_asset,
                                                                         tracked_order.quote_asset,
                                                                         (tracked_order.fee_asset
                                                                          or tracked_order.quote_asset),
                                                                         float(tracked_order.executed_amount_base),
                                                                         float(tracked_order.executed_amount_quote),
                                                                         float(tracked_order.fee_paid),
                                                                         order_type))
                    else:
                        self.logger().info(f"The market order {client_order_id} has failed according to "
                                           f"order status API.")
                        self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                             MarketOrderFailureEvent(
                                                 self._current_timestamp,
                                                 client_order_id,
                                                 order_type
                                             ))
                    self.c_stop_tracking_order(client_order_id)

    async def _iter_kafka_messages(self, topic: str) -> AsyncIterable[ConsumerRecord]:
        while True:
            try:
                consumer = AIOKafkaConsumer(topic, loop=self._ev_loop, bootstrap_servers=conf.kafka_bootstrap_server)
                await consumer.start()
                partition = list(consumer.assignment())[0]
                await consumer.seek_to_end(partition)

                while True:
                    response = await consumer.getmany(partition, timeout_ms=1000)
                    if partition in response:
                        for record in response[partition]:
                            yield record
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unknown error. Retrying after 5 seconds.",
                    exc_info=True,
                    app_warning_msg="Could not fetch message from Kafka. Check network connection."
                )
                await asyncio.sleep(5.0)

    async def _iter_user_event_queue(self) -> AsyncIterable[Dict[str, any]]:
        while True:
            try:
                yield await self._user_stream_tracker.user_stream.get()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unknown error. Retrying after 1 second.",
                    exc_info=True,
                    app_warning_msg="Could not fetch user events from Huobi. Check API key and network connection."
                )
                await asyncio.sleep(1.0)

    async def _user_stream_event_listener(self):
        async for event_message in self._iter_user_event_queue():
            try:
                order_state = event_message["order-state"]
                exchange_order_id = event_message["order-id"]

                tracked_order = None
                for order in self._in_flight_orders.values():
                    if order.exchange_order_id == exchange_order_id:
                        tracked_order = order
                        break

                if tracked_order is None:
                    continue
                tracked_order.update_with_trade_id(event_message["seq-id"], exchange_order_id)

                order_type_description = event_message.get["order-type"]
                execute_price = Decimal(event_message["price"])
                execute_amount_diff = s_decimal_0

                if order_state == "submitted" or order_state == "partial-filled":
                    remaining_size = Decimal(event_message["unfilled-amount"])
                    new_confirmed_amount = Decimal(event_message["filled-amount"])
                    execute_amount_diff = new_confirmed_amount - tracked_order.executed_amount_base
                    tracked_order.executed_amount_base = new_confirmed_amount
                    tracked_order.executed_amount_quote += execute_amount_diff * execute_price
                    tracked_order.fee_paid = Decimal(event_message["filled-fees"])

                elif order_state == "filled":
                    remaining_size = Decimal(event_message["unfilled-amount"])
                    new_confirmed_amount = Decimal(event_message["filled-amount"])
                    execute_amount_diff = new_confirmed_amount - tracked_order.executed_amount_base
                    tracked_order.executed_amount_base = new_confirmed_amount
                    tracked_order.executed_amount_quote += execute_amount_diff * execute_price
                    tracked_order.fee_paid = Decimal(event_message["filled-fees"])
                    tracked_order.last_state = "done"

                    if tracked_order.trade_type == TradeType.BUY:
                        self.logger().info(f"The market buy order {tracked_order.client_order_id} has completed "
                                           f"according to the Huobi user stream.")
                        self.c_trigger_event(self.MARKET_BUY_ORDER_COMPLETED_EVENT_TAG,
                                             BuyOrderCompletedEvent(self._current_timestamp,
                                                                    tracked_order.client_order_id,
                                                                    tracked_order.base_asset,
                                                                    tracked_order.quote_asset,
                                                                    (tracked_order.fee_asset
                                                                     or tracked_order.base_asset),
                                                                    float(tracked_order.executed_amount_base),
                                                                    float(tracked_order.executed_amount_quote),
                                                                    float(tracked_order.fee_paid),
                                                                    tracked_order.order_type))
                    else:
                        self.logger().info(f"The market sell order {tracked_order.client_order_id} has completed "
                                           f"according to Huobi user stream.")
                        self.c_trigger_event(self.MARKET_SELL_ORDER_COMPLETED_EVENT_TAG,
                                             SellOrderCompletedEvent(self._current_timestamp,
                                                                     tracked_order.client_order_id,
                                                                     tracked_order.base_asset,
                                                                     tracked_order.quote_asset,
                                                                     (tracked_order.fee_asset
                                                                      or tracked_order.quote_asset),
                                                                     float(tracked_order.executed_amount_base),
                                                                     float(tracked_order.executed_amount_quote),
                                                                     float(tracked_order.fee_paid),
                                                                     tracked_order.order_type))

                else: # reason == "canceled":
                    execute_amount_diff = 0
                    tracked_order.last_state = "order-state"
                    self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                        OrderCancelledEvent(self._current_timestamp, tracked_order.client_order_id))
                self.c_stop_tracking_order(tracked_order.client_order_id)

                # Emit event if executed amount is greater than 0.
                if execute_amount_diff > s_decimal_0:
                    order_filled_event = OrderFilledEvent(
                        self._current_timestamp,
                        tracked_order.client_order_id,
                        tracked_order.symbol,
                        tracked_order.trade_type,
                        tracked_order.order_type,
                        float(execute_price),
                        float(execute_amount_diff),
                        self.c_get_fee(
                          tracked_order.base_asset,
                          tracked_order.quote_asset,
                          tracked_order.order_type,
                          tracked_order.trade_type,
                          float(execute_price),
                          float(execute_amount_diff),
                        )
                    )
                    self.logger().info(f"Filled {execute_amount_diff} out of {tracked_order.amount} of the "
                                       f"{order_type_description} order {tracked_order.client_order_id}.")
                    self.c_trigger_event(self.MARKET_ORDER_FILLED_EVENT_TAG, order_filled_event)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await asyncio.sleep(5.0)

    async def _status_polling_loop(self):
        while True:
            try:
                self._poll_notifier = asyncio.Event()
                await self._poll_notifier.wait()

                await asyncio.gather(
                    self._update_balances(),
                    self._update_order_status(),
                    self._update_order_fills_from_trades()
                )
                self._last_pull_timestamp = self._current_timestamp
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network("Unexpected error while fetching account updates.", exc_info=True,
                                      app_warning_msg="Could not fetch account updates from Huobi. "
                                                      "Check API key and network connection.")
                await asyncio.sleep(0.5)

    async def _trading_rules_polling_loop(self):
        while True:
            try:
                await asyncio.gather(
                    self._update_trading_rules(),
                )
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network("Unexpected error while fetching trading rules.", exc_info=True,
                                      app_warning_msg="Could not fetch new trading rules from Huobi. "
                                                      "Check network connection.")
                await asyncio.sleep(0.5)

    @property
    def status_dict(self) -> Dict[str, bool]:
        return {
            "order_books_initialized": len(self._order_book_tracker.order_books) > 0,
            "account_balance": len(self._account_balances) > 0 if self._trading_required else True,
            "trading_rule_initialized": len(self._trading_rules) > 0
        }

    @property
    def ready(self) -> bool:
        return all(self.status_dict.values())

    async def server_time(self) -> int:
        """
        :return: The current server time in milliseconds since UNIX epoch.
        """
        result = await self.query_url("get", "/v1/common/timestamp", new Dict[str, any] )
        return result

    def get_all_balances(self) -> Dict[str, float]:
        return self._account_balances.copy()

    async def get_deposit_info(self, asset: str) -> DepositInfo:
        cdef:
            dict deposit_reply
            str err_msg
            str deposit_address

        # Huobi API currently does not support deposits - no documentation
        return DepositInfo("", new Dict[str, any])

    async def execute_withdraw(self, tracking_id: str, to_address: str, currency: str, amount: float):
        withdraw_url = "/v1/dw/withdraw/api/create"
        check_url = "/v1/query/deposit-withdraw"
        params = {
            "address": to_address,
            "currency": currency,
            "amount": str(Decimal(amount))
        }
        if currency.lowerCase() == "usdt":
            params.update({"chain": "usdterc20"})

        try:
            withdraw_result = await self.query_auth_url("post", HUOBI_ROOT_API, withdraw_url, params)
            self.logger().info(f"Successfully withdrew {amount} of {currency}. {withdraw_result}")

            data = {
                "type": "withdraw",
                "from": withdraw_result,
                "size": "1"
            }
            withdraw_info = await self.query_auth_url("get", HUOBI_ROOT_API, check_url, data)
            for item in withdraw_info["data"]:
                withdraw_fee = item["fee"]
                break

            self.c_trigger_event(self.MARKET_WITHDRAW_ASSET_EVENT_TAG,
                             MarketWithdrawAssetEvent(self._current_timestamp, tracking_id, to_address, currency,
                                                      float(amount), float(withdraw_fee)))

        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().network(
                f"Error sending withdraw request to Huobi for {currency}.",
                exc_info=True,
                app_warning_msg=f"Could not send {currency} withdrawal request to Huobi. "
                                f"Check network connection."
            )
            self.c_trigger_event(self.MARKET_TRANSACTION_FAILURE_EVENT_TAG,
                                 MarketTransactionFailureEvent(self._current_timestamp, tracking_id))

    cdef str c_withdraw(self, str address, str currency, double amount):
        cdef:
            int64_t tracking_nonce = <int64_t>(time.time() * 1e6)
            str tracking_id = str(f"withdraw://{currency}/{tracking_nonce}")
        asyncio.ensure_future(self.execute_withdraw(tracking_id, address, currency, amount))
        return tracking_id

    async def place_order(self, order_id: str, symbol: str, amount: Decimal, is_buy: bool, order_type: OrderType,
                          price: Decimal):
        path_url = "/v1/order/orders/place"
        side = "buy" if is_buy else "sell"
        order_type = "limit" if order_type is OrderType.LIMIT else "market"

        account_id = self.get_account_id()
        params = {
            "account-id": account_id,
            "symbol": symbol,
            "type": f"{side}-{order_type}",
            "amount": float(amount),
            "price": float(price),
            "client-order-id": order_id
        }
        order_result = await self.query_auth_url("post", HUOBI_ROOT_API, path_url, params)
        return order_result

    async def execute_buy(self,
                          order_id: str,
                          symbol: str,
                          amount: float,
                          order_type: OrderType,
                          price: Optional[float] = NaN):
        cdef:
            TradingRule trading_rule = self._trading_rules[symbol]

        decimal_amount = self.c_quantize_order_amount(symbol, amount)
        decimal_price = (self.c_quantize_order_price(symbol, price)
                         if order_type is OrderType.LIMIT
                         else s_decimal_0)
        if decimal_amount < trading_rule.min_order_size:
            raise ValueError(f"Buy order amount {decimal_amount} is lower than the minimum order size "
                             f"{trading_rule.min_order_size}.")

        try:
            order_result = await self.place_order(order_id, symbol, decimal_amount, True, order_type, decimal_price)
            if order_type is OrderType.LIMIT:
                self.c_start_tracking_order(
                    order_id,
                    str(order_result),
                    symbol,
                    TradeType.BUY,
                    decimal_price,
                    decimal_amount,
                    order_type
                )
            elif order_type is OrderType.MARKET:
                self.c_start_tracking_order(
                    order_id,
                    str(order_result),
                    symbol,
                    TradeType.BUY,
                    None,
                    decimal_amount,
                    order_type
                )
            else:
                raise ValueError(f"Invalid OrderType {order_type}. Aborting.")

            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(f"Created {order_type} buy order {order_id} for "
                                   f"{decimal_amount} {symbol}.")
            self.c_trigger_event(self.MARKET_BUY_ORDER_CREATED_EVENT_TAG,
                                 BuyOrderCreatedEvent(
                                     self._current_timestamp,
                                     order_type,
                                     symbol,
                                     float(decimal_amount),
                                     float(decimal_price),
                                     order_id
                                 ))

        except asyncio.CancelledError:
            raise

        except asyncio.TimeoutError:
            self.logger().network(f"Timeout Error encountered while submitting buy ",exc_info=True)

        except Exception:
            self.c_stop_tracking_order(order_id)
            order_type_str = 'MARKET' if order_type == OrderType.MARKET else 'LIMIT'
            self.logger().network(
                f"Error submitting buy {order_type_str} order to Huobi for "
                f"{decimal_amount} {symbol} "
                f"{decimal_price if order_type is OrderType.LIMIT else ''}.",
                exc_info=True,
                app_warning_msg=f"Failed to submit buy order to Huobi. Check API key and network connection."
            )
            self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                 MarketOrderFailureEvent(self._current_timestamp, order_id, order_type))

    cdef str c_buy(self, str symbol, double amount, object order_type = OrderType.MARKET, double price = NaN,
                   dict kwargs = {}):
        cdef:
            int64_t tracking_nonce = <int64_t>(time.time() * 1e6)
            str order_id = str(f"buy-{symbol}-{tracking_nonce}")
        asyncio.ensure_future(self.execute_buy(order_id, symbol, amount, order_type, price))
        return order_id

    async def execute_sell(self,
                           order_id: str,
                           symbol: str,
                           amount: float,
                           order_type: OrderType,
                           price: Optional[float] = NaN):
        cdef:
            TradingRule trading_rule = self._trading_rules[symbol]

        decimal_amount = self.quantize_order_amount(symbol, amount)
        decimal_price = (self.c_quantize_order_price(symbol, price)
                         if order_type is OrderType.LIMIT
                         else s_decimal_0)
        if decimal_amount < trading_rule.min_order_size:
            raise ValueError(f"Sell order amount {decimal_amount} is lower than the minimum order size "
                             f"{trading_rule.min_order_size}.")

        try:
            order_result = await self.place_order(order_id, symbol, decimal_amount, False, order_type, decimal_price)
            if order_type is OrderType.LIMIT:
                self.c_start_tracking_order(
                    order_id,
                    str(order_result),
                    symbol,
                    TradeType.SELL,
                    decimal_price,
                    decimal_amount,
                    order_type
                )
            elif order_type is OrderType.MARKET:
                self.c_start_tracking_order(
                    order_id,
                    str(order_result),
                    symbol,
                    TradeType.SELL,
                    None,
                    decimal_amount,
                    order_type
                )
            else:
                raise ValueError(f"Invalid OrderType {order_type}. Aborting.")

            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(f"Created {order_type} sell order {order_id} for "
                                   f"{decimal_amount} {symbol}.")
            self.c_trigger_event(self.MARKET_SELL_ORDER_CREATED_EVENT_TAG,
                                 SellOrderCreatedEvent(
                                     self._current_timestamp,
                                     order_type,
                                     symbol,
                                     float(decimal_amount),
                                     float(decimal_price),
                                     order_id
                                 ))

        except asyncio.TimeoutError:
            self.logger().network(f"Timeout Error encountered while submitting sell ",exc_info=True)
        except asyncio.CancelledError:
            raise
        except Exception:
            self.c_stop_tracking_order(order_id)
            order_type_str = 'MARKET' if order_type is OrderType.MARKET else 'LIMIT'
            self.logger().network(
                f"Error submitting sell {order_type_str} order to Huobi for "
                f"{decimal_amount} {symbol} "
                f"{decimal_price if order_type is OrderType.LIMIT else ''}.",
                exc_info=True,
                app_warning_msg=f"Failed to submit sell order to Huobi. Check API key and network connection."
            )
            self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                 MarketOrderFailureEvent(self._current_timestamp, order_id, order_type))

    cdef str c_sell(self, str symbol, double amount, object order_type = OrderType.MARKET, double price = NaN,
                    dict kwargs = {}):
        cdef:
            int64_t tracking_nonce = <int64_t>(time.time() * 1e6)
            str order_id = str(f"sell-{symbol}-{tracking_nonce}")
        asyncio.ensure_future(self.execute_sell(order_id, symbol, amount, order_type, price))
        return order_id

    async def execute_cancel(self, symbol: str, order_id: str):
        tracked_order = self._in_flight_orders.get(order_id)
        params = {"order-ids": [int(tracked_order.exchange_order_id)]}
        try:
            cancel_result = await self.query_auth_url("post", HUOBI_ROOT_API,
                                                      "/v1/order/orders/batchcancel",
                                                      params)
            if int(order_id) in cancel_result["data"]["success"]:
                self.logger().info(f"Successfully cancelled order {order_id}.")
                self.c_stop_tracking_order(order_id)
                self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                 OrderCancelledEvent(self._current_timestamp, order_id))
                return order_id
            else:
                for item in cancel_result["data"]["failed"]:
                    if item["err-code"] == "order-queryorder-invalid":
                        self.logger().info(f"The order {order_id} does not exist on Huobi. No cancellation needed.")
                        self.c_stop_tracking_order(order_id)
                        self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                     OrderCancelledEvent(self._current_timestamp, order_id))
                        return order_id
        except Exception as e:
            self.logger().network(
                f"Failed to cancel order {order_id}: {str(e)}",
                exc_info=True,
                app_warning_msg=f"Failed to cancel the order {order_id} on Huobi. "
                                f"Check API key and network connection."
            )
        return None

    cdef c_cancel(self, str symbol, str order_id):
        asyncio.ensure_future(self.execute_cancel(symbol, order_id))
        return order_id

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        incomplete_orders = [o for o in self._in_flight_orders.values() if not o.is_done]
        tasks = [self.execute_cancel(o.symbol, o.client_order_id) for o in incomplete_orders]
        order_id_set = set([o.client_order_id for o in incomplete_orders])
        successful_cancellations = []

        try:
            async with timeout(timeout_seconds):
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for client_order_id in results:
                    if type(client_order_id) is str:
                        order_id_set.remove(client_order_id)
                        successful_cancellations.append(CancellationResult(client_order_id, True))
        except Exception:
            self.logger().network(
                f"Unexpected error cancelling orders.",
                exc_info=True,
                app_warning_msg="Failed to cancel order with Huobi. Check API key and network connection."
            )

        failed_cancellations = [CancellationResult(oid, False) for oid in order_id_set]
        return successful_cancellations + failed_cancellations

    cdef double c_get_balance(self, str currency) except? -1:
        return float(self._account_balances.get(currency, 0.0))

    cdef double c_get_available_balance(self, str currency) except? -1:
        return float(self._account_available_balances.get(currency, 0.0))

    cdef double c_get_price(self, str symbol, bint is_buy) except? -1:
        cdef:
            OrderBook order_book = self.c_get_order_book(symbol)

        return order_book.c_get_price(is_buy)

    cdef OrderBook c_get_order_book(self, str symbol):
        cdef:
            dict order_books = self._order_book_tracker.order_books

        if symbol not in order_books:
            raise ValueError(f"No order book exists for '{symbol}'.")
        return order_books[symbol]

    cdef c_did_timeout_tx(self, str tracking_id):
        self.c_trigger_event(self.MARKET_TRANSACTION_FAILURE_EVENT_TAG,
                             MarketTransactionFailureEvent(self._current_timestamp, tracking_id))

    cdef c_start_tracking_order(self,
                                str client_order_id,
                                str order_id,
                                str symbol,
                                object order_type,
                                object trade_type,
                                object price,
                                object amount):
        self._in_flight_orders[order_id] = HuobiInFlightOrder(
            client_order_id=client_order_id,
            exchange_order_id=order_id,
            symbol=symbol,
            order_type=order_type,
            trade_type=trade_type,
            price=price,
            amount=amount
        )

    cdef c_stop_tracking_order(self, str order_id):
        if order_id in self._in_flight_orders:
            del self._in_flight_orders[order_id]

    cdef object c_get_order_price_quantum(self, str symbol, double price):
        cdef:
            TradingRule trading_rule = self._trading_rules[symbol]
        return trading_rule.min_price_increment

    cdef object c_get_order_size_quantum(self, str symbol, double order_size):
        cdef:
            TradingRule trading_rule = self._trading_rules[symbol]
        return Decimal(trading_rule.min_base_amount_increment)

    cdef object c_quantize_order_amount(self, str symbol, double amount, double price = 0.0):
        cdef:
            TradingRule trading_rule = self._trading_rules[symbol]
            double current_price = self.c_get_price(symbol, False)

        global s_decimal_0
        quantized_amount = MarketBase.c_quantize_order_amount(self, symbol, amount)

        # Check against min_order_size. If not passing check, return 0.
        if quantized_amount < trading_rule.min_order_size:
            return s_decimal_0

        # Check against max_order_size. If not passing check, return 0.
        if quantized_amount > trading_rule.max_order_size:
            return s_decimal_0

        return quantized_amount
