import asyncio
import logging

from decimal import Decimal
from typing import Any, AsyncIterable, Dict, List, Optional

import aiohttp
from async_timeout import timeout
from libc.stdint cimport int64_t

from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.connector.exchange.bittrex.bittrex_auth import BittrexAuth
from hummingbot.connector.exchange.bittrex.bittrex_in_flight_order import BittrexInFlightOrder
from hummingbot.connector.exchange.bittrex.bittrex_order_book_tracker import BittrexOrderBookTracker
from hummingbot.connector.exchange.bittrex.bittrex_user_stream_tracker import BittrexUserStreamTracker
from hummingbot.connector.trading_rule cimport TradingRule
from hummingbot.core.clock cimport Clock
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketEvent,
    MarketOrderFailureEvent,
    MarketTransactionFailureEvent,
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
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce
from hummingbot.logger import HummingbotLogger

bm_logger = None
s_decimal_0 = Decimal(0)
s_decimal_NaN = Decimal("NaN")
NaN = float("nan")


cdef class BittrexExchangeTransactionTracker(TransactionTracker):
    cdef:
        BittrexExchange _owner

    def __init__(self, owner: BittrexExchange):
        super().__init__()
        self._owner = owner

    cdef c_did_timeout_tx(self, str tx_id):
        TransactionTracker.c_did_timeout_tx(self, tx_id)
        self._owner.c_did_timeout_tx(tx_id)

