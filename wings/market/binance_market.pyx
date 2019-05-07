import math
import aiohttp
from aiokafka import (
    AIOKafkaConsumer,
    ConsumerRecord
)
import asyncio
from async_timeout import timeout
from binance.client import Client as BinanceClient
from binance import client as binance_client_module
from binance.exceptions import BinanceAPIException
from decimal import (
    Decimal
)
from functools import partial
import logging
import pandas as pd
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
import conf
import wings
from wings.async_call_scheduler import AsyncCallScheduler
from wings.clock cimport Clock
from wings.data_source.binance_api_order_book_data_source import BinanceAPIOrderBookDataSource
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
    MarketTransactionFailureEvent,
    OrderType,
    TradeType,
    TradeFee
)
from wings.market.market_base import (
    MarketBase,
    NaN
)
from wings.network_iterator import NetworkStatus
from wings.order_book_tracker import (
    OrderBookTrackerDataSourceType
)
from wings.order_book cimport OrderBook
from wings.tracker.binance_order_book_tracker import BinanceOrderBookTracker
from wings.tracker.binance_user_stream_tracker import BinanceUserStreamTracker
from wings.user_stream_tracker import UserStreamTrackerDataSourceType
from wings.cancellation_result import CancellationResult
from wings.transaction_tracker import TransactionTracker
from wings.wallet.wallet_base import WalletBase
from wings.wallet.wallet_base cimport WalletBase
from collections import deque
import statistics

s_logger = None
s_decimal_0 = Decimal(0)


