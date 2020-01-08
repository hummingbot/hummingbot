from collections import defaultdict
from libc.stdint cimport int64_t
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
from decimal import Decimal
from functools import partial
import logging
import pandas as pd
import re
from typing import (
    Any,
    Dict,
    List,
    AsyncIterable,
    Optional,
    Coroutine,
    Tuple,
)
import conf
from hummingbot.core.utils.async_call_scheduler import AsyncCallScheduler
from hummingbot.core.clock cimport Clock
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from hummingbot.market.binance.binance_api_order_book_data_source import BinanceAPIOrderBookDataSource
from hummingbot.logger import HummingbotLogger
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
from hummingbot.market.market_base import (
    MarketBase,
    s_decimal_NaN,
)
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.data_type.order_book_tracker import OrderBookTrackerDataSourceType
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.market.binance.binance_order_book_tracker import BinanceOrderBookTracker
from hummingbot.market.binance.binance_user_stream_tracker import BinanceUserStreamTracker
from hummingbot.market.binance.binance_time import BinanceTime
from hummingbot.market.binance.binance_in_flight_order import BinanceInFlightOrder
from hummingbot.market.deposit_info import DepositInfo
from hummingbot.core.data_type.user_stream_tracker import UserStreamTrackerDataSourceType
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.transaction_tracker import TransactionTracker
from hummingbot.market.trading_rule cimport TradingRule
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce

s_logger = None
s_decimal_0 = Decimal(0)
TRADING_PAIR_SPLITTER = re.compile(r"^(\w+)(BTC|ETH|BNB|XRP|USDT|USDC|USDS|TUSD|PAX|TRX|BUSD|NGN|RUB|TRY|EUR)$")


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
        public object min_withdraw_amount
        public object withdraw_fee

    def __init__(self, asset_name: str, min_withdraw_amount: float, withdraw_fee: float):
        self.asset_name = asset_name
        self.min_withdraw_amount = min_withdraw_amount
        self.withdraw_fee = withdraw_fee

    def __repr__(self) -> str:
        return f"WithdrawRule(asset_name='{self.asset_name}', min_withdraw_amount={self.min_withdraw_amount}, " \
               f"withdraw_fee={self.withdraw_fee})"