cdef class BittrexExchange(ExchangeBase):
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
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True):
        super().__init__()
        self._account_available_balances = {}
        self._account_balances = {}
        self._account_id = ""
        self._bittrex_auth = BittrexAuth(bittrex_api_key, bittrex_secret_key)
        self._ev_loop = asyncio.get_event_loop()
        self._in_flight_orders = {}
        self._last_poll_timestamp = 0
        self._last_timestamp = 0
        self._order_book_tracker = BittrexOrderBookTracker(trading_pairs=trading_pairs)
        self._order_not_found_records = {}
        self._poll_notifier = asyncio.Event()
        self._poll_interval = poll_interval
        self._shared_client = None
        self._status_polling_task = None
        self._trading_required = trading_required
        self._trading_rules = {}
        self._trading_rules_polling_task = None
        self._tx_tracker = BittrexExchangeTransactionTracker(self)
        self._user_stream_event_listener_task = None
        self._user_stream_tracker = BittrexUserStreamTracker(bittrex_auth=self._bittrex_auth,
                                                             trading_pairs=trading_pairs)
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

    @property
    def in_flight_orders(self) -> Dict[str, BittrexInFlightOrder]:
        return self._in_flight_orders

    @property
    def user_stream_tracker(self) -> BittrexUserStreamTracker:
        return self._user_stream_tracker

    def restore_tracking_states(self, saved_states: Dict[str, any]):
        self._in_flight_orders.update({
            key: BittrexInFlightOrder.from_json(value)
            for key, value in saved_states.items()
        })

    cdef c_start(self, Clock clock, double timestamp):
        self._tx_tracker.c_start(clock, timestamp)
        ExchangeBase.c_start(self, clock, timestamp)

    cdef c_tick(self, double timestamp):
        cdef:
            int64_t last_tick = <int64_t> (self._last_timestamp / self._poll_interval)
            int64_t current_tick = <int64_t> (timestamp / self._poll_interval)

        ExchangeBase.c_tick(self, timestamp)
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
                          object price,
                          object is_maker = None):
        # There is no API for checking fee
        # Fee info from https://bittrex.zendesk.com/hc/en-us/articles/115003684371
        is_maker = order_type is OrderType.LIMIT_MAKER
        return estimate_fee("bittrex", is_maker)

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

    def _format_trading_rules(self, market_dict: Dict[str, Any]) -> List[TradingRule]:
        cdef:
            list retval = []

            object eth_btc_price = Decimal(market_dict["ETH-BTC"]["lastTradeRate"])
            object btc_usd_price = Decimal(market_dict["BTC-USD"]["lastTradeRate"])
            object btc_usdt_price = Decimal(market_dict["BTC-USDT"]["lastTradeRate"])

        for market in market_dict.values():
            try:
                trading_pair = market.get("symbol")
                min_trade_size = market.get("minTradeSize")
                precision = market.get("precision")
                last_trade_rate = Decimal(market.get("lastTradeRate"))

                # skip offline trading pair
                if market.get("status") != "OFFLINE":

                    # Trading Rules info from Bittrex API response
                    retval.append(TradingRule(trading_pair,
                                              min_order_size=Decimal(min_trade_size),
                                              min_price_increment=Decimal(f"1e-{precision}"),
                                              min_base_amount_increment=Decimal(f"1e-{precision}"),
                                              min_quote_amount_increment=Decimal(f"1e-{precision}")
                                              ))
                    # https://bittrex.zendesk.com/hc/en-us/articles/360001473863-Bittrex-Trading-Rules
                    # "No maximum, but the user must have sufficient funds to cover the order at the time it is placed."
            except Exception:
                self.logger().error(f"Error parsing the trading pair rule {market}. Skipping.", exc_info=True)
        return retval

    async def _update_trading_rules(self):
        cdef:
            # The poll interval for withdraw rules is 60 seconds.
            int64_t last_tick = <int64_t> (self._last_timestamp / 60.0)
            int64_t current_tick = <int64_t> (self._current_timestamp / 60.0)
        if current_tick > last_tick or len(self._trading_rules) <= 0:
            market_path_url = "/markets"
            ticker_path_url = "/markets/tickers"

            market_list = await self._api_request("GET", path_url=market_path_url)

            ticker_list = await self._api_request("GET", path_url=ticker_path_url)
            ticker_data = {item["symbol"]: item for item in ticker_list}

            result_list = [
                {**market, **ticker_data[market["symbol"]]}
                for market in market_list
                if market["symbol"] in ticker_data
            ]

            result_list = {market["symbol"]: market for market in result_list}

            trading_rules_list = self._format_trading_rules(result_list)
            self._trading_rules.clear()
            for trading_rule in trading_rules_list:
                self._trading_rules[trading_rule.trading_pair] = trading_rule

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

    async def _update_order_status(self):
        cdef:
            # This is intended to be a backup measure to close straggler orders, in case Bittrex's user stream events
            # are not capturing the updates as intended. Also handles filled events that are not captured by
            # _user_stream_event_listener
            # The poll interval for order status is 10 seconds.
            int64_t last_tick = <int64_t> (self._last_poll_timestamp / self.UPDATE_ORDERS_INTERVAL)
            int64_t current_tick = <int64_t> (self._current_timestamp / self.UPDATE_ORDERS_INTERVAL)

        if current_tick > last_tick and len(self._in_flight_orders) > 0:

            tracked_orders = list(self._in_flight_orders.values())
            open_orders = await self.list_orders()
            open_orders = dict((entry["id"], entry) for entry in open_orders)

            for tracked_order in tracked_orders:
                try:
                    exchange_order_id = await tracked_order.get_exchange_order_id()
                except asyncio.TimeoutError:
                    if tracked_order.last_state == "FAILURE":
                        self.c_stop_tracking_order(client_order_id)
                        self.logger().warning(
                            f"No exchange ID found for {client_order_id} on order status update."
                            f" Order no longer tracked. This is most likely due to a POST_ONLY_NOT_MET error."
                        )
                        continue
                    else:
                        self.logger().error(f"Exchange order ID never updated for {tracked_order.client_order_id}")
                        raise
                client_order_id = tracked_order.client_order_id
                order = open_orders.get(exchange_order_id)

                # Do nothing, if the order has already been cancelled or has failed
                if client_order_id not in self._in_flight_orders:
                    continue

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
                        f"{tracked_order}",
                        app_warning_msg=f"Could not fetch updates for the order {client_order_id}. "
                                        f"Check API key and network connection."
                    )
                    continue

                order_state = order["status"]
                order_type = tracked_order.order_type.name.lower()
                trade_type = tracked_order.trade_type.name.lower()
                order_type_description = tracked_order.order_type_description

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
                                             tracked_order.trading_pair,
                                             tracked_order.trade_type,
                                             tracked_order.order_type,
                                             executed_price,
                                             executed_amount_diff,
                                             self.c_get_fee(
                                                 tracked_order.base_asset,
                                                 tracked_order.quote_asset,
                                                 tracked_order.order_type,
                                                 tracked_order.trade_type,
                                                 executed_price,
                                                 executed_amount_diff
                                             )
                                         ))

                if order_state == "CLOSED":
                    self._process_api_closed(order, tracked_order)

    def _process_api_closed(self, order: Dict, tracked_order: BittrexInFlightOrder):
        order_type = tracked_order.order_type
        trade_type = tracked_order.trade_type
        client_order_id = tracked_order.client_order_id
        if order["quantity"] == order["fillQuantity"]:  # Order COMPLETED
            tracked_order.last_state = "CLOSED"
            self.logger().info(f"The {order_type}-{trade_type} "
                               f"{client_order_id} has completed according to Bittrex order status API.")

            if tracked_order.trade_type is TradeType.BUY:
                self.c_trigger_event(self.MARKET_BUY_ORDER_COMPLETED_EVENT_TAG,
                                     BuyOrderCompletedEvent(
                                         self._current_timestamp,
                                         tracked_order.client_order_id,
                                         tracked_order.base_asset,
                                         tracked_order.quote_asset,
                                         tracked_order.fee_asset or tracked_order.base_asset,
                                         tracked_order.executed_amount_base,
                                         tracked_order.executed_amount_quote,
                                         tracked_order.fee_paid,
                                         tracked_order.order_type))
            elif tracked_order.trade_type is TradeType.SELL:
                self.c_trigger_event(self.MARKET_SELL_ORDER_COMPLETED_EVENT_TAG,
                                     SellOrderCompletedEvent(
                                         self._current_timestamp,
                                         tracked_order.client_order_id,
                                         tracked_order.base_asset,
                                         tracked_order.quote_asset,
                                         tracked_order.fee_asset or tracked_order.base_asset,
                                         tracked_order.executed_amount_base,
                                         tracked_order.executed_amount_quote,
                                         tracked_order.fee_paid,
                                         tracked_order.order_type))
        else:  # Order PARTIAL-CANCEL or CANCEL
            tracked_order.last_state = "CANCELLED"
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
                content = stream_message.get("content")
                event_type = stream_message.get("event_type")

                if event_type == "balance":  # Updates total balance and available balance of specified currency
                    balance_delta = content["delta"]
                    asset_name = balance_delta["currencySymbol"]
                    total_balance = Decimal(balance_delta["total"])
                    available_balance = Decimal(balance_delta["available"])
                    self._account_available_balances[asset_name] = available_balance
                    self._account_balances[asset_name] = total_balance
                elif event_type == "order":  # Updates track order status
                    safe_ensure_future(self._process_order_update_event(stream_message))
                elif event_type == "execution":
                    safe_ensure_future(self._process_execution_event(stream_message))

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await asyncio.sleep(5.0)

    async def _process_order_update_event(self, stream_message: Dict[str, Any]):
        content = stream_message["content"]
        order = content["delta"]
        order_status = order["status"]
        order_id = order["id"]
        tracked_order: BittrexInFlightOrder = None

        for o in self._in_flight_orders.values():
            exchange_order_id = await o.get_exchange_order_id()
            if exchange_order_id == order_id:
                tracked_order = o
                break

        if tracked_order and order_status == "CLOSED":
            if order["quantity"] == order["fillQuantity"]:
                tracked_order.last_state = "done"
                event = (self.MARKET_BUY_ORDER_COMPLETED_EVENT_TAG
                         if tracked_order.trade_type == TradeType.BUY
                         else self.MARKET_SELL_ORDER_COMPLETED_EVENT_TAG)
                event_class = (BuyOrderCompletedEvent
                               if tracked_order.trade_type == TradeType.BUY
                               else SellOrderCompletedEvent)

                try:
                    await asyncio.wait_for(tracked_order.wait_until_completely_filled(), timeout=1)
                except asyncio.TimeoutError:
                    fee_asset = tracked_order.quote_asset
                    fee = self.get_fee(
                        tracked_order.base_asset,
                        tracked_order.quote_asset,
                        tracked_order.order_type,
                        tracked_order.trade_type,
                        tracked_order.amount,
                        tracked_order.price)
                    fee_amount = fee.fee_amount_in_quote(tracked_order.trading_pair,
                                                         tracked_order.price,
                                                         tracked_order.amount,
                                                         self)
                else:
                    fee_asset = tracked_order.fee_asset or tracked_order.quote_asset
                    fee_amount = tracked_order.fee_paid

                self.logger().info(f"The {tracked_order.trade_type.name} order {tracked_order.client_order_id} "
                                   f"has completed according to order delta websocket API.")
                self.c_trigger_event(event,
                                     event_class(
                                         self._current_timestamp,
                                         tracked_order.client_order_id,
                                         tracked_order.base_asset,
                                         tracked_order.quote_asset,
                                         fee_asset,
                                         tracked_order.executed_amount_base,
                                         tracked_order.executed_amount_quote,
                                         fee_amount,
                                         tracked_order.order_type
                                     ))
                self.c_stop_tracking_order(tracked_order.client_order_id)

            else:  # CANCEL
                self.logger().info(f"The order {tracked_order.client_order_id} has been cancelled "
                                   f"according to Order Delta WebSocket API.")
                tracked_order.last_state = "cancelled"
                self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                     OrderCancelledEvent(self._current_timestamp,
                                                         tracked_order.client_order_id))
                self.c_stop_tracking_order(tracked_order.client_order_id)

    async def _process_execution_event(self, stream_message: Dict[str, Any]):
        content = stream_message["content"]
        events = content["deltas"]

        for execution_event in events:
            order_id = execution_event["orderId"]

            tracked_order = None
            for order in self._in_flight_orders.values():
                exchange_order_id = await order.get_exchange_order_id()
                if exchange_order_id == order_id:
                    tracked_order = order
                    break

            if tracked_order:
                updated = tracked_order.update_with_trade_update(execution_event)

                if updated:
                    self.logger().info(f"Filled {Decimal(execution_event['quantity'])} out of "
                                       f"{tracked_order.amount} of the "
                                       f"{tracked_order.order_type_description} order "
                                       f"{tracked_order.client_order_id}. - ws")
                    self.c_trigger_event(self.MARKET_ORDER_FILLED_EVENT_TAG,
                                         OrderFilledEvent(
                                             self._current_timestamp,
                                             tracked_order.client_order_id,
                                             tracked_order.trading_pair,
                                             tracked_order.trade_type,
                                             tracked_order.order_type,
                                             Decimal(execution_event["rate"]),
                                             Decimal(execution_event["quantity"]),
                                             AddedToCostTradeFee(
                                                 flat_fees=[
                                                     TokenAmount(
                                                         tracked_order.fee_asset, Decimal(execution_event["commission"])
                                                     )
                                                 ]
                                             ),
                                             exchange_trade_id=execution_event["id"]
                                         ))

    async def _status_polling_loop(self):
        while True:
            try:
                self._poll_notifier = asyncio.Event()
                await self._poll_notifier.wait()

                await safe_gather(
                    self._update_balances(),
                    self._update_order_status(),
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

    cdef OrderBook c_get_order_book(self, str trading_pair):
        cdef:
            dict order_books = self._order_book_tracker.order_books

        if trading_pair not in order_books:
            raise ValueError(f"No order book exists for '{trading_pair}'.")
        return order_books[trading_pair]

    def start_tracking_order(self,
                             order_id: str,
                             exchange_order_id: str,
                             trading_pair: str,
                             order_type: OrderType,
                             trade_type: TradeType,
                             price: Decimal,
                             amount: Decimal):
        """Helper method for testing."""
        self.c_start_tracking_order(order_id, exchange_order_id, trading_pair, order_type, trade_type, price, amount)

    cdef c_start_tracking_order(self,
                                str order_id,
                                str exchange_order_id,
                                str trading_pair,
                                object order_type,
                                object trade_type,
                                object price,
                                object amount):
        self._in_flight_orders[order_id] = BittrexInFlightOrder(
            order_id,
            exchange_order_id,
            trading_pair,
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

    cdef object c_get_order_price_quantum(self, str trading_pair, object price):
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]
        return Decimal(trading_rule.min_price_increment)

    cdef object c_get_order_size_quantum(self, str trading_pair, object order_size):
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]
        return Decimal(trading_rule.min_base_amount_increment)

    cdef object c_quantize_order_amount(self, str trading_pair, object amount, object price=0.0):
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]
            object quantized_amount = ExchangeBase.c_quantize_order_amount(self, trading_pair, amount)

        global s_decimal_0
        if quantized_amount < trading_rule.min_order_size:
            return s_decimal_0

        return quantized_amount

    def supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER]

    async def place_order(self,
                          order_id: str,
                          trading_pair: str,
                          amount: Decimal,
                          is_buy: bool,
                          order_type: OrderType,
                          price: Decimal) -> Dict[str, Any]:

        path_url = "/orders"

        body = {}
        if order_type is OrderType.LIMIT:  # Bittrex supports CEILING_LIMIT & CEILING_MARKET
            body = {
                "marketSymbol": str(trading_pair),
                "direction": "BUY" if is_buy else "SELL",
                "type": "LIMIT",
                "quantity": f"{amount:f}",
                "limit": f"{price:f}",
                "timeInForce": "GOOD_TIL_CANCELLED"
                # Available options [GOOD_TIL_CANCELLED, IMMEDIATE_OR_CANCEL,
                # FILL_OR_KILL, POST_ONLY_GOOD_TIL_CANCELLED]
            }
        elif order_type is OrderType.LIMIT_MAKER:
            body = {
                "marketSymbol": str(trading_pair),
                "direction": "BUY" if is_buy else "SELL",
                "type": "LIMIT",
                "quantity": f"{amount:f}",
                "limit": f"{price:f}",
                "timeInForce": "POST_ONLY_GOOD_TIL_CANCELLED"
            }
        api_response = await self._api_request("POST", path_url=path_url, body=body)
        return api_response

    async def execute_buy(self,
                          order_id: str,
                          trading_pair: str,
                          amount: Decimal,
                          order_type: OrderType,
                          price: Optional[Decimal] = s_decimal_0):
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]
            double quote_amount
            object decimal_amount
            object decimal_price
            str exchange_order_id
            object tracked_order

        decimal_amount = self.c_quantize_order_amount(trading_pair, amount)
        if order_type is OrderType.LIMIT or order_type is OrderType.LIMIT_MAKER:
            decimal_price = self.c_quantize_order_price(trading_pair, price)
        else:
            decimal_price = s_decimal_0

        if decimal_amount < trading_rule.min_order_size:
            raise ValueError(f"Buy order amount {decimal_amount} is lower than the minimum order size "
                             f"{trading_rule.min_order_size}.")

        try:
            order_result = None
            self.c_start_tracking_order(
                order_id,
                None,
                trading_pair,
                order_type,
                TradeType.BUY,
                decimal_price,
                decimal_amount
            )
            if order_type is OrderType.LIMIT or order_type is OrderType.LIMIT_MAKER:
                order_result = await self.place_order(order_id,
                                                      trading_pair,
                                                      decimal_amount,
                                                      True,
                                                      order_type,
                                                      decimal_price)
            else:
                raise ValueError(f"Invalid OrderType {order_type}. Aborting.")

            exchange_order_id = order_result["id"]

            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None and exchange_order_id:
                tracked_order.update_exchange_order_id(exchange_order_id)
                order_type_str = order_type.name.lower()
                self.logger().info(f"Created {order_type_str} buy order {order_id} for "
                                   f"{decimal_amount} {trading_pair}")
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
        except Exception:
            tracked_order = self._in_flight_orders.get(order_id)
            tracked_order.last_state = "FAILURE"
            self.c_stop_tracking_order(order_id)
            order_type_str = order_type.name.lower()
            self.logger().network(
                f"Error submitting buy {order_type_str} order to Bittrex for "
                f"{decimal_amount} {trading_pair} "
                f"{decimal_price if order_type in [OrderType.LIMIT, OrderType.LIMIT_MAKER] else ''}.",
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
                   str trading_pair,
                   object amount,
                   object order_type=OrderType.LIMIT,
                   object price=NaN,
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
                           order_type: OrderType = OrderType.LIMIT,
                           price: Optional[Decimal] = NaN):
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]
            double quote_amount
            object decimal_amount
            object decimal_price
            str exchange_order_id
            object tracked_order

        decimal_amount = self.c_quantize_order_amount(trading_pair, amount)
        if order_type is OrderType.LIMIT or order_type is OrderType.LIMIT_MAKER:
            decimal_price = self.c_quantize_order_price(trading_pair, price)
        else:
            decimal_price = s_decimal_0

        if decimal_amount < trading_rule.min_order_size:
            raise ValueError(f"Sell order amount {decimal_amount} is lower than the minimum order size "
                             f"{trading_rule.min_order_size}")

        try:
            order_result = None

            self.c_start_tracking_order(
                order_id,
                None,
                trading_pair,
                order_type,
                TradeType.SELL,
                decimal_price,
                decimal_amount
            )

            if order_type is OrderType.LIMIT or order_type is OrderType.LIMIT_MAKER:
                order_result = await self.place_order(order_id,
                                                      trading_pair,
                                                      decimal_amount,
                                                      False,
                                                      order_type,
                                                      decimal_price)
            else:
                raise ValueError(f"Invalid OrderType {order_type}. Aborting.")

            exchange_order_id = order_result["id"]
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None and exchange_order_id:
                tracked_order.update_exchange_order_id(exchange_order_id)
                order_type_str = order_type.name.lower()
                self.logger().info(f"Created {order_type_str} sell order {order_id} for "
                                   f"{decimal_amount} {trading_pair}.")
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
            tracked_order = self._in_flight_orders.get(order_id)
            tracked_order.last_state = "FAILURE"
            self.c_stop_tracking_order(order_id)
            order_type_str = order_type.name.lower()
            self.logger().network(
                f"Error submitting sell {order_type_str} order to Bittrex for "
                f"{decimal_amount} {trading_pair} "
                f"{decimal_price if order_type in [OrderType.LIMIT, OrderType.LIMIT_MAKER] else ''}.",
                exc_info=True,
                app_warning_msg=f"Failed to submit sell order to Bittrex. Check API key and network connection."
            )
            self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                 MarketOrderFailureEvent(self._current_timestamp, order_id, order_type))

    cdef str c_sell(self,
                    str trading_pair,
                    object amount,
                    object order_type=OrderType.LIMIT,
                    object price=0.0,
                    dict kwargs={}):
        cdef:
            int64_t tracking_nonce = <int64_t> get_tracking_nonce()
            str order_id = str(f"sell-{trading_pair}-{tracking_nonce}")

        safe_ensure_future(self.execute_sell(order_id, trading_pair, amount, order_type, price))
        return order_id

    async def execute_cancel(self, trading_pair: str, order_id: str):
        try:
            tracked_order = self._in_flight_orders.get(order_id)

            if tracked_order is None:
                self.logger().error(f"The order {order_id} is not tracked. ")
                raise ValueError
            path_url = f"/orders/{tracked_order.exchange_order_id}"

            cancel_result = await self._api_request("DELETE", path_url=path_url)
            if cancel_result["status"] == "CLOSED":
                self.logger().info(f"Successfully cancelled order {order_id}.")
                tracked_order.last_state = "CANCELLED"
                self.c_stop_tracking_order(order_id)
                self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                     OrderCancelledEvent(self._current_timestamp, order_id))
                return order_id
        except asyncio.CancelledError:
            raise
        except Exception as err:
            if "NOT_FOUND" in str(err):
                # The order was never there to begin with. So cancelling it is a no-op but semantically successful.
                self.logger().info(f"The order {order_id} does not exist on Bittrex. No cancellation needed.")
                self.c_stop_tracking_order(order_id)
                self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                     OrderCancelledEvent(self._current_timestamp, order_id))
                return order_id

            if "ORDER_NOT_OPEN" in str(err):
                state_result = await self._api_request("GET", path_url=path_url)
                self.logger().error(  # this indicates a potential error
                    f"Tried to cancel order {order_id} which is already closed. Order details: {state_result}."
                )
                if state_result["status"] == "CLOSED":
                    self._process_api_closed(state_result, tracked_order)
                return order_id

            self.logger().network(
                f"Failed to cancel order {order_id}: {str(err)}.",
                exc_info=True,
                app_warning_msg=f"Failed to cancel the order {order_id} on Bittrex. "
                                f"Check API key and network connection."
            )
        return None

    cdef c_cancel(self, str trading_pair, str order_id):
        safe_ensure_future(self.execute_cancel(trading_pair, order_id))
        return order_id

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        incomplete_orders = [order for order in self._in_flight_orders.values() if not order.is_done]
        tasks = [self.execute_cancel(o.trading_pair, o.client_order_id) for o in incomplete_orders]
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
        self._order_book_tracker.stop()
        if self._status_polling_task is not None:
            self._status_polling_task.cancel()
        if self._user_stream_tracker_task is not None:
            self._user_stream_tracker_task.cancel()
        if self._user_stream_event_listener_task is not None:
            self._user_stream_event_listener_task.cancel()
        self._status_polling_task = self._user_stream_tracker_task = \
            self._user_stream_event_listener_task = None

    async def stop_network(self):
        self._stop_network()

    async def start_network(self):
        self._stop_network()
        self._order_book_tracker.start()
        self._trading_rules_polling_task = safe_ensure_future(self._trading_rules_polling_loop())
        if self._trading_required:
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())
            self._user_stream_tracker_task = safe_ensure_future(self._user_stream_tracker.start())
            self._user_stream_event_listener_task = safe_ensure_future(self._user_stream_event_listener())

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
                price: Decimal = s_decimal_NaN,
                is_maker: Optional[bool] = None) -> AddedToCostTradeFee:
        return self.c_get_fee(base_currency, quote_currency, order_type, order_side, amount, price, is_maker)

    def get_order_book(self, trading_pair: str) -> OrderBook:
        return self.c_get_order_book(trading_pair)
