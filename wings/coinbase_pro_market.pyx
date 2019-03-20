import math
import json
import aiohttp
from aiokafka import (
    AIOKafkaConsumer,
    ConsumerRecord
)
import asyncio
from async_timeout import timeout
import hmac, hashlib, base64, requests
from requests.auth import AuthBase
from decimal import (
    Decimal
)
from functools import partial
import logging
import re
import time
from typing import (
    Dict,
    List,
    AsyncIterable,
    Optional,
    Coroutine
)
from web3 import Web3

import wings
from wings.clock cimport Clock
from wings.events import (
    MarketEvent,
    MarketReceivedAssetEvent,
    MarketWithdrawAssetEvent,
    BuyOrderCompletedEvent,
    SellOrderCompletedEvent,
    OrderFilledEvent,
    OrderCancelledEvent,
    BuyOrderCreatedEvent,
    SellOrderCreatedEvent,
    MarketTransactionFailureEvent)
from wings.market_base import (
    MarketBase,
    OrderType,
)
from wings.order_book_tracker import (
    OrderBookTrackerDataSourceType
)
from wings.order_book cimport OrderBook
# from wings.tracker.coinbase_pro_order_book_tracker import CoinbaseProOrderBookTracker
from wings.cancellation_result import CancellationResult
from .transaction_tracker import TransactionTracker
from .wallet_base import WalletBase
from .wallet_base cimport WalletBase

s_logger = None
s_decimal_0 = Decimal(0)


class CoinbaseProAuth:
    def __init__(self, api_key, secret_key, passphrase):
        self.api_key = api_key
        self.secret_key = secret_key
        self.passphrase = passphrase

    def get_headers(self, method: str = "GET", path_url: str = "/accounts", body: str = "") -> Dict[str, str]:
        timestamp = str(time.time())
        message = timestamp + method.upper() + path_url + body
        hmac_key = base64.b64decode(self.secret_key)
        signature = hmac.new(hmac_key, message.encode('utf8'), hashlib.sha256)
        signature_b64 = base64.b64encode(bytes(signature.digest())).decode('utf8')

        return {
            'CB-ACCESS-SIGN': signature_b64,
            'CB-ACCESS-TIMESTAMP': timestamp,
            'CB-ACCESS-KEY': self.api_key,
            'CB-ACCESS-PASSPHRASE': self.passphrase,
            'Content-Type': 'application/json'
        }


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


cdef class InFlightOrder:
    cdef:
        public str client_order_id
        public int64_t exchange_order_id
        public str symbol
        public bint is_buy
        public object amount
        public object executed_amount
        public object quote_asset_amount
        public str fee_asset
        public object fee_paid
        public str last_state

    def __init__(self, client_order_id: str, exchange_order_id: int, symbol: str, is_buy: bool, amount: Decimal):
        global s_decimal_0

        self.client_order_id = client_order_id
        self.exchange_order_id = exchange_order_id
        self.symbol = symbol
        self.is_buy = is_buy
        self.amount = amount
        self.executed_amount = s_decimal_0
        self.quote_asset_amount = s_decimal_0
        self.fee_asset = None
        self.fee_paid = s_decimal_0
        self.last_state = 'NEW'

    def __repr__(self) -> str:
        return f"InFlightOrder(client_order_id='{self.client_order_id}', exchange_order_id={self.exchange_order_id}, " \
               f"symbol='{self.symbol}', is_buy={self.is_buy}, amount={self.amount}, " \
               f"executed_amount={self.executed_amount}, quote_asset_amount={self.quote_asset_amount}, " \
               f"fee_asset='{self.fee_asset}', fee_paid={self.fee_paid}, last_state='{self.last_state}')"

    def update_with_execution_report(self, execution_report: Dict[str, any]):
        last_executed_quantity = Decimal(execution_report["l"])
        last_commission_amount = Decimal(execution_report["n"])
        last_commission_asset = execution_report["N"]
        last_order_state = execution_report["X"]
        last_executed_price = Decimal(execution_report["L"])
        quote_asset_amount = last_executed_price * last_executed_quantity
        self.executed_amount += last_executed_quantity
        self.quote_asset_amount += quote_asset_amount
        if last_commission_asset is not None:
            self.fee_asset = last_commission_asset
        self.fee_paid += last_commission_amount
        self.last_state = last_order_state

    @property
    def is_done(self) -> bool:
        return self.last_state in {"FILLED", "CANCELED", "PENDING_CANCEL", "REJECTED", "EXPIRED"}

    @property
    def is_failure(self) -> bool:
        return self.last_state in {"CANCELED", "PENDING_CANCEL", "REJECTED", "EXPIRED"}

    @property
    def base_asset(self) -> str:
        return self.symbol.split("")[0]

    @property
    def quote_asset(self) -> str:
        return self.symbol.split("")[1]