cdef class BinanceMarket(MarketBase):
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
    BINANCE_TRADE_TOPIC_NAME = "binance-trade.serialized"
    BINANCE_USER_STREAM_TOPIC_NAME = "binance-user-stream.serialized"

    ORDER_NOT_EXIST_CONFIRMATION_COUNT = 3

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(__name__)
        return s_logger

    def __init__(self,
                 binance_api_key: str,
                 binance_api_secret: str,
                 poll_interval: float = 5.0,
                 order_book_tracker_data_source_type: OrderBookTrackerDataSourceType =
                 OrderBookTrackerDataSourceType.EXCHANGE_API,
                 user_stream_tracker_data_source_type: UserStreamTrackerDataSourceType =
                 UserStreamTrackerDataSourceType.EXCHANGE_API,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True):

        self.monkey_patch_binance_time()
        super().__init__()
        self._trading_required = trading_required
        self._order_book_tracker = BinanceOrderBookTracker(data_source_type=order_book_tracker_data_source_type,
                                                           trading_pairs=trading_pairs)
        self._binance_client = BinanceClient(binance_api_key, binance_api_secret)
        self._user_stream_tracker = BinanceUserStreamTracker(
            data_source_type=user_stream_tracker_data_source_type, binance_client=self._binance_client)
        self._ev_loop = asyncio.get_event_loop()
        self._poll_notifier = asyncio.Event()
        self._last_timestamp = 0
        self._poll_interval = poll_interval
        self._in_flight_orders = {}  # Dict[client_order_id:str, BinanceInFlightOrder]
        self._order_not_found_records = {}  # Dict[client_order_id:str, count:int]
        self._tx_tracker = BinanceMarketTransactionTracker(self)
        self._withdraw_rules = {}  # Dict[trading_pair:str, WithdrawRule]
        self._trading_rules = {}  # Dict[trading_pair:str, TradingRule]
        self._trade_fees = {}  # Dict[trading_pair:str, (maker_fee_percent:Decimal, taken_fee_percent:Decimal)]
        self._last_update_trade_fees_timestamp = 0
        self._data_source_type = order_book_tracker_data_source_type
        self._status_polling_task = None
        self._user_stream_tracker_task = None
        self._user_stream_event_listener_task = None
        self._order_tracker_task = None
        self._trading_rules_polling_task = None
        self._async_scheduler = AsyncCallScheduler(call_interval=0.5)
        self._last_pull_timestamp = 0

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
        if BinanceMarket.split_trading_pair(exchange_trading_pair) is None:
            return None
        # Binance does not split BASEQUOTE (BTCUSDT)
        base_asset, quote_asset = BinanceMarket.split_trading_pair(exchange_trading_pair)
        return f"{base_asset}-{quote_asset}"

    @staticmethod
    def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
        # Binance does not split BASEQUOTE (BTCUSDT)
        return hb_trading_pair.replace("-", "")

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
    def in_flight_orders(self) -> Dict[str, BinanceInFlightOrder]:
        return self._in_flight_orders

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
            key: BinanceInFlightOrder.from_json(value)
            for key, value in saved_states.items()
        })

    async def get_active_exchange_markets(self) -> pd.DataFrame:
        return await BinanceAPIOrderBookDataSource.get_active_exchange_markets()

    def monkey_patch_binance_time(self):
        if binance_client_module.time != BinanceTime.get_instance():
            binance_client_module.time = BinanceTime.get_instance()
            BinanceTime.get_instance().start()

    async def schedule_async_call(
            self,
            coro: Coroutine,
            timeout_seconds: float,
            app_warning_msg: str = "Binance API call failed. Check API key and network connection.") -> any:
        return await self._async_scheduler.schedule_async_call(coro, timeout_seconds, app_warning_msg=app_warning_msg)

    async def query_api(
            self,
            func,
            *args,
            app_warning_msg: str = "Binance API call failed. Check API key and network connection.",
            **kwargs) -> Dict[str, any]:
        return await self._async_scheduler.call_async(partial(func, *args, **kwargs),
                                                      timeout_seconds=self.API_CALL_TIMEOUT,
                                                      app_warning_msg=app_warning_msg)

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
            free_balance = Decimal(balance_entry["free"])
            total_balance = Decimal(balance_entry["free"]) + Decimal(balance_entry["locked"])
            self._account_available_balances[asset_name] = free_balance
            self._account_balances[asset_name] = total_balance
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    async def _update_trade_fees(self):
        cdef:
            double current_timestamp = self._current_timestamp

        if current_timestamp - self._last_update_trade_fees_timestamp > 60.0 * 60.0 or len(self._trade_fees) < 1:
            try:
                res = await self.query_api(self._binance_client.get_trade_fee)
                for fee in res["tradeFee"]:
                    self._trade_fees[fee["symbol"]] = (Decimal(fee["maker"]), Decimal(fee["taker"]))
                self._last_update_trade_fees_timestamp = current_timestamp
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network("Error fetching Binance trade fees.", exc_info=True,
                                      app_warning_msg=f"Could not fetch Binance trading fees. "
                                                      f"Check network connection.")
                raise

    cdef object c_get_fee(self,
                          str base_currency,
                          str quote_currency,
                          object order_type,
                          object order_side,
                          object amount,
                          object price):
        cdef:
            object maker_trade_fee = Decimal("0.001")
            object taker_trade_fee = Decimal("0.001")
            str trading_pair = base_currency + quote_currency

        if trading_pair not in self._trade_fees:
            # https://www.binance.com/en/fee/schedule
            self.logger().warning(f"Unable to find trade fee for {trading_pair}. Using default 0.1% maker/taker fee.")
        else:
            maker_trade_fee, taker_trade_fee = self._trade_fees.get(trading_pair)
        return TradeFee(percent=maker_trade_fee if order_type is OrderType.LIMIT else taker_trade_fee)

    async def _update_withdraw_rules(self):
        cdef:
            # The poll interval for withdraw rules is 60 seconds.
            int64_t last_tick = <int64_t>(self._last_timestamp / 60.0)
            int64_t current_tick = <int64_t>(self._current_timestamp / 60.0)
        if current_tick > last_tick or len(self._withdraw_rules) < 1:
            asset_rules = await self.query_url("https://www.binance.com/assetWithdraw/getAllAsset.html")
            for asset_rule in asset_rules:
                asset_name = asset_rule["assetCode"]
                min_withdraw_amount = Decimal(asset_rule["minProductWithdraw"])
                withdraw_fee = Decimal(asset_rule["transactionFee"])
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
            trading_rules_list = self._format_trading_rules(exchange_info)
            self._trading_rules.clear()
            for trading_rule in trading_rules_list:
                self._trading_rules[trading_rule.trading_pair] = trading_rule

    def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        """
        Example:
        {
            "symbol": "ETHBTC",
            "baseAssetPrecision": 8,
            "quotePrecision": 8,
            "orderTypes": ["LIMIT", "MARKET"],
            "filters": [
                {
                    "filterType": "PRICE_FILTER",
                    "minPrice": "0.00000100",
                    "maxPrice": "100000.00000000",
                    "tickSize": "0.00000100"
                }, {
                    "filterType": "LOT_SIZE",
                    "minQty": "0.00100000",
                    "maxQty": "100000.00000000",
                    "stepSize": "0.00100000"
                }, {
                    "filterType": "MIN_NOTIONAL",
                    "minNotional": "0.00100000"
                }
            ]
        }
        """
        cdef:
            list trading_pair_rules = exchange_info_dict.get("symbols", [])
            list retval = []
        for rule in trading_pair_rules:
            try:
                trading_pair = rule.get("symbol")
                filters = rule.get("filters")
                price_filter = [f for f in filters if f.get("filterType") == "PRICE_FILTER"][0]
                lot_size_filter = [f for f in filters if f.get("filterType") == "LOT_SIZE"][0]
                min_notional_filter = [f for f in filters if f.get("filterType") == "MIN_NOTIONAL"][0]

                min_order_size = Decimal(lot_size_filter.get("minQty"))
                tick_size = price_filter.get("tickSize")
                step_size = Decimal(lot_size_filter.get("stepSize"))
                min_notional = Decimal(min_notional_filter.get("minNotional"))

                retval.append(
                    TradingRule(trading_pair,
                                min_order_size=min_order_size,
                                min_price_increment=Decimal(tick_size),
                                min_base_amount_increment=Decimal(step_size),
                                min_notional_size=Decimal(min_notional)))

            except Exception:
                self.logger().error(f"Error parsing the trading pair rule {rule}. Skipping.", exc_info=True)
        return retval

    async def _update_order_fills_from_trades(self):
        cdef:
            # This is intended to be a backup measure to get filled events with trade ID for orders,
            # in case Binance's user stream events are not working.
            # This is separated from _update_order_status which only updates the order status without producing filled
            # events, since Binance's get order endpoint does not return trade IDs.
            # The poll interval for order status is 10 seconds.
            int64_t last_tick = <int64_t>(self._last_pull_timestamp / 10.0)
            int64_t current_tick = <int64_t>(self._current_timestamp / 10.0)

        if current_tick > last_tick and len(self._in_flight_orders) > 0:
            trading_pairs_to_order_map = defaultdict(lambda: {})
            for o in self._in_flight_orders.values():
                trading_pairs_to_order_map[o.trading_pair][o.exchange_order_id] = o

            trading_pairs = list(trading_pairs_to_order_map.keys())
            tasks = [self.query_api(self._binance_client.get_my_trades, symbol=trading_pair)
                     for trading_pair in trading_pairs]
            results = await safe_gather(*tasks, return_exceptions=True)
            for trades, trading_pair in zip(results, trading_pairs):
                order_map = trading_pairs_to_order_map[trading_pair]
                if isinstance(trades, Exception):
                    self.logger().network(
                        f"Error fetching trades update for the order {trading_pair}: {trades}.",
                        app_warning_msg=f"Failed to fetch trade update for {trading_pair}."
                    )
                    continue
                for trade in trades:
                    order_id = str(trade["orderId"])
                    if order_id in order_map:
                        tracked_order = order_map[order_id]
                        order_type = OrderType.LIMIT if trade["isMaker"] else OrderType.MARKET
                        applied_trade = order_map[order_id].update_with_trade_update(trade)
                        if applied_trade:
                            self.c_trigger_event(self.MARKET_ORDER_FILLED_EVENT_TAG,
                                                 OrderFilledEvent(
                                                     self._current_timestamp,
                                                     tracked_order.client_order_id,
                                                     tracked_order.trading_pair,
                                                     tracked_order.trade_type,
                                                     order_type,
                                                     Decimal(trade["price"]),
                                                     Decimal(trade["qty"]),
                                                     self.c_get_fee(
                                                         tracked_order.base_asset,
                                                         tracked_order.quote_asset,
                                                         order_type,
                                                         tracked_order.trade_type,
                                                         Decimal(trade["price"]),
                                                         Decimal(trade["qty"])),
                                                     exchange_trade_id=trade["id"]
                                                 ))

    async def _update_order_status(self):
        cdef:
            # This is intended to be a backup measure to close straggler orders, in case Binance's user stream events
            # are not working.
            # The poll interval for order status is 10 seconds.
            int64_t last_tick = <int64_t>(self._last_pull_timestamp / 10.0)
            int64_t current_tick = <int64_t>(self._current_timestamp / 10.0)

        if current_tick > last_tick and len(self._in_flight_orders) > 0:
            tracked_orders = list(self._in_flight_orders.values())
            tasks = [self.query_api(self._binance_client.get_order,
                                    symbol=o.trading_pair, origClientOrderId=o.client_order_id)
                     for o in tracked_orders]
            results = await safe_gather(*tasks, return_exceptions=True)
            for order_update, tracked_order in zip(results, tracked_orders):
                client_order_id = tracked_order.client_order_id

                # If the order has already been cancelled or has failed do nothing
                if client_order_id not in self._in_flight_orders:
                    continue

                if isinstance(order_update, Exception):
                    if order_update.code == 2013 or order_update.message == "Order does not exist.":
                        self._order_not_found_records[client_order_id] = \
                            self._order_not_found_records.get(client_order_id, 0) + 1
                        if self._order_not_found_records[client_order_id] < self.ORDER_NOT_EXIST_CONFIRMATION_COUNT:
                            # Wait until the order not found error have repeated a few times before actually treating
                            # it as failed. See: https://github.com/CoinAlpha/hummingbot/issues/601
                            continue
                        self.c_trigger_event(
                            self.MARKET_ORDER_FAILURE_EVENT_TAG,
                            MarketOrderFailureEvent(self._current_timestamp, client_order_id, tracked_order.order_type)
                        )
                        self.c_stop_tracking_order(client_order_id)
                    else:
                        self.logger().network(
                            f"Error fetching status update for the order {client_order_id}: {order_update}.",
                            app_warning_msg=f"Failed to fetch status update for the order {client_order_id}."
                        )
                    continue

                # Update order execution status
                tracked_order.last_state = order_update["status"]
                order_type = OrderType.LIMIT if order_update["type"] == "LIMIT" else OrderType.MARKET
                executed_amount_base = Decimal(order_update["executedQty"])
                executed_amount_quote = Decimal(order_update["cummulativeQuoteQty"])

                if tracked_order.is_done:
                    if not tracked_order.is_failure:
                        if tracked_order.trade_type is TradeType.BUY:
                            self.logger().info(f"The market buy order {tracked_order.client_order_id} has completed "
                                               f"according to order status API.")
                            self.c_trigger_event(self.MARKET_BUY_ORDER_COMPLETED_EVENT_TAG,
                                                 BuyOrderCompletedEvent(self._current_timestamp,
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
                            self.logger().info(f"The market sell order {client_order_id} has completed "
                                               f"according to order status API.")
                            self.c_trigger_event(self.MARKET_SELL_ORDER_COMPLETED_EVENT_TAG,
                                                 SellOrderCompletedEvent(self._current_timestamp,
                                                                         client_order_id,
                                                                         tracked_order.base_asset,
                                                                         tracked_order.quote_asset,
                                                                         (tracked_order.fee_asset
                                                                          or tracked_order.quote_asset),
                                                                         executed_amount_base,
                                                                         executed_amount_quote,
                                                                         tracked_order.fee_paid,
                                                                         order_type))
                    else:
                        # check if its a cancelled order
                        # if its a cancelled order, issue cancel and stop tracking order
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
                self.logger().network(
                    "Unknown error. Retrying after 5 seconds.",
                    exc_info=True,
                    app_warning_msg="Could not fetch message from Kafka. Check network connection."
                )
                await asyncio.sleep(5.0)

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
                # Refer to https://github.com/binance-exchange/binance-official-api-docs/blob/master/user-data-stream.md
                # As per the order update section in Binance the ID of the order being cancelled is under the "C" key
                if event_type == "executionReport":
                    execution_type = event_message.get("x")
                    if execution_type != "CANCELED":
                        client_order_id = event_message.get("c")
                    else:
                        client_order_id = event_message.get("C")

                    tracked_order = self._in_flight_orders.get(client_order_id)

                    if tracked_order is None:
                        # Hiding the messages for now. Root cause to be investigated in later sprints.
                        self.logger().debug(f"Unrecognized order ID from user stream: {client_order_id}.")
                        self.logger().debug(f"Event: {event_message}")
                        continue

                    tracked_order.update_with_execution_report(event_message)

                    if execution_type == "TRADE":
                        order_filled_event = OrderFilledEvent.order_filled_event_from_binance_execution_report(event_message)
                        order_filled_event = order_filled_event._replace(trade_fee=self.c_get_fee(
                            tracked_order.base_asset,
                            tracked_order.quote_asset,
                            OrderType.LIMIT if event_message["o"] == "LIMIT" else OrderType.MARKET,
                            TradeType.BUY if event_message["S"] == "BUY" else TradeType.SELL,
                            Decimal(event_message["l"]),
                            Decimal(event_message["L"])
                        ))
                        self.c_trigger_event(self.MARKET_ORDER_FILLED_EVENT_TAG, order_filled_event)

                    if tracked_order.is_done:
                        if not tracked_order.is_failure:
                            if tracked_order.trade_type is TradeType.BUY:
                                self.logger().info(f"The market buy order {tracked_order.client_order_id} has completed "
                                                   f"according to user stream.")
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
                                                                            tracked_order.order_type))
                            else:
                                self.logger().info(f"The market sell order {tracked_order.client_order_id} has completed "
                                                   f"according to user stream.")
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
                        else:
                            # check if its a cancelled order
                            # if its a cancelled order, check in flight orders
                            # if present in in flight orders issue cancel and stop tracking order
                            if tracked_order.is_cancelled:
                                if tracked_order.client_order_id in self._in_flight_orders:
                                    self.logger().info(f"Successfully cancelled order {tracked_order.client_order_id}.")
                                    self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                                         OrderCancelledEvent(
                                                             self._current_timestamp,
                                                             tracked_order.client_order_id))
                            else:
                                self.logger().info(f"The market order {tracked_order.client_order_id} has failed according to "
                                                   f"order status API.")
                                self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                                     MarketOrderFailureEvent(
                                                         self._current_timestamp,
                                                         tracked_order.client_order_id,
                                                         tracked_order.order_type
                                                     ))
                        self.c_stop_tracking_order(tracked_order.client_order_id)

                elif event_type == "outboundAccountInfo":
                    local_asset_names = set(self._account_balances.keys())
                    remote_asset_names = set()
                    balances = event_message["B"]
                    for balance_entry in balances:
                        asset_name = balance_entry["a"]
                        free_balance = Decimal(balance_entry["f"])
                        total_balance = Decimal(balance_entry["f"]) + Decimal(balance_entry["l"])
                        self._account_available_balances[asset_name] = free_balance
                        self._account_balances[asset_name] = total_balance
                        remote_asset_names.add(asset_name)

                    asset_names_to_remove = local_asset_names.difference(remote_asset_names)
                    for asset_name in asset_names_to_remove:
                        del self._account_available_balances[asset_name]
                        del self._account_balances[asset_name]

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
                await safe_gather(
                    self._update_balances(),
                    self._update_order_fills_from_trades(),
                    self._update_order_status(),
                )
                self._last_pull_timestamp = self._current_timestamp
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network("Unexpected error while fetching account updates.", exc_info=True,
                                      app_warning_msg="Could not fetch account updates from Binance. "
                                                      "Check API key and network connection.")
                await asyncio.sleep(0.5)

    async def _trading_rules_polling_loop(self):
        while True:
            try:
                await safe_gather(
                    self._update_withdraw_rules(),
                    self._update_trading_rules(),
                    self._update_trade_fees()
                )
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network("Unexpected error while fetching trading rules.", exc_info=True,
                                      app_warning_msg="Could not fetch new trading rules from Binance. "
                                                      "Check network connection.")
                await asyncio.sleep(0.5)

    @property
    def status_dict(self) -> Dict[str, bool]:
        return {
            "order_books_initialized": self._order_book_tracker.ready,
            "account_balance": len(self._account_balances) > 0 if self._trading_required else True,
            "withdraw_rules_initialized": len(self._withdraw_rules) > 0,
            "trading_rule_initialized": len(self._trading_rules) > 0,
            "trade_fees_initialized": len(self._trade_fees) > 0
        }

    @property
    def ready(self) -> bool:
        return all(self.status_dict.values())

    async def server_time(self) -> int:
        """
        :return: The current server time in milliseconds since UNIX epoch.
        """
        result = await self.query_api(self._binance_client.get_server_time)
        return result["serverTime"]

    async def get_deposit_info(self, asset: str) -> DepositInfo:
        cdef:
            dict deposit_reply
            str err_msg
            str deposit_address

        deposit_reply = await self.query_api(self._binance_client.get_deposit_address, asset=asset)
        if deposit_reply.get("success") is not True:
            err_msg = deposit_reply.get("msg") or str(deposit_reply)
            self.logger().network(f"Could not get deposit address for {asset}: {err_msg}",
                                  app_warning_msg=f"Could not get deposit address for {asset}: {err_msg}.")

        deposit_address = deposit_reply["address"]
        del deposit_reply["address"]
        return DepositInfo(deposit_address, **deposit_reply)

    async def execute_withdraw(self, tracking_id: str, to_address: str, currency: str, amount: Decimal):
        decimal_amount = str(f"{amount:.12g}")
        try:
            withdraw_result = await self.query_api(self._binance_client.withdraw,
                                                   asset=currency, address=to_address, amount=decimal_amount)
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().network(
                f"Error sending withdraw request to Binance for {currency}.",
                exc_info=True,
                app_warning_msg=f"Could not send {currency} withdrawal request to Binance. "
                                f"Check network connection."
            )
            self.c_trigger_event(self.MARKET_TRANSACTION_FAILURE_EVENT_TAG,
                                 MarketTransactionFailureEvent(self._current_timestamp, tracking_id))
            return

        # Since the Binance API client already does some checking for us, if no exception has been raised... the
        # withdraw result here should be valid.
        withdraw_fee = self._withdraw_rules[currency].withdraw_fee if currency in self._withdraw_rules else s_decimal_0
        self.c_trigger_event(self.MARKET_WITHDRAW_ASSET_EVENT_TAG,
                             MarketWithdrawAssetEvent(self._current_timestamp, tracking_id, to_address, currency,
                                                      amount, withdraw_fee))

    cdef str c_withdraw(self, str address, str currency, object amount):
        cdef:
            int64_t tracking_nonce = <int64_t> get_tracking_nonce()
            str tracking_id = str(f"withdraw://{currency}/{tracking_nonce}")
        safe_ensure_future(self.execute_withdraw(tracking_id, address, currency, amount))
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
        self._order_tracker_task = safe_ensure_future(self._order_book_tracker.start())
        self._trading_rules_polling_task = safe_ensure_future(self._trading_rules_polling_loop())
        if self._trading_required:
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())
            self._user_stream_tracker_task = safe_ensure_future(self._user_stream_tracker.start())
            self._user_stream_event_listener_task = safe_ensure_future(self._user_stream_event_listener())

    def _stop_network(self):
        if self._order_tracker_task is not None:
            self._order_tracker_task.cancel()
        if self._status_polling_task is not None:
            self._status_polling_task.cancel()
        if self._user_stream_tracker_task is not None:
            self._user_stream_tracker_task.cancel()
        if self._user_stream_event_listener_task is not None:
            self._user_stream_event_listener_task.cancel()
        if self._trading_rules_polling_task is not None:
            self._trading_rules_polling_task.cancel()
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
        MarketBase.c_tick(self, timestamp)
        self._tx_tracker.c_tick(timestamp)
        if current_tick > last_tick:
            if not self._poll_notifier.is_set():
                self._poll_notifier.set()
        self._last_timestamp = timestamp

    async def execute_buy(self,
                          order_id: str,
                          trading_pair: str,
                          amount: Decimal,
                          order_type: OrderType,
                          price: Optional[Decimal] = s_decimal_NaN):
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]
            object m = TRADING_PAIR_SPLITTER.match(trading_pair)
            str base_currency = m.group(1)
            str quote_currency = m.group(2)
            object buy_fee = self.c_get_fee(base_currency, quote_currency, order_type, TradeType.BUY, amount, price)
            double adjusted_amount

        decimal_amount = self.c_quantize_order_amount(trading_pair, amount)
        decimal_price = (self.c_quantize_order_price(trading_pair, price)
                         if order_type is OrderType.LIMIT
                         else s_decimal_0)
        if decimal_amount < trading_rule.min_order_size:
            raise ValueError(f"Buy order amount {decimal_amount} is lower than the minimum order size "
                             f"{trading_rule.min_order_size}.")

        try:
            order_result = None
            order_decimal_amount = f"{decimal_amount:f}"
            if order_type is OrderType.LIMIT:
                order_decimal_price = f"{decimal_price:f}"
                self.c_start_tracking_order(
                    order_id,
                    "",
                    trading_pair,
                    TradeType.BUY,
                    decimal_price,
                    decimal_amount,
                    order_type
                )
                order_result = await self.query_api(self._binance_client.order_limit_buy,
                                                    symbol=trading_pair,
                                                    quantity=order_decimal_amount,
                                                    price=order_decimal_price,
                                                    newClientOrderId=order_id)
            elif order_type is OrderType.MARKET:
                self.c_start_tracking_order(
                    order_id,
                    "",
                    trading_pair,
                    TradeType.BUY,
                    Decimal("NaN"),
                    decimal_amount,
                    order_type
                )
                order_result = await self.query_api(self._binance_client.order_market_buy,
                                                    symbol=trading_pair,
                                                    quantity=order_decimal_amount,
                                                    newClientOrderId=order_id)
            else:
                raise ValueError(f"Invalid OrderType {order_type}. Aborting.")

            exchange_order_id = str(order_result["orderId"])
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(f"Created {order_type} buy order {order_id} for "
                                   f"{decimal_amount} {trading_pair}.")
                tracked_order.exchange_order_id = exchange_order_id
            self.c_trigger_event(self.MARKET_BUY_ORDER_CREATED_EVENT_TAG,
                                 BuyOrderCreatedEvent(
                                     self._current_timestamp,
                                     order_type,
                                     trading_pair,
                                     decimal_amount,
                                     decimal_price,
                                     order_id
                                 ))

        except asyncio.CancelledError:
            raise

        except Exception as e:
            self.c_stop_tracking_order(order_id)
            order_type_str = 'MARKET' if order_type == OrderType.MARKET else 'LIMIT'
            self.logger().network(
                f"Error submitting buy {order_type_str} order to Binance for "
                f"{decimal_amount} {trading_pair} "
                f"{decimal_price if order_type is OrderType.LIMIT else ''}.",
                exc_info=True,
                app_warning_msg=f"Failed to submit buy order to Binance. Check API key and network connection."
            )
            self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                 MarketOrderFailureEvent(self._current_timestamp, order_id, order_type))

    cdef str c_buy(self, str trading_pair, object amount, object order_type=OrderType.MARKET, object price=s_decimal_NaN,
                   dict kwargs={}):
        cdef:
            int64_t tracking_nonce = <int64_t> get_tracking_nonce()
            str order_id = str(f"buy-{trading_pair}-{tracking_nonce}")
        safe_ensure_future(self.execute_buy(order_id, trading_pair, amount, order_type, price))
        return order_id

    async def execute_sell(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           order_type: OrderType,
                           price: Optional[Decimal] = Decimal("NaN")):
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]

        decimal_amount = self.quantize_order_amount(trading_pair, amount)
        decimal_price = (self.c_quantize_order_price(trading_pair, price)
                         if order_type is OrderType.LIMIT
                         else s_decimal_0)
        if decimal_amount < trading_rule.min_order_size:
            raise ValueError(f"Sell order amount {decimal_amount} is lower than the minimum order size "
                             f"{trading_rule.min_order_size}.")

        try:
            order_result = None
            order_decimal_amount = f"{decimal_amount:f}"
            if order_type is OrderType.LIMIT:
                order_decimal_price = f"{decimal_price:f}"
                self.c_start_tracking_order(
                    order_id,
                    "",
                    trading_pair,
                    TradeType.SELL,
                    decimal_price,
                    decimal_amount,
                    order_type
                )
                order_result = await self.query_api(self._binance_client.order_limit_sell,
                                                    symbol=trading_pair,
                                                    quantity=order_decimal_amount,
                                                    price=order_decimal_price,
                                                    newClientOrderId=order_id)
            elif order_type is OrderType.MARKET:
                self.c_start_tracking_order(
                    order_id,
                    "",
                    trading_pair,
                    TradeType.SELL,
                    Decimal("NaN"),
                    decimal_amount,
                    order_type
                )
                order_result = await self.query_api(self._binance_client.order_market_sell,
                                                    symbol=trading_pair,
                                                    quantity=order_decimal_amount,
                                                    newClientOrderId=order_id)
            else:
                raise ValueError(f"Invalid OrderType {order_type}. Aborting.")

            exchange_order_id = str(order_result["orderId"])
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(f"Created {order_type} sell order {order_id} for "
                                   f"{decimal_amount} {trading_pair}.")
                tracked_order.exchange_order_id = exchange_order_id

            self.c_trigger_event(self.MARKET_SELL_ORDER_CREATED_EVENT_TAG,
                                 SellOrderCreatedEvent(
                                     self._current_timestamp,
                                     order_type,
                                     trading_pair,
                                     decimal_amount,
                                     decimal_price,
                                     order_id
                                 ))
        except asyncio.CancelledError:
            raise
        except Exception:
            self.c_stop_tracking_order(order_id)
            order_type_str = 'MARKET' if order_type is OrderType.MARKET else 'LIMIT'
            self.logger().network(
                f"Error submitting sell {order_type_str} order to Binance for "
                f"{decimal_amount} {trading_pair} "
                f"{decimal_price if order_type is OrderType.LIMIT else ''}.",
                exc_info=True,
                app_warning_msg=f"Failed to submit sell order to Binance. Check API key and network connection."
            )
            self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                 MarketOrderFailureEvent(self._current_timestamp, order_id, order_type))

    cdef str c_sell(self, str trading_pair, object amount, object order_type=OrderType.MARKET, object price=s_decimal_NaN,
                    dict kwargs={}):
        cdef:
            int64_t tracking_nonce = <int64_t> get_tracking_nonce()
            str order_id = str(f"sell-{trading_pair}-{tracking_nonce}")
        safe_ensure_future(self.execute_sell(order_id, trading_pair, amount, order_type, price))
        return order_id

    async def execute_cancel(self, trading_pair: str, order_id: str):
        try:
            cancel_result = await self.query_api(self._binance_client.cancel_order,
                                                 symbol=trading_pair,
                                                 origClientOrderId=order_id)
        except BinanceAPIException as e:
            if "Unknown order sent" in e.message or e.code == 2011:
                # The order was never there to begin with. So cancelling it is a no-op but semantically successful.
                self.logger().debug(f"The order {order_id} does not exist on Binance. No cancellation needed.")
                self.c_stop_tracking_order(order_id)
                self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                     OrderCancelledEvent(self._current_timestamp, order_id))
                return {
                    # Required by cancel_all() below.
                    "origClientOrderId": order_id
                }

        if isinstance(cancel_result, dict) and cancel_result.get("status") == "CANCELED":
            self.logger().info(f"Successfully cancelled order {order_id}.")
            self.c_stop_tracking_order(order_id)
            self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                 OrderCancelledEvent(self._current_timestamp, order_id))
        return cancel_result

    cdef c_cancel(self, str trading_pair, str order_id):
        safe_ensure_future(self.execute_cancel(trading_pair, order_id))
        return order_id

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        incomplete_orders = [o for o in self._in_flight_orders.values() if not o.is_done]
        tasks = [self.execute_cancel(o.trading_pair, o.client_order_id) for o in incomplete_orders]
        order_id_set = set([o.client_order_id for o in incomplete_orders])
        successful_cancellations = []

        try:
            async with timeout(timeout_seconds):
                cancellation_results = await safe_gather(*tasks, return_exceptions=True)
                for cr in cancellation_results:
                    if isinstance(cr, BinanceAPIException):
                        continue
                    if isinstance(cr, dict) and "origClientOrderId" in cr:
                        client_order_id = cr.get("origClientOrderId")
                        order_id_set.remove(client_order_id)
                        successful_cancellations.append(CancellationResult(client_order_id, True))
        except Exception:
            self.logger().network(
                f"Unexpected error cancelling orders.",
                exc_info=True,
                app_warning_msg="Failed to cancel order with Binance. Check API key and network connection."
            )

        failed_cancellations = [CancellationResult(oid, False) for oid in order_id_set]
        return successful_cancellations + failed_cancellations

    cdef OrderBook c_get_order_book(self, str trading_pair):
        cdef:
            dict order_books = self._order_book_tracker.order_books

        if trading_pair not in order_books:
            raise ValueError(f"No order book exists for '{trading_pair}'.")
        return order_books[trading_pair]

    cdef c_did_timeout_tx(self, str tracking_id):
        self.c_trigger_event(self.MARKET_TRANSACTION_FAILURE_EVENT_TAG,
                             MarketTransactionFailureEvent(self._current_timestamp, tracking_id))

    cdef c_start_tracking_order(self,
                                str order_id,
                                str exchange_order_id,
                                str trading_pair,
                                object trade_type,
                                object price,
                                object amount,
                                object order_type):
        self._in_flight_orders[order_id] = BinanceInFlightOrder(
            client_order_id=order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=trading_pair,
            order_type=order_type,
            trade_type=trade_type,
            price=price,
            amount=amount
        )

    cdef c_stop_tracking_order(self, str order_id):
        if order_id in self._in_flight_orders:
            del self._in_flight_orders[order_id]
        if order_id in self._order_not_found_records:
            del self._order_not_found_records[order_id]

    cdef object c_get_order_price_quantum(self, str trading_pair, object price):
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]
        return trading_rule.min_price_increment

    cdef object c_get_order_size_quantum(self, str trading_pair, object order_size):
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]
        return Decimal(trading_rule.min_base_amount_increment)

    cdef object c_quantize_order_amount(self, str trading_pair, object amount, object price=s_decimal_0):
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]
            object current_price = self.c_get_price(trading_pair, False)
            object notional_size
        global s_decimal_0
        quantized_amount = MarketBase.c_quantize_order_amount(self, trading_pair, amount)

        # Check against min_order_size and min_notional_size. If not passing either check, return 0.
        if quantized_amount < trading_rule.min_order_size:
            return s_decimal_0

        if price == s_decimal_0:
            notional_size = current_price * quantized_amount
        else:
            notional_size = price * quantized_amount

        # Add 1% as a safety factor in case the prices changed while making the order.
        if notional_size < trading_rule.min_notional_size * Decimal("1.01"):
            return s_decimal_0

        return quantized_amount
