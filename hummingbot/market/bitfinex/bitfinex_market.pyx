import asyncio
import collections
import json
import logging
import time
from decimal import Decimal
from typing import Optional, List, Dict, Any, AsyncIterable, Tuple

import aiohttp
from libc.stdint cimport int64_t
from libcpp cimport bool

import conf
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.core.data_type.order_book_tracker import OrderBookTrackerDataSourceType
from hummingbot.core.data_type.transaction_tracker import TransactionTracker
from hummingbot.core.event.events import (
    BuyOrderCreatedEvent,
    MarketEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    SellOrderCreatedEvent,
    TradeFee,
    TradeType,
    OrderFilledEvent,
    BuyOrderCompletedEvent,
    SellOrderCompletedEvent,
)
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.logger import HummingbotLogger
from hummingbot.market.bitfinex import (
    BITFINEX_REST_AUTH_URL,
    BITFINEX_REST_URL,
    SubmitOrder,
    ContentEventType,
    TRADING_PAIR_SPLITTER,
    MIN_BASE_AMOUNT_INCREMENT,
)
from hummingbot.market.market_base import (
    MarketBase,
    OrderType,
)
from hummingbot.market.bitfinex.bitfinex_auth import BitfinexAuth
from hummingbot.market.bitfinex.bitfinex_in_flight_order cimport BitfinexInFlightOrder
from hummingbot.market.bitfinex.bitfinex_order_book_tracker import \
    BitfinexOrderBookTracker
from hummingbot.market.bitfinex.bitfinex_user_stream_tracker import \
    BitfinexUserStreamTracker
from hummingbot.market.trading_rule cimport TradingRule

s_logger = None
s_decimal_0 = Decimal(0)
general_order_size_quantum = Decimal(conf.bitfinex_quote_increment)

Wallet = collections.namedtuple('Wallet',
                                'wallet_type currency balance unsettled_interest balance_available')


cdef class BitfinexMarketTransactionTracker(TransactionTracker):
    cdef:
        BitfinexMarket _owner

    def __init__(self, owner: BitfinexMarket):
        super().__init__()
        self._owner = owner

    cdef c_did_timeout_tx(self, str tx_id):
        TransactionTracker.c_did_timeout_tx(self, tx_id)
        self._owner.c_did_timeout_tx(tx_id)

