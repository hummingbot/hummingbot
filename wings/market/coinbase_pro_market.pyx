import aiohttp
import asyncio
from async_timeout import timeout
from decimal import Decimal
import json
import logging
import time
from typing import (
    Any,
    Dict,
    List,
    Optional,
    AsyncIterable,
)
from web3 import Web3
from libc.stdint cimport int64_t

from wings.clock cimport Clock
from wings.events import (
    TradeType,
    TradeFee,
    MarketEvent,
    BuyOrderCompletedEvent,
    SellOrderCompletedEvent,
    OrderFilledEvent,
    OrderCancelledEvent,
    BuyOrderCreatedEvent,
    SellOrderCreatedEvent,
    MarketReceivedAssetEvent,
    MarketWithdrawAssetEvent,
    MarketTransactionFailureEvent
)
from wings.market.market_base import (
    MarketBase,
    OrderType,
)
from wings.network_iterator import NetworkStatus
from wings.order_book_tracker import OrderBookTrackerDataSourceType
from wings.order_book cimport OrderBook
from wings.market.coinbase_pro_auth import CoinbaseProAuth
from wings.tracker.coinbase_pro_order_book_tracker import CoinbaseProOrderBookTracker
from wings.tracker.coinbase_pro_user_stream_tracker import CoinbaseProUserStreamTracker
from wings.cancellation_result import CancellationResult
from wings.transaction_tracker import TransactionTracker
from wings.wallet.wallet_base import WalletBase
from wings.wallet.wallet_base cimport WalletBase

s_logger = None
s_decimal_0 = Decimal(0)


cdef class InFlightOrder:
    cdef:
        public str client_order_id
        public str exchange_order_id
        public str symbol
        public bint is_buy
        public object order_type
        public object amount
        public object price
        public object executed_amount
        public object quote_asset_amount
        public str fee_asset
        public object fee_paid
        public str last_state
        public object exchange_order_id_update_event

    def __init__(self,
                 client_order_id: str,
                 exchange_order_id: str,
                 symbol: str,
                 is_buy: bool,
                 order_type: OrderType,
                 amount: Decimal,
                 price: Decimal):
        global s_decimal_0

        self.client_order_id = client_order_id
        self.exchange_order_id = exchange_order_id
        self.symbol = symbol
        self.is_buy = is_buy
        self.order_type = order_type
        self.amount = amount
        self.price = price
        self.executed_amount = s_decimal_0
        self.quote_asset_amount = s_decimal_0
        self.fee_asset = None
        self.fee_paid = s_decimal_0
        self.last_state = "open"
        self.exchange_order_id_update_event = asyncio.Event()

    def __repr__(self) -> str:
        return f"InFlightOrder(client_order_id='{self.client_order_id}', exchange_order_id={self.exchange_order_id}, " \
               f"symbol='{self.symbol}', is_buy={self.is_buy}, order_type={self.order_type_description}, " \
               f"amount={self.amount}, price={self.price}, executed_amount={self.executed_amount}, "\
               f"quote_asset_amount={self.quote_asset_amount}, fee_asset='{self.fee_asset}', "\
               f"fee_paid={self.fee_paid}, last_state='{self.last_state}')"

    @property
    def is_done(self) -> bool:
        return self.last_state in {"filled", "canceled" "done"}

    @property
    def is_failure(self) -> bool:
        # This is the only known canceled state
        return self.last_state == "canceled"

    @property
    def base_asset(self) -> str:
        return self.symbol.split("-")[0]

    @property
    def quote_asset(self) -> str:
        return self.symbol.split("-")[1]

    @property
    def order_type_description(self) -> str:
        order_type = "market" if self.order_type is OrderType.MARKET else "limit"
        side = "buy" if self.is_buy else "sell"
        return f"{order_type} {side}"

    def update_exchange_order_id(self, exchange_id: str):
        self.exchange_order_id = exchange_id
        self.exchange_order_id_update_event.set()

    async def get_exchange_order_id(self):
        if self.exchange_order_id == "":
            await self.exchange_order_id_update_event.wait()
        return self.exchange_order_id


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


