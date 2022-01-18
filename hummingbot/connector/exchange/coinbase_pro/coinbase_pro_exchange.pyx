import asyncio
import copy
import logging
from decimal import Decimal
from typing import Any, AsyncIterable, Dict, List, Optional

from async_timeout import timeout
from libc.stdint cimport int64_t

from hummingbot.connector.exchange.coinbase_pro import coinbase_pro_constants as CONSTANTS
from hummingbot.connector.exchange.coinbase_pro.coinbase_pro_auth import CoinbaseProAuth
from hummingbot.connector.exchange.coinbase_pro.coinbase_pro_in_flight_order cimport CoinbaseProInFlightOrder
from hummingbot.connector.exchange.coinbase_pro.coinbase_pro_in_flight_order import CoinbaseProInFlightOrder
from hummingbot.connector.exchange.coinbase_pro.coinbase_pro_order_book_tracker import CoinbaseProOrderBookTracker
from hummingbot.connector.exchange.coinbase_pro.coinbase_pro_user_stream_tracker import CoinbaseProUserStreamTracker
from hummingbot.connector.exchange.coinbase_pro.coinbase_pro_utils import (
    CoinbaseProRESTRequest,
    build_coinbase_pro_web_assistant_factory
)
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.connector.trading_rule cimport TradingRule
from hummingbot.core.clock cimport Clock
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.transaction_tracker import TransactionTracker
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
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.utils.estimate_fee import estimate_fee
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.rest_assistant import RESTAssistant
from hummingbot.logger import HummingbotLogger

s_logger = None
s_decimal_0 = Decimal("0.0")
s_decimal_nan = Decimal("nan")

cdef class CoinbaseProExchangeTransactionTracker(TransactionTracker):
    cdef:
        CoinbaseProExchange _owner

    def __init__(self, owner: CoinbaseProExchange):
        super().__init__()
        self._owner = owner

    cdef c_did_timeout_tx(self, str tx_id):
        TransactionTracker.c_did_timeout_tx(self, tx_id)
        self._owner.c_did_timeout_tx(tx_id)


