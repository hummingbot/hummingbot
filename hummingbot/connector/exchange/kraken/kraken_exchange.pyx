from libc.stdint cimport int64_t, int32_t
import aiohttp
import asyncio
from async_timeout import timeout
from decimal import Decimal
import logging
import pandas as pd
from collections import defaultdict
import re
from typing import (
    Any,
    Dict,
    List,
    AsyncIterable,
    Optional,
)
from hummingbot.core.utils.asyncio_throttle import Throttler
import copy
from hummingbot.core.utils.async_call_scheduler import AsyncCallScheduler
from hummingbot.core.clock cimport Clock
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from hummingbot.connector.exchange.kraken.kraken_api_order_book_data_source import KrakenAPIOrderBookDataSource
from hummingbot.connector.exchange.kraken.kraken_auth import KrakenAuth
from hummingbot.connector.exchange.kraken.kraken_utils import (
    convert_from_exchange_symbol,
    convert_from_exchange_trading_pair,
    convert_to_exchange_trading_pair,
    split_to_base_quote,
    is_dark_pool)
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
from hummingbot.connector.exchange.kraken.kraken_order_book_tracker import KrakenOrderBookTracker
from hummingbot.connector.exchange.kraken.kraken_user_stream_tracker import KrakenUserStreamTracker
from hummingbot.connector.exchange.kraken.kraken_in_flight_order import KrakenInFlightOrder
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.transaction_tracker import TransactionTracker
from hummingbot.connector.trading_rule cimport TradingRule
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce
from hummingbot.core.utils.estimate_fee import estimate_fee

s_logger = None
s_decimal_0 = Decimal(0)
s_decimal_NaN = Decimal("NaN")
KRAKEN_ROOT_API = "https://api.kraken.com"
ADD_ORDER_URI = "/0/private/AddOrder"
CANCEL_ORDER_URI = "/0/private/CancelOrder"
BALANCE_URI = "/0/private/Balance"
OPEN_ORDERS_URI = "/0/private/OpenOrders"
QUERY_ORDERS_URI = "/0/private/QueryOrders"
ASSET_PAIRS_URI = "https://api.kraken.com/0/public/AssetPairs"
TIME_URL = "https://api.kraken.com/0/public/Time"


cdef class KrakenExchangeTransactionTracker(TransactionTracker):
    cdef:
        KrakenExchange _owner

    def __init__(self, owner: KrakenExchange):
        super().__init__()
        self._owner = owner

    cdef c_did_timeout_tx(self, str tx_id):
        TransactionTracker.c_did_timeout_tx(self, tx_id)
        self._owner.c_did_timeout_tx(tx_id)


