import aiohttp
import asyncio
from async_timeout import timeout
from decimal import Decimal
import json
import logging
import pandas as pd
import time
from typing import (
    Any,
    Dict,
    List,
    Optional,
    AsyncIterable,
)
from libc.stdint cimport int64_t

from hummingbot.core.clock cimport Clock
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book_tracker import OrderBookTrackerDataSourceType
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.core.data_type.transaction_tracker import TransactionTracker
from hummingbot.core.event.events import (
    TradeType,
    TradeFee,
    MarketEvent,
    BuyOrderCompletedEvent,
    SellOrderCompletedEvent,
    OrderFilledEvent,
    OrderCancelledEvent,
    BuyOrderCreatedEvent,
    SellOrderCreatedEvent,
    MarketWithdrawAssetEvent,
    MarketTransactionFailureEvent,
    MarketOrderFailureEvent
)
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.logger import HummingbotLogger
from hummingbot.market.coinbase_pro.coinbase_pro_auth import CoinbaseProAuth
from hummingbot.market.coinbase_pro.coinbase_pro_order_book_tracker import CoinbaseProOrderBookTracker
from hummingbot.market.coinbase_pro.coinbase_pro_user_stream_tracker import CoinbaseProUserStreamTracker
from hummingbot.market.coinbase_pro.coinbase_pro_api_order_book_data_source import CoinbaseProAPIOrderBookDataSource
from hummingbot.market.deposit_info import DepositInfo
from hummingbot.market.market_base import (
    MarketBase,
    OrderType,
)
from hummingbot.market.trading_rule cimport TradingRule
from hummingbot.market.coinbase_pro.coinbase_pro_in_flight_order import CoinbaseProInFlightOrder
from hummingbot.market.coinbase_pro.coinbase_pro_in_flight_order cimport CoinbaseProInFlightOrder


s_logger = None
s_decimal_0 = Decimal(0)


cdef class CoinbaseProMarketTransactionTracker(TransactionTracker):
    cdef:
        CoinbaseProMarket _owner

    def __init__(self, owner: CoinbaseProMarket):
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
        public object amount
        public str currency
        public bint has_tx_receipt

    def __init__(self, tracking_id: str, tx_hash: str, from_address: str, to_address: str, amount: Decimal, currency: str):
        self.tracking_id = tracking_id
        self.timestamp_ms = int(time.time() * 1000)
        self.tx_hash = tx_hash
        self.from_address = from_address
        self.to_address = to_address
        self.amount = amount
        self.currency = currency
        self.has_tx_receipt = False

    def __repr__(self) -> str:
        return f"InFlightDeposit(tracking_id='{self.tracking_id}', timestamp_ms={self.timestamp_ms}, " \
        f"tx_hash='{self.tx_hash}', has_tx_receipt={self.has_tx_receipt})"


