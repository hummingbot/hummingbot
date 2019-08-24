import aiohttp
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
from hummingbot.core.data_type.user_stream_tracker import UserStreamTrackerDataSourceType
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
from hummingbot.logger import HummingbotLogger
from hummingbot.market.huobi.huobi_api_order_book_data_source import HuobiAPIOrderBookDataSource
from hummingbot.market.huobi.huobi_auth import HuobiAuth
from hummingbot.market.huobi.huobi_in_flight_order import HuobiInFlightOrder
from hummingbot.market.huobi.huobi_order_book_tracker import HuobiOrderBookTracker
# from hummingbot.market.huobi.huobi_user_stream_tracker import HuobiUserStreamTracker
from hummingbot.market.trading_rule cimport TradingRule
from hummingbot.market.market_base import (
    MarketBase,
    NaN
)

hm_logger = None
s_decimal_0 = Decimal(0)
SYMBOL_SPLITTER = re.compile(r"^(\w+)(usdt|husd|btc|eth|ht|trx)$")
HUOBI_ROOT_API = "https://api.huobi.pro/v1/"


cdef class HuobiMarketTransactionTracker(TransactionTracker):
    cdef:
        HuobiMarket _owner

    def __init__(self, owner: HuobiMarket):
        super().__init__()
        self._owner = owner

    cdef c_did_timeout_tx(self, str tx_id):
        TransactionTracker.c_did_timeout_tx(self, tx_id)
        self._owner.c_did_timeout_tx(tx_id)


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
    API_CALL_TIMEOUT = 10.0

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global hm_logger
        if hm_logger is None:
            hm_logger = logging.getLogger(__name__)
        return hm_logger

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
        self._account_available_balances = {}
        self._account_balances = {}
        self._account_id = ""
        self._async_scheduler = AsyncCallScheduler(call_interval=0.5)
        self._data_source_type = order_book_tracker_data_source_type
        self._ev_loop = asyncio.get_event_loop()
        self._huobi_auth = HuobiAuth(api_key=huobi_api_key, secret_key=huobi_secret_key)
        self._in_flight_orders = {}
        self._last_pull_timestamp = 0
        self._last_timestamp = 0
        self._order_book_tracker = HuobiOrderBookTracker(
            data_source_type=order_book_tracker_data_source_type,
            symbols=symbols
        )
        self._order_tracker_task = None
        self._poll_notifier = asyncio.Event()
        self._poll_interval = poll_interval
        self._shared_client = None
        self._status_polling_task = None
        self._trading_required = trading_required
        self._trading_rules = {}
        self._trading_rules_polling_task = None
        self._tx_tracker = HuobiMarketTransactionTracker(self)
        # self._user_stream_tracker = HuobiUserStreamTracker(
        #     huobi_auth=self._huobi_auth,
        #     data_source_type=user_stream_tracker_data_source_type
        # )
        self._user_stream_event_listener_task = None
        self._user_stream_tracker_task = None

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
    def tracking_states(self) -> Dict[str, Any]:
        return {
            key: value.to_json()
            for key, value in self._in_flight_orders.items()
        }

    def restore_tracking_states(self, saved_states: Dict[str, Any]):
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
            await self._update_account_id()
            self._status_polling_task = asyncio.ensure_future(self._status_polling_loop())
            self._trading_rules_polling_task = asyncio.ensure_future(self._trading_rules_polling_loop())
            self._user_stream_tracker_task = asyncio.ensure_future(self._user_stream_tracker.start())
            self._user_stream_event_listener_task = asyncio.ensure_future(self._user_stream_event_listener())

    def _stop_network(self):
        if self._order_tracker_task is not None:
            self._order_tracker_task.cancel()
            self._order_tracker_task = None
        if self._status_polling_task is not None:
            self._status_polling_task.cancel()
            self._status_polling_task = None
        if self._user_stream_tracker_task is not None:
            self._user_stream_tracker_task.cancel()
            self._user_stream_tracker_task = None
        if self._user_stream_event_listener_task is not None:
            self._user_stream_event_listener_task.cancel()
            self._user_stream_event_listener_task = None
        if self._trading_rules_polling_task is not None:
            self._trading_rules_polling_task.cancel()
            self._trading_rules_polling_task = None

    async def stop_network(self):
        self._stop_network()

    async def check_network(self) -> NetworkStatus:
        try:
            await self.query_url(method="get", path_url="common/timestamp")
        except asyncio.CancelledError:
            raise
        except Exception as e:
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

    async def query_url(self,
                        method,
                        path_url,
                        params: Optional[Dict[str, Any]] = None,
                        data = None,
                        is_auth_required: bool = False) -> Dict[str, Any]:
        content_type = "application/json" if method == "post" else "application/x-www-form-urlencoded"
        headers = {"Content-Type": content_type}
        url = HUOBI_ROOT_API + path_url
        client = await self._http_client()
        if is_auth_required:
            params = self._huobi_auth.add_auth_to_params(method, path_url, params)
        async with client.request(method=method,
                                  url=url,
                                  headers=headers,
                                  params=params,
                                  data=ujson.dumps(data),
                                  timeout=self.API_CALL_TIMEOUT) as response:
            if response.status != 200:
                raise IOError(f"Error fetching data from {url}. HTTP status is {response.status}.")
            try:
                parsed_response = await response.json()
            except Exception:
                raise IOError(f"Error parsing data from {url}.")

            data = parsed_response.get("data")
            if data is None:
                raise IOError(f"Error reading data from {url}. Response is {parsed_response}.")
            return parsed_response["data"]

    async def _update_account_id(self) -> str:
        accounts = await self.query_url("get", path_url="account/accounts", is_auth_required=True)
        try:
            for account in accounts:
                if account["state"] == "working" and account["type"] == "spot":
                    self._account_id = str(account["id"])
        except Exception as e:
            raise ValueError(f"Unable to retrieve account id: {e}")

    async def _update_balances(self):
        cdef:
            str path_url = f"account/accounts/{self._account_id}/balance"
            dict data = await self.query_url("get", path_url=path_url, is_auth_required=True)
            list balances = data.get("list", [])
            dict new_available_balances = {}
            dict new_balances = {}
            str asset_name
            object balance

        if len(balances) > 0:
            for balance_entry in balances:
                asset_name = balance_entry["currency"]
                balance = Decimal(balance_entry["balance"])
                if balance == s_decimal_0:
                    continue
                if asset_name not in new_available_balances:
                    new_available_balances[asset_name] = s_decimal_0
                if asset_name not in new_balances:
                    new_balances[asset_name] = s_decimal_0

                new_balances[asset_name] += balance
                if balance_entry["type"] == "trade":
                    new_available_balances[asset_name] = balance

            self._account_available_balances.clear()
            self._account_available_balances = new_available_balances
            self._account_balances.clear()
            self._account_balances = new_balances

    cdef object c_get_fee(self,
                          str base_currency,
                          str quote_currency,
                          object order_type,
                          object order_side,
                          double amount,
                          double price):
        # https://www.hbg.com/en-us/about/fee/
        return TradeFee(percent=0.002)

    async def _update_trading_rules(self):
        cdef:
            # The poll interval for trade rules is 60 seconds.
            int64_t last_tick = <int64_t>(self._last_timestamp / 60.0)
            int64_t current_tick = <int64_t>(self._current_timestamp / 60.0)
        if current_tick > last_tick or len(self._trading_rules) < 1:
            exchange_info = await self.query_url("get", path_url="common/symbols")
            trading_rules_list = self._format_trading_rules(exchange_info)
            self._trading_rules.clear()
            for trading_rule in trading_rules_list:
                self._trading_rules[trading_rule.symbol] = trading_rule

    def _format_trading_rules(self, raw_symbol_info: List[Dict[str, Any]]) -> List[TradingRule]:
        cdef:
            list trading_rules = []

        for info in raw_symbol_info:
            try:
                trading_rules.append(
                    TradingRule(symbol=info["symbol"],
                                min_order_size=Decimal(info["min-order-amt"]),
                                max_order_size=Decimal(info["max-order-amt"]),
                                min_price_increment=Decimal(f"1e-{info['price-precision']}"),
                                min_base_amount_increment=Decimal(f"1e-{info['amount-precision']}"),
                                min_quote_amount_increment=Decimal(f"1e-{info['value-precision']}"))
                )
            except Exception:
                self.logger().error(f"Error parsing the symbol rule {info}. Skipping.", exc_info=True)
        return trading_rules

    async def list_orders(self, symbol_set) -> List[Any]:
        path_url = "order/openOrders"
        result = []
        for symbol in symbol_set:
            params = {
                "account-id": int(self._account_id),
                "symbol": symbol
            }
            open_orders = await self.query_url("get", path_url, params, is_auth_required=True)
            for item in open_orders:
                result.append(item)
        return result

    async def get_order_status(self, exchange_order_id: str) -> Dict[str, Any]:
        """
        Example:
        {
            "id": 59378,
            "symbol": "ethusdt",
            "account-id": 100009,
            "amount": "10.1000000000",
            "price": "100.1000000000",
            "created-at": 1494901162595,
            "type": "buy-limit",
            "field-amount": "10.1000000000",
            "field-cash-amount": "1011.0100000000",
            "field-fees": "0.0202000000",
            "finished-at": 1494901400468,
            "user-id": 1000,
            "source": "api",
            "state": "filled",
            "canceled-at": 0,
            "exchange": "huobi",
            "batch": ""
        }
        """
        path_url = f"order/orders/{exchange_order_id}"
        return await self.query_url("get", path_url=path_url, is_auth_required=True)

    async def _update_order_status(self):
        cdef:
            # The poll interval for order status is 10 seconds.
            int64_t last_tick = <int64_t>(self._last_pull_timestamp / 10.0)
            int64_t current_tick = <int64_t>(self._current_timestamp / 10.0)

        if current_tick > last_tick and len(self._in_flight_orders) > 0:
            tracked_orders = list(self._in_flight_orders.values())
            for tracked_order in tracked_orders:
                exchange_order_id = await tracked_order.get_exchange_order_id()
                order_update = await self.get_order_status(exchange_order_id)
                if order_update is None:
                    self.logger().network(
                        f"Error fetching status update for the order {tracked_order.client_order_id}: "
                        f"{order_update}.",
                        app_warning_msg=f"Could not fetch updates for the order {tracked_order.client_order_id}. "
                                        f"The order has either been filled or canceled."
                    )
                    continue

                order_state = order_update["state"]
                if order_state == "submitted":
                    continue

                # Calculate the newly executed amount for this update.
                tracked_order.last_state = order_state
                new_confirmed_amount = Decimal(order_update["field-amount"])  # probably typo in API (filled)
                execute_amount_diff = new_confirmed_amount - tracked_order.executed_amount_base
                

                tracked_order.executed_amount_base = new_confirmed_amount
                tracked_order.executed_amount_quote = Decimal(order_update["field-cash-amount"])
                tracked_order.fee_paid = Decimal(order_update["field-fees"])

                if execute_amount_diff > s_decimal_0:
                    execute_price = Decimal(order_update["field-cash-amount"]) / new_confirmed_amount
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
                                        f"order {tracked_order.client_order_id}.")
                    self.c_trigger_event(self.MARKET_ORDER_FILLED_EVENT_TAG, order_filled_event)

                if order_state in ["canceled", "partially-canceled", "filled"]:
                    self.c_stop_tracking_order(tracked_order.client_order_id)
                    if tracked_order.executed_amount_base > s_decimal_0:
                        if tracked_order.trade_type is TradeType.BUY:
                            self.logger().info(f"The market buy order {tracked_order.client_order_id} has completed "
                                               f"according to order status API.")
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
                                               f"according to order status API.")
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
                    else:
                        self.logger().info(f"The market order {tracked_order.client_order_id} has been cancelled according"
                                           f" to order status API.")
                        self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                             OrderCancelledEvent(self._current_timestamp,
                                                                 tracked_order.client_order_id))

    async def _status_polling_loop(self):
        while True:
            try:
                self._poll_notifier = asyncio.Event()
                await self._poll_notifier.wait()

                await asyncio.gather(
                    self._update_balances(),
                    self._update_order_status(),
                )
                self._last_pull_timestamp = self._current_timestamp
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network("Unexpected error while fetching account updates.",
                                      exc_info=True,
                                      app_warning_msg="Could not fetch account updates from Huobi. "
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
                                      app_warning_msg="Could not fetch new trading rules from Huobi. "
                                                      "Check network connection.")
                await asyncio.sleep(0.5)

    @property
    def status_dict(self) -> Dict[str, bool]:
        return {
            "account_id_initialized": self._account_id != "",
            "order_books_initialized": len(self._order_book_tracker.order_books) > 0,
            "account_balance": len(self._account_balances) > 0 if self._trading_required else True,
            "trading_rule_initialized": len(self._trading_rules) > 0
        }

    @property
    def ready(self) -> bool:
        return all(self.status_dict.values())

    def get_all_balances(self) -> Dict[str, Decimal]:
        return self._account_balances.copy()

    async def place_order(self,
                          order_id: str,
                          symbol: str,
                          amount: Decimal,
                          is_buy: bool,
                          order_type: OrderType,
                          price: Decimal) -> str:
        path_url = "order/orders/place"
        side = "buy" if is_buy else "sell"
        order_type_str = "limit" if order_type is OrderType.LIMIT else "market"
        params = {
            "account-id": self._account_id,
            "amount": str(amount),
            "client-order-id": order_id,
            "symbol": symbol,
            "type": f"{side}-{order_type_str}",
        }
        if order_type is OrderType.LIMIT:
            params["price"] = str(price)
        exchange_order_id = await self.query_url(
            "post",
            path_url=path_url,
            params=params,
            data=params,
            is_auth_required=True
        )
        return str(exchange_order_id)

    async def execute_buy(self,
                          order_id: str,
                          symbol: str,
                          amount: float,
                          order_type: OrderType,
                          price: Optional[float] = NaN):
        cdef:
            TradingRule trading_rule = self._trading_rules[symbol]
            double quote_amount
            object decimal_amount
            object decimal_price
            str exchange_order_id
            object tracked_order

        if order_type is OrderType.MARKET:
            quote_amount = (<OrderBook>self.c_get_order_book(symbol)).c_get_quote_volume_for_base_amount(
                True, amount).result_volume
            # Quantize according to price rules, not base token amount rules.
            decimal_amount = self.c_quantize_order_price(symbol, quote_amount)
            decimal_price = s_decimal_0
        else:
            decimal_amount = self.c_quantize_order_amount(symbol, amount)
            decimal_price = self.c_quantize_order_price(symbol, price)
            if decimal_amount < trading_rule.min_order_size:
                raise ValueError(f"Buy order amount {decimal_amount} is lower than the minimum order size "
                                 f"{trading_rule.min_order_size}.")
        try:
            exchange_order_id = await self.place_order(order_id, symbol, decimal_amount, True, order_type, decimal_price)
            self.c_start_tracking_order(
                client_order_id=order_id,
                exchange_order_id=exchange_order_id,
                symbol=symbol,
                order_type=order_type,
                trade_type=TradeType.BUY,
                price=decimal_price,
                amount=decimal_amount
            )
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(f"Created {order_type} buy order {order_id} for {decimal_amount} {symbol}.")
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
            order_type_str = "MARKET" if order_type == OrderType.MARKET else "LIMIT"
            self.logger().network(
                f"Error submitting buy {order_type_str} order to Huobi for "
                f"{decimal_amount} {symbol} "
                f"{decimal_price if order_type is OrderType.LIMIT else ''}.",
                exc_info=True,
                app_warning_msg=f"Failed to submit buy order to Huobi. Check API key and network connection."
            )
            self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                 MarketOrderFailureEvent(self._current_timestamp, order_id, order_type))

    cdef str c_buy(self,
                   str symbol,
                   double amount,
                   object order_type = OrderType.MARKET,
                   double price = NaN,
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
            object decimal_amount
            object decimal_price
            str exchange_order_id
            object tracked_order

        decimal_amount = self.quantize_order_amount(symbol, amount)
        decimal_price = (self.c_quantize_order_price(symbol, price)
                         if order_type is OrderType.LIMIT
                         else s_decimal_0)
        if decimal_amount < trading_rule.min_order_size:
            raise ValueError(f"Sell order amount {decimal_amount} is lower than the minimum order size "
                             f"{trading_rule.min_order_size}.")

        try:
            exchange_order_id = await self.place_order(order_id, symbol, decimal_amount, False, order_type, decimal_price)
            self.c_start_tracking_order(
                client_order_id=order_id,
                exchange_order_id=exchange_order_id,
                symbol=symbol,
                order_type=order_type,
                trade_type=TradeType.SELL,
                price=decimal_price,
                amount=decimal_amount
            )
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(f"Created {order_type} sell order {order_id} for {decimal_amount} {symbol}.")
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
            order_type_str = "MARKET" if order_type is OrderType.MARKET else "LIMIT"
            self.logger().network(
                f"Error submitting sell {order_type_str} order to Huobi for "
                f"{decimal_amount} {symbol} "
                f"{decimal_price if order_type is OrderType.LIMIT else ''}.",
                exc_info=True,
                app_warning_msg=f"Failed to submit sell order to Huobi. Check API key and network connection."
            )
            self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                 MarketOrderFailureEvent(self._current_timestamp, order_id, order_type))

    cdef str c_sell(self,
                    str symbol,
                    double amount,
                    object order_type = OrderType.MARKET, double price = NaN,
                    dict kwargs = {}):
        cdef:
            int64_t tracking_nonce = <int64_t>(time.time() * 1e6)
            str order_id = str(f"sell-{symbol}-{tracking_nonce}")
        asyncio.ensure_future(self.execute_sell(order_id, symbol, amount, order_type, price))
        return order_id

    async def execute_cancel(self, symbol: str, order_id: str):
        tracked_order = self._in_flight_orders.get(order_id)
        if tracked_order is None:
            raise ValueError(f"Failed to cancel order - {order_id}. Order not found.")
        path_url = f"order/orders/{tracked_order.exchange_order_id}/submitcancel"
        try:
            await self.query_url("post", path_url=path_url, is_auth_required=True)
        except Exception as e:
            self.logger().network(
                f"Failed to cancel order {order_id}: {str(e)}",
                exc_info=True,
                app_warning_msg=f"Failed to cancel the order {order_id} on Huobi. "
                                f"Check API key and network connection."
            )

    cdef c_cancel(self, str symbol, str order_id):
        asyncio.ensure_future(self.execute_cancel(symbol, order_id))
        return order_id

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        incomplete_orders = [o for o in self._in_flight_orders.values() if not o.is_done]
        cancel_order_ids = [o.exchange_order_id for o in incomplete_orders]
        path_url = "order/orders/batchcancel"
        params = {"order-ids": ujson.dumps(cancel_order_ids)}
        data = {"order-ids": cancel_order_ids}
        # tasks = [self.execute_cancel(o.symbol, o.client_order_id) for o in incomplete_orders]
        # order_id_set = set([o.client_order_id for o in incomplete_orders])
        # successful_cancellations = []
        cancellation_results = []
        try:
            cancel_all_results = await self.query_url("post", path_url=path_url, params=params, data=data, is_auth_required=True)
            for oid in cancel_all_results["success"]:
                cancellation_results.append(CancellationResult(oid, True))
            for oid in cancel_all_results["failed"]:
                cancellation_results.append(CancellationResult(oid, False))
        except Exception as e:
            self.logger().network(
                f"Failed to cancel all orders: {cancel_order_ids}",
                exc_info=True,
                app_warning_msg=f"Failed to cancel all orders on Huobi. Check API key and network connection."
            )
        return cancellation_results

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
        return order_books.get(symbol)

    cdef c_did_timeout_tx(self, str tracking_id):
        self.c_trigger_event(self.MARKET_TRANSACTION_FAILURE_EVENT_TAG,
                             MarketTransactionFailureEvent(self._current_timestamp, tracking_id))

    cdef c_start_tracking_order(self,
                                str client_order_id,
                                str exchange_order_id,
                                str symbol,
                                object order_type,
                                object trade_type,
                                object price,
                                object amount):
        self._in_flight_orders[client_order_id] = HuobiInFlightOrder(
            client_order_id=client_order_id,
            exchange_order_id=exchange_order_id,
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
            object quantized_amount = MarketBase.c_quantize_order_amount(self, symbol, amount)

        # Check against min_order_size. If not passing check, return 0.
        if quantized_amount < trading_rule.min_order_size:
            return s_decimal_0

        # Check against max_order_size. If not passing check, return maximum.
        if quantized_amount > trading_rule.max_order_size:
            return trading_rule.max_order_size

        return quantized_amount
