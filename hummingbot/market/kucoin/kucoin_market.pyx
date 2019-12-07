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
from hummingbot.market.kucoin.kucoin_api_order_book_data_source import KucoinAPIOrderBookDataSource
from hummingbot.market.kucoin.kucoin_auth import KucoinAuth
from hummingbot.market.kucoin.kucoin_in_flight_order import KucoinInFlightOrder
from hummingbot.market.kucoin.kucoin_order_book_tracker import KucoinOrderBookTracker
from hummingbot.market.trading_rule cimport TradingRule
from hummingbot.market.market_base import (
    MarketBase,
    NaN,
    s_decimal_NaN)

hm_logger = None
s_decimal_0 = Decimal(0)
KUCOIN_ROOT_API = "https://api.kucoin.com"


class KucoinAPIError(IOError):
    def __init__(self, error_payload: Dict[str, Any]):
        super().__init__()
        self.error_payload = error_payload


cdef class KucoinMarketTransactionTracker(TransactionTracker):
    cdef:
        KucoinMarket _owner

    def __init__(self, owner: KucoinMarket):
        super().__init__()
        self._owner = owner

    cdef c_did_timeout_tx(self, str tx_id):
        TransactionTracker.c_did_timeout_tx(self, tx_id)
        self._owner.c_did_timeout_tx(tx_id)