cdef class CoinbaseProExchange(ExchangeBase):
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
    UPDATE_FEE_PERCENTAGE_INTERVAL = 60.0
    MAKER_FEE_PERCENTAGE_DEFAULT = 0.005
    TAKER_FEE_PERCENTAGE_DEFAULT = 0.005

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(__name__)
        return s_logger

    def __init__(self,
                 coinbase_pro_api_key: str,
                 coinbase_pro_secret_key: str,
                 coinbase_pro_passphrase: str,
                 poll_interval: float = 5.0,    # interval which the class periodically pulls status from the rest API
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True):
        super().__init__()
        self._trading_required = trading_required
        auth = CoinbaseProAuth(coinbase_pro_api_key, coinbase_pro_secret_key, coinbase_pro_passphrase)
        self._web_assistants_factory = build_coinbase_pro_web_assistant_factory(auth)
        self._order_book_tracker = CoinbaseProOrderBookTracker(trading_pairs, self._web_assistants_factory)
        self._user_stream_tracker = CoinbaseProUserStreamTracker(
            trading_pairs=trading_pairs,
            web_assistants_factory=self._web_assistants_factory,
        )
        self._ev_loop = asyncio.get_event_loop()
        self._poll_notifier = asyncio.Event()
        self._last_timestamp = 0
        self._last_order_update_timestamp = 0
        self._last_fee_percentage_update_timestamp = 0
        self._poll_interval = poll_interval
        self._in_flight_orders = {}
        self._tx_tracker = CoinbaseProExchangeTransactionTracker(self)
        self._trading_rules = {}
        self._status_polling_task = None
        self._user_stream_tracker_task = None
        self._user_stream_event_listener_task = None
        self._trading_rules_polling_task = None
        self._rest_assistant = None
        self._maker_fee_percentage = Decimal(self.MAKER_FEE_PERCENTAGE_DEFAULT)
        self._taker_fee_percentage = Decimal(self.TAKER_FEE_PERCENTAGE_DEFAULT)
        self._real_time_balance_update = False

    @property
    def name(self) -> str:
        """
        *required
        :return: A lowercase name / id for the market. Must stay consistent with market name in global settings.
        """
        return "coinbase_pro"

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        """
        *required
        Get mapping of all the order books that are being tracked.
        :return: Dict[trading_pair : OrderBook]
        """
        return self._order_book_tracker.order_books

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
    def in_flight_orders(self) -> Dict[str, CoinbaseProInFlightOrder]:
        return self._in_flight_orders

    @property
    def user_stream_tracker(self) -> CoinbaseProUserStreamTracker:
        return self._user_stream_tracker

    @property
    def maker_fee_percentage(self) -> Decimal:
        return self._maker_fee_percentage

    @property
    def taker_fee_percentage(self) -> Decimal:
        return self._taker_fee_percentage

    @property
    def trading_rules(self):
        return self._trading_rules

    def restore_tracking_states(self, saved_states: Dict[str, any]):
        """
        *required
        Updates inflight order statuses from API results
        This is used by the MarketsRecorder class to orchestrate market classes at a higher level.
        """
        self._in_flight_orders.update({
            key: CoinbaseProInFlightOrder.from_json(value)
            for key, value in saved_states.items()
        })

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
            await self._api_request(RESTMethod.GET, endpoint=CONSTANTS.TIME_PATH_URL)
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

        ExchangeBase.c_tick(self, timestamp)
        if current_tick > last_tick:
            if not self._poll_notifier.is_set():
                self._poll_notifier.set()
        self._last_timestamp = timestamp

    async def _get_rest_assistant(self) -> RESTAssistant:
        if self._rest_assistant is None:
            self._rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        return self._rest_assistant

    async def _api_request(
        self,
        method: RESTMethod,
        url: Optional[str] = None,
        endpoint: Optional[str] = None,
        data: Any = None,
    ) -> Dict[str, Any]:
        """
        A wrapper for submitting API requests to Coinbase Pro
        :returns: json data from the endpoints
        """
        client = await self._get_rest_assistant()
        request = CoinbaseProRESTRequest(method, url, data=data, endpoint=endpoint, is_auth_required=True)
        request.data = "" if request.data is None else request.data
        response = await client.call(request, timeout=self.API_CALL_TIMEOUT)
        resp_data = await response.json()
        if response.status != 200:
            raise IOError(f"Error fetching data from {response.url}. HTTP status is {response.status}. {resp_data}")
        response_data = await response.json()
        return response_data

    cdef object c_get_fee(self,
                          str base_currency,
                          str quote_currency,
                          object order_type,
                          object order_side,
                          object amount,
                          object price,
                          object is_maker = None):
        """
        *required
        function to calculate fees for a particular order
        :returns: TradeFee class that includes fee percentage and flat fees
        """
        # There is no API for checking user's fee tier
        # Fee info from https://pro.coinbase.com/fees
        is_maker = order_type is OrderType.LIMIT_MAKER
        return estimate_fee("coinbase_pro", is_maker)

    async def _update_fee_percentage(self):
        """
        Pulls the API for updated balances
        """
        cdef:
            double current_timestamp = self._current_timestamp

        if current_timestamp - self._last_fee_percentage_update_timestamp <= self.UPDATE_FEE_PERCENTAGE_INTERVAL:
            return

        fee_info = await self._api_request(RESTMethod.GET, endpoint=CONSTANTS.FEES_PATH_URL)
        self._maker_fee_percentage = Decimal(fee_info["maker_fee_rate"])
        self._taker_fee_percentage = Decimal(fee_info["taker_fee_rate"])
        self._last_fee_percentage_update_timestamp = current_timestamp

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

        account_balances = await self._api_request(RESTMethod.GET, endpoint=CONSTANTS.ACCOUNTS_PATH_URL)

        for balance_entry in account_balances:
            asset_name = balance_entry["currency"]
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
        if current_tick > last_tick or len(self._trading_rules) == 0:
            product_info = await self._api_request(RESTMethod.GET, endpoint=CONSTANTS.PRODUCTS_PATH_URL)
            trading_rules_list = self._format_trading_rules(product_info)
            self._trading_rules.clear()
            for trading_rule in trading_rules_list:
                self._trading_rules[trading_rule.trading_pair] = trading_rule

    def _format_trading_rules(self, raw_trading_rules: List[Any]) -> List[TradingRule]:
        """
        Turns json data from API into TradingRule instances
        :returns: List of TradingRule
        """
        cdef:
            list retval = []
        for rule in raw_trading_rules:
            try:
                trading_pair = rule.get("id")
                retval.append(TradingRule(trading_pair,
                                          min_price_increment=Decimal(str(rule.get("quote_increment"))),
                                          min_base_amount_increment=Decimal(str(rule.get("base_increment"))),
                                          min_order_size=Decimal(str(rule.get("base_min_size"))),
                                          max_order_size=Decimal(str(rule.get("base_max_size"))),
                                          supports_market_orders=(not rule.get("limit_only"))))
            except Exception:
                self.logger().error(f"Error parsing the trading_pair rule {rule}. Skipping.", exc_info=True)
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
            client_order_id = tracked_order.client_order_id
            if order_update is None:
                try:
                    order = await self.get_order(client_order_id)
                except IOError as e:
                    if "order not found" in str(e):
                        # The order does not exist. So we should not be tracking it.
                        self.logger().info(
                            f"The tracked order {client_order_id} does not exist on Coinbase Pro."
                            f"Order removed from tracking."
                        )
                        self.c_stop_tracking_order(client_order_id)
                        self.c_trigger_event(
                            self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                            OrderCancelledEvent(self._current_timestamp, client_order_id)
                        )
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    self.logger().network(
                        f"Error fetching status update for the order {client_order_id}: ",
                        exc_info=True,
                        app_warning_msg=f"Could not fetch updates for the order {client_order_id}. "
                                        f"Check API key and network connection.{e}"
                    )
                continue

            done_reason = order_update.get("done_reason")
            # Calculate the newly executed amount for this update.
            new_confirmed_amount = Decimal(order_update["filled_size"])
            execute_amount_diff = new_confirmed_amount - tracked_order.executed_amount_base
            execute_price = s_decimal_0 if new_confirmed_amount == s_decimal_0 \
                else Decimal(order_update["executed_value"]) / new_confirmed_amount

            order_type_description = tracked_order.order_type_description
            order_type = tracked_order.order_type
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
                    # Coinbase Pro's websocket stream tags events with order_id rather than trade_id
                    # Using order_id here for easier data validation
                    exchange_trade_id=exchange_order_id,
                )
                self.logger().info(f"Filled {execute_amount_diff} out of {tracked_order.amount} of the "
                                   f"{order_type_description} order {client_order_id}.")
                self.c_trigger_event(self.MARKET_ORDER_FILLED_EVENT_TAG, order_filled_event)

            # Update the tracked order
            tracked_order.last_state = done_reason if done_reason in {"filled", "canceled"} else order_update["status"]
            tracked_order.executed_amount_base = new_confirmed_amount
            tracked_order.executed_amount_quote = Decimal(order_update["executed_value"])
            tracked_order.fee_paid = Decimal(order_update["fill_fees"])
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

    async def _iter_user_event_queue(self) -> AsyncIterable[OrderBookMessage]:
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
                content = event_message
                event_type = content.get("type")
                exchange_order_ids = [content.get("order_id"),
                                      content.get("maker_order_id"),
                                      content.get("taker_order_id")]

                tracked_order = None
                for order in list(self._in_flight_orders.values()):
                    await order.get_exchange_order_id()
                    if order.exchange_order_id in exchange_order_ids:
                        tracked_order = order
                        break

                if tracked_order is None:
                    continue

                order_type_description = tracked_order.order_type_description
                execute_price = Decimal(content.get("price", 0.0))
                execute_amount_diff = s_decimal_0

                if event_type == "match":
                    updated = tracked_order.update_with_trade_update(content)
                    if updated:
                        execute_amount_diff = Decimal(content.get("size", 0.0))
                        self.logger().info(f"Filled {execute_amount_diff} out of {tracked_order.amount} of the "
                                           f"{order_type_description} order {tracked_order.client_order_id}")
                        exchange_order_id = tracked_order.exchange_order_id

                        self.c_trigger_event(self.MARKET_ORDER_FILLED_EVENT_TAG,
                                             OrderFilledEvent(
                                                 self._current_timestamp,
                                                 tracked_order.client_order_id,
                                                 tracked_order.trading_pair,
                                                 tracked_order.trade_type,
                                                 tracked_order.order_type,
                                                 execute_price,
                                                 execute_amount_diff,
                                                 AddedToCostTradeFee(
                                                     percent=tracked_order.fee_rate_from_trade_update(content)
                                                 ),
                                                 exchange_trade_id=content["trade_id"]
                                             ))

                if event_type == "change":
                    if content.get("new_size") is not None:
                        tracked_order.amount = Decimal(content.get("new_size", 0.0))
                    elif content.get("new_funds") is not None:
                        if tracked_order.price is not s_decimal_0:
                            tracked_order.amount = Decimal(content.get("new_funds")) / tracked_order.price
                    else:
                        self.logger().error(f"Invalid change message - '{content}'. Aborting.")

                if event_type in ["open", "done"]:
                    remaining_size = Decimal(content.get("remaining_size", tracked_order.amount))
                    new_confirmed_amount = tracked_order.amount - remaining_size
                    execute_amount_diff = new_confirmed_amount - tracked_order.executed_amount_base
                    tracked_order.executed_amount_base = new_confirmed_amount
                    tracked_order.executed_amount_quote += execute_amount_diff * execute_price

                if content.get("reason") == "filled":  # Only handles orders with "done" status
                    if tracked_order.trade_type == TradeType.BUY:
                        self.logger().info(f"The market buy order {tracked_order.client_order_id} has completed "
                                           f"according to Coinbase Pro user stream.")
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
                                           f"according to Coinbase Pro user stream.")
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
                    tracked_order.last_state = "filled"
                    self.c_stop_tracking_order(tracked_order.client_order_id)

                elif content.get("reason") == "canceled":  # reason == "canceled":
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
                          price: Decimal):
        """
        Async wrapper for placing orders through the rest API.
        :returns: json response from the API
        """
        data = {
            "size": f"{amount:f}",
            "product_id": trading_pair,
            "side": "buy" if is_buy else "sell",
            "type": "limit",
        }
        if order_type is OrderType.LIMIT:
            data["price"] = f"{price:f}"
        elif order_type is OrderType.LIMIT_MAKER:
            data["price"] = f"{price:f}"
            data["post_only"] = True
        order_result = await self._api_request(RESTMethod.POST, endpoint=CONSTANTS.ORDERS_PATH_URL, data=data)
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
            TradingRule trading_rule = self._trading_rules[trading_pair]

        decimal_amount = self.quantize_order_amount(trading_pair, amount)
        decimal_price = self.quantize_order_price(trading_pair, price)
        if decimal_amount < trading_rule.min_order_size:
            raise ValueError(f"Buy order amount {decimal_amount} is lower than the minimum order size "
                             f"{trading_rule.min_order_size}.")

        try:
            self.c_start_tracking_order(order_id, trading_pair, order_type, TradeType.BUY, decimal_price, decimal_amount)
            order_result = await self.place_order(order_id, trading_pair, decimal_amount, True, order_type, decimal_price)

            exchange_order_id = order_result["id"]
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(f"Created {order_type} buy order {order_id} for {decimal_amount} {trading_pair}.")
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
                f"Error submitting buy {order_type_str} order to Coinbase Pro for "
                f"{decimal_amount} {trading_pair} {price}.",
                exc_info=True,
                app_warning_msg="Failed to submit buy order to Coinbase Pro. "
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
            int64_t tracking_nonce = <int64_t> get_tracking_nonce()
            str order_id = str(f"buy-{trading_pair}-{tracking_nonce}")

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
            TradingRule trading_rule = self._trading_rules[trading_pair]

        decimal_amount = self.quantize_order_amount(trading_pair, amount)
        decimal_price = self.quantize_order_price(trading_pair, price)
        if decimal_amount < trading_rule.min_order_size:
            raise ValueError(f"Sell order amount {decimal_amount} is lower than the minimum order size "
                             f"{trading_rule.min_order_size}.")

        try:
            self.c_start_tracking_order(order_id, trading_pair, order_type, TradeType.SELL, decimal_price, decimal_amount)
            order_result = await self.place_order(order_id, trading_pair, decimal_amount, False, order_type, decimal_price)

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
        except Exception:
            self.c_stop_tracking_order(order_id)
            order_type_str = order_type.name.lower()
            self.logger().network(
                f"Error submitting sell {order_type_str} order to Coinbase Pro for "
                f"{decimal_amount} {trading_pair} {price}.",
                exc_info=True,
                app_warning_msg="Failed to submit sell order to Coinbase Pro. "
                                "Check API key and network connection."
            )
            self.c_trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                                 MarketOrderFailureEvent(self._current_timestamp, order_id, order_type))

    cdef str c_sell(self,
                    str trading_pair,
                    object amount,
                    object order_type=OrderType.LIMIT,
                    object price=s_decimal_0,
                    dict kwargs={}):
        """
        *required
        Synchronous wrapper that generates a client-side order ID and schedules the sell order.
        """
        cdef:
            int64_t tracking_nonce = <int64_t> get_tracking_nonce()
            str order_id = str(f"sell-{trading_pair}-{tracking_nonce}")
        safe_ensure_future(self.execute_sell(order_id, trading_pair, amount, order_type, price))
        return order_id

    async def execute_cancel(self, trading_pair: str, order_id: str):
        """
        Function that makes API request to cancel an active order
        """
        try:
            exchange_order_id = await self._in_flight_orders.get(order_id).get_exchange_order_id()
            endpoint = f"{CONSTANTS.ORDERS_PATH_URL}/{exchange_order_id}"
            cancelled_id = await self._api_request(RESTMethod.DELETE, endpoint=endpoint)
            if cancelled_id == exchange_order_id:
                self.logger().info(f"Successfully cancelled order {order_id}.")
                self.c_stop_tracking_order(order_id)
                self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                     OrderCancelledEvent(self._current_timestamp, order_id))
                return order_id
        except IOError as e:
            if "order not found" in str(e):
                # The order was never there to begin with. So cancelling it is a no-op but semantically successful.
                self.logger().info(f"The order {order_id} does not exist on Coinbase Pro. No cancellation needed.")
                self.c_stop_tracking_order(order_id)
                self.c_trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                     OrderCancelledEvent(self._current_timestamp, order_id))
                return order_id
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(
                f"Failed to cancel order {order_id}: ",
                exc_info=True,
                app_warning_msg=f"Failed to cancel the order {order_id} on Coinbase Pro. "
                                f"Check API key and network connection.{e}"
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
                    else:
                        self.logger().warning(
                            f"failed to cancel order with error: "
                            f"{repr(client_order_id)}"
                        )
        except Exception as e:
            self.logger().network(
                f"Unexpected error cancelling orders.",
                exc_info=True,
                app_warning_msg="Failed to cancel order on Coinbase Pro. Check API key and network connection."
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
                    self._update_fee_percentage(),
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unexpected error while fetching account updates.",
                    exc_info=True,
                    app_warning_msg=f"Could not fetch account updates on Coinbase Pro. "
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
                    app_warning_msg=f"Could not fetch trading rule updates on Coinbase Pro. "
                                    f"Check network connection."
                )
                await asyncio.sleep(0.5)

    async def get_order(self, client_order_id: str) -> Dict[str, Any]:
        """
        Gets status update for a particular order via rest API
        :returns: json response
        """
        order = self._in_flight_orders.get(client_order_id)
        if order is None:
            return None
        exchange_order_id = await order.get_exchange_order_id()
        endpoint = f"{CONSTANTS.ORDERS_PATH_URL}/{exchange_order_id}"
        result = await self._api_request(RESTMethod.GET, endpoint=endpoint)
        return result

    async def list_orders(self) -> List[Any]:
        """
        Gets a list of the user's active orders via rest API
        :returns: json response
        """
        endpoint = f"{CONSTANTS.ORDERS_PATH_URL}?status=all"
        result = await self._api_request(RESTMethod.GET, endpoint=endpoint)
        return result

    cdef OrderBook c_get_order_book(self, str trading_pair):
        """
        :returns: OrderBook for a specific trading pair
        """
        cdef:
            dict order_books = self._order_book_tracker.order_books

        if trading_pair not in order_books:
            raise ValueError(f"No order book exists for '{trading_pair}'.")
        return order_books[trading_pair]

    def start_tracking_order(self,
                             order_id: str,
                             trading_pair: str,
                             order_type: OrderType,
                             trade_type: TradeType,
                             price: Decimal,
                             amount: Decimal):
        self.c_start_tracking_order(
            order_id,
            trading_pair,
            order_type,
            trade_type,
            price,
            amount)

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
        self._in_flight_orders[client_order_id] = CoinbaseProInFlightOrder(
            client_order_id,
            None,
            trading_pair,
            order_type,
            trade_type,
            price,
            amount,
        )

    cdef c_stop_tracking_order(self, str order_id):
        """
        Delete an order from self._in_flight_orders mapping
        """
        if order_id in self._in_flight_orders:
            del self._in_flight_orders[order_id]

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
        return trading_rule.min_base_amount_increment

    cdef object c_quantize_order_amount(self, str trading_pair, object amount, object price=s_decimal_0):
        """
        *required
        Check current order amount against trading rule, and correct any rule violations
        :return: Valid order amount in Decimal format
        """
        cdef:
            TradingRule trading_rule = self._trading_rules[trading_pair]

        global s_decimal_0
        quantized_amount = ExchangeBase.c_quantize_order_amount(self, trading_pair, amount)

        # Check against min_order_size. If not passing either check, return 0.
        if quantized_amount < trading_rule.min_order_size:
            return s_decimal_0

        # Check against max_order_size. If not passing either check, return 0.
        if quantized_amount > trading_rule.max_order_size:
            return s_decimal_0

        return quantized_amount

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
                price: Decimal = s_decimal_nan,
                is_maker: Optional[bool] = None) -> AddedToCostTradeFee:
        return self.c_get_fee(base_currency, quote_currency, order_type, order_side, amount, price, is_maker)

    def get_order_book(self, trading_pair: str) -> OrderBook:
        return self.c_get_order_book(trading_pair)
