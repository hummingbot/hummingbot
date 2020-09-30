import asyncio
from async_timeout import timeout
from decimal import Decimal
from threading import Thread
import logging
import pandas as pd
import re
import copy
from typing import (
    Any,
    Dict,
    List,
    Optional,
    AsyncIterable
)
from libc.stdint cimport int64_t

from hummingbot.core.clock cimport Clock
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.limit_order import LimitOrder
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
    MarketTransactionFailureEvent,
    MarketOrderFailureEvent
)
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.eterbase.eterbase_auth import EterbaseAuth
from hummingbot.connector.exchange.eterbase.eterbase_order_book_tracker import EterbaseOrderBookTracker
from hummingbot.connector.exchange.eterbase.eterbase_user_stream_tracker import EterbaseUserStreamTracker
from hummingbot.connector.exchange.eterbase.eterbase_api_order_book_data_source import EterbaseAPIOrderBookDataSource
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.core.event.events import OrderType
from hummingbot.connector.exchange.eterbase.eterbase_utils import (
    convert_from_exchange_trading_pair)
from hummingbot.connector.exchange.eterbase.eterbase_trading_rule cimport EterbaseTradingRule
from hummingbot.connector.exchange.eterbase.eterbase_in_flight_order cimport EterbaseInFlightOrder

from datetime import datetime, timedelta
import time

import hummingbot.connector.exchange.eterbase.eterbase_constants as constants
from hummingbot.connector.exchange.eterbase.eterbase_utils import api_request

s_logger = None
s_decimal_0 = Decimal(0)
s_decimal_nan = Decimal("nan")


def start_background_loop(loop: asyncio.AbstractEventLoop) -> None:
    loop.run_forever()


cdef class EterbaseExchangeTransactionTracker(TransactionTracker):

    cdef:
        EterbaseExchange _owner

    def __init__(self, owner: EterbaseExchange):
        super().__init__()
        self._owner = owner

    cdef c_did_timeout_tx(self, str tx_id):
        TransactionTracker.c_did_timeout_tx(self, tx_id)
        self._owner.c_did_timeout_tx(tx_id)


