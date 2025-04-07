import asyncio
import logging
import math
import time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, AsyncIterable, Dict, List, Optional, Union

import aiohttp
import ujson

from hummingbot.connector.exchange.ndax import ndax_constants as CONSTANTS, ndax_utils
from hummingbot.connector.exchange.ndax.ndax_api_order_book_data_source import NdaxAPIOrderBookDataSource
from hummingbot.connector.exchange.ndax.ndax_auth import NdaxAuth
from hummingbot.connector.exchange.ndax.ndax_in_flight_order import NdaxInFlightOrder, NdaxInFlightOrderNotCreated
from hummingbot.connector.exchange.ndax.ndax_order_book_tracker import NdaxOrderBookTracker
from hummingbot.connector.exchange.ndax.ndax_user_stream_tracker import NdaxUserStreamTracker
from hummingbot.connector.exchange.ndax.ndax_websocket_adaptor import NdaxWebSocketAdaptor
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.clock import Clock
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.common import OpenOrder, OrderType, TradeType
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderFilledEvent,
    SellOrderCompletedEvent,
    SellOrderCreatedEvent,
)
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter

s_decimal_NaN = Decimal("nan")
s_decimal_0 = Decimal(0)

RESOURCE_NOT_FOUND_ERR = "Resource Not Found"


