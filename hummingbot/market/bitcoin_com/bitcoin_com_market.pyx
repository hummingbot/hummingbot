import aiohttp
import asyncio
import json
import logging
import pandas as pd
import time
import re
import hummingbot.market.bitcoin_com.bitcoin_com_constants as constants

from async_timeout import timeout
from decimal import Decimal
from typing import (
    Any,
    Dict,
    List,
    Optional,
    AsyncIterable,
    Tuple
)
from libc.stdint cimport int64_t
from hummingbot.core.clock cimport Clock
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book_tracker import OrderBookTrackerDataSourceType
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.core.data_type.transaction_tracker import TransactionTracker
from hummingbot.core.event.events import (
    TradeType,
    TradeFee,
    MarketEvent,
    BuyOrderCompletedEvent,
    SellOrderCompletedEvent,
    OrderFilledEvent,
    OrderCancelledEvent,
    BuyOrderCreatedEvent,
    SellOrderCreatedEvent,
    MarketWithdrawAssetEvent,
    MarketTransactionFailureEvent,
    MarketOrderFailureEvent
)
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from hummingbot.logger import HummingbotLogger
from hummingbot.market.bitcoin_com.bitcoin_com_auth import BitcoinComAuth
from hummingbot.market.bitcoin_com.bitcoin_com_order_book_tracker import BitcoinComOrderBookTracker
from hummingbot.market.bitcoin_com.bitcoin_com_user_stream_tracker import BitcoinComUserStreamTracker
from hummingbot.market.bitcoin_com.bitcoin_com_api_order_book_data_source import BitcoinComAPIOrderBookDataSource
from hummingbot.market.deposit_info import DepositInfo
from hummingbot.market.market_base import (
    MarketBase,
    OrderType,
)
from hummingbot.market.trading_rule cimport TradingRule
from hummingbot.market.bitcoin_com.bitcoin_com_in_flight_order import BitcoinComInFlightOrder
from hummingbot.market.bitcoin_com.bitcoin_com_in_flight_order cimport BitcoinComInFlightOrder
from hummingbot.market.bitcoin_com.bitcoin_com_utils import EventTypes, join_paths
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce

s_logger = None
s_decimal_0 = Decimal(0)
s_decimal_nan = Decimal("nan")
TRADING_PAIR_SPLITTER = re.compile(r"^(\w+)(BTC|ETH|USD|USDT|BCH)$")

cdef class BitcoinComMarketTransactionTracker(TransactionTracker):
    cdef:
        BitcoinComMarket _owner

    def __init__(self, owner: BitcoinComMarket):
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


