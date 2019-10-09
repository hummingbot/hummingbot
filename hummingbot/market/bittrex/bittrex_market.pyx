import asyncio
import logging
import time
from decimal import Decimal
from typing import Optional, List, Dict, Any, AsyncIterable

import aiohttp
import pandas as pd
from async_timeout import timeout
from libc.stdint cimport int64_t

from hummingbot.core.clock cimport Clock
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.core.data_type.order_book_tracker import OrderBookTrackerDataSourceType
from hummingbot.core.event.events import (
    MarketEvent,
    TradeFee,
    OrderType,
    OrderFilledEvent,
    TradeType,
    BuyOrderCompletedEvent,
    SellOrderCompletedEvent, OrderCancelledEvent, MarketTransactionFailureEvent,
    MarketOrderFailureEvent, SellOrderCreatedEvent, BuyOrderCreatedEvent)
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.logger import HummingbotLogger
from hummingbot.market.bittrex.bittrex_api_order_book_data_source import BittrexAPIOrderBookDataSource
from hummingbot.market.bittrex.bittrex_auth import BittrexAuth
from hummingbot.market.bittrex.bittrex_in_flight_order import BittrexInFlightOrder
from hummingbot.market.bittrex.bittrex_order_book_tracker import BittrexOrderBookTracker
from hummingbot.market.bittrex.bittrex_user_stream_tracker import BittrexUserStreamTracker
from hummingbot.market.deposit_info import DepositInfo
from hummingbot.market.market_base import NaN
from hummingbot.market.trading_rule cimport TradingRule

bm_logger = None
s_decimal_0 = Decimal(0)

cdef class BittrexMarketTransactionTracker(TransactionTracker):
    cdef:
        BittrexMarket _owner

    def __init__(self, owner: BittrexMarket):
        super().__init__()
        self._owner = owner

    cdef c_did_timeout_tx(self, str tx_id):
        TransactionTracker.c_did_timeout_tx(self, tx_id)
        self._owner.c_did_timeout_tx(tx_id)

