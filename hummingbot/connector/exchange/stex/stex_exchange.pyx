from libc.stdint cimport int64_t, int32_t
import aiohttp
import asyncio
import math
from async_timeout import timeout
from decimal import Decimal
import logging
import pandas as pd
from collections import defaultdict
from typing import (
    Any,
    Dict,
    List,
    AsyncIterable,
    Optional,
)
from hummingbot.core.utils.asyncio_throttle import Throttler
import copy
from hummingbot.core.utils.async_call_scheduler import AsyncCallScheduler
from hummingbot.core.clock cimport Clock
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from hummingbot.connector.exchange.stex.stex_api_order_book_data_source import StexAPIOrderBookDataSource
from hummingbot.connector.exchange.stex.stex_auth import StexAuth
#import hummingbot.connector.exchange.stex.stex_constants as constants
from hummingbot.connector.exchange.stex.stex_utils import (
    convert_from_exchange_trading_pair,
    convert_to_exchange_trading_pair)
from hummingbot.logger import HummingbotLogger
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
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.connector.exchange.stex.stex_order_book_tracker import StexOrderBookTracker
from hummingbot.connector.exchange.stex.stex_user_stream_tracker import StexUserStreamTracker
from hummingbot.connector.exchange.stex.stex_in_flight_order import StexInFlightOrder
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.transaction_tracker import TransactionTracker
from hummingbot.connector.trading_rule cimport TradingRule
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce
from hummingbot.core.utils.estimate_fee import estimate_fee

s_logger = None
s_decimal_0 = Decimal(0)
s_decimal_NaN = Decimal("NaN")
JSON_SETTINGS = 'settings-private.json'
STEX_ROOT_API = "https://api3.stex.com"
STEX_TIME_URL = "https://api3.stex.com/public/ping"
STEX_TOKEN_URL = "https://api3.stex.com/oauth/token"
cdef class StexExchangeTransactionTracker(TransactionTracker):
    cdef:
        StexExchange _owner

    def __init__(self, owner):
        super().__init__()
        self._owner = owner

    cdef c_did_timeout_tx(self, str tx_id):
        TransactionTracker.c_did_timeout_tx(self, tx_id)
        self._owner.c_did_timeout_tx(tx_id)