cdef class BitcoinComMarket(MarketBase):
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
    UPDATE_ORDERS_INTERVAL = 10.0

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(__name__)
        return s_logger

    def __init__(self,
                 bitcoin_com_api_key: str,
                 bitcoin_com_secret_key: str,
                 poll_interval: float = 5.0,    # interval which the class periodically pulls status from the rest API
                 order_book_tracker_data_source_type: OrderBookTrackerDataSourceType =
                 OrderBookTrackerDataSourceType.EXCHANGE_API,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True):
        super().__init__()
        self._trading_required = trading_required
        self._bitcoin_com_auth = BitcoinComAuth(bitcoin_com_api_key, bitcoin_com_secret_key)
        self._order_book_tracker = BitcoinComOrderBookTracker(
            data_source_type=order_book_tracker_data_source_type,
            trading_pairs=trading_pairs
        )
        self._user_stream_tracker = BitcoinComUserStreamTracker(
            bitcoin_com_auth=self._bitcoin_com_auth,
            trading_pairs=trading_pairs
        )
        self._ev_loop = asyncio.get_event_loop()
        self._poll_notifier = asyncio.Event()
        self._last_timestamp = 0
        self._last_order_update_timestamp = 0
        self._poll_interval = poll_interval
        self._in_flight_orders = {}
        self._tx_tracker = BitcoinComMarketTransactionTracker(self)
        self._trading_rules = {}
        self._trade_fees = {}  # Dict[trading_pair:str, (maker_fee_percent:Decimal, taken_fee_percent:Decimal)]
        self._withdraw_fees = {}  # Dict[currency:str, (payoutEnabled:bool, payoutFee:Decimal)]
        self._data_source_type = order_book_tracker_data_source_type
        self._status_polling_task = None
        self._order_tracker_task = None
        self._user_stream_tracker_task = None
        self._user_stream_event_listener_task = None
        self._trading_rules_polling_task = None
        self._withdraw_fees_polling_task = None
        self._shared_client = None

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
        if BitcoinComMarket.split_trading_pair(exchange_trading_pair) is None:
            return None
        # exchange does not split BASEQUOTE (BTCUSDT)
        base_asset, quote_asset = BitcoinComMarket.split_trading_pair(exchange_trading_pair)
        return f"{base_asset}-{quote_asset}"

    @staticmethod
    def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
        # exchange does not split BASEQUOTE (BTCUSDT)
        return hb_trading_pair.replace("-", "")

    @property
    def name(self) -> str:
        """
        *required
        :return: A lowercase name / id for the market. Must stay consistent with market name in global settings.
        """
        return constants.EXCHANGE_NAME

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        """
        *required
        Get mapping of all the order books that are being tracked.
        :return: Dict[trading_pair : OrderBook]
        """
        return self._order_book_tracker.order_books

    @property
    def bitcoin_com(self) -> BitcoinComAuth:
        """
        :return: BitcoinComAuth class.
        """
        return self._bitcoin_com_auth

    @property
    def status_dict(self) -> Dict[str, bool]:
        """
        *required
        :return: a dictionary of relevant status checks.
        This is used by `ready` method below to determine if a market is ready for trading.
        """
        return {
            "order_books_initialized": self._order_book_tracker.ready,
            "account_balance": len(self._account_balances) > 0 if self._trading_required else True,
            "trading_rule_initialized": len(self._trading_rules) > 0 if self._trading_required else True,
            "trade_fees_initialized": len(self._trade_fees) > 0 if self._trading_required else True,
            "withdraw_fees_initialized": len(self._withdraw_fees) > 0 if self._trading_required else True
        }

    @property
    def ready(self) -> bool:
        """
        *required
        :return: a boolean value that indicates if the market is ready for trading
        """
        return all(self.status_dict.values())

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
            key: BitcoinComInFlightOrder.from_json(value)
            for key, value in saved_states.items()
        })

    async def get_active_exchange_markets(self) -> pd.DataFrame:
        """
        *required
        Used by the discovery strategy to read order books of all actively trading markets,
        and find opportunities to profit
        """
        return await BitcoinComAPIOrderBookDataSource.get_active_exchange_markets()

    cdef c_start(self, Clock clock, double timestamp):
        """
        *required
        c_start function used by top level Clock to orchestrate components of the bot
        """
        self._tx_tracker.c_start(clock, timestamp)
        MarketBase.c_start(self, clock, timestamp)

    async def start_network(self):
        """
        *required
        Async function used by NetworkBase class to handle when a single market goes online
        """
        if self._order_tracker_task is not None:
            self._stop_network()

        self._order_tracker_task = safe_ensure_future(self._order_book_tracker.start())
        if self._trading_required:
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())
            self._trading_rules_polling_task = safe_ensure_future(self._trading_rules_polling_loop())
            self._withdraw_fees_polling_task = safe_ensure_future(self._withdraw_fees_polling_loop())
            self._user_stream_tracker_task = safe_ensure_future(self._user_stream_tracker.start())
            self._user_stream_event_listener_task = safe_ensure_future(self._user_stream_event_listener())

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

    async def stop_network(self):
        """
        *required
        Async wrapper for `self._stop_network`. Used by NetworkBase class to handle when a single market goes offline.
        """
        self._stop_network()

    async def check_network(self) -> NetworkStatus:
        """
        *required
        Async function used by NetworkBase class to check if the market is online / offline.
        """
        try:
            await self._api_request(
                "get",
                url=join_paths(constants.REST_MARKETS_URL, "ETHBTC")
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    cdef c_tick(self, double timestamp):
        """
        *required
        Used by top level Clock to orchestrate components of the bot.
        This function is called frequently with every clock tick
        """
        cdef:
            int64_t last_tick = <int64_t>(self._last_timestamp / self._poll_interval)
            int64_t current_tick = <int64_t>(timestamp / self._poll_interval)

        MarketBase.c_tick(self, timestamp)
        if current_tick > last_tick:
            if not self._poll_notifier.is_set():
                self._poll_notifier.set()
        self._last_timestamp = timestamp

    async def _http_client(self) -> aiohttp.ClientSession:
        """
        :returns: Shared client session instance
        """
        if self._shared_client is None:
            self._shared_client = aiohttp.ClientSession()
        return self._shared_client

    async def _api_request(self,
                           http_method: str,
                           path_url: str = None,
                           url: str = None,
                           data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        A wrapper for submitting API requests to the exchange
        :returns: json data from the endpoints
        """
        assert path_url is not None or url is not None

        url = f"{constants.REST_URL}{path_url}" if url is None else url
        data_str = "" if data is None else json.dumps(data)
        headers = self.bitcoin_com.get_headers()

        client = await self._http_client()
        async with client.request(http_method,
                                  url=url, timeout=self.API_CALL_TIMEOUT, data=data_str, headers=headers) as response:
            data = await response.json()
            if response.status != 200:
                raise IOError(f"Error fetching data from {url}. HTTP status is {response.status}. {data}")
            return data

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
        # Fee info from https://api.exchange.bitcoin.com/#create-new-order
        cdef:
            object maker_fee = None
            object taker_fee = None
            str trading_pair = base_currency + quote_currency

        if trading_pair not in self._trade_fees:
            raise ValueError(f"Unable to find trade fees for {trading_pair}.")
        else:
            maker_fee, taker_fee = self._trade_fees.get(trading_pair)

        return TradeFee(percent=maker_fee if order_type is OrderType.LIMIT else taker_fee)

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

        account_balances = await self._api_request(
            "get",
            url=constants.REST_BALANCE_URL
        )

        for balance_entry in account_balances:
            asset_name = balance_entry["currency"]
            available_balance = Decimal(balance_entry["available"])
            reserved_balance = Decimal(balance_entry["reserved"])
            total_balance = available_balance + reserved_balance
            self._account_available_balances[asset_name] = available_balance
            self._account_balances[asset_name] = total_balance
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    async def _update_trading_rules(self):
        """
        Pulls the API for trading rules (min / max order size, etc)
        """
        cdef:
            # The poll interval for withdraw rules is 60 seconds.
            int64_t last_tick = <int64_t>(self._last_timestamp / 60.0)
            int64_t current_tick = <int64_t>(self._current_timestamp / 60.0)
        if current_tick > last_tick or len(self._trading_rules) <= 0:
            product_info = await self._api_request(
                "get",
                url=constants.REST_MARKETS_URL
            )
            trading_rules_list = self._format_trading_rules(product_info)
            self._trading_rules.clear()
            for trading_rule in trading_rules_list:
                self._trading_rules[trading_rule.trading_pair] = trading_rule

            # update trade_fees
            self._trade_fees.clear()
            for item in product_info:
                self._trade_fees[item["id"]] = (Decimal(item["provideLiquidityRate"]), Decimal(item["takeLiquidityRate"]))

    def _format_trading_rules(self, raw_trading_rules: List[Any]) -> List[TradingRule]:
        """
        Turns json data from API into TradingRule instances
        :returns: List of TradingRule
        """
        cdef:
            list retval = []
        for rule in raw_trading_rules:
            try:
                # TODO: research more here, max size
                trading_pair = rule.get("id")
                min_order_size = rule.get("quantityIncrement")
                min_price_increment = rule.get("tickSize")

                retval.append(
                    TradingRule(
                        trading_pair=trading_pair,
                        min_order_size=Decimal(min_order_size),
                        min_price_increment=Decimal(min_price_increment),
                        min_base_amount_increment=Decimal(min_price_increment),
                        min_quote_amount_increment=Decimal(min_price_increment)
                    )
                )
            except Exception:
                self.logger().error(f"Error parsing the symbol rule {rule}. Skipping.", exc_info=True)
        return retval

    async def _update_withdraw_fees(self):
        """
        Pulls the API for trading pair status (payoutEnabled, payoutFee)
        """
        cdef:
            # The poll interval for withdraw rules is 60 seconds.
            int64_t last_tick = <int64_t>(self._last_timestamp / 60.0)
            int64_t current_tick = <int64_t>(self._current_timestamp / 60.0)
        if current_tick > last_tick or len(self._withdraw_fees) <= 0:
            product_info = await self._api_request(
                "get",
                url=constants.REST_CURRENCY_URL
            )
            withdraw_withdraw_fees_list = self._format_withdraw_fees(product_info)
            self._withdraw_fees.clear()
            for data in withdraw_withdraw_fees_list:
                self._withdraw_fees[data["currency"]] = (data["payoutEnabled"], data["payoutFee"])

    def _format_withdraw_fees(self, raw_info: List[Any]) -> List[(bool, str)]:
        """
        Turns json data from API into tuple
        :returns: List of tuples
        """
        cdef:
            list retval = []
        for info in raw_info:
            try:
                currency = info.get("id")
                payoutEnabled = info.get("payoutEnabled")
                payoutFee = info.get("payoutFee")

                retval.append({
                    "currency": currency,
                    "payoutEnabled": payoutEnabled,
                    "payoutFee": Decimal(payoutFee)
                })
            except Exception:
                self.logger().error(f"Error parsing the symbol withdraw fee {info}. Skipping.", exc_info=True)
        return retval

    async def _update_order_status(self):
        """
        Pulls the rest API for for latest order statuses and update local order statuses.
        """
        cdef:
            double current_timestamp = self._current_timestamp

        if current_timestamp - self._last_order_update_timestamp <= self.UPDATE_ORDERS_INTERVAL:
            return

        tracked_orders = list(self._in_flight_orders.values())
        results = await self.list_orders()
        order_dict = dict((str(result["id"]), result) for result in results)

        for tracked_order in tracked_orders:
            exchange_order_id = await tracked_order.get_exchange_order_id()
            order_update = order_dict.get(exchange_order_id)

            if order_update is None:
                order_update = await self.get_history_order(tracked_order.client_order_id)

            if order_update is None:
                self.logger().network(
                    f"Error fetching status update for the order {tracked_order.client_order_id}: "
                    f"{order_update}.",
                    app_warning_msg=f"Could not fetch updates for the order {tracked_order.client_order_id}. "
                                    f"Check API key and network connection."
                )
                continue

            done_reason = order_update.get("status")
            # Calculate the newly executed amount for this update.
            new_confirmed_amount = Decimal(order_update["cumQuantity"])
            execute_amount_diff = new_confirmed_amount - tracked_order.executed_amount_base
            execute_price = Decimal(order_update["price"])

            client_order_id = tracked_order.client_order_id
            order_type_description = tracked_order.order_type_description
            order_type = OrderType.MARKET if tracked_order.order_type == OrderType.MARKET else OrderType.LIMIT

            # Emit event if executed amount is greater than 0.
            if execute_amount_diff > s_decimal_0:
                order_filled_event = OrderFilledEvent(
                    self._current_timestamp,
                    tracked_order.client_order_id,
                    tracked_order.trading_pair,
                    tracked_order.trade_type,
                    order_type,
                    execute_price,
                    execute_amount_diff,
                    self.c_get_fee(
                        tracked_order.base_asset,
                        tracked_order.quote_asset,
                        order_type,
                        tracked_order.trade_type,
                        execute_price,
                        execute_amount_diff,
                    ),
                    exchange_trade_id=exchange_order_id,
                )
                self.logger().info(f"Filled {execute_amount_diff} out of {tracked_order.amount} of the "
                                   f"{order_type_description} order {client_order_id}.")
                self.c_trigger_event(self.MARKET_ORDER_FILLED_EVENT_TAG, order_filled_event)

            # Update the tracked order
            tracked_order.last_state = done_reason if done_reason in {"filled", "canceled"} else order_update["status"]
            tracked_order.executed_amount_base = new_confirmed_amount
            tracked_order.executed_amount_quote += execute_amount_diff * execute_price

            if tracked_order.is_done:
                if not tracked_order.is_failure:
                    # TODO: track fee, need to call API
                    # tracked_order.fee_paid = Decimal(order_update["fill_fees"])

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

    async def _user_stream_event_listener(self):
        """
        Update order statuses from incoming messages from the user stream
        """
        async for event_message in self._iter_user_event_queue():
            try:
                content = event_message.content
                event_type = content["event_type"]

                # at the moment we only handle order events
                if (event_type is not EventTypes.ActiveOrdersUpdate):
                    continue

                tracked_order = None

                for order in self._in_flight_orders.values():
                    if order.exchange_order_id == content["id"]:
                        tracked_order = order
                        break

                if tracked_order is None:
                    continue

                order_type_description = tracked_order.order_type_description
                tracked_order.last_state = content["status"]
                execute_price = s_decimal_0
                execute_amount_diff = s_decimal_0

                if content["reportType"] == "trade":
                    execute_price = Decimal(content["tradePrice"])
                    execute_amount_diff = Decimal(content["tradeQuantity"])
                    tracked_order.executed_amount_base += execute_amount_diff
                    tracked_order.executed_amount_quote += execute_amount_diff * execute_price

                elif content["reportType"] == "replaced":
                    tracked_order.amount = Decimal(content["quantity"])
                    tracked_order.price = Decimal(content["price"])

                if execute_amount_diff > s_decimal_0:
                    self.logger().info(f"Filled {execute_amount_diff} out of {tracked_order.amount} of the "
                                       f"{order_type_description} order {tracked_order.client_order_id}")
                    self.c_trigger_event(self.MARKET_ORDER_FILLED_EVENT_TAG,
                                         OrderFilledEvent(
                                             self._current_timestamp,
                                             tracked_order.client_order_id,
                                             tracked_order.trading_pair,
                                             tracked_order.trade_type,
                                             tracked_order.order_type,
                                             execute_price,
                                             execute_amount_diff,
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

                if content["status"] == "filled":
                    if tracked_order.trade_type == TradeType.BUY:
                        self.logger().info(f"The market buy order {tracked_order.client_order_id} has completed "
                                           f"according to Bitcoin.com user stream.")
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
                                           f"according to Bitcoin.com user stream.")
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
                elif content["status"] in ["suspended", "canceled", "expired"]:
                    execute_amount_diff = 0
                    tracked_order.last_state = "canceled"
                    self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                         OrderCancelledEvent(self._current_timestamp, tracked_order.client_order_id))
                    execute_amount_diff = 0
                    self.c_stop_tracking_order(tracked_order.client_order_id)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await asyncio.sleep(5.0)

    async def place_order(self, client_order_id: str, trading_pair: str, amount: Decimal, is_buy: bool, order_type: OrderType,
                          price: Decimal):
        """
        Async wrapper for placing orders through the rest API.
        :returns: json response from the API
        """
        path_url = "/order"
        data = {
            "symbol": trading_pair,
            "clientOrderId": client_order_id,
            "side": "buy" if is_buy else "sell",
            "type": "limit" if order_type is OrderType.LIMIT else "market",
            "quantity": float(amount),
        }

        if (order_type is OrderType.LIMIT):
            data["price"] = float(price)

        order_result = await self._api_request("post", path_url=path_url, data=data)
        return order_result

    async def execute_buy(self,
                          client_order_id: str,
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
            raise ValueError(f"Buy order amount {decimal_amount} is lower than the minimum order size "
                             f"{trading_rule.min_order_size}.")

        try:
            self.c_start_tracking_order(client_order_id, trading_pair, order_type, TradeType.BUY, decimal_price, decimal_amount)
            order_result = await self.place_order(client_order_id, trading_pair, decimal_amount, True, order_type, decimal_price)

            exchange_order_id = str(order_result["id"])
            tracked_order = self._in_flight_orders.get(client_order_id)
            if tracked_order is not None:
                self.logger().info(f"Created {order_type} buy order {client_order_id} for {decimal_amount} {trading_pair}.")
                tracked_order.update_exchange_order_id(exchange_order_id)

            self.c_trigger_event(self.MARKET_BUY_ORDER_CREATED_EVENT_TAG,
                                 BuyOrderCreatedEvent(self._current_timestamp,
                                                      order_type,
                                                      trading_pair,
                                                      decimal_amount,
                                                      decimal_price,
                                                      client_order_id))
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.c_stop_tracking_order(client_order_id)
            order_type_str = "MARKET" if order_type == OrderType.MARKET else "LIMIT"
            self.logger().network(
                f"Error submitting buy {order_type_str} order to Bitcoin.com for "
                f"{decimal_amount} {trading_pair} {price}.",
                exc_info=True,
                app_warning_msg="Failed to submit buy order to Bitcoin.com. "
                                "Check API key and network connection."
            )
            self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                 MarketOrderFailureEvent(self._current_timestamp, client_order_id, order_type))

    cdef str c_buy(self, str trading_pair, object amount, object order_type=OrderType.MARKET, object price=s_decimal_0,
                   dict kwargs={}):
        """
        *required
        Synchronous wrapper that generates a client-side order ID and schedules the buy order.
        """
        cdef:
            int64_t tracking_nonce = <int64_t> get_tracking_nonce()
            str client_order_id = str(f"buy-{trading_pair}-{tracking_nonce}")

        safe_ensure_future(self.execute_buy(client_order_id, trading_pair, amount, order_type, price))
        return client_order_id

    async def execute_sell(self,
                           client_order_id: str,
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

        decimal_amount = self.quantize_order_amount(trading_pair, amount)
        decimal_price = self.quantize_order_price(trading_pair, price)
        if decimal_amount < trading_rule.min_order_size:
            raise ValueError(f"Sell order amount {decimal_amount} is lower than the minimum order size "
                             f"{trading_rule.min_order_size}.")

        try:
            self.c_start_tracking_order(client_order_id, trading_pair, order_type, TradeType.SELL, decimal_price, decimal_amount)
            order_result = await self.place_order(client_order_id, trading_pair, decimal_amount, False, order_type, decimal_price)

            exchange_order_id = str(order_result["id"])
            tracked_order = self._in_flight_orders.get(client_order_id)
            if tracked_order is not None:
                self.logger().info(f"Created {order_type} sell order {client_order_id} for {decimal_amount} {trading_pair}.")
                tracked_order.update_exchange_order_id(exchange_order_id)

            self.c_trigger_event(self.MARKET_SELL_ORDER_CREATED_EVENT_TAG,
                                 SellOrderCreatedEvent(self._current_timestamp,
                                                       order_type,
                                                       trading_pair,
                                                       decimal_amount,
                                                       decimal_price,
                                                       client_order_id))
        except asyncio.CancelledError:
            raise
        except Exception:
            self.c_stop_tracking_order(client_order_id)
            order_type_str = "MARKET" if order_type == OrderType.MARKET else "LIMIT"
            self.logger().network(
                f"Error submitting sell {order_type_str} order to Bitcoin.com for "
                f"{decimal_amount} {trading_pair} {price}.",
                exc_info=True,
                app_warning_msg="Failed to submit sell order to Bitcoin.com. "
                                "Check API key and network connection."
            )
            self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                 MarketOrderFailureEvent(self._current_timestamp, client_order_id, order_type))

    cdef str c_sell(self, str trading_pair, object amount, object order_type=OrderType.MARKET, object price=s_decimal_0,
                    dict kwargs={}):
        """
        *required
        Synchronous wrapper that generates a client-side order ID and schedules the sell order.
        """
        cdef:
            int64_t tracking_nonce = <int64_t> get_tracking_nonce()
            str client_order_id = str(f"sell-{trading_pair}-{tracking_nonce}")
        safe_ensure_future(self.execute_sell(client_order_id, trading_pair, amount, order_type, price))
        return client_order_id

    async def execute_cancel(self, trading_pair: str, client_order_id: str):
        """
        Function that makes API request to cancel an active order
        """
        try:
            path_url = f"/order/{client_order_id}"
            order = await self._api_request("delete", path_url=path_url)
            if order["clientOrderId"] == client_order_id:
                self.logger().info(f"Successfully cancelled order {client_order_id}.")
                self.c_stop_tracking_order(client_order_id)
                self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                     OrderCancelledEvent(self._current_timestamp, client_order_id))
                return client_order_id
        except IOError as e:
            if "order not found" in e.message:
                # The order was never there to begin with. So cancelling it is a no-op but semantically successful.
                self.logger().info(f"The order {client_order_id} does not exist on Bitcoin.com. No cancellation needed.")
                self.c_stop_tracking_order(client_order_id)
                self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                     OrderCancelledEvent(self._current_timestamp, client_order_id))
                return client_order_id
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(
                f"Failed to cancel order {client_order_id}: {str(e)}",
                exc_info=True,
                app_warning_msg=f"Failed to cancel the order {client_order_id} on Bitcoin.com. "
                                f"Check API key and network connection."
            )
        return None

    cdef c_cancel(self, str trading_pair, str client_order_id):
        """
        *required
        Synchronous wrapper that schedules cancelling an order.
        """
        safe_ensure_future(self.execute_cancel(trading_pair, client_order_id))
        return client_order_id

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        """
        *required
        Async function that cancels all active orders.
        Used by bot's top level stop and exit commands (cancelling outstanding orders on exit)
        :returns: List of CancellationResult which indicates whether each order is successfully cancelled.
        """
        incomplete_orders = [o for o in self._in_flight_orders.values() if not o.is_done]
        tasks = [self.execute_cancel(o.trading_pair, o.client_order_id) for o in incomplete_orders]
        order_id_set = set([o.client_order_id for o in incomplete_orders])
        successful_cancellations = []

        try:
            async with timeout(timeout_seconds):
                results = await safe_gather(*tasks, return_exceptions=True)
                for client_order_id in results:
                    if type(client_order_id) is str:
                        order_id_set.remove(client_order_id)
                        successful_cancellations.append(CancellationResult(client_order_id, True))
        except Exception:
            self.logger().network(
                f"Unexpected error cancelling orders.",
                exc_info=True,
                app_warning_msg="Failed to cancel order on Bitcoin.com. Check API key and network connection."
            )

        failed_cancellations = [CancellationResult(oid, False) for oid in order_id_set]
        return successful_cancellations + failed_cancellations

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
                    self._update_order_status(),
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unexpected error while fetching account updates.",
                    exc_info=True,
                    app_warning_msg=f"Could not fetch account updates on Bitcoin.com. "
                                    f"Check API key and network connection."
                )

    async def _withdraw_fees_polling_loop(self):
        """
        Separate background process that periodically pulls for withdraw fees changes
        (Since withdraw fees don't get updated often, it is pulled less often.)
        """
        while True:
            try:
                await safe_gather(self._update_withdraw_fees())
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unexpected error while fetching withdraw fees.",
                    exc_info=True,
                    app_warning_msg=f"Could not fetch withdraw fees updates on Bitcoin.com. "
                                    f"Check network connection."
                )
                await asyncio.sleep(0.5)

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
                    app_warning_msg=f"Could not fetch trading rule updates on Bitcoin.com. "
                                    f"Check network connection."
                )
                await asyncio.sleep(0.5)

    async def get_order(self, client_order_id: str) -> Dict[str, Any]:
        """
        Gets status update for a particular order via rest API
        :returns: json response
        """
        order = self._in_flight_orders.get(client_order_id)
        exchange_order_id = await order.get_exchange_order_id()
        path_url = f"/order/{exchange_order_id}"
        result = await self._api_request("get", path_url=path_url)
        return result

    async def get_history_order(self, client_order_id: str) -> Dict[str, Any]:
        """
        Gets status update for a particular order via rest API
        :returns: json response
        """
        path_url = f"/history/order/?clientOrderId={client_order_id}"
        result = await self._api_request("get", path_url=path_url)

        if (len(result) == 0):
            return None

        return result[0]

    async def list_orders(self) -> List[Any]:
        """
        Gets a list of the user's active orders via rest API
        :returns: json response
        """
        path_url = "/order"
        result = await self._api_request("get", path_url=path_url)
        return result

    async def get_account_balances(self) -> Dict[str, Any]:
        """
        Gets a dict of the user's account balance, this is different
        from '_update_balances' which queries the trading balance.
        :returns: Dict keyed by currency
        """
        path_url = "/account/balance"
        result = await self._api_request("get", path_url=path_url)
        balances: Dict[str, Any] = {item["currency"]: item for item in result}

        return balances

    async def get_transfers(self) -> Dict[str, Any]:
        """
        Gets a list of the user's transfers via rest API
        :returns: json response
        """
        path_url = "/account/transactions"
        result = await self._api_request("get", path_url=path_url)
        return result

    async def get_deposit_address(self, asset: str) -> str:
        """
        Gets a list of the user's crypto address for a particular asset,
        so that the bot can deposit funds into Bitcoin.com
        :returns: json response
        """
        path_url = f"/account/crypto/address/{asset}"
        deposit_result = await self._api_request("get", path_url=path_url)
        return deposit_result.get("address")

    async def get_deposit_info(self, asset: str) -> DepositInfo:
        """
        Calls `self.get_deposit_address` and format the response into a DepositInfo instance
        :returns: a DepositInfo instance
        """
        return DepositInfo(await self.get_deposit_address(asset))

    async def execute_withdraw(self, str tracking_id, str to_address, str currency, object amount):
        """
        Function that makes API request to withdraw funds
        """
        try:
            if self._withdraw_fees[currency] is None:
                raise ValueError(f"Currency's {currency} withdraw fee data does not exist")

            payoutEnabled, payoutFee = self._withdraw_fees[currency]

            if payoutEnabled is False:
                raise ValueError(f"Withdrawl for currency {currency} is not enabled")

            account_balances = await self.get_account_balances()
            available_balance = Decimal(account_balances[currency]["available"])
            required_balance = amount + payoutFee

            if required_balance > available_balance:
                raise ValueError(f"Withdrawl for currency {currency} requires atleast {required_balance} {currency}")

            path_url = "/account/crypto/withdraw"
            data = {
                "amount": float(amount),
                "currency": currency,
                "address": to_address
            }

            withdraw_result = await self._api_request("post", path_url=path_url, data=data)
            self.logger().info(f"Successfully withdrew {amount} of {currency}. {withdraw_result}")
            withdraw_fee = payoutFee
            self.c_trigger_event(self.MARKET_WITHDRAW_ASSET_EVENT_TAG,
                                 MarketWithdrawAssetEvent(self._current_timestamp, tracking_id, to_address, currency,
                                                          amount, withdraw_fee))
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(
                f"Error sending withdraw request to Bitcoin.com for {currency}.",
                exc_info=True,
                app_warning_msg=f"Failed to issue withdrawal request for {currency} from Bitcoin.com. "
                                f"Check API key and network connection."
            )
            self.c_trigger_event(self.MARKET_TRANSACTION_FAILURE_EVENT_TAG,
                                 MarketTransactionFailureEvent(self._current_timestamp, tracking_id))

    cdef str c_withdraw(self, str to_address, str currency, object amount):
        """
        *required
        Synchronous wrapper that schedules a withdrawal.
        """
        cdef:
            int64_t tracking_nonce = <int64_t> get_tracking_nonce()
            str tracking_id = str(f"withdraw://{currency}/{tracking_nonce}")
        safe_ensure_future(self.execute_withdraw(tracking_id, to_address, currency, amount))
        return tracking_id

    cdef OrderBook c_get_order_book(self, str trading_pair):
        """
        :returns: OrderBook for a specific trading pair
        """
        cdef:
            dict order_books = self._order_book_tracker.order_books

        if trading_pair not in order_books:
            raise ValueError(f"No order book exists for '{trading_pair}'.")
        return order_books[trading_pair]

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
        self._in_flight_orders[client_order_id] = BitcoinComInFlightOrder(
            client_order_id,
            None,
            trading_pair,
            order_type,
            trade_type,
            price,
            amount,
        )

    cdef c_stop_tracking_order(self, str client_order_id):
        """
        Delete an order from self._in_flight_orders mapping
        """
        if client_order_id in self._in_flight_orders:
            del self._in_flight_orders[client_order_id]

    cdef c_did_timeout_tx(self, str tracking_id):
        """
        Triggers MarketEvent.TransactionFailure when an Ethereum transaction has timed out
        """
        self.c_trigger_event(self.MARKET_TRANSACTION_FAILURE_EVENT_TAG,
                             MarketTransactionFailureEvent(self._current_timestamp, tracking_id))

    cdef object c_get_order_price_quantum(self, str trading_pair, object price):
        """
        *required
        Get the minimum increment interval for price
        :return: Min order price increment in Decimal format
        """
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]
        return trading_rule.min_price_increment

    cdef object c_get_order_size_quantum(self, str trading_pair, object order_size):
        """
        *required
        Get the minimum increment interval for order size (e.g. 0.01 USD)
        :return: Min order size increment in Decimal format
        """
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]

        # Bitcoin.com is using the min_order_size as max_precision
        # Order size must be a multiple of the min_order_size
        return trading_rule.min_order_size

    cdef object c_quantize_order_amount(self, str trading_pair, object amount, object price=s_decimal_0):
        """
        *required
        Check current order amount against trading rule, and correct any rule violations
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
