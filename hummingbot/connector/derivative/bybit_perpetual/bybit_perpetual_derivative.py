import asyncio
import copy
import logging
import math
import time
import warnings
from decimal import Decimal
from typing import Any, AsyncIterable, Dict, List, Optional

import aiohttp
import pandas as pd
import ujson

import hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_utils as bybit_utils
from hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_api_order_book_data_source import \
    BybitPerpetualAPIOrderBookDataSource as OrderBookDataSource
from hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_auth import BybitPerpetualAuth
from hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_in_flight_order import BybitPerpetualInFlightOrder
from hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_order_book_tracker import (
    BybitPerpetualOrderBookTracker
)
from hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_user_stream_tracker import (
    BybitPerpetualUserStreamTracker
)
from hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_websocket_adaptor import (
    BybitPerpetualWebSocketAdaptor
)
from hummingbot.connector.derivative.perpetual_budget_checker import PerpetualBudgetChecker
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.connector.perpetual_trading import PerpetualTrading
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.funding_info import FundingInfo
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    FundingPaymentCompletedEvent,
    MarketEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderFilledEvent,
    OrderType,
    PositionAction,
    PositionMode,
    PositionSide,
    SellOrderCompletedEvent,
    SellOrderCreatedEvent,
    TradeType
)
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.logger import HummingbotLogger

s_decimal_NaN = Decimal("nan")
s_decimal_0 = Decimal(0)