cdef class CoinbaseProMarket(MarketBase):
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
    UPDATE_ORDERS_INTERVAL = 10.0

    COINBASE_API_ENDPOINT = "https://api.pro.coinbase.com"

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(__name__)
        return s_logger

    def __init__(self,
                 coinbase_pro_api_key: str,
                 coinbase_pro_secret_key: str,
                 coinbase_pro_passphrase: str,
                 poll_interval: float = 5.0,
                 order_book_tracker_data_source_type: OrderBookTrackerDataSourceType =
                    OrderBookTrackerDataSourceType.EXCHANGE_API,
                 symbols: Optional[List[str]] = None,
                 trading_required: bool = True):
        super().__init__()
        self._trading_required = trading_required
        self._coinbase_auth = CoinbaseProAuth(coinbase_pro_api_key, coinbase_pro_secret_key, coinbase_pro_passphrase)
        self._order_book_tracker = CoinbaseProOrderBookTracker(data_source_type=order_book_tracker_data_source_type,
                                                               symbols=symbols)
        self._user_stream_tracker = CoinbaseProUserStreamTracker(coinbase_pro_auth=self._coinbase_auth,
                                                                 symbols=symbols)
        self._account_balances = {}
        self._account_available_balances = {}
        self._ev_loop = asyncio.get_event_loop()
        self._poll_notifier = asyncio.Event()
        self._last_timestamp = 0
        self._last_order_update_timestamp = 0
        self._poll_interval = poll_interval
        self._in_flight_orders = {}
        self._tx_tracker = CoinbaseProMarketTransactionTracker(self)
        self._trading_rules = {}
        self._data_source_type = order_book_tracker_data_source_type
        self._status_polling_task = None
        self._order_tracker_task = None
        self._user_stream_tracker_task = None
        self._user_stream_event_listener_task = None
        self._trading_rules_polling_task = None
        self._shared_client = None

    @property
    def name(self) -> str:
        return "coinbase_pro"

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        return self._order_book_tracker.order_books

    @property
    def coinbase_auth(self) -> CoinbaseProAuth:
        return self._coinbase_auth

    @property
    def status_dict(self) -> Dict[str, bool]:
        return {
            "order_books_initialized": len(self._order_book_tracker.order_books) > 0,
            "account_balance": len(self._account_balances) > 0 if self._trading_required else True,
            "trading_rule_initialized": len(self._trading_rules) > 0 if self._trading_required else True
        }

    @property
    def ready(self) -> bool:
        return all(self.status_dict.values())

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
            key: CoinbaseProInFlightOrder.from_json(value)
            for key, value in saved_states.items()
        })

    async def get_active_exchange_markets(self) -> pd.DataFrame:
        return await CoinbaseProAPIOrderBookDataSource.get_active_exchange_markets()

    def get_all_balances(self) -> Dict[str, float]:
        return self._account_balances.copy()

    cdef c_start(self, Clock clock, double timestamp):
        self._tx_tracker.c_start(clock, timestamp)
        MarketBase.c_start(self, clock, timestamp)

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
        self._order_tracker_task = self._status_polling_task = self._user_stream_tracker_task = \
            self._user_stream_event_listener_task = None

    async def stop_network(self):
        self._stop_network()

    async def check_network(self) -> NetworkStatus:
        try:
            await self._api_request("get", path_url="/time")
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
        if current_tick > last_tick:
            if not self._poll_notifier.is_set():
                self._poll_notifier.set()
        self._last_timestamp = timestamp

    async def _http_client(self) -> aiohttp.ClientSession:
        if self._shared_client is None:
            self._shared_client = aiohttp.ClientSession()
        return self._shared_client

    async def _api_request(self,
                           http_method: str,
                           path_url: str = None,
                           url: str = None,
                           data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        assert path_url is not None or url is not None

        url = f"{self.COINBASE_API_ENDPOINT}{path_url}" if url is None else url
        data_str = "" if data is None else json.dumps(data)
        headers = self.coinbase_auth.get_headers(http_method, path_url, data_str)

        client = await self._http_client()
        async with client.request(http_method,
                                  url=url, timeout=self.API_CALL_TIMEOUT, data=data_str, headers=headers) as response:
            data = await response.json()
            if response.status != 200:
                raise IOError(f"Error fetching data from {url}. HTTP status is {response.status}. {data}")
            return data

    cdef object c_get_fee(self,
                          str base_currency,
                          str quote_currency,
                          object order_type,
                          object order_side,
                          double amount,
                          double price):
        # There is no API for checking user's fee tier
        # Fee info from https://pro.coinbase.com/fees
        cdef:
            double maker_fee = 0.0015
            double taker_fee = 0.0025

        return TradeFee(percent=maker_fee if order_type is OrderType.LIMIT else taker_fee)

    async def _update_balances(self):
        cdef:
            dict account_info
            list balances
            str asset_name
            set local_asset_names = set(self._account_balances.keys())
            set remote_asset_names = set()
            set asset_names_to_remove

        path_url = "/accounts"
        account_balances = await self._api_request("get", path_url=path_url)

        for balance_entry in account_balances:
            asset_name = balance_entry["currency"]
            available_balance = Decimal(balance_entry["available"])
            total_balance = Decimal(balance_entry["balance"])
            self._account_available_balances[asset_name] = available_balance
            self._account_balances[asset_name] = total_balance
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    async def _update_trading_rules(self):
        cdef:
            # The poll interval for withdraw rules is 60 seconds.
            int64_t last_tick = <int64_t>(self._last_timestamp / 60.0)
            int64_t current_tick = <int64_t>(self._current_timestamp / 60.0)
        if current_tick > last_tick or len(self._trading_rules) <= 0:
            product_info = await self._api_request("get", path_url="/products")
            trading_rules_list = self._format_trading_rules(product_info)
            self._trading_rules.clear()
            for trading_rule in trading_rules_list:
                self._trading_rules[trading_rule.symbol] = trading_rule

    def _format_trading_rules(self, raw_trading_rules: List[Any]) -> List[TradingRule]:
        cdef:
            list retval = []
        for rule in raw_trading_rules:
            try:
                symbol = rule.get("id")
                retval.append(TradingRule(symbol,
                                          min_price_increment=Decimal(rule.get("quote_increment")),
                                          min_order_size=Decimal(rule.get("base_min_size")),
                                          max_order_size=Decimal(rule.get("base_max_size")),
                                          supports_market_orders=(not rule.get("limit_only"))))
            except Exception:
                self.logger().error(f"Error parsing the symbol rule {rule}. Skipping.", exc_info=True)
        return retval

    async def _update_order_status(self):
        cdef:
            double current_timestamp = self._current_timestamp

        if current_timestamp - self._last_order_update_timestamp <= self.UPDATE_ORDERS_INTERVAL:
            return

        tracked_orders = list(self._in_flight_orders.values())
        results = await self.list_orders()
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

            # Update the tracked order
            tracked_order.last_state = done_reason if done_reason in {"filled", "canceled"} else order_update["status"]
            tracked_order.executed_amount_base = new_confirmed_amount
            tracked_order.executed_amount_quote = Decimal(order_update["executed_value"])
            tracked_order.fee_paid = Decimal(order_update["fill_fees"])
            if tracked_order.is_done:
                if not tracked_order.is_failure:
                    if tracked_order.trade_type == TradeType.BUY:
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
                                                                    order_type))
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
                                                                     order_type))
                else:
                    self.logger().info(f"The market order {tracked_order.client_order_id} has failed according to "
                                       f"order status API.")
                    self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                         MarketOrderFailureEvent(
                                             self._current_timestamp,
                                             tracked_order.client_order_id,
                                             order_type
                                         ))
                self.c_stop_tracking_order(tracked_order.client_order_id)
        self._last_order_update_timestamp = current_timestamp

    async def _iter_user_event_queue(self) -> AsyncIterable[Dict[str, Any]]:
        while True:
            try:
                yield await self._user_stream_tracker.user_stream.get()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unknown error. Retrying after 1 seconds.", exc_info=True)
                await asyncio.sleep(1.0)

    async def _user_stream_event_listener(self):
        async for event_message in self._iter_user_event_queue():
            try:
                content = event_message.content
                event_type = content.get("type")
                exchange_order_ids = [content.get("order_id"),
                                      content.get("maker_order_id"),
                                      content.get("taker_order_id")]

                tracked_order = None
                for order in self._in_flight_orders.values():
                    if order.exchange_order_id in exchange_order_ids:
                        tracked_order = order
                        break

                if tracked_order is None:
                    continue

                order_type_description = tracked_order.order_type_description
                execute_price = Decimal(content.get("price", 0.0))
                execute_amount_diff = s_decimal_0

                if event_type == "open":
                    remaining_size = Decimal(content.get("remaining_size"))
                    new_confirmed_amount = tracked_order.amount - remaining_size
                    execute_amount_diff = new_confirmed_amount - tracked_order.executed_amount_base
                    tracked_order.executed_amount_base = new_confirmed_amount
                    tracked_order.executed_amount_quote += execute_amount_diff * execute_price
                elif event_type == "done":
                    remaining_size = Decimal(content.get("remaining_size", 0.0))
                    reason = content.get("reason")
                    if reason == "filled":
                        new_confirmed_amount = tracked_order.amount - remaining_size
                        execute_amount_diff = new_confirmed_amount - tracked_order.executed_amount_base
                        tracked_order.executed_amount_base = new_confirmed_amount
                        tracked_order.executed_amount_quote += execute_amount_diff * execute_price
                        tracked_order.last_state = "done"

                        if tracked_order.trade_type == TradeType.BUY:
                            self.logger().info(f"The market buy order {tracked_order.client_order_id} has completed "
                                               f"according to Coinbase Pro user stream.")
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
                                               f"according to Coinbase Pro user stream.")
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
                        tracked_order.last_state = "canceled"
                        self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                            OrderCancelledEvent(self._current_timestamp, tracked_order.client_order_id))
                        execute_amount_diff = 0
                    self.c_stop_tracking_order(tracked_order.client_order_id)
                elif event_type == "match":
                    execute_amount_diff = Decimal(content.get("size", 0.0))
                    tracked_order.executed_amount_base += execute_amount_diff
                    tracked_order.executed_amount_quote += execute_amount_diff * execute_price
                elif event_type == "change":
                    if content.get("new_size") is not None:
                        tracked_order.amount = Decimal(content.get("new_size", 0.0))
                    elif content.get("new_funds") is not None:
                        if tracked_order.price is not s_decimal_0:
                            tracked_order.amount = Decimal(content.get("new_funds")) / tracked_order.price
                    else:
                        self.logger().error(f"Invalid change message - '{content}'. Aborting.")

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

    async def place_order(self, order_id: str, symbol: str, amount: Decimal, is_buy: bool, order_type: OrderType,
                          price: float):
        path_url = "/orders"
        data = {
            "price": price,
            "size": float(amount),
            "product_id": symbol,
            "side": "buy" if is_buy else "sell",
            "type": "limit" if order_type is OrderType.LIMIT else "market",
        }

        order_result = await self._api_request("post", path_url=path_url, data=data)
        return order_result

    async def execute_buy(self,
                          order_id: str,
                          symbol: str,
                          amount: float,
                          order_type: OrderType,
                          price: Optional[float] = None):
        cdef:
            TradingRule trading_rule = self._trading_rules[symbol]

        decimal_amount = self.quantize_order_amount(symbol, amount)
        decimal_price = self.quantize_order_price(symbol, price)
        if decimal_amount < trading_rule.min_order_size:
            raise ValueError(f"Buy order amount {decimal_amount} is lower than the minimum order size "
                             f"{trading_rule.min_order_size}.")

        try:
            self.c_start_tracking_order(order_id, symbol, order_type, TradeType.BUY, decimal_price, decimal_amount)
            order_result = await self.place_order(order_id, symbol, decimal_amount, True, order_type, decimal_price)

            exchange_order_id = order_result["id"]
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(f"Created {order_type} buy order {order_id} for {decimal_amount} {symbol}.")
                tracked_order.update_exchange_order_id(exchange_order_id)

            self.c_trigger_event(self.MARKET_BUY_ORDER_CREATED_EVENT_TAG,
                                 BuyOrderCreatedEvent(self._current_timestamp,
                                                      order_type,
                                                      symbol,
                                                      float(decimal_amount),
                                                      float(decimal_price),
                                                      order_id))
        except asyncio.CancelledError:
            raise
        except Exception:
            self.c_stop_tracking_order(order_id)
            order_type_str = "MARKET" if order_type == OrderType.MARKET else "LIMIT"
            self.logger().network(
                f"Error submitting buy {order_type_str} order to Coinbase Pro for "
                f"{decimal_amount} {symbol} {price}.",
                exc_info=True,
                app_warning_msg="Failed to submit buy order to Coinbase Pro. "
                                "Check API key and network connection."
            )
            self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                 MarketOrderFailureEvent(self._current_timestamp, order_id, order_type))

    cdef str c_buy(self, str symbol, double amount, object order_type = OrderType.MARKET, double price = 0.0,
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
                           price: Optional[float] = None):
        cdef:
            TradingRule trading_rule = self._trading_rules[symbol]

        decimal_amount = self.quantize_order_amount(symbol, amount)
        decimal_price = self.quantize_order_price(symbol, price)
        if decimal_amount < trading_rule.min_order_size:
            raise ValueError(f"Sell order amount {decimal_amount} is lower than the minimum order size "
                             f"{trading_rule.min_order_size}.")

        try:
            self.c_start_tracking_order(order_id, symbol, order_type, TradeType.SELL, decimal_price, decimal_amount)
            order_result = await self.place_order(order_id, symbol, decimal_amount, False, order_type, decimal_price)

            exchange_order_id = order_result["id"]
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(f"Created {order_type} sell order {order_id} for {decimal_amount} {symbol}.")
                tracked_order.update_exchange_order_id(exchange_order_id)

            self.c_trigger_event(self.MARKET_SELL_ORDER_CREATED_EVENT_TAG,
                                 SellOrderCreatedEvent(self._current_timestamp,
                                                       order_type,
                                                       symbol,
                                                       float(decimal_amount),
                                                       float(decimal_price),
                                                       order_id))
        except asyncio.CancelledError:
            raise
        except Exception:
            self.c_stop_tracking_order(order_id)
            order_type_str = "MARKET" if order_type == OrderType.MARKET else "LIMIT"
            self.logger().network(
                f"Error submitting sell {order_type_str} order to Coinbase Pro for "
                f"{decimal_amount} {symbol} {price}.",
                exc_info=True,
                app_warning_msg="Failed to submit sell order to Coinbase Pro. "
                                "Check API key and network connection."
            )
            self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                 MarketOrderFailureEvent(self._current_timestamp, order_id, order_type))

    cdef str c_sell(self, str symbol, double amount, object order_type = OrderType.MARKET, double price = 0.0,
                    dict kwargs = {}):
        cdef:
            int64_t tracking_nonce = <int64_t>(time.time() * 1e6)
            str order_id = str(f"sell-{symbol}-{tracking_nonce}")
        asyncio.ensure_future(self.execute_sell(order_id, symbol, amount, order_type, price))
        return order_id

    async def execute_cancel(self, symbol: str, order_id: str):
        try:
            exchange_order_id = await self._in_flight_orders.get(order_id).get_exchange_order_id()
            path_url = f"/orders/{exchange_order_id}"
            [cancelled_id] = await self._api_request("delete", path_url=path_url)
            if cancelled_id == exchange_order_id:
                self.logger().info(f"Successfully cancelled order {order_id}.")
                self.c_stop_tracking_order(order_id)
                self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                     OrderCancelledEvent(self._current_timestamp, order_id))
                return order_id
        except IOError as e:
            if "order not found" in e.message:
                # The order was never there to begin with. So cancelling it is a no-op but semantically successful.
                self.logger().info(f"The order {order_id} does not exist on Coinbase Pro. No cancellation needed.")
                self.c_stop_tracking_order(order_id)
                self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                     OrderCancelledEvent(self._current_timestamp, order_id))
                return order_id
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(
                f"Failed to cancel order {order_id}: {str(e)}",
                exc_info=True,
                app_warning_msg=f"Failed to cancel the order {order_id} on Coinbase Pro. "
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
                app_warning_msg="Failed to cancel order on Coinbase Pro. Check API key and network connection."
            )

        failed_cancellations = [CancellationResult(oid, False) for oid in order_id_set]
        return successful_cancellations + failed_cancellations

    async def get_active_exchange_markets(self):
        return await CoinbaseProAPIOrderBookDataSource.get_active_exchange_markets()

    async def _status_polling_loop(self):
        while True:
            try:
                self._poll_notifier = asyncio.Event()
                await self._poll_notifier.wait()

                await asyncio.gather(
                    self._update_balances(),
                    self._update_order_status(),
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unexpected error while fetching account updates.",
                    exc_info=True,
                    app_warning_msg=f"Could not fetch account updates on Coinbase Pro. "
                                    f"Check API key and network connection."
                )

    async def _trading_rules_polling_loop(self):
        while True:
            try:
                await asyncio.gather(self._update_trading_rules())
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unexpected error while fetching trading rules.",
                    exc_info=True,
                    app_warning_msg=f"Could not fetch trading rule updates on Coinbase Pro. "
                                    f"Check network connection."
                )
                await asyncio.sleep(0.5)

    async def get_order(self, client_order_id: str) -> Dict[str, Any]:
        order = self._in_flight_orders.get(client_order_id)
        exchange_order_id = await order.get_exchange_order_id()
        path_url = f"/orders/{exchange_order_id}"
        result = await self._api_request("get", path_url=path_url)
        return result

    async def list_orders(self) -> List[Any]:
        path_url = "/orders?status=all"
        result = await self._api_request("get", path_url=path_url)
        return result

    async def get_transfers(self) -> Dict[str, Any]:
        path_url = "/transfers"
        result = await self._api_request("get", path_url=path_url)
        return result

    async def list_coinbase_accounts(self) -> Dict[str, str]:
        path_url = "/coinbase-accounts"
        coinbase_accounts = await self._api_request("get", path_url=path_url)
        ids = [a["id"] for a in coinbase_accounts]
        currencies = [a["currency"] for a in coinbase_accounts]
        return dict(zip(currencies, ids))

    async def get_deposit_address(self, asset: str) -> str:
        coinbase_account_id_dict = await self.list_coinbase_accounts()
        account_id = coinbase_account_id_dict.get(asset)
        path_url = f"/coinbase-accounts/{account_id}/addresses"
        deposit_result = await self._api_request("post", path_url=path_url)
        return deposit_result.get("address")

    async def get_deposit_info(self, asset: str) -> DepositInfo:
        return DepositInfo(await self.get_deposit_address(asset))

    async def execute_withdraw(self, str tracking_id, str to_address, str currency, double amount):
        path_url = "/withdrawals/crypto"
        data = {
            "amount": amount,
            "currency": currency,
            "crypto_address": to_address,
            "no_destination_tag": True,
        }
        try:
            withdraw_result = await self._api_request("post", path_url=path_url, data=data)
            self.logger().info(f"Successfully withdrew {amount} of {currency}. {withdraw_result}")
            # Withdrawing of digital assets from Coinbase Pro is currently free
            withdraw_fee = 0.0
            # Currently, we assume when coinbase accepts the API request, the withdraw is valid
            # In the future, if the confirmation of the withdrawal becomes more essential,
            # we can perform status check by using self.get_transfers()
            self.c_trigger_event(self.MARKET_WITHDRAW_ASSET_EVENT_TAG,
                                 MarketWithdrawAssetEvent(self._current_timestamp, tracking_id, to_address, currency,
                                                          float(amount), float(withdraw_fee)))
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(
                f"Error sending withdraw request to Coinbase Pro for {currency}.",
                exc_info=True,
                app_warning_msg=f"Failed to issue withdrawal request for {currency} from Coinbase Pro. "
                                f"Check API key and network connection."
            )
            self.c_trigger_event(self.MARKET_TRANSACTION_FAILURE_EVENT_TAG,
                                 MarketTransactionFailureEvent(self._current_timestamp, tracking_id))

    cdef str c_withdraw(self, str to_address, str currency, double amount):
        cdef:
            int64_t tracking_nonce = <int64_t>(time.time() * 1e6)
            str tracking_id = str(f"withdraw://{currency}/{tracking_nonce}")
        asyncio.ensure_future(self.execute_withdraw(tracking_id, to_address, currency, amount))
        return tracking_id

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

    cdef c_start_tracking_order(self,
                                str client_order_id,
                                str symbol,
                                object order_type,
                                object trade_type,
                                object price,
                                object amount):
        self._in_flight_orders[client_order_id] = CoinbaseProInFlightOrder(
            client_order_id,
            "",
            symbol,
            order_type,
            trade_type,
            price,
            amount,
        )

    cdef c_stop_tracking_order(self, str order_id):
        if order_id in self._in_flight_orders:
            del self._in_flight_orders[order_id]

    cdef c_did_timeout_tx(self, str tracking_id):
        self.c_trigger_event(self.MARKET_TRANSACTION_FAILURE_EVENT_TAG,
                             MarketTransactionFailureEvent(self._current_timestamp, tracking_id))

    cdef object c_get_order_price_quantum(self, str symbol, double price):
        cdef:
            TradingRule trading_rule = self._trading_rules[symbol]
        return trading_rule.min_price_increment

    cdef object c_get_order_size_quantum(self, str symbol, double order_size):
        cdef:
            TradingRule trading_rule = self._trading_rules[symbol]

        # Coinbase Pro is using the min_order_size as max_precision
        # Order size must be a multiple of the min_order_size
        return trading_rule.min_order_size

    cdef object c_quantize_order_amount(self, str symbol, double amount, double price=0.0):
        cdef:
            TradingRule trading_rule = self._trading_rules[symbol]

        global s_decimal_0
        quantized_amount = MarketBase.c_quantize_order_amount(self, symbol, amount)

        # Check against min_order_size. If not passing either check, return 0.
        if quantized_amount < trading_rule.min_order_size:
            return s_decimal_0

        # Check against max_order_size. If not passing either check, return 0.
        if quantized_amount > trading_rule.max_order_size:
            return s_decimal_0

        return quantized_amount
