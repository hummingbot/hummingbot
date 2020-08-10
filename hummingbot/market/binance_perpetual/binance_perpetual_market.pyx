import re
from collections import defaultdict
from enum import Enum
from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../")))

from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.estimate_fee import estimate_fee

from async_timeout import timeout

from hummingbot.core.clock cimport Clock
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.market.binance_perpetual.binance_perpetual_in_flight_order import BinancePerpetualsInFlightOrder

from hummingbot.core.utils.tracking_nonce import get_tracking_nonce
from hummingbot.market.binance_perpetual.binance_perpetual_order_book_data_source import (
    BinancePerpetualOrderBookDataSource
)

import asyncio
import hashlib
import hmac
import time
import logging
import pandas as pd
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple, AsyncIterable
from urllib.parse import urlencode
from libc.stdint cimport int64_t

import aiohttp

from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.core.data_type.order_book_tracker import OrderBookTrackerDataSourceType
from hummingbot.core.data_type.user_stream_tracker import UserStreamTrackerDataSourceType
from hummingbot.core.event.events import (
    OrderType,
    TradeType,
    MarketOrderFailureEvent,
    MarketEvent,
    OrderCancelledEvent,
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    SellOrderCreatedEvent,
    OrderFilledEvent,
    SellOrderCompletedEvent)
from hummingbot.core.utils.async_call_scheduler import AsyncCallScheduler
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.utils.asyncio_throttle import Throttler
from hummingbot.logger import HummingbotLogger
from hummingbot.market.binance_perpetual.binance_perpetual_order_book_tracker import BinancePerpetualOrderBookTracker
from hummingbot.market.binance_perpetual.binance_perpetual_user_stream_tracker import BinancePerpetualUserStreamTracker
from hummingbot.market.market_base import MarketBase, s_decimal_NaN
from hummingbot.market.trading_rule cimport TradingRule


class MethodType(Enum):
    GET = "GET"
    POST = "POST"
    DELETE = "DELETE"
    PUT = "PUT"


bpm_logger = None

TRADING_PAIR_SPLITTER = re.compile(
    r"^(\w+)(BTC|ETH|BNB|XRP|USDT|USDC|USDS|TUSD|PAX|TRX|BUSD|NGN|RUB|TRY|EUR|IDRT|ZAR|UAH|GBP|BKRW|BIDR)$")
BROKER_ID = "x-XEKWYICX"

cdef str get_client_order_id(str order_side, object trading_pair):
    cdef:
        int64_t nonce = <int64_t> get_tracking_nonce()
        object symbols = trading_pair.split("-")
        str base = symbols[0].upper()
        str quote = symbols[1].upper()
    return f"{BROKER_ID}-{order_side.upper()[0]}{base[0]}{base[-1]}{quote[0]}{quote[-1]}{nonce}"

