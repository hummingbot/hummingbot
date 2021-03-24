from collections import defaultdict
from libc.stdint cimport int64_t
import aiohttp
from aiokafka import (
    AIOKafkaConsumer,
    ConsumerRecord
)
import asyncio
from async_timeout import timeout
from hummingbot.connector.exchange.tokocrypto.tokocrypto.client import Client as TokocryptoClient
from hummingbot.connector.exchange.tokocrypto.tokocrypto import client as tokocrypto_client_module
from hummingbot.connector.exchange.tokocrypto.tokocrypto.exceptions import TokocryptoAPIException
from decimal import Decimal
from functools import partial
import logging
import pandas as pd
import time
from typing import (
    Any,
    Dict,
    List,
    AsyncIterable,
    Optional,
    Coroutine,
)

import conf
from hummingbot.core.utils.asyncio_throttle import Throttler
from hummingbot.core.utils.async_call_scheduler import AsyncCallScheduler
from hummingbot.core.clock cimport Clock
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from hummingbot.connector.exchange.tokocrypto.tokocrypto_api_order_book_data_source import TokocryptoAPIOrderBookDataSource
from hummingbot.logger import HummingbotLogger
from hummingbot.core.event.events import (
    MarketEvent,
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
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.transaction_tracker import TransactionTracker
from hummingbot.connector.trading_rule cimport TradingRule
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce
from hummingbot.core.utils.estimate_fee import estimate_fee
from .tokocrypto_order_book_tracker import TokocryptoOrderBookTracker
from .tokocrypto_time import TokocryptoTime
from .tokocrypto_in_flight_order import TokocryptoInFlightOrder
from .tokocrypto_utils import (
    convert_from_exchange_trading_pair,
    convert_to_tokocrypto_exchange_trading_pair)

s_logger = None
s_decimal_0 = Decimal(0)
s_decimal_NaN = Decimal("nan")
BROKER_ID = "xTKOTC"


cdef str get_client_order_id(str order_side, object trading_pair):
    cdef:
        int64_t nonce = <int64_t> get_tracking_nonce()
        object symbols = trading_pair.split("-")
        str base = symbols[0].upper()
        str quote = symbols[1].upper()
    return f"{BROKER_ID}{order_side.upper()[0]}{base[0]}{base[-1]}{quote[0]}{quote[-1]}{nonce}"


cdef class TokocryptoExchangeTransactionTracker(TransactionTracker):
    cdef:
        TokocryptoExchange _owner

    def __init__(self, owner: TokocryptoExchange):
        super().__init__()
        self._owner = owner

    cdef c_did_timeout_tx(self, str tx_id):
        TransactionTracker.c_did_timeout_tx(self, tx_id)
        self._owner.c_did_timeout_tx(tx_id)


cdef class TokocryptoExchange(ExchangeBase):
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
    TOKOCRYPTO_TRADE_TOPIC_NAME = "tokocrypto-trade.serialized"
    TOKOCRYPTO_USER_STREAM_TOPIC_NAME = "tokocrypto-user-stream.serialized"

    ORDER_NOT_EXIST_CONFIRMATION_COUNT = 3

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(__name__)
        return s_logger

    def __init__(self,
                 tokocrypto_api_key: str,
                 tokocrypto_api_secret: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True,
                 domain="com"
                 ):

        self.monkey_patch_tokocrypto_time()
        super().__init__()
        self._trading_required = trading_required
        self._order_book_tracker = TokocryptoOrderBookTracker(trading_pairs=trading_pairs, domain=domain)
        self._domain = domain
        self._tokocrypto_client = TokocryptoClient(tokocrypto_api_key, tokocrypto_api_secret, tld=domain)
        self._user_stream_tracker = None
        self._ev_loop = asyncio.get_event_loop()
        self._poll_notifier = asyncio.Event()
        self._last_timestamp = 0
        self._in_flight_orders = {}  # Dict[client_order_id:str, BinanceInFlightOrder]
        self._order_not_found_records = {}  # Dict[client_order_id:str, count:int]
        self._tx_tracker = TokocryptoExchangeTransactionTracker(self)
        self._trading_rules = {}  # Dict[trading_pair:str, TradingRule]
        self._trade_fees = {}  # Dict[trading_pair:str, (maker_fee_percent:Decimal, taken_fee_percent:Decimal)]
        self._last_update_trade_fees_timestamp = 0
        self._status_polling_task = None
        self._user_stream_event_listener_task = None
        self._trading_rules_polling_task = None
        self._async_scheduler = AsyncCallScheduler(call_interval=0.5)
        self._last_poll_timestamp = 0
        self._throttler = Throttler((10.0, 1.0))

    @property
    def name(self) -> str:
        if self._domain == "com":
            return "tokocrypto"
        else:
            return f"tokocrypto_{self._domain}"

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        return self._order_book_tracker.order_books

    @property
    def tokocrypto_client(self) -> TokocryptoClient:
        return self._tokocrypto_client

    @property
    def trading_rules(self) -> Dict[str, TradingRule]:
        return self._trading_rules

    @property
    def in_flight_orders(self) -> Dict[str, TokocryptoInFlightOrder]:
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

    @property
    def order_book_tracker(self) -> TokocryptoOrderBookTracker:
        return self._order_book_tracker

    def restore_tracking_states(self, saved_states: Dict[str, any]):
        self._in_flight_orders.update({
            key: TokocryptoInFlightOrder.from_json(value)
            for key, value in saved_states.items()
        })

    async def get_active_exchange_markets(self) -> pd.DataFrame:
        return await TokocryptoAPIOrderBookDataSource.get_active_exchange_markets()

    def monkey_patch_tokocrypto_time(self):
        if tokocrypto_client_module.time != TokocryptoTime.get_instance():
            tokocrypto_client_module.time = TokocryptoTime.get_instance()
            TokocryptoTime.get_instance().start()

    async def schedule_async_call(
            self,
            coro: Coroutine,
            timeout_seconds: float,
            app_warning_msg: str = "Tokocrypto API call failed. Check API key and network connection.") -> any:
        return await self._async_scheduler.schedule_async_call(coro, timeout_seconds, app_warning_msg=app_warning_msg)

    async def query_api(
            self,
            func,
            *args,
            app_warning_msg: str = "Tokocrypto API call failed. Check API key and network connection.",
            request_weight: int = 1,
            **kwargs) -> Dict[str, any]:
        async with self._throttler.weighted_task(request_weight=request_weight):
            try:
                return await self._async_scheduler.call_async(partial(func, *args, **kwargs),
                                                              timeout_seconds=self.API_CALL_TIMEOUT,
                                                              app_warning_msg=app_warning_msg)
            except Exception as ex:
                if "Timestamp for this request" in str(ex):
                    self.logger().warning("Got Tokocrypto timestamp error. "
                                          "Going to force update Tokocrypto server time offset...")
                    tokocrypto_time = TokocryptoTime.get_instance()
                    tokocrypto_time.clear_time_offset_ms_samples()
                    await tokocrypto_time.schedule_update_server_time_offset()
                raise ex

    async def query_url(self, url, request_weight: int = 1) -> any:
        async with self._throttler.weighted_task(request_weight=request_weight):
            async with aiohttp.ClientSession() as client:
                async with client.get(url, timeout=self.API_CALL_TIMEOUT) as response:
                    if response.status != 200:
                        raise IOError(f"Error fetching data from {url}. HTTP status is {response.status}.")
                    data = await response.json()
                    return data

    async def _update_balances(self):
        cdef:
            dict account_info
            dict account_info_data
            list balances
            str asset_name
            set local_asset_names = set(self._account_balances.keys())
            set remote_asset_names = set()
            set asset_names_to_remove

        account_info = await self.query_api(self._tokocrypto_client.get_account)
        # print('accountInfo', account_info)
        account_info_data = account_info["data"]
        # print('account_info_data', account_info_data)
        balances = account_info_data["accountAssets"]
        # print('balances', balances)
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
                res = await self.query_api(self._tokocrypto_client.get_trade_fee)
                for fee in res["tradeFee"]:
                    self._trade_fees[fee["symbol"]] = (Decimal(fee["maker"]), Decimal(fee["taker"]))
                self._last_update_trade_fees_timestamp = current_timestamp
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network("Error fetching tokocrypto trade fees.", exc_info=True,
                                      app_warning_msg=f"Could not fetch tokocrypto trading fees. "
                                                      f"Check network connection.")
                raise

    cdef object c_get_fee(self,
                          str base_currency,
                          str quote_currency,
                          object order_type,
                          object order_side,
                          object amount,
                          object price):
        """
        cdef:
            object maker_trade_fee = Decimal("0.001")
            object taker_trade_fee = Decimal("0.001")
            str trading_pair = base_currency + quote_currency

        if order_type.is_limit_type() and fee_overrides_config_map["binance_maker_fee"].value is not None:
            return TradeFee(percent=fee_overrides_config_map["binance_maker_fee"].value / Decimal("100"))
        if order_type is OrderType.MARKET and fee_overrides_config_map["binance_taker_fee"].value is not None:
            return TradeFee(percent=fee_overrides_config_map["binance_taker_fee"].value / Decimal("100"))

        if trading_pair not in self._trade_fees:
            # https://www.tokocrypto.com/en/fee/schedule
            self.logger().warning(f"Unable to find trade fee for {trading_pair}. Using default 0.1% maker/taker fee.")
        else:
            maker_trade_fee, taker_trade_fee = self._trade_fees.get(trading_pair)
        return TradeFee(percent=maker_trade_fee if order_type.is_limit_type() else taker_trade_fee)
        """
        is_maker = order_type is OrderType.LIMIT_MAKER
        return estimate_fee(self.name, is_maker)

    async def _update_trading_rules(self):
        cdef:
            int64_t last_tick = <int64_t>(self._last_timestamp / 60.0)
            int64_t current_tick = <int64_t>(self._current_timestamp / 60.0)
        # print('_update_trading_rules', {'current_tick' : current_tick, 'last_tick' : last_tick, '_current_trading_rules_len' : len(self._trading_rules)})
        if current_tick > last_tick or len(self._trading_rules) < 1:
            exchange_info = await self.query_api(self._tokocrypto_client.get_exchange_info)
            # self.logger().info(f"exchange_info = {exchange_info}", exc_info=True)
            trading_rules_list = self._format_trading_rules(exchange_info)
            self._trading_rules.clear()
            for trading_rule in trading_rules_list:
                self._trading_rules[convert_from_exchange_trading_pair(trading_rule.trading_pair)] = trading_rule
            # self.logger().info(f"trading_rule = {self._trading_rules}", exc_info=True)

    def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        cdef:
            list trading_pair_rules = exchange_info_dict.get("list", [])
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
            # in case Tokocrypto's user stream events are not working.
            # This is separated from _update_order_status which only updates the order status without producing filled
            # events, since Tokocrypto's get order endpoint does not return trade IDs.
            # The minimum poll interval for order status is 10 seconds.
            int64_t last_tick = <int64_t>(self._last_poll_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL)
            int64_t current_tick = <int64_t>(self._current_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL)

        if current_tick > last_tick and len(self._in_flight_orders) > 0:
            trading_pairs_to_order_map = defaultdict(lambda: {})
            for o in self._in_flight_orders.values():
                trading_pairs_to_order_map[o.trading_pair][o.exchange_order_id] = o

            trading_pairs = list(trading_pairs_to_order_map.keys())
            tasks = [self.query_api(self._tokocrypto_client.get_my_trades, symbol=convert_to_tokocrypto_exchange_trading_pair(trading_pair))
                     for trading_pair in trading_pairs]
            self.logger().debug("Polling for order fills of %d trading pairs.", len(tasks))
            results = await safe_gather(*tasks, return_exceptions=True)
            tradesList = []
            tradesList.append(results[0]["data"]["list"])
            for trades, trading_pair in zip(tradesList, trading_pairs):
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
                        order_type = tracked_order.order_type
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
                                                     exchange_trade_id=trade["tradeId"]
                                                 ))

    async def _update_order_status(self):
        cdef:
            # This is intended to be a backup measure to close straggler orders, in case Tokocrypto's user stream events
            # are not working.
            # The minimum poll interval for order status is 10 seconds.
            int64_t last_tick = <int64_t>(self._last_poll_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL)
            int64_t current_tick = <int64_t>(self._current_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL)

        if current_tick > last_tick and len(self._in_flight_orders) > 0:
            tracked_orders = list(self._in_flight_orders.values())
            tasks = [self.query_api(self._tokocrypto_client.get_order,
                                    symbol=convert_to_tokocrypto_exchange_trading_pair(o.trading_pair), orderId=o.client_order_id)
                     for o in tracked_orders]
            self.logger().debug("Polling for order status updates of %d orders.", len(tasks))
            results = await safe_gather(*tasks, return_exceptions=True)
            orderResult = []
            orderResult.append(results[0]["data"])
            for order_update, tracked_order in zip(orderResult, tracked_orders):
                client_order_id = tracked_order.client_order_id

                # If the order has already been cancelled or has failed do nothing
                if client_order_id not in str(self._in_flight_orders):
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
                tracked_order.last_state = str(order_update["status"])
                order_type = str(order_update["type"])
                executed_amount_base = Decimal(order_update["executedQty"])
                executed_amount_quote = Decimal(order_update["executedQuoteQty"])

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
                self._last_poll_timestamp = self._current_timestamp
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network("Unexpected error while fetching account updates.", exc_info=True,
                                      app_warning_msg="Could not fetch account updates from Tokocrypto. "
                                                      "Check API key and network connection.")
                await asyncio.sleep(0.5)

    async def _trading_rules_polling_loop(self):
        while True:
            try:
                await safe_gather(
                    self._update_trading_rules(),
                )
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network("Unexpected error while fetching trading rules.", exc_info=True,
                                      app_warning_msg="Could not fetch new trading rules from Tokocrypto. "
                                                      "Check network connection.")
                await asyncio.sleep(0.5)

    @property
    def status_dict(self) -> Dict[str, bool]:
        return {
            "order_books_initialized": self._order_book_tracker.ready,
            "account_balance": len(self._account_balances) > 0 if self._trading_required else True,
            "trading_rule_initialized": len(self._trading_rules) > 0,
        }

    @property
    def ready(self) -> bool:
        return all(self.status_dict.values())

    async def server_time(self) -> int:
        """
        :return: The current server time in milliseconds since UNIX epoch.
        """
        result = await self.query_api(self._tokocrypto_client.get_server_time)
        return result["serverTime"]

    cdef c_start(self, Clock clock, double timestamp):
        self._tx_tracker.c_start(clock, timestamp)
        ExchangeBase.c_start(self, clock, timestamp)

    cdef c_stop(self, Clock clock):
        ExchangeBase.c_stop(self, clock)
        self._async_scheduler.stop()

    async def start_network(self):
        self._order_book_tracker.start()
        self._trading_rules_polling_task = safe_ensure_future(self._trading_rules_polling_loop())
        if self._trading_required:
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())

    def _stop_network(self):
        self._order_book_tracker.stop()
        if self._status_polling_task is not None:
            self._status_polling_task.cancel()
        if self._trading_rules_polling_task is not None:
            self._trading_rules_polling_task.cancel()
        self._status_polling_task = None

    async def stop_network(self):
        self._stop_network()

    async def check_network(self) -> NetworkStatus:
        try:
            await self.query_api(self._tokocrypto_client.ping)
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    cdef c_tick(self, double timestamp):
        cdef:
            double now = time.time()
            double poll_interval = self.SHORT_POLL_INTERVAL
            int64_t last_tick = <int64_t>(self._last_timestamp / poll_interval)
            int64_t current_tick = <int64_t>(timestamp / poll_interval)
        ExchangeBase.c_tick(self, timestamp)
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
        return await self.create_order(TradeType.BUY, order_id, trading_pair, amount, order_type, price)

    cdef str c_buy(self, str trading_pair, object amount, object order_type=OrderType.LIMIT, object price=s_decimal_NaN,
                   dict kwargs={}):
        cdef:
            str order_id = get_client_order_id("buy", trading_pair)
        safe_ensure_future(self.execute_buy(order_id, trading_pair, amount, order_type, price))
        return order_id

    @staticmethod
    def tokocrypto_order_type(order_type: OrderType) -> str:
        if order_type is OrderType.MARKET:
            return TokocryptoClient.ORDER_TYPE_MARKET
        else:
            return TokocryptoClient.ORDER_TYPE_LIMIT

    @staticmethod
    def to_hb_order_type(tokocrypto_type: str) -> OrderType:
        return OrderType[tokocrypto_type]

    @staticmethod
    def to_hb_trade_type(tokocrypto_trade_type: str) -> TradeType:
        return TradeType[tokocrypto_trade_type]

    def supported_order_types(self):
        return [OrderType.LIMIT]

    async def create_order(self,
                           trade_type: TradeType,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           order_type: OrderType,
                           price: Optional[Decimal] = Decimal("NaN")):
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]
        amount = self.c_quantize_order_amount(trading_pair, amount)
        price = self.c_quantize_order_price(trading_pair, price)
        if amount < trading_rule.min_order_size:
            raise ValueError(f"Buy order amount {amount} is lower than the minimum order size "
                             f"{trading_rule.min_order_size}.")
        order_result = None
        amount_str = f"{amount:f}"
        price_str = f"{price:f}"
        type_str = TokocryptoExchange.tokocrypto_order_type(order_type)
        side_str = TokocryptoClient.SIDE_BUY if trade_type is TradeType.BUY else TokocryptoClient.SIDE_SELL
        api_params = {"symbol": convert_to_tokocrypto_exchange_trading_pair(trading_pair),
                      "side": side_str,
                      "quantity": amount_str,
                      "type": type_str,
                      "clientId": order_id,
                      "price": price_str}
        try:
            order_result = await self.query_api(self._tokocrypto_client.create_order, **api_params)
            exchange_order_id = str(order_result["data"]["orderId"])
            self.c_start_tracking_order(exchange_order_id,
                                        exchange_order_id,
                                        trading_pair,
                                        trade_type,
                                        price,
                                        amount,
                                        order_type
                                        )
            self.logger().info(f"Created {type_str} {side_str} order {exchange_order_id} for "
                               f"{amount} {trading_pair}.")

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
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.c_stop_tracking_order(order_id)
            self.logger().network(
                f"Error submitting {side_str} {type_str} order to Tokocrypto for "
                f"{amount} {trading_pair} "
                f"{price}.",
                exc_info=True,
                app_warning_msg=str(e)
            )
            self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                 MarketOrderFailureEvent(self._current_timestamp, order_id, order_type))

    async def execute_sell(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           order_type: OrderType,
                           price: Optional[Decimal] = Decimal("NaN")):
        return await self.create_order(TradeType.SELL, order_id, trading_pair, amount, order_type, price)

    cdef str c_sell(self, str trading_pair, object amount, object order_type=OrderType.LIMIT, object price=s_decimal_NaN,
                    dict kwargs={}):
        cdef:
            str order_id = get_client_order_id("sell", trading_pair)
        safe_ensure_future(self.execute_sell(order_id, trading_pair, amount, order_type, price))
        return order_id

    async def execute_cancel(self, trading_pair: str, order_id: str):
        try:
            cancel_result = await self.query_api(self._tokocrypto_client.cancel_order,
                                                 symbol=convert_to_tokocrypto_exchange_trading_pair(trading_pair),
                                                 orderId=order_id)
        except TokocryptoAPIException as e:
            if "Unknown order sent" in e.message or e.code == 2011:
                # The order was never there to begin with. So cancelling it is a no-op but semantically successful.
                self.logger().debug(f"The order {order_id} does not exist on Tokocrypto. No cancellation needed.")
                self.c_stop_tracking_order(order_id)
                self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                     OrderCancelledEvent(self._current_timestamp, order_id))
                return {
                    # Required by cancel_all() below.
                    "orderId": order_id
                }
            else:
                raise e

        if isinstance(cancel_result, dict) and cancel_result["msg"] == "Success":
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
                    if isinstance(cr, TokocryptoAPIException):
                        continue
                    if isinstance(cr, dict) and "orderId" in str(cr):
                        client_order_id = str(cr["data"]["orderId"])
                        order_id_set.remove(client_order_id)
                        successful_cancellations.append(CancellationResult(client_order_id, True))
        except Exception:
            self.logger().network(
                f"Unexpected error cancelling orders.",
                exc_info=True,
                app_warning_msg="Failed to cancel order with Tokocrypto. Check API key and network connection."
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
        self._in_flight_orders[order_id] = TokocryptoInFlightOrder(
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
        quantized_amount = ExchangeBase.c_quantize_order_amount(self, trading_pair, amount)

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

    def get_price(self, trading_pair: str, is_buy: bool) -> Decimal:
        return self.c_get_price(trading_pair, is_buy)

    def buy(self, trading_pair: str, amount: Decimal, order_type=OrderType.MARKET,
            price: Decimal = s_decimal_NaN, **kwargs) -> str:
        return self.c_buy(trading_pair, amount, order_type, price, kwargs)

    def sell(self, trading_pair: str, amount: Decimal, order_type=OrderType.MARKET,
             price: Decimal = s_decimal_NaN, **kwargs) -> str:
        return self.c_sell(trading_pair, amount, order_type, price, kwargs)

    def cancel(self, trading_pair: str, client_order_id: str):
        return self.c_cancel(trading_pair, client_order_id)

    def get_fee(self,
                base_currency: str,
                quote_currency: str,
                order_type: OrderType,
                order_side: TradeType,
                amount: Decimal,
                price: Decimal = s_decimal_NaN) -> TradeFee:
        return self.c_get_fee(base_currency, quote_currency, order_type, order_side, amount, price)

    def get_order_book(self, trading_pair: str) -> OrderBook:
        return self.c_get_order_book(trading_pair)
