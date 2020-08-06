import re
from enum import Enum
from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../")))

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
from hummingbot.core.utils.async_utils import safe_ensure_future
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
        self._trade_fees = {}
        self._last_update_trade_fees_timestamp = 0
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
        pass

    @property
    def limit_orders(self):
        pass

    # ORDER PLACE AND CANCEL EXECUTIONS ---
    async def create_order(self,
                           trade_type: TradeType,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           order_type: OrderType,
                           price: Optional[Decimal] = Decimal("NaN")):
        # cdef:
        #     TradingRule trading_rule = self._trading_rules[trading_pair]
        if order_type == OrderType.LIMIT_MAKER:
            raise ValueError("Binance Perpetuals does not support the Limit Maker order type.")
        # amount = self.c_quantize_order_amount(trading_pair, amount)
        # price = Decimal("NaN") if order_type == OrderType.MARKET else self.c_quantize_order_price(trading_pair, price)

        # if amount < trading_rule.min_order_size:
        #     raise ValueError(f"Buy order amount {amount} is lower than the minimum order size "
        #                      f"{trading_rule.min_order_size}")

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
            order_result = await self.request(path="order",
                                              params=api_params,
                                              method=MethodType.POST,
                                              is_signed=True)
            self.logger().debug(f"WESLEY TESTING --- ORDER RESULTS: {order_result}")
            print(f"ORDER RESULTS --- {order_result}")

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
            self.logger().debug(f"WESLEY TESTING --- Error: {e}")
            print(e)
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
        print("WESLEY TESTING--- EXECUTE BUY")
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
        print("WESLEY TESTING--- C_BUY")
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
        pass

    async def cancel_all_account_orders(self, str trading_pair):
        try:
            params = {
                "timestamp": f"{int(time.time()) * 1000}",
                "symbol": trading_pair
            }
            return await self.request(
                path="allOpenOrders",
                params=params,
                method=MethodType.DELETE,
                is_signed=True
            )
        except Exception as e:
            self.logger().error(f"Could not cancel all account orders.")
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
                path="order",
                params=params,
                method=MethodType.DELETE,
                is_signed=True
            )
            print(f"WESLEY TESTING --- Cancelled Response: {response}")
        except Exception as e:
            self.logger().error(f"Could not cancel order {client_order_id} (on Binance Perp. {trading_pair})")
            raise e
        if response.get("status", None) == "CANCELED":
            self.logger().info(f"Successfully canceled order {client_order_id}")
            self.c_stop_tracking_order(client_order_id)
            self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                 OrderCancelledEvent(self._current_timestamp, client_order_id))
        return response

    # ORDER TRACKING ---
    cdef c_start_tracking_order(self, str order_id, str exchange_order_id, str trading_pair, object trading_type,
                                object price, object amount, object order_type):
        pass

    cdef c_stop_tracking_order(self, str order_id):
        pass

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

    # MARKET INFO ---

    cdef object c_get_fee(self, str base_currency, str quote_currency, object order_type, object order_side,
                          object amount, object price):
        return

    cdef OrderBook c_get_order_book(self, str trading_pair):
        cdef:
            dict order_books = self._order_book_tracker.order_books
        if trading_pair not in order_books:
            raise ValueError(f"No order book exists for '{trading_pair}'.")
        return order_books[trading_pair]

    cdef object c_get_order_price_quantum(self, str trading_pair, object price):
        return

    cdef object c_get_order_size_quantum(self, str trading_pair, object order_size):
        return

    # TODO: IMPLEMENT WITH A 1X MARGIN INITIALLY (KEEPS ASSET MANAGEMENT EASIER)
    async def set_margin(self, margin: int):
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
                async with aiohttp.ClientSession() as client:
                    query = urlencode(sorted(params.items()))
                    if is_signed:
                        secret = bytes(self._binance_api_secret.encode("utf-8"))
                        signature = hmac.new(secret, query.encode("utf-8"), hashlib.sha256).hexdigest()
                        query += f"&signature={signature}"
                    async with client.request(
                            method=method.value,
                            url="https://fapi.binance.com/fapi/v1/" + path + "?" + query,
                            headers={"X-MBX-APIKEY": self._binance_api_key}) as response:
                        if response.status != 200:
                            print(f"WESLEY TESTING --- Request Error: {response}")
                            raise IOError(f"Error fetching data from {path}. HTTP status is {response.status}.")
                        return await response.json()
            except Exception as e:
                self.logger().warning(f"Error fetching {path}")
                raise e

    cdef c_did_timout_tx(self, str tracking_id):
        pass

    async def _update_trading_rules(self):
        cdef:
            int64_t last_tick = <int64_t> (self._last_timestamp / 60.0)
            int64_t current_tick = <int64_t> (self._current_timestamp / 60.0)
        if current_tick > last_tick or len(self._trading_rules) < 1:
            exchange_info = await self.request(path="exchangeInfo", method=MethodType.GET, is_signed=False)
            trading_rules_list = self.format_trading_rules(exchange_info)
            self._trading_rules.clear()
            for trading_rule in trading_rules_list:
                self._trading_rules[trading_rule.trading_pair] = trading_rule

    def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        """
            Example:
            {
                "symbol": "BTCUSDT",
                "status": "TRADING",
                "maintMarginPercent": "2.5000",
                "requiredMarginPercent": "5.0000",
                "baseAsset": "BTC",
                "quoteAsset": "USDT",
                "pricePrecision": 2,
                "quantityPrecision": 3,
                "baseAssetPrecision": 8,
                "quotePrecision": 8,
                "filters": [
                    {
                        "minPrice": "0.01",
                        "maxPrice": "100000",
                        "filterType": "PRICE_FILTER",
                        "tickSize": "0.01"
                    },
                    {
                        "stepSize": "0.001",
                        "filterType": "LOT_SIZE",
                        "maxQty": "1000",
                        "minQty": "0.001"
                    },
                    {
                        "stepSize": "0.001",
                        "filterType": "MARKET_LOT_SIZE",
                        "maxQty": "1000",
                        "minQty": "0.001"
                    },
                    {
                        "limit": 0,
                        "filterType": "MAX_NUM_ORDERS"
                    },
                    {
                        "multiplierDown": "0.7000",
                        "multiplierUp": "1.3000",
                        "multiplierDecimal": "4",
                        "filterType": "PERCENT_PRICE"
                    }
                ],
                "orderTypes": [
                    "LIMIT",
                    "MARKET",
                    "STOP",
                    "STOP_MARKET",
                    "TAKE_PROFIT",
                    "TAKE_PROFIT_MARKET"
                ],
                "timeInForce": [
                    "GTC",
                    "IOC",
                    "FOK",
                    "GTX"
                ]
            }
        """
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

    # Not Needed ---

    # TODO: DEPRECATED
    async def get_active_exchange_markets(self) -> pd.DataFrame:
        return await BinancePerpetualOrderBookDataSource.get_active_exchange_markets()

    cdef str c_withdraw(self, str address, str currency, object amount):
        pass

    async def get_deposit_info(self, asset: str):
        pass