cdef class BinancePerpetualMarket(MarketBase):
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
    SHORT_POLL_INTERVAL = 5.0
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0
    LONG_POLL_INTERVAL = 120.0
    ORDER_NOT_EXIST_CONFIRMATION_COUNT = 3

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global bpm_logger
        if bpm_logger is None:
            bpm_logger = logging.getLogger(__name__)
        return bpm_logger

    def __init__(self,
                 binance_api_key: str,
                 binance_api_secret: str,
                 order_book_tracker_data_source_type: OrderBookTrackerDataSourceType =
                 OrderBookTrackerDataSourceType.EXCHANGE_API,
                 user_stream_tracker_data_source_type: UserStreamTrackerDataSourceType =
                 UserStreamTrackerDataSourceType.EXCHANGE_API,
                 trading_pairs: Optional[List[str]] = None):
        super().__init__()
        self._binance_api_key = binance_api_key
        self._binance_api_secret = binance_api_secret

        self._user_stream_tracker = BinancePerpetualUserStreamTracker(
            data_source_type=user_stream_tracker_data_source_type,
            api_key=self._binance_api_key)
        self._order_book_tracker = BinancePerpetualOrderBookTracker(
            data_source_type=order_book_tracker_data_source_type,
            trading_pairs=trading_pairs)
        self._ev_loop = asyncio.get_event_loop()
        self._poll_notifier = asyncio.Event()
        self._in_flight_orders = {}
        self._order_not_found_records = {}
        self._last_timestamp = 0
        self._trading_rules = {}
        # self._trade_fees = {}
        # self._last_update_trade_fees_timestamp = 0
        self._data_source_type = order_book_tracker_data_source_type
        self._status_polling_task = None
        self._user_stream_event_listener_task = None
        self._trading_rules_polling_task = None
        self._async_scheduler = AsyncCallScheduler(call_interval=0.5)
        self._last_poll_timestamp = 0
        self._throttler = Throttler((10.0, 1.0))

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        return self._order_book_tracker.order_books

    @property
    def ready(self):
        return all(self.status_dict.values())

    @property
    def in_flight_orders(self) -> Dict[str, BinancePerpetualsInFlightOrder]:
        return self._in_flight_orders

    @property
    def status_dict(self):
        return {
            "order_books_initialized": self._order_book_tracker.ready,
            "account_balance": len(self._account_balances) > 0 if self._trading_required else True,
            "trading_rule_initialized": len(self._trading_rules) > 0

            # TODO: Uncomment when figured out trade fees
            # "trade_fees_initialized": len(self._trade_fees) > 0
        }

    @property
    def limit_orders(self):
        return [in_flight_order.to_limit_order() for in_flight_order in self._in_flight_orders.values()]

    cdef c_start(self, Clock clock, double timestamp):
        MarketBase.c_start(self, clock, timestamp)

    cdef c_stop(self, Clock clock):
        MarketBase.c_stop(self, clock)
        self._async_scheduler.stop()

    async def start_network(self):
        print("WESLEY TESTING --- BINANCE NETWORK STARTED")
        self._order_book_tracker.start()
        self._trading_rules_polling_task = safe_ensure_future(self._trading_rules_polling_loop())
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
            await self.request("/fapi/v1/ping")
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    # ORDER PLACE AND CANCEL EXECUTIONS ---
    async def create_order(self,
                           trade_type: TradeType,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           order_type: OrderType,
                           price: Optional[Decimal] = Decimal("NaN")):
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]
        if order_type == OrderType.LIMIT_MAKER:
            raise ValueError("Binance Perpetuals does not support the Limit Maker order type.")

        amount = self.c_quantize_order_amount(trading_pair, amount)
        price = Decimal("NaN") if order_type == OrderType.MARKET else self.c_quantize_order_price(trading_pair, price)

        if amount < trading_rule.min_order_size:
            raise ValueError(f"Buy order amount {amount} is lower than the minimum order size "
                             f"{trading_rule.min_order_size}")

        order_result = None
        api_params = {"symbol": trading_pair,
                      "side": "BUY" if trade_type is TradeType.BUY else "SELL",
                      "type": order_type.name.upper(),
                      "quantity": f"{amount}",
                      "timestamp": f"{int(time.time()) * 1000}",
                      "newClientOrderId": order_id
                      }
        if order_type != OrderType.MARKET:
            api_params["price"] = f"{price}"
        if order_type == OrderType.LIMIT:
            api_params["timeInForce"] = "GTC"

        self.c_start_tracking_order(order_id, "", trading_pair, trade_type, price, amount, order_type)

        try:
            order_result = await self.request(path="/fapi/v1/order",
                                              params=api_params,
                                              method=MethodType.POST,
                                              is_signed=True)
            event_tag = self.MARKET_BUY_ORDER_CREATED_EVENT_TAG if trade_type is TradeType.BUY \
                else self.MARKET_SELL_ORDER_CREATED_EVENT_TAG
            event_class = BuyOrderCreatedEvent if trade_type is TradeType.BUY else SellOrderCreatedEvent
            self.c_trigger_event(event_tag,
                                 event_class(
                                     self._current_timestamp,
                                     order_type,
                                     trading_pair,
                                     amount,
                                     price,
                                     order_id
                                 ))
            return order_result
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.c_stop_tracking_order(order_id)
            self.logger().network(
                f"Error submitting order to Binance Perpetuals for {amount} {trading_pair} "
                f"{'' if order_type is OrderType.MARKET else price}.",
                exc_info=True,
                app_warning_msg=str(e)
            )
            self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                 MarketOrderFailureEvent(self._current_timestamp, order_id, order_type))

    async def execute_buy(self,
                          order_id: str,
                          trading_pair: str,
                          amount: Decimal,
                          order_type: OrderType,
                          price: Optional[Decimal] = s_decimal_NaN):
        return await self.create_order(TradeType.BUY, order_id, trading_pair, amount, order_type, price)

    cdef str c_buy(self,
                   str trading_pair,
                   object amount,
                   object order_type=OrderType.MARKET,
                   object price=s_decimal_NaN,
                   dict kwargs={}):
        cdef:
            str t_pair = BinancePerpetualMarket.convert_from_exchange_trading_pair(trading_pair)
            str order_id = get_client_order_id("buy", t_pair)
        safe_ensure_future(self.execute_buy(order_id, trading_pair, amount, order_type, price))
        return order_id

    async def execute_sell(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           order_type: OrderType,
                           price: Optional[Decimal] = Decimal("NaN")):
        return await self.create_order(TradeType.SELL, order_id, trading_pair, amount, order_type, price)

    cdef str c_sell(self, str trading_pair, object amount, object order_type=OrderType.MARKET,
                    object price=s_decimal_NaN, dict kwargs={}):
        cdef:
            str t_pair = BinancePerpetualMarket.convert_from_exchange_trading_pair(trading_pair)
            str order_id = get_client_order_id("sell", t_pair)
        safe_ensure_future(self.execute_sell(order_id, trading_pair, amount, order_type, price))
        return order_id

    async def cancel_all(self, timeout_seconds: float):
        incomplete_orders = [order for order in self._in_flight_orders.values() if not order.is_done]
        tasks = [self.execute_cancel(order.trading_pair, order.client_order_id) for order in incomplete_orders]
        order_id_set = set([order.client_order_id for order in incomplete_orders])
        successful_cancellations = []

        try:
            async with timeout(timeout_seconds):
                cancellation_results = await safe_gather(*tasks, return_exceptions=True)
                for cancel_result in cancellation_results:
                    # TODO: QUESTION --- SHOULD I CHECK FOR THE BinanceAPIException CONSIDERING WE ARE MOVING AWAY FROM BINANCE-CLIENT?
                    if isinstance(cancel_result, dict) and "clientOrderId" in cancel_result:
                        client_order_id = cancel_result.get("clientOrderId")
                        order_id_set.remove(client_order_id)
                        successful_cancellations.append(CancellationResult(client_order_id, True))
        except Exception:
            self.logger().network(
                f"Unexpected error cancelling orders.",
                exc_info=True,
                app_warning_msg="Failed to cancel order with Binance Perpetual. Check API key and network connection."
            )
        failed_cancellations = [CancellationResult(order_id, False) for order_id in order_id_set]
        return successful_cancellations + failed_cancellations

    async def cancel_all_account_orders(self, str trading_pair):
        try:
            params = {
                "timestamp": f"{int(time.time()) * 1000}",
                "symbol": trading_pair
            }
            response = await self.request(
                path="/fapi/v1/allOpenOrders",
                params=params,
                method=MethodType.DELETE,
                is_signed=True
            )
            if response.get("code") == 200:
                print("CANCELLING ALL ORDERS")
                for order_id in list(self._in_flight_orders.keys()):
                    self.c_stop_tracking_order(order_id)
            else:
                raise IOError(f"Error cancelling all account orders. Server Response: {response}")
        except Exception as e:
            self.logger().error("Could not cancel all account orders.")
            raise e

    cdef c_cancel(self, str trading_pair, str client_order_id):
        safe_ensure_future(self.execute_cancel(trading_pair, client_order_id))
        return client_order_id

    async def execute_cancel(self, trading_pair: str, client_order_id: str):
        try:
            params = {
                "origClientOrderId": client_order_id,
                "symbol": trading_pair,
                "timestamp": f"{int(time.time()) * 1000}"
            }
            response = await self.request(
                path="/fapi/v1/order",
                params=params,
                method=MethodType.DELETE,
                is_signed=True
            )
        except Exception as e:
            self.logger().error(f"Could not cancel order {client_order_id} (on Binance Perp. {trading_pair})")
            raise e
        if response.get("status", None) == "CANCELED":
            self.logger().info(f"Successfully canceled order {client_order_id}")
            self.c_stop_tracking_order(client_order_id)
            self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                 OrderCancelledEvent(self._current_timestamp, client_order_id))
        return response

    cdef object c_quantize_order_amount(self, str trading_pair, object amount, object price=Decimal(0)):
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]
            object current_price = self.c_get_price(trading_pair, False)
            object notional_size
        quantized_amount = MarketBase.c_quantize_order_amount(self, trading_pair, amount)
        if quantized_amount < trading_rule.min_order_size:
            return Decimal(0)
        if price == Decimal(0):
            notional_size = current_price * quantized_amount
        else:
            notional_size = price * quantized_amount

        # TODO: NOTIONAL MIN SIZE DOES NOT EXIST
        # if notional_size < trading_rule.min_notional_size * Decimal("1.01"):
        #     return Decimal(0)

        return quantized_amount

    cdef object c_get_order_price_quantum(self, str trading_pair, object price):
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]
        return trading_rule.min_price_increment

    cdef object c_get_order_size_quantum(self, str trading_pair, object order_size):
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]
        return Decimal(trading_rule.min_base_amount_increment)

    # ORDER TRACKING ---
    cdef c_start_tracking_order(self, str order_id, str exchange_order_id, str trading_pair, object trading_type,
                                object price, object amount, object order_type):
        self._in_flight_orders[order_id] = BinancePerpetualsInFlightOrder(
            client_order_id=order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=trading_pair,
            order_type=order_type,
            trade_type=trading_type,
            price=price,
            amount=amount
        )

    cdef c_stop_tracking_order(self, str order_id):
        if order_id in self._in_flight_orders:
            del self._in_flight_orders[order_id]
        if order_id in self._order_not_found_records:
            del self._order_not_found_records[order_id]

    async def _iter_user_event_queue(self) -> AsyncIterable[Dict[str, any]]:
        while True:
            try:
                yield await self._user_stream_tracker.user_stream.get()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unknown error. Retrying after 1 seconds.",
                    exc_info=True,
                    app_warning_msg="Could not fetch user events from Binance. Check API key and network connection."
                )
                await asyncio.sleep(1.0)

    async def _user_stream_event_listener(self):
        async for event_message in self._iter_user_event_queue():
            try:
                event_type = event_message.get("e")
                if event_type == "ORDER_TRADE_UPDATE":
                    order_message = event_message.get("o")
                    client_order_id = order_message.get("c")

                    # If the order has already been cancelled
                    if client_order_id not in self._in_flight_orders:
                        continue

                    tracked_order = self._in_flight_orders.get(client_order_id)
                    tracked_order.update_with_execution_report(event_message)

                    # Execution Type: Trade => Filled
                    trade_type = TradeType.BUY if order_message.get("S") == "BUY" else TradeType.SELL
                    if event_message.get("x") == "TRADE":
                        order_filled_event = OrderFilledEvent(
                            timestamp=event_message.get("E") * 1e-3,
                            order_id=client_order_id,
                            trading_pair=order_message.get("s"),
                            trade_type=trade_type,
                            order_type=OrderType[order_message.get("o")],
                            price=Decimal(order_message.get("L")),
                            amount=Decimal(order_message.get("l")),
                            trade_fee=self.c_get_fee(
                                base_currency=tracked_order.base_asset,
                                quote_currency=tracked_order.quote_asset,
                                order_type=OrderType[order_message.get("o")],
                                order_side=trade_type,
                                amount=order_message.get("q"),
                                price=order_message.get("p")
                            ),
                            exchange_trade_id=order_message.get("t")
                        )
                    if tracked_order.is_done:
                        if not tracked_order.is_failure:
                            event_tag = None
                            event_class = None
                            if trade_type is TradeType.BUY:
                                event_tag = self.MARKET_BUY_ORDER_COMPLETED_EVENT_TAG
                                event_class = BuyOrderCompletedEvent
                            else:
                                event_tag = self.MARKET_SELL_ORDER_COMPLETED_EVENT_TAG
                                event_class = SellOrderCompletedEvent
                            self.logger().info(f"The market {trade_type} order {client_order_id} has completed "
                                               f"according to order status API.")
                            self.c_trigger_event(event_tag,
                                                 event_class(
                                                     self._current_timestamp,
                                                     client_order_id,
                                                     tracked_order.base_asset,
                                                     tracked_order.quote_asset,
                                                     (tracked_order.fee_asset or tracked_order.quote_asset),
                                                     tracked_order.executed_amount_base,
                                                     tracked_order.executed_amount_quote,
                                                     tracked_order.fee_paid,
                                                     tracked_order.order_type)
                                                 )
                        else:
                            if tracked_order.is_cancelled:
                                if tracked_order.client_order_id in self._in_flight_orders:
                                    self.logger().info(f"Successfully cancelled order {tracked_order.client_order_id}.")
                                    self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                                         OrderCancelledEvent(
                                                             self._current_timestamp,
                                                             tracked_order.client_order_id))
                                else:
                                    self.logger().info(f"The market order {tracked_order.client_order_id} has failed "
                                                       f"according to order status API.")
                                    self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                                         MarketOrderFailureEvent(
                                                             self._current_timestamp,
                                                             tracked_order.client_order_id,
                                                             tracked_order.order_type
                                                         ))
                        self.c_stop_tracking_order(tracked_order.client_order_id)
                # TODO: IMPLEMENT
                elif event_type == "ACCOUNT_UPDATE":
                    pass
                # TODO: IMPLEMENT
                elif event_type == "MARGIN_CALL":
                    pass
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"Unexpected error in user stream listener loop: {e}", exc_info=True)
                await asyncio.sleep(5.0)

    # MARKET AND ACCOUNT INFO ---
    # TODO: IMPLEMENT --- not right
    cdef object c_get_fee(self, str base_currency, str quote_currency, object order_type, object order_side,
                          object amount, object price):
        is_maker = order_type is OrderType.LIMIT
        return estimate_fee("binance", is_maker)

    cdef OrderBook c_get_order_book(self, str trading_pair):
        cdef:
            dict order_books = self._order_book_tracker.order_books
        if trading_pair not in order_books:
            raise ValueError(f"No order book exists for '{trading_pair}'.")
        return order_books[trading_pair]

    async def _update_trading_rules(self):
        cdef:
            int64_t last_tick = <int64_t> (self._last_timestamp / 60.0)
            int64_t current_tick = <int64_t> (self._current_timestamp / 60.0)
        print("WESLEY TESTING --- UPDATING TRADE RULES")
        if current_tick > last_tick or len(self._trading_rules) < 1:
            exchange_info = await self.request(path="/fapi/v1/exchangeInfo", method=MethodType.GET, is_signed=False)
            trading_rules_list = self._format_trading_rules(exchange_info)
            self._trading_rules.clear()
            for trading_rule in trading_rules_list:
                self._trading_rules[trading_rule.trading_pair] = trading_rule

    def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        cdef:
            list rules = exchange_info_dict.get("symbols", [])
            list return_val = []
        for rule in rules:
            try:
                trading_pair = rule["symbol"]
                filters = rule["filters"]
                filt_dict = {fil["filterType"]: fil for fil in filters}

                min_order_size = Decimal(filt_dict.get("LOT_SIZE").get("minQty"))
                step_size = Decimal(filt_dict.get("LOT_SIZE").get("stepSize"))
                tick_size = Decimal(filt_dict.get("PRICE_FILTER").get("tickSize"))

                # TODO: BINANCE PERPETUALS DOES NOT HAVE A MIN NOTIONAL VALUE, NEED TO CREATE NEW DERIVITIVES INFRASTRUCTURE
                # min_notional = 0

                return_val.append(
                    TradingRule(trading_pair,
                                min_order_size=min_order_size,
                                min_price_increment=Decimal(tick_size),
                                min_base_amount_increment=Decimal(step_size),
                                # min_notional_size=Decimal(min_notional))
                                )
                )
            except Exception as e:
                self.logger().error(f"Error parsing the trading pair rule {rule}. Error: {e}. Skipping...",
                                    exc_info=True)
        return return_val

    async def _trading_rules_polling_loop(self):
        while True:
            try:
                await safe_gather(
                    self._update_trading_rules()

                    # TODO: Uncomment when implemented
                    # self._update_trade_fees()
                )
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network("Unexpected error while fetching trading rules.", exc_info=True,
                                      app_warning_msg="Could not fetch new trading rules from Binance Perpetuals. "
                                                      "Check network connection.")
                await asyncio.sleep(0.5)

    async def _status_polling_loop(self):
        while True:
            try:
                self._poll_notifier = asyncio.Event()
                await self._poll_notifier.wait()
                await safe_gather(
                    self._update_balances(),
                    self._update_order_fills_from_trades(),
                    self._update_order_status
                )
                self._last_poll_timestamp = self._current_timestamp
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network("Unexpected error while fetching account updates.", exc_info=True,
                                      app_warning_msg="Could not fetch account updates from Binance Perpetuals. "
                                                      "Check API key and network connection.")
                await asyncio.sleep(0.5)

    async def _update_balances(self):
        cdef:
            dict account_info
            list balances
            str asset_name
            set local_asset_names = set(self._account_balances.keys())
            set remote_asset_names = set()
            set asset_names_to_remove
        params = {"timestamp": f"{int(time.time()) * 1000}"}
        account_info = await self.request(path="/fapi/v2/account", is_signed=True, params=params)
        assets = account_info.get("assets")
        for asset in assets:
            asset_name = asset.get("asset")
            available_balance = Decimal(asset.get("availableBalance"))
            wallet_balance = Decimal(asset.get("walletBalance"))
            self._account_available_balances[asset_name] = available_balance
            self._account_balances[asset_name] = wallet_balance
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    async def _update_order_fills_from_trades(self):
        cdef:
            int64_t last_tick = <int64_t>(self._last_poll_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL)
            int64_t current_tick = <int64_t>(self._current_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL)
        if current_tick > last_tick and len(self._in_flight_orders) > 0:
            trading_pairs_to_order_map = defaultdict(lambda: {})
            for order in self._in_flight_orders.values():
                trading_pairs_to_order_map[order.trading_pair][order.exchange_order_id] = order
            trading_pairs = list(trading_pairs_to_order_map.keys())
            tasks = [
                self.request(
                    path="/fapi/v1/userTrades",
                    params={
                        "timestamp": f"{int(time.time()) * 1000}",
                        "symbol": trading_pair
                    }
                ) for trading_pair in trading_pairs]
            self.logger().debug(f"Polling for order fills of {len(tasks)} trading_pairs.")
            results = await safe_gather(*tasks, return_exceptions=True)
            for trades, trading_pair in zip(results, trading_pairs):
                order_map = trading_pairs_to_order_map.get(trading_pair)
                if isinstance(trades, Exception):
                    self.logger().network(
                        f"Error fetching trades update for the order {trading_pair}: {trades}.",
                        app_warning_msg=f"Failed to fetch trade update for {trading_pair}."
                    )
                    continue
                for trade in trades:
                    order_id = str(trade.get("orderId"))
                    if order_id in order_map:
                        tracked_order = order_map.get(order_id)
                        order_type = tracked_order.order_type
                        applied_trade = tracked_order.update_with_trade_updates(trade)
                        if applied_trade:
                            self.c_trigger_event(
                                self.MARKET_ORDER_FILLED_EVENT_TAG,
                                OrderFilledEvent(
                                    self._current_timestamp,
                                    tracked_order.client_order_id,
                                    tracked_order.trading_pair,
                                    tracked_order.trade_type,
                                    order_type,
                                    Decimal(trade.get("price")),
                                    Decimal(trade.get("qty")),
                                    self.c_get_fee(
                                        tracked_order.base_asset,
                                        tracked_order.quote_asset,
                                        order_type,
                                        tracked_order.trade_type,
                                        Decimal(trade["price"]),
                                        Decimal(trade["qty"])),
                                    exchange_trade_id=trade["id"]
                                )
                            )

    async def _update_order_status(self):
        cdef:
            int64_t last_tick = <int64_t>(self._last_poll_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL)
            int64_t current_tick = <int64_t>(self._current_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL)
        if current_tick > last_tick and len(self._in_flight_orders) > 0:
            tracked_orders = list(self._in_flight_orders)
            tasks = [self.request(path="/fapi/v1/order",
                                  params={
                                      "symbol": order.trading_pair,
                                      "origClientOrderId": order.client_order_id,
                                      "timestamp": f"{int(time.time()) * 1000}"
                                  },
                                  method=MethodType.GET,
                                  is_signed=True)
                     for order in tracked_orders]
            self.logger().debug(f"Polling for order status updates of {len(tasks)} orders.")
            results = await safe_gather(*tasks, return_exceptions=True)
            for order_update, tracked_order in zip(results, tracked_orders):
                client_order_id = tracked_order.client_order_id
                if client_order_id not in self._in_flight_orders:
                    continue
                if isinstance(order_update, Exception):
                    # NO_SUCH_ORDER code
                    if order_update.code == 2013 or order_update.message == "Order does not exist.":
                        self._order_not_found_records[client_order_id] = \
                            self._order_not_found_records.get(client_order_id, 0) + 1
                        if self._order_not_found_records[client_order_id] < self.ORDER_NOT_EXIST_CONFIRMATION_COUNT:
                            continue
                        self.c_trigger_event(
                            self.MARKET_ORDER_FAILURE_EVENT_TAG,
                            MarketOrderFailureEvent(self._current_timestamp, client_order_id, tracked_order.order_type)
                        )
                        self.c_stop_tracking_order(client_order_id)
                    else:
                        self.logger().network(f"Error fetching status update for the order {client_order_id}: "
                                              f"{order_update}.")
                    continue
                tracked_order.last_state = order_update.get("status")
                order_type = OrderType[order_update.get("type")]
                executed_amount_base = Decimal(order_update.get("executedQty"))
                executed_amount_quote = Decimal(order_update.get("cumQuote"))

                if tracked_order.is_done:
                    if not tracked_order.is_failure:
                        event_tag = None
                        event_class = None
                        if tracked_order.trade_type is TradeType.BUY:
                            event_tag = self.MARKET_BUY_ORDER_COMPLETED_EVENT_TAG
                            event_class = BuyOrderCompletedEvent
                        else:

                            event_tag = self.MARKET_SELL_ORDER_COMPLETED_EVENT_TAG
                            event_class = SellOrderCompletedEvent
                        self.logger().info(f"The market {tracked_order.trade_type.name} order {client_order_id} has "
                                           f"completed according to order status API.")
                        self.c_trigger_event(event_tag,
                                             event_class(self._current_timestamp,
                                                         client_order_id,
                                                         tracked_order.base_asset,
                                                         tracked_order.quote_asset,
                                                         (tracked_order.fee_asset
                                                          or tracked_order.base_asset),
                                                         executed_amount_base,
                                                         executed_amount_quote,
                                                         tracked_order.fee_paid,
                                                         order_type))
                    else:
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
                                                     order_type
                                                 ))
                    self.c_stop_tracking_order(client_order_id)

    # TODO: QUESTION: What do I do about trading fees
    # async def _update_trade_fees(self):
    #     cdef:
    #         double current_timestamp = self._current_timestamp
    #     if current_timestamp - self._last_update_trade_fees_timestamp > 60.0 * 60.0 or len(self._trade_fees) < 1:
    #         try:
    #             response = await self.request(
    #
    #             )
    #             for fee in response["tradeFee"]:
    #                 self._trade_fees[fee["symbol"]] = (Decimal(fee["maker"]), Decimal(fee["taker"]))
    #             self._last_update_trade_fees_timestamp = current_timestamp
    #         except asyncio.CancelledError:
    #             raise
    #         except Exception:
    #             self.logger().network("Error fetching Binance trade fees.", exc_info=True,
    #                                   app_warning_msg=f"Could not fetch Binance trading fees. "
    #                                                   f"Check network connection.")
    #             raise

    # TODO: IMPLEMENT WITH A 1X MARGIN INITIALLY (KEEPS ASSET MANAGEMENT EASIER)
    async def set_margin(self, margin: int):
        pass

    # TODO: IMPLEMENT (ADDITIONAL) --> Return order PnL
    async def get_order_pnl(self, client_order_id: str):
        pass

    # Helper Functions ---
    @staticmethod
    def split_trading_pair(trading_pair: str) -> Optional[Tuple[str, str]]:
        try:
            m = TRADING_PAIR_SPLITTER.match(trading_pair)
            return m.group(1), m.group(2)
        # Exceptions are now logged as warnings in trading pair fetcher
        except Exception as e:
            return None

    @staticmethod
    def convert_from_exchange_trading_pair(exchange_trading_pair: str) -> Optional[str]:
        if BinancePerpetualMarket.split_trading_pair(exchange_trading_pair) is None:
            return None
        # Binance does not split BASEQUOTE (BTCUSDT)
        base_asset, quote_asset = BinancePerpetualMarket.split_trading_pair(exchange_trading_pair)
        return f"{base_asset}-{quote_asset}"

    async def request(self, path: str, params: Dict[str, Any] = {}, method: MethodType = MethodType.GET,
                      is_signed: bool = False, request_weight: int = 1):
        async with self._throttler.weighted_task(request_weight):
            try:
                # TODO: QUESTION --- SHOULD I ADD AN ASYNC TIMEOUT? (aync with timeout(API_CALL_TIMEOUT)
                async with aiohttp.ClientSession() as client:
                    query = urlencode(sorted(params.items()))
                    if is_signed:
                        secret = bytes(self._binance_api_secret.encode("utf-8"))
                        signature = hmac.new(secret, query.encode("utf-8"), hashlib.sha256).hexdigest()
                        query += f"&signature={signature}"
                    async with client.request(
                            method=method.value,
                            url="https://fapi.binance.com" + path + "?" + query,
                            headers={"X-MBX-APIKEY": self._binance_api_key}) as response:
                        if response.status != 200:
                            print(f"WESLEY TESTING --- Request Error: {response}")
                            raise IOError(f"Error fetching data from {path}. HTTP status is {response.status}.")
                        return await response.json()
            except Exception as e:
                self.logger().warning(f"Error fetching {path}")
                raise e

    # Not Needed ---
    cdef c_did_timout_tx(self, str tracking_id):
        pass

    cdef str c_withdraw(self, str address, str currency, object amount):
        pass

    async def get_deposit_info(self, asset: str):
        pass

    # DEPRECATED
    async def get_active_exchange_markets(self) -> pd.DataFrame:
        return await BinancePerpetualOrderBookDataSource.get_active_exchange_markets()
