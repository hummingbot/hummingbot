import asyncio
import collections
import json
import logging
import time
import uuid

from decimal import Decimal
from typing import Any, AsyncIterable, Dict, List, Optional

import aiohttp

from libc.stdint cimport int64_t
from libcpp cimport bool

from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.connector.exchange.bitfinex import (
    AFF_CODE,
    BITFINEX_REST_AUTH_URL,
    BITFINEX_REST_URL,
    BITFINEX_REST_URL_V1,
    ContentEventType,
    OrderStatus,
)
from hummingbot.connector.exchange.bitfinex.bitfinex_auth import BitfinexAuth
from hummingbot.connector.exchange.bitfinex.bitfinex_in_flight_order cimport BitfinexInFlightOrder
from hummingbot.connector.exchange.bitfinex.bitfinex_order_book_tracker import BitfinexOrderBookTracker
from hummingbot.connector.exchange.bitfinex.bitfinex_user_stream_tracker import BitfinexUserStreamTracker
from hummingbot.connector.exchange.bitfinex.bitfinex_utils import (
    convert_from_exchange_token,
    convert_from_exchange_trading_pair,
    convert_to_exchange_trading_pair,
    get_precision,
)
from hummingbot.connector.exchange.bitfinex.bitfinex_websocket import BitfinexWebsocket
from hummingbot.connector.trading_rule cimport TradingRule
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.core.data_type.transaction_tracker import TransactionTracker
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderFilledEvent,
    OrderType,
    SellOrderCompletedEvent,
    SellOrderCreatedEvent,
    TradeType,
)
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.utils.estimate_fee import estimate_fee
from hummingbot.logger import HummingbotLogger


s_logger = None
s_decimal_0 = Decimal(0)
s_decimal_nan = Decimal("nan")

Wallet = collections.namedtuple('Wallet',
                                'wallet_type currency balance unsettled_interest balance_available')

OrderRetrieved = collections.namedtuple(
    "OrderRetrived",
    "id gid cid symbol mts_create mts_update "
    "amount amount_orig type type_prev n1 n2 "
    "flags status n3 n4 price price_exec"
)  # 18


cdef class BitfinexExchangeTransactionTracker(TransactionTracker):
    cdef:
        BitfinexExchange _owner

    def __init__(self, owner: BitfinexExchange):
        super().__init__()
        self._owner = owner

    cdef c_did_timeout_tx(self, str tx_id):
        TransactionTracker.c_did_timeout_tx(self, tx_id)
        self._owner.c_did_timeout_tx(tx_id)