class BinanceTime:
    """
    Used to monkey patch Binance client's time module to adjust request timestamp when needed
    """
    BINANCE_TIME_API = "https://api.binance.com/api/v1/time"
    _bt_logger = None
    _bt_shared_instance = None

    @classmethod
    def logger(cls) -> logging.Logger:
        global _bt_logger
        if _bt_logger is None:
            _bt_logger = logging.getLogger(__name__)
        return _bt_logger

    @classmethod
    def get_instance(cls) -> "BinanceTime":
        if cls._bt_shared_instance is None:
            cls._bt_shared_instance = BinanceTime()
        return cls._bt_shared_instance

    def __init__(self, check_interval: float = 60.0):
        self._time_offset_ms = deque([])
        self._set_server_time_offset_task = None
        self._started = False
        self.SERVER_TIME_OFFSET_CHECK_INTERVAL = check_interval
        self.median_window = 100

    @property
    def started(self):
        return self._started

    @property
    def time_offset_ms(self):
        if not self._time_offset_ms or len(self._time_offset_ms) < 3:
            return 0.0
        return statistics.median(self._time_offset_ms)

    def set_time_offset_ms(self, offset):
        self._time_offset_ms.append(offset)
        if len(self._time_offset_ms) > self.median_window :
            self._time_offset_ms.popleft()

    def time(self):
        return time.time() + self.time_offset_ms * 1e-3

    def start(self):
        if self._set_server_time_offset_task is None:
            self._set_server_time_offset_task = asyncio.ensure_future(self.set_server_time_offset())
            self._started = True

    def stop(self):
        if self._set_server_time_offset_task:
            self._set_server_time_offset_task.cancel()
            self._started = False

    async def set_server_time_offset(self):
        while True:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(self.BINANCE_TIME_API) as resp:
                        time_now_ms = time.time() * 1e3
                        resp_data = await resp.json()
                        binance_server_time = resp_data["serverTime"]
                        time_after_ms = time.time() * 1e3
                expected_server_time = int((time_after_ms + time_now_ms)//2)
                time_offset =  binance_server_time - expected_server_time
                self.set_time_offset_ms(time_offset)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(f"Error getting Binance server time.", exc_info=True)
            finally:
                await asyncio.sleep(self.SERVER_TIME_OFFSET_CHECK_INTERVAL)

cdef class BinanceMarketTransactionTracker(TransactionTracker):
    cdef:
        BinanceMarket _owner

    def __init__(self, owner: BinanceMarket):
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

    SYMBOL_SPLITTER = re.compile(r"^(\w+)(BTC|ETH|BNB|XRP|USDT|USDC|TUSD|PAX)$")

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
        m = self.SYMBOL_SPLITTER.match(self.symbol)
        return m.group(1)

    @property
    def quote_asset(self) -> str:
        m = self.SYMBOL_SPLITTER.match(self.symbol)
        return m.group(2)


cdef class TradingRule:
    cdef:
        public str symbol
        public object price_tick_size
        public object order_step_size
        public object min_order_size
        public object min_notional_size

    @classmethod
    def parse_exchange_info(cls, exchange_info_dict: Dict[str, any]) -> List[TradingRule]:
        cdef:
            list symbol_rules = exchange_info_dict.get("symbols", [])
            list retval = []
        for rule in symbol_rules:
            try:
                symbol = rule.get("symbol")
                filters = rule.get("filters")
                price_filter = [f for f in filters if f.get("filterType") == "PRICE_FILTER"][0]
                lot_size_filter = [f for f in filters if f.get("filterType") == "LOT_SIZE"][0]
                min_notional_filter = [f for f in filters if f.get("filterType") == "MIN_NOTIONAL"][0]
                retval.append(TradingRule(symbol,
                                          Decimal(price_filter.get("tickSize")),
                                          Decimal(lot_size_filter.get("stepSize")),
                                          Decimal(lot_size_filter.get("minQty")),
                                          Decimal(min_notional_filter.get("minNotional"))))
            except Exception:
                BinanceMarket.logger().error(f"Error parsing the symbol rule {rule}. Skipping.", exc_info=True)
        return retval

    def __init__(self, symbol: str, price_tick_size: Decimal, order_step_size: Decimal, min_order_size: Decimal,
                 min_notional_size: Decimal):
        self.symbol = symbol
        self.price_tick_size = price_tick_size
        self.order_step_size = order_step_size
        self.min_order_size = min_order_size
        self.min_notional_size = min_notional_size

    def __repr__(self) -> str:
        return f"TradingRule(symbol='{self.symbol}', price_tick_size={self.price_tick_size}, " \
               f"order_step_size={self.order_step_size}, min_order_size={self.min_order_size}, " \
               f"min_notional_size={self.min_notional_size})"


cdef class BinanceMarket(MarketBase):
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
    BINANCE_TRADE_TOPIC_NAME = "binance-trade.serialized"
    BINANCE_USER_STREAM_TOPIC_NAME = "binance-user-stream.serialized"

    @classmethod
    def logger(cls) -> logging.Logger:
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(__name__)
        return s_logger

    def __init__(self,
                 web3_url: str,
                 binance_api_key: str,
                 binance_api_secret: str,
                 poll_interval: float = 5.0,
                 order_book_tracker_data_source_type: OrderBookTrackerDataSourceType =
                    OrderBookTrackerDataSourceType.EXCHANGE_API,
                 user_stream_tracker_data_source_type: UserStreamTrackerDataSourceType =
                    UserStreamTrackerDataSourceType.EXCHANGE_API,
                 symbols: Optional[List[str]] = None):

        self.monkey_patch_binance_time()
        super().__init__()
        self._order_book_tracker = BinanceOrderBookTracker(data_source_type=order_book_tracker_data_source_type,
                                                           symbols=symbols)
        self._binance_client = BinanceClient(binance_api_key, binance_api_secret)
        self._user_stream_tracker = BinanceUserStreamTracker(
            data_source_type=user_stream_tracker_data_source_type, binance_client=self._binance_client)
        self._account_balances = {}
        self._ev_loop = asyncio.get_event_loop()
        self._poll_notifier = asyncio.Event()
        self._last_timestamp = 0
        self._poll_interval = poll_interval
        self._in_flight_deposits = {}
        self._in_flight_orders = {}
        self._tx_tracker = BinanceMarketTransactionTracker(self)
        self._w3 = Web3(Web3.HTTPProvider(web3_url))
        self._withdraw_rules = {}
        self._trading_rules = {}
        self._trade_fees = {}
        self._last_update_trade_fees_timestamp = 0
        self._data_source_type = order_book_tracker_data_source_type
        self._status_polling_task = None
        self._user_stream_tracker_task = None
        self._user_stream_event_listener_task = None
        self._order_tracker_task = None
        self._async_scheduler = AsyncCallScheduler(call_interval=0.5)

    @property
    def name(self) -> str:
        return "binance"

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        return self._order_book_tracker.order_books

    @property
    def binance_client(self) -> BinanceClient:
        return self._binance_client

    @property
    def withdraw_rules(self) -> Dict[str, WithdrawRule]:
        return self._withdraw_rules

    @property
    def trading_rules(self) -> Dict[str, TradingRule]:
        return self._trading_rules

    @property
    def in_flight_orders(self) -> Dict[str, InFlightOrder]:
        return self._in_flight_orders

    @property
    def in_flight_deposits(self) -> Dict[str, InFlightDeposit]:
        return self._in_flight_deposits

    async def get_active_exchange_markets(self) -> pd.DataFrame:
        return await BinanceAPIOrderBookDataSource.get_active_exchange_markets()

    def monkey_patch_binance_time(self):
        if binance_client_module.time != BinanceTime.get_instance():
            binance_client_module.time = BinanceTime.get_instance()
            BinanceTime.get_instance().start()

    async def schedule_async_call(self, coro: Coroutine, timeout_seconds: float) -> any:
        return await self._async_scheduler.schedule_async_call(coro, timeout_seconds)

    async def query_api(self, func, *args, **kwargs) -> Dict[str, any]:
        async with timeout(self.API_CALL_TIMEOUT):
            coro = self._ev_loop.run_in_executor(wings.get_executor(), partial(func, *args, **kwargs))
            return await self.schedule_async_call(coro, self.API_CALL_TIMEOUT)

    async def query_url(self, url) -> any:
        async with aiohttp.ClientSession() as client:
            async with client.get(url, timeout=self.API_CALL_TIMEOUT) as response:
                if response.status != 200:
                    raise IOError(f"Error fetching data from {url}. HTTP status is {response.status}.")
                data = await response.json()
                return data

    async def _update_balances(self):
        cdef:
            dict account_info
            list balances
            str asset_name
            set local_asset_names = set(self._account_balances.keys())
            set remote_asset_names = set()
            set asset_names_to_remove

        account_info = await self.query_api(self._binance_client.get_account)
        balances = account_info["balances"]
        for balance_entry in balances:
            asset_name = balance_entry["asset"]
            balance = Decimal(balance_entry["free"]) + Decimal(balance_entry["locked"])
            self._account_balances[asset_name] = balance
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_balances[asset_name]

    async def _check_failed_eth_tx(self):
        in_flight_deposits = [d for d in self._in_flight_deposits.values() if not d.has_tx_receipt]
        tasks = [self._ev_loop.run_in_executor(wings.get_executor(),
                                               self._w3.eth.getTransactionReceipt, d.tx_hash)
                 for d in in_flight_deposits]
        receipts = await asyncio.gather(*tasks)
        for d , receipt in zip(in_flight_deposits, receipts):
            if receipt is None or receipt.blockHash is None:
                continue
            if receipt.status == 0:
                self.c_did_fail_tx(d.tracking_id)
            d.has_tx_receipt = True

    async def _update_trade_fees(self):
        cdef:
            double current_timestamp = self._current_timestamp

        if current_timestamp - self._last_update_trade_fees_timestamp > 60.0 * 60.0 or len(self._trade_fees) < 1:
            try:
                res = await self.query_api(self._binance_client.get_trade_fee)
                for fee in res["tradeFee"]:
                    self._trade_fees[fee["symbol"]] = (fee["maker"], fee["taker"])
                self._last_update_trade_fees_timestamp = current_timestamp
            except Exception:
                self.logger().error("Error fetching Binance trade fees.", exc_info=True)
                raise

    cdef object c_get_fee(self,
                          str base_currency,
                          str quote_currency,
                          object order_type,
                          object order_side,
                          double amount,
                          double price):
        cdef:
            double maker_trade_fee = 0.001
            double taker_trade_fee = 0.001
            str symbol = base_currency + quote_currency

        if symbol not in self._trade_fees:
            # https://www.binance.com/en/fee/schedule
            self.logger().warning(f"Unable to find trade fee for {symbol}. Using default 0.1% maker/taker fee.")
        else:
            maker_trade_fee, taker_trade_fee = self._trade_fees.get(symbol)
        return TradeFee(percent=maker_trade_fee if order_type is OrderType.LIMIT else taker_trade_fee)

    async def _check_deposit_completion(self):
        if len(self._in_flight_deposits) < 1:
            return

        # Emit the API call.
        min_timestamp = min(d.timestamp_ms for d in self._in_flight_deposits.values())
        tx_hash_to_deposit_map = dict((d.tx_hash, d) for d in self._in_flight_deposits.values())
        api_reply = await self.query_api(self._binance_client.get_deposit_history, startTime=min_timestamp)

        # Get the deposit list data from the API reply.
        if not isinstance(api_reply, dict) or api_reply["success"] is not True:
            self.logger().error(f"Invalid reply from Binance deposit history API endpoint: {api_reply}")
            return
        deposit_list = api_reply["depositList"]

        # For each record in the deposit list, match it against known in-flight deposits.
        # Emit received asset events.
        for deposit_record in deposit_list:
            if deposit_record["status"] != 1:
                continue
            tx_id = deposit_record.get("txId", "")
            if tx_id in tx_hash_to_deposit_map:
                tracking_record = tx_hash_to_deposit_map[tx_id]
                self.logger().info(f"Received {deposit_record['amount']} {deposit_record['asset']} from "
                                   f"{tracking_record.from_address} via tx id {tx_id}.")
                self.c_trigger_event(self.MARKET_RECEIVED_ASSET_EVENT_TAG,
                                     MarketReceivedAssetEvent(
                                         deposit_record["insertTime"] * 1e-3,
                                         tracking_record.tracking_id,
                                         tracking_record.from_address,
                                         tracking_record.to_address,
                                         deposit_record["asset"],
                                         float(deposit_record["amount"])
                                     ))
                self.c_stop_tracking_deposit(tracking_record.tracking_id)

    async def _update_withdraw_rules(self):
        cdef:
            # The poll interval for withdraw rules is 60 seconds.
            int64_t last_tick = <int64_t>(self._last_timestamp / 60.0)
            int64_t current_tick = <int64_t>(self._current_timestamp / 60.0)
        if current_tick > last_tick or len(self._withdraw_rules) < 1:
            asset_rules = await self.query_url("https://www.binance.com/assetWithdraw/getAllAsset.html")
            for asset_rule in asset_rules:
                asset_name = asset_rule["assetCode"]
                min_withdraw_amount = float(asset_rule["minProductWithdraw"])
                withdraw_fee = float(asset_rule["transactionFee"])
                if asset_name not in self._withdraw_rules:
                    self._withdraw_rules[asset_name] = WithdrawRule(asset_name, min_withdraw_amount, withdraw_fee)
                else:
                    existing_rule = self._withdraw_rules[asset_name]
                    existing_rule.min_withdraw_amount = min_withdraw_amount
                    existing_rule.withdraw_fee = withdraw_fee

    async def _update_trading_rules(self):
        cdef:
            # The poll interval for withdraw rules is 60 seconds.
            int64_t last_tick = <int64_t>(self._last_timestamp / 60.0)
            int64_t current_tick = <int64_t>(self._current_timestamp / 60.0)
        if current_tick > last_tick or len(self._trading_rules) < 1:
            exchange_info = await self.query_api(self._binance_client.get_exchange_info)
            trading_rules_list = TradingRule.parse_exchange_info(exchange_info)
            self._trading_rules.clear()
            for trading_rule in trading_rules_list:
                self._trading_rules[trading_rule.symbol] = trading_rule

    async def _update_order_status(self):
        cdef:
            # This is intended to be a backup measure to close straggler orders, in case Binance's user stream events
            # are not working.
            # The poll interval for order status is 10 seconds.
            int64_t last_tick = <int64_t>(self._last_timestamp / 10.0)
            int64_t current_tick = <int64_t>(self._current_timestamp / 10.0)

        if current_tick > last_tick and len(self._in_flight_orders) > 0:
            tracked_orders = list(self._in_flight_orders.values())
            tasks = [self.query_api(self._binance_client.get_order, origClientOrderId=o.client_order_id)
                     for o in tracked_orders]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for order_update, tracked_order in zip(results, tracked_orders):
                if isinstance(order_update, Exception):
                    self.logger().error(f"Error fetching status update for the order {tracked_order.client_order_id}: "
                                        f"{order_update}.")
                    continue
                tracked_order.last_state = order_update["status"]
                client_order_id = tracked_order.client_order_id

                if tracked_order.last_state in ["FILLED", "PARTIALLY_FILLED"]:
                    self.c_trigger_event(self.MARKET_ORDER_FILLED_EVENT_TAG,
                                         OrderFilledEvent(
                                            self._current_timestamp,
                                            tracked_order.client_order_id,
                                            tracked_orders.symbol,
                                            TradeType.BUY if tracked_order.is_buy else TradeType.SELL,
                                            OrderType.LIMIT if order_update["type"]=="LIMIT" else OrderType.MARKET,
                                            float(order_update["price"]),
                                            float(order_update["executedQty"])
                                         ))
                if tracked_order.is_done:
                    if not tracked_order.is_failure:
                        if tracked_order.is_buy:
                            self.logger().info(f"The market buy order {client_order_id} has completed "
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
                            self.logger().info(f"The market sell order {client_order_id} has completed "
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
                        self.logger().info(f"The market order {client_order_id} has failed according to "
                                           f"order status API.")
                        self.c_trigger_event(self.MARKET_TRANSACTION_FAILURE_EVENT_TAG,
                                             MarketTransactionFailureEvent(
                                                 self._current_timestamp,
                                                 tracked_order.client_order_id
                                             ))
                    self.c_stop_tracking_order(tracked_order.client_order_id)

    async def _iter_kafka_messages(self, topic: str) -> AsyncIterable[ConsumerRecord]:
        while True:
            try:
                consumer = AIOKafkaConsumer(topic, loop=self._ev_loop, bootstrap_servers=conf.kafka_bootstrap_server)
                await consumer.start()
                partition = list(consumer.assignment())[0]
                await consumer.seek_to_end(partition)

                while True:
                    response = await consumer.getmany(partition, timeout_ms=1000)
                    if partition in response:
                        for record in response[partition]:
                            yield record
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unknown error. Retrying after 5 seconds.", exc_info=True)
                await asyncio.sleep(5.0)

    async def _iter_user_event_queue(self) -> AsyncIterable[Dict[str, any]]:
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
                event_type = event_message.get("e")
                if event_type != "executionReport":
                    continue
                client_order_id = event_message.get("c")
                tracked_order = self._in_flight_orders.get(client_order_id)
                if tracked_order is None:
                    self.logger().warning(f"Unrecognized order ID from user stream: {client_order_id}. Skipping.")
                    continue
                tracked_order.update_with_execution_report(event_message)
                execution_type = event_message.get("x")
                if execution_type == "TRADE":
                    self.c_trigger_event(self.MARKET_ORDER_FILLED_EVENT_TAG,
                                         OrderFilledEvent.order_filled_event_from_binance_execution_report(
                                             event_message))

                if tracked_order.is_done:
                    if not tracked_order.is_failure:
                        if tracked_order.is_buy:
                            self.logger().info(f"The market buy order {client_order_id} has completed "
                                               f"according to user stream.")
                            self.c_trigger_event(self.MARKET_BUY_ORDER_COMPLETED_EVENT_TAG,
                                                 BuyOrderCompletedEvent(self._current_timestamp,
                                                                        client_order_id,
                                                                        tracked_order.base_asset,
                                                                        tracked_order.quote_asset,
                                                                        (tracked_order.fee_asset
                                                                         or tracked_order.base_asset),
                                                                        float(tracked_order.executed_amount),
                                                                        float(tracked_order.quote_asset_amount),
                                                                        float(tracked_order.fee_paid)))
                        else:
                            self.logger().info(f"The market sell order {client_order_id} has completed "
                                               f"according to user stream.")
                            self.c_trigger_event(self.MARKET_SELL_ORDER_COMPLETED_EVENT_TAG,
                                                 SellOrderCompletedEvent(self._current_timestamp,
                                                                         client_order_id,
                                                                         tracked_order.base_asset,
                                                                         tracked_order.quote_asset,
                                                                         (tracked_order.fee_asset
                                                                          or tracked_order.quote_asset),
                                                                         float(tracked_order.executed_amount),
                                                                         float(tracked_order.quote_asset_amount),
                                                                         float(tracked_order.fee_paid)))
                    else:
                        self.logger().info(f"The market order {client_order_id} has failed according to user stream.")
                        self.c_trigger_event(self.MARKET_TRANSACTION_FAILURE_EVENT_TAG,
                                             MarketTransactionFailureEvent(
                                                 self._current_timestamp,
                                                 tracked_order.client_order_id
                                             ))
                    self.c_stop_tracking_order(client_order_id)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await asyncio.sleep(5.0)

    async def _status_polling_loop(self):
        while True:
            try:
                self._poll_notifier = asyncio.Event()
                await self._poll_notifier.wait()

                await asyncio.gather(
                    self._update_balances(),
                    self._check_failed_eth_tx(),
                    self._check_deposit_completion(),
                    self._update_withdraw_rules(),
                    self._update_trading_rules(),
                    self._update_order_status(),
                    self._update_trade_fees()
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error while fetching account updates.", exc_info=True)
                await asyncio.sleep(0.5)

    @property
    def ready(self) -> bool:
        return (len(self._order_book_tracker.order_books) > 0 and
                len(self._account_balances) > 0 and
                len(self._withdraw_rules) > 0 and
                len(self._trading_rules) > 0 and
                len(self._trade_fees) > 0)

    async def server_time(self) -> int:
        """
        :return: The current server time in milliseconds since UNIX epoch.
        """
        result = await self.query_api(self._binance_client.get_server_time)
        return result["serverTime"]

    def get_all_balances(self) -> Dict[str, float]:
        return self._account_balances.copy()

    async def execute_deposit(self, tracking_id: str, from_wallet: WalletBase, currency: str, amount: float):
        cdef:
            dict deposit_reply
            str deposit_address
            str tx_hash

        # First, get the deposit address from Binance.
        try:
            deposit_reply, server_time_ms = await asyncio.gather(
                self.query_api(self._binance_client.get_deposit_address, asset=currency),
                self.server_time()
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(f"Error fetching deposit address and server time for depositing {currency}.",
                                exc_info=True)
            self.c_trigger_event(self.MARKET_TRANSACTION_FAILURE_EVENT_TAG,
                                 MarketTransactionFailureEvent(self._current_timestamp, tracking_id))
            return

        if deposit_reply.get("success") is not True:
            self.logger().error(f"Could not get deposit address for {currency}: {deposit_reply}")
            self.c_trigger_event(self.MARKET_TRANSACTION_FAILURE_EVENT_TAG,
                                 MarketTransactionFailureEvent(self._current_timestamp, tracking_id))
            return

        deposit_address = Web3.toChecksumAddress(deposit_reply["address"])

        # Then, send the transaction from the wallet, and remember the in flight transaction.
        tx_hash = from_wallet.send(deposit_address, currency, amount)
        self.c_start_tracking_deposit(tracking_id, server_time_ms, tx_hash, from_wallet.address, deposit_address)

    cdef str c_deposit(self, WalletBase from_wallet, str currency, double amount):
        cdef:
            int64_t tracking_nonce = <int64_t>(time.time() * 1e6)
            str tracking_id = str(f"deposit://{currency}/{tracking_nonce}")
        asyncio.ensure_future(self.execute_deposit(tracking_id, from_wallet, currency, amount))

        self._tx_tracker.c_start_tx_tracking(tracking_id, self.DEPOSIT_TIMEOUT)
        return tracking_id

    async def execute_withdraw(self, tracking_id: str, to_address: str, currency: str, amount: float):
        decimal_amount = str(Decimal(f"{amount:.12g}"))
        try:
            withdraw_result = await self.query_api(self._binance_client.withdraw,
                                                   asset=currency, address=to_address, amount=decimal_amount)
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(f"Error sending withdraw request to Binance for {currency}.", exc_info=True)
            self.c_trigger_event(self.MARKET_TRANSACTION_FAILURE_EVENT_TAG,
                                 MarketTransactionFailureEvent(self._current_timestamp, tracking_id))
            return

        # Since the Binance API client already does some checking for us, if no exception has been raised... the
        # withdraw result here should be valid.
        withdraw_fee = self._withdraw_rules[currency].withdraw_fee if currency in self._withdraw_rules else 0.0
        self.c_trigger_event(self.MARKET_WITHDRAW_ASSET_EVENT_TAG,
                             MarketWithdrawAssetEvent(self._current_timestamp, tracking_id, to_address, currency,
                                                      float(amount), float(withdraw_fee)))

    cdef str c_withdraw(self, str address, str currency, double amount):
        cdef:
            int64_t tracking_nonce = <int64_t>(time.time() * 1e6)
            str tracking_id = str(f"withdraw://{currency}/{tracking_nonce}")
        asyncio.ensure_future(self.execute_withdraw(tracking_id, address, currency, amount))
        return tracking_id

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
            await self.query_api(self._binance_client.ping)
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

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

    async def execute_buy(self,
                          order_id: str,
                          symbol: str,
                          amount: float,
                          order_type: OrderType,
                          price: Optional[float] = NaN):
        cdef:
            TradingRule trading_rule = self._trading_rules[symbol]
            object m = self.SYMBOL_SPLITTER.match(self.symbol)
            str base_currency = m.group(1)
            str quote_currency = m.group(2)
            object buy_fee = self.c_get_fee(base_currency, quote_currency, order_type, TradeType.BUY, amount, price)
            double adjusted_amount

        # Unlike most other exchanges, Binance takes fees out of requested base amount instead of
        # charging additional fees for limit and market buy orders.
        # To make the Binance market class function like other market classes, the amount base
        # token requested is adjusted to account for fees.
        adjusted_amount = amount / (1 - buy_fee.percent)
        decimal_amount = self.quantize_order_amount(symbol, adjusted_amount)
        if decimal_amount < trading_rule.min_order_size:
            raise ValueError(f"Buy order amount {decimal_amount} is lower than the minimum order size "
                             f"{trading_rule.min_order_size}.")

        try:
            self.c_start_tracking_order(order_id, -1, symbol, True, decimal_amount)
            order_result = None
            if order_type is OrderType.LIMIT:
                order_result = await self.query_api(self._binance_client.order_limit_buy,
                                                    symbol=symbol,
                                                    quantity=str(decimal_amount),
                                                    price=price,
                                                    newClientOrderId=order_id)
            elif order_type is OrderType.MARKET:
                order_result = await self.query_api(self._binance_client.order_market_buy,
                                                    symbol=symbol,
                                                    quantity=str(decimal_amount),
                                                    newClientOrderId=order_id)
            else:
                raise ValueError(f"Invalid OrderType {order_type}. Aborting.")

            self.c_trigger_event(self.MARKET_BUY_ORDER_CREATED_EVENT_TAG,
                                 BuyOrderCreatedEvent(
                                     self._current_timestamp,
                                     order_type,
                                     symbol,
                                     decimal_amount,
                                     0.0 if math.isnan(price) else price,
                                     order_id
                                 ))

            exchange_order_id = order_result["orderId"]
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(f"Created {order_type} buy order {order_id} for "
                                   f"{decimal_amount} {symbol}.")
                tracked_order.exchange_order_id = exchange_order_id
        except asyncio.CancelledError:
            raise
        except Exception:
            self.c_stop_tracking_order(order_id)
            order_type_str = 'MARKET' if order_type == OrderType.MARKET else 'LIMIT'
            self.logger().error(f"Error submitting buy {order_type_str} order to Binance for "
                                f"{decimal_amount} {symbol} {price}.",
                                exc_info=True)
            self.c_trigger_event(self.MARKET_TRANSACTION_FAILURE_EVENT_TAG,
                                 MarketTransactionFailureEvent(self._current_timestamp, order_id))

    cdef str c_buy(self, str symbol, double amount, object order_type = OrderType.MARKET, double price = NaN,
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

        decimal_amount = self.quantize_order_amount(symbol, amount)
        if decimal_amount < trading_rule.min_order_size:
            raise ValueError(f"Sell order amount {decimal_amount} is lower than the minimum order size "
                             f"{trading_rule.min_order_size}.")

        try:
            self.c_start_tracking_order(order_id, -1, symbol, False, decimal_amount)
            order_result = None
            if order_type is OrderType.LIMIT:
                order_result = await self.query_api(self._binance_client.order_limit_sell,
                                                    symbol=symbol,
                                                    quantity=str(decimal_amount),
                                                    price=str(price),
                                                    newClientOrderId=order_id)
            elif order_type is OrderType.MARKET:
                order_result = await self.query_api(self._binance_client.order_market_sell,
                                                    symbol=symbol,
                                                    quantity=str(decimal_amount),
                                                    newClientOrderId=order_id)
            else:
                raise ValueError(f"Invalid OrderType {order_type}. Aborting.")

            self.c_trigger_event(self.MARKET_SELL_ORDER_CREATED_EVENT_TAG,
                                 SellOrderCreatedEvent(
                                     self._current_timestamp,
                                     order_type,
                                     symbol,
                                     decimal_amount,
                                     0.0 if math.isnan(price) else price,
                                     order_id
                                 ))
            exchange_order_id = order_result["orderId"]
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(f"Created {order_type} sell order {order_id} for "
                                   f"{decimal_amount} {symbol}.")
                tracked_order.exchange_order_id = exchange_order_id
        except asyncio.CancelledError:
            raise
        except Exception:
            self.c_stop_tracking_order(order_id)
            order_type_str = 'MARKET' if order_type == OrderType.MARKET else 'LIMIT'
            self.logger().error(f"Error submitting sell {order_type_str} order to Binance for "
                                f"{decimal_amount} {symbol} {price}.",
                                exc_info=True)
            self.c_trigger_event(self.MARKET_TRANSACTION_FAILURE_EVENT_TAG,
                                 MarketTransactionFailureEvent(self._current_timestamp, order_id))

    cdef str c_sell(self, str symbol, double amount, object order_type = OrderType.MARKET, double price = NaN,
                    dict kwargs = {}):
        cdef:
            int64_t tracking_nonce = <int64_t>(time.time() * 1e6)
            str order_id = str(f"sell-{symbol}-{tracking_nonce}")
        asyncio.ensure_future(self.execute_sell(order_id, symbol, amount, order_type, price))
        return order_id

    async def execute_cancel(self, symbol: str, order_id: str):
        try:
            cancel_result = await self.query_api(self._binance_client.cancel_order,
                                                 symbol=symbol,
                                                 origClientOrderId=order_id)
        except BinanceAPIException as e:
            if "Unknown order sent" in e.message:
                # The order was never there to begin with. So cancelling it is a no-op but semantically successful.
                self.logger().info(f"The order {order_id} does not exist on Binance. No cancellation needed.")
                self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                     OrderCancelledEvent(self._current_timestamp, order_id))
                return {
                    # Required by cancel_all() below.
                    "origClientOrderId": order_id
                }

        if isinstance(cancel_result, dict) and cancel_result.get("status") == "CANCELED":
            self.logger().info(f"Successfully cancelled order {order_id}.")
            self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                 OrderCancelledEvent(self._current_timestamp, order_id))
        return cancel_result

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
                cancellation_results = await asyncio.gather(*tasks, return_exceptions=True)
                for cr in cancellation_results:
                    if isinstance(cr, BinanceAPIException):
                        continue
                    if isinstance(cr, dict) and "origClientOrderId" in cr:
                        client_order_id = cr.get("origClientOrderId")
                        order_id_set.remove(client_order_id)
                        successful_cancellations.append(CancellationResult(client_order_id, True))
        except Exception:
            self.logger().error(f"Unexpected error cancelling orders.", exc_info=True)

        failed_cancellations = [CancellationResult(oid, False) for oid in order_id_set]
        return successful_cancellations + failed_cancellations

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

    cdef c_start_tracking_deposit(self, str tracking_id, int64_t start_time_ms, str tx_hash, str from_address,
                                  str to_address):
        self._in_flight_deposits[tracking_id] = InFlightDeposit(tracking_id, start_time_ms, tx_hash, from_address,
                                                                to_address)

    cdef c_stop_tracking_deposit(self, str tracking_id):
        self._tx_tracker.c_stop_tx_tracking(tracking_id)
        if tracking_id in self._in_flight_deposits:
            del self._in_flight_deposits[tracking_id]

    cdef c_start_tracking_order(self, str order_id, int64_t exchange_order_id, str symbol, bint is_buy, object amount):
        self._in_flight_orders[order_id] = InFlightOrder(order_id, exchange_order_id, symbol, is_buy, amount)

    cdef c_stop_tracking_order(self, str order_id):
        if order_id in self._in_flight_orders:
            del self._in_flight_orders[order_id]

    cdef object c_get_order_price_quantum(self, str symbol, double price):
        cdef:
            TradingRule trading_rule = self._trading_rules[symbol]
        return trading_rule.price_tick_size

    cdef object c_get_order_size_quantum(self, str symbol, double order_size):
        cdef:
            TradingRule trading_rule = self._trading_rules[symbol]
        return Decimal(trading_rule.order_step_size)

    cdef object c_quantize_order_amount(self, str symbol, double amount):
        cdef:
            TradingRule trading_rule = self._trading_rules[symbol]

        global s_decimal_0
        quantized_amount = MarketBase.c_quantize_order_amount(self, symbol, amount)

        # Check against min_order_size and min_notional_size. If not passing either check, return 0.
        if quantized_amount < trading_rule.min_order_size:
            return s_decimal_0

        cdef:
            double current_price = self.c_get_price(symbol, False)
            double notional_size = current_price * float(quantized_amount)

        # Add 1% as a safety factor in case the prices changed while making the order.
        if notional_size < float(trading_rule.min_notional_size) * 1.01:
            return s_decimal_0

        return quantized_amount
