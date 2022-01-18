import asyncio
import copy
import logging
import math
import time
from decimal import Decimal
from typing import Any, AsyncIterable, Dict, List, Optional

from async_timeout import timeout
from hummingbot.connector.exchange.gate_io import gate_io_constants as CONSTANTS
from hummingbot.connector.exchange.gate_io.gate_io_auth import GateIoAuth
from hummingbot.connector.exchange.gate_io.gate_io_in_flight_order import GateIoInFlightOrder
from hummingbot.connector.exchange.gate_io.gate_io_order_book_tracker import GateIoOrderBookTracker
from hummingbot.connector.exchange.gate_io.gate_io_user_stream_tracker import GateIoUserStreamTracker
from hummingbot.connector.exchange.gate_io.gate_io_utils import (
    GateIoAPIError,
    GateIORESTRequest,
    api_call_with_retries,
    build_gate_io_api_factory,
    convert_from_exchange_trading_pair,
    convert_to_exchange_trading_pair,
    get_new_client_order_id
)
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.rest_assistant import RESTAssistant
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.clock import Clock
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.common import OpenOrder
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderFilledEvent,
    OrderType,
    SellOrderCompletedEvent,
    SellOrderCreatedEvent,
    TradeType
)
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.logger import HummingbotLogger

ctce_logger = None
s_decimal_NaN = Decimal("nan")


