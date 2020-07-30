import asyncio
import hashlib
import hmac
import time
import logging
from decimal import Decimal
from typing import Optional, List, Dict
from urllib.parse import urlencode

import aiohttp

from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_tracker import OrderBookTrackerDataSourceType
from hummingbot.core.data_type.user_stream_tracker import UserStreamTrackerDataSourceType
from hummingbot.core.event.events import OrderType, TradeType, MarketOrderFailureEvent
from hummingbot.core.utils.async_call_scheduler import AsyncCallScheduler
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.core.utils.asyncio_throttle import Throttler
from hummingbot.logger import HummingbotLogger
from hummingbot.market.binance_perpetual.binance_perpetual_order_book_tracker import BinancePerpetualOrderBookTracker
from hummingbot.market.binance_perpetual.binance_perpetual_user_stream_tracker import BinancePerpetualUserStreamTracker
from hummingbot.market.market_base import MarketBase, s_decimal_NaN
from hummingbot.market.trading_rule import TradingRule

bpm_logger = None

cdef class BinancePerpetualMarket(MarketBase):
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

    # ABSTRACT IMPLEMENTATION ---

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        return self._order_book_tracker.order_books

    @property
    def ready(self):
        raise NotImplementedError

    @property
    def limit_orders(self):
        raise NotImplementedError

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
        raise NotImplementedError

    def c_sell(self, trading_pair, amount, order_type=OrderType.MARKET, price=s_decimal_NaN, kwargs={}):
        raise NotImplementedError

    async def get_active_exchange_markets(self):
        raise NotImplementedError

    async def get_deposit_info(self, asset: str):
        raise NotImplementedError

    async def cancel_all(self, timeout_seconds: float):
        raise NotImplementedError

    def c_cancel(self, trading_pair, client_order_id):
        raise NotImplementedError

    def c_stop_tracking_order(self, order_id):
        raise NotImplementedError

    def c_get_fee(self, base_currency, quote_currency, order_type, order_side, amount, price):
        raise NotImplementedError

    def c_withdraw(self, address, currency, amount):
        raise NotImplementedError

    def c_get_order_book(self, trading_pair):
        raise NotImplementedError

    def c_get_order_price_quantum(self, trading_pair, price):
        raise NotImplementedError

    def c_get_order_size_quantum(self, trading_pair, order_size):
        raise NotImplementedError

    # Helper Functions ---
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
        amount = self.c_quantize_order_amount(trading_pair, amount)
        price = Decimal("NaN") if order_type == OrderType.MARKET else self.c_quantize_order_price(trading_pair, price)

        # if amount < trading_rule.min_order_size:
        #     raise ValueError(f"Buy order amount {amount} is lower than the minimum order size "
        #                      f"{trading_rule.min_order_size}")

        order_result = None
        api_params = {"symbol": trading_pair,
                      "side": "BUY" if trade_type is TradeType.BUY else "SELL",
                      "type": order_type.name.upper(),
                      "quantity": f"{amount}",
                      "newClientOrderId": order_id}
        if order_type != OrderType.MARKET:
            api_params["price"] = f"{price}"
        if order_type == OrderType.LIMIT:
            api_params["timeInForce"] = "GTC"

        # TODO: Uncomment when implemented
        # self.c_start_tracking_order(order_id, "", trading_pair, trade_type, price, amount, order_type)

        try:
            order_result = await self.signed_request("order", api_params)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            # TODO: Uncomment when implemented
            # self.c_stop_tracking_order(order_id)

            self.logger().network(
                f"Error submitting order to Binance Perpetuals for {amount} {trading_pair} "
                f"{''if order_type is OrderType.MARKET else price}.",
                exc_info=True,
                app_warning_msg=str(e)
            )
            self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                 MarketOrderFailureEvent(self._current_timestamp, order_id, order_type))

    async def signed_request(self, path: str, params, request_weight: int = 1):
        async with self._throttler.weighted_task(request_weight):
            try:
                async with aiohttp.ClientSession() as client:
                    secret = bytes(self._binance_api_secret.encode("utf-8"))
                    signature = hmac.new(secret, params.encode("utf-8"), hashlib.sha256).hexdigest()
                    query = urlencode(sorted(params.items())) + f"&timestamp={int(time.time()) * 1000}" \
                                                                f"&signature={signature}"

                    response = await safe_gather(
                        client.post("https://fapi.binance.com/fapi/v1/" + path + "?" + query,
                                    headers={"X-MBX-APIKEY": self._binance_api_key})
                    )
                    if response.status != 200:
                        raise IOError(f"Error fetching data from {path}. HTTP status is {response.status}.")
            except Exception as e:
                self.logger().warning(f"Error fetching {path}")
                raise e

    cdef c_start_tracking_order(self, str order_id, str exchange_order_id, str trading_pair, object trading_type,
                                object price, object amount, object order_type):
        raise NotImplementedError

    cdef c_stop_tracking_order(self, str order_id):
        raise NotImplementedError

    cdef c_did_timout_tx(self, str tracking_id):
        raise NotImplementedError