cdef class StexExchange(ExchangeBase):
    MARKET_RECEIVED_ASSET_EVENT_TAG = MarketEvent.ReceivedAsset.value
    MARKET_BUY_ORDER_COMPLETED_EVENT_TAG = MarketEvent.BuyOrderCompleted.value
    MARKET_SELL_ORDER_COMPLETED_EVENT_TAG = MarketEvent.SellOrderCompleted.value
    MARKET_ORDER_CANCELLED_EVENT_TAG = MarketEvent.OrderCancelled.value
    MARKET_TRANSACTION_FAILURE_EVENT_TAG = MarketEvent.TransactionFailure.value
    MARKET_ORDER_FAILURE_EVENT_TAG = MarketEvent.OrderFailure.value
    MARKET_ORDER_FILLED_EVENT_TAG = MarketEvent.OrderFilled.value
    MARKET_BUY_ORDER_CREATED_EVENT_TAG = MarketEvent.BuyOrderCreated.value
    MARKET_SELL_ORDER_CREATED_EVENT_TAG = MarketEvent.SellOrderCreated.value

    API_CALL_TIMEOUT = 10.0


    ORDER_NOT_EXIST_CONFIRMATION_COUNT = 3

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(__name__)
        return s_logger

    def __init__(self,
                 stex_access_token: str,
                 trading_pairs: Optional[List[str]] = None,
                 poll_interval: float = 10.0,
                 trading_required: bool = True):

        super().__init__()
        self._trading_required = trading_required
        self._order_book_tracker = StexOrderBookTracker(trading_pairs=trading_pairs)
        self._stex_auth = StexAuth(stex_access_token)
        self._user_stream_tracker = StexUserStreamTracker(stex_auth=self._stex_auth)
        self._auth_dict: Dict[str, Any] = self._stex_auth.generate_auth_dict()
        self._ev_loop = asyncio.get_event_loop()
        self._poll_notifier = asyncio.Event()
        self._last_timestamp = 0
        self._poll_interval = poll_interval
        self._in_flight_orders = {}  # Dict[client_order_id:str, StexnFlightOrder]
        self._order_not_found_records = {}  # Dict[client_order_id:str, count:int]
        self._tx_tracker = StexExchangeTransactionTracker(self)
        self._trading_rules = {}  # Dict[trading_pair:str, TradingRule]
        self._trade_fees = {}  # Dict[trading_pair:str, (maker_fee_percent:Decimal, taken_fee_percent:Decimal)]
        self._last_update_trade_fees_timestamp = 0
        self._status_polling_task = None
        self._user_stream_tracker_task = None
        self._user_stream_event_listener_task = None
        self._trading_rules_polling_task = None
        self._async_scheduler = AsyncCallScheduler(call_interval=0.5)
        self._throttler = Throttler(rate_limit = (10.0, 1.0))
        self._last_pull_timestamp = 0
        self._shared_client = None
        self._asset_pairs = {}
        self._real_time_balance_update = False
        self._currency_pair_dict = {}

    @property
    def name(self) -> str:
        return "stex"

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        return self._order_book_tracker.order_books

    @property
    def stex_auth(self) -> StexAuth:
        return self._stex_auth

    @property
    def trading_rules(self) -> Dict[str, StexInFlightOrder]:
        return self._trading_rules

    @property
    def in_flight_orders(self) -> Dict[str, StexInFlightOrder]:
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
            order_id: value.to_json()
            for order_id, value in self._in_flight_orders.items()
        }

    def restore_tracking_states(self, saved_states: Dict[str, Any]):
        in_flight_orders: Dict[str, KrakenInFlightOrder] = {}
        for key, value in saved_states.items():
            in_flight_orders[key] = StexInFlightOrder.from_json(value)
        self._in_flight_orders.update(in_flight_orders)

    async def _http_client(self) -> aiohttp.ClientSession:
        if self._shared_client is None:
            self._shared_client = aiohttp.ClientSession()
        return self._shared_client

    async def _api_request(self,
                           path_url: str,
                           method:str = 'GET',
                           format_type: str ='url',
                           is_auth_required: bool = False,
                           data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = STEX_ROOT_API + path_url
        client = await self._http_client()
        headers = {'Content-Type': 'application/json', 'User-Agent': 'stex_python_client'}
        if is_auth_required == True:
            headers['Authorization'] = 'Bearer {}'.format(self._auth_dict["access_token"])
        if method == 'POST' and format_type == 'url':
            response_coro = client.post(url = url, headers = headers)
        if method == 'GET' and format_type == 'url':
            response_coro = client.get(url = url, headers = headers)
        if method == 'DELETE' and format_type =='url':
            response_coro = client.delete(url=url, headers=headers)
        if method == 'POST' and format_type == 'form':
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
            response_coro = client.post(url=url, headers=headers, data=data)
        async with response_coro as response:
            if response.status != 200:
                raise IOError(f"Error fetching data from {url}. Response: {await response.json()}.")
            try:
                parsed_response = await response.json()
                return parsed_response
            except:
                raise IOError(f"Error parsing data from {url}.")

    async def _update_balances(self):
        cdef:
            dict account_info
            dict balances
            dict balance
            str asset_name
            set local_asset_names = set(self._account_balances.keys())
            set remote_asset_names = set()
            set asset_names_to_remove

        account_info = await self._api_request(method="POST",path_url= "/profile/info", is_auth_required = True)
        balances = account_info["data"]["approx_balance"]
        for asset_name, balance in balances.items():
            free_balance = Decimal(balance['balance'])
            total_balance = Decimal(balance['total_balance'])
            self._account_available_balances[asset_name] = free_balance
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
                          object amount,
                          object price):
        is_maker = False
        return estimate_fee("stex", is_maker)

    async def _update_trading_rules(self):
        cdef:
            int64_t last_tick = <int64_t>(self._last_timestamp / 60.0)
            int64_t current_tick = <int64_t>(self._current_timestamp / 60.0)
        if current_tick > last_tick or len(self._trading_rules) < 1:
            exchange_info = await self._api_request(method="GET", path_url="/public/currency_pairs/list/ALL")
            trading_rules_list = self._format_trading_rules(exchange_info["data"])
            self._trading_rules.clear()
             # Update currency pair id and trading pair conversion dict for later use
            for info in exchange_info["data"]:
                currency_pair = convert_from_exchange_trading_pair(info.get('symbol', None))
                currency_pair_id = info.get('id', None)
                if currency_pair:
                    self._currency_pair_dict[currency_pair] = currency_pair_id
            for trading_rule in trading_rules_list:
                self._trading_rules[trading_rule.trading_pair] = trading_rule

    def _format_trading_rules(self, raw_trading_pair_info: List[Dict[str, Any]]) -> List[TradingRule]:
        cdef:
            list trading_rules = []

        for info in raw_trading_pair_info:
            try:
                trading_pair = convert_from_exchange_trading_pair(info["symbol"])
                min_order_size = Decimal(str(info["min_order_amount"]))
                min_price_increment = Decimal(str(info["min_buy_price"])) #min_buy_price or min_sell_price ?
                currency_decimals = Decimal(str(info["currency_precision"]))
                market_decimals = Decimal(str(info["market_precision"]))
                currency_step = Decimal("1") / Decimal(str(math.pow(10, currency_decimals)))
                market_step = Decimal("1") / Decimal(str(math.pow(10, market_decimals)))
                trading_rules.append(
                    TradingRule(trading_pair=trading_pair,
                                min_order_size=min_order_size,
                                min_price_increment=min_price_increment,
                                min_base_amount_increment=currency_step,
                                min_quote_amount_increment=market_step)
                )
            except Exception:
                self.logger().error(f"Error parsing the trading pair rule {info}. Skipping.", exc_info=True)
        return trading_rules

    async def get_order_status(self, exchange_order_id: str) -> Dict[str, Any]:
        """
        Example:
        {
          "success": true,
          "data": {
            "id": 828680665,
            "currency_pair_id": 1,
            "currency_pair_name": "NXT_BTC",
            "price": "0.011384",
            "trigger_price": 0.011385,
            "initial_amount": "13.942",
            "processed_amount": "3.724",
            "type": "SELL",
            "original_type": "STOP_LIMIT_SELL",
            "created": "2019-01-17 10:14:48",
            "timestamp": "1547720088",
            "status": "PARTIAL"
            }
        }
        """
        path_url = f"/trading/order/{exchange_order_id}"
        return await self._api_request(method="GET", path_url=path_url, is_auth_required = True)

    async def _update_order_status(self):
        cdef:
            int64_t last_tick = <int64_t>(self._last_poll_timestamp / self.UPDATE_ORDERS_INTERVAL)
            int64_t current_tick = <int64_t>(self._current_timestamp / self.UPDATE_ORDERS_INTERVAL)

        if len(self._in_flight_orders) > 0:
            tracked_orders = list(self._in_flight_orders.values())
            tasks = [await self.get_order_status(o.exchange_order_id) for o in tracked_orders]
            results = await safe_gather(*tasks, return_exceptions=True)

            for order_update, tracked_order in zip(results, tracked_orders):
                client_order_id = tracked_order.client_order_id

                if client_order_id not in self._in_flight_orders:
                    continue

                if isinstance(order_update, Exception):
                    self.logger().network(
                        f"Error fetching status update for the order {client_order_id}: {order_update}.",
                        app_warning_msg=f"Failed to fetch status update for the order {client_order_id}."
                    )
                    continue

                if order_update.get("success") is False:
                    self.logger().debug(f"Error in fetched status update for order {client_order_id}: "
                                        f"{order_update['message']}")
                    self.c_cancel(tracked_order.trading_pair, tracked_order.client_order_id)
                    continue

                update = order_update.get("data")

                if not update:
                    self._order_not_found_records[client_order_id] = self._order_not_found_records.get(client_order_id, 0) + 1
                    if self._order_not_found_records[client_order_id] < self.ORDER_NOT_EXIST_CONFIRMATION_COUNT:
                        continue
                    self.c_trigger_event(
                        self.MARKET_ORDER_FAILURE_EVENT_TAG,
                        MarketOrderFailureEvent(self._current_timestamp, client_order_id, tracked_order.order_type)
                    )
                    self.c_stop_tracking_order(client_order_id)
                    continue

                tracked_order.last_state = order_update["status"]
                executed_amount_base = Decimal(order_update["processed_amount"])
                executed_amount_quote = Decimal(order_update["initial_amount"])

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
                                                                         or tracked_order.quote_asset),
                                                                        executed_amount_base,
                                                                        executed_amount_quote,
                                                                        tracked_order.fee_paid,
                                                                        tracked_order.order_type))
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
                                                                         executed_amount_base,
                                                                         executed_amount_quote,
                                                                         tracked_order.fee_paid,
                                                                         tracked_order.order_type))
                    else:
                        # check if its a cancelled order
                        # if its a cancelled order, issue cancel and stop tracking order
                        if tracked_order.is_cancelled:
                            self.logger().info(f"Successfully cancelled order {client_order_id}.")
                            self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                                 OrderCancelledEvent(
                                                     self._current_timestamp,
                                                     client_order_id))
                        else:
                            self.logger().info(f"The market order {client_order_id} has failed according to "
                                               f"order status API.")
                            self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                                 MarketOrderFailureEvent(
                                                     self._current_timestamp,
                                                     client_order_id,
                                                     tracked_order.order_type
                                                 ))
                    self.c_stop_tracking_order(client_order_id)

    async def _iter_user_event_queue(self) -> AsyncIterable[Dict[str, Any]]:
        while True:
            try:
                yield await self._user_stream_tracker.user_stream.get()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unknown error. Retrying after 1 seconds.",
                    exc_info=True,
                    app_warning_msg="Could not fetch user events from Stex. Check API key and network connection."
                )
                await asyncio.sleep(1.0)

    async def _user_stream_event_listener(self):
        async for event_message in self._iter_user_event_queue():
            try:
                updates: List[Any] = event_message[1]
                for update in updates:
                    exchange_order_id = update["id"]
                    trading_pair = convert_from_exchange_trading_pair(update["currency_pair_name"])
                    order_status = update["status"]
                    try:
                        client_order_id = next(key for key, value in self._in_flight_orders.items()
                                               if value.exchange_order_id == exchange_order_id)
                    except StopIteration:
                        continue

                    if order_status not in ["PROCESSING", "PENDING", "PARTIAL", "FINISHED", "CANCELLED"]:
                        self.logger().debug(f"Unrecognized order update response - {event_message}")
                    tracked_order = self._in_flight_orders.get(client_order_id)

                    if tracked_order is None:
                        continue

                    execute_amount_diff = s_decimal_0
                    execute_price = Decimal(update["price"])
                    order_type = update["type"]

                    execute_amount_diff = Decimal(update["processed_amount"])
                    tracked_order.executed_amount_base += execute_amount_diff
                    tracked_order.executed_amount_quote += Decimal(execute_amount_diff * execute_price)

                    if execute_amount_diff > s_decimal_0:
                        self.logger().info(f"Filed {execute_amount_diff} out of {tracked_order.amount} of order "
                                           f"{order_type.upper()}-{client_order_id}")
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

                    if order_status == "FINISHED":
                        tracked_order.last_state = order_status
                        if tracked_order.trade_type is TradeType.BUY:
                            self.logger().info(f"The LIMIT_BUY order {tracked_order.client_order_id} has completed "
                                               f"according to order delta websocket API.")
                            self.c_trigger_event(self.MARKET_BUY_ORDER_COMPLETED_EVENT_TAG,
                                                 BuyOrderCompletedEvent(
                                                     self._current_timestamp,
                                                     tracked_order.client_order_id,
                                                     tracked_order.base_asset,
                                                     tracked_order.quote_asset,
                                                     tracked_order.fee_asset or tracked_order.quote_asset,
                                                     tracked_order.executed_amount_base,
                                                     tracked_order.executed_amount_quote,
                                                     tracked_order.fee_paid,
                                                     tracked_order.order_type
                                                 ))

                        elif tracked_order.trade_type is TradeType.SELL:
                                self.logger().info(f"The LIMIT_SELL order {tracked_order.client_order_id} has completed "
                                                   f"according to order delta websocket API.")
                                self.c_trigger_event(self.MARKET_SELL_ORDER_COMPLETED_EVENT_TAG,
                                                     SellOrderCompletedEvent(
                                                         self._current_timestamp,
                                                         tracked_order.client_order_id,
                                                         tracked_order.base_asset,
                                                         tracked_order.quote_asset,
                                                         tracked_order.fee_asset or tracked_order.quote_asset,
                                                         tracked_order.executed_amount_base,
                                                         tracked_order.executed_amount_quote,
                                                         tracked_order.fee_paid,
                                                         tracked_order.order_type
                                                     ))
                        self.c_stop_tracking_order(tracked_order.client_order_id)
                        continue

                    if order_status == "CANCELLED":
                            tracked_order.last_state = order_status
                            self.logger().info(f"The order {tracked_order.client_order_id} has been cancelled "
                                               f"according to order delta websocket API.")
                            self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                                 OrderCancelledEvent(self._current_timestamp,
                                                                     tracked_order.client_order_id))
                            self.c_stop_tracking_order(tracked_order.client_order_id)

            except asyncio.CancelledError:
                    raise
            except Exception as e:
                self.logger().error(f"Unexpected error in user stream listener loop. {e}", exc_info=True)
                await asyncio.sleep(5.0)

    async def _status_polling_loop(self):
        while True:
            try:
                self._poll_notifier = asyncio.Event()
                await self._poll_notifier.wait()
                await safe_gather(
                    self._update_balances(),
                    self._update_order_status(),
                )
                self._last_pull_timestamp = self._current_timestamp
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network("Unexpected error while fetching account updates.", exc_info=True,
                                      app_warning_msg="Could not fetch account updates from Stex. "
                                                      "Check API key and network connection.")
                await asyncio.sleep(0.5)

    async def _trading_rules_polling_loop(self):
        while True:
            try:
                await safe_gather(
                    self._update_trading_rules(),
                )
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network("Unexpected error while fetching trading rules.", exc_info=True,
                                      app_warning_msg="Could not fetch new trading rules from Stex. "
                                                      "Check network connection.")
                await asyncio.sleep(0.5)

    def status_dict(self) -> Dict[str, bool]:
        return {
            "order_books_initialized": self._order_book_tracker.ready,
            "account_balance": len(self._account_balances) > 0 if self._trading_required else True,
            "trading_rule_initialized": len(self._trading_rules) > 0
        }

    @property
    def ready(self) -> bool:
        return all(self.status_dict().values())

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

    def _stop_network(self):
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

    async def check_network(self) -> NetworkStatus:
        try:
            client = await self._http_client()
            await client.get(STEX_TIME_URL)
        except asyncio.CancelledError:
            raise
        except Exception:
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