class BybitPerpetualDerivative(ExchangeBase, PerpetualTrading):
    _logger = None

    _DEFAULT_TIME_IN_FORCE = "GoodTillCancel"
    SHORT_POLL_INTERVAL = 5.0
    UPDATE_TRADING_RULES_INTERVAL = 60.0
    LONG_POLL_INTERVAL = 120.0

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self,
                 bybit_perpetual_api_key: str = None,
                 bybit_perpetual_secret_key: str = None,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True,
                 domain: Optional[str] = None):

        ExchangeBase.__init__(self)
        PerpetualTrading.__init__(self)

        self._trading_pairs = trading_pairs
        self._trading_required = trading_required
        self._domain = domain
        self._shared_client = None
        self._last_timestamp = 0
        self._real_time_balance_update = False
        self._status_poll_notifier = asyncio.Event()
        self._funding_fee_poll_notifier = asyncio.Event()

        self._in_flight_orders = {}
        self._trading_rules = {}
        self._last_trade_history_timestamp = None
        self._next_funding_fee_timestamp = bybit_utils.get_next_funding_timestamp(time.time())

        self._throttler = self._get_throttler_instance()
        self._auth: BybitPerpetualAuth = BybitPerpetualAuth(api_key=bybit_perpetual_api_key,
                                                            secret_key=bybit_perpetual_secret_key)
        self._order_book_tracker = BybitPerpetualOrderBookTracker(
            session=self._aiohttp_client(),
            throttler=self._throttler,
            trading_pairs=trading_pairs,
            domain=domain)
        self._user_stream_tracker = BybitPerpetualUserStreamTracker(self._auth, domain=domain)
        self._budget_checker = PerpetualBudgetChecker(self)

        # Set Position Mode depending on the Perpetual Market
        if not self._domain:
            self.set_position_mode(PositionMode.HEDGE)

        # Tasks
        self._funding_fee_polling_task = None
        self._user_funding_fee_polling_task = None
        self._status_polling_task = None
        self._user_stream_tracker_task = None
        self._user_stream_event_listener_task = None
        self._trading_rules_polling_task = None

    @property
    def name(self) -> str:
        return CONSTANTS.EXCHANGE_NAME

    @property
    def trading_rules(self) -> Dict[str, TradingRule]:
        return self._trading_rules

    @property
    def in_flight_orders(self) -> Dict[str, BybitPerpetualInFlightOrder]:
        return self._in_flight_orders

    @property
    def status_dict(self) -> Dict[str, bool]:
        """
        A dictionary of statuses of various exchange's components. Used to determine if the connector is ready
        """
        return {
            "order_books_initialized": self._order_book_tracker.ready,
            "account_balance": not self._trading_required or len(self._account_balances) > 0,
            "trading_rule_initialized": len(self._trading_rules) > 0,
            "user_stream_initialized": not self._trading_required or self._user_stream_tracker.data_source.last_recv_time > 0,
            "funding_info": self._order_book_tracker.is_funding_info_initialized()
        }

    @property
    def ready(self) -> bool:
        """
        Determines if the connector is ready.
        :return True when all statuses pass, this might take 5-10 seconds for all the connector's components and
        services to be ready.
        """
        return all(self.status_dict.values())

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        return self._order_book_tracker.order_books

    @property
    def limit_orders(self) -> List[LimitOrder]:
        return [
            in_flight_order.to_limit_order()
            for in_flight_order in self._in_flight_orders.values()
        ]

    @property
    def tracking_states(self) -> Dict[str, Any]:
        """
        :return: active in-flight order in JSON format. Used to save order entries into local sqlite database.
        """
        return {
            client_oid: order.to_json()
            for client_oid, order in self._in_flight_orders.items()
            if not order.is_done
        }

    @property
    def budget_checker(self) -> PerpetualBudgetChecker:
        return self._budget_checker

    def restore_tracking_states(self, saved_states: Dict[str, Any]):
        """
        Restore in-flight orders from the saved tracking states(from local db). This is such that the connector can pick
        up from where it left off before Hummingbot client was terminated.
        :param saved_states: The saved tracking_states.
        """
        self._in_flight_orders.update({
            client_oid: BybitPerpetualInFlightOrder.from_json(order_json)
            for client_oid, order_json in saved_states.items()
        })
        self._throttler = self._get_throttler_instance()

    def _aiohttp_client(self) -> aiohttp.ClientSession:
        """
        :returns Shared aiohttp Client session
        """
        if self._shared_client is None:
            self._shared_client = aiohttp.ClientSession()
        return self._shared_client

    def supported_position_modes(self) -> List[PositionMode]:
        # Linear Perpetuals ONLY supports Hedge mode and Non-linear perpetuals ONLY supports One-way
        if all(bybit_utils.is_linear_perpetual(tp) for tp in self._trading_pairs):
            return [PositionMode.HEDGE]
        elif all(not bybit_utils.is_linear_perpetual(tp) for tp in self._trading_pairs):
            # As of ByBit API v2, we only support ONEWAY mode for non-linear perpetuals
            return [PositionMode.ONEWAY]
        else:
            self.logger().warning("Currently there is no support for both linear and non-linear markets concurrently. "
                                  "Please start another Hummingbot instance.")
            return []

    async def start_network(self):
        self._order_book_tracker.start()
        self._trading_rules_polling_task = safe_ensure_future(self._trading_rules_polling_loop())
        if self._trading_required:
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())
            self._user_stream_tracker_task = safe_ensure_future(self._user_stream_tracker.start())
            self._user_stream_event_listener_task = safe_ensure_future(self._user_stream_event_listener())
            self._user_funding_fee_polling_task = safe_ensure_future(self._user_funding_fee_polling_loop())

    async def stop_network(self):
        self._status_poll_notifier = asyncio.Event()
        self._funding_fee_poll_notifier = asyncio.Event()
        self._order_book_tracker.stop()

        if self._status_polling_task is not None:
            self._status_polling_task.cancel()
            self._status_polling_task = None
        if self._trading_rules_polling_task is not None:
            self._trading_rules_polling_task.cancel()
            self._trading_rules_polling_task = None
        if self._user_stream_tracker_task is not None:
            self._user_stream_tracker_task.cancel()
            self._user_stream_tracker_task = None
        if self._user_stream_event_listener_task is not None:
            self._user_stream_event_listener_task.cancel()
            self._user_stream_event_listener_task = None
        if self._user_funding_fee_polling_task is not None:
            self._user_funding_fee_polling_task.cancel()
            self._user_funding_fee_polling_task = None

    async def check_network(self) -> NetworkStatus:
        """
        This function is required by NetworkIterator base class and is called periodically to check
        the network connection. Simply ping the network (or call any light weight public API).
        """
        try:
            resp = await self._api_request(
                method="GET",
                endpoint=CONSTANTS.SERVER_TIME_PATH_URL)
            if "ret_code" not in resp or resp["ret_code"] != 0:
                raise Exception()
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    def supported_order_types(self) -> List[OrderType]:
        """
        :return a list of OrderType supported by this connector
        """
        return [OrderType.LIMIT, OrderType.MARKET]

    async def _trading_pair_symbol(self, trading_pair: str) -> str:
        return await self._order_book_tracker.trading_pair_symbol(trading_pair)

    async def _api_request(self,
                           method: str,
                           endpoint: Dict[str, str],
                           trading_pair: Optional[str] = None,
                           params: Optional[Dict[str, Any]] = None,
                           body: Optional[Dict[str, Any]] = None,
                           is_auth_required: bool = False,
                           limit_id: Optional[str] = None,
                           referer_header_required: bool = False,
                           ):
        """
        Sends an aiohttp request and waits for a response.
        :param method: The HTTP method, e.g. get or post
        :param endpoint: API end point
        :param params: The query parameters of the API request
        :param body: The body parameters of the API request
        :param is_auth_required: Whether an authentication is required, when True the function will add encrypted
        signature to the request.
        :param limit_id: The id used for the API throttler. If not supplied, the `path_url` is used instead.
        :returns A response in json format.
        """
        params = params or {}
        body = body or {}
        if limit_id is None:
            limit_id = bybit_utils.get_rest_api_limit_id_for_endpoint(
                endpoint=endpoint,
                trading_pair=trading_pair,
            )
        path_url = bybit_utils.rest_api_path_for_endpoint(endpoint, trading_pair)
        url = bybit_utils.rest_api_url_for_endpoint(path_url, self._domain)
        client = self._aiohttp_client()

        if method == "GET":
            if is_auth_required:
                params = self._auth.extend_params_with_authentication_info(params=params)
            async with self._throttler.execute_task(limit_id):
                response = await client.get(url=url,
                                            headers=self._auth.get_headers(referer_header_required),
                                            params=params,
                                            )
        elif method == "POST":
            if is_auth_required:
                params = self._auth.extend_params_with_authentication_info(params=body)
            async with self._throttler.execute_task(limit_id):
                response = await client.post(url=url,
                                             headers=self._auth.get_headers(referer_header_required),
                                             data=ujson.dumps(params)
                                             )
        else:
            raise NotImplementedError(f"{method} HTTP Method not implemented. ")

        response_status = response.status
        parsed_response: Dict[str, Any] = await response.json()

        # Checks HTTP Status and checks if "result" field is in the response.
        if response_status != 200 or "result" not in parsed_response:
            self.logger().error(f"Error fetching data from {url}. HTTP status is {response_status}. "
                                f"Message: {parsed_response} "
                                f"Params: {params} "
                                f"Data: {body}")
            raise Exception(f"Error fetching data from {url}. HTTP status is {response_status}. "
                            f"Message: {parsed_response} "
                            f"Params: {params} "
                            f"Data: {body}")

        return parsed_response

    def get_order_price_quantum(self, trading_pair: str, price: Decimal) -> Decimal:
        """
        Returns a price step, a minimum price increment for a given trading pair.
        :param trading_pair: trading pair for which the price quantum will be calculated
        :param price: the actual price
        """
        trading_rule = self._trading_rules[trading_pair]
        return trading_rule.min_price_increment

    def get_order_size_quantum(self, trading_pair: str, order_size: Decimal) -> Decimal:
        """
        Returns an order amount step, a minimum amount increment for a given trading pair.
        :param trading_pair: trading pair for which the size quantum will be calculated
        :param order_size: the actual amount
        """
        trading_rule = self._trading_rules[trading_pair]
        return Decimal(trading_rule.min_base_amount_increment)

    def get_order_book(self, trading_pair: str) -> OrderBook:
        if trading_pair not in self._order_book_tracker.order_books:
            raise ValueError(f"No order book exists for '{trading_pair}'.")
        return self._order_book_tracker.order_books[trading_pair]

    def start_tracking_order(
        self,
        order_id: str,
        exchange_order_id: Optional[str],
        trading_pair: str,
        trading_type: object,
        price: object,
        amount: object,
        order_type: object,
        leverage: int,
        position: str,
    ):
        self._in_flight_orders[order_id] = BybitPerpetualInFlightOrder(
            client_order_id=order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=trading_pair,
            order_type=order_type,
            trade_type=trading_type,
            price=price,
            amount=amount,
            leverage=leverage,
            position=position)

    def stop_tracking_order(self, order_id: str):
        """
        Stops tracking an order by simply removing it from _in_flight_orders dictionary.
        :param order_id" client order id of the order that should no longer be tracked
        """
        if order_id in self._in_flight_orders:
            del self._in_flight_orders[order_id]

    async def _create_order(self,
                            trade_type: TradeType,
                            order_id: str,
                            trading_pair: str,
                            amount: Decimal,
                            position_action: PositionAction,
                            price: Decimal = s_decimal_0,
                            order_type: OrderType = OrderType.MARKET):
        """
        Calls create-order API end point to place an order, starts tracking the order and triggers order created event.
        :param trade_type: BUY or SELL
        :param order_id: Internal order id (also called client_order_id)
        :param trading_pair: The market to place order
        :param amount: The order amount (in base token value)
        :param amount: Action to take for the position (OPEN or CLOSE)
        :param price: The order price
        :param order_type: The order type
        """
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        params = {}

        if position_action not in [PositionAction.OPEN, PositionAction.CLOSE]:
            raise ValueError("Specify either OPEN_POSITION or CLOSE_POSITION position_action to create an order")

        try:

            amount: Decimal = self.quantize_order_amount(trading_pair, amount)
            if amount < trading_rule.min_order_size:
                raise ValueError(f"{trade_type.name} order amount {amount} is lower than the minimum order size "
                                 f"{trading_rule.min_order_size}.")

            params = {
                "side": "Buy" if trade_type == TradeType.BUY else "Sell",
                "symbol": await self._trading_pair_symbol(trading_pair),
                "qty": amount,
                "time_in_force": self._DEFAULT_TIME_IN_FORCE,
                "close_on_trigger": False,
                "order_link_id": order_id,
                "reduce_only": False,
            }

            if position_action == PositionAction.CLOSE:
                params.update({
                    "close_on_trigger": True,
                    "reduce_only": True
                })

            if order_type.is_limit_type():
                price: Decimal = self.quantize_order_price(trading_pair, price)
                params.update({
                    "order_type": "Limit",
                    "price": price,
                })
            else:
                params.update({
                    "order_type": "Market"
                })

            self.start_tracking_order(order_id,
                                      None,
                                      trading_pair,
                                      trade_type,
                                      price,
                                      amount,
                                      order_type,
                                      self.get_leverage(trading_pair),
                                      position_action.name)

            send_order_results = await self._api_request(
                method="POST",
                endpoint=CONSTANTS.PLACE_ACTIVE_ORDER_PATH_URL,
                trading_pair=trading_pair,
                body=params,
                is_auth_required=True,
                referer_header_required=True,
            )

            if send_order_results["ret_code"] != 0:
                raise ValueError(f"Order is rejected by the API. "
                                 f"Error Msg: {send_order_results['ret_msg']}. Parameters: {params}")

            result = send_order_results["result"]
            exchange_order_id = str(result["order_id"])

            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(f"Created {order_type.name} {trade_type.name} order {order_id} for {trading_pair}. "
                                   f"Amount: {result['qty']} Price: {result.get('price', None)}.")
                tracked_order.update_exchange_order_id(exchange_order_id)

        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.stop_tracking_order(order_id)
            self.trigger_event(MarketEvent.OrderFailure,
                               MarketOrderFailureEvent(self.current_timestamp, order_id, order_type))
            self.logger().network(
                f"Error submitting {trade_type.name} {order_type.name} order to Bybit Perpetual for "
                f"{amount} {trading_pair} {price}. Error: {str(e)} Parameters: {params if params else None}",
                exc_info=True,
                app_warning_msg="Error submitting order to Bybit Perpetual. "
            )

    def buy(self, trading_pair: str, amount: Decimal, order_type: OrderType = OrderType.MARKET,
            price: Decimal = s_decimal_NaN, **kwargs) -> str:
        """
        Buys an amount of base asset as specified in the trading pair. This function returns immediately.
        To see an actual order, wait for a BuyOrderCreatedEvent.
        :param trading_pair: The market (e.g. BTC-CAD) to buy from
        :param amount: The amount in base token value
        :param order_type: The order type
        :param price: The price in which the order is to be placed at
        :returns: A new client order id
        """
        order_id: str = bybit_utils.get_new_client_order_id(True, trading_pair)
        safe_ensure_future(self._create_order(trade_type=TradeType.BUY,
                                              trading_pair=trading_pair,
                                              order_id=order_id,
                                              amount=amount,
                                              price=price,
                                              order_type=order_type,
                                              position_action=kwargs["position_action"]
                                              ))
        return order_id

    def sell(self, trading_pair: str, amount: Decimal, order_type: OrderType = OrderType.MARKET,
             price: Decimal = s_decimal_NaN, **kwargs) -> str:
        """
        Sells an amount of base asset as specified in the trading pair. This function returns immediately.
        To see an actual order, wait for a BuyOrderCreatedEvent.
        :param trading_pair: The market (e.g. BTC-CAD) to buy from
        :param amount: The amount in base token value
        :param order_type: The order type
        :param price: The price in which the order is to be placed at
        :returns: A new client order id
        """
        order_id: str = bybit_utils.get_new_client_order_id(False, trading_pair)
        safe_ensure_future(self._create_order(trade_type=TradeType.SELL,
                                              trading_pair=trading_pair,
                                              order_id=order_id,
                                              amount=amount,
                                              price=price,
                                              order_type=order_type,
                                              position_action=kwargs["position_action"]
                                              ))
        return order_id

    def trigger_order_created_event(self, order: BybitPerpetualInFlightOrder):
        event_tag = MarketEvent.BuyOrderCreated if order.trade_type is TradeType.BUY else MarketEvent.SellOrderCreated
        event_class = BuyOrderCreatedEvent if order.trade_type is TradeType.BUY else SellOrderCreatedEvent
        self.trigger_event(event_tag,
                           event_class(
                               self.current_timestamp,
                               order.order_type,
                               order.trading_pair,
                               order.amount,
                               order.price,
                               order.client_order_id,
                               exchange_order_id=order.exchange_order_id,
                               leverage=self._leverage[order.trading_pair],
                               position=order.position
                           ))

    async def _execute_cancel(self, trading_pair: str, order_id: str) -> str:
        """
        Executes order cancellation process by first calling the CancelOrder endpoint. The API response simply verifies
        that the API request have been received by the API servers. To determine if an order is successfully cancelled,
        we either call the GetOrderStatus/GetOpenOrders endpoint or wait for a OrderStateEvent/OrderTradeEvent from the WS.
        :param trading_pair: The market (e.g. BTC-CAD) the order is in.
        :param order_id: The client_order_id of the order to be cancelled.
        """
        try:
            tracked_order: Optional[BybitPerpetualInFlightOrder] = self._in_flight_orders.get(order_id, None)
            if tracked_order is None:
                raise ValueError(f"Order {order_id} is not being tracked")

            body_params = {
                "symbol": await self._trading_pair_symbol(trading_pair),
                "order_link_id": tracked_order.client_order_id
            }
            if tracked_order.exchange_order_id:
                body_params["order_id"] = tracked_order.exchange_order_id

            # The API response simply verifies that the API request have been received by the API servers.
            response = await self._api_request(
                method="POST",
                endpoint=CONSTANTS.CANCEL_ACTIVE_ORDER_PATH_URL,
                trading_pair=trading_pair,
                body=body_params,
                is_auth_required=True,
            )

            response_code = response["ret_code"]
            if response_code != 0:
                if response_code == CONSTANTS.ORDER_NOT_EXISTS_ERROR_CODE:
                    self.logger().warning(
                        f"Failed to cancel order {order_id}:"
                        f" order not found ({response_code} - {response['ret_msg']})")
                    self.stop_tracking_order(order_id)
                else:
                    raise IOError(f"Bybit Perpetual encountered a problem cancelling the order"
                                  f" ({response['ret_code']} - {response['ret_msg']})")

            return order_id

        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().error(f"Failed to cancel order {order_id}: {str(e)}")
            self.logger().network(
                f"Failed to cancel order {order_id}: {str(e)}",
                exc_info=True,
                app_warning_msg=f"Failed to cancel order {order_id} on Bybit Perpetual. "
                                f"Check API key and network connection."
            )

    def cancel(self, trading_pair: str, order_id: str):
        """
        Cancel an order. This function returns immediately.
        An Order is only determined to be cancelled when a OrderCancelledEvent is received.
        :param trading_pair: The market (e.g. BTC-CAD) of the order.
        :param order_id: The client_order_id of the order to be cancelled.
        """
        safe_ensure_future(self._execute_cancel(trading_pair, order_id))
        return order_id

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        """
        Async function that cancels all active orders.
        Used by bot's top level stop and exit commands (cancelling outstanding orders on exit)
        :returns: List of CancellationResult which indicates whether each order is successfully cancelled.
        """
        tasks = []
        order_id_set = set()
        for order in self._in_flight_orders.values():
            if not order.is_done:
                order_id_set.add(order.client_order_id)
                tasks.append(asyncio.get_event_loop().create_task(
                    self._execute_cancel(order.trading_pair, order.client_order_id)))
        successful_cancellations = []

        try:
            results = await asyncio.wait_for(
                asyncio.shield(safe_gather(*tasks, return_exceptions=True)),
                timeout_seconds)
            for result in results:
                if result is not None:
                    order_id_set.remove(result)
                    successful_cancellations.append(CancellationResult(result, True))
        except asyncio.TimeoutError:
            self.logger().warning("Cancellation of all active orders for Bybit Perpetual connector"
                                  " stopped after max wait time")

        failed_cancellations = [CancellationResult(oid, False) for oid in order_id_set]
        return successful_cancellations + failed_cancellations

    def tick(self, timestamp: float):
        """
        Is called automatically by the clock for each clock tick(1 second by default).
        It checks if a status polling task is due for execution.
        """
        now = time.time()
        poll_interval = (self.SHORT_POLL_INTERVAL
                         if now - self._user_stream_tracker.last_recv_time > 60.0
                         else self.LONG_POLL_INTERVAL)
        last_tick = int(self._last_timestamp / poll_interval)
        current_tick = int(timestamp / poll_interval)
        if current_tick > last_tick:
            self._status_poll_notifier.set()
        if now >= self._next_funding_fee_timestamp + CONSTANTS.FUNDING_SETTLEMENT_DURATION[1]:
            self._funding_fee_poll_notifier.set()

        self._last_timestamp = timestamp

    def get_fee(self,
                base_currency: str,
                quote_currency: str,
                order_type: OrderType,
                order_side: TradeType,
                amount: Decimal,
                price: Decimal = s_decimal_NaN,
                is_maker: Optional[bool] = None):
        warnings.warn(
            "The 'estimate_fee' method is deprecated, use 'build_trade_fee' and 'build_perpetual_trade_fee' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        raise DeprecationWarning(
            "The 'estimate_fee' method is deprecated, use 'build_trade_fee' and 'build_perpetual_trade_fee' instead."
        )

    def _format_trading_rules(self, instrument_info: List[Dict[str, Any]]) -> Dict[str, TradingRule]:
        """
        Converts JSON API response into a local dictionary of trading rules.
        :param instrument_info: The JSON API response.
        :returns: A dictionary of trading pair to its respective TradingRule.
        """
        trading_rules = {}
        for instrument in instrument_info:
            try:
                trading_pair = combine_to_hb_trading_pair(instrument['base_currency'], instrument['quote_currency'])
                is_linear = bybit_utils.is_linear_perpetual(trading_pair)
                collateral_token = instrument["quote_currency"] if is_linear else instrument["base_currency"]
                trading_rules[trading_pair] = TradingRule(
                    trading_pair=trading_pair,
                    min_order_size=Decimal(str(instrument["lot_size_filter"]["min_trading_qty"])),
                    max_order_size=Decimal(str(instrument["lot_size_filter"]["max_trading_qty"])),
                    min_price_increment=Decimal(str(instrument["price_filter"]["tick_size"])),
                    min_base_amount_increment=Decimal(str(instrument["lot_size_filter"]["qty_step"])),
                    buy_order_collateral_token=collateral_token,
                    sell_order_collateral_token=collateral_token,
                )
            except Exception:
                self.logger().error(f"Error parsing the trading pair rule: {instrument}. Skipping...",
                                    exc_info=True)
        return trading_rules

    async def _update_trading_rules(self):
        params = {}
        symbols_response: Dict[str, Any] = await self._api_request(
            method="GET",
            endpoint=CONSTANTS.QUERY_SYMBOL_ENDPOINT,
            params=params,
        )
        self._trading_rules.clear()
        self._trading_rules = self._format_trading_rules(symbols_response["result"])

    async def _trading_rules_polling_loop(self):
        """
        Periodically update trading rules.
        """
        while True:
            try:
                await self._update_trading_rules()
                await asyncio.sleep(self.UPDATE_TRADING_RULES_INTERVAL)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().network(f"Unexpected error while fetching trading rules. Error: {str(e)}",
                                      exc_info=True,
                                      app_warning_msg="Could not fetch new trading rules from Bybit Perpetual. "
                                                      "Check network connection.")
                await asyncio.sleep(0.5)

    async def _update_balances(self):
        """
        Calls REST API to update total and available balances
        """
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        wallet_balance: Dict[str, Dict[str, Any]] = await self._api_request(
            method="GET",
            endpoint=CONSTANTS.GET_WALLET_BALANCE_PATH_URL,
            is_auth_required=True,
        )

        for asset_name, balance_json in wallet_balance["result"].items():
            self._account_balances[asset_name] = Decimal(str(balance_json["wallet_balance"]))
            self._account_available_balances[asset_name] = Decimal(str(balance_json["available_balance"]))
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

        self._in_flight_orders_snapshot = {k: copy.copy(v) for k, v in self._in_flight_orders.items()}
        self._in_flight_orders_snapshot_timestamp = self.current_timestamp

    async def _update_order_status(self):
        """
        Calls REST API to get order status
        """

        active_orders: List[BybitPerpetualInFlightOrder] = [
            o for o in self._in_flight_orders.values()]

        tasks = []
        for active_order in active_orders:
            query_params = {
                "symbol": await self._trading_pair_symbol(active_order.trading_pair),
                "order_link_id": active_order.client_order_id
            }
            if active_order.exchange_order_id is not None:
                query_params["order_id"] = active_order.exchange_order_id

            tasks.append(
                asyncio.create_task(self._api_request(
                    method="GET",
                    endpoint=CONSTANTS.QUERY_ACTIVE_ORDER_PATH_URL,
                    trading_pair=active_order.trading_pair,
                    params=query_params,
                    is_auth_required=True,
                )))
        self.logger().debug(f"Polling for order status updates of {len(tasks)} orders.")

        raw_responses: List[Dict[str, Any]] = await safe_gather(*tasks, return_exceptions=True)

        # Initial parsing of responses. Removes Exceptions.
        parsed_status_responses: List[Dict[str, Any]] = []
        for resp in raw_responses:
            if not isinstance(resp, Exception):
                parsed_status_responses.append(resp["result"])
            else:
                self.logger().error(f"Error fetching order status. Response: {resp}")

        for order_status in parsed_status_responses:
            self._process_order_event_message(order_status)

    async def _update_trade_history(self):
        """
        Calls REST API to get trade history (order fills)
        """

        trade_history_tasks = []

        for trading_pair in self._trading_pairs:
            body_params = {
                "symbol": await self._trading_pair_symbol(trading_pair),
                "limit": 200,
            }
            if self._last_trade_history_timestamp:
                body_params["start_time"] = int(int(self._last_trade_history_timestamp) * 1e3)

            trade_history_tasks.append(
                asyncio.create_task(self._api_request(
                    method="GET",
                    endpoint=CONSTANTS.USER_TRADE_RECORDS_PATH_URL,
                    trading_pair=trading_pair,
                    params=body_params,
                    is_auth_required=True)))

        raw_responses: List[Dict[str, Any]] = await safe_gather(*trade_history_tasks, return_exceptions=True)

        # Initial parsing of responses. Joining all the responses
        parsed_history_resps: List[Dict[str, Any]] = []
        for resp in raw_responses:
            if not isinstance(resp, Exception):
                self._last_trade_history_timestamp = float(resp["time_now"])
                trade_entries = (resp["result"]["trade_list"]
                                 if "trade_list" in resp["result"]
                                 else resp["result"]["data"])
                if trade_entries:
                    parsed_history_resps.extend(trade_entries)
            else:
                self.logger().error(f"Error fetching trades history. Response: {resp}")

        # Trade updates must be handled before any order status updates.
        for trade in parsed_history_resps:
            self._process_trade_event_message(trade)

    async def _status_polling_loop(self):
        """
        Periodically update user balances and order status via REST API. This serves as a fallback measure for web
        socket API updates.
        """
        while True:
            try:
                self._status_poll_notifier = asyncio.Event()
                await self._status_poll_notifier.wait()
                start_ts = self.current_timestamp
                await safe_gather(
                    self._update_balances(),
                    self._update_positions(),
                    self._update_order_status(),
                    self._update_trade_history(),
                )
                self._last_poll_timestamp = start_ts
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"Unexpected error while in status polling loop. Error: {str(e)}", exc_info=True)
                self.logger().network("Unexpected error while fetching account updates.",
                                      exc_info=True,
                                      app_warning_msg="Could not fetch account updates from Bybit Perpetual. "
                                                      "Check API key and network connection.")
                await asyncio.sleep(0.5)

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
                    app_warning_msg="Could not fetch user events from NDAX. Check API key and network connection."
                )
                await asyncio.sleep(1.0)

    async def _user_stream_event_listener(self):
        """
        Listens to message in _user_stream_tracker.user_stream queue.
        """
        async for event_message in self._iter_user_event_queue():
            try:
                endpoint = BybitPerpetualWebSocketAdaptor.endpoint_from_message(event_message)
                payload = BybitPerpetualWebSocketAdaptor.payload_from_message(event_message)

                if endpoint == CONSTANTS.WS_SUBSCRIPTION_POSITIONS_ENDPOINT_NAME:
                    for position_msg in payload:
                        symbol_trading_pair_map: Dict[str, str] = await OrderBookDataSource.trading_pair_symbol_map(self._domain)
                        self._process_account_position_event(position_msg, symbol_trading_pair_map)
                elif endpoint == CONSTANTS.WS_SUBSCRIPTION_ORDERS_ENDPOINT_NAME:
                    for order_msg in payload:
                        self._process_order_event_message(order_msg)
                elif endpoint == CONSTANTS.WS_SUBSCRIPTION_EXECUTIONS_ENDPOINT_NAME:
                    for trade_msg in payload:
                        self._process_trade_event_message(trade_msg)
                else:
                    self.logger().debug(f"Unknown event received from the connector ({event_message})")
            except asyncio.CancelledError:
                raise
            except Exception as ex:
                self.logger().error(f"Unexpected error in user stream listener loop ({ex})", exc_info=True)
                await asyncio.sleep(5.0)

    def _process_account_position_event(self, position_msg: Dict[str, Any], symbol_trading_pair_map: Dict[str, str]):
        """
        Updates position
        :param account_position_event: The position event message payload
        """
        ex_trading_pair = position_msg.get("symbol")
        hb_trading_pair = symbol_trading_pair_map.get(ex_trading_pair)
        position_side = PositionSide.LONG if position_msg.get("side") == "Buy" else PositionSide.SHORT
        position_value = Decimal(str(position_msg.get("position_value")))
        entry_price = Decimal(str(position_msg.get("entry_price")))
        amount = Decimal(str(position_msg.get("size")))
        leverage = Decimal(str(position_msg.get("leverage")))
        unrealized_pnl = position_value - (amount * entry_price * leverage)
        pos_key = self.position_key(hb_trading_pair, position_side)
        if amount != s_decimal_0:
            self._account_positions[pos_key] = Position(
                trading_pair=hb_trading_pair,
                position_side=position_side,
                unrealized_pnl=unrealized_pnl,
                entry_price=entry_price,
                amount=amount * (Decimal("-1.0") if position_side == PositionSide.SHORT else Decimal("1.0")),
                leverage=leverage,
            )
        else:
            if pos_key in self._account_positions:
                del self._account_positions[pos_key]

    def _process_order_event_message(self, order_msg: Dict[str, Any]):
        """
        Updates in-flight order and triggers cancellation or failure event if needed.
        :param order_msg: The order event message payload
        """
        client_order_id = str(order_msg["order_link_id"])

        if client_order_id in self.in_flight_orders:
            tracked_order = self.in_flight_orders[client_order_id]
            was_created = tracked_order.is_created

            # Update order execution status
            tracked_order.last_state = order_msg["order_status"]

            if was_created and tracked_order.is_new:
                self.trigger_order_created_event(tracked_order)
            elif tracked_order.is_cancelled:
                self.logger().info(f"Successfully cancelled order {client_order_id}")
                self.trigger_event(MarketEvent.OrderCancelled,
                                   OrderCancelledEvent(
                                       self.current_timestamp,
                                       client_order_id))
                self.stop_tracking_order(client_order_id)
            elif tracked_order.is_failure:
                reason = order_msg["reject_reason"] if "reject_reason" in order_msg else "unknown"
                self.logger().info(f"The market order {client_order_id} has failed according to order status event. "
                                   f"Reason: {reason}")
                self.trigger_event(MarketEvent.OrderFailure,
                                   MarketOrderFailureEvent(
                                       self.current_timestamp,
                                       client_order_id,
                                       tracked_order.order_type
                                   ))
                self.stop_tracking_order(client_order_id)
            elif tracked_order.is_filled:
                self.logger().info(f"The {tracked_order.trade_type.name} order "
                                   f"{tracked_order.client_order_id} has been completed "
                                   f"according to order status update")
                self._mark_as_completed(tracked_order)

    def _process_trade_event_message(self, trade_msg: Dict[str, Any]):
        """
        Updates in-flight order and trigger order filled event for trade message received. Triggers order completed
        event if the total executed amount equals to the specified order amount.
        :param order_msg: The trade event message payload
        """

        client_order_id = str(trade_msg["order_link_id"])
        if client_order_id in self.in_flight_orders:
            tracked_order = self.in_flight_orders[client_order_id]
            updated = tracked_order.update_with_trade_update(trade_msg)

            if updated:

                self.trigger_event(
                    MarketEvent.OrderFilled,
                    OrderFilledEvent(
                        self.current_timestamp,
                        tracked_order.client_order_id,
                        tracked_order.trading_pair,
                        tracked_order.trade_type,
                        tracked_order.order_type,
                        Decimal(trade_msg["exec_price"]) if "exec_price" in trade_msg else Decimal(trade_msg["price"]),
                        Decimal(trade_msg["exec_qty"]),
                        AddedToCostTradeFee(
                            flat_fees=[TokenAmount(tracked_order.fee_asset, Decimal(trade_msg["exec_fee"]))]
                        ),
                        exchange_trade_id=str(trade_msg["exec_id"]),
                        leverage=self._leverage[tracked_order.trading_pair],
                        position=tracked_order.position
                    )
                )
                if (math.isclose(tracked_order.executed_amount_base, tracked_order.amount) or
                        tracked_order.executed_amount_base >= tracked_order.amount):
                    tracked_order.mark_as_filled()
                    self.logger().info(f"The {tracked_order.trade_type.name} order "
                                       f"{tracked_order.client_order_id} has completed "
                                       f"according to order status API")
                    self._mark_as_completed(tracked_order)

    def _mark_as_completed(self, tracked_order: BybitPerpetualInFlightOrder):
        event_tag = (MarketEvent.BuyOrderCompleted if tracked_order.trade_type is TradeType.BUY
                     else MarketEvent.SellOrderCompleted)
        event_class = (BuyOrderCompletedEvent if tracked_order.trade_type is TradeType.BUY
                       else SellOrderCompletedEvent)
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

    async def _fetch_funding_fee(self, trading_pair: str) -> bool:
        """
        Retrieves the last funding fee/payment.
        :param: trading_pair: The specified trading pair
        :return: Returns True if the fetching was successful.
        """
        try:
            ex_trading_pair = bybit_utils.convert_to_exchange_trading_pair(trading_pair)
            symbol_trading_pair_map: Dict[str, str] = await OrderBookDataSource.trading_pair_symbol_map(self._domain)
            if ex_trading_pair not in symbol_trading_pair_map:
                self.logger().error(f"Unable to fetch funding fee for {trading_pair}. Trading pair not supported.")
                return False

            params = {
                "symbol": ex_trading_pair
            }
            raw_response: Dict[str, Any] = await self._api_request(
                method="GET",
                endpoint=CONSTANTS.GET_LAST_FUNDING_RATE_PATH_URL,
                trading_pair=trading_pair,
                params=params,
                is_auth_required=True)
            data: Dict[str, Any] = raw_response["result"]

            if not data:
                # An empty funding fee/payment is retrieved.
                return True

            funding_rate: Decimal = Decimal(str(data["funding_rate"]))
            position_size: Decimal = Decimal(str(data["size"]))
            payment: Decimal = funding_rate * position_size
            action: str = "paid" if payment < s_decimal_0 else "received"
            if bybit_utils.is_linear_perpetual(trading_pair):
                timestamp: int = int(pd.Timestamp(data["exec_time"], tz="UTC").timestamp() * 1e3)
            else:
                timestamp: int = int(data["exec_timestamp"] * 1e3)
            if payment != s_decimal_0:
                self.logger().info(f"Funding payment of {payment} {action} on {trading_pair} market.")
                self.trigger_event(MarketEvent.FundingPaymentCompleted,
                                   FundingPaymentCompletedEvent(timestamp=timestamp,
                                                                market=self.name,
                                                                funding_rate=funding_rate,
                                                                trading_pair=trading_pair,
                                                                amount=payment))

            return True
        except Exception as e:
            self.logger().error(f"Unexpected error occurred fetching funding fee for {trading_pair}. Error: {e}",
                                exc_info=True)
            return False

    async def _user_funding_fee_polling_loop(self):
        """
        Retrieve User Funding Fee every Funding Time(every 8hrs). Trigger FundingPaymentCompleted event as required.
        """
        while True:
            try:
                await self._funding_fee_poll_notifier.wait()

                tasks = []
                for trading_pair in self._trading_pairs:
                    tasks.append(
                        asyncio.create_task(self._fetch_funding_fee(trading_pair))
                    )
                # Only when all tasks is successful would the event notifier be resetted
                responses: List[bool] = await safe_gather(*tasks)
                if all(responses):
                    self._funding_fee_poll_notifier = asyncio.Event()
                    self._next_funding_fee_timestamp = bybit_utils.get_next_funding_timestamp(time.time())

            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"Unexpected error whilst retrieving funding payments. "
                                    f"Error: {e} ",
                                    exc_info=True)

    async def _update_positions(self):
        """
        Retrieves all positions using the REST API.
        """
        symbol_trading_pair_map: Dict[str, str] = await OrderBookDataSource.trading_pair_symbol_map(self._domain)

        position_tasks = []

        for trading_pair in self._trading_pairs:
            body_params = {"symbol": await self._trading_pair_symbol(trading_pair)}
            position_tasks.append(
                asyncio.create_task(self._api_request(
                    method="GET",
                    endpoint=CONSTANTS.GET_POSITIONS_PATH_URL,
                    trading_pair=trading_pair,
                    params=body_params,
                    is_auth_required=True)))

        raw_responses: List[Dict[str, Any]] = await safe_gather(*position_tasks, return_exceptions=True)

        # Initial parsing of responses. Joining all the responses
        parsed_resps: List[Dict[str, Any]] = []
        for resp in raw_responses:
            if not isinstance(resp, Exception):
                result = resp["result"]
                if result:
                    position_entries = result if isinstance(result, list) else [result]
                    parsed_resps.extend(position_entries)
            else:
                self.logger().error(f"Error fetching trades history. Response: {resp}")

        for position in parsed_resps:
            data = position
            ex_trading_pair = data.get("symbol")
            hb_trading_pair = symbol_trading_pair_map.get(ex_trading_pair)
            position_side = PositionSide.LONG if data.get("side") == "Buy" else PositionSide.SHORT
            unrealized_pnl = Decimal(str(data.get("unrealised_pnl")))
            entry_price = Decimal(str(data.get("entry_price")))
            amount = Decimal(str(data.get("size")))
            leverage = Decimal(str(data.get("leverage"))) if bybit_utils.is_linear_perpetual(hb_trading_pair) \
                else Decimal(str(data.get("effective_leverage")))
            pos_key = self.position_key(hb_trading_pair, position_side)
            if amount != s_decimal_0:
                self._account_positions[pos_key] = Position(
                    trading_pair=hb_trading_pair,
                    position_side=position_side,
                    unrealized_pnl=unrealized_pnl,
                    entry_price=entry_price,
                    amount=amount * (Decimal("-1.0") if position_side == PositionSide.SHORT else Decimal("1.0")),
                    leverage=leverage,
                )
            else:
                if pos_key in self._account_positions:
                    del self._account_positions[pos_key]

    async def _set_leverage(self, trading_pair: str, leverage: int = 1):
        ex_trading_pair = bybit_utils.convert_to_exchange_trading_pair(trading_pair)
        symbol_trading_pair_map: Dict[str, str] = await OrderBookDataSource.trading_pair_symbol_map(self._domain)
        if ex_trading_pair not in symbol_trading_pair_map:
            self.logger().error(f"Unable to set leverage for {trading_pair}. Trading pair not supported.")
            return

        if bybit_utils.is_linear_perpetual(trading_pair):
            body_params = {
                "symbol": ex_trading_pair,
                "buy_leverage": leverage,
                "sell_leverage": leverage
            }
        else:
            body_params = {
                "symbol": ex_trading_pair,
                "leverage": leverage
            }

        resp: Dict[str, Any] = await self._api_request(
            method="POST",
            endpoint=CONSTANTS.SET_LEVERAGE_PATH_URL,
            trading_pair=trading_pair,
            body=body_params,
            is_auth_required=True)

        if resp["ret_code"] == 0 or (resp["ret_code"] == 34036 and resp["ret_msg"] == "leverage not modified"):
            self._leverage[trading_pair] = leverage
            self.logger().info(f"Leverage Successfully set to {leverage} for {trading_pair}.")
        else:
            self.logger().error(f"Unable to set leverage for {trading_pair}. Leverage: {leverage}")

    def set_leverage(self, trading_pair: str, leverage: int):
        safe_ensure_future(self._set_leverage(trading_pair=trading_pair, leverage=leverage))

    def get_funding_info(self, trading_pair: str) -> Optional[FundingInfo]:
        """
        Retrieves the Funding Info for the specified trading pair.
        Note: This function should NOT be called when the connector is not yet ready.
        :param: trading_pair: The specified trading pair.
        """
        if trading_pair in self._order_book_tracker.data_source.funding_info:
            return self._order_book_tracker.data_source.funding_info[trading_pair]
        else:
            self.logger().error(f"Funding Info for {trading_pair} not found. Proceeding to fetch using REST API.")
            safe_ensure_future(self._order_book_tracker.data_source.get_funding_info(trading_pair))
            return None

    def get_buy_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.buy_order_collateral_token

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.sell_order_collateral_token

    def _get_throttler_instance(self) -> AsyncThrottler:
        if self._trading_pairs is not None:
            trading_pairs = [tp for tp in self._trading_pairs]
        else:
            trading_pairs = []

        for order in self._in_flight_orders.values():
            trading_pair = order.trading_pair
            if trading_pair not in trading_pairs:
                trading_pairs.append(trading_pair)

        rate_limits = bybit_utils.build_rate_limits(trading_pairs)
        throttler = AsyncThrottler(rate_limits)
        return throttler