cdef class BitfinexExchange(ExchangeBase):
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
    UPDATE_ORDERS_INTERVAL = 10.0
    ORDER_NOT_EXIST_CONFIRMATION_COUNT = 3

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(__name__)
        return s_logger

    def __init__(self,
                 bitfinex_api_key: str,
                 bitfinex_secret_key: str,
                 # interval which the class periodically pulls status from the rest API
                 poll_interval: float = 5.0,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True):
        super().__init__()

        self._ev_loop = asyncio.get_event_loop()
        self._poll_notifier = asyncio.Event()

        self._trading_required = trading_required
        self._bitfinex_auth = BitfinexAuth(bitfinex_api_key, bitfinex_secret_key)
        self._order_book_tracker = BitfinexOrderBookTracker(trading_pairs)
        self._user_stream_tracker = BitfinexUserStreamTracker(
            bitfinex_auth=self._bitfinex_auth, trading_pairs=trading_pairs)
        self._tx_tracker = BitfinexExchangeTransactionTracker(self)

        self._last_timestamp = 0
        self._last_order_update_timestamp = 0
        self._poll_interval = poll_interval
        self._in_flight_orders = {}
        self._trading_rules = {}
        self._order_not_found_records = {}
        self._status_polling_task = None
        self._order_tracker_task = None
        self._user_stream_tracker_task = None
        self._user_stream_event_listener_task = None
        self._trading_rules_polling_task = None
        self._shared_client = None
        self._pending_requests = []
        self._ws = BitfinexWebsocket(self._bitfinex_auth)
        self._ws_task = None

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
            int64_t last_tick = <int64_t > (self._last_timestamp / self._poll_interval)
            int64_t current_tick = <int64_t > (timestamp / self._poll_interval)

        ExchangeBase.c_tick(self, timestamp)
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

    @property
    def in_flight_orders(self) -> Dict[str, BitfinexInFlightOrder]:
        return self._in_flight_orders

    async def get_ws(self):
        if self._ws._client is None or self._ws._client.open is False:
            await self._ws.connect()
            await self._ws.authenticate()

        return self._ws

    cdef object c_get_fee(self,
                          str base_currency,
                          str quote_currency,
                          object order_type,
                          object order_side,
                          object amount,
                          object price,
                          object is_maker = None):
        """
        *required
        function to calculate fees for a particular order
        :returns: TradeFee class that includes fee percentage and flat fees
        """
        # There is no API for checking user's fee tier
        # Fee info from https://www.bitfinex.com/fees
        # cdef:
        #     object maker_fee = MAKER_FEE
        #     object taker_fee = TAKER_FEE

        # return TradeFee(
        #     percent=maker_fee if order_type is OrderType.LIMIT else taker_fee
        # )

        is_maker = order_type is OrderType.LIMIT
        return estimate_fee("bitfinex", is_maker)

    async def _request_calc(self, currencies):
        await self._ws.emit([
            0,
            "calc",
            None,
            list(map(
                lambda currency: [f"wallet_exchange_{currency}"],
                currencies
            ))
        ])

    # NOTICE: we only use WS to get balance data due to replay attack protection
    # TODO: reduce '_update_balances' timer and re-enable it
    async def _update_balances(self):
        """
        Pulls the API for updated balances
        """

        currencies = list(self._account_balances.keys())
        await self._request_calc(currencies)

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
            if balance_entry.wallet_type != "exchange":
                continue

            asset_name = balance_entry.currency
            asset_name = convert_from_exchange_token(asset_name)
            # None or 0
            self._account_balances[asset_name] = Decimal(balance_entry.balance or 0)
            self._account_available_balances[asset_name] = Decimal(balance_entry.balance) - Decimal(balance_entry.unsettled_interest)
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
        # when exchange is online start streams
        self._order_tracker_task = self._order_book_tracker.start()
        if self._trading_required:
            self._ws_task = safe_ensure_future(self._ws_message_listener())
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())
            self._trading_rules_polling_task = safe_ensure_future(self._trading_rules_polling_loop())
            self._user_stream_tracker_task = safe_ensure_future(self._user_stream_tracker.start())
            self._user_stream_event_listener_task = safe_ensure_future(self._user_stream_event_listener())

    async def stop_network(self):
        """
        *required
        Async wrapper for `self._stop_network`. Used by NetworkBase class to handle when a single market goes offline.
        """
        self._stop_network()

    def _stop_network(self):
        """
        Synchronous function that handles when a single market goes offline
        """
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
        if self._ws_task is not None:
            self._ws_task.cancel()

    async def _ws_message_listener(self):
        while True:
            try:
                await self._ws.connect()
                await self._ws.authenticate()

                async for msg in self._ws.messages():
                    pass

            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().network(
                    "Unexpected error while listeneing to messages.",
                    exc_info=True,
                    app_warning_msg=f"Could not listen to Bitfinex messages. "
                )

    async def _status_polling_loop(self):
        """
        Background process that periodically pulls for changes from the rest API
        """
        while True:
            try:
                self._poll_notifier = asyncio.Event()
                await self._poll_notifier.wait()
                # await self._update_balances()
                await self._update_order_status()

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
        path_url = "symbols_details"
        info = await self._api_public_v1("get", path_url=path_url)
        return info

    async def _api_public_v1(
        self,
        http_method: str,
        path_url,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        url = f"{BITFINEX_REST_URL_V1}/{path_url}"
        req = await self._api_do_request(http_method, url, None, data)
        return req

    async def _api_public(self,
                          http_method: str,
                          path_url,
                          data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:

        url = f"{BITFINEX_REST_URL}/{path_url}"
        req = await self._api_do_request(http_method, url, None, data)
        return req

    async def _api_private_fn(self,
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

    # here we queue authenticated rest api calls due to reply attack protection
    async def _api_private(self,
                           http_method: str,
                           path_url,
                           data: Optional[Dict[Any]] = None) -> Dict[Any]:

        id = uuid.uuid4()
        self._pending_requests.append(id)

        while (self._pending_requests[0] != id):
            await asyncio.sleep(0.1)

        try:
            return await self._api_private_fn(http_method, path_url, data)
        finally:
            self._pending_requests.pop(0)

    async def _api_do_request(self,
                              http_method: str,
                              url,
                              headers,
                              data_str: Optional[str, list] = None) -> list:
        """
        A wrapper for submitting API requests to Bitfinex
        :returns: json data from the endpoints
        """

        try:
            client = await self._http_client()
            async with client.request(http_method,
                                      url=url, timeout=self.API_CALL_TIMEOUT, json=data_str,
                                      headers=headers) as response:
                data = await response.json()

                if response.status != 200:
                    raise IOError(
                        f"Error fetching data from {url}. HTTP status is {response.status}. {data}")

                return data
        except Exception as e:
            self.logger().network(
                f"Failed to do order",
                exc_info=True,
                app_warning_msg=f"Failed to do order on Bitfinex. Check API key and network connection."
            )

        return None

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

        quantized_amount = ExchangeBase.c_quantize_order_amount(self, trading_pair, amount)
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
            int64_t last_tick = <int64_t > (self._last_timestamp / 60.0)
            int64_t current_tick = <int64_t > (self._current_timestamp / 60.0)

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
                exchange_trading_pair = rule["pair"].upper()
                trading_pair = convert_from_exchange_trading_pair(exchange_trading_pair)
                precision = get_precision(rule["price_precision"])

                retval.append(
                    TradingRule(
                        trading_pair,
                        min_price_increment=precision,
                        min_base_amount_increment=precision,
                        min_quote_amount_increment=precision,
                        min_order_size=Decimal(str(rule["minimum_order_size"])),
                        max_order_size=Decimal(str(rule["maximum_order_size"])),
                    )
                )
            except Exception:
                self.logger().error(
                    f"Error parsing the trading_pair rule {rule}. Skipping.",
                    exc_info=True)
        return retval

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
        exchange_trading_pair = convert_to_exchange_trading_pair(trading_pair)

        data = [
            0,
            "on",
            None,
            {
                "type": {
                    OrderType.LIMIT.name: "EXCHANGE LIMIT",
                    OrderType.MARKET.name: "MARKET",
                }[order_type.name],
                "symbol": exchange_trading_pair,
                "price": str(price),
                "amount": str(amount),
                "meta": {
                    "order_id": order_id,
                    "aff_code": AFF_CODE
                }
            }
        ]

        def waitFor(msg):
            isN = msg[1] == "n"
            okEvent = msg[2][1] == "on-req"
            okOrderId = msg[2][4][31]["order_id"] == order_id
            isSuccess = msg[2][6] == "SUCCESS"

            if isN and okEvent and okOrderId:
                if isSuccess:
                    return True
                else:
                    raise IOError(f"Couldn't place order {order_id}")

            return False

        ws = await self.get_ws()
        await ws.emit(data)

        async for response in ws.messages(waitFor=waitFor):
            return response

    def start_tracking_order(self,
                             order_id: str,
                             trading_pair: str,
                             order_type: OrderType,
                             trade_type: TradeType,
                             price: Decimal,
                             amount: Decimal,):
        self.c_start_tracking_order(order_id, trading_pair, order_type, trade_type, price, amount)

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
            int64_t tracking_nonce = <int64_t > (time.time() * 1e6)
            str order_id = str(f"buy-{trading_pair}-{tracking_nonce}")

        safe_ensure_future(self.execute_buy(order_id, trading_pair, amount, order_type, price))
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
            self.c_start_tracking_order(
                order_id,
                trading_pair,
                order_type,
                TradeType.BUY,
                decimal_price,
                decimal_amount
            )
            order_result = await self.place_order(order_id, trading_pair,
                                                  decimal_amount, True, order_type,
                                                  decimal_price)

            # TODO: order_result needs to be ID
            exchange_order_id = str(order_result[2][4][0])

            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(
                    f"Created {order_type} buy order {order_id} for {decimal_amount} {trading_pair}."
                )
                tracked_order.update_exchange_order_id(exchange_order_id)

            self.c_trigger_event(
                self.MARKET_BUY_ORDER_CREATED_EVENT_TAG,
                BuyOrderCreatedEvent(
                    self._current_timestamp,
                    order_type,
                    trading_pair,
                    decimal_amount,
                    decimal_price,
                    order_id
                )
            )
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
            self.c_trigger_event(
                self.MARKET_ORDER_FAILURE_EVENT_TAG,
                MarketOrderFailureEvent(
                    self._current_timestamp,
                    order_id, order_type
                )
            )

    cdef c_stop_tracking_order(self, str order_id):
        """
        Delete an order from self._in_flight_orders mapping
        """
        if order_id in self._in_flight_orders:
            del self._in_flight_orders[order_id]

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
            int64_t tracking_nonce = <int64_t > (time.time() * 1e6)
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

            # TODO: order_result needs to be ID
            exchange_order_id = str(order_result[2][4][0])

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

            data = [
                0,
                "oc",
                None,
                {
                    "id": int(exchange_order_id)
                }
            ]

            def waitFor(msg):
                okEvent = msg[1] == "oc"
                okOrderId = msg[2][31]["order_id"] == order_id

                return okEvent and okOrderId

            ws = await self.get_ws()
            await ws.emit(data)

            response = None
            async for _response in ws.messages(waitFor=waitFor):
                response = _response
                break

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
        # .. EXEC_PRICE, ORDER_TYPE,      ORDER_PRICE, MAKER,   FEE,  FEE_CURRENCY, CID]]
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
            data["trade_id"] = content[0]
            data["price"] = content[5]
            data["amount"] = content[4]
            data["fee"] = content[9]
            data["fee_currency"] = content[10]

        return data

    async def _user_stream_event_listener(self):
        """
        Update order statuses from incoming messages from the user stream
        """
        async for event_message in self._iter_user_event_queue():
            try:
                isWallet = event_message[1] in [ContentEventType.WALLET_SNAPSHOT, ContentEventType.WALLET_UPDATE]

                # update balances
                if isWallet:
                    local_asset_names = set(self._account_balances.keys())
                    remote_asset_names = set()
                    asset_names_to_remove = set()

                    event_type = event_message[1]
                    content = event_message[2]
                    wallets = content if event_type == ContentEventType.WALLET_SNAPSHOT else [content]

                    for wallet in wallets:
                        wallet_type = wallet[0]
                        if (wallet_type != "exchange"):
                            continue

                        asset_name = convert_from_exchange_token(wallet[1])
                        balance = wallet[2]
                        balance_available = wallet[4]

                        self._account_balances[asset_name] = Decimal(balance or 0)
                        self._account_available_balances[asset_name] = Decimal(balance_available or 0)
                        # remote_asset_names.add(asset_name)

                    # asset_names_to_remove = local_asset_names.difference(remote_asset_names)
                    # for asset_name in asset_names_to_remove:
                    #     del self._account_available_balances[asset_name]
                    #     del self._account_balances[asset_name]

                # else (previous author)
                else:
                    self._process_trade_event(event_message)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await asyncio.sleep(5.0)

    def _process_trade_event(self, event_message: List[Any]):
        content = self.parse_message_content(*event_message)
        if not content:
            return
        event_type = content.get("type")
        # str - because from exchange come int; order.exchange_order_id is str
        exchange_order_ids = [
            str(content.get("order_id")),
            str(content.get("maker_order_id")),
            str(content.get("taker_order_id"))
        ]

        tracked_order = None
        for order in self._in_flight_orders.values():
            if order.exchange_order_id in exchange_order_ids:
                tracked_order = order
                break
        if tracked_order is None:
            return

        order_type_description = tracked_order.order_type_description
        execute_price = Decimal(content.get("price", 0.0))
        execute_amount_diff = s_decimal_0

        # trade update is like rollup state. each event increment
        # amount and price. When amount is 0, it will meant order fill.
        if event_type in [ContentEventType.TRADE_UPDATE]:
            updated = tracked_order.update_with_trade_update(content)

            if updated:
                amount_come = Decimal(str(content["amount"]))
                execute_amount_diff = (abs(tracked_order.amount) - abs(amount_come)).quantize(Decimal('1e-8'))

                self.logger().info(
                    f"Order filled {amount_come} out of {tracked_order.amount} of the "
                    f"{order_type_description} order {tracked_order.client_order_id}"
                )
                self.c_trigger_event(
                    self.MARKET_ORDER_FILLED_EVENT_TAG,
                    OrderFilledEvent(
                        self._current_timestamp,
                        tracked_order.client_order_id,
                        tracked_order.trading_pair,
                        tracked_order.trade_type,
                        tracked_order.order_type,
                        execute_price,
                        tracked_order.executed_amount_base,
                        AddedToCostTradeFee(
                            flat_fees=[TokenAmount(tracked_order.fee_asset, Decimal(str(content.get("fee"))))]
                        ),
                        exchange_trade_id=tracked_order.exchange_order_id
                    )
                )

                if tracked_order.is_done and not tracked_order.is_cancelled:
                    if tracked_order.trade_type == TradeType.BUY:
                        event_type = self.MARKET_BUY_ORDER_COMPLETED_EVENT_TAG
                        event_class = BuyOrderCompletedEvent
                    else:
                        event_type = self.MARKET_SELL_ORDER_COMPLETED_EVENT_TAG
                        event_class = SellOrderCompletedEvent

                    self.logger().info(
                        f"The market {tracked_order.trade_type.name.lower()} "
                        f"order {tracked_order.client_order_id} has completed "
                        "according to Bitfinex user stream."
                    )

                    self.c_trigger_event(
                        event_type,
                        event_class(
                            self._current_timestamp,
                            tracked_order.client_order_id,
                            tracked_order.base_asset,
                            tracked_order.quote_asset,
                            (tracked_order.fee_asset or tracked_order.quote_asset),
                            tracked_order.executed_amount_base,
                            tracked_order.executed_amount_quote,
                            tracked_order.fee_paid,
                            tracked_order.order_type
                        )
                    )
                    self.c_stop_tracking_order(tracked_order.client_order_id)

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        try:
            tracked_orders = self._in_flight_orders.copy().values()
            client_oids = list(map(lambda order: order.client_order_id, tracked_orders))
            exchange_oids = list(map(lambda order: int(order.exchange_order_id), tracked_orders))

            data = [
                0,
                "oc_multi",
                None,
                {
                    "id": exchange_oids
                }
            ]

            def waitFor(msg):
                return msg[1] == "n" and msg[2][1] == "oc_multi-req"

            ws = await self.get_ws()
            await ws.emit(data)

            response = None
            cancellation_results = []
            async for _response in ws.messages(waitFor=waitFor):
                cancelled_client_oids = [o[-1]['order_id'] for o in _response[2][4]]
                self.logger().info(f"Succesfully cancelled orders: {cancelled_client_oids}")
                for c_oid in cancelled_client_oids:
                    cancellation_results.append(CancellationResult(c_oid, True))
                break

            return cancellation_results
        except Exception as e:
            self.logger().network(
                f"Failed to cancel all orders: {client_oids}",
                exc_info=True,
                app_warning_msg=f"Failed to cancel all orders on Bitfinex. Check API key and network connection."
            )
            return list(map(lambda client_order_id: CancellationResult(client_order_id, False), client_oids))

    @property
    def limit_orders(self) -> List[LimitOrder]:
        """
        *required
        :return: list of active limit orders
        """
        return [
            in_flight_order.to_limit_order()
            for in_flight_order in self._in_flight_orders.values()
        ]

    # sqlite
    @property
    def tracking_states(self) -> Dict[str, any]:
        """
        *required
        :return: Dict[client_order_id: InFlightOrder]
        This is used by the MarketsRecorder class to orchestrate market classes at a higher level.
        """
        return {
            key: value.to_json()
            for key, value in self._in_flight_orders.items()
        }

    def restore_tracking_states(self, saved_states: Dict[str, any]):
        """
        *required
        Updates inflight order statuses from API results
        This is used by the MarketsRecorder class to orchestrate market classes at a higher level.
        """
        self._in_flight_orders.update({
            key: BitfinexInFlightOrder.from_json(value)
            for key, value in saved_states.items()
        })

    # list of active orders
    async def list_orders(self) -> List[OrderRetrieved]:
        """
        Gets a list of the user's active orders via rest API
        :returns: json response
        """
        path_url = "auth/r/orders"
        result = await self._api_private("post", path_url=path_url, data={})
        orders = [OrderRetrieved._make(res[:18]) for res in result]
        return orders

    # history list of orders
    async def list_orders_history(self) -> List[OrderRetrieved]:
        """
        Gets a list of the user's active orders via rest API
        :returns: json response
        """
        path_url = "auth/r/orders/hist"
        result = await self._api_private("post", path_url=path_url, data={})
        orders = [OrderRetrieved._make(res[:18]) for res in result]
        return orders

    def calculate_fee(self, price, amount, _type, order_type):
        # fee_percent dependent only from order_type
        fee_percent = self.c_get_fee(None, None, order_type, None, None, None).percent
        if _type == TradeType.BUY:
            fee = price * fee_percent
        else:
            fee = price * Decimal(abs(amount)) * fee_percent
        return fee

    async def _update_order_status(self):
        """
        Pulls the rest API for for latest order statuses and update local order statuses.
        """
        cdef:
            dict order_dict
            double current_timestamp = self._current_timestamp

        if current_timestamp - self._last_order_update_timestamp <= self.UPDATE_ORDERS_INTERVAL:
            return
        tracked_orders = list(self._in_flight_orders.values())
        active_orders = await self.list_orders()
        inactive_orders = await self.list_orders_history()
        all_orders = active_orders + inactive_orders
        order_dict = dict((str(order.id), order) for order in all_orders)

        for tracked_order in tracked_orders:
            client_order_id = tracked_order.client_order_id
            exchange_order_id = tracked_order.exchange_order_id
            order_update = order_dict.get(str(exchange_order_id))

            if order_update is None:
                self._order_not_found_records[client_order_id] = \
                    self._order_not_found_records.get(client_order_id, 0) + 1

                if self._order_not_found_records[client_order_id] < self.ORDER_NOT_EXIST_CONFIRMATION_COUNT:
                    # Wait until the order not found error have repeated for a few times before actually treating
                    # it as a fail. See: https://github.com/CoinAlpha/hummingbot/issues/601
                    continue

                tracked_order.last_state = OrderStatus.CANCELED
                self.c_trigger_event(
                    self.MARKET_ORDER_FAILURE_EVENT_TAG,
                    MarketOrderFailureEvent(self._current_timestamp,
                                            client_order_id,
                                            tracked_order.order_type)
                )
                self.c_stop_tracking_order(client_order_id)
                self.logger().network(
                    f"Error fetching status update for the order {client_order_id}: "
                    f"{tracked_order}",
                    app_warning_msg=f"Could not fetch updates for the order {client_order_id}. "
                                    f"Check API key and network connection."
                )
                continue

            # Calculate the newly executed amount for this update.
            original_amount = Decimal(abs(order_update.amount_orig))
            rest_amount = Decimal(abs(order_update.amount))
            base_execute_amount_diff = original_amount - rest_amount
            base_execute_price = Decimal(order_update.price_exec)

            client_order_id = tracked_order.client_order_id
            order_type_description = tracked_order.order_type_description
            order_type = OrderType.MARKET if tracked_order.order_type == OrderType.MARKET else OrderType.LIMIT

            # Emit event if executed amount is greater than 0.
            if base_execute_amount_diff > s_decimal_0:
                order_filled_event = OrderFilledEvent(
                    self._current_timestamp,
                    tracked_order.client_order_id,
                    tracked_order.trading_pair,
                    tracked_order.trade_type,
                    order_type,
                    base_execute_price,
                    base_execute_amount_diff,
                    self.c_get_fee(
                        tracked_order.base_asset,
                        tracked_order.quote_asset,
                        order_type,
                        tracked_order.trade_type,
                        base_execute_amount_diff,
                        base_execute_price,
                    ),
                    exchange_trade_id=exchange_order_id,
                )
                self.logger().info(f"Filled {base_execute_amount_diff} out of {tracked_order.amount} of the "
                                   f"{order_type_description} order {client_order_id}.")
                self.c_trigger_event(self.MARKET_ORDER_FILLED_EVENT_TAG, order_filled_event)

            # Update the tracked order
            tracked_order.set_status(order_update.status)
            tracked_order.executed_amount_base = base_execute_amount_diff
            tracked_order.executed_amount_quote = base_execute_amount_diff * base_execute_price
            tracked_order.fee_paid = self.calculate_fee(base_execute_amount_diff,
                                                        order_update.price_exec,
                                                        tracked_order.trade_type,
                                                        tracked_order.order_type
                                                        )
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
                                                                    tracked_order.executed_amount_base,
                                                                    tracked_order.executed_amount_quote,
                                                                    tracked_order.fee_paid,
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
                                                                     tracked_order.executed_amount_base,
                                                                     tracked_order.executed_amount_quote,
                                                                     tracked_order.fee_paid,
                                                                     order_type))
                else:
                    self.logger().info(f"The market order {tracked_order.client_order_id} has failed/been cancelled "
                                       f"according to order status API.")
                    self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                         OrderCancelledEvent(
                                             self._current_timestamp,
                                             tracked_order.client_order_id
                                         ))

                self.c_stop_tracking_order(tracked_order.client_order_id)
        self._last_order_update_timestamp = current_timestamp

    def get_price(self, trading_pair: str, is_buy: bool) -> Decimal:
        return self.c_get_price(trading_pair, is_buy)

    def buy(self, trading_pair: str, amount: Decimal, order_type=OrderType.MARKET,
            price: Decimal = s_decimal_nan, **kwargs) -> str:
        return self.c_buy(trading_pair, amount, order_type, price, kwargs)

    def sell(self, trading_pair: str, amount: Decimal, order_type=OrderType.MARKET,
             price: Decimal = s_decimal_nan, **kwargs) -> str:
        return self.c_sell(trading_pair, amount, order_type, price, kwargs)

    def cancel(self, trading_pair: str, client_order_id: str):
        return self.c_cancel(trading_pair, client_order_id)

    def get_fee(self,
                base_currency: str,
                quote_currency: str,
                order_type: OrderType,
                order_side: TradeType,
                amount: Decimal,
                price: Decimal = s_decimal_nan,
                is_maker: Optional[bool] = None) -> AddedToCostTradeFee:
        return self.c_get_fee(base_currency, quote_currency, order_type, order_side, amount, price, is_maker)

    def get_order_book(self, trading_pair: str) -> OrderBook:
        return self.c_get_order_book(trading_pair)