class GateIoExchange(ExchangeBase):
    """
    GateIoExchange connects with Gate.io exchange and provides order book pricing, user account tracking and
    trading functionality.
    """
    ORDER_NOT_EXIST_CONFIRMATION_COUNT = 3
    ORDER_NOT_EXIST_CANCEL_COUNT = 2

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global ctce_logger
        if ctce_logger is None:
            ctce_logger = logging.getLogger(__name__)
        return ctce_logger

    def __init__(self,
                 gate_io_api_key: str,
                 gate_io_secret_key: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True
                 ):
        """
        :param gate_io_api_key: The API key to connect to private Gate.io APIs.
        :param gate_io_secret_key: The API secret.
        :param trading_pairs: The market trading pairs which to track order book data.
        :param trading_required: Whether actual trading is needed.
        """
        super().__init__()
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._gate_io_auth = GateIoAuth(gate_io_api_key, gate_io_secret_key)
        self._throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        self._api_factory = build_gate_io_api_factory()
        self._rest_assistant: Optional[RESTAssistant] = None
        self._order_book_tracker = GateIoOrderBookTracker(
            self._throttler, trading_pairs, self._api_factory
        )
        self._user_stream_tracker = GateIoUserStreamTracker(
            self._gate_io_auth, trading_pairs, self._api_factory
        )
        self._ev_loop = asyncio.get_event_loop()
        self._poll_notifier = asyncio.Event()
        self._last_timestamp = 0
        self._in_flight_orders = {}  # Dict[client_order_id:str, GateIoInFlightOrder]
        self._order_not_found_records = {}  # Dict[client_order_id:str, count:int]
        self._trading_rules = {}  # Dict[trading_pair:str, TradingRule]
        self._status_polling_task = None
        self._user_stream_event_listener_task = None
        self._trading_rules_polling_task = None
        self._last_poll_timestamp = 0
        self._real_time_balance_update = False
        self._update_balances_fetching = False
        self._update_balances_queued = False
        self._update_balances_finished = asyncio.Event()

    @property
    def name(self) -> str:
        return "gate_io"

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        return self._order_book_tracker.order_books

    @property
    def trading_rules(self) -> Dict[str, TradingRule]:
        return self._trading_rules

    @property
    def in_flight_orders(self) -> Dict[str, GateIoInFlightOrder]:
        return self._in_flight_orders

    @property
    def status_dict(self) -> Dict[str, bool]:
        """
        A dictionary of statuses of various connector's components.
        """
        return {
            "order_books_initialized": self._order_book_tracker.ready,
            "account_balance": len(self._account_balances) > 0 if self._trading_required else True,
            "trading_rule_initialized": len(self._trading_rules) > 0,
            "user_stream_initialized":
                self._user_stream_tracker.data_source.last_recv_time > 0 if self._trading_required else True,
        }

    @property
    def ready(self) -> bool:
        """
        :return True when all statuses pass, this might take 5-10 seconds for all the connector's components and
        services to be ready.
        """
        return all(self.status_dict.values())

    @property
    def limit_orders(self) -> List[LimitOrder]:
        return [
            in_flight_order.to_limit_order()
            for in_flight_order in self._in_flight_orders.values()
        ]

    @property
    def tracking_states(self) -> Dict[str, any]:
        """
        :return active in-flight orders in json format, is used to save in sqlite db.
        """
        return {
            key: value.to_json()
            for key, value in self._in_flight_orders.items()
            if not value.is_done
        }

    async def _get_rest_assistant(self) -> RESTAssistant:
        if self._rest_assistant is None:
            self._rest_assistant = await self._api_factory.get_rest_assistant()
        return self._rest_assistant

    def restore_tracking_states(self, saved_states: Dict[str, any]):
        """
        Restore in-flight orders from saved tracking states, this is st the connector can pick up on where it left off
        when it disconnects.
        :param saved_states: The saved tracking_states.
        """
        self._in_flight_orders.update({
            key: GateIoInFlightOrder.from_json(value)
            for key, value in saved_states.items()
        })

    def supported_order_types(self) -> List[OrderType]:
        """
        :return a list of OrderType supported by this connector.
        Note that Market order type is no longer required and will not be used.
        """
        return [OrderType.LIMIT]

    def get_taker_order_type(self):
        return OrderType.LIMIT

    def start(self, clock: Clock, timestamp: float):
        """
        This function is called automatically by the clock.
        """
        super().start(clock, timestamp)

    def stop(self, clock: Clock):
        """
        This function is called automatically by the clock.
        """
        super().stop(clock)

    async def start_network(self):
        """
        This function is required by NetworkIterator base class and is called automatically.
        It starts tracking order book, polling trading rules,
        updating statuses and tracking user data.
        """
        self._order_book_tracker.start()
        self._trading_rules_polling_task = safe_ensure_future(self._trading_rules_polling_loop())
        if self._trading_required:
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())
            self._user_stream_tracker_task = safe_ensure_future(self._user_stream_tracker.start())
            self._user_stream_event_listener_task = safe_ensure_future(self._user_stream_event_listener())

    async def stop_network(self):
        """
        This function is required by NetworkIterator base class and is called automatically.
        """
        # Resets timestamps for status_polling_task
        self._last_poll_timestamp = 0
        self._last_timestamp = 0
        self._poll_notifier = asyncio.Event()
        # Reset balance queue
        self._update_balances_fetching = False
        self._update_balances_queued = False
        self._update_balances_finished = asyncio.Event()

        self._order_book_tracker.stop()
        if self._status_polling_task is not None:
            self._status_polling_task.cancel()
            self._status_polling_task = None
        if self._trading_rules_polling_task is not None:
            self._trading_rules_polling_task.cancel()
            self._trading_rules_polling_task = None
        if self._status_polling_task is not None:
            self._status_polling_task.cancel()
            self._status_polling_task = None
        if self._user_stream_tracker_task is not None:
            self._user_stream_tracker_task.cancel()
            self._user_stream_tracker_task = None
        if self._user_stream_event_listener_task is not None:
            self._user_stream_event_listener_task.cancel()
            self._user_stream_event_listener_task = None

    async def check_network(self) -> NetworkStatus:
        """
        This function is required by NetworkIterator base class and is called periodically to check
        the network connection. Simply ping the network (or call any light weight public API).
        """
        try:
            # since there is no ping endpoint, the lowest rate call is to get BTC-USD symbol
            endpoint = CONSTANTS.NETWORK_CHECK_PATH_URL
            request = GateIORESTRequest(
                method=RESTMethod.GET, endpoint=endpoint, throttler_limit_id=endpoint
            )
            await self._api_request(request)
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    async def _trading_rules_polling_loop(self):
        """
        Periodically update trading rule.
        """
        while True:
            try:
                await self._update_trading_rules()
                await asyncio.sleep(CONSTANTS.INTERVAL_TRADING_RULES)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().network(f"Unexpected error while fetching trading rules. Error: {str(e)}",
                                      exc_info=True,
                                      app_warning_msg=("Could not fetch new trading rules from "
                                                       f"{CONSTANTS.EXCHANGE_NAME}. Check network connection."))
                await asyncio.sleep(0.5)

    async def _update_trading_rules(self):
        endpoint = CONSTANTS.SYMBOL_PATH_URL
        request = GateIORESTRequest(
            method=RESTMethod.GET, endpoint=endpoint, throttler_limit_id=endpoint
        )
        symbols_info = await self._api_request(request)
        self._trading_rules.clear()
        self._trading_rules = self._format_trading_rules(symbols_info)

    def _format_trading_rules(self, symbols_info: Dict[str, Any]) -> Dict[str, TradingRule]:
        """
        Converts json API response into a dictionary of trading rules.
        :param symbols_info: The json API response
        :return A dictionary of trading rules.
        Response Example:
        [
            {
                "id": "ETH_USDT",
                "base": "ETH",
                "quote": "USDT",
                "fee": "0.2",
                "min_base_amount": "0.001",
                "min_quote_amount": "1.0",
                "amount_precision": 3,
                "precision": 6,
                "trade_status": "tradable",
                "sell_start": 1516378650,
                "buy_start": 1516378650
            }
        ]
        """
        result = {}
        for rule in symbols_info:
            try:
                trading_pair = convert_from_exchange_trading_pair(rule["id"])
                min_amount_inc = Decimal(f"1e-{rule['amount_precision']}")
                min_price_inc = Decimal(f"1e-{rule['precision']}")
                min_amount = Decimal(str(rule.get("min_base_amount", min_amount_inc)))
                min_notional = Decimal(str(rule.get("min_quote_amount", min_price_inc)))
                result[trading_pair] = TradingRule(trading_pair,
                                                   min_order_size=min_amount,
                                                   min_price_increment=min_price_inc,
                                                   min_base_amount_increment=min_amount_inc,
                                                   min_notional_size=min_notional,
                                                   min_order_value=min_notional,
                                                   )
            except Exception:
                self.logger().error(f"Error parsing the trading pair rule {rule}. Skipping.", exc_info=True)
        return result

    async def _api_request(self, request: GateIORESTRequest) -> Dict[str, Any]:
        rest_assistant: RESTAssistant = await self._get_rest_assistant()
        response = await api_call_with_retries(
            request, rest_assistant, self._throttler, self.logger(), self._gate_io_auth
        )
        return response

    def get_order_price_quantum(self, trading_pair: str, price: Decimal):
        """
        Returns a price step, a minimum price increment for a given trading pair.
        """
        trading_rule = self._trading_rules[trading_pair]
        return trading_rule.min_price_increment

    def get_order_size_quantum(self, trading_pair: str, order_size: Decimal):
        """
        Returns an order amount step, a minimum amount increment for a given trading pair.
        """
        trading_rule = self._trading_rules[trading_pair]
        return Decimal(trading_rule.min_base_amount_increment)

    def get_order_book(self, trading_pair: str) -> OrderBook:
        if trading_pair not in self._order_book_tracker.order_books:
            raise ValueError(f"No order book exists for '{trading_pair}'.")
        return self._order_book_tracker.order_books[trading_pair]

    def buy(self, trading_pair: str, amount: Decimal, order_type=OrderType.LIMIT,
            price: Decimal = s_decimal_NaN, **kwargs) -> str:
        """
        Buys an amount of base asset (of the given trading pair). This function returns immediately.
        To see an actual order, you'll have to wait for BuyOrderCreatedEvent.
        :param trading_pair: The market (e.g. BTC-USDT) to buy from
        :param amount: The amount in base token value
        :param order_type: The order type
        :param price: The price (note: this is no longer optional)
        :returns A new internal order id
        """
        order_id: str = get_new_client_order_id(True, trading_pair)
        safe_ensure_future(self._create_order(TradeType.BUY, order_id, trading_pair, amount, order_type, price))
        return order_id

    def sell(self, trading_pair: str, amount: Decimal, order_type=OrderType.LIMIT,
             price: Decimal = s_decimal_NaN, **kwargs) -> str:
        """
        Sells an amount of base asset (of the given trading pair). This function returns immediately.
        To see an actual order, you'll have to wait for SellOrderCreatedEvent.
        :param trading_pair: The market (e.g. BTC-USDT) to sell from
        :param amount: The amount in base token value
        :param order_type: The order type
        :param price: The price (note: this is no longer optional)
        :returns A new internal order id
        """
        order_id: str = get_new_client_order_id(False, trading_pair)
        safe_ensure_future(self._create_order(TradeType.SELL, order_id, trading_pair, amount, order_type, price))
        return order_id

    def cancel(self, trading_pair: str, order_id: str):
        """
        Cancel an order. This function returns immediately.
        To get the cancellation result, you'll have to wait for OrderCancelledEvent.
        :param trading_pair: The market (e.g. BTC-USDT) of the order.
        :param order_id: The internal order id (also called client_order_id)
        """
        safe_ensure_future(self._execute_cancel(trading_pair, order_id))
        return order_id

    async def _create_order(self,
                            trade_type: TradeType,
                            order_id: str,
                            trading_pair: str,
                            amount: Decimal,
                            order_type: OrderType,
                            price: Decimal):
        """
        Calls create-order API end point to place an order, starts tracking the order and triggers order created event.
        :param trade_type: BUY or SELL
        :param order_id: Internal order id (also called client_order_id)
        :param trading_pair: The market to place order
        :param amount: The order amount (in base token value)
        :param order_type: The order type
        :param price: The order price
        """
        try:
            if not order_type.is_limit_type():
                raise Exception(f"Unsupported order type: {order_type}")
            trading_rule = self._trading_rules[trading_pair]

            amount = self.quantize_order_amount(trading_pair, amount)
            price = self.quantize_order_price(trading_pair, price)
            if amount < trading_rule.min_order_size:
                raise ValueError(f"{trade_type.name.title()} order amount {amount} is lower than the minimum order size "
                                 f"{trading_rule.min_order_size}.")

            order_type_str = order_type.name.lower().split("_")[0]
            api_params = {"text": order_id,
                          "currency_pair": convert_to_exchange_trading_pair(trading_pair),
                          "side": trade_type.name.lower(),
                          "type": order_type_str,
                          "price": f"{price:f}",
                          "amount": f"{amount:f}",
                          }
            self.start_tracking_order(order_id, None, trading_pair, trade_type, price, amount, order_type)

            endpoint = CONSTANTS.ORDER_CREATE_PATH_URL
            request = GateIORESTRequest(
                method=RESTMethod.POST,
                endpoint=endpoint,
                data=api_params,
                is_auth_required=True,
                throttler_limit_id=endpoint,
            )
            order_result = await self._api_request(request)
            if order_result.get('status') in {"cancelled", "expired", "failed"}:
                raise GateIoAPIError({'label': 'ORDER_REJECTED', 'message': 'Order rejected.'})
            else:
                exchange_order_id = str(order_result["id"])
                tracked_order = self._in_flight_orders.get(order_id)
                if tracked_order is not None:
                    self.logger().info(f"Created {order_type.name} {trade_type.name} order {order_id} for "
                                       f"{amount} {trading_pair}.")
                    tracked_order.update_exchange_order_id(exchange_order_id)
                    if trade_type is TradeType.BUY:
                        event_tag = MarketEvent.BuyOrderCreated
                        event_cls = BuyOrderCreatedEvent
                    else:
                        event_tag = MarketEvent.SellOrderCreated
                        event_cls = SellOrderCreatedEvent
                    self.trigger_event(event_tag,
                                       event_cls(self.current_timestamp,
                                                 order_type,
                                                 trading_pair,
                                                 amount,
                                                 price,
                                                 order_id,
                                                 exchange_order_id))
        except asyncio.CancelledError:
            raise
        except Exception as e:
            error_reason = e.error_message if isinstance(e, GateIoAPIError) else str(e)
            self.stop_tracking_order(order_id)
            self.logger().error(
                f"Error submitting {trade_type.name} {order_type.name} order to {CONSTANTS.EXCHANGE_NAME} for "
                f"{amount} {trading_pair} {price} - {error_reason}.",
                exc_info=True,
            )
            self.trigger_event(MarketEvent.OrderFailure,
                               MarketOrderFailureEvent(self.current_timestamp, order_id, order_type))

    def start_tracking_order(self,
                             order_id: str,
                             exchange_order_id: str,
                             trading_pair: str,
                             trade_type: TradeType,
                             price: Decimal,
                             amount: Decimal,
                             order_type: OrderType):
        """
        Starts tracking an order by simply adding it into _in_flight_orders dictionary.
        """
        self._in_flight_orders[order_id] = GateIoInFlightOrder(
            client_order_id=order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=trading_pair,
            order_type=order_type,
            trade_type=trade_type,
            price=price,
            amount=amount
        )

    def stop_tracking_order(self, order_id: str):
        """
        Stops tracking an order by simply removing it from _in_flight_orders dictionary.
        """
        if order_id in self._in_flight_orders:
            del self._in_flight_orders[order_id]
        if order_id in self._order_not_found_records:
            del self._order_not_found_records[order_id]

    async def _execute_cancel(self, trading_pair: str, order_id: str) -> str:
        """
        Executes order cancellation process by first calling cancel-order API. The API result doesn't confirm whether
        the cancellation is successful, it simply states it receives the request.
        :param trading_pair: The market trading pair (Unused during cancel on Gate.io)
        :param order_id: The internal order id
        order.last_state to change to CANCELED
        """
        order_was_cancelled = False
        err_msg = None
        try:
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is None:
                self.logger().warning(f"Failed to cancel order {order_id}. Order not found in inflight orders.")
            else:
                if tracked_order.exchange_order_id is None:
                    await tracked_order.get_exchange_order_id()
                ex_order_id = tracked_order.exchange_order_id
                endpoint = CONSTANTS.ORDER_DELETE_PATH_URL.format(id=ex_order_id)
                params = {'currency_pair': convert_to_exchange_trading_pair(trading_pair)}
                request = GateIORESTRequest(
                    method=RESTMethod.DELETE,
                    endpoint=endpoint,
                    params=params,
                    is_auth_required=True,
                    throttler_limit_id=CONSTANTS.ORDER_DELETE_LIMIT_ID,
                )
                await self._api_request(request)
                order_was_cancelled = True
        except asyncio.CancelledError:
            raise
        except (asyncio.TimeoutError, GateIoAPIError) as e:
            if isinstance(e, asyncio.TimeoutError):
                err_msg = 'Order not tracked.'
                err_lbl = 'ORDER_NOT_FOUND'
            else:
                err_msg = e.error_message
                err_lbl = e.error_label
            self._order_not_found_records[order_id] = self._order_not_found_records.get(order_id, 0) + 1
            if err_lbl == 'ORDER_NOT_FOUND' and \
                    self._order_not_found_records[order_id] >= self.ORDER_NOT_EXIST_CANCEL_COUNT:
                order_was_cancelled = True
        if order_was_cancelled:
            self.logger().info(f"Successfully cancelled order {order_id} on {CONSTANTS.EXCHANGE_NAME}.")
            self.stop_tracking_order(order_id)
            self.trigger_event(MarketEvent.OrderCancelled,
                               OrderCancelledEvent(self.current_timestamp, order_id))
            tracked_order.cancelled_event.set()
            return CancellationResult(order_id, True)
        else:
            err_msg = err_msg or "(no details available)"
            self.logger().network(
                f"Failed to cancel order {order_id}: {err_msg}",
                exc_info=True,
                app_warning_msg=f"Failed to cancel the order {order_id} on {CONSTANTS.EXCHANGE_NAME}. "
                                f"Check API key and network connection."
            )
            return CancellationResult(order_id, False)

    async def _status_polling_loop(self):
        """
        Periodically update user balances and order status via REST API. This serves as a fallback measure for web
        socket API updates.
        """
        while True:
            try:
                await self._poll_notifier.wait()
                await safe_gather(
                    self._update_balances(),
                    self._update_order_status(),
                )
                self._last_poll_timestamp = (time.time() if math.isnan(self.current_timestamp)
                                             else self.current_timestamp)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(str(e), exc_info=True)
                warn_msg = (f"Could not fetch account updates from {CONSTANTS.EXCHANGE_NAME}. "
                            "Check API key and network connection.")
                self.logger().network("Unexpected error while fetching account updates.", exc_info=True,
                                      app_warning_msg=warn_msg)
                await asyncio.sleep(0.5)
            finally:
                self._poll_notifier = asyncio.Event()

    async def _update_balances(self):
        """
        Calls REST API to update total and available balances.
        """
        try:
            # Check for in progress balance updates, queue if fetching and none already waiting, otherwise skip.
            if self._update_balances_fetching:
                if not self._update_balances_queued:
                    self._update_balances_queued = True
                    await self._update_balances_finished.wait()
                    self._update_balances_queued = False
                    self._update_balances_finished = asyncio.Event()
                else:
                    return
            self._update_balances_fetching = True
            endpoint = CONSTANTS.USER_BALANCES_PATH_URL
            request = GateIORESTRequest(
                method=RESTMethod.GET,
                endpoint=endpoint,
                is_auth_required=True,
                throttler_limit_id=endpoint,
            )
            account_info = await self._api_request(request)
            self._process_balance_message(account_info)
            self._update_balances_fetching = False
            # Set balance update finished event if there's one waiting.
            if self._update_balances_queued and not self._update_balances_finished.is_set():
                self._update_balances_finished.set()
        except Exception as e:
            if self._update_balances_queued:
                if self._update_balances_finished.is_set():
                    self._update_balances_finished = asyncio.Event()
                else:
                    self._update_balances_finished.set()
                self._update_balances_queued = False
            if self._update_balances_fetching:
                self._update_balances_fetching = False
            warn_msg = (f"Could not fetch balance update from {CONSTANTS.EXCHANGE_NAME}")
            self.logger().network(f"Unexpected error while fetching balance update - {str(e)}", exc_info=True,
                                  app_warning_msg=warn_msg)

    def stop_tracking_order_exceed_not_found_limit(self, tracked_order: GateIoInFlightOrder):
        """
        Increments and checks if the tracked order has exceed the ORDER_NOT_EXIST_CONFIRMATION_COUNT limit.
        If true, Triggers a MarketOrderFailureEvent and stops tracking the order.
        """
        client_order_id = tracked_order.client_order_id
        self._order_not_found_records[client_order_id] = self._order_not_found_records.get(client_order_id, 0) + 1
        if self._order_not_found_records[client_order_id] >= self.ORDER_NOT_EXIST_CONFIRMATION_COUNT:
            # Wait until the order not found error have repeated a few times before actually treating
            # it as failed. See: https://github.com/CoinAlpha/hummingbot/issues/601
            self.trigger_event(MarketEvent.OrderFailure,
                               MarketOrderFailureEvent(
                                   self.current_timestamp, client_order_id, tracked_order.order_type))
            self.stop_tracking_order(client_order_id)

    async def _update_order_status(self):
        """
        Calls REST API to get status update for each in-flight order.
        """

        tracked_orders: List[GateIoInFlightOrder] = list(self._in_flight_orders.values())

        order_status_tasks = []
        order_trade_tasks = []

        for tracked_order in tracked_orders:
            try:
                exchange_order_id = await tracked_order.get_exchange_order_id()
            except asyncio.TimeoutError:
                self.logger().network(f"Skipped order status update for {tracked_order.client_order_id} "
                                      "- waiting for exchange order id.")
                continue
            trading_pair = convert_to_exchange_trading_pair(tracked_order.trading_pair)

            params = {
                "currency_pair": trading_pair,
                "order_id": exchange_order_id
            }
            order_trade_request = GateIORESTRequest(
                method=RESTMethod.GET,
                endpoint=CONSTANTS.MY_TRADES_PATH_URL,
                params=params,
                is_auth_required=True,
                throttler_limit_id=CONSTANTS.MY_TRADES_PATH_URL,
            )
            params = {"currency_pair": trading_pair}
            order_status_request = GateIORESTRequest(
                method=RESTMethod.GET,
                endpoint=CONSTANTS.ORDER_STATUS_PATH_URL.format(id=exchange_order_id),
                params=params,
                is_auth_required=True,
                throttler_limit_id=CONSTANTS.ORDER_STATUS_LIMIT_ID,
            )

            order_status_tasks.append(asyncio.create_task(self._api_request(order_status_request)))
            order_trade_tasks.append(asyncio.create_task(self._api_request(order_trade_request)))
        self.logger().debug(f"Polling for order updates of {len(tracked_orders)} orders.")

        # Process order trades first before processing order statuses
        trade_responses = await safe_gather(*order_trade_tasks, return_exceptions=True)
        for response, tracked_order in zip(trade_responses, tracked_orders):
            if not isinstance(response, GateIoAPIError):
                if len(response) > 0:
                    for trade_fills in response:
                        self._process_trade_message(trade_fills, tracked_order.client_order_id)
            else:
                self.logger().warning(f"Failed to fetch trade updates for order {tracked_order.client_order_id}. "
                                      f"Response: {response}")
                if response.error_label == 'ORDER_NOT_FOUND':
                    self.stop_tracking_order_exceed_not_found_limit(tracked_order=tracked_order)

        status_responses = await safe_gather(*order_status_tasks, return_exceptions=True)
        for response, tracked_order in zip(status_responses, tracked_orders):
            if not isinstance(response, GateIoAPIError):
                self._process_order_message(response)
            else:
                self.logger().warning(f"Failed to fetch order status updates for order {tracked_order.client_order_id}. "
                                      f"Response: {response}")
                if response.error_label == 'ORDER_NOT_FOUND':
                    self.stop_tracking_order_exceed_not_found_limit(tracked_order=tracked_order)

    def _process_order_message(self, order_msg: Dict[str, Any]):
        """
        Updates in-flight order and triggers cancellation or failure event if needed.
        :param order_msg: The order response from either REST or web socket API (they are of the same format)
        Example Order:
        {
            "id": "52109248977",
            "text": "3",
            "create_time": "1622638707",
            "update_time": "1622638807",
            "currency_pair": "BTC_USDT",
            "type": "limit",
            "account": "spot",
            "side": "buy",
            "amount": "0.001",
            "price": "1999.8",
            "time_in_force": "gtc",
            "left": "0.001",
            "filled_total": "0",
            "fee": "0",
            "fee_currency": "BTC",
            "point_fee": "0",
            "gt_fee": "0",
            "gt_discount": true,
            "rebated_fee": "0",
            "rebated_fee_currency": "BTC",
            "create_time_ms": "1622638707326",
            "update_time_ms": "1622638807635",
            ... optional params
            "status": "open",
            "event": "finish"
            "iceberg": "0",
            "fill_price": "0",
            "user": 5660412,
        }
        """

        client_order_id = str(order_msg["text"])
        tracked_order = self.in_flight_orders.get(client_order_id, None)
        if tracked_order:

            tracked_order.last_state = order_msg.get("status", order_msg.get("event"))

            if tracked_order.is_cancelled:
                self.logger().info(f"Successfully cancelled order {tracked_order.client_order_id}.")
                self.stop_tracking_order(tracked_order.client_order_id)
                self.trigger_event(MarketEvent.OrderCancelled,
                                   OrderCancelledEvent(self.current_timestamp, tracked_order.client_order_id))
                tracked_order.cancelled_event.set()
            elif tracked_order.is_failure:
                self.logger().info(f"The order {tracked_order.client_order_id} has failed according to order status API. ")
                self.trigger_event(MarketEvent.OrderFailure,
                                   MarketOrderFailureEvent(
                                       self.current_timestamp, tracked_order.client_order_id, tracked_order.order_type))
                self.stop_tracking_order(tracked_order.client_order_id)

    def _process_trade_message(self, trade_msg: Dict[str, Any], client_order_id: Optional[str] = None):
        """
        Updates in-flight order and trigger order filled event for trade message received. Triggers order completed
        event if the total executed amount equals to the specified order amount.
        Example Trade:
        {
            "id": 1234567890,
            "user_id": 1234567,
            "order_id": "96780687179",
            "currency_pair": "ETH_USDT",
            "create_time": 1637764970,
            "create_time_ms": "1637764970928.48",
            "side": "buy",
            "amount": "0.005",
            "role": "maker",
            "price": "4191.1",
            "fee": "0.000009",
            "fee_currency": "ETH",
            "point_fee": "0",
            "gt_fee": "0",
            "text": "t-HBOT-B-EHUT1637764969004024",
        }
        """
        client_order_id = client_order_id or str(trade_msg["text"])
        tracked_order = self.in_flight_orders.get(client_order_id, None)
        if tracked_order:
            updated = tracked_order.update_with_trade_update(trade_msg)
            if updated:
                self._trigger_order_fill(tracked_order=tracked_order,
                                         update_msg=trade_msg)

    def _trigger_order_fill(self,
                            tracked_order: GateIoInFlightOrder,
                            update_msg: Dict[str, Any]):
        self.trigger_event(
            MarketEvent.OrderFilled,
            OrderFilledEvent(
                self.current_timestamp,
                tracked_order.client_order_id,
                tracked_order.trading_pair,
                tracked_order.trade_type,
                tracked_order.order_type,
                Decimal(str(update_msg.get("fill_price", update_msg.get("price", "0")))),
                tracked_order.executed_amount_base,
                AddedToCostTradeFee(flat_fees=[TokenAmount(tracked_order.fee_asset, tracked_order.fee_paid)]),
                str(update_msg.get("update_time_ms", update_msg.get("id")))
            )
        )
        if math.isclose(tracked_order.executed_amount_base, tracked_order.amount) or \
                tracked_order.executed_amount_base >= tracked_order.amount or \
                tracked_order.is_done:
            tracked_order.last_state = "FILLED"
            self.logger().info(f"The {tracked_order.trade_type.name} order "
                               f"{tracked_order.client_order_id} has completed "
                               f"according to order status API.")
            event_tag = MarketEvent.BuyOrderCompleted if tracked_order.trade_type is TradeType.BUY \
                else MarketEvent.SellOrderCompleted
            event_class = BuyOrderCompletedEvent if tracked_order.trade_type is TradeType.BUY \
                else SellOrderCompletedEvent
            self.trigger_event(event_tag,
                               event_class(self.current_timestamp,
                                           tracked_order.client_order_id,
                                           tracked_order.base_asset,
                                           tracked_order.quote_asset,
                                           tracked_order.fee_asset,
                                           tracked_order.executed_amount_base,
                                           tracked_order.executed_amount_quote,
                                           tracked_order.fee_paid,
                                           tracked_order.order_type,
                                           tracked_order.exchange_order_id))
            self.stop_tracking_order(tracked_order.client_order_id)

    def _process_balance_message(self, balance_update):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()
        for account in balance_update:
            asset_name = account["currency"]
            self._account_available_balances[asset_name] = Decimal(str(account["available"]))
            self._account_balances[asset_name] = Decimal(str(account["locked"])) + Decimal(str(account["available"]))
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

        self._in_flight_orders_snapshot = {k: copy.copy(v) for k, v in self._in_flight_orders.items()}
        self._in_flight_orders_snapshot_timestamp = self.current_timestamp

    def _process_balance_message_ws(self, balance_update):
        for account in balance_update:
            asset_name = account["currency"]
            self._account_available_balances[asset_name] = Decimal(str(account["available"]))
            self._account_balances[asset_name] = Decimal(str(account["total"]))

        self._in_flight_orders_snapshot = {k: copy.copy(v) for k, v in self._in_flight_orders.items()}
        self._in_flight_orders_snapshot_timestamp = self.current_timestamp

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        """
        Cancels all in-flight orders and waits for cancellation results.
        Used by bot's top level stop and exit commands (cancelling outstanding orders on exit)
        :param timeout_seconds: The timeout at which the operation will be canceled.
        :returns List of CancellationResult which indicates whether each order is successfully cancelled.
        """
        if self._trading_pairs is None:
            raise Exception("cancel_all can only be used when trading_pairs are specified.")
        open_orders = [o for o in self._in_flight_orders.values() if not o.is_done]
        if len(open_orders) == 0:
            return []
        tasks = [self._execute_cancel(o.trading_pair, o.client_order_id) for o in open_orders]
        cancellation_results = []
        cancel_timeout = timeout_seconds * len(open_orders) if len(open_orders) else timeout_seconds
        try:
            async with timeout(cancel_timeout):
                cancellation_results = await safe_gather(*tasks, return_exceptions=False)
        except Exception:
            self.logger().network(
                "Unexpected error cancelling orders.", exc_info=True,
                app_warning_msg=(f"Failed to cancel all orders on {CONSTANTS.EXCHANGE_NAME}. "
                                 "Check API key and network connection.")
            )
        return cancellation_results

    def tick(self, timestamp: float):
        """
        Is called automatically by the clock for each clock's tick (1 second by default).
        It checks if status polling task is due for execution.
        """
        now = time.time()
        # Using 120 seconds here as Gate.io websocket is quiet
        poll_interval = (CONSTANTS.SHORT_POLL_INTERVAL
                         if now - self._user_stream_tracker.last_recv_time > 120.0
                         else CONSTANTS.LONG_POLL_INTERVAL)
        last_tick = int(self._last_timestamp / poll_interval)
        current_tick = int(timestamp / poll_interval)
        if current_tick > last_tick:
            if not self._poll_notifier.is_set():
                self._poll_notifier.set()
        self._last_timestamp = timestamp

    def get_fee(self,
                base_currency: str,
                quote_currency: str,
                order_type: OrderType,
                order_side: TradeType,
                amount: Decimal,
                price: Decimal = s_decimal_NaN,
                is_maker: Optional[bool] = None) -> AddedToCostTradeFee:
        """
        To get trading fee, this function is simplified by using fee override configuration. Most parameters to this
        function are ignore except order_type. Use OrderType.LIMIT_MAKER to specify you want trading fee for
        maker order.
        """
        is_maker = order_type is OrderType.LIMIT_MAKER
        return AddedToCostTradeFee(percent=self.estimate_fee_pct(is_maker))

    async def _iter_user_event_queue(self) -> AsyncIterable[Dict[str, any]]:
        while True:
            try:
                yield await self._user_stream_tracker.user_stream.get()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unknown error. Retrying after 1 seconds.", exc_info=True,
                    app_warning_msg=(f"Could not fetch user events from {CONSTANTS.EXCHANGE_NAME}. "
                                     "Check API key and network connection."))
                await asyncio.sleep(1.0)

    async def _user_stream_event_listener(self):
        """
        Listens to message in _user_stream_tracker.user_stream queue. The messages are put in by
        GateIoAPIUserStreamDataSource.
        """
        async for event_message in self._iter_user_event_queue():
            try:
                user_channels = [
                    CONSTANTS.USER_TRADES_ENDPOINT_NAME,
                    CONSTANTS.USER_ORDERS_ENDPOINT_NAME,
                    CONSTANTS.USER_BALANCE_ENDPOINT_NAME,
                ]

                channel: str = event_message.get("channel", None)
                results: str = event_message.get("result", None)

                if channel not in user_channels:
                    self.logger().error(f"Unexpected message in user stream: {event_message}.", exc_info=True)
                    continue
                if channel == CONSTANTS.USER_TRADES_ENDPOINT_NAME:
                    for trade_msg in results:
                        self._process_trade_message(trade_msg)
                elif channel == CONSTANTS.USER_ORDERS_ENDPOINT_NAME:
                    for order_msg in results:
                        self._process_order_message(order_msg)
                elif channel == CONSTANTS.USER_BALANCE_ENDPOINT_NAME:
                    self._process_balance_message_ws(results)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await asyncio.sleep(5.0)

    # This is currently unused, but looks like a future addition.
    async def get_open_orders(self) -> List[OpenOrder]:
        endpoint = CONSTANTS.USER_ORDERS_PATH_URL
        request = GateIORESTRequest(
            method=RESTMethod.GET,
            endpoint=endpoint,
            is_auth_required=True,
            throttler_limit_id=endpoint,
        )
        result = await self._api_request(request)
        ret_val = []
        for pair_orders in result:
            for order in pair_orders["orders"]:
                if CONSTANTS.HBOT_ORDER_ID not in order["text"]:
                    continue
                if order["type"] != OrderType.LIMIT.name.lower():
                    self.logger().info(f"Unsupported order type found: {order['type']}")
                    continue
                ret_val.append(
                    OpenOrder(
                        client_order_id=order["text"],
                        trading_pair=convert_from_exchange_trading_pair(order["currency_pair"]),
                        price=Decimal(str(order["price"])),
                        amount=Decimal(str(order["amount"])),
                        executed_amount=Decimal(str(order["filled_total"])),
                        status=order["status"],
                        order_type=OrderType.LIMIT,
                        is_buy=True if order["side"].lower() == TradeType.BUY.name.lower() else False,
                        time=int(order["create_time"]),
                        exchange_order_id=order["id"]
                    )
                )
        return ret_val