cdef class BittrexMarket(MarketBase):
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
    ORDER_NOT_EXIST_CONFIRMATION_COUNT = 3

    BITTREX_API_ENDPOINT = "https://api.bittrex.com/v3"

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global bm_logger
        if bm_logger is None:
            bm_logger = logging.getLogger(__name__)
        return bm_logger

    def __init__(self,
                 bittrex_api_key: str,
                 bittrex_secret_key: str,
                 poll_interval: float = 5.0,
                 order_book_tracker_data_source_type: OrderBookTrackerDataSourceType =
                 OrderBookTrackerDataSourceType.EXCHANGE_API,
                 symbols: Optional[List[str]] = None,
                 trading_required: bool = True):
        super().__init__()
        self._account_available_balances = {}
        self._account_balances = {}
        self._account_id = ""
        self._bittrex_auth = BittrexAuth(bittrex_api_key, bittrex_secret_key)
        self._data_source_type = order_book_tracker_data_source_type
        self._ev_loop = asyncio.get_event_loop()
        self._in_flight_orders = {}
        self._last_poll_timestamp = 0
        self._last_timestamp = 0
        self._order_book_tracker = BittrexOrderBookTracker(data_source_type=order_book_tracker_data_source_type,
                                                           symbols=symbols)
        self._order_not_found_records = {}
        self._order_tracker_task = None
        self._poll_notifier = asyncio.Event()
        self._poll_interval = poll_interval
        self._shared_client = None
        self._status_polling_task = None
        self._trading_required = trading_required
        self._trading_rules = {}
        self._trading_rules_polling_task = None
        self._tx_tracker = BittrexMarketTransactionTracker(self)
        self._user_stream_event_listener_task = None
        self._user_stream_tracker = BittrexUserStreamTracker(bittrex_auth=self._bittrex_auth,
                                                             symbols=symbols)
        self._user_stream_tracker_task = None
        self._check_network_interval = 60.0

    @property
    def name(self) -> str:
        return "bittrex"

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        return self._order_book_tracker.order_books

    @property
    def bittrex_auth(self) -> BittrexAuth:
        return self._bittrex_auth

    @property
    def status_dict(self) -> Dict[str, bool]:
        return {
            "order_book_initialized": self._order_book_tracker.ready,
            "account_balance": len(self._account_balances) > 0 if self._trading_required else True,
            "trading_rule_initialized": len(self._trading_rules) > 0 if self._trading_required else True
        }

    @property
    def ready(self) -> bool:
        return all(self.status_dict.values())

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
            key: BittrexInFlightOrder.from_json(value)
            for key, value in saved_states.items()
        })

    async def get_active_exchange_markets(self) -> pd.DataFrame:
        return await BittrexAPIOrderBookDataSource.get_active_exchange_markets()

    def get_all_balances(self) -> Dict[str, float]:
        return self._account_balances.copy()

    cdef c_start(self, Clock clock, double timestamp):
        self._tx_tracker.c_start(clock, timestamp)
        MarketBase.c_start(self, clock, timestamp)

    cdef c_tick(self, double timestamp):
        cdef:
            int64_t last_tick = <int64_t> (self._last_timestamp / self._poll_interval)
            int64_t current_tick = <int64_t> (timestamp / self._poll_interval)

        MarketBase.c_tick(self, timestamp)
        self._tx_tracker.c_tick(timestamp)
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
        # There is no API for checking fee
        # Fee info from https://bittrex.zendesk.com/hc/en-us/articles/115003684371
        cdef:
            double maker_fee = 0.0025
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

        path_url = "/balances"
        account_balances = await self._api_request("GET", path_url=path_url)

        for balance_entry in account_balances:
            asset_name = balance_entry["currencySymbol"]
            available_balance = Decimal(balance_entry["available"])
            total_balance = Decimal(balance_entry["total"])
            self._account_available_balances[asset_name] = available_balance
            self._account_balances[asset_name] = total_balance
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    def _format_trading_rules(self, market_list: List[Any]) -> List[TradingRule]:
        cdef:
            list retval = []
        for market in market_list:
            try:
                symbol = market.get("symbol")
                min_trade_size = market.get("minTradeSize")
                precision = market.get("precision")
                # Trading Rules info from
                retval.append(TradingRule(symbol,
                                          min_order_size=Decimal(min_trade_size),
                                          min_price_increment=Decimal(f"1e-{precision}"),
                                          min_base_amount_increment=Decimal(f"1e-{precision}"),
                                          min_quote_amount_increment=Decimal(f"1e-{precision}"),
                                          ))
                # https://bittrex.zendesk.com/hc/en-us/articles/360001473863-Bittrex-Trading-Rules
                # "No maximum, but the user must have sufficient funds to cover the order at the time it is placed."
            except Exception:
                self.logger().error(f"Error parsing the symbol rule {market}. Skipping.", exc_info=True)
        return retval

    async def _update_trading_rules(self):
        cdef:
            # The poll interval for withdraw rules is 60 seconds.
            int64_t last_tick = <int64_t> (self._last_timestamp / 60.0)
            int64_t current_tick = <int64_t> (self._current_timestamp / 60.0)
        if current_tick > last_tick or len(self._trading_rules) <= 0:
            path_url = "/markets"
            market_list = await self._api_request("GET", path_url=path_url)
            trading_rules_list = self._format_trading_rules(market_list)
            self._trading_rules.clear()
            for trading_rule in trading_rules_list:
                self._trading_rules[trading_rule.symbol] = trading_rule

    async def list_orders(self) -> List[Any]:
        """
        Only a list of all currently open orders(does not include filled orders)
        :returns json response
        i.e.
        Result = [
              {
                "id": "string (uuid)",
                "marketSymbol": "string",
                "direction": "string",
                "type": "string",
                "quantity": "number (double)",
                "limit": "number (double)",
                "ceiling": "number (double)",
                "timeInForce": "string",
                "expiresAt": "string (date-time)",
                "clientOrderId": "string (uuid)",
                "fillQuantity": "number (double)",
                "commission": "number (double)",
                "proceeds": "number (double)",
                "status": "string",
                "createdAt": "string (date-time)",
                "updatedAt": "string (date-time)",
                "closedAt": "string (date-time)"
              }
              ...
            ]

        """
        path_url = "/orders/open"

        result = await self._api_request("GET", path_url=path_url)
        return result

    async def get_order(self, uuid: str) -> Dict[str, Any]:
        # Used to retrieve a single order by uuid
        """
        Result:
        {
          "id": "string (uuid)",
          "marketSymbol": "string",
          "direction": "string",
          "type": "string",
          "quantity": "number (double)",
          "limit": "number (double)",
          "ceiling": "number (double)",
          "timeInForce": "string",
          "expiresAt": "string (date-time)",
          "clientOrderId": "string (uuid)",
          "fillQuantity": "number (double)",
          "commission": "number (double)",
          "proceeds": "number (double)",
          "status": "string",
          "createdAt": "string (date-time)",
          "updatedAt": "string (date-time)",
          "closedAt": "string (date-time)"
        }
        """
        path_url = f"/orders/{uuid}"

        result = await self._api_request("GET", path_url=path_url)
        return result

    async def _update_order_fills_from_trades(self):
        cdef:
            # This is intended to be a backup measure to get filled events with trade ID for orders,
            # in case Bittrex's user stream events are not working.
            # This is separated from _update_order_status which only updates the order status without producing filled
            # events, since Bittrex's get order endpoint does not return trade IDs.
            # The poll interval for order status is 10 seconds.
            int64_t last_tick = <int64_t>(self._last_poll_timestamp / self.UPDATE_ORDERS_INTERVAL)
            int64_t current_tick = <int64_t>(self._current_timestamp / self.UPDATE_ORDERS_INTERVAL)

        if current_tick > last_tick and len(self._in_flight_orders) > 0:

            tracked_orders = list(self._in_flight_orders.values())
            open_orders = await self.list_orders()
            open_orders = dict((entry["id"], entry) for entry in open_orders)

            for tracked_order in tracked_orders:
                exchange_order_id = await tracked_order.get_exchange_order_id()
                client_order_id = tracked_order.client_order_id
                order = await self.get_order(exchange_order_id)

                if order is None:  # Handles order that are currently tracked but no longer open in exchange
                    self._order_not_found_records[client_order_id] = \
                        self._order_not_found_records.get(client_order_id, 0) + 1

                    if self._order_not_found_records[client_order_id] < self.ORDER_NOT_EXIST_CONFIRMATION_COUNT:
                        # Wait until the order not found error have repeated for a few times before actually treating
                        # it as a fail. See: https://github.com/CoinAlpha/hummingbot/issues/601
                        continue
                    tracked_order.last_state = "CLOSED"
                    self.c_trigger_event(
                        self.MARKET_ORDER_FAILURE_EVENT_TAG,
                        MarketOrderFailureEvent(self._current_timestamp,
                                                client_order_id,
                                                tracked_order.order_type)
                    )
                    self.c_stop_tracking_order(client_order_id)
                    self.logger().network(
                        f"Error fetching status update for the order {client_order_id}: "
                        f"{order}",
                        app_warning_msg=f"Could not fetch updates for the order {client_order_id}. "
                                        f"Check API key and network connection."
                    )
                    continue

                order_state = order["status"]
                order_type_description = tracked_order.order_type_description
                tracked_order.last_state = order_state

                executed_price = Decimal(order["limit"])
                executed_amount_diff = s_decimal_0

                remaining_size = Decimal(order["quantity"]) - Decimal(order["fillQuantity"])
                new_confirmed_amount = tracked_order.amount - remaining_size
                executed_amount_diff = new_confirmed_amount - tracked_order.executed_amount_base
                tracked_order.executed_amount_base = new_confirmed_amount
                tracked_order.executed_amount_quote += executed_amount_diff * executed_price

                if executed_amount_diff > s_decimal_0:
                    self.logger().info(f"Filled {executed_amount_diff} out of {tracked_order.amount} of the "
                                       f"{order_type_description} order {tracked_order.client_order_id}.")
                    self.c_trigger_event(self.MARKET_ORDER_FILLED_EVENT_TAG,
                                         OrderFilledEvent(
                                             self._current_timestamp,
                                             tracked_order.client_order_id,
                                             tracked_order.symbol,
                                             tracked_order.trade_type,
                                             tracked_order.order_type,
                                             float(executed_price),
                                             float(executed_amount_diff),
                                             self.c_get_fee(
                                                 tracked_order.base_asset,
                                                 tracked_order.quote_asset,
                                                 tracked_order.order_type,
                                                 tracked_order.trade_type,
                                                 float(executed_price),
                                                 float(executed_amount_diff)
                                             )
                                         ))

    async def _update_order_status(self):
        cdef:
            # This is intended to be a backup measure to close straggler orders, in case Bittrex's user stream events
            # are not capturing the updates as intended.
            # The poll interval for order status is 10 seconds.
            int64_t last_tick = <int64_t>(self._last_poll_timestamp / self.UPDATE_ORDERS_INTERVAL)
            int64_t current_tick = <int64_t>(self._current_timestamp / self.UPDATE_ORDERS_INTERVAL)

        if current_tick > last_tick and len(self._in_flight_orders) > 0:

            tracked_orders = list(self._in_flight_orders.values())
            open_orders = await self.list_orders()
            open_orders = dict((entry["id"], entry) for entry in open_orders)

            for tracked_order in tracked_orders:
                exchange_order_id = await tracked_order.get_exchange_order_id()
                client_order_id = tracked_order.client_order_id
                order = await self.get_order(exchange_order_id)

                if order is None:  # Handles order that are currently tracked but no longer open in exchange
                    self._order_not_found_records[client_order_id] = \
                        self._order_not_found_records.get(client_order_id, 0) + 1

                    if self._order_not_found_records[client_order_id] < self.ORDER_NOT_EXIST_CONFIRMATION_COUNT:
                        # Wait until the order not found error have repeated for a few times before actually treating
                        # it as a fail. See: https://github.com/CoinAlpha/hummingbot/issues/601
                        continue
                    self.c_trigger_event(
                        self.MARKET_ORDER_FAILURE_EVENT_TAG,
                        MarketOrderFailureEvent(self._current_timestamp,
                                                client_order_id,
                                                tracked_order.order_type)
                    )
                    self.c_stop_tracking_order(client_order_id)
                    self.logger().network(
                        f"Error fetching status update for the order {client_order_id}: "
                        f"{order}",
                        app_warning_msg=f"Could not fetch updates for the order {client_order_id}. "
                                        f"Check API key and network connection."
                    )
                    continue

                order_state = order["status"]
                order_type = "LIMIT" if tracked_order.order_type is OrderType.LIMIT else "MARKET"
                trade_type = "BUY" if tracked_order.trade_type is TradeType.BUY else "SELL"
                tracked_order.last_state = order_state
                if order_state == "CLOSED":
                    if order["quantity"] == order["fillQuantity"]:  # Order COMPLETED
                        self.logger().info(f"The {order_type}-{trade_type} "
                                           f"{client_order_id} has completed according to Bittrex order status API.")

                        if tracked_order.trade_type is TradeType.BUY:
                            self.c_trigger_event(self.MARKET_BUY_ORDER_COMPLETED_EVENT_TAG,
                                                 BuyOrderCompletedEvent(
                                                     self._current_timestamp,
                                                     tracked_order.client_order_id,
                                                     tracked_order.base_asset,
                                                     tracked_order.quote_asset,
                                                     (tracked_order.fee_asset
                                                      or tracked_order.base_asset),
                                                     float(tracked_order.executed_amount_base),
                                                     float(tracked_order.executed_amount_quote),
                                                     float(tracked_order.fee_paid),
                                                     tracked_order.order_type))
                        elif tracked_order.trade_type is TradeType.SELL:
                            self.c_trigger_event(self.MARKET_SELL_ORDER_COMPLETED_EVENT_TAG,
                                                 SellOrderCompletedEvent(
                                                     self._current_timestamp,
                                                     tracked_order.client_order_id,
                                                     tracked_order.base_asset,
                                                     tracked_order.quote_asset,
                                                     (tracked_order.fee_asset
                                                      or tracked_order.base_asset),
                                                     float(tracked_order.executed_amount_base),
                                                     float(tracked_order.executed_amount_quote),
                                                     float(tracked_order.fee_paid),
                                                     tracked_order.order_type))
                    else:  # Order PARTIAL-CANCEL or CANCEL
                        self.logger().info(f"The {tracked_order.order_type}-{tracked_order.trade_type} "
                                           f"{client_order_id} has been cancelled according to Bittrex order status API.")
                        self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                             OrderCancelledEvent(
                                                 self._current_timestamp,
                                                 client_order_id
                                             ))

                    self.c_stop_tracking_order(client_order_id)

    async def _iter_user_stream_queue(self) -> AsyncIterable[Dict[str, Any]]:
        while True:
            try:
                yield await self._user_stream_tracker.user_stream.get()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unknown error. Retrying after 1 second.", exc_info=True)
                await asyncio.sleep(1.0)

    async def _user_stream_event_listener(self):
        async for stream_message in self._iter_user_stream_queue():
            try:
                content = stream_message.content.get("content")
                event_type = stream_message.content.get("event_type")

                if event_type == "uB":  # Updates total balance and available balance of specified currency
                    asset_name = content["C"]
                    total_balance = content["b"]
                    available_balance = content["a"]
                    self._account_available_balances[asset_name] = available_balance
                    self._account_balances[asset_name] = total_balance
                elif event_type == "uO":  # Updates track order status
                    order = content["o"]
                    order_status = content["TY"]
                    order_id = order["OU"]

                    tracked_order = None
                    for o in self._in_flight_orders.values():
                        if o.exchange_order_id == order_id:
                            tracked_order = o
                            break

                    if tracked_order is None:
                        continue

                    order_type_description = tracked_order.order_type_description
                    execute_price = Decimal(order["PU"])
                    execute_amount_diff = s_decimal_0
                    tracked_order.fee_paid = Decimal(order["n"])

                    precision = str(self.c_get_order_size_quantum(tracked_order.symbol, Decimal(order['q'])))[-1]

                    remaining_size = Decimal(str(round(order["q"], int(precision))))

                    new_confirmed_amount = Decimal(tracked_order.amount - remaining_size)
                    execute_amount_diff = Decimal(new_confirmed_amount - tracked_order.executed_amount_base)
                    tracked_order.executed_amount_base = new_confirmed_amount
                    tracked_order.executed_amount_quote += Decimal(execute_amount_diff * execute_price)

                    if execute_amount_diff > s_decimal_0:
                        self.logger().info(f"Filled {execute_amount_diff} out of {tracked_order.amount} of the "
                                           f"{order_type_description} order {tracked_order.client_order_id}.")
                        self.c_trigger_event(self.MARKET_ORDER_FILLED_EVENT_TAG,
                                             OrderFilledEvent(
                                                 self._current_timestamp,
                                                 tracked_order.client_order_id,
                                                 tracked_order.symbol,
                                                 tracked_order.trade_type,
                                                 tracked_order.order_type,
                                                 float(execute_price),
                                                 float(execute_amount_diff),
                                                 self.c_get_fee(
                                                     tracked_order.base_asset,
                                                     tracked_order.quote_asset,
                                                     tracked_order.order_type,
                                                     tracked_order.trade_type,
                                                     float(execute_price),
                                                     float(execute_amount_diff)
                                                 )
                                             ))

                    if order_status == 2:  # FILL(COMPLETE)
                        # trade_type = TradeType.BUY if content["OT"] == "LIMIT_BUY" else TradeType.SELL
                        tracked_order.last_state = "done"
                        if tracked_order.trade_type is TradeType.BUY:
                            self.logger().info(f"The LIMIT_BUY order {tracked_order.client_order_id} has completed "
                                               f"according to order delta websocket API.")
                            self.c_trigger_event(self.MARKET_BUY_ORDER_COMPLETED_EVENT_TAG,
                                                 BuyOrderCompletedEvent(
                                                     self._current_timestamp,
                                                     tracked_order.client_order_id,
                                                     tracked_order.base_asset,
                                                     tracked_order.quote_asset,
                                                     (tracked_order.fee_asset
                                                      or tracked_order.quote_asset),
                                                     float(tracked_order.executed_amount_base),
                                                     float(tracked_order.executed_amount_quote),
                                                     float(tracked_order.fee_paid),
                                                     tracked_order.order_type
                                                 ))
                        elif tracked_order.trade_type is TradeType.SELL:
                            self.logger().info(f"The LIMIT_SELL order {tracked_order.client_order_id} has completed "
                                               f"according to Order Delta WebSocket API.")
                            self.c_trigger_event(self.MARKET_SELL_ORDER_COMPLETED_EVENT_TAG,
                                                 SellOrderCompletedEvent(self._current_timestamp,
                                                                         tracked_order.client_order_id,
                                                                         tracked_order.base_asset,
                                                                         tracked_order.quote_asset,
                                                                         (tracked_order.fee_asset
                                                                          or tracked_order.quote_asset),
                                                                         float(tracked_order.executed_amount_base),
                                                                         float(tracked_order.executed_amount_quote),
                                                                         float(tracked_order.fee_paid),
                                                                         tracked_order.order_type
                                                                         ))
                        self.c_stop_tracking_order(tracked_order.client_order_id)
                        continue

                    if order_status == 3:  # CANCEL
                        tracked_order.last_state = "cancelled"
                        self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                             OrderCancelledEvent(self._current_timestamp,
                                                                 tracked_order.client_order_id))
                        self.c_stop_tracking_order(tracked_order.client_order_id)
                else:
                    # Ignores all other user stream message types
                    continue

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
                    self._update_order_fills_from_trades()
                )
                self._last_poll_timestamp = self._current_timestamp
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network("Unexpected error while polling updates.",
                                      exc_info=True,
                                      app_warning_msg=f"Could not fetch updates from Bittrex. "
                                                      f"Check API key and network connection.")
                await asyncio.sleep(5.0)

    async def _trading_rules_polling_loop(self):
        while True:
            try:
                await self._update_trading_rules()
                await asyncio.sleep(60 * 5)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network("Unexpected error while fetching trading rule updates.",
                                      exc_info=True,
                                      app_warning_msg=f"Could not fetch updates from Bitrrex. "
                                                      f"Check API key and network connection.")
                await asyncio.sleep(0.5)

    async def get_order(self, client_order_id: str) -> Dict[str, Any]:
        order = self._in_flight_orders.get(client_order_id)
        exchange_order_id = await order.get_exchange_order_id()
        path_url = f"/order/{exchange_order_id}"
        result = await self._api_request("GET", path_url=path_url)
        return result

    async def get_deposit_address(self, currency: str) -> str:
        path_url = f"/addresses/{currency}"

        deposit_result = await self._api_request("GET", path_url=path_url)
        return deposit_result.get("cryptoAddress")

    async def get_deposit_info(self, asset: str) -> DepositInfo:
        return DepositInfo(await self.get_deposit_address(asset))

    cdef double c_get_balance(self, str currency) except? -1:
        return float(self._account_balances.get(currency, 0.0))

    cdef double c_get_available_balance(self, str currency) except? -1:
        return float(self._account_available_balances.get(currency, 0.0))

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
                                str symbol,
                                object order_type,
                                object trade_type,
                                object price,
                                object amount):
        self._in_flight_orders[order_id] = BittrexInFlightOrder(
            order_id,
            None,
            symbol,
            order_type,
            trade_type,
            price,
            amount
        )

    cdef c_stop_tracking_order(self, str order_id):
        if order_id in self._in_flight_orders:
            del self._in_flight_orders[order_id]

    cdef c_did_timeout_tx(self, str tracking_id):
        self.c_trigger_event(self.MARKET_TRANSACTION_FAILURE_EVENT_TAG,
                             MarketTransactionFailureEvent(self._current_timestamp, tracking_id))

    cdef object c_get_order_price_quantum(self, str symbol, object price):
        cdef:
            TradingRule trading_rule = self._trading_rules[symbol]
        return Decimal(trading_rule.min_price_increment)

    cdef object c_get_order_size_quantum(self, str symbol, object order_size):
        cdef:
            TradingRule trading_rule = self._trading_rules[symbol]
        return Decimal(trading_rule.min_base_amount_increment)

    cdef object c_quantize_order_amount(self, str symbol, object amount, object price=0.0):
        cdef:
            TradingRule trading_rule = self._trading_rules[symbol]
            object quantized_amount = MarketBase.c_quantize_order_amount(self, symbol, amount)

        global s_decimal_0
        if quantized_amount < trading_rule.min_order_size:
            return s_decimal_0

        return quantized_amount

    async def place_order(self,
                          order_id: str,
                          symbol: str,
                          amount: Decimal,
                          is_buy: bool,
                          order_type: OrderType,
                          price: Decimal) -> Dict[str, Any]:

        path_url = "/orders"

        body = {}
        if order_type is OrderType.LIMIT:  # Bittrex supports CEILING_LIMIT & CEILING_MARKET
            body = {
                "marketSymbol": str(symbol),
                "direction": "BUY" if is_buy else "SELL",
                "type": "LIMIT",
                "quantity": str(amount),
                "limit": str(price),
                "timeInForce": "GOOD_TIL_CANCELLED"
                # Available options [GOOD_TIL_CANCELLED, IMMEDIATE_OR_CANCEL,
                # FILL_OR_KILL, POST_ONLY_GOOD_TIL_CANCELLED]
            }
        elif order_type is OrderType.MARKET:
            body = {
                "marketSymbol": str(symbol),
                "direction": "BUY" if is_buy else "SELL",
                "type": "MARKET",
                "quantity": str(amount),
                "timeInForce": "IMMEDIATE_OR_CANCEL"
                # Available options [IMMEDIATE_OR_CANCEL, FILL_OR_KILL]
            }

        api_response = await self._api_request("POST", path_url=path_url, body=body)

        return api_response

    async def execute_buy(self,
                          order_id: str,
                          symbol: str,
                          amount: Decimal,
                          order_type: OrderType,
                          price: Optional[float] = NaN):
        cdef:
            TradingRule trading_rule = self._trading_rules[symbol]
            double quote_amount
            object decimal_amount
            object decimal_price
            str exchange_order_id
            object tracked_order

        decimal_amount = self.c_quantize_order_amount(symbol, amount)
        decimal_price = (self.c_quantize_order_price(symbol, price)
                         if order_type is OrderType.LIMIT
                         else s_decimal_0)

        if decimal_amount < trading_rule.min_order_size:
            raise ValueError(f"Buy order amount {decimal_amount} is lower than the minimum order size "
                             f"{trading_rule.min_order_size}.")

        try:
            self.c_start_tracking_order(order_id, symbol, order_type, TradeType.BUY, decimal_price, decimal_amount)
            order_result = None
            if order_type is OrderType.LIMIT:

                order_result = await self.place_order(order_id,
                                                      symbol,
                                                      decimal_amount,
                                                      True,
                                                      order_type,
                                                      decimal_price)

            elif order_type is OrderType.MARKET:
                decimal_price = self.c_get_price(symbol, True)
                order_result = await self.place_order(order_id,
                                                      symbol,
                                                      decimal_amount,
                                                      True,
                                                      order_type,
                                                      decimal_price)

            else:
                raise ValueError(f"Invalid OrderType {order_type}. Aborting.")

            exchange_order_id = order_result["id"]
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                order_type_str = "MARKET" if order_type == OrderType.MARKET else "LIMIT"
                self.logger().info(f"Created {order_type_str} buy order {order_id} for "
                                   f"{decimal_amount} {symbol}")
                tracked_order.update_exchange_order_id(exchange_order_id)
            self.c_trigger_event(self.MARKET_BUY_ORDER_CREATED_EVENT_TAG,
                                 BuyOrderCreatedEvent(
                                     self._current_timestamp,
                                     order_type,
                                     symbol,
                                     float(decimal_amount),
                                     float(decimal_price),
                                     order_id
                                 ))

        except asyncio.CancelledError:
            raise
        except Exception:
            tracked_order = self._in_flight_orders.get(order_id)
            tracked_order.last_state = "FAILURE"
            self.c_stop_tracking_order(order_id)
            order_type_str = "LIMIT" if order_type is OrderType.LIMIT else "MARKET"
            self.logger().network(
                f"Error submitting buy {order_type_str} order to Bittrex for "
                f"{decimal_amount} {symbol}"
                f"{decimal_price}.",
                exc_info=True,
                app_warning_msg=f"Failed to submit buy order to Bittrex. Check API key and network connection."
            )
            self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                 MarketOrderFailureEvent(
                                     self._current_timestamp,
                                     order_id,
                                     order_type
                                 ))

    cdef str c_buy(self,
                   str symbol,
                   object amount,
                   object order_type=OrderType.LIMIT,
                   object price=NaN,
                   dict kwargs={}):
        cdef:
            int64_t tracking_nonce = <int64_t> (time.time() * 1e6)
            str order_id = str(f"buy-{symbol}-{tracking_nonce}")
        safe_ensure_future(self.execute_buy(order_id, symbol, amount, order_type, price))
        return order_id

    async def execute_sell(self,
                           order_id: str,
                           symbol: str,
                           amount: Decimal,
                           order_type: OrderType = OrderType.LIMIT,
                           price: Optional[Decimal] = NaN):
        cdef:
            TradingRule trading_rule = self._trading_rules[symbol]
            double quote_amount
            object decimal_amount
            object decimal_price
            str exchange_order_id
            object tracked_order

        decimal_amount = self.c_quantize_order_amount(symbol, amount)
        decimal_price = (self.c_quantize_order_price(symbol, price)
                         if order_type is OrderType.LIMIT
                         else s_decimal_0)

        if decimal_amount < trading_rule.min_order_size:
            raise ValueError(f"Sell order amount {decimal_amount} is lower than the minimum order size "
                             f"{trading_rule.min_order_size}")

        try:
            self.c_start_tracking_order(order_id, symbol, order_type, TradeType.SELL, decimal_price, decimal_amount)
            order_result = None
            if order_type is OrderType.LIMIT:
                order_result = await self.place_order(order_id,
                                                      symbol,
                                                      decimal_amount,
                                                      False,
                                                      order_type,
                                                      decimal_price)
            elif order_type is OrderType.MARKET:
                decimal_price = self.c_get_price(symbol, False)
                order_result = await self.place_order(order_id,
                                                      symbol,
                                                      decimal_amount,
                                                      False,
                                                      order_type,
                                                      decimal_price)
            else:
                raise ValueError(f"Invalid OrderType {order_type}. Aborting.")

            exchange_order_id = order_result["id"]
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(f"Created {order_type} sell order {order_id} for "
                                   f"{decimal_amount} {symbol}.")
                tracked_order.update_exchange_order_id(exchange_order_id)
            self.c_trigger_event(self.MARKET_SELL_ORDER_CREATED_EVENT_TAG,
                                 SellOrderCreatedEvent(
                                     self._current_timestamp,
                                     order_type,
                                     symbol,
                                     float(decimal_amount),
                                     float(decimal_price),
                                     order_id
                                 ))
        except asyncio.CancelledError:
            raise
        except Exception:
            tracked_order = self._in_flight_orders.get(order_id)
            tracked_order.last_state = "FAILURE"
            self.c_stop_tracking_order(order_id)
            order_type_str = "LIMIT" if order_type is OrderType.LIMIT else "MARKET"
            self.logger().network(
                f"Error submitting sell {order_type_str} order to Bittrex for "
                f"{decimal_amount} {symbol}"
                f"{decimal_price if order_type is OrderType.LIMIT else ''}.",
                exc_info=True,
                app_warning_msg=f"Failed to submit sell order to Bittrex. Check API key and network connection."
            )
            self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                 MarketOrderFailureEvent(self._current_timestamp, order_id, order_type))

    cdef str c_sell(self,
                    str symbol,
                    object amount,
                    object order_type=OrderType.MARKET,
                    object price=0.0,
                    dict kwargs={}):
        cdef:
            int64_t tracking_nonce = <int64_t> (time.time() * 1e6)
            str order_id = str(f"sell-{symbol}-{tracking_nonce}")

        safe_ensure_future(self.execute_sell(order_id, symbol, amount, order_type, price))
        return order_id

    async def execute_cancel(self, symbol: str, order_id: str):
        tracked_order = self._in_flight_orders.get(order_id)
        if tracked_order is None:
            self.logger().error(f"The order {order_id} is not tracked. ")
            raise ValueError(f"Failed to cancel order - {order_id}. Order not found.")

        path_url = f"/orders/{tracked_order.exchange_order_id}"

        try:
            cancel_result = await self._api_request("DELETE", path_url=path_url)
            if cancel_result["status"] == "CLOSED":
                self.logger().info(f"Successfully cancelled order {order_id}.")
                tracked_order.last_state = "CANCELLED"
                self.c_stop_tracking_order(order_id)
                self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                     OrderCancelledEvent(self._current_timestamp, order_id))
                return order_id
        except IOError as err:
            if "NOT_FOUND" in str(err):
                # The order was never there to begin with. So cancelling it is a no-op but semantically successful.
                self.logger().info(f"The order {order_id} does not exist on Bittrex. No cancellation needed.")
                self.c_stop_tracking_order(order_id)
                self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                     OrderCancelledEvent(self._current_timestamp, order_id))
                return order_id
        except asyncio.CancelledError:
            raise
        except Exception as err:
            self.logger().network(
                f"Failed to cancel order {order_id}: {str(err)}.",
                exc_info=True,
                app_warning_msg=f"Failed to cancel the order {order_id} on Bittrex. "
                                f"Check API key and network connection."
            )
        return None

    cdef c_cancel(self, str symbol, str order_id):
        safe_ensure_future(self.execute_cancel(symbol, order_id))
        return order_id

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        incomplete_orders = [order for order in self._in_flight_orders.values() if not order.is_done]
        tasks = [self.execute_cancel(o.symbol, o.client_order_id) for o in incomplete_orders]
        order_id_set = set([o.client_order_id for o in incomplete_orders])
        successful_cancellation = []

        try:
            async with timeout(timeout_seconds):
                api_responses = await safe_gather(*tasks, return_exceptions=True)
                for order_id in api_responses:
                    if order_id:
                        order_id_set.remove(order_id)
                        successful_cancellation.append(CancellationResult(order_id, True))
        except Exception:
            self.logger().network(
                f"Unexpected error cancelling orders.",
                exc_info=True,
                app_warning_msg="Failed to cancel order on Bittrex. Check API key and network connection."
            )

        failed_cancellation = [CancellationResult(oid, False) for oid in order_id_set]
        return successful_cancellation + failed_cancellation

    async def _http_client(self) -> aiohttp.ClientSession:
        if self._shared_client is None:
            self._shared_client = aiohttp.ClientSession()
        return self._shared_client

    async def _api_request(self,
                           http_method: str,
                           path_url: str = None,
                           params: Dict[str, any] = None,
                           body: Dict[str, any] = None,
                           subaccount_id: str = '') -> Dict[str, Any]:
        assert path_url is not None

        url = f"{self.BITTREX_API_ENDPOINT}{path_url}"

        auth_dict = self.bittrex_auth.generate_auth_dict(http_method, url, params, body, subaccount_id)

        # Updates the headers and params accordingly
        headers = auth_dict["headers"]

        if body:
            body = auth_dict["body"]  # Ensures the body is the same as that signed in Api-Content-Hash

        client = await self._http_client()
        async with client.request(http_method,
                                  url=url,
                                  headers=headers,
                                  params=params,
                                  data=body,
                                  timeout=self.API_CALL_TIMEOUT) as response:
            data = await response.json()
            if response.status not in [200, 201]:  # HTTP Response code of 20X generally means it is successful
                raise IOError(f"Error fetching response from {http_method}-{url}. HTTP Status Code {response.status}: "
                              f"{data}")
            return data

    async def check_network(self) -> NetworkStatus:
        try:
            await self._api_request("GET", path_url="/ping")
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    def _stop_network(self):
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
        self._stop_network()

    async def start_network(self):
        if self._order_tracker_task is not None:
            self._stop_network()

        self._order_tracker_task = safe_ensure_future(self._order_book_tracker.start())
        self._trading_rules_polling_task = safe_ensure_future(self._trading_rules_polling_loop())
        if self._trading_required:
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())
            self._user_stream_tracker_task = safe_ensure_future(self._user_stream_tracker.start())
            self._user_stream_event_listener_task = safe_ensure_future(self._user_stream_event_listener())