cdef class BitfinexMarket(MarketBase):
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
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(__name__)
        return s_logger

    def __init__(self,
                 bitfinex_api_key: str,
                 bitfinex_secret_key: str,
                 poll_interval: float = 5.0,
                 # interval which the class periodically pulls status from the rest API
                 order_book_tracker_data_source_type: OrderBookTrackerDataSourceType =
                 OrderBookTrackerDataSourceType.EXCHANGE_API,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True):
        super().__init__()

        self._ev_loop = asyncio.get_event_loop()
        self._poll_notifier = asyncio.Event()

        self._trading_required = trading_required
        self._bitfinex_auth = BitfinexAuth(bitfinex_api_key, bitfinex_secret_key)
        self._order_book_tracker = BitfinexOrderBookTracker(
            data_source_type=order_book_tracker_data_source_type,
            trading_pairs=trading_pairs)
        self._user_stream_tracker = BitfinexUserStreamTracker(
            bitfinex_auth=self._bitfinex_auth, trading_pairs=trading_pairs)
        self._tx_tracker = BitfinexMarketTransactionTracker(self)

        self._last_timestamp = 0
        self._last_order_update_timestamp = 0
        self._poll_interval = poll_interval
        self._in_flight_orders = {}
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
        """
        *required
        :return: A lowercase name / id for the market. Must stay consistent with market name in global settings.
        """
        return "bitfinex"

    @property
    def bitfinex_auth(self) -> BitfinexAuth:
        """
        """
        return self._bitfinex_auth

    cdef c_tick(self, double timestamp):
        """
        *required
        Used by top level Clock to orchestrate components of the bot.
        This function is called frequently with every clock tick
        """
        cdef:
            int64_t last_tick = <int64_t> (self._last_timestamp / self._poll_interval)
            int64_t current_tick = <int64_t> (timestamp / self._poll_interval)

        MarketBase.c_tick(self, timestamp)
        if current_tick > last_tick:
            if not self._poll_notifier.is_set():
                self._poll_notifier.set()
        self._last_timestamp = timestamp

    @property
    def ready(self) -> bool:
        """
        *required
        :return: a boolean value that indicates if the market is ready for trading
        """
        return all(self.status_dict.values())

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        """
        *required
        Get mapping of all the order books that are being tracked.
        :return: Dict[trading_pair : OrderBook]
        """
        return self._order_book_tracker.order_books

    @property
    def status_dict(self) -> Dict[str]:
        """
        *required
        :return: a dictionary of relevant status checks.
        This is used by `ready` method below to determine if a market is ready for trading.
        """
        return {
            # info about bids| ask and other stuffs
            "order_books_initialized": self._order_book_tracker.ready,
            # info from wallets
            "account_balance": len(
                self._account_balances) > 0 if self._trading_required else True,
            # take info about trading pairs
            "trading_rule_initialized":
                len(self._trading_rules) > 0 if self._trading_required else True
        }

    cdef object c_get_fee(self,
                          str base_currency,
                          str quote_currency,
                          object order_type,
                          object order_side,
                          object amount,
                          object price):
        """
        *required
        function to calculate fees for a particular order
        :returns: TradeFee class that includes fee percentage and flat fees
        """
        # There is no API for checking user's fee tier
        # Fee info from https://www.bitfinex.com/fees
        cdef:
            object maker_fee = Decimal("0.001")
            object taker_fee = Decimal("0.002")

        return TradeFee(
            percent=maker_fee if order_type is OrderType.LIMIT else taker_fee)

    async def _update_balances(self):
        """
        Pulls the API for updated balances
        """
        cdef:
            dict account_info
            list balances
            str asset_name
            set local_asset_names = set(self._account_balances.keys())
            set remote_asset_names = set()
            set asset_names_to_remove

        account_balances = await self._api_balance()

        # push trading-pairs-info, that set in config
        for balance_entry in account_balances:
            # TODO: need more info about other types: exchange, margin, funding.
            #  Now work only with EXCHANGE
            if balance_entry.wallet_type != "exchange":
                continue
            asset_name = balance_entry.currency
            # None or 0
            available_balance = Decimal(balance_entry.balance_available or 0)
            total_balance = Decimal(balance_entry.balance or 0)
            self._account_available_balances[asset_name] = available_balance
            self._account_balances[asset_name] = total_balance
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    async def check_network(self) -> NetworkStatus:
        """
        *required
        Async function used by NetworkBase class to check if the market is online / offline.
        """
        try:
            await self._api_platform_status()
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    async def start_network(self):
        """
        *required
        Async function used by NetworkBase class to handle when a single market goes online
        """
        if self._order_tracker_task is not None:
            self._stop_network()
        # when exchange is online start streams
        self._order_tracker_task = safe_ensure_future(self._order_book_tracker.start())
        if self._trading_required:
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())
            self._trading_rules_polling_task = safe_ensure_future(self._trading_rules_polling_loop())
            self._user_stream_tracker_task = safe_ensure_future(self._user_stream_tracker.start())
            self._user_stream_event_listener_task = safe_ensure_future(self._user_stream_event_listener())

    async def _status_polling_loop(self):
        """
        Background process that periodically pulls for changes from the rest API
        """
        while True:
            try:
                self._poll_notifier = asyncio.Event()
                await self._poll_notifier.wait()
                await safe_gather(
                    self._update_balances(),
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unexpected error while fetching account updates.",
                    exc_info=True,
                    app_warning_msg=f"Could not fetch account updates on Bitfinex. "
                )

    async def _trading_rules_polling_loop(self):
        """
        Separate background process that periodically pulls for trading rule changes
        (Since trading rules don't get updated often, it is pulled less often.)
        """
        while True:
            try:
                await safe_gather(self._update_trading_rules())
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unexpected error while fetching trading rules.",
                    exc_info=True,
                    app_warning_msg=f"Could not fetch trading rule updates on Bitfinex. "
                                    f"Check network connection."
                )
                await asyncio.sleep(0.5)

    async def _api_balance(self):
        path_url = "auth/r/wallets"
        account_balances = await self._api_private("post", path_url=path_url, data={})
        wallets = []
        for balance_entry in account_balances:
            wallets.append(Wallet._make(balance_entry[:5]))
        return wallets

    async def _api_platform_status(self):
        path_url = "platform/status"
        platform_status = await self._api_public("get", path_url=path_url)
        return platform_status

    async def _api_platform_config_pair_info(self):
        path_url = "conf/pub:info:pair"
        info = await self._api_public("get", path_url=path_url)
        return info[0] if len(info) > 0 else 0

    async def _api_public(self,
                          http_method: str,
                          path_url,
                          data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:

        url = f"{BITFINEX_REST_URL}/{path_url}"
        req = await self._api_do_request(http_method, url, None, data)
        return req

    async def _api_private(self,
                           http_method: str,
                           path_url,
                           data: Optional[Dict[Any]] = None) -> Dict[Any]:

        url = f"{BITFINEX_REST_AUTH_URL}/{path_url}"
        data_str = json.dumps(data)
        #  because BITFINEX_REST_AUTH_URL already have v2  postfix, but v2 need
        #  for generate right signature for path
        headers = self.bitfinex_auth.generate_api_headers(f"v2/{path_url}", data_str)

        req = await self._api_do_request(http_method=http_method,
                                         url=url,
                                         headers=headers,
                                         data_str=data)
        return req

    async def _api_do_request(self,
                              http_method: str,
                              url,
                              headers,
                              data_str: Optional[str, list] = None) -> list:
        """
        A wrapper for submitting API requests to Bitfinex
        :returns: json data from the endpoints
        """

        client = await self._http_client()
        async with client.request(http_method,
                                  url=url, timeout=self.API_CALL_TIMEOUT, json=data_str,
                                  headers=headers) as response:
            data = await response.json()
            if response.status != 200:
                raise IOError(
                    f"Error fetching data from {url}. HTTP status is {response.status}. {data}")
            return data

    async def _http_client(self) -> aiohttp.ClientSession:
        """
        :returns: Shared client session instance
        """
        if self._shared_client is None:
            self._shared_client = aiohttp.ClientSession()
        return self._shared_client

    cdef object c_get_order_size_quantum(self, str trading_pair, object order_size):
        """
        *required
        Get the minimum increment interval for order size (e.g. 0.01 USD)
        :return: Min order size increment in Decimal format
        """
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]
        # is set manually. For ETH is 0.04 increment-step 0.01
        return trading_rule.min_base_amount_increment

    cdef object c_quantize_order_amount(self, str trading_pair, object amount, object price=s_decimal_0):
        """
        *required
        Note: Bitfinex does not provide API for correct order sizing. Hardcoded 0.05 minimum and 0.01 precision
        until better information is available.
        :return: Valid order amount in Decimal format
        """

        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]

        global s_decimal_0

        quantized_amount = MarketBase.c_quantize_order_amount(self, trading_pair, amount)
        # Check against min_order_size. If not passing either check, return 0.
        if quantized_amount < trading_rule.min_order_size:
            return s_decimal_0

        # Check against max_order_size. If not passing either check, return 0.
        if quantized_amount > trading_rule.max_order_size:
            return s_decimal_0

        return quantized_amount

    cdef OrderBook c_get_order_book(self, str trading_pair):
        """
        :returns: OrderBook for a specific trading pair
        """
        cdef:
            dict order_books = self._order_book_tracker.order_books

        if trading_pair not in order_books:
            raise ValueError(f"No order book exists for '{trading_pair}'.")
        return order_books[trading_pair]

    cdef object c_get_order_price_quantum(self, str trading_pair, object price):
        """
        *required
        Get the minimum increment interval for price
        :return: Min order price increment in Decimal format
        """
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]
        return trading_rule.min_price_increment

    async def _update_trading_rules(self):
        """
        Pulls the API for trading rules (min / max order size, etc)
        """
        cdef:
            # The poll interval for withdraw rules is 60 seconds.
            int64_t last_tick = <int64_t> (self._last_timestamp / 60.0)
            int64_t current_tick = <int64_t> (self._current_timestamp / 60.0)

        if current_tick > last_tick or len(self._trading_rules) <= 0:
            info = await self._api_platform_config_pair_info()
            trading_rules_list = self._format_trading_rules(info)
            self._trading_rules.clear()
            for trading_rule in trading_rules_list:
                self._trading_rules[trading_rule.trading_pair] = trading_rule

    def _format_trading_rules(self, raw_trading_rules: List[Any]) -> List[TradingRule]:
        """
        Turns json data from API into TradingRule instances
        :returns: List of TradingRule
        """
        cdef:
            list retval = []
        for rule in raw_trading_rules:
            try:
                trading_pair_id = rule[0]
                retval.append(
                    TradingRule(trading_pair_id,
                                min_price_increment=Decimal(conf.bitfinex_quote_increment),
                                min_order_size=Decimal(str(rule[1][3])),
                                min_base_amount_increment=MIN_BASE_AMOUNT_INCREMENT,
                                min_quote_amount_increment=MIN_BASE_AMOUNT_INCREMENT,
                                max_order_size=Decimal(str(rule[1][4]))))
            except Exception:
                self.logger().error(
                    f"Error parsing the trading_pair rule {rule}. Skipping.",
                    exc_info=True)
        return retval

    #  buy func
    async def place_order(self,
                          order_id: str,
                          trading_pair: str,
                          amount: Decimal,
                          is_buy: bool,
                          order_type: OrderType,
                          price: Decimal):
        """
        Async wrapper for placing orders through the rest API.
        :returns: json response from the API
        """
        path_url = "auth/w/order/submit"
        data = {
            "type": {
                OrderType.LIMIT.name: "EXCHANGE LIMIT",
                OrderType.MARKET.name: "MARKET",
            }[order_type.name],  # LIMIT, EXCHANGE
            "symbol": f't{trading_pair}',
            "price": str(price),
            "amount": str(amount),
            "flags": 0,
        }

        order_result = await self._api_private("post", path_url=path_url, data=data)
        return order_result

    cdef c_start_tracking_order(self,
                                str client_order_id,
                                str trading_pair,
                                object order_type,
                                object trade_type,
                                object price,
                                object amount):
        """
        Add new order to self._in_flight_orders mapping
        """
        self._in_flight_orders[client_order_id] = BitfinexInFlightOrder(
            client_order_id,
            None,
            trading_pair,
            order_type,
            trade_type,
            price,
            amount,
        )

    cdef str c_buy(self, str trading_pair, object amount,
                   object order_type=OrderType.MARKET, object price=s_decimal_0,
                   dict kwargs={}):
        """
        *required
        Synchronous wrapper that generates a client-side order ID and schedules the buy order.
        """
        cdef:
            int64_t tracking_nonce = <int64_t> (time.time() * 1e6)
            str order_id = str(f"buy-{trading_pair}-{tracking_nonce}")

        safe_ensure_future(
            self.execute_buy(order_id, trading_pair, amount, order_type, price))
        return order_id

    async def execute_buy(self,
                          order_id: str,
                          trading_pair: str,
                          amount: Decimal,
                          order_type: OrderType,
                          price: Optional[Decimal] = s_decimal_0):
        """
        Function that takes strategy inputs, auto corrects itself with trading rule,
        and submit an API request to place a buy order
        """
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]

        decimal_amount = self.quantize_order_amount(trading_pair, amount)
        decimal_price = self.quantize_order_price(trading_pair, price)
        if decimal_amount < trading_rule.min_order_size:
            raise ValueError(
                f"Buy order amount {decimal_amount} is lower than the minimum order size "
                f"{trading_rule.min_order_size}.")

        try:
            self.c_start_tracking_order(order_id, trading_pair, order_type,
                                        TradeType.BUY, decimal_price, decimal_amount)
            order_result = await self.place_order(order_id, trading_pair,
                                                  decimal_amount, True, order_type,
                                                  decimal_price)

            exchange_order = SubmitOrder.parse(order_result[4][0])
            exchange_order_id = exchange_order.oid

            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(
                    f"Created {order_type} buy order {order_id} for {decimal_amount} {trading_pair}.")
                tracked_order.update_exchange_order_id(exchange_order_id)

            self.c_trigger_event(self.MARKET_BUY_ORDER_CREATED_EVENT_TAG,
                                 BuyOrderCreatedEvent(self._current_timestamp,
                                                      order_type,
                                                      trading_pair,
                                                      decimal_amount,
                                                      decimal_price,
                                                      order_id))
        except asyncio.CancelledError:
            raise
        except Exception:
            self.c_stop_tracking_order(order_id)
            order_type_str = "MARKET" if order_type == OrderType.MARKET else "LIMIT"
            self.logger().network(
                f"Error submitting buy {order_type_str} order to Bitfinex for "
                f"{decimal_amount} {trading_pair} {price}.",
                exc_info=True,
                app_warning_msg="Failed to submit buy order to Bitfinex. "
                                "Check API key and network connection."
            )
            self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                 MarketOrderFailureEvent(self._current_timestamp,
                                                         order_id, order_type))

    cdef c_stop_tracking_order(self, str order_id):
        """
        Delete an order from self._in_flight_orders mapping
        """
        if order_id in self._in_flight_orders:
            del self._in_flight_orders[order_id]

    # sell
    cdef str c_sell(self,
                    str trading_pair,
                    object amount,
                    object order_type=OrderType.MARKET,
                    object price=s_decimal_0,
                    dict kwargs={}):
        """
        *required
        Synchronous wrapper that generates a client-side order ID and schedules the sell order.
        """
        cdef:
            # TODO: в доках используют time.time() надо разобратсья почему тут умножение
            int64_t tracking_nonce = <int64_t>(time.time() * 1e6)
            str order_id = str(f"sell-{trading_pair}-{tracking_nonce}")
        safe_ensure_future(self.execute_sell(order_id, trading_pair, amount, order_type, price))
        return order_id

    async def execute_sell(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           order_type: OrderType,
                           price: Optional[Decimal] = s_decimal_0):
        """
        Function that takes strategy inputs, auto corrects itself with trading rule,
        and submit an API request to place a sell order
        """
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]

        decimal_amount = self.quantize_order_amount(trading_pair, abs(amount))
        decimal_price = self.quantize_order_price(trading_pair, price)
        if decimal_amount < trading_rule.min_order_size:
            raise ValueError(f"Sell order amount {decimal_amount} is lower than the minimum order size "
                             f"{trading_rule.min_order_size}.")

        try:
            # sell - is negative amount
            decimal_amount *= -1
            self.c_start_tracking_order(order_id, trading_pair, order_type, TradeType.SELL, decimal_price, decimal_amount)
            order_result = await self.place_order(order_id, trading_pair, decimal_amount, False, order_type, decimal_price)

            exchange_order = SubmitOrder.parse(order_result[4][0])
            exchange_order_id = exchange_order.oid

            tracked_order = self._in_flight_orders.get(order_id)

            if tracked_order is not None:
                self.logger().info(f"Created {order_type} sell order {order_id} for {decimal_amount} {trading_pair}.")
                tracked_order.update_exchange_order_id(exchange_order_id)

            self.c_trigger_event(self.MARKET_SELL_ORDER_CREATED_EVENT_TAG,
                                 SellOrderCreatedEvent(self._current_timestamp,
                                                       order_type,
                                                       trading_pair,
                                                       decimal_amount,
                                                       decimal_price,
                                                       order_id))
        except asyncio.CancelledError:
            raise
        except Exception:
            self.c_stop_tracking_order(order_id)
            order_type_str = "MARKET" if order_type == OrderType.MARKET else "LIMIT"
            self.logger().network(
                f"Error submitting sell {order_type_str} order to Bitfinex for "
                f"{decimal_amount} {trading_pair} {price}.",
                exc_info=True,
                app_warning_msg="Failed to submit sell order to Bitfinex. "
                                "Check API key and network connection."
            )
            self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                 MarketOrderFailureEvent(self._current_timestamp, order_id, order_type))

    async def execute_cancel(self, trading_pair: str, order_id: str):
        """
        Function that makes API request to cancel an active order
        """
        try:
            exchange_order_id = await self._in_flight_orders.get(order_id).get_exchange_order_id()
            path_url = "auth/w/order/cancel"

            data = {
                "id": int(exchange_order_id)
            }

            cancel_result = await self._api_private("post", path_url=path_url, data=data)
            # return order_id
            self.logger().info(f"Successfully cancelled order {order_id}.")
            self.c_stop_tracking_order(order_id)
            self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                 OrderCancelledEvent(self._current_timestamp, order_id))
            return order_id

        except IOError as e:
            if "order not found" in e.message:
                # The order was never there to begin with. So cancelling it is a no-op but semantically successful.
                self.logger().info(f"The order {order_id} does not exist on Bitfinex. No cancellation needed.")
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
                app_warning_msg=f"Failed to cancel the order {order_id} on Bitfinex. "
                                f"Check API key and network connection."
            )
        return None

    cdef c_cancel(self, str trading_pair, str order_id):
        """
        *required
        Synchronous wrapper that schedules cancelling an order.
        """
        safe_ensure_future(self.execute_cancel(trading_pair, order_id))
        return order_id

    # streamer
    @staticmethod
    def split_trading_pair(trading_pair: str) -> Tuple[str, str]:
        try:
            # from exchange trading-pair is ETHUSD, split by regex
            m = TRADING_PAIR_SPLITTER.match(trading_pair)
            return m.group(1), m.group(2)
        except Exception as e:
            raise ValueError(f"Error parsing trading_pair {trading_pair}: {str(e)}")

    async def _iter_user_event_queue(self) -> AsyncIterable[Dict[str, Any]]:
        """
        Iterator for incoming messages from the user stream.
        """
        while True:
            try:
                yield await self._user_stream_tracker.user_stream.get()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unknown error. Retrying after 1 seconds.", exc_info=True)
                await asyncio.sleep(1.0)

    def parse_message_content(self, oid, _type, content=None):
        # listen only this events
        if _type not in [ContentEventType.TRADE_UPDATE]:
            return
        data = {
            "type": _type,
            "order_id": 0,
            "maker_order_id": 0,
            "taker_order_id": 0,
            "price": 0,
            "amount": 0,
            "reason": "",
        }

        # [CHAN_ID, TYPE, [ID,    SYMBOL,  MTS_CREATE,  ORDER_ID,   EXEC_AMOUNT....
        # [0,       'te', [40xx, 'tETHUSD', 157613xxxx, 3566953xxx, 0.04, .....
        # .. EXEC_PRICE, ORDER_TYPE,      ORDER_PRICE  MAKER    FEE   FEE_CURRENCY
        # .. 142.88,    'EXCHANGE LIMIT', 142.88,      1,       None, None, 1576132037108]]
        if _type == ContentEventType.TRADE_UPDATE:
            data["order_id"] = content[3]
            # if amount is negative it mean sell, if positive is's buy.
            # zero no can, because minimal step is present. fot eth is 0.04
            # maker_order_id - this “makes” the marketplace; like products on
            #   a store shelf - buy
            # taker_order_id - “taker” consumes the book liquidity by ‘taking’
            #   an order from the order book  - sell
            data["maker_order_id"] = content[3] if content[4] > 0 else None
            data["taker_order_id"] = content[3] if content[4] < 0 else None
            data["price"] = content[5]
            data["amount"] = content[4]

        return data

    async def _user_stream_event_listener(self):
        """
        Update order statuses from incoming messages from the user stream
        """
        async for event_message in self._iter_user_event_queue():
            self.logger().info(f"event come from exchange: {event_message.content[:2]}")

            try:
                content = self.parse_message_content(*event_message.content)
                if not content:
                    continue
                event_type = content.get("type")
                # str - because from exchange come int; order.exchange_order_id is str
                exchange_order_ids = [str(content.get("order_id")),
                                      str(content.get("maker_order_id")),
                                      str(content.get("taker_order_id"))]

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

                # trade update is like rollup state. each event increment
                # amount and price. When amount is 0, it will meant order fill.
                if event_type in [ContentEventType.TRADE_UPDATE]:
                    # amount_come - negative is sell, positive - buy.
                    # for checking that order is fill
                    amount_come = Decimal(content["amount"]).quantize(Decimal('1e-8'))
                    execute_amount_diff = (abs(tracked_order.amount) - abs(amount_come)).quantize(Decimal('1e-8'))
                    tracked_order.executed_amount_base += abs(amount_come)
                    tracked_order.executed_amount_quote += abs(amount_come) * execute_price

                if execute_amount_diff == s_decimal_0.quantize(Decimal('1e-8')) \
                        and event_type in [ContentEventType.TRADE_UPDATE]:
                    self.logger().info(f"Order filled {execute_amount_diff} out of {tracked_order.amount} of the "
                                       f"{order_type_description} order {tracked_order.client_order_id}")
                    self.c_trigger_event(self.MARKET_ORDER_FILLED_EVENT_TAG,
                                         OrderFilledEvent(
                                             self._current_timestamp,
                                             tracked_order.client_order_id,
                                             tracked_order.trading_pair,
                                             tracked_order.trade_type,
                                             tracked_order.order_type,
                                             execute_price,
                                             tracked_order.executed_amount_base,
                                             self.c_get_fee(
                                                 tracked_order.base_asset,
                                                 tracked_order.quote_asset,
                                                 tracked_order.order_type,
                                                 tracked_order.trade_type,
                                                 execute_price,
                                                 execute_amount_diff,
                                             ),
                                             exchange_trade_id=tracked_order.exchange_order_id
                                         ))
                    # buy
                    if content["maker_order_id"]:
                        if tracked_order.trade_type == TradeType.BUY:
                            self.logger().info(f"The market buy order {tracked_order.client_order_id} has completed "
                                               f"according to Bitfinex user stream.")
                            self.c_trigger_event(self.MARKET_BUY_ORDER_COMPLETED_EVENT_TAG,
                                                 BuyOrderCompletedEvent(self._current_timestamp,
                                                                        tracked_order.client_order_id,
                                                                        tracked_order.quote_asset,
                                                                        tracked_order.base_asset,
                                                                        (tracked_order.fee_asset
                                                                         or tracked_order.base_asset),
                                                                        tracked_order.executed_amount_base,
                                                                        tracked_order.executed_amount_quote,
                                                                        tracked_order.fee_paid,
                                                                        tracked_order.order_type))
                        self.c_stop_tracking_order(tracked_order.client_order_id)
                    # sell
                    if content["taker_order_id"]:
                        if tracked_order.trade_type == TradeType.SELL:
                            self.logger().info(f"The market sell order {tracked_order.client_order_id} has completed "
                                               f"according to Bitfinex user stream.")

                            self.c_trigger_event(self.MARKET_SELL_ORDER_COMPLETED_EVENT_TAG,
                                                 SellOrderCompletedEvent(self._current_timestamp,
                                                                         tracked_order.client_order_id,
                                                                         tracked_order.base_asset,
                                                                         tracked_order.quote_asset,
                                                                         (tracked_order.fee_asset
                                                                          or tracked_order.quote_asset),
                                                                         tracked_order.executed_amount_base,
                                                                         tracked_order.executed_amount_quote,
                                                                         tracked_order.fee_paid,
                                                                         tracked_order.order_type))
                        self.c_stop_tracking_order(tracked_order.client_order_id)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await asyncio.sleep(5.0)