cdef class TradingRule:
    cdef:
        public str symbol
        public object quote_increment
        public object base_min_size
        public object base_max_size

    @classmethod
    def parse_exchange_info(cls, trading_rules: List[any]) -> List[TradingRule]:
        cdef:
            list retval = []
        for rule in trading_rules:
            try:
                symbol = rule.get("id")
                retval.append(TradingRule(symbol,
                                          Decimal(rule.get("quote_increment")),
                                          Decimal(rule.get("base_min_size")),
                                          Decimal(rule.get("base_max_size"))))
            except Exception:
                CoinbaseProMarket.logger().error(f"Error parsing the symbol rule {rule}. Skipping.", exc_info=True)
        return retval

    def __init__(self, symbol: str, quote_increment: Decimal, base_min_size: Decimal, base_max_size: Decimal):
        self.symbol = symbol
        self.quote_increment = quote_increment
        self.base_min_size = base_min_size
        self.base_max_size = base_max_size

    def __repr__(self) -> str:
        return f"TradingRule(symbol='{self.symbol}', quote_increment={self.quote_increment}, " \
               f"base_min_size={self.base_min_size}, base_max_size={self.base_max_size}"


cdef class CoinbaseProMarket(MarketBase):
    MARKET_RECEIVED_ASSET_EVENT_TAG = MarketEvent.ReceivedAsset.value
    MARKET_BUY_ORDER_COMPLETED_EVENT_TAG = MarketEvent.BuyOrderCompleted.value
    MARKET_SELL_ORDER_COMPLETED_EVENT_TAG = MarketEvent.SellOrderCompleted.value
    MARKET_WITHDRAW_ASSET_EVENT_TAG = MarketEvent.WithdrawAsset.value
    MARKET_ORDER_CANCELLED_EVENT_TAG = MarketEvent.OrderCancelled.value
    MARKET_TRANSACTION_FAILURE_EVENT_TAG = MarketEvent.TransactionFailure.value
    MARKET_ORDER_FILLED_EVENT_TAG = MarketEvent.OrderFilled.value
    MARKET_BUY_ORDER_CREATED_EVENT_TAG = MarketEvent.BuyOrderCreated.value
    MARKET_SELL_ORDER_CREATED_EVENT_TAG = MarketEvent.SellOrderCreated.value

    DEPOSIT_TIMEOUT = 1800.0
    API_CALL_TIMEOUT = 10.0

    # COINBASE_API_ENDPOINT = "https://api.pro.coinbase.com"
    COINBASE_API_ENDPOINT = "https://api-public.sandbox.pro.coinbase.com"

    @classmethod
    def logger(cls) -> logging.Logger:
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(__name__)
        return s_logger

    def __init__(self,
                 web3_url: str,
                 coinbase_pro_api_key,
                 coinbase_pro_secret_key,
                 coinbase_pro_passphrase,
                 poll_interval: float = 5.0,
                 order_book_tracker_data_source_type: OrderBookTrackerDataSourceType =
                    OrderBookTrackerDataSourceType.EXCHANGE_API,
                 symbols: Optional[List[str]] = None):
        super().__init__()
        self._coinbase_client = CoinbaseProAuth(coinbase_pro_api_key, coinbase_pro_secret_key, coinbase_pro_passphrase)
        # self._order_book_tracker = CoinbaseProOrderBookTracker(data_source_type=order_book_tracker_data_source_type,
        #                                                        symbols=symbols)
        self._account_balances = {}
        self._ev_loop = asyncio.get_event_loop()
        self._poll_notifier = asyncio.Event()
        self._last_timestamp = 0
        self._poll_interval = poll_interval
        self._in_flight_deposits = {}
        self._in_flight_orders = {}
        self._tx_tracker = CoinbaseProMarketTransactionTracker(self)
        self._w3 = Web3(Web3.HTTPProvider(web3_url))
        self._withdraw_rules = {}
        self._trading_rules = {}
        self._data_source_type = order_book_tracker_data_source_type
        self._status_polling_task = None
        self._user_stream_tracker_task = None
        self._user_stream_event_listener_task = None
        self._order_tracker_task = None
        self._coro_queue = asyncio.Queue()
        self._coro_scheduler_task = None

    # @property
    # def order_books(self) -> Dict[str, OrderBook]:
    #     return self._order_book_tracker.order_books

    @property
    def coinbase_client(self) -> CoinbaseProAuth:
        return self._coinbase_client

    @property
    def ready(self) -> bool:
        return (
                # len(self._order_book_tracker.order_books) > 0 and
                # len(self._account_balances) > 0 and
                # len(self._withdraw_rules) > 0 and
                len(self._trading_rules) > 0)

    def get_all_balances(self) -> Dict[str, float]:
        return self._account_balances.copy()

    cdef str c_deposit(self, WalletBase from_wallet, str currency, double amount):
        raise NotImplementedError

    cdef str c_withdraw(self, str address, str currency, double amount):
        raise NotImplementedError

    cdef c_start(self, Clock clock, double timestamp):
        self._tx_tracker.c_start(clock, timestamp)
        MarketBase.c_start(self, clock, timestamp)
        # self._order_tracker_task = asyncio.ensure_future(self._order_book_tracker.start())
        self._status_polling_task = asyncio.ensure_future(self._status_polling_loop())
        # self._user_stream_tracker_task = asyncio.ensure_future(self._user_stream_tracker.start())
        # self._user_stream_event_listener_task = asyncio.ensure_future(self._user_stream_event_listener())
        # self._coro_scheduler_task = asyncio.ensure_future(self.coro_scheduler(self._coro_queue))

    cdef c_tick(self, double timestamp):
        cdef:
            int64_t last_tick = <int64_t>(self._last_timestamp / self._poll_interval)
            int64_t current_tick = <int64_t>(timestamp / self._poll_interval)

        self._tx_tracker.c_tick(timestamp)
        MarketBase.c_tick(self, timestamp)
        if current_tick > last_tick:
            if not self._poll_notifier.is_set():
                self._poll_notifier.set()
        self._last_timestamp = timestamp

    async def _api_request(self,
                           http_method: str,
                           url: str,
                           data: Optional[Dict[str, any]] = None,
                           headers: Optional[Dict[str, str]] = None):
        client = aiohttp.ClientSession()
        async with client.request(http_method, url=url, timeout=self.API_CALL_TIMEOUT, data=data,
                                  headers=headers) as response:
            if response.status != 200:
                raise IOError(f"Error fetching data from {url}. HTTP status is {response.status}.")
            data = await response.json()
            await client.close()
            return data

    async def _update_balances(self):
        cdef:
            dict account_info
            list balances
            str asset_name
            set local_asset_names = set(self._account_balances.keys())
            set remote_asset_names = set()
            set asset_names_to_remove

        path_url = "/accounts"
        url = f"{self.COINBASE_API_ENDPOINT}{path_url}"
        headers = self.coinbase_client.get_headers("GET", path_url)
        account_balances = await self._api_request('get', url=url, headers=headers)

        for balance_entry in account_balances:
            asset_name = balance_entry["currency"]
            balance = Decimal(balance_entry["balance"])
            self._account_balances[asset_name] = balance
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_balances[asset_name]

    async def _update_trading_rules(self):
        cdef:
            # The poll interval for withdraw rules is 60 seconds.
            int64_t last_tick = <int64_t>(self._last_timestamp / 60.0)
            int64_t current_tick = <int64_t>(self._current_timestamp / 60.0)
        if current_tick > last_tick or len(self._trading_rules) < 1:
            product_info = await self._api_request('get', url=f"{self.COINBASE_API_ENDPOINT}/products")
            trading_rules_list = TradingRule.parse_exchange_info(product_info)
            self._trading_rules.clear()
            for trading_rule in trading_rules_list:
                self._trading_rules[trading_rule.symbol] = trading_rule

    async def place_order(self, order_id: str, symbol: str, amount: Decimal, is_buy: bool = True, order_type: OrderType,
                          price: float):
        path_url = "/orders"
        url = f"{self.COINBASE_API_ENDPOINT}{path_url}"
        data = {
            "client_oid": order_id,
            "price": price,
            "size": amount,
            "product_id": symbol,
            "side": "buy" if is_buy else "sell",
            "type": "limit" if order_type is OrderType.LIMIT else "market",
        }
        headers = self.coinbase_client.get_headers("GET", path_url, body=json.dumps(data))
        order_result = await self._api_request('post', url=url, data=data, headers=headers)
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
        if decimal_amount < trading_rule.base_min_size:
            raise ValueError(f"Buy order amount {decimal_amount} is lower than the minimum order size "
                             f"{trading_rule.base_min_size}.")

        try:
            self.c_start_tracking_order(order_id, -1, symbol, True, decimal_amount)
            order_result = await self.place_order(order_id, symbol, decimal_amount, True, order_type, price)
            self.c_trigger_event(self.MARKET_BUY_ORDER_CREATED_EVENT_TAG,
                                 BuyOrderCreatedEvent(self._current_timestamp, order_type, symbol, decimal_amount,
                                                      0.0 if price is None else price, order_id))

            exchange_order_id = order_result["id"]
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(f"Created {order_type} buy order {order_id} for {decimal_amount} {symbol}.")
                tracked_order.exchange_order_id = exchange_order_id
        except asyncio.CancelledError:
            raise
        except Exception:
            order_type_str = 'MARKET' if order_type == OrderType.MARKET else 'LIMIT'
            self.logger().error(f"Error submitting buy {order_type_str} order to Coinbase Pro for "
                                f"{decimal_amount} {symbol} {price}.", exc_info=True)
            self.c_trigger_event(self.MARKET_TRANSACTION_FAILURE_EVENT_TAG,
                                 MarketTransactionFailureEvent(self._current_timestamp, order_id))

    cdef str c_buy(self, str symbol, double amount, object order_type = OrderType.MARKET, double price = None,
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
        if decimal_amount < trading_rule.base_min_size:
            raise ValueError(f"Sell order amount {decimal_amount} is lower than the minimum order size "
                             f"{trading_rule.base_min_size}.")

        try:
            self.c_start_tracking_order(order_id, -1, symbol, False, decimal_amount)
            order_result = await self.place_order(order_id, symbol, decimal_amount, False, order_type, price)
            self.c_trigger_event(self.MARKET_SELL_ORDER_CREATED_EVENT_TAG,
                                 SellOrderCreatedEvent(self._current_timestamp, order_type, symbol, decimal_amount,
                                                      0.0 if price is None else price, order_id))

            exchange_order_id = order_result["id"]
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(f"Created {order_type} buy order {order_id} for {decimal_amount} {symbol}.")
                tracked_order.exchange_order_id = exchange_order_id
        except asyncio.CancelledError:
            raise
        except Exception:
            order_type_str = 'MARKET' if order_type == OrderType.MARKET else 'LIMIT'
            self.logger().error(f"Error submitting buy {order_type_str} order to Coinbase Pro for "
                                f"{decimal_amount} {symbol} {price}.", exc_info=True)
            self.c_trigger_event(self.MARKET_TRANSACTION_FAILURE_EVENT_TAG,
                                 MarketTransactionFailureEvent(self._current_timestamp, order_id))

    cdef str c_sell(self, str symbol, double amount, object order_type = OrderType.MARKET, double price = None,
                    dict kwargs = {}):
        cdef:
            int64_t tracking_nonce = <int64_t>(time.time() * 1e6)
            str order_id = str(f"sell-{symbol}-{tracking_nonce}")
        asyncio.ensure_future(self.execute_sell(order_id, symbol, amount, order_type, price))
        return order_id

    async def execute_cancel(self, symbol: str, order_id: str):
        raise NotImplementedError

    cdef c_cancel(self, str symbol, str order_id):
        asyncio.ensure_future(self.execute_cancel(symbol, order_id))
        return order_id

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        raise NotImplementedError

    async def _status_polling_loop(self):
        while True:
            try:
                await asyncio.gather(
                    self._update_balances(),
                    # self._check_failed_eth_tx(),
                    # self._check_deposit_completion(),
                    # self._update_withdraw_rules(),
                    self._update_trading_rules(),
                    # self._update_order_status()
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error while fetching account updates.", exc_info=True)
            finally:
                self._poll_notifier = asyncio.Event()
                await self._poll_notifier.wait()

    cdef double c_get_balance(self, str currency) except? -1:
        return float(self._account_balances.get(currency, 0.0))

    cdef double c_get_price(self, str symbol, bint is_buy) except? -1:
        cdef:
            OrderBook order_book = self.c_get_order_book(symbol)
        return order_book.c_get_price(is_buy)

    cdef OrderBook c_get_order_book(self, str symbol):
        raise NotImplementedError

    cdef c_did_timeout_tx(self, str tracking_id):
        raise NotImplementedError

    cdef c_did_fail_tx(self, str tracking_id):
                raise NotImplementedError

    cdef c_start_tracking_deposit(self, str tracking_id, int64_t start_time_ms, str tx_hash, str from_address,
                                  str to_address):
        raise NotImplementedError

    cdef c_stop_tracking_deposit(self, str tracking_id):
        raise NotImplementedError

    cdef c_start_tracking_order(self, str order_id, int64_t exchange_order_id, str symbol, bint is_buy, object amount):
        self._in_flight_orders[order_id] = InFlightOrder(order_id, exchange_order_id, symbol, is_buy, amount)

    cdef c_stop_tracking_order(self, str order_id):
        if order_id in self._in_flight_orders:
            del self._in_flight_orders[order_id]

    cdef object c_get_order_price_quantum(self, str symbol, double price):
        cdef:
            TradingRule trading_rule = self._trading_rules[symbol]
        return trading_rule.quote_increment

    cdef object c_get_order_size_quantum(self, str symbol, double order_size):
        cdef:
            TradingRule trading_rule = self._trading_rules[symbol]
        return Decimal(0.01)

    cdef object c_quantize_order_amount(self, str symbol, double amount):
        cdef:
            TradingRule trading_rule = self._trading_rules[symbol]

        global s_decimal_0
        quantized_amount = MarketBase.c_quantize_order_amount(self, symbol, amount)

        # Check against base_min_size. If not passing either check, return 0.
        if quantized_amount < trading_rule.base_min_size:
            return s_decimal_0

        # Check against base_max_size. If not passing either check, return 0.
        if quantized_amount > trading_rule.base_max_size:
            return s_decimal_0

        return quantized_amount