class NdaxExchange(ExchangeBase):
    """
    Class to onnect with NDAX exchange. Provides order book pricing, user account tracking and
    trading functionality.
    """
    SHORT_POLL_INTERVAL = 5.0
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0
    UPDATE_TRADING_RULES_INTERVAL = 60.0
    LONG_POLL_INTERVAL = 120.0
    ORDER_EXCEED_NOT_FOUND_COUNT = 2

    _logger = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self,
                 client_config_map: "ClientConfigAdapter",
                 ndax_uid: str,
                 ndax_api_key: str,
                 ndax_secret_key: str,
                 ndax_account_name: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True,
                 domain: Optional[str] = None
                 ):
        """
        :param ndax_uid: User ID of the account
        :param ndax_api_key: The API key to connect to private NDAX APIs.
        :param ndax_secret_key: The API secret.
        :param ndax_account_name: The name of the account associated to the user account.
        :param trading_pairs: The market trading pairs which to track order book data.
        :param trading_required: Whether actual trading is needed.
        """
        super().__init__(client_config_map)
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._auth = NdaxAuth(uid=ndax_uid,
                              api_key=ndax_api_key,
                              secret_key=ndax_secret_key,
                              account_name=ndax_account_name)
        self._throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        self._shared_client = aiohttp.ClientSession()
        self._set_order_book_tracker(NdaxOrderBookTracker(
            throttler=self._throttler, shared_client=self._shared_client, trading_pairs=trading_pairs, domain=domain
        ))
        self._user_stream_tracker = NdaxUserStreamTracker(
            throttler=self._throttler, shared_client=self._shared_client, auth_assistant=self._auth, domain=domain
        )
        self._domain = domain
        self._ev_loop = asyncio.get_event_loop()
        self._poll_notifier = asyncio.Event()
        self._last_timestamp = 0
        self._in_flight_orders = {}
        self._order_not_found_records = {}  # Dict[client_order_id:str, count:int]
        self._trading_rules = {}  # Dict[trading_pair:str, TradingRule]
        self._last_poll_timestamp = 0

        self._status_polling_task = None
        self._user_stream_tracker_task = None
        self._user_stream_event_listener_task = None
        self._trading_rules_polling_task = None

        self._account_id = None

    @property
    def name(self) -> str:
        return CONSTANTS.EXCHANGE_NAME

    @property
    def account_id(self) -> int:
        return self._account_id

    @property
    def trading_rules(self) -> Dict[str, TradingRule]:
        return self._trading_rules

    @property
    def in_flight_orders(self) -> Dict[str, NdaxInFlightOrder]:
        return self._in_flight_orders

    @property
    def status_dict(self) -> Dict[str, bool]:
        """
        A dictionary of statuses of various exchange's components. Used to determine if the connector is ready
        """
        return {
            "account_id_initialized": self.account_id if self._trading_required else True,
            "order_books_initialized": self.order_book_tracker.ready,
            "account_balance": len(self._account_balances) > 0 if self._trading_required else True,
            "trading_rule_initialized": len(self._trading_rules) > 0,
            "user_stream_initialized":
                self._user_stream_tracker.data_source.last_recv_time > 0 if self._trading_required else True,
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
        return self.order_book_tracker.order_books

    @property
    def limit_orders(self) -> List[LimitOrder]:
        return [
            in_flight_order.to_limit_order()
            for in_flight_order in self._in_flight_orders.values()
        ]

    @property
    def tracking_states(self) -> Dict[str, Any]:
        """
        :return active in-flight order in JSON format. Used to save order entries into local sqlite databse.
        """
        return {
            client_oid: order.to_json()
            for client_oid, order in self._in_flight_orders.items()
            if not order.is_done
        }

    async def initialized_account_id(self) -> int:
        if not self._account_id:
            self._account_id = await self._get_account_id()
        return self._account_id

    def restore_tracking_states(self, saved_states: Dict[str, Any]):
        """
        Restore in-flight orders from the saved tracking states(from local db). This is such that the connector can pick
        up from where it left off before Hummingbot client was terminated.
        :param saved_states: The saved tracking_states.
        """
        self._in_flight_orders.update({
            client_oid: NdaxInFlightOrder.from_json(order_json)
            for client_oid, order_json in saved_states.items()
        })

    def supported_order_types(self) -> List[OrderType]:
        """
        :return: a list of OrderType supported by this connector.
        Note that Market order type is no longer required and will not be used.
        """
        return [OrderType.MARKET, OrderType.LIMIT, OrderType.LIMIT_MAKER]

    async def _get_account_id(self) -> int:
        """
        Calls REST API to retrieve Account ID
        """
        params = {
            "OMSId": 1,
            "UserId": self._auth.uid,
            "UserName": self._auth.account_name
        }

        resp: List[int] = await self._api_request(
            "GET",
            path_url=CONSTANTS.USER_ACCOUNT_INFOS_PATH_URL,
            params=params,
            is_auth_required=True,
        )

        account_info = next((account_info for account_info in resp
                             if account_info.get("AccountName") == self._auth.account_name),
                            None)
        if account_info is None:
            self.logger().error(f"There is no account named {self._auth.account_name} "
                                f"associated with the current NDAX user")
            acc_id = None
        else:
            acc_id = int(account_info.get("AccountId"))

        return acc_id

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
        self.logger().warning("This exchange connector does not provide trades feed. "
                              "Strategies which depend on it will not work properly.")
        self.order_book_tracker.start()
        self._trading_rules_polling_task = safe_ensure_future(self._trading_rules_polling_loop())
        if self._trading_required:
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())
            self._user_stream_tracker_task = safe_ensure_future(self._user_stream_tracker.start())
            self._user_stream_event_listener_task = safe_ensure_future(self._user_stream_event_listener())

    async def stop_network(self):
        """
        This function is required by NetworkIterator base class and is called automatically.
        """
        self.order_book_tracker.stop()
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

    async def check_network(self) -> NetworkStatus:
        """
        This function is required by NetworkIterator base class and is called periodically to check
        the network connection. Simply ping the network (or call any light weight public API).
        """
        try:
            resp = await self._api_request(
                method="GET",
                path_url=CONSTANTS.PING_PATH_URL,
                limit_id=CONSTANTS.HTTP_PING_ID,
            )
            if "msg" not in resp or resp["msg"] != "PONG":
                raise Exception()
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    async def _api_request(self,
                           method: str,
                           path_url: str,
                           params: Optional[Dict[str, Any]] = None,
                           data: Optional[Dict[str, Any]] = None,
                           is_auth_required: bool = False,
                           limit_id: Optional[str] = None) -> Union[Dict[str, Any], List[Any]]:
        """
        Sends an aiohttp request and waits for a response.
        :param method: The HTTP method, e.g. get or post
        :param path_url: The path url or the API end point
        :param params: The query parameters of the API request
        :param params: The body parameters of the API request
        :param is_auth_required: Whether an authentication is required, when True the function will add encrypted
        signature to the request.
        :param limit_id: The id used for the API throttler. If not supplied, the `path_url` is used instead.
        :returns A response in json format.
        """
        url = ndax_utils.rest_api_url(self._domain) + path_url

        try:
            if is_auth_required:
                headers = self._auth.get_auth_headers()
            else:
                headers = self._auth.get_headers()

            limit_id = limit_id or path_url
            if method == "GET":
                async with self._throttler.execute_task(limit_id):
                    response = await self._shared_client.get(url, headers=headers, params=params)
            elif method == "POST":
                async with self._throttler.execute_task(limit_id):
                    response = await self._shared_client.post(url, headers=headers, data=ujson.dumps(data))
            else:
                raise NotImplementedError(f"{method} HTTP Method not implemented. ")

            data = await response.text()
            if data == CONSTANTS.API_LIMIT_REACHED_ERROR_MESSAGE:
                raise Exception(f"The exchange API request limit has been reached (original error '{data}')")

            parsed_response = await response.json()

        except ValueError as e:
            self.logger().error(f"{str(e)}")
            raise ValueError(f"Error authenticating request {method} {url}. Error: {str(e)}")
        except Exception as e:
            raise IOError(f"Error parsing data from {url}. Error: {str(e)}")
        if response.status != 200 or (isinstance(parsed_response, dict) and not parsed_response.get("result", True)):
            self.logger().error(f"Error fetching data from {url}. HTTP status is {response.status}. "
                                f"Message: {parsed_response} "
                                f"Params: {params} "
                                f"Data: {data}")
            raise Exception(f"Error fetching data from {url}. HTTP status is {response.status}. "
                            f"Message: {parsed_response} "
                            f"Params: {params} "
                            f"Data: {data}")

        return parsed_response

    def get_order_price_quantum(self, trading_pair: str, price: Decimal) -> Decimal:
        """
        Used by quantize_order_price() in _create_order()
        Returns a price step, a minimum price increment for a given trading pair.
        """
        trading_rule = self._trading_rules[trading_pair]
        return trading_rule.min_price_increment

    def get_order_size_quantum(self, trading_pair: str, order_size: Decimal) -> Decimal:
        """
        Used by quantize_order_price() in _create_order()
        Returns an order amount step, a minimum amount increment for a given trading pair.
        """
        trading_rule = self._trading_rules[trading_pair]
        return Decimal(trading_rule.min_base_amount_increment)

    def get_order_book(self, trading_pair: str) -> OrderBook:
        if trading_pair not in self.order_book_tracker.order_books:
            raise ValueError(f"No order book exists for '{trading_pair}'.")
        return self.order_book_tracker.order_books[trading_pair]

    async def _create_order(self,
                            trade_type: TradeType,
                            order_id: str,
                            trading_pair: str,
                            amount: Decimal,
                            price: Decimal = s_decimal_0,
                            order_type: OrderType = OrderType.MARKET):
        """
        Calls create-order API end point to place an order, starts tracking the order and triggers order created event.
        :param trade_type: BUY or SELL
        :param order_id: Internal order id (also called client_order_id)
        :param trading_pair: The market to place order
        :param amount: The order amount (in base token value)
        :param price: The order price
        :param order_type: The order type
        """
        trading_rule: TradingRule = self._trading_rules[trading_pair]

        trading_pair_ids: Dict[str, int] = await self.order_book_tracker.data_source.get_instrument_ids()

        try:
            amount: Decimal = self.quantize_order_amount(trading_pair, amount)
            if amount < trading_rule.min_order_size:
                raise ValueError(f"{trade_type.name} order amount {amount} is lower than the minimum order size "
                                 f"{trading_rule.min_order_size}.")

            params = {
                "InstrumentId": trading_pair_ids[trading_pair],
                "OMSId": 1,
                "AccountId": await self.initialized_account_id(),
                "ClientOrderId": int(order_id),
                "Side": 0 if trade_type == TradeType.BUY else 1,
                "Quantity": amount,
                "TimeInForce": 1,  # GTC
            }

            if order_type.is_limit_type():
                price: Decimal = self.quantize_order_price(trading_pair, price)

                params.update({
                    "OrderType": 2,  # Limit
                    "LimitPrice": price,
                })
            else:
                params.update({
                    "OrderType": 1  # Market
                })

            self.start_tracking_order(order_id,
                                      None,
                                      trading_pair,
                                      trade_type,
                                      price,
                                      amount,
                                      order_type
                                      )

            send_order_results = await self._api_request(
                method="POST",
                path_url=CONSTANTS.SEND_ORDER_PATH_URL,
                data=params,
                is_auth_required=True
            )

            if send_order_results["status"] == "Rejected":
                raise ValueError(f"Order is rejected by the API. "
                                 f"Parameters: {params} Error Msg: {send_order_results['errormsg']}")

            exchange_order_id = str(send_order_results["OrderId"])
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(f"Created {order_type.name} {trade_type.name} order {order_id} for "
                                   f"{amount} {trading_pair}.")
                tracked_order.update_exchange_order_id(exchange_order_id)

        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.stop_tracking_order(order_id)
            self.trigger_event(MarketEvent.OrderFailure,
                               MarketOrderFailureEvent(self.current_timestamp, order_id, order_type))
            self.logger().network(
                f"Error submitting {trade_type.name} {order_type.name} order to NDAX for "
                f"{amount} {trading_pair} {price}. Error: {str(e)}",
                exc_info=True,
                app_warning_msg="Error submitting order to NDAX. "
            )

    def trigger_order_created_event(self, order: NdaxInFlightOrder):
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
                               order.creation_timestamp,
                               exchange_order_id=order.exchange_order_id
                           ))

    def buy(self, trading_pair: str, amount: Decimal, order_type: OrderType = OrderType.MARKET,
            price: Decimal = s_decimal_NaN, **kwargs) -> str:
        """
        Buys an amount of base asset as specified in the trading pair. This function returns immediately.
        To see an actual order, wait for a BuyOrderCreatedEvent.
        :param trading_pair: The market (e.g. BTC-CAD) to buy from
        :param amount: The amount in base token value
        :param order_type: The order type
        :param price: The price in which the order is to be placed at
        :returns A new client order id
        """
        order_id: str = ndax_utils.get_new_client_order_id(True, trading_pair)
        safe_ensure_future(self._create_order(trade_type=TradeType.BUY,
                                              trading_pair=trading_pair,
                                              order_id=order_id,
                                              amount=amount,
                                              price=price,
                                              order_type=order_type,
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
        :returns A new client order id
        """
        order_id: str = ndax_utils.get_new_client_order_id(False, trading_pair)
        safe_ensure_future(self._create_order(trade_type=TradeType.SELL,
                                              trading_pair=trading_pair,
                                              order_id=order_id,
                                              amount=amount,
                                              price=price,
                                              order_type=order_type,
                                              ))
        return order_id

    async def _execute_cancel(self, trading_pair: str, order_id: str) -> str:
        """
        To determine if an order is successfully canceled, we either call the
        GetOrderStatus/GetOpenOrders endpoint or wait for a OrderStateEvent/OrderTradeEvent from the WS.
        :param trading_pair: The market (e.g. BTC-CAD) the order is in.
        :param order_id: The client_order_id of the order to be cancelled.
        """
        try:
            tracked_order: Optional[NdaxInFlightOrder] = self._in_flight_orders.get(order_id, None)
            if tracked_order is None:
                raise ValueError(f"Failed to cancel order - {order_id}. Order not being tracked.")
            if tracked_order.is_locally_working:
                raise NdaxInFlightOrderNotCreated(
                    f"Failed to cancel order - {order_id}. Order not yet created."
                    f" This is most likely due to rate-limiting."
                )

            body_params = {
                "OMSId": 1,
                "AccountId": await self.initialized_account_id(),
                "OrderId": await tracked_order.get_exchange_order_id()
            }

            # The API response simply verifies that the API request have been received by the API servers.
            await self._api_request(
                method="POST",
                path_url=CONSTANTS.CANCEL_ORDER_PATH_URL,
                data=body_params,
                is_auth_required=True
            )

            return order_id

        except asyncio.CancelledError:
            raise
        except NdaxInFlightOrderNotCreated:
            raise
        except Exception as e:
            self.logger().error(f"Failed to cancel order {order_id}: {str(e)}")
            self.logger().network(
                f"Failed to cancel order {order_id}: {str(e)}",
                exc_info=True,
                app_warning_msg=f"Failed to cancel order {order_id} on NDAX. "
                                f"Check API key and network connection."
            )
            if RESOURCE_NOT_FOUND_ERR in str(e):
                self._order_not_found_records[order_id] = self._order_not_found_records.get(order_id, 0) + 1
                if self._order_not_found_records[order_id] >= self.ORDER_EXCEED_NOT_FOUND_COUNT:
                    self.logger().warning(f"Order {order_id} does not seem to be active, will stop tracking order...")
                    self.stop_tracking_order(order_id)
                    self.trigger_event(MarketEvent.OrderCancelled,
                                       OrderCancelledEvent(self.current_timestamp, order_id))

    def cancel(self, trading_pair: str, order_id: str):
        """
        Cancel an order. This function returns immediately.
        An Order is only determined to be cancelled when a OrderCancelledEvent is received.
        :param trading_pair: The market (e.g. BTC-CAD) of the order.
        :param order_id: The client_order_id of the order to be cancelled.
        """
        safe_ensure_future(self._execute_cancel(trading_pair, order_id))
        return order_id

    async def get_open_orders(self) -> List[OpenOrder]:
        query_params = {
            "OMSId": 1,
            "AccountId": await self.initialized_account_id(),
        }
        open_orders: List[Dict[str, Any]] = await self._api_request(method="GET",
                                                                    path_url=CONSTANTS.GET_OPEN_ORDERS_PATH_URL,
                                                                    params=query_params,
                                                                    is_auth_required=True)

        trading_pair_id_map: Dict[str, int] = await self.order_book_tracker.data_source.get_instrument_ids()
        id_trading_pair_map: Dict[int, str] = {instrument_id: trading_pair
                                               for trading_pair, instrument_id in trading_pair_id_map.items()}

        return [OpenOrder(client_order_id=order["ClientOrderId"],
                          trading_pair=id_trading_pair_map[order["Instrument"]],
                          price=Decimal(str(order["Price"])),
                          amount=Decimal(str(order["Quantity"])),
                          executed_amount=Decimal(str(order["QuantityExecuted"])),
                          status=order["OrderState"],
                          order_type=OrderType.LIMIT if order["OrderType"] == "Limit" else OrderType.MARKET,
                          is_buy=True if order["Side"] == "Buy" else False,
                          time=order["ReceiveTime"],
                          exchange_order_id=order["OrderId"],
                          )
                for order in open_orders]

    async def cancel_all(self, timeout_sec: float) -> List[CancellationResult]:
        """
        Cancels all in-flight orders and waits for cancellation results.
        Used by bot's top level stop and exit commands (cancelling outstanding orders on exit)
        :param timeout_sec: The timeout at which the operation will be canceled.
        :returns List of CancellationResult which indicates whether each order is successfully cancelled.
        """

        # Note: NDAX's CancelOrder endpoint simply indicates if the cancel requests has been successfully received.
        cancellation_results = []
        tracked_orders = self.in_flight_orders
        try:
            for order in tracked_orders.values():
                self.cancel(trading_pair=order.trading_pair,
                            order_id=order.client_order_id)

            open_orders = await self.get_open_orders()

            for client_oid, tracked_order in tracked_orders.items():
                matched_order = [o for o in open_orders if o.client_order_id == client_oid]
                if not matched_order:
                    cancellation_results.append(CancellationResult(client_oid, True))
                    self.trigger_event(MarketEvent.OrderCancelled,
                                       OrderCancelledEvent(self.current_timestamp, client_oid))
                else:
                    cancellation_results.append(CancellationResult(client_oid, False))

        except Exception as ex:
            self.logger().network(
                f"Failed to cancel all orders ({ex})",
                exc_info=True,
                app_warning_msg="Failed to cancel all orders on NDAX. Check API key and network connection."
            )
        return cancellation_results

    def _format_trading_rules(self, instrument_info: List[Dict[str, Any]]) -> Dict[str, TradingRule]:
        """
        Converts JSON API response into a local dictionary of trading rules.
        :param instrument_info: The JSON API response.
        :returns: A dictionary of trading pair to its respective TradingRule.
        """
        result = {}
        for instrument in instrument_info:
            try:
                trading_pair = f"{instrument['Product1Symbol']}-{instrument['Product2Symbol']}"

                result[trading_pair] = TradingRule(trading_pair=trading_pair,
                                                   min_order_size=Decimal(str(instrument["MinimumQuantity"])),
                                                   min_price_increment=Decimal(str(instrument["PriceIncrement"])),
                                                   min_base_amount_increment=Decimal(str(instrument["QuantityIncrement"])),
                                                   )
            except Exception:
                self.logger().error(f"Error parsing the trading pair rule: {instrument}. Skipping...",
                                    exc_info=True)
        return result

    async def _update_trading_rules(self):
        params = {
            "OMSId": 1
        }
        instrument_info: List[Dict[str, Any]] = await self._api_request(
            method="GET",
            path_url=CONSTANTS.MARKETS_URL,
            params=params
        )
        self._trading_rules.clear()
        self._trading_rules = self._format_trading_rules(instrument_info)

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
                                      app_warning_msg="Could not fetch new trading rules from NDAX. "
                                      "Check network connection.")
                await asyncio.sleep(0.5)

    async def _update_balances(self):
        """
        Calls REST API to update total and available balances
        """
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        params = {
            "OMSId": 1,
            "AccountId": await self.initialized_account_id()
        }
        account_positions: List[Dict[str, Any]] = await self._api_request(
            method="GET",
            path_url=CONSTANTS.ACCOUNT_POSITION_PATH_URL,
            params=params,
            is_auth_required=True
        )
        for position in account_positions:
            asset_name = position["ProductSymbol"]
            self._account_balances[asset_name] = Decimal(str(position["Amount"]))
            self._account_available_balances[asset_name] = self._account_balances[asset_name] - Decimal(
                str(position["Hold"]))
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    def start_tracking_order(self,
                             order_id: str,
                             exchange_order_id: Optional[str],
                             trading_pair: str,
                             trade_type: TradeType,
                             price: Decimal,
                             amount: Decimal,
                             order_type: OrderType):
        """
        Starts tracking an order by simply adding it into _in_flight_orders dictionary.
        """
        self._in_flight_orders[order_id] = NdaxInFlightOrder(
            client_order_id=order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=trading_pair,
            order_type=order_type,
            trade_type=trade_type,
            price=price,
            amount=amount,
            creation_timestamp=self.current_timestamp
        )

    def stop_tracking_order(self, order_id: str):
        """
        Stops tracking an order by simply removing it from _in_flight_orders dictionary.
        """
        if order_id in self._in_flight_orders:
            del self._in_flight_orders[order_id]

    async def _update_order_status(self):
        """
        Calls REST API to get order status
        """
        # Waiting on buy and sell functionality.
        active_orders: List[NdaxInFlightOrder] = [
            o for o in self._in_flight_orders.values()
            if not o.is_locally_working
        ]
        if len(active_orders) == 0:
            return

        tasks = []
        for active_order in active_orders:
            ex_order_id: Optional[str] = None
            try:
                ex_order_id = await active_order.get_exchange_order_id()
            except asyncio.TimeoutError:
                # We assume that tracked orders without an exchange order id is an order that failed to be created.
                self._order_not_found_records[active_order.client_order_id] = self._order_not_found_records.get(active_order.client_order_id, 0) + 1
                self.logger().debug(f"Tracker order {active_order.client_order_id} does not have an exchange id."
                                    f"Attempting fetch in next polling interval")
                if self._order_not_found_records[active_order.client_order_id] >= self.ORDER_EXCEED_NOT_FOUND_COUNT:
                    self.logger().info(f"Order {active_order.client_order_id} does not seem to be active, will stop tracking order...")
                    self.stop_tracking_order(active_order.client_order_id)
                    self.trigger_event(MarketEvent.OrderCancelled,
                                       OrderCancelledEvent(self.current_timestamp, active_order.client_order_id))
                continue

            query_params = {
                "OMSId": 1,
                "AccountId": await self.initialized_account_id(),
                "OrderId": int(ex_order_id),
            }

            tasks.append(
                asyncio.create_task(self._api_request(method="GET",
                                                      path_url=CONSTANTS.GET_ORDER_STATUS_PATH_URL,
                                                      params=query_params,
                                                      is_auth_required=True,
                                                      )))
        self.logger().debug(f"Polling for order status updates of {len(tasks)} orders. ")

        raw_responses: List[Dict[str, Any]] = await safe_gather(*tasks, return_exceptions=True)

        # Initial parsing of responses. Removes Exceptions.
        parsed_status_responses: List[Dict[str, Any]] = []
        for resp in raw_responses:
            if not isinstance(resp, Exception):
                parsed_status_responses.append(resp)
            else:
                self.logger().error(f"Error fetching order status. Response: {resp}")

        if len(parsed_status_responses) == 0:
            return

        min_ts: int = min([int(order_status["ReceiveTime"])
                           for order_status in parsed_status_responses])

        trade_history_tasks = []
        trading_pair_ids: Dict[str, int] = await self.order_book_tracker.data_source.get_instrument_ids()

        for trading_pair in self._trading_pairs:
            body_params = {
                "OMSId": 1,
                "AccountId": await self.initialized_account_id(),
                "UserId": self._auth.uid,
                "InstrumentId": trading_pair_ids[trading_pair],
                "StartTimestamp": min_ts,
            }
            trade_history_tasks.append(
                asyncio.create_task(self._api_request(method="POST",
                                                      path_url=CONSTANTS.GET_TRADES_HISTORY_PATH_URL,
                                                      data=body_params,
                                                      is_auth_required=True)))

        raw_responses: List[Dict[str, Any]] = await safe_gather(*trade_history_tasks, return_exceptions=True)

        # Initial parsing of responses. Joining all the responses
        parsed_history_resps: List[Dict[str, Any]] = []
        for resp in raw_responses:
            if not isinstance(resp, Exception):
                parsed_history_resps.extend(resp)
            else:
                self.logger().error(f"Error fetching trades history. Response: {resp}")

        # Trade updates must be handled before any order status updates.
        for trade in parsed_history_resps:
            self._process_trade_event_message(trade)

        for order_status in parsed_status_responses:
            self._process_order_event_message(order_status)

    def _reset_poll_notifier(self):
        self._poll_notifier = asyncio.Event()

    async def _status_polling_loop(self):
        """
        Periodically update user balances and order status via REST API. This serves as a fallback measure for web
        socket API updates.
        """
        while True:
            try:
                self._reset_poll_notifier()
                await self._poll_notifier.wait()
                start_ts = self.current_timestamp
                await safe_gather(
                    self._update_balances(),
                    self._update_order_status(),
                )
                self._last_poll_timestamp = start_ts
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"Unexpected error while in status polling loop. Error: {str(e)}", exc_info=True)
                self.logger().network("Unexpected error while fetching account updates.",
                                      exc_info=True,
                                      app_warning_msg="Could not fetch account updates from NDAX. "
                                                      "Check API key and network connection.")
                await asyncio.sleep(0.5)

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
                endpoint = NdaxWebSocketAdaptor.endpoint_from_message(event_message)
                payload = NdaxWebSocketAdaptor.payload_from_message(event_message)

                if endpoint == CONSTANTS.ACCOUNT_POSITION_EVENT_ENDPOINT_NAME:
                    self._process_account_position_event(payload)
                elif endpoint == CONSTANTS.ORDER_STATE_EVENT_ENDPOINT_NAME:
                    self._process_order_event_message(payload)
                elif endpoint == CONSTANTS.ORDER_TRADE_EVENT_ENDPOINT_NAME:
                    self._process_trade_event_message(payload)
                else:
                    self.logger().debug(f"Unknown event received from the connector ({event_message})")
            except asyncio.CancelledError:
                raise
            except Exception as ex:
                self.logger().error(f"Unexpected error in user stream listener loop ({ex})", exc_info=True)
                await asyncio.sleep(5.0)

    def _process_account_position_event(self, account_position_event: Dict[str, Any]):
        token = account_position_event["ProductSymbol"]
        amount = Decimal(str(account_position_event["Amount"]))
        on_hold = Decimal(str(account_position_event["Hold"]))
        self._account_balances[token] = amount
        self._account_available_balances[token] = (amount - on_hold)

    def _process_order_event_message(self, order_msg: Dict[str, Any]):
        """
        Updates in-flight order and triggers cancellation or failure event if needed.
        :param order_msg: The order event message payload
        """
        client_order_id = str(order_msg["ClientOrderId"])
        if client_order_id in self.in_flight_orders:
            tracked_order = self.in_flight_orders[client_order_id]
            was_locally_working = tracked_order.is_locally_working

            # Update order execution status
            tracked_order.last_state = order_msg["OrderState"]

            if was_locally_working and tracked_order.is_working:
                self.trigger_order_created_event(tracked_order)
            elif tracked_order.is_cancelled:
                self.logger().info(f"Successfully canceled order {client_order_id}")
                self.trigger_event(MarketEvent.OrderCancelled,
                                   OrderCancelledEvent(
                                       self.current_timestamp,
                                       client_order_id))
                self.stop_tracking_order(client_order_id)
            elif tracked_order.is_failure:
                self.logger().info(f"The market order {client_order_id} has failed according to order status event. "
                                   f"Reason: {order_msg['ChangeReason']}")
                self.trigger_event(MarketEvent.OrderFailure,
                                   MarketOrderFailureEvent(
                                       self.current_timestamp,
                                       client_order_id,
                                       tracked_order.order_type
                                   ))
                self.stop_tracking_order(client_order_id)

    def _process_trade_event_message(self, order_msg: Dict[str, Any]):
        """
        Updates in-flight order and trigger order filled event for trade message received. Triggers order completed
        event if the total executed amount equals to the specified order amount.
        :param order_msg: The order event message payload
        """

        client_order_id = str(order_msg["ClientOrderId"])
        if client_order_id in self.in_flight_orders:
            tracked_order = self.in_flight_orders[client_order_id]
            updated = tracked_order.update_with_trade_update(order_msg)

            if updated:
                trade_amount = Decimal(str(order_msg["Quantity"]))
                trade_price = Decimal(str(order_msg["Price"]))
                trade_fee = self.get_fee(base_currency=tracked_order.base_asset,
                                         quote_currency=tracked_order.quote_asset,
                                         order_type=tracked_order.order_type,
                                         order_side=tracked_order.trade_type,
                                         amount=trade_amount,
                                         price=trade_price)
                amount_for_fee = (trade_amount if tracked_order.trade_type is TradeType.BUY
                                  else trade_amount * trade_price)
                tracked_order.fee_paid += amount_for_fee * trade_fee.percent

                self.trigger_event(
                    MarketEvent.OrderFilled,
                    OrderFilledEvent(
                        self.current_timestamp,
                        tracked_order.client_order_id,
                        tracked_order.trading_pair,
                        tracked_order.trade_type,
                        tracked_order.order_type,
                        trade_price,
                        trade_amount,
                        trade_fee,
                        exchange_trade_id=str(order_msg["TradeId"])
                    )
                )
                if (math.isclose(tracked_order.executed_amount_base, tracked_order.amount) or
                        tracked_order.executed_amount_base >= tracked_order.amount):
                    tracked_order.mark_as_filled()
                    self.logger().info(f"The {tracked_order.trade_type.name} order "
                                       f"{tracked_order.client_order_id} has completed "
                                       f"according to order status API")
                    event_tag = (MarketEvent.BuyOrderCompleted if tracked_order.trade_type is TradeType.BUY
                                 else MarketEvent.SellOrderCompleted)
                    event_class = (BuyOrderCompletedEvent if tracked_order.trade_type is TradeType.BUY
                                   else SellOrderCompletedEvent)
                    self.trigger_event(event_tag,
                                       event_class(self.current_timestamp,
                                                   tracked_order.client_order_id,
                                                   tracked_order.base_asset,
                                                   tracked_order.quote_asset,
                                                   tracked_order.executed_amount_base,
                                                   tracked_order.executed_amount_quote,
                                                   tracked_order.order_type,
                                                   tracked_order.exchange_order_id))
                    self.stop_tracking_order(tracked_order.client_order_id)

    async def all_trading_pairs(self) -> List[str]:
        # This method should be removed and instead we should implement _initialize_trading_pair_symbol_map
        return await NdaxAPIOrderBookDataSource.fetch_trading_pairs(
            domain=self._domain,
            throttler=self._throttler,
        )

    async def get_last_traded_prices(self, trading_pairs: List[str]) -> Dict[str, float]:
        # This method should be removed and instead we should implement _get_last_traded_price
        return await NdaxAPIOrderBookDataSource.get_last_traded_prices(
            trading_pairs=trading_pairs,
            domain=self._domain,
            throttler=self._throttler,
            shared_client=self._shared_client)