cdef class KucoinMarket(MarketBase):
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
                 kucoin_api_key: str,
				 kucoin_passphrase: str,
                 kucoin_secret_key: str,
                 poll_interval: float = 5.0,
                 order_book_tracker_data_source_type: OrderBookTrackerDataSourceType =
                 OrderBookTrackerDataSourceType.EXCHANGE_API,
                 symbols: Optional[List[str]] = None,
                 trading_required: bool = True):

        super().__init__()
        self._account_id = ""
        self._async_scheduler = AsyncCallScheduler(call_interval=0.5)
        self._data_source_type = order_book_tracker_data_source_type
        self._ev_loop = asyncio.get_event_loop()
        self._kucoin_auth = KucoinAuth(api_key=kucoin_api_key, passphrase=kucoin_passphrase, secret_key=kucoin_secret_key)
        self._in_flight_orders = {}
        self._last_poll_timestamp = 0
        self._last_timestamp = 0
        self._order_book_tracker = KucoinOrderBookTracker(
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
        self._tx_tracker = KucoinMarketTransactionTracker(self)

    @staticmethod
    def split_symbol(symbol: str) -> Tuple[str, str]:
        try:
            m = symbol.split("-")
            return m[1], m[2]
        except Exception as e:
            raise ValueError(f"Error parsing symbol {symbol}: {str(e)}")

    @staticmethod
    def convert_from_exchange_trading_pair(exchange_trading_pair: str) -> str:
        return exchange_trading_pair

    @staticmethod
    def convert_to_exchange_trading_pair(ku_trading_pair: str) -> str:
        return ku_trading_pair

    @property
    def name(self) -> str:
        return "kucoin"

    @property
    def order_book_tracker(self) -> KucoinOrderBookTracker:
        return self._order_book_tracker

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        return self._order_book_tracker.order_books

    @property
    def trading_rules(self) -> Dict[str, TradingRule]:
        return self._trading_rules

    @property
    def in_flight_orders(self) -> Dict[str, KucoinInFlightOrder]:
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
            key: KucoinInFlightOrder.from_json(value)
            for key, value in saved_states.items()
        })

    @property
    def shared_client(self) -> str:
        return self._shared_client

    @shared_client.setter
    def shared_client(self, client: aiohttp.ClientSession):
        self._shared_client = client

    async def get_active_exchange_markets(self) -> pd.DataFrame:
        return await KucoinAPIOrderBookDataSource.get_active_exchange_markets()

    cdef c_start(self, Clock clock, double timestamp):
        self._tx_tracker.c_start(clock, timestamp)
        MarketBase.c_start(self, clock, timestamp)

    cdef c_stop(self, Clock clock):
        MarketBase.c_stop(self, clock)
        self._async_scheduler.stop()

    async def start_network(self):
        if self._order_tracker_task is not None:
            self._stop_network()
        self._order_tracker_task = safe_ensure_future(self._order_book_tracker.start())
        self._trading_rules_polling_task = safe_ensure_future(self._trading_rules_polling_loop())
        if self._trading_required:
            await self._update_account_id()
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())

    def _stop_network(self):
        if self._order_tracker_task is not None:
            self._order_tracker_task.cancel()
            self._order_tracker_task = None
        if self._status_polling_task is not None:
            self._status_polling_task.cancel()
            self._status_polling_task = None
        if self._trading_rules_polling_task is not None:
            self._trading_rules_polling_task.cancel()
            self._trading_rules_polling_task = None

    async def stop_network(self):
        self._stop_network()

    async def check_network(self) -> NetworkStatus:
        try:
            await self._api_request(method="get", path_url="/api/v1/timestamp")
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

    async def _api_request(self,
                           method,
                           path_url,
                           params: Optional[Dict[str, Any]] = None,
                           data=None,
                           is_auth_required: bool = False) -> Dict[str, Any]:
        content_type = "application/json" if method == "post" else "application/x-www-form-urlencoded"
        headers = {"Content-Type": content_type}
        url = KUCOIN_ROOT_API + path_url
        client = await self._http_client()
        if is_auth_required:
            params = self._kucoin_auth.add_auth_to_params(method, path_url, params)
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
                self.logger().error(f"Error received from {url}. Response is {parsed_response}.")
                return {"error": parsed_response}
            return data

    async def _update_account_id(self) -> str:
        accounts = await self._api_request("get", path_url="/api/v1/accounts", is_auth_required=True)
        try:
            for account in accounts:
                if account["type"] == "trade":
                    self._account_id = str(account["id"])
        except Exception as e:
            raise ValueError(f"Unable to retrieve account id: {e}")

    async def _update_balances(self):
        cdef:
            str path_url = "/api/v1/accounts"
            dict data = await self._api_request("get", path_url=path_url, is_auth_required=True)
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
                    new_available_balances[asset_name] = Decimal(balance_entry["available"])

            self._account_available_balances.clear()
            self._account_available_balances = new_available_balances
            self._account_balances.clear()
            self._account_balances = new_balances

    cdef object c_get_fee(self,
                          str base_currency,
                          str quote_currency,
                          object order_type,
                          object order_side,
                          object amount,
                          object price):
        # There is no API for checking user's fee tier
        # Fee info from https://www.kucoin.com/vip/fee
        return TradeFee(percent=0.001)

    async def _update_trading_rules(self):
        cdef:
            # The poll interval for trade rules is 60 seconds.
            int64_t last_tick = <int64_t>(self._last_timestamp / 60.0)
            int64_t current_tick = <int64_t>(self._current_timestamp / 60.0)
        if current_tick > last_tick or len(self._trading_rules) < 1:
            exchange_info = await self._api_request("get", path_url="/api/v1/symbols")
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
                                min_order_size=Decimal(info["baseMinSize"]),
                                max_order_size=Decimal(info["baseMaxSize"]),
                                min_price_increment=Decimal(info['priceIncrement']),
                                min_base_amount_increment=Decimal(info['baseIncrement']),
                                min_quote_amount_increment=Decimal(info['quoteIncrement']),
                                min_notional_size=Decimal(info["quoteMinSize"]))
                )
            except Exception:
                self.logger().error(f"Error parsing the symbol rule {info}. Skipping.", exc_info=True)
        return trading_rules

    async def get_order_status(self, exchange_order_id: str) -> Dict[str, Any]:
        path_url = f"/api/v1/orders/{exchange_order_id}"
        return await self._api_request("get", path_url=path_url, is_auth_required=True)

    async def _update_order_status(self):
        cdef:
            # The poll interval for order status is 10 seconds.
            int64_t last_tick = <int64_t>(self._last_poll_timestamp / self.UPDATE_ORDERS_INTERVAL)
            int64_t current_tick = <int64_t>(self._current_timestamp / self.UPDATE_ORDERS_INTERVAL)

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
                

                order_state = order_update["isActive"]
                if order_state:
                    continue

                # Calculate the newly executed amount for this update.
                tracked_order.last_state = order_state
                new_confirmed_amount = Decimal(order_update["funds"])  # API isn't detailed enough assuming dealSize
                execute_amount_diff = new_confirmed_amount - tracked_order.executed_amount_base

                if execute_amount_diff > s_decimal_0:
                    tracked_order.executed_amount_base = new_confirmed_amount
                    tracked_order.executed_amount_quote = Decimal(order_update["dealSize"])
                    tracked_order.fee_paid = Decimal(order_update["fee"])
                    execute_price = Decimal(order_update["funds"]) / new_confirmed_amount
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
                        ),
                        exchange_trade_id=exchange_order_id,
                    )
                    self.logger().info(f"Filled {execute_amount_diff} out of {tracked_order.amount} of the "
                                       f"order {tracked_order.client_order_id}.")
                    self.c_trigger_event(self.MARKET_ORDER_FILLED_EVENT_TAG, order_filled_event)

                if order_state == False and order_update["cancelExist"] == False:
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
                                                                     tracked_order.fee_asset or tracked_order.quote_asset,
                                                                     float(tracked_order.executed_amount_base),
                                                                     float(tracked_order.executed_amount_quote),
                                                                     float(tracked_order.fee_paid),
                                                                     tracked_order.order_type))

                if order_state == False and order_update["cancelExist"] == True:
                    self.c_stop_tracking_order(tracked_order.client_order_id)
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
                                      app_warning_msg="Could not fetch account updates from Kucoin. "
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
                                      app_warning_msg="Could not fetch new trading rules from Kucoin. "
                                                      "Check network connection.")
                await asyncio.sleep(0.5)

    @property
    def status_dict(self) -> Dict[str, bool]:
        return {
            "account_id_initialized": self._account_id != "" if self._trading_required else True,
            "order_books_initialized": self._order_book_tracker.ready,
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
        path_url = "/api/v1/orders"
        side = "buy" if is_buy else "sell"
        order_type_str = "limit" if order_type is OrderType.LIMIT else "market"
        params = {
            "funds": str(amount),
            "clientOid": order_id,
			"side": side,
            "symbol": symbol,
            "type": order_type_str,
        }
        if order_type is OrderType.LIMIT:
            params["price"] = str(price)
        exchange_order_id = await self._api_request(
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
                          amount: Decimal,
                          order_type: OrderType,
                          price: Decimal):
        cdef:
            TradingRule trading_rule = self._trading_rules[symbol]
            double quote_amount
            object decimal_amount
            object decimal_price
            str exchange_order_id
            object tracked_order

        if order_type is OrderType.MARKET:
            quote_amount = (<OrderBook>self.c_get_order_book(symbol)).c_get_quote_volume_for_base_amount(
                True, float(amount)).result_volume
            # Quantize according to price rules, not base token amount rules.
            decimal_amount = self.c_quantize_order_price(symbol, Decimal(quote_amount))
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
        except Exception:
            self.c_stop_tracking_order(order_id)
            order_type_str = "MARKET" if order_type == OrderType.MARKET else "LIMIT"
            self.logger().network(
                f"Error submitting buy {order_type_str} order to Kucoin for "
                f"{decimal_amount} {symbol} "
                f"{decimal_price if order_type is OrderType.LIMIT else ''}.",
                exc_info=True,
                app_warning_msg=f"Failed to submit buy order to Kucoin. Check API key and network connection."
            )
            self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                 MarketOrderFailureEvent(self._current_timestamp, order_id, order_type))

    cdef str c_buy(self,
                   str symbol,
                   object amount,
                   object order_type = OrderType.MARKET,
                   object price = s_decimal_0,
                   dict kwargs = {}):
        cdef:
            int64_t tracking_nonce = <int64_t>(time.time() * 1e6)
            str order_id = f"buy-{symbol}-{tracking_nonce}"

        safe_ensure_future(self.execute_buy(order_id, symbol, amount, order_type, price))
        return order_id

    async def execute_sell(self,
                           order_id: str,
                           symbol: str,
                           amount: Decimal,
                           order_type: OrderType,
                           price: Decimal):
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
        except asyncio.CancelledError:
            raise
        except Exception:
            self.c_stop_tracking_order(order_id)
            order_type_str = "MARKET" if order_type is OrderType.MARKET else "LIMIT"
            self.logger().network(
                f"Error submitting sell {order_type_str} order to Kucoin for "
                f"{decimal_amount} {symbol} "
                f"{decimal_price if order_type is OrderType.LIMIT else ''}.",
                exc_info=True,
                app_warning_msg=f"Failed to submit sell order to Kucoin. Check API key and network connection."
            )
            self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                 MarketOrderFailureEvent(self._current_timestamp, order_id, order_type))

    cdef str c_sell(self,
                    str symbol,
                    object amount,
                    object order_type = OrderType.MARKET,
                    object price = s_decimal_0,
                    dict kwargs = {}):
        cdef:
            int64_t tracking_nonce = <int64_t>(time.time() * 1e6)
            str order_id = f"sell-{symbol}-{tracking_nonce}"
        safe_ensure_future(self.execute_sell(order_id, symbol, amount, order_type, price))
        return order_id

    async def execute_cancel(self, symbol: str, order_id: str):
        try:
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is None:
                raise ValueError(f"Failed to cancel order - {order_id}. Order not found.")
            path_url = f"/api/v1/orders/{tracked_order.exchange_order_id}"
            await self._api_request("delete", path_url=path_url, is_auth_required=True)
        except Exception as e:
            self.logger().network(
                f"Failed to cancel order {order_id}: {str(e)}",
                exc_info=True,
                app_warning_msg=f"Failed to cancel the order {order_id} on Kucoin. "
                                f"Check API key and network connection."
            )

    cdef c_cancel(self, str symbol, str order_id):
        safe_ensure_future(self.execute_cancel(symbol, order_id))
        return order_id

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        path_url = "/api/v1/orders"
        params = {}
        data = {}
        cancellation_results = []
        try:
            cancel_all_results = await self._api_request(
                "delete",
                path_url=path_url,
                params=params,
                data=data,
                is_auth_required=True
            )
            for oid in cancel_all_results["cancelledOrderIds"]:
                cancellation_results.append(CancellationResult(oid, True))
            for cancel_error in cancel_all_results["failed"]:
                oid = cancel_error["order-id"]
                cancellation_results.append(CancellationResult(oid, False))
        except Exception as e:
            self.logger().network(
                f"Failed to cancel all orders.",
                exc_info=True,
                app_warning_msg=f"Failed to cancel all orders on Kucoin. Check API key and network connection."
            )
        return cancellation_results

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
        self._in_flight_orders[client_order_id] = KucoinInFlightOrder(
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

    cdef object c_get_order_price_quantum(self, str symbol, object price):
        cdef:
            TradingRule trading_rule = self._trading_rules[symbol]
        return trading_rule.min_price_increment

    cdef object c_get_order_size_quantum(self, str symbol, object order_size):
        cdef:
            TradingRule trading_rule = self._trading_rules[symbol]
        return Decimal(trading_rule.min_base_amount_increment)

    cdef object c_quantize_order_amount(self, str symbol, object amount, object price=s_decimal_0):
        cdef:
            TradingRule trading_rule = self._trading_rules[symbol]
            object quantized_amount = MarketBase.c_quantize_order_amount(self, symbol, amount)
            object current_price = self.c_get_price(symbol, False)
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