cdef class TradingRule:
    cdef:
        public str symbol
        public object quote_increment
        public object base_min_size
        public object base_max_size
        public bint limit_only

    @classmethod
    def parse_exchange_info(cls, trading_rules: List[Any]) -> List[TradingRule]:
        cdef:
            list retval = []
        for rule in trading_rules:
            try:
                symbol = rule.get("id")
                retval.append(TradingRule(symbol,
                                          Decimal(rule.get("quote_increment")),
                                          Decimal(rule.get("base_min_size")),
                                          Decimal(rule.get("base_max_size")),
                                          rule.get("limit_only")))
            except Exception:
                CoinbaseProMarket.logger().error(f"Error parsing the symbol rule {rule}. Skipping.", exc_info=True)
        return retval

    def __init__(self, symbol: str,
                 quote_increment: Decimal,
                 base_min_size: Decimal,
                 base_max_size: Decimal,
                 limit_only: bool):
        self.symbol = symbol
        self.quote_increment = quote_increment
        self.base_min_size = base_min_size
        self.base_max_size = base_max_size
        self.limit_only = limit_only

    def __repr__(self) -> str:
        return f"TradingRule(symbol='{self.symbol}', quote_increment={self.quote_increment}, " \
               f"base_min_size={self.base_min_size}, base_max_size={self.base_max_size}, limit_only={self.limit_only}"


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
    UPDATE_ORDERS_INTERVAL = 10.0

    COINBASE_API_ENDPOINT = "https://api.pro.coinbase.com"

    @classmethod
    def logger(cls) -> logging.Logger:
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(__name__)
        return s_logger

    def __init__(self,
                 web3_url: str,
                 coinbase_pro_api_key: str,
                 coinbase_pro_secret_key: str,
                 coinbase_pro_passphrase: str,
                 poll_interval: float = 5.0,
                 order_book_tracker_data_source_type: OrderBookTrackerDataSourceType =
                    OrderBookTrackerDataSourceType.EXCHANGE_API,
                 symbols: Optional[List[str]] = None):
        super().__init__()
        self._coinbase_auth = CoinbaseProAuth(coinbase_pro_api_key, coinbase_pro_secret_key, coinbase_pro_passphrase)
        self._order_book_tracker = CoinbaseProOrderBookTracker(data_source_type=order_book_tracker_data_source_type,
                                                               symbols=symbols)
        self._user_stream_tracker = CoinbaseProUserStreamTracker(coinbase_pro_auth=self._coinbase_auth,
                                                                 symbols=symbols)
        self._account_balances = {}
        self._ev_loop = asyncio.get_event_loop()
        self._poll_notifier = asyncio.Event()
        self._last_timestamp = 0
        self._last_order_update_timestamp = 0
        self._poll_interval = poll_interval
        self._in_flight_deposits = {}
        self._in_flight_orders = {}
        self._tx_tracker = CoinbaseProMarketTransactionTracker(self)
        self._w3 = Web3(Web3.HTTPProvider(web3_url))
        self._trading_rules = {}
        self._data_source_type = order_book_tracker_data_source_type
        self._status_polling_task = None
        self._order_tracker_task = None
        self._user_stream_tracker_task = None
        self._user_stream_event_listener_task = None
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
    def ready(self) -> bool:
        return (len(self._order_book_tracker.order_books) > 0 and
                len(self._account_balances) > 0 and
                len(self._trading_rules) > 0)

    def get_all_balances(self) -> Dict[str, float]:
        return self._account_balances.copy()

    cdef c_start(self, Clock clock, double timestamp):
        self._tx_tracker.c_start(clock, timestamp)
        MarketBase.c_start(self, clock, timestamp)

    async def start_network(self):
        if self._order_tracker_task is not None:
            self._stop_network()

        self._order_tracker_task = asyncio.ensure_future(self._order_book_tracker.start())
        self._status_polling_task = asyncio.ensure_future(self._status_polling_loop())
        self._user_stream_tracker_task = asyncio.ensure_future(self._user_stream_tracker.start())
        self._user_stream_event_listener_task = asyncio.ensure_future(self._user_stream_event_listener())

    def _stop_network(self):
        if self._order_tracker_task is not None:
            self._order_tracker_task.cancel()
            self._status_polling_task.cancel()
            self._user_stream_tracker_task.cancel()
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
                          str symbol,
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
            balance = Decimal(balance_entry["balance"])
            self._account_balances[asset_name] = balance
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_balances[asset_name]

    async def _update_eth_tx_status(self):
        in_flight_deposits = [d for d in self._in_flight_deposits.values() if not d.has_tx_receipt]
        tx_hash_to_deposit_map = dict((d.tx_hash, d) for d in in_flight_deposits)

        for d in in_flight_deposits:
            receipt = self._w3.eth.getTransactionReceipt(d.tx_hash)
            if receipt is None or receipt.blockHash is None:
                continue
            if receipt.status == 0:
                d.has_tx_receipt = True
                self.c_did_fail_tx(d.tracking_id)
            if receipt.status == 1:
                self.logger().info(f"Received {d.amount} {d.currency} from {d.from_address} via tx hash {d.tx_hash}.")
                self.c_trigger_event(self.MARKET_RECEIVED_ASSET_EVENT_TAG,
                                     MarketReceivedAssetEvent(
                                         self._current_timestamp,
                                         d.tracking_id,
                                         d.from_address,
                                         d.to_address,
                                         d.currency,
                                         float(d.amount)
                                     ))
                d.has_tx_receipt = True
                self.c_stop_tracking_deposit(d.tracking_id)

    async def _update_trading_rules(self):
        cdef:
            # The poll interval for withdraw rules is 60 seconds.
            int64_t last_tick = <int64_t>(self._last_timestamp / 60.0)
            int64_t current_tick = <int64_t>(self._current_timestamp / 60.0)
        if current_tick > last_tick or len(self._trading_rules) <= 0:
            product_info = await self._api_request("get", path_url="/products")
            trading_rules_list = TradingRule.parse_exchange_info(product_info)
            self._trading_rules.clear()
            for trading_rule in trading_rules_list:
                self._trading_rules[trading_rule.symbol] = trading_rule

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
                self.logger().error(f"Error fetching status update for the order {tracked_order.client_order_id}: "
                                    f"{order_update}.")
                continue

            done_reason = order_update.get("done_reason")
            # Calculate the newly executed amount for this update.
            new_confirmed_amount = float(order_update["filled_size"])
            execute_amount_diff = new_confirmed_amount - float(tracked_order.executed_amount)
            execute_price = 0.0 if new_confirmed_amount == 0 \
                            else float(order_update["executed_value"]) / new_confirmed_amount

            client_order_id = tracked_order.client_order_id
            order_type_description = tracked_order.order_type_description

            # Emit event if executed amount is greater than 0.
            if execute_amount_diff > 0:
                order_filled_event = OrderFilledEvent(
                    self._current_timestamp,
                    tracked_order.client_order_id,
                    tracked_order.symbol,
                    TradeType.BUY if tracked_order.is_buy else TradeType.SELL,
                    OrderType.MARKET if tracked_order.order_type == OrderType.MARKET else OrderType.LIMIT,
                    execute_price,
                    execute_amount_diff
                )
                self.logger().info(f"Filled {execute_amount_diff} out of {tracked_order.amount} of the "
                                   f"{order_type_description} order {client_order_id}.")
                self.c_trigger_event(self.MARKET_ORDER_FILLED_EVENT_TAG, order_filled_event)

            # Update the tracked order
            tracked_order.last_state = done_reason if done_reason in {"filled", "canceled"} else order_update["status"]
            tracked_order.executed_amount = Decimal(new_confirmed_amount)
            tracked_order.quote_asset_amount = Decimal(order_update["executed_value"])
            tracked_order.fee_paid = Decimal(order_update["fill_fees"])
            if tracked_order.is_done:
                if not tracked_order.is_failure:
                    if tracked_order.is_buy:
                        self.logger().info(f"The market buy order {tracked_order.client_order_id} has completed "
                                           f"according to order status API.")
                        self.c_trigger_event(self.MARKET_BUY_ORDER_COMPLETED_EVENT_TAG,
                                             BuyOrderCompletedEvent(self._current_timestamp,
                                                                    tracked_order.client_order_id,
                                                                    tracked_order.base_asset,
                                                                    tracked_order.quote_asset,
                                                                    (tracked_order.fee_asset
                                                                     or tracked_order.base_asset),
                                                                    float(tracked_order.executed_amount),
                                                                    float(tracked_order.quote_asset_amount),
                                                                    float(tracked_order.fee_paid)))
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
                                                                     float(tracked_order.executed_amount),
                                                                     float(tracked_order.quote_asset_amount),
                                                                     float(tracked_order.fee_paid)))
                else:
                    self.logger().info(f"The market order {tracked_order.client_order_id} has failed according to "
                                       f"order status API.")
                    self.c_trigger_event(self.MARKET_TRANSACTION_FAILURE_EVENT_TAG,
                                         MarketTransactionFailureEvent(
                                             self._current_timestamp,
                                             tracked_order.client_order_id
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
                execute_price = float(content.get("price")) if content.get("price") is not None else 0.0
                execute_amount_diff = 0.0

                if event_type == "open":
                    remaining_size = float(content.get("remaining_size"))
                    new_confirmed_amount = float(tracked_order.amount) - remaining_size
                    execute_amount_diff = new_confirmed_amount - float(tracked_order.executed_amount)
                    tracked_order.executed_amount = Decimal(new_confirmed_amount)
                    tracked_order.quote_asset_amount = tracked_order.quote_asset_amount + \
                                                       Decimal(execute_amount_diff * execute_price)
                elif event_type == "done":
                    remaining_size = float(content.get("remaining_size"))
                    reason = content.get("reason")
                    if reason == "filled":
                        new_confirmed_amount = float(tracked_order.amount) - remaining_size
                        execute_amount_diff = new_confirmed_amount - float(tracked_order.executed_amount)
                        tracked_order.executed_amount = Decimal(new_confirmed_amount)
                        tracked_order.quote_asset_amount = tracked_order.quote_asset_amount + \
                                                       Decimal(execute_amount_diff * execute_price)
                        tracked_order.last_state = "done"

                        if tracked_order.is_buy:
                            self.logger().info(f"The market buy order {tracked_order.client_order_id} has completed "
                                               f"according to Coinbase Pro user stream.")
                            self.c_trigger_event(self.MARKET_BUY_ORDER_COMPLETED_EVENT_TAG,
                                                 BuyOrderCompletedEvent(self._current_timestamp,
                                                                        tracked_order.client_order_id,
                                                                        tracked_order.base_asset,
                                                                        tracked_order.quote_asset,
                                                                        (tracked_order.fee_asset
                                                                         or tracked_order.base_asset),
                                                                        float(tracked_order.executed_amount),
                                                                        float(tracked_order.quote_asset_amount),
                                                                        float(tracked_order.fee_paid)))
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
                                                                         float(tracked_order.executed_amount),
                                                                         float(tracked_order.quote_asset_amount),
                                                                         float(tracked_order.fee_paid)))
                    else: # reason == "canceled":
                        execute_amount_diff = 0
                        tracked_order.last_state = "canceled"
                        self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                            OrderCancelledEvent(self._current_timestamp, tracked_order.client_order_id))
                        execute_amount_diff = 0
                    self.c_stop_tracking_order(tracked_order.client_order_id)
                elif event_type == "match":
                    execute_amount_diff = float(content.get("size"))
                    tracked_order.executed_amount += Decimal(execute_amount_diff)
                    tracked_order.quote_asset_amount = tracked_order.quote_asset_amount + \
                                                       Decimal(execute_amount_diff * execute_price)
                elif event_type == "change":
                    if content.get("new_size") is not None:
                        tracked_order.amount = Decimal(content.get("new_size"))
                    elif content.get("new_funds") is not None:
                        if tracked_order.price is not s_decimal_0:
                            tracked_order.amount = Decimal(content.get("new_funds")) / tracked_order.price
                    else:
                        self.logger().error(f"Invalid change message - '{content}'. Aborting.")

                # Emit event if executed amount is greater than 0.
                if execute_amount_diff > 0:
                    order_filled_event = OrderFilledEvent(
                        self._current_timestamp,
                        tracked_order.client_order_id,
                        tracked_order.symbol,
                        TradeType.BUY if tracked_order.is_buy else TradeType.SELL,
                        OrderType.MARKET if tracked_order.order_type == OrderType.MARKET else OrderType.LIMIT,
                        execute_price,
                        execute_amount_diff
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
        if decimal_amount < trading_rule.base_min_size:
            raise ValueError(f"Buy order amount {decimal_amount} is lower than the minimum order size "
                             f"{trading_rule.base_min_size}.")

        try:
            self.c_start_tracking_order(order_id, "", symbol, True, order_type, decimal_amount, decimal_price)
            order_result = await self.place_order(order_id, symbol, decimal_amount, True, order_type, decimal_price)
            self.c_trigger_event(self.MARKET_BUY_ORDER_CREATED_EVENT_TAG,
                                 BuyOrderCreatedEvent(self._current_timestamp, order_type, symbol, decimal_amount,
                                                      price, order_id))

            exchange_order_id = order_result["id"]
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(f"Created {order_type} buy order {order_id} for {decimal_amount} {symbol}.")
                tracked_order.update_exchange_order_id(exchange_order_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            self.c_stop_tracking_order(order_id)
            order_type_str = "MARKET" if order_type == OrderType.MARKET else "LIMIT"
            self.logger().error(f"Error submitting buy {order_type_str} order to Coinbase Pro for "
                                f"{decimal_amount} {symbol} {price}.", exc_info=True)
            self.c_trigger_event(self.MARKET_TRANSACTION_FAILURE_EVENT_TAG,
                                 MarketTransactionFailureEvent(self._current_timestamp, order_id))

    cdef str c_buy(self, str symbol, double amount, object order_type = OrderType.MARKET, double price = 0.0,
                   dict kwargs = {}):
        cdef:
            int64_t tracking_nonce = <int64_t>(time.time() * 1e6)
            str order_id = str(f"buy-{symbol}-{tracking_nonce}")
            object buy_fee
            double adjusted_amount

        # Coinbase Pro charges additional fees for buy limit orders
        # limit buy 10 XLM for 1 USDC and the fee is 2%, balance requires 1.02 USDC
        adjusted_amount = amount
        if order_type is OrderType.LIMIT:
            buy_fee = self.c_get_fee(symbol, order_type, TradeType.BUY, amount, price)
            adjusted_amount = amount / (1 + buy_fee.percent)

        asyncio.ensure_future(self.execute_buy(order_id, symbol, adjusted_amount, order_type, price))
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
        if decimal_amount < trading_rule.base_min_size:
            raise ValueError(f"Sell order amount {decimal_amount} is lower than the minimum order size "
                             f"{trading_rule.base_min_size}.")

        try:
            self.c_start_tracking_order(order_id, "", symbol, False, order_type, decimal_amount, decimal_price)
            order_result = await self.place_order(order_id, symbol, decimal_amount, False, order_type, decimal_price)
            self.c_trigger_event(self.MARKET_SELL_ORDER_CREATED_EVENT_TAG,
                                 SellOrderCreatedEvent(self._current_timestamp, order_type, symbol, decimal_amount,
                                                       price, order_id))

            exchange_order_id = order_result["id"]
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(f"Created {order_type} sell order {order_id} for {decimal_amount} {symbol}.")
                tracked_order.update_exchange_order_id(exchange_order_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            self.c_stop_tracking_order(order_id)
            order_type_str = "MARKET" if order_type == OrderType.MARKET else "LIMIT"
            self.logger().error(f"Error submitting sell {order_type_str} order to Coinbase Pro for "
                                f"{decimal_amount} {symbol} {price}.", exc_info=True)
            self.c_trigger_event(self.MARKET_TRANSACTION_FAILURE_EVENT_TAG,
                                 MarketTransactionFailureEvent(self._current_timestamp, order_id))

    cdef str c_sell(self, str symbol, double amount, object order_type = OrderType.MARKET, double price = 0.0,
                    dict kwargs = {}):
        cdef:
            int64_t tracking_nonce = <int64_t>(time.time() * 1e6)
            str order_id = str(f"sell-{symbol}-{tracking_nonce}")
        asyncio.ensure_future(self.execute_sell(order_id, symbol, amount, order_type, price))
        return order_id

    async def execute_cancel(self, symbol: str, order_id: str):
        exchange_order_id = await self._in_flight_orders.get(order_id).get_exchange_order_id()
        path_url = f"/orders/{exchange_order_id}"
        try:
            [cancelled_id] = await self._api_request("delete", path_url=path_url)
            if cancelled_id == exchange_order_id:
                self.logger().info(f"Successfully cancelled order {order_id}.")
                self.c_stop_tracking_order(order_id)
                self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                     OrderCancelledEvent(self._current_timestamp, order_id))
        except Exception as e:
            self.logger().error(f"Failed to cancel order {order_id}: {str(e)}")
        return order_id

    cdef c_cancel(self, str symbol, str order_id):
        asyncio.ensure_future(self.execute_cancel(symbol, order_id))
        return order_id

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        incomplete_orders = [o for o in self._in_flight_orders.values() if not o.is_done]
        successful_cancellations = []

        try:
            path_url = "/orders"
            async with timeout(timeout_seconds):
                results = await self._api_request("delete", path_url=path_url)

            exchange_order_id_map = dict(zip([o.exchange_order_id for o in incomplete_orders], incomplete_orders))
            for exchange_order_id in results:
                order = exchange_order_id_map.get(exchange_order_id)
                if order is not None:
                    exchange_order_id_map.pop(exchange_order_id, None)
                    successful_cancellations.append(CancellationResult(order.client_order_id, True))
        except Exception:
            self.logger().error(f"Unexpected error cancelling orders.", exc_info=True)

        failed_cancellations = [CancellationResult(order.client_order_id, False)
                                for order in list(exchange_order_id_map.values())]
        return successful_cancellations + failed_cancellations

    async def _status_polling_loop(self):
        while True:
            try:
                self._poll_notifier = asyncio.Event()
                await self._poll_notifier.wait()

                await asyncio.gather(
                    self._update_balances(),
                    self._update_trading_rules(),
                    self._update_order_status(),
                    self._update_eth_tx_status(),
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error while fetching account updates.", exc_info=True)

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

    async def get_deposit_address(self, currency: str) -> str:
        coinbase_account_id_dict = await self.list_coinbase_accounts()
        account_id = coinbase_account_id_dict.get(currency)
        path_url = f"/coinbase-accounts/{account_id}/addresses"
        deposit_result = await self._api_request("post", path_url=path_url)
        return deposit_result.get("address")

    async def execute_deposit(self, tracking_id: str, from_wallet: WalletBase, currency: str, amount: float):
        cdef:
            dict deposit_reply
            str deposit_address
            str tx_hash

        # First, get the deposit address from Coinbase Pro.
        try:
            to_address = await self.get_deposit_address(currency)
        except Exception as e:
            self.logger().error(f"Error fetching deposit address for {currency}. {e}", exc_info=True)
            self.c_trigger_event(self.MARKET_TRANSACTION_FAILURE_EVENT_TAG,
                                 MarketTransactionFailureEvent(self._current_timestamp, tracking_id))
            return

        # Then, send the transaction from the wallet, and remember the in flight transaction.
        tx_hash = from_wallet.send(to_address, currency, amount)
        self.c_start_tracking_deposit(tracking_id, tx_hash, from_wallet.address, to_address, amount, currency)

    cdef str c_deposit(self, WalletBase from_wallet, str currency, double amount):
        cdef:
            int64_t tracking_nonce = <int64_t>(time.time() * 1e6)
            str tracking_id = str(f"deposit://{currency}/{tracking_nonce}")
        asyncio.ensure_future(self.execute_deposit(tracking_id, from_wallet, currency, amount))
        self._tx_tracker.c_start_tx_tracking(tracking_id, self.DEPOSIT_TIMEOUT)
        return tracking_id

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
            self.logger().error(f"Error sending withdraw request to Coinbase Pro for {currency}.", exc_info=True)
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
                                str order_id,
                                str exchange_order_id,
                                str symbol,
                                bint is_buy,
                                object order_type,
                                object amount,
                                object price):
        self._in_flight_orders[order_id] = InFlightOrder(order_id, exchange_order_id, symbol, is_buy, order_type,
                                                         amount, price)
    cdef c_stop_tracking_order(self, str order_id):
        if order_id in self._in_flight_orders:
            del self._in_flight_orders[order_id]

    cdef c_start_tracking_deposit(self,
                                  str tracking_id,
                                  str tx_hash,
                                  str from_address,
                                  str to_address,
                                  object amount,
                                  str currency):
        self._in_flight_deposits[tracking_id] = InFlightDeposit(tracking_id, tx_hash, from_address, to_address, amount, currency)

    cdef c_stop_tracking_deposit(self, str tracking_id):
        self._tx_tracker.c_stop_tx_tracking(tracking_id)
        if tracking_id in self._in_flight_deposits:
            del self._in_flight_deposits[tracking_id]

    cdef c_did_timeout_tx(self, str tracking_id):
        if tracking_id in self._in_flight_deposits:
            self.c_stop_tracking_deposit(tracking_id)
        self.c_trigger_event(self.MARKET_TRANSACTION_FAILURE_EVENT_TAG,
                             MarketTransactionFailureEvent(self._current_timestamp, tracking_id))

    cdef c_did_fail_tx(self, str tracking_id):
        if tracking_id in self._in_flight_deposits:
            self.c_stop_tracking_deposit(tracking_id)
        self.c_trigger_event(self.MARKET_TRANSACTION_FAILURE_EVENT_TAG,
                             MarketTransactionFailureEvent(self._current_timestamp, tracking_id))

    cdef object c_get_order_price_quantum(self, str symbol, double price):
        cdef:
            TradingRule trading_rule = self._trading_rules[symbol]
        return trading_rule.quote_increment

    cdef object c_get_order_size_quantum(self, str symbol, double order_size):
        cdef:
            TradingRule trading_rule = self._trading_rules[symbol]

        # Coinbase Pro is using the base_min_size as max_precision
        # Order size must be a multiple of the base_min_size
        return trading_rule.base_min_size

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