cdef class EterbaseExchange(ExchangeBase):
    MARKET_BUY_ORDER_COMPLETED_EVENT_TAG = MarketEvent.BuyOrderCompleted.value
    MARKET_SELL_ORDER_COMPLETED_EVENT_TAG = MarketEvent.SellOrderCompleted.value
    MARKET_ORDER_CANCELLED_EVENT_TAG = MarketEvent.OrderCancelled.value
    MARKET_TRANSACTION_FAILURE_EVENT_TAG = MarketEvent.TransactionFailure.value
    MARKET_ORDER_FAILURE_EVENT_TAG = MarketEvent.OrderFailure.value
    MARKET_ORDER_FILLED_EVENT_TAG = MarketEvent.OrderFilled.value
    MARKET_BUY_ORDER_CREATED_EVENT_TAG = MarketEvent.BuyOrderCreated.value
    MARKET_SELL_ORDER_CREATED_EVENT_TAG = MarketEvent.SellOrderCreated.value

    UPDATE_ORDERS_INTERVAL = 10.0

    ORDER_NOT_EXIST_CONFIRMATION_COUNT = 3

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(__name__)
        return s_logger

    def __init__(self,
                 eterbase_api_key: str,
                 eterbase_secret_key: str,
                 eterbase_account: str,
                 poll_interval: float = 5.0,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True):
        super().__init__()
        self._trading_required = trading_required
        self._eterbase_account = eterbase_account
        self._eterbase_auth = EterbaseAuth(eterbase_api_key,
                                           eterbase_secret_key)
        self._order_book_tracker = EterbaseOrderBookTracker(trading_pairs = trading_pairs)
        self._user_stream_tracker = EterbaseUserStreamTracker(eterbase_auth = self._eterbase_auth,
                                                              eterbase_account = self._eterbase_account,
                                                              trading_pairs = trading_pairs)
        self._ev_loop = asyncio.get_event_loop()
        self._poll_notifier = asyncio.Event()
        self._last_timestamp = 0
        self._last_order_update_timestamp = 0
        self._poll_interval = poll_interval
        self._in_flight_orders = dict()
        self._tx_tracker = EterbaseExchangeTransactionTracker(self)
        self._trading_rules = {}
        self._status_polling_task = None
        self._order_tracker_task = None
        self._user_stream_tracker_task = None
        self._user_stream_event_listener_task = None
        self._trading_rules_polling_task = None
        self._shared_client = None
        self._maker_fee = None
        self._taker_fee = None
        self._order_not_found_records: Dict[str, Int] = {}
        self._real_time_balance_update = False

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
        """
        return self._order_book_tracker.order_books

    @property
    def eterbase_auth(self) -> EterbaseAuth:
        """
        :return: Eterbase class
        """
        return self._eterbase_auth

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
            "trading_rule_initialized": len(self._trading_rules) > 0 if self._trading_required else True
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

    @property
    def in_flight_orders(self) -> Dict[str, EterbaseInFlightOrder]:
        return self._in_flight_orders

    def restore_tracking_states(self, saved_states: Dict[str, any]):
        """
        *required
        Updates inflight order statuses from API results
        This is used by the MarketsRecorder class to orchestrate market classes at a higher level.
        """
        self._in_flight_orders.update({
            key: EterbaseInFlightOrder.from_json(value)
            for key, value in saved_states.items()
        })

    async def get_active_exchange_markets(self) -> pd.DataFrame:
        """
        *required
        Used by the discovery strategy to read order books of all actively trading markets,
        and find opportunities to profit
        """
        return await EterbaseAPIOrderBookDataSource.get_active_exchange_markets()

    cdef c_start(self, Clock clock, double timestamp):
        """
        *required
        c_start function used by top level Clock to orchestrate components of the bot
        """
        self._tx_tracker.c_start(clock, timestamp)
        ExchangeBase.c_start(self, clock, timestamp)

    async def start_network(self):
        """
        *required
        Async function used by NetworkBase class to handle when a single market goes online
        """
        if self._order_tracker_task is not None:
            self._stop_network()
        self._order_book_tracker.start()
        if self._trading_required:
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())
            self._trading_rules_polling_task = safe_ensure_future(self._trading_rules_polling_loop())
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
            await api_request("get", path_url="/ping")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error("Unexpected error when checking network", exc_info=True)
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

        ExchangeBase.c_tick(self, timestamp)
        if current_tick > last_tick:
            if not self._poll_notifier.is_set():
                self._poll_notifier.set()
        self._last_timestamp = timestamp

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

        cdef:
            object maker_fee = None
            object taker_fee = None

        if ((self._maker_fee is None) or (self._taker_fee is None)):
            path_url = f"/accounts/{self._eterbase_account}/customer-profile"

            loop = asyncio.new_event_loop()
            t = Thread(target=start_background_loop, args=(loop, ), daemon=True)
            t.start()
            future = asyncio.run_coroutine_threadsafe(api_request("get", path_url=path_url, auth=self._eterbase_auth, loop=loop), loop)
            customer_profile = future.result(constants.API_TIMEOUT_SEC)
            loop.stop()

            maker_fee = Decimal(customer_profile['membership']['current']['makerFee'])
            if (maker_fee > 1):
                maker_fee = Decimal(0)
            taker_fee = Decimal(customer_profile['membership']['current']['takerFee'])
            self.logger().debug(f"makerFee: {maker_fee}, takerFee: {taker_fee}")
            self._maker_fee = maker_fee
            self._taker_fee = taker_fee

        return TradeFee(percent=self._maker_fee if order_type is OrderType.LIMIT_MAKER else self._taker_fee)

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

        path_url = f"/accounts/{self._eterbase_account}/balances"
        account_balances = await api_request("get", path_url=path_url, auth=self._eterbase_auth)
        for balance_entry in account_balances:
            asset_name = balance_entry["assetId"]
            available_balance = Decimal(balance_entry["available"])
            total_balance = Decimal(balance_entry["balance"])
            self._account_available_balances[asset_name] = available_balance
            self._account_balances[asset_name] = total_balance
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

        self._in_flight_orders_snapshot = {k: copy.copy(v) for k, v in self._in_flight_orders.items()}
        self._in_flight_orders_snapshot_timestamp = self._current_timestamp

    async def _update_trading_rules(self):
        """
        Pulls the API for trading rules (min / max order size, etc)
        """
        cdef:
            # The poll interval for withdraw rules is 60 seconds.
            int64_t last_tick = <int64_t>(self._last_timestamp / 60.0)
            int64_t current_tick = <int64_t>(self._current_timestamp / 60.0)
        if current_tick > last_tick or len(self._trading_rules) <= 0:
            product_info = await api_request("get", path_url="/markets")

            trading_rules_list = self._format_trading_rules(product_info)
            self._trading_rules.clear()
            for trading_rule in trading_rules_list:
                self._trading_rules[convert_from_exchange_trading_pair(trading_rule.trading_pair)] = trading_rule

    def _format_trading_rules(self, raw_trading_rules: List[Any]) -> List[EterbaseTradingRule]:
        """
        Turns json data from API into TradingRule instances
        :returns: List of TradingRule
        """
        cdef:
            list retval = []
        for rule in raw_trading_rules:
            try:
                trading_pair = rule.get("symbol")
                priceSigDigs = rule.get("priceSigDigs")
                qtySigDigs = rule.get("qtySigDigs")
                costSigDigs = rule.get("costSigDigs")
                trad_rules= rule.get("tradingRules")
                allowedOrderTypes = rule.get("allowedOrderTypes")
                mn_order_size= None
                mx_order_size= None
                mn_price_increment= None
                orderTypeMarket = False
                orderTypeLimit = False

                for orderTp in allowedOrderTypes:
                    if orderTp == 1:
                        orderTypeMarket = True
                    elif orderTp == 2:
                        orderTypeLimit = True

                for trad_rule in trad_rules:
                    attr = trad_rule.get("attribute")
                    con = trad_rule.get("condition")
                    value = trad_rule.get("value")
                    if (attr == "Qty"):
                        if (con == "Min"):
                            mn_order_size = Decimal(str(value))
                        elif (con == "Max"):
                            mx_order_size = Decimal(str(value))
                    elif (attr == "OrderCount"):
                        self.logger().debug("eterbase_market - format_trading_rules - orderCount: future imp")
                    elif (attr == "Cost"):
                        if (con == "Min"):
                            min_order_value = Decimal(str(value))
                        elif (con == "Max"):
                            max_order_value = Decimal(str(value))

                retval.append(EterbaseTradingRule(trading_pair,
                                                  min_order_size = mn_order_size,
                                                  max_order_size = mx_order_size,
                                                  min_order_value = min_order_value,
                                                  max_order_value = max_order_value,
                                                  max_price_significant_digits = priceSigDigs,
                                                  max_cost_significant_digits = costSigDigs,
                                                  max_quantity_significant_digits = qtySigDigs,
                                                  supports_limit_orders = orderTypeLimit,
                                                  supports_market_orders = orderTypeMarket,
                                                  min_price_increment = Decimal(f"1e-{priceSigDigs}"),
                                                  min_base_amount_increment = Decimal(f"1e-{qtySigDigs}"),
                                                  min_quote_amount_increment = Decimal(f"1e-{costSigDigs}")))
            except Exception as ex:
                self.logger().error(f"Error parsing the trading_pair rule {rule}. Skipping.", exc_info=True)
                self.logger().error(str(ex))
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
        order_dict = dict((result["id"], result) for result in results)
        for tracked_order in tracked_orders:
            exchange_order_id = await tracked_order.get_exchange_order_id()
            order_update = order_dict.get(exchange_order_id)
            if order_update is None:
                self._order_not_found_records[exchange_order_id] = self._order_not_found_records.get(exchange_order_id, 0) + 1
                if self._order_not_found_records[exchange_order_id] < self.ORDER_NOT_EXIST_CONFIRMATION_COUNT:
                    # Wait until the order not found error have repeated a few times before actually treating
                    # it as failed. See: https://github.com/CoinAlpha/hummingbot/issues/601
                    continue
                self.logger().network(
                    f"Error fetching status update for the order {tracked_order.client_order_id}: "
                    f"{order_update}.",
                    app_warning_msg=f"Could not fetch updates for the order {tracked_order.client_order_id}. OrderId: {exchange_order_id}. "
                                    f"Check API key and network connection.")
                continue
            try:
                order_fills = await self.get_order_fills(exchange_order_id)
            except IOError as ioe:
                if ((ioe.args[1] == 400) and ("'Invalid order ID'" in ioe.args[0])):
                    self._order_not_found_records[exchange_order_id] = self._order_not_found_records.get(exchange_order_id, 0) + 1
                    if self._order_not_found_records[exchange_order_id] < self.ORDER_NOT_EXIST_CONFIRMATION_COUNT:
                        # Wait until the order not found error have repeated a few times before actually treating
                        # it as failed. See: https://github.com/CoinAlpha/hummingbot/issues/601
                        continue
                    self.c_trigger_event(
                        self.MARKET_ORDER_FAILURE_EVENT_TAG,
                        MarketOrderFailureEvent(self._current_timestamp, tracked_order.client_order_id, tracked_order.order_type)
                    )
                    self.c_stop_tracking_order(tracked_order.client_order_id)
                else:
                    self.logger().network(
                        f"Error fetching status update for the order {tracked_order.client_order_id}: "
                        f"{order_update}."
                        f"Exception: {ioe}",
                        app_warning_msg=f"Could not fetch updates for the order {tracked_order.client_order_id}. OrderId: {exchange_order_id}. "
                                        f"Check API key and network connection.")
                continue

            done_reason = order_update.get("closeReason")

            # Calculate the newly executed amount/cost for this update.
            # Cost only for MARKET order BUY
            execute_amount_diff = s_decimal_0
            new_confirmed_amount = s_decimal_0
            new_confirmed_amount = Decimal(order_update["qty"]) - Decimal(order_update["remainingQty"])
            execute_amount_diff = new_confirmed_amount - tracked_order.executed_amount_base

            client_order_id = tracked_order.client_order_id
            order_type_description = tracked_order.order_type_description
            # Emit event if executed amount is greater than 0.
            if (execute_amount_diff > s_decimal_0):
                # Find execute price
                for order_fill in order_fills:
                    if order_fill["orderId"] == order_update["id"]:
                        if not(order_fill["id"] in tracked_order.fill_ids):
                            execute_price = Decimal(order_fill["price"])
                            order_filled_event = OrderFilledEvent(
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
                                # Eterbase websocket stream tags events with order_id rather than trade_id
                                # Using order_id here for easier data validation
                                exchange_trade_id = exchange_order_id,
                            )
                            self.logger().info(f"Filled {execute_amount_diff} out of {tracked_order.amount} of the "
                                               f"{order_type_description} order {client_order_id}.")

                            self.c_trigger_event(self.MARKET_ORDER_FILLED_EVENT_TAG, order_filled_event)

                            # Add order fill into set for current tracked_order
                            tracked_order.fill_ids.add(order_fill["id"])

                            # Update the tracked order from fills
                            tracked_order.executed_amount_quote = tracked_order.executed_amount_quote + Decimal(order_fill["cost"])
                            tracked_order.fee_paid = tracked_order.fee_paid + Decimal(order_fill["fee"])

            # Update the tracked order

            tracked_order.last_state = done_reason if done_reason in {"FILLED",
                                                                      "USER_REQUESTED_CANCEL",
                                                                      "ADMINISTRATIVE_CANCEL",
                                                                      "NOT_ENOUGH_LIQUIDITY",
                                                                      "EXPIRED",
                                                                      "ONE_CANCELS_OTHER"} else str(order_update["state"])
            tracked_order.executed_amount_base = new_confirmed_amount

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
                                                                    tracked_order.order_type))
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
                                                                     tracked_order.order_type))
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
                event_type = content.get("type")
                exchange_order_ids = [content.get("orderId")]

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

                if event_type == "match" or event_type == "o_fill":
                    execute_amount_diff = Decimal(content.get("qty", 0.0))
                    tracked_order.executed_amount_base += execute_amount_diff
                    tracked_order.executed_amount_quote += execute_amount_diff * execute_price

                if event_type == "change" or event_type == "o_triggered":
                    if content.get("new_size") is not None:
                        tracked_order.amount = Decimal(content.get("new_size", 0.0))
                    elif content.get("new_funds") is not None:
                        if tracked_order.price is not s_decimal_0:
                            tracked_order.amount = Decimal(content.get("new_funds")) / tracked_order.price
                    else:
                        self.logger().error(f"Invalid change message - '{content}'. Aborting.")

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

                if (event_type=="o_closed") and content.get("closeReason") == "FILLED":
                    if tracked_order.trade_type == TradeType.BUY:
                        self.logger().info(f"The market buy order {tracked_order.client_order_id} has completed "
                                           f"according to Eterbase user stream.")
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
                    elif tracked_order.trade_type == TradeType.SELL:
                        self.logger().info(f"The market sell order {tracked_order.client_order_id} has completed "
                                           f"according to Eterbase user stream.")
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
                        self.logger().error("Unexpected error order type is not sell nor buy.", exc_info=True)
                    self.c_stop_tracking_order(tracked_order.client_order_id)
                elif (event_type=="o_closed") and content.get("closeReason") != "FILLED":
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

    def supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER]

    async def place_order(self, order_id: str, trading_pair: str, amount: Decimal, is_buy: bool, order_type: OrderType,
                          price: Decimal, cost: Optional[Decimal]):
        """
        Async wrapper for placing orders through the rest API.
        :returns: json response from the API
        """
        tp_map_mkrtid: Dict[str, str] = await EterbaseAPIOrderBookDataSource.get_map_market_id()
        path_url = "/orders"

        if order_type is OrderType.LIMIT or order_type is OrderType.LIMIT_MAKER:
            type_order = 2
        else:
            self.logger().error(f"Unsuported Order type value - {order_type}.", exc_info=True)

        if is_buy is True:
            side_order = 1
        elif is_buy is False:
            side_order = 2
        else:
            self.logger().error(f"Unsuported Order side value - {is_buy}.", exc_info=True)

        data = {
            "accountId": self._eterbase_account,
            "marketId": tp_map_mkrtid[trading_pair],
            "side": side_order,
            "type": type_order,
            "refId": order_id
        }

        if order_type is OrderType.LIMIT or order_type is OrderType.LIMIT_MAKER:
            data["limitPrice"] = str(price)
            data["qty"] = str(amount)
            if order_type is OrderType.LIMIT_MAKER:
                data["postOnly"] = True
        else:
            self.logger().error(f"Unsuported OrderType - {order_type}.", exc_info=True)

        order_result = await api_request("post", path_url = path_url, data = data, auth = self._eterbase_auth)

        return order_result

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
            EterbaseTradingRule trading_rule = self._trading_rules[trading_pair]
        decimal_amount = self.quantize_order_amount(trading_pair, amount)
        decimal_price = self.quantize_order_price(trading_pair, price)
        decimal_cost = s_decimal_0
        # For Order Market type is needed cost
        if (order_type == OrderType.LIMIT or order_type == OrderType.LIMIT_MAKER):
            # convert price according significant digits
            decimal_price = self.c_round_to_sig_digits(decimal_price, trading_rule.max_price_significant_digits)
            if decimal_amount < trading_rule.min_order_size:
                raise ValueError(f"Buy order amount {decimal_amount} is lower than the minimum order size "
                                 f"{trading_rule.min_order_size}.")
            if decimal_amount > trading_rule.max_order_size:
                raise ValueError(f"Buy order amount {decimal_amount} is higer than the maximum order size "
                                 f"{trading_rule.max_order_size}.")
        else:
            raise ValueError(f"Unsuported Order type {order_type}.")
        try:
            self.c_start_tracking_order(order_id, trading_pair, order_type, TradeType.BUY, decimal_price, decimal_amount, decimal_cost)
            order_result = await self.place_order(order_id, trading_pair, decimal_amount, True, order_type, decimal_price, decimal_cost)

            exchange_order_id = order_result["id"]
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(f"Created {order_type} buy order {order_id} for amount {decimal_amount} and price {decimal_price} or cost {decimal_cost} {trading_pair}.")
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
            order_type_str = order_type.name.lower()
            self.logger().network(
                f"Error submitting buy {order_type_str} order to Eterbase for "
                f"{decimal_amount} {trading_pair} {price}.",
                exc_info=True,
                app_warning_msg="Failed to submit buy order to Eterbase. "
                                "Check API key and network connection."
            )
            self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                 MarketOrderFailureEvent(self._current_timestamp, order_id, order_type))

    cdef str c_buy(self, str trading_pair, object amount, object order_type=OrderType.LIMIT, object price=s_decimal_0,
                   dict kwargs={}):
        """
        *required
        Synchronous wrapper that generates a client-side order ID and schedules the buy order.
        """
        cdef:
            int64_t tracking_nonce = <int64_t>(time.time() * 1e6)
            str order_id = str(f"b-{tracking_nonce}")
        safe_ensure_future(self.execute_buy(order_id, trading_pair, amount, order_type, price))
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
            EterbaseTradingRule trading_rule = self._trading_rules[trading_pair]
        decimal_amount = self.quantize_order_amount(trading_pair, amount)
        decimal_price = self.quantize_order_price(trading_pair, price)
        decimal_cost = s_decimal_0

        # convert price according significant digits
        decimal_price = self.c_round_to_sig_digits(decimal_price, trading_rule.max_price_significant_digits)
        if decimal_amount < trading_rule.min_order_size:
            raise ValueError(f"Sell order amount {decimal_amount} is lower than the minimum order size "
                             f"{trading_rule.min_order_size}.")

        try:
            self.c_start_tracking_order(order_id, trading_pair, order_type, TradeType.SELL, decimal_price, decimal_amount, decimal_cost)
            order_result = await self.place_order(order_id, trading_pair, decimal_amount, False, order_type, decimal_price, decimal_cost)

            exchange_order_id = order_result["id"]
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
        except Exception as e:
            self.c_stop_tracking_order(order_id)
            order_type_str = order_type.name.lower()
            self.logger().network(
                f"Error submitting sell {order_type_str} order to Eterbase for "
                f"{decimal_amount} {trading_pair} {price}.",
                exc_info=True,
                app_warning_msg="Failed to submit sell order to Eterbase. "
                                "Check API key and network connection."
            )
            self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                 MarketOrderFailureEvent(self._current_timestamp, order_id, order_type))

    cdef str c_sell(self, str trading_pair, object amount, object order_type=OrderType.LIMIT, object price=s_decimal_0,
                    dict kwargs={}):
        """
        *required
        Synchronous wrapper that generates a client-side order ID and schedules the sell order.
        """
        cdef:
            int64_t tracking_nonce = <int64_t>(time.time() * 1e6)
            str order_id = str(f"s-{tracking_nonce}")
        safe_ensure_future(self.execute_sell(order_id, trading_pair, amount, order_type, price))
        return order_id

    async def execute_cancel(self, trading_pair: str, order_id: str):
        """
        Function that makes API request to cancel an active order
        """
        try:
            exchange_order_id = await self._in_flight_orders.get(order_id).get_exchange_order_id()
            path_url = f"/orders/{exchange_order_id}"
            await api_request("delete", path_url=path_url, auth=self._eterbase_auth)
            self.logger().info(f"Successfully cancelled order {order_id}. Exchange_Order_Id {exchange_order_id}")
            self.c_stop_tracking_order(order_id)
            self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                 OrderCancelledEvent(self._current_timestamp, order_id))
            return order_id
        except IOError as e:
            if "order not found" in e.message:
                # The order was never there to begin with. So cancelling it is a no-op but semantically successful.
                self.logger().info(f"The order {order_id} does not exist on Eterbase. No cancellation needed.")
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
                app_warning_msg=f"Failed to cancel the order {order_id} on Eterbase. "
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
                app_warning_msg="Failed to cancel order on Eterbase. Check API key and network connection."
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
                    app_warning_msg=f"Could not fetch account updates on Eterbase. "
                                    f"Check API key and network connection."
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
                    app_warning_msg=f"Could not fetch trading rule updates on Eterbase. "
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
        path_url = f"/orders/{exchange_order_id}"
        result = await api_request("get", path_url=path_url, auth=self._eterbase_auth)

        return result

    async def get_order_fills(self, exchange_order_id: str) -> Dict:
        """
        Gets status update for a particular order via rest API
        :returns: json response
        """
        path_url = f"/orders/{exchange_order_id}/fills?from=" + str(self.to_unix_time_minus_ten_d())
        result = await api_request("get", path_url=path_url, auth=self._eterbase_auth)

        return result

    def to_unix_time_minus_ten_d(self) -> int:

        d = datetime.today() - timedelta(days=1)

        return int(d.timestamp() * 1000)

    async def list_orders(self) -> List[Any]:
        """
        Gets a list of the user's active orders via rest API
        :returns: json response
        """
        path_url1 = "/accounts/" + self._eterbase_account + "/orders?state=ACTIVE&limit=50&from=" + str(self.to_unix_time_minus_ten_d())

        result1 = await api_request("get", path_url=path_url1, auth=self._eterbase_auth)

        path_url2 = "/accounts/" + self._eterbase_account + "/orders?state=INACTIVE&limit=50&from=" + str(self.to_unix_time_minus_ten_d())

        result2 = await api_request("get", path_url=path_url2, auth=self._eterbase_auth)

        results = []
        for r in result1:
            results.append(r)
        for r in result2:
            results.append(r)

        return results

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
                                object amount,
                                object cost):
        """
        Add new order to self._in_flight_orders mapping
        """
        self._in_flight_orders[client_order_id] = EterbaseInFlightOrder(
            client_order_id,
            None,
            trading_pair,
            order_type,
            trade_type,
            price,
            amount,
            cost
        )

    cdef c_stop_tracking_order(self, str order_id):
        """
        Delete an order from self._in_flight_orders mapping
        """
        if order_id in self._in_flight_orders:
            del self._in_flight_orders[order_id]
        if order_id in self._order_not_found_records:
            del self._order_not_found_records[order_id]

    cdef c_did_timeout_tx(self, str tracking_id):
        """
        Triggers MarketEvent.TransactionFailure when an Ethereum transaction has timed out
        """
        self.c_trigger_event(self.MARKET_TRANSACTION_FAILURE_EVENT_TAG,
                             MarketTransactionFailureEvent(self._current_timestamp, tracking_id))

    cdef object c_round_to_sig_digits(self, object number, int sigdig, object maxdecimal=None):
        """
        Round number to significant digits
        """
        rounded_number = s_decimal_0

        str_number = ("{0:." + str(sigdig) + "g}").format(number)
        if re.search(r'e+', str_number):
            rounded_number = Decimal("{:.0f}".format(Decimal(str_number)))
        else:
            rounded_number = Decimal(str_number)
        if (maxdecimal is not None):
            if (type(maxdecimal) is int):
                (sign, digits, exponent) = rounded_number.as_tuple()
                if (-maxdecimal > exponent):
                    rounded_number = Decimal(("{:." + str(maxdecimal) + "f}").format(rounded_number))
            else:
                self.logger().error(f"Maxdecimal={maxdecimal} parameter must by None or int type.")
        return rounded_number

    cdef object c_get_order_price_quantum(self, str trading_pair, object price):
        """
        *required
        Get the minimum increment interval for price
        :return: Min order price increment in Decimal format
        """
        cdef:
            EterbaseTradingRule trading_rule = self._trading_rules[trading_pair]

        rounded_price = self.c_round_to_sig_digits(price, trading_rule.max_price_significant_digits)

        (sign, digits, exponent) = rounded_price.as_tuple()
        base_str = ""
        for i in range(trading_rule.max_price_significant_digits):
            if (i < len(digits)):
                base_str += str(digits[i])
            else:
                base_str += "0"

        price_quantum = rounded_price / Decimal(base_str)

        return price_quantum

    cdef object c_get_order_size_quantum(self, str trading_pair, object order_size):
        """
        *required
        Get the minimum increment interval for order size (e.g. 0.01 USD)
        :return: Min order size increment in Decimal format
        """
        cdef:
            EterbaseTradingRule trading_rule = self._trading_rules[trading_pair]

        rounded_amount = self.c_round_to_sig_digits(order_size, trading_rule.max_quantity_significant_digits, 8)

        (sign, digits, exponent) = rounded_amount.as_tuple()
        base_str = ""
        for i in range(trading_rule.max_quantity_significant_digits):
            if (i < len(digits)):
                base_str += str(digits[i])
            else:
                base_str += "0"

        size_quantum = rounded_amount / Decimal(base_str)
        return size_quantum

    cdef object c_quantize_order_amount(self, str trading_pair, object amount, object price=s_decimal_0):
        """
        *required
        Check current order amount against trading rule, and correct any rule violations
        :return: Valid order amount in Decimal format
        """
        cdef:
            EterbaseTradingRule trading_rule = self._trading_rules[trading_pair]

        global s_decimal_0

        # only 8 decimal places are allowed for amount in API
        quantized_amount = self.c_round_to_sig_digits(amount, trading_rule.max_quantity_significant_digits, 8)

        # Check against min_order_size. If not passing either check, return 0.
        if quantized_amount < trading_rule.min_order_size:
            return s_decimal_0

        # Check against max_order_size. If not passing either check, return 0.
        if quantized_amount > trading_rule.max_order_size:
            return s_decimal_0

        return quantized_amount

    cdef object c_quantize_cost(self, str trading_pair, object amount, object price):
        """
        *required
        Check current order cost against trading rule, and correct any rule violations
        :return: Valid order cost in Decimal format
        """
        cdef:
            EterbaseTradingRule trading_rule = self._trading_rules[trading_pair]

        global s_decimal_0

        cost = amount * price
        # only 8 decimal places are allowed for cost in API
        quantized_cost = self.c_round_to_sig_digits(cost, trading_rule.max_cost_significant_digits, 8)

        # Check against min_order_value. If not passing either check, return 0.
        if quantized_cost < trading_rule.min_order_value:
            return s_decimal_0

        # Check against max_order_value. If not passing either check, return 0.
        if quantized_cost > trading_rule.max_order_value:
            return s_decimal_0

        return quantized_cost

    cdef object c_quantize_order_price(self, str trading_pair, object price):
        """
        *required
        Check current order amount against trading rule, and correct any rule violations
        :return: Valid order amount in Decimal format
        """
        cdef:
            EterbaseTradingRule trading_rule = self._trading_rules[trading_pair]

        quantized_price = ExchangeBase.c_quantize_order_price(self, trading_pair, price)

        quantized_price = self.c_round_to_sig_digits(quantized_price, trading_rule.max_price_significant_digits)

        return quantized_price

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
                price: Decimal = s_decimal_nan) -> TradeFee:
        return self.c_get_fee(base_currency, quote_currency, order_type, order_side, amount, price)

    def get_order_book(self, trading_pair: str) -> OrderBook:
        return self.c_get_order_book(trading_pair)