#order type (BUY / SELL / STOP_LIMIT_BUY / STOP_LIMIT_SELL)

    async def place_order(self,
                          trading_pair: str,
                          amount: Decimal,
                          order_type: OrderType,
                          is_buy: bool,
                          price: Optional[Decimal] = s_decimal_NaN):

        currency_pair_id = self._currency_pair_dict.get(trading_pair)
        path_url = "/trading/orders/{}".format(currency_pair_id)
        data = {
            "type": "BUY" if is_buy else "SELL",
            'amount': amount,
            'price': price
        }
        return await self._api_request(method = 'POST',
                                       path_url = path_url,
                                       format_type = 'form',
                                       data = data,
                                       is_auth_required = True)
    async def execute_buy(self,
                          order_id: str,
                          trading_pair: str,
                          amount: Decimal,
                          order_type: OrderType,
                          price: Optional[Decimal] = s_decimal_NaN):
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]

        decimal_amount = self.c_quantize_order_amount(trading_pair, amount)
        decimal_price = self.c_quantize_order_price(trading_pair, price)

        try:
            order_result = None
            order_decimal_amount = f"{decimal_amount:f}"
            if order_type is OrderType.LIMIT:
                order_decimal_price = f"{decimal_price:f}"
                order_result = await self.place_order(trading_pair=trading_pair,
                                                      amount=order_decimal_amount,
                                                      order_type=order_type,
                                                      is_buy=True,
                                                      price=order_decimal_price)

                exchange_order_id = order_result["data"]["id"]

                self.c_start_tracking_order(
                    order_id,
                    exchange_order_id,
                    trading_pair,
                    TradeType.BUY,
                    decimal_price,
                    decimal_amount,
                    order_type
                )
                tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(f"Created {order_type} buy order {order_id} for "
                                   f"{decimal_amount} {trading_pair}.")
                tracked_order.exchange_order_id = exchange_order_id
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

        except Exception as e:
            self.c_stop_tracking_order(order_id)
            order_type_str = 'LIMIT'
            self.logger().network(
                f"Error submitting buy {order_type_str} order to Stex for "
                f"{decimal_amount} {trading_pair}"
                f" {decimal_price}.",
                exc_info=True,
                app_warning_msg=f"Failed to submit buy order to Stex. Check API key and network connection."
            )
            self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                 MarketOrderFailureEvent(self._current_timestamp, order_id, order_type))

    cdef str c_buy(self, str trading_pair, object amount, object order_type=OrderType.LIMIT, object price=s_decimal_NaN,
                   dict kwargs={}):
        cdef:
            int64_t tracking_nonce = <int64_t> get_tracking_nonce()
            str order_id = str(f"buy-{trading_pair}-{tracking_nonce}")
        safe_ensure_future(self.execute_buy(order_id, trading_pair, amount, order_type, price=price))
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

        try:
            order_result = None
            order_decimal_amount = f"{decimal_amount:f}"
            if order_type is OrderType.LIMIT:
                order_decimal_price = f"{decimal_price:f}"
                order_result = await self.place_order(trading_pair=trading_pair,
                                                      amount=order_decimal_amount,
                                                      order_type=order_type,
                                                      is_buy=False,
                                                      price=order_decimal_price)

                exchange_order_id = order_result["data"]["id"]

                self.c_start_tracking_order(
                    order_id,
                    exchange_order_id,
                    trading_pair,
                    TradeType.SELL,
                    decimal_price,
                    decimal_amount,
                    order_type,
                )

            else:
                raise ValueError(f"Invalid OrderType {order_type}. Aborting.")


            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(f"Created {order_type} sell order {order_id} for "
                                   f"{decimal_amount} {trading_pair}.")
                tracked_order.exchange_order_id = exchange_order_id

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
            order_type_str = 'LIMIT'
            self.logger().network(
                f"Error submitting sell {order_type_str} order to Stex for "
                f"{decimal_amount} {trading_pair} "
                f"{decimal_price}.",
                exc_info=True,
                app_warning_msg=f"Failed to submit sell order to Stex. Check API key and network connection."
            )
            self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                 MarketOrderFailureEvent(self._current_timestamp, order_id, order_type))

    cdef str c_sell(self, str trading_pair, object amount, object order_type=OrderType.LIMIT, object price=s_decimal_NaN,dict kwargs={}):
        cdef:
            int64_t tracking_nonce = <int64_t> get_tracking_nonce()
            str order_id = str(f"sell-{trading_pair}-{tracking_nonce}")
        safe_ensure_future(self.execute_sell(order_id, trading_pair, amount, order_type, price=price))
        return order_id

    async def execute_cancel(self, trading_pair: str, order_id: str):
        try:
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is None:
                raise ValueError(f"Failed to cancel order – {order_id}. Order not found.")

            path_url = "/trading/order/" + str(order_id)

            cancel_result = await self._api_request(method="DELETE",
                                                    path_url=path_url,
                                                    is_auth_required=True
                                                    )
            accepted_orders = cancel_result["data"]["put_into_processing_queue"]
            rejected_orders = cancel_result["data"]["not_put_into_processing_queue"]

            if cancel_result["success"]==False or (len(accepted_orders)==0 and len(rejected_orders)==0):
                self.logger().warning(f"Error cancelling order on Stex",exc_info=True)
            else:
                self.c_stop_tracking_order(order_id)
                self.logger().info(f"Successfully cancelled order {order_id}.")
                self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                     OrderCancelledEvent(self._current_timestamp,order_id))
            return {"origClientOrderId": order_id}

        except Exception as e:
            self.logger().warning(f"Error cancelling order on Kraken",
                                  exc_info=True)

    cdef c_cancel(self, str trading_pair, str order_id):
        safe_ensure_future(self.execute_cancel(trading_pair, order_id))
        return order_id

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        incomplete_orders = [(key, o) for (key, o) in self._in_flight_orders.items() if not o.is_done]
        tasks = [self.execute_cancel(o.trading_pair, key) for (key, o) in incomplete_orders]
        order_id_set = set([key for (key, o) in incomplete_orders])
        successful_cancellations = []

        try:
            async with timeout(timeout_seconds):
                cancellation_results = await safe_gather(*tasks, return_exceptions=True)
                for cr in cancellation_results:
                    if isinstance(cr, Exception):
                        continue
                    if isinstance(cr, dict) and "origClientOrderId" in cr:
                        client_order_id = cr.get("origClientOrderId")
                        order_id_set.remove(client_order_id)
                        successful_cancellations.append(CancellationResult(client_order_id, True))

        except Exception:
            self.logger().network(
                f"Unexpected error cancelling orders.",
                exc_info=True,
                app_warning_msg="Failed to cancel order with Stex. Check API key and network connection."
            )

        failed_cancellations = [CancellationResult(oid, False) for oid in order_id_set]
        return successful_cancellations + failed_cancellations

    cdef OrderBook c_get_order_book(self, str trading_pair):
        cdef:
            dict order_books = self._order_book_tracker.order_books

        if trading_pair not in order_books:
            raise ValueError(f"No order book exists for '{trading_pair}'.")
        return order_books[trading_pair]

    cdef c_did_timeout_tx(self, str tracking_id):
        self.c_trigger_event(self.MARKET_TRANSACTION_FAILURE_EVENT_TAG,
                             MarketTransactionFailureEvent(self._current_timestamp, tracking_id))

    cdef c_start_tracking_order(self,
                                str order_id,
                                str exchange_order_id,
                                str trading_pair,
                                object trade_type,
                                object price,
                                object amount,
                                object order_type):
        self._in_flight_orders[order_id] = StexInFlightOrder(
            client_order_id=order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=trading_pair,
            trade_type=trade_type,
            price=price,
            amount=amount,
            order_type=order_type,
        )

    cdef c_stop_tracking_order(self, str order_id):
        if order_id in self._in_flight_orders:
            del self._in_flight_orders[order_id]
        if order_id in self._order_not_found_records:
            del self._order_not_found_records[order_id]

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

        global s_decimal_0
        if quantized_amount < trading_rule.min_order_size:
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