cdef class KrakenExchange(ExchangeBase):
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
    KRAKEN_TRADE_TOPIC_NAME = "kraken-trade.serialized"
    KRAKEN_USER_STREAM_TOPIC_NAME = "kraken-user-stream.serialized"

    ORDER_NOT_EXIST_CONFIRMATION_COUNT = 3

    API_MAX_COUNTER = 20
    API_COUNTER_DECREASE_RATE_PER_SEC = 0.33
    API_COUNTER_POINTS = {ADD_ORDER_URI: 0,
                          CANCEL_ORDER_URI: 0,
                          BALANCE_URI: 1,
                          OPEN_ORDERS_URI: 1,
                          QUERY_ORDERS_URI: 1}

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(__name__)
        return s_logger

    def __init__(self,
                 kraken_api_key: str,
                 kraken_secret_key: str,
                 poll_interval: float = 10.0,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True):

        super().__init__()
        self._trading_required = trading_required
        self._order_book_tracker = KrakenOrderBookTracker(trading_pairs=trading_pairs)
        self._kraken_auth = KrakenAuth(kraken_api_key, kraken_secret_key)
        self._user_stream_tracker = KrakenUserStreamTracker(kraken_auth=self._kraken_auth)
        self._ev_loop = asyncio.get_event_loop()
        self._poll_notifier = asyncio.Event()
        self._last_timestamp = 0
        self._poll_interval = poll_interval
        self._in_flight_orders = {}  # Dict[client_order_id:str, KrakenInFlightOrder]
        self._order_not_found_records = {}  # Dict[client_order_id:str, count:int]
        self._tx_tracker = KrakenExchangeTransactionTracker(self)
        self._trading_rules = {}  # Dict[trading_pair:str, TradingRule]
        self._trade_fees = {}  # Dict[trading_pair:str, (maker_fee_percent:Decimal, taken_fee_percent:Decimal)]
        self._last_update_trade_fees_timestamp = 0
        self._status_polling_task = None
        self._user_stream_tracker_task = None
        self._user_stream_event_listener_task = None
        self._trading_rules_polling_task = None
        self._async_scheduler = AsyncCallScheduler(call_interval=0.5)
        self._throttler = Throttler(rate_limit=(self.API_MAX_COUNTER, self.API_MAX_COUNTER/self.API_COUNTER_DECREASE_RATE_PER_SEC),
                                    retry_interval=1.0/self.API_COUNTER_DECREASE_RATE_PER_SEC)
        self._last_pull_timestamp = 0
        self._shared_client = None
        self._asset_pairs = {}
        self._last_userref = 0
        self._real_time_balance_update = False

    @property
    def name(self) -> str:
        return "kraken"

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        return self._order_book_tracker.order_books

    @property
    def kraken_auth(self) -> KrakenAuth:
        return self._kraken_auth

    @property
    def trading_rules(self) -> Dict[str, TradingRule]:
        return self._trading_rules

    @property
    def in_flight_orders(self) -> Dict[str, KrakenInFlightOrder]:
        return self._in_flight_orders

    @property
    def limit_orders(self) -> List[LimitOrder]:
        return [
            in_flight_order.to_limit_order()
            for in_flight_order in self._in_flight_orders.values()
        ]

    @property
    def tracking_states(self) -> Dict[str, Any]:
        return {
            order_id: value.to_json()
            for order_id, value in self._in_flight_orders.items()
        }

    def restore_tracking_states(self, saved_states: Dict[str, Any]):
        in_flight_orders: Dict[str, KrakenInFlightOrder] = {}
        for key, value in saved_states.items():
            in_flight_orders[key] = KrakenInFlightOrder.from_json(value)
            self._last_userref = max(int(value["userref"]), self._last_userref)
        self._in_flight_orders.update(in_flight_orders)

    async def asset_pairs(self) -> Dict[str, Any]:
        if not self._asset_pairs:
            client = await self._http_client()
            asset_pairs_response = await client.get(ASSET_PAIRS_URI)
            asset_pairs_data: Dict[str, Any] = await asset_pairs_response.json()
            asset_pairs: Dict[str, Any] = asset_pairs_data["result"]
            self._asset_pairs = {f"{details['base']}-{details['quote']}": details
                                 for _, details in asset_pairs.items() if not is_dark_pool(details)}
        return self._asset_pairs

    async def get_active_exchange_markets(self) -> pd.DataFrame:
        return await KrakenAPIOrderBookDataSource.get_active_exchange_markets()

    async def _update_balances(self):
        cdef:
            dict open_orders
            dict balances
            str asset_name
            str balance
            str base
            str quote
            set local_asset_names = set(self._account_balances.keys())
            set remote_asset_names = set()
            set asset_names_to_remove

        balances = await self._api_request_with_retry("POST", BALANCE_URI, is_auth_required=True)
        open_orders = await self._api_request_with_retry("POST", OPEN_ORDERS_URI, is_auth_required=True)

        locked = defaultdict(Decimal)

        for order in open_orders.get("open").values():
            if order.get("status") == "open":
                details = order.get("descr")
                if details.get("ordertype") == "limit":
                    pair = convert_from_exchange_trading_pair(details.get("pair"), tuple((await self.asset_pairs()).keys()))
                    (base, quote) = self.split_trading_pair(pair)
                    vol_locked = Decimal(order.get("vol", 0)) - Decimal(order.get("vol_exec", 0))
                    if details.get("type") == "sell":
                        locked[convert_from_exchange_symbol(base)] += vol_locked
                    elif details.get("type") == "buy":
                        locked[convert_from_exchange_symbol(quote)] += vol_locked * Decimal(details.get("price"))

        for asset_name, balance in balances.items():
            cleaned_name = convert_from_exchange_symbol(asset_name).upper()
            total_balance = Decimal(balance)
            free_balance = total_balance - Decimal(locked[cleaned_name])
            self._account_available_balances[cleaned_name] = free_balance
            self._account_balances[cleaned_name] = total_balance
            remote_asset_names.add(cleaned_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

        self._in_flight_orders_snapshot = {k: copy.copy(v) for k, v in self._in_flight_orders.items()}
        self._in_flight_orders_snapshot_timestamp = self._current_timestamp

    cdef object c_get_fee(self,
                          str base_currency,
                          str quote_currency,
                          object order_type,
                          object order_side,
                          object amount,
                          object price):
        """
        cdef:
            object maker_trade_fee = Decimal("0.0016")
            object taker_trade_fee = Decimal("0.0026")
            str trading_pair = base_currency + quote_currency

        if order_type is OrderType.LIMIT and fee_overrides_config_map["kraken_maker_fee"].value is not None:
            return TradeFee(percent=fee_overrides_config_map["kraken_maker_fee"].value / Decimal("100"))
        if order_type is OrderType.MARKET and fee_overrides_config_map["kraken_taker_fee"].value is not None:
            return TradeFee(percent=fee_overrides_config_map["kraken_taker_fee"].value / Decimal("100"))

        if trading_pair in self._trade_fees:
            maker_trade_fee, taker_trade_fee = self._trade_fees.get(trading_pair)
        return TradeFee(percent=maker_trade_fee if order_type is OrderType.LIMIT else taker_trade_fee)
        """
        is_maker = order_type is OrderType.LIMIT_MAKER
        return estimate_fee("kraken", is_maker)

    async def _update_trading_rules(self):
        cdef:
            # The poll interval for withdraw rules is 60 seconds.
            int64_t last_tick = <int64_t>(self._last_timestamp / 60.0)
            int64_t current_tick = <int64_t>(self._current_timestamp / 60.0)
        if current_tick > last_tick or len(self._trading_rules) < 1:
            asset_pairs = await self.asset_pairs()
            trading_rules_list = self._format_trading_rules(asset_pairs)
            self._trading_rules.clear()
            for trading_rule in trading_rules_list:
                self._trading_rules[convert_from_exchange_trading_pair(trading_rule.trading_pair)] = trading_rule

    def _format_trading_rules(self, asset_pairs_dict: Dict[str, Any]) -> List[TradingRule]:
        """
        Example:
        {
            "XBTUSDT": {
              "altname": "XBTUSDT",
              "wsname": "XBT/USDT",
              "aclass_base": "currency",
              "base": "XXBT",
              "aclass_quote": "currency",
              "quote": "USDT",
              "lot": "unit",
              "pair_decimals": 1,
              "lot_decimals": 8,
              "lot_multiplier": 1,
              "leverage_buy": [2, 3],
              "leverage_sell": [2, 3],
              "fees": [
                [0, 0.26],
                [50000, 0.24],
                [100000, 0.22],
                [250000, 0.2],
                [500000, 0.18],
                [1000000, 0.16],
                [2500000, 0.14],
                [5000000, 0.12],
                [10000000, 0.1]
              ],
              "fees_maker": [
                [0, 0.16],
                [50000, 0.14],
                [100000, 0.12],
                [250000, 0.1],
                [500000, 0.08],
                [1000000, 0.06],
                [2500000, 0.04],
                [5000000, 0.02],
                [10000000, 0]
              ],
              "fee_volume_currency": "ZUSD",
              "margin_call": 80,
              "margin_stop": 40,
              "ordermin": "0.0002"
            }
        }
        """
        cdef:
            list retval = []
        for trading_pair, rule in asset_pairs_dict.items():
            try:
                base, quote = split_to_base_quote(trading_pair)
                base = convert_from_exchange_symbol(base)
                min_order_size = Decimal(rule.get('ordermin', 0))
                min_price_increment = Decimal(f"1e-{rule.get('pair_decimals')}")
                min_base_amount_increment = Decimal(f"1e-{rule.get('lot_decimals')}")
                retval.append(
                    TradingRule(
                        trading_pair,
                        min_order_size=min_order_size,
                        min_price_increment=min_price_increment,
                        min_base_amount_increment=min_base_amount_increment,
                    )
                )
            except Exception:
                self.logger().error(f"Error parsing the trading pair rule {rule}. Skipping.", exc_info=True)
        return retval

    async def _update_order_status(self):
        cdef:
            # This is intended to be a backup measure to close straggler orders, in case Kraken's user stream events
            # are not working.
            # The poll interval for order status is 10 seconds.
            int64_t last_tick = <int64_t>(self._last_pull_timestamp / 10.0)
            int64_t current_tick = <int64_t>(self._current_timestamp / 10.0)

        if len(self._in_flight_orders) > 0:
            tracked_orders = list(self._in_flight_orders.values())
            tasks = [self._api_request_with_retry("POST",
                                                  QUERY_ORDERS_URI,
                                                  data={"txid": o.exchange_order_id},
                                                  is_auth_required=True)
                     for o in tracked_orders]
            results = await safe_gather(*tasks, return_exceptions=True)

            for order_update, tracked_order in zip(results, tracked_orders):
                client_order_id = tracked_order.client_order_id

                # If the order has already been cancelled or has failed do nothing
                if client_order_id not in self._in_flight_orders:
                    continue

                if isinstance(order_update, Exception):
                    self.logger().network(
                        f"Error fetching status update for the order {client_order_id}: {order_update}.",
                        app_warning_msg=f"Failed to fetch status update for the order {client_order_id}."
                    )
                    continue

                if order_update.get("error") is not None and "EOrder:Invalid order" not in order_update["error"]:
                    self.logger().debug(f"Error in fetched status update for order {client_order_id}: "
                                        f"{order_update['error']}")
                    self.c_cancel(tracked_order.trading_pair, tracked_order.client_order_id)
                    continue

                update = order_update.get(tracked_order.exchange_order_id)

                if not update:
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
                    continue

                # Update order execution status
                tracked_order.last_state = update["status"]
                executed_amount_base = Decimal(update["vol_exec"])
                executed_amount_quote = executed_amount_base * Decimal(update["price"])

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
                                                                         or tracked_order.quote_asset),
                                                                        executed_amount_base,
                                                                        executed_amount_quote,
                                                                        update["fee"],
                                                                        tracked_order.order_type))
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
                                                                         update["fee"],
                                                                         tracked_order.order_type))
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
                                                     tracked_order.order_type
                                                 ))
                    self.c_stop_tracking_order(client_order_id)

    async def _iter_user_event_queue(self) -> AsyncIterable[Dict[str, Any]]:
        while True:
            try:
                yield await self._user_stream_tracker.user_stream.get()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unknown error. Retrying after 1 seconds.",
                    exc_info=True,
                    app_warning_msg="Could not fetch user events from Kraken. Check API key and network connection."
                )
                await asyncio.sleep(1.0)

    async def _user_stream_event_listener(self):
        async for event_message in self._iter_user_event_queue():
            try:
                # Event type is second from last, there is newly added sequence number (last item).
                # https://docs.kraken.com/websockets/#sequence-numbers
                event_type: str = event_message[-2]
                updates: List[Any] = event_message[0]
                if event_type == "ownTrades":
                    for update in updates:
                        trade_id: str = next(iter(update))
                        trade: Dict[str, str] = update[trade_id]
                        trade["trade_id"] = trade_id
                        exchange_order_id = trade.get("ordertxid")
                        try:
                            client_order_id = next(key for key, value in self._in_flight_orders.items()
                                                   if value.exchange_order_id == exchange_order_id)
                        except StopIteration:
                            continue

                        tracked_order = self._in_flight_orders.get(client_order_id)

                        if tracked_order is None:
                            # Hiding the messages for now. Root cause to be investigated in later sprints.
                            self.logger().debug(f"Unrecognized order ID from user stream: {client_order_id}.")
                            self.logger().debug(f"Event: {event_message}")
                            self.logger().debug(f"Order Event: {update}")
                            continue

                        tracked_order.update_with_trade_update(trade)

                        self.c_trigger_event(self.MARKET_ORDER_FILLED_EVENT_TAG,
                                             OrderFilledEvent(self._current_timestamp,
                                                              tracked_order.client_order_id,
                                                              tracked_order.trading_pair,
                                                              tracked_order.trade_type,
                                                              tracked_order.order_type,
                                                              Decimal(trade.get("price")),
                                                              Decimal(trade.get("vol")),
                                                              self.c_get_fee(
                                                                  tracked_order.base_asset,
                                                                  tracked_order.quote_asset,
                                                                  tracked_order.order_type,
                                                                  tracked_order.trade_type,
                                                                  float(Decimal(trade.get("price"))),
                                                                  float(Decimal(trade.get("vol")))),
                                                              trade.get("trade_id")))

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
                                                                                 or tracked_order.quote_asset),
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
                    self._update_order_status(),
                )
                self._last_pull_timestamp = self._current_timestamp
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network("Unexpected error while fetching account updates.", exc_info=True,
                                      app_warning_msg="Could not fetch account updates from Kraken. "
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
                                      app_warning_msg="Could not fetch new trading rules from Kraken. "
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

    cdef c_start(self, Clock clock, double timestamp):
        self._tx_tracker.c_start(clock, timestamp)
        ExchangeBase.c_start(self, clock, timestamp)

    cdef c_stop(self, Clock clock):
        ExchangeBase.c_stop(self, clock)
        self._async_scheduler.stop()

    async def start_network(self):
        self._stop_network()
        self._order_book_tracker.start()
        self._trading_rules_polling_task = safe_ensure_future(self._trading_rules_polling_loop())
        if self._trading_required:
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())
            self._user_stream_tracker_task = safe_ensure_future(self._user_stream_tracker.start())
            self._user_stream_event_listener_task = safe_ensure_future(self._user_stream_event_listener())

    def _stop_network(self):
        self._order_book_tracker.stop()
        if self._status_polling_task is not None:
            self._status_polling_task.cancel()
        if self._user_stream_tracker_task is not None:
            self._user_stream_tracker_task.cancel()
        if self._user_stream_event_listener_task is not None:
            self._user_stream_event_listener_task.cancel()
        if self._trading_rules_polling_task is not None:
            self._trading_rules_polling_task.cancel()
        self._status_polling_task = self._user_stream_tracker_task = \
            self._user_stream_event_listener_task = None

    async def stop_network(self):
        self._stop_network()

    async def check_network(self) -> NetworkStatus:
        try:
            client = await self._http_client()
            await client.get(TIME_URL)
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    cdef c_tick(self, double timestamp):
        cdef:
            int64_t last_tick = <int64_t>(self._last_timestamp / self._poll_interval)
            int64_t current_tick = <int64_t>(timestamp / self._poll_interval)
        ExchangeBase.c_tick(self, timestamp)
        self._tx_tracker.c_tick(timestamp)
        if current_tick > last_tick:
            if not self._poll_notifier.is_set():
                self._poll_notifier.set()
        self._last_timestamp = timestamp

    def generate_userref(self):
        self._last_userref += 1
        return self._last_userref

    async def _http_client(self) -> aiohttp.ClientSession:
        if self._shared_client is None:
            self._shared_client = aiohttp.ClientSession()
        return self._shared_client

    @staticmethod
    def is_cloudflare_exception(exception: Exception):
        """
        Error status 5xx or 10xx are related to Cloudflare.
        https://support.kraken.com/hc/en-us/articles/360001491786-API-error-messages#6
        """
        return bool(re.search(r"HTTP status is (5|10)\d\d\.", str(exception)))

    async def get_open_orders_with_userref(self, userref: int):
        data = {'userref': userref}
        return await self._api_request_with_retry("POST",
                                                  OPEN_ORDERS_URI,
                                                  is_auth_required=True,
                                                  data=data)

    async def _api_request_with_retry(self,
                                      method: str,
                                      path_url: str,
                                      params: Optional[Dict[str, Any]] = None,
                                      data: Optional[Dict[str, Any]] = None,
                                      is_auth_required: bool = False,
                                      request_weight: int = 1,
                                      retry_count = 5,
                                      retry_interval = 2.0) -> Dict[str, Any]:
        request_weight = self.API_COUNTER_POINTS.get(path_url, 0)
        if retry_count == 0:
            return await self._api_request(method, path_url, params, data, is_auth_required, request_weight)

        result = None
        for retry_attempt in range(retry_count):
            try:
                result= await self._api_request(method, path_url, params, data, is_auth_required, request_weight)
                break
            except IOError as e:
                if self.is_cloudflare_exception(e):
                    if path_url == ADD_ORDER_URI:
                        self.logger().info(f"Retrying {path_url}")
                        # Order placement could have been successful despite the IOError, so check for the open order.
                        response = self.get_open_orders_with_userref(data.get('userref'))
                        if any(response.get("open").values()):
                            return response
                    self.logger().warning(f"Cloudflare error. Attempt {retry_attempt+1}/{retry_count} API command {method}: {path_url}")
                    await asyncio.sleep(retry_interval ** retry_attempt)
                    continue
                else:
                    raise e
        if result is None:
            raise IOError(f"Error fetching data from {KRAKEN_ROOT_API + path_url}.")
        return result

    async def _api_request(self,
                           method: str,
                           path_url: str,
                           params: Optional[Dict[str, Any]] = None,
                           data: Optional[Dict[str, Any]] = None,
                           is_auth_required: bool = False,
                           request_weight: int = 1) -> Dict[str, Any]:
        async with self._throttler.weighted_task(request_weight=request_weight):
            url = KRAKEN_ROOT_API + path_url
            client = await self._http_client()
            headers = {}
            data_dict = data if data is not None else {}

            if is_auth_required:
                auth_dict: Dict[str, Any] = self._kraken_auth.generate_auth_dict(path_url, data=data)
                headers.update(auth_dict["headers"])
                data_dict = auth_dict["postDict"]

            response_coro = client.request(
                method=method.upper(),
                url=url,
                headers=headers,
                params=params,
                data=data_dict,
                timeout=100
            )

            async with response_coro as response:
                if response.status != 200:
                    raise IOError(f"Error fetching data from {url}. HTTP status is {response.status}.")
                try:
                    response_json = await response.json()
                except Exception:
                    raise IOError(f"Error parsing data from {url}.")

                try:
                    err = response_json["error"]
                    if "EOrder:Unknown order" in err or "EOrder:Invalid order" in err:
                        return {"error": err}
                    elif "EAPI:Invalid nonce" in err:
                        self.logger().error(f"Invalid nonce error from {url}. " +
                                            "Please ensure your Kraken API key nonce window is at least 10, " +
                                            "and if needed reset your API key.")
                        raise IOError({"error": response_json})
                except IOError:
                    raise
                except Exception:
                    pass

                data = response_json.get("result")
                if data is None:
                    self.logger().error(f"Error received from {url}. Response is {response_json}.")
                    raise IOError({"error": response_json})
                return data

    async def get_order(self, client_order_id: str) -> Dict[str, Any]:
        o = self._in_flight_orders.get(client_order_id)
        result = await self._api_request_with_retry("POST",
                                                    QUERY_ORDERS_URI,
                                                    data={"txid": o.exchange_order_id},
                                                    is_auth_required=True)
        return result

    def supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER]

    async def place_order(self,
                          userref: int,
                          trading_pair: str,
                          amount: Decimal,
                          order_type: OrderType,
                          is_buy: bool,
                          price: Optional[Decimal] = s_decimal_NaN):

        trading_pair = convert_to_exchange_trading_pair(trading_pair)
        data = {
            "pair": trading_pair,
            "type": "buy" if is_buy else "sell",
            "ordertype": "limit",
            "volume": str(amount),
            "userref": userref,
            "price": str(price)
        }
        if order_type is OrderType.LIMIT_MAKER:
            data["oflags"] = "post"
        return await self._api_request_with_retry("post",
                                                  ADD_ORDER_URI,
                                                  data=data,
                                                  is_auth_required=True)

    async def execute_buy(self,
                          order_id: str,
                          trading_pair: str,
                          amount: Decimal,
                          order_type: OrderType,
                          price: Optional[Decimal] = s_decimal_NaN,
                          userref: int = 0):
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]
            str base_currency = self.split_trading_pair(trading_pair)[0]
            str quote_currency = self.split_trading_pair(trading_pair)[1]
            object buy_fee = self.c_get_fee(base_currency, quote_currency, order_type, TradeType.BUY, amount, price)

        decimal_amount = self.c_quantize_order_amount(trading_pair, amount)
        decimal_price = self.c_quantize_order_price(trading_pair, price)
        if decimal_amount < trading_rule.min_order_size:
            raise ValueError(f"Buy order amount {decimal_amount} is lower than the minimum order size "
                             f"{trading_rule.min_order_size}.")

        try:
            order_result = None
            order_decimal_amount = f"{decimal_amount:f}"
            if order_type is OrderType.LIMIT or order_type is OrderType.LIMIT_MAKER:
                order_decimal_price = f"{decimal_price:f}"
                self.c_start_tracking_order(
                    order_id,
                    "",
                    trading_pair,
                    TradeType.BUY,
                    decimal_price,
                    decimal_amount,
                    order_type,
                    userref
                )
                order_result = await self.place_order(userref=userref,
                                                      trading_pair=trading_pair,
                                                      amount=order_decimal_amount,
                                                      order_type=order_type,
                                                      is_buy=True,
                                                      price=order_decimal_price)
            else:
                raise ValueError(f"Invalid OrderType {order_type}. Aborting.")

            exchange_order_id = order_result["txid"][0]
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
            order_type_str = 'LIMIT' if order_type is OrderType.LIMIT else "LIMIT_MAKER"
            self.logger().network(
                f"Error submitting buy {order_type_str} order to Kraken for "
                f"{decimal_amount} {trading_pair}"
                f" {decimal_price}.",
                exc_info=True,
                app_warning_msg=f"Failed to submit buy order to Kraken. Check API key and network connection."
            )
            self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                 MarketOrderFailureEvent(self._current_timestamp, order_id, order_type))

    cdef str c_buy(self, str trading_pair, object amount, object order_type=OrderType.LIMIT, object price=s_decimal_NaN,
                   dict kwargs={}):
        cdef:
            int64_t tracking_nonce = <int64_t> get_tracking_nonce()
            int32_t userref = <int32_t> self.generate_userref()
            str order_id = str(f"buy-{trading_pair}-{tracking_nonce}")
        safe_ensure_future(self.execute_buy(order_id, trading_pair, amount, order_type, price=price, userref=userref))
        return order_id

    async def execute_sell(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           order_type: OrderType,
                           price: Optional[Decimal] = Decimal("NaN"),
                           userref: int = 0):
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]

        decimal_amount = self.quantize_order_amount(trading_pair, amount)
        decimal_price = self.c_quantize_order_price(trading_pair, price)

        if decimal_amount < trading_rule.min_order_size:
            raise ValueError(f"Sell order amount {decimal_amount} is lower than the minimum order size "
                             f"{trading_rule.min_order_size}.")

        try:
            order_result = None
            order_decimal_amount = f"{decimal_amount:f}"
            if order_type is OrderType.LIMIT or order_type is OrderType.LIMIT_MAKER:
                order_decimal_price = f"{decimal_price:f}"
                self.c_start_tracking_order(
                    order_id,
                    "",
                    trading_pair,
                    TradeType.SELL,
                    decimal_price,
                    decimal_amount,
                    order_type,
                    userref
                )
                order_result = await self.place_order(userref=userref,
                                                      trading_pair=trading_pair,
                                                      amount=order_decimal_amount,
                                                      order_type=order_type,
                                                      is_buy=False,
                                                      price=order_decimal_price)
            else:
                raise ValueError(f"Invalid OrderType {order_type}. Aborting.")

            exchange_order_id = order_result["txid"][0]
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
            order_type_str = 'LIMIT' if order_type is OrderType.LIMIT else "LIMIT_MAKER"
            self.logger().network(
                f"Error submitting sell {order_type_str} order to Kraken for "
                f"{decimal_amount} {trading_pair} "
                f"{decimal_price}.",
                exc_info=True,
                app_warning_msg=f"Failed to submit sell order to Kraken. Check API key and network connection."
            )
            self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                 MarketOrderFailureEvent(self._current_timestamp, order_id, order_type))

    cdef str c_sell(self, str trading_pair, object amount, object order_type=OrderType.LIMIT, object price=s_decimal_NaN,
                    dict kwargs={}):
        cdef:
            int64_t tracking_nonce = <int64_t> get_tracking_nonce()
            int32_t userref = <int32_t> self.generate_userref()
            str order_id = str(f"sell-{trading_pair}-{tracking_nonce}")
        safe_ensure_future(self.execute_sell(order_id, trading_pair, amount, order_type, price=price, userref=userref))
        return order_id

    async def execute_cancel(self, trading_pair: str, order_id: str):
        try:
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is None:
                raise ValueError(f"Failed to cancel order – {order_id}. Order not found.")
            data: Dict[str, str] = {"txid": tracked_order.exchange_order_id}
            cancel_result = await self._api_request_with_retry("POST",
                                                               CANCEL_ORDER_URI,
                                                               data=data,
                                                               is_auth_required=True)

            if isinstance(cancel_result, dict) and (cancel_result.get("count") == 1 or cancel_result.get("error") is not None):
                self.logger().info(f"Successfully cancelled order {order_id}.")
                self.c_stop_tracking_order(order_id)
                self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                     OrderCancelledEvent(self._current_timestamp, order_id))
            return {
                "origClientOrderId": order_id
            }
        except Exception as e:
            self.logger().warning(f"Error cancelling order on Kraken",
                                  exc_info=True)

    cdef c_cancel(self, str trading_pair, str order_id):
        safe_ensure_future(self.execute_cancel(trading_pair, order_id))
        return order_id

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        incomplete_orders = [(key, o) for (key, o) in self._in_flight_orders.items() if not o.is_done]
        tasks = [self.execute_cancel(o.trading_pair, key) for (key, o) in incomplete_orders]
        order_id_set = set([key for (key, o) in incomplete_orders])
        successful_cancellations = []

        try:
            async with timeout(timeout_seconds):
                cancellation_results = await safe_gather(*tasks, return_exceptions=True)
                for cr in cancellation_results:
                    if isinstance(cr, Exception):
                        continue
                    if isinstance(cr, dict) and "origClientOrderId" in cr:
                        client_order_id = cr.get("origClientOrderId")
                        order_id_set.remove(client_order_id)
                        successful_cancellations.append(CancellationResult(client_order_id, True))
        except Exception:
            self.logger().network(
                f"Unexpected error cancelling orders.",
                exc_info=True,
                app_warning_msg="Failed to cancel order with Kraken. Check API key and network connection."
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
                                object order_type,
                                int userref):
        self._in_flight_orders[order_id] = KrakenInFlightOrder(
            client_order_id=order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=trading_pair,
            trade_type=trade_type,
            price=price,
            amount=amount,
            order_type=order_type,
            userref=userref
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
            object quantized_amount = ExchangeBase.c_quantize_order_amount(self, trading_pair, amount)

        global s_decimal_0
        if quantized_amount < trading_rule.min_order_size:
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
