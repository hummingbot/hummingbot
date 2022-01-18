import asyncio
import copy
import json
import logging
import math
from decimal import Decimal
from typing import Any, AsyncIterable, Dict, List, Optional

from hummingbot.connector.exchange.bitmart import bitmart_constants as CONSTANTS
from hummingbot.connector.exchange.bitmart import bitmart_utils
from hummingbot.connector.exchange.bitmart.bitmart_auth import BitmartAuth
from hummingbot.connector.exchange.bitmart.bitmart_in_flight_order import BitmartInFlightOrder
from hummingbot.connector.exchange.bitmart.bitmart_order_book_tracker import BitmartOrderBookTracker
from hummingbot.connector.exchange.bitmart.bitmart_user_stream_tracker import BitmartUserStreamTracker
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.clock import Clock
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.common import OpenOrder
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
    OrderType,
    SellOrderCompletedEvent,
    SellOrderCreatedEvent,
    TradeType
)
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.estimate_fee import estimate_fee
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest
from hummingbot.core.web_assistant.rest_assistant import RESTAssistant
from hummingbot.logger import HummingbotLogger

ctce_logger = None
s_decimal_NaN = Decimal("nan")
s_decimal_0 = Decimal(0)


class BitmartExchange(ExchangeBase):
    """
    BitmartExchange connects with BitMart exchange and provides order book pricing, user account tracking and
    trading functionality.
    """
    API_CALL_TIMEOUT = 10.0
    POLL_INTERVAL = 1.0
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0
    UPDATE_TRADE_STATUS_MIN_INTERVAL = 10.0

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global ctce_logger
        if ctce_logger is None:
            ctce_logger = logging.getLogger(__name__)
        return ctce_logger

    def __init__(self,
                 bitmart_api_key: str,
                 bitmart_secret_key: str,
                 bitmart_memo: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True,
                 ):
        """
        :param bitmart_api_key: The API key to connect to private BitMart APIs.
        :param bitmart_secret_key: The API secret.
        :param trading_pairs: The market trading pairs which to track order book data.
        :param trading_required: Whether actual trading is needed.
        """
        super().__init__()
        self._api_factory = bitmart_utils.build_api_factory()
        self._rest_assistant = None
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._bitmart_auth = BitmartAuth(api_key=bitmart_api_key,
                                         secret_key=bitmart_secret_key,
                                         memo=bitmart_memo)
        self._throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        self._order_book_tracker = BitmartOrderBookTracker(
            throttler=self._throttler, trading_pairs=trading_pairs
        )
        self._user_stream_tracker = BitmartUserStreamTracker(
            throttler=self._throttler, bitmart_auth=self._bitmart_auth, trading_pairs=trading_pairs
        )
        self._ev_loop = asyncio.get_event_loop()
        self._shared_client = None
        self._poll_notifier = asyncio.Event()
        self._last_timestamp = 0
        self._in_flight_orders = {}  # Dict[client_order_id:str, BitmartInFlightOrder]
        self._order_not_found_records = {}  # Dict[client_order_id:str, count:int]
        self._trading_rules = {}  # Dict[trading_pair:str, TradingRule]
        self._status_polling_task = None
        self._user_stream_event_listener_task = None
        self._trading_rules_polling_task = None
        self._last_poll_timestamp = 0
        self._real_time_balance_update = False

    @property
    def name(self) -> str:
        return "bitmart"

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        return self._order_book_tracker.order_books

    @property
    def trading_rules(self) -> Dict[str, TradingRule]:
        return self._trading_rules

    @property
    def in_flight_orders(self) -> Dict[str, BitmartInFlightOrder]:
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

    def restore_tracking_states(self, saved_states: Dict[str, any]):
        """
        Restore in-flight orders from saved tracking states, this is st the connector can pick up on where it left off
        when it disconnects.
        :param saved_states: The saved tracking_states.
        """
        self._in_flight_orders.update({
            key: BitmartInFlightOrder.from_json(value)
            for key, value in saved_states.items()
        })

    def supported_order_types(self) -> List[OrderType]:
        """
        :return a list of OrderType supported by this connector.
        Note that Market order type is no longer required and will not be used.
        """
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER]

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
            request = RESTRequest(
                method=RESTMethod.GET,
                url=f"{CONSTANTS.REST_URL}/{CONSTANTS.CHECK_NETWORK_PATH_URL}",
            )
            rest_assistant = await self._get_rest_assistant()
            response = await rest_assistant.call(request=request)
            if response.status != 200:
                raise Exception
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    async def _get_rest_assistant(self) -> RESTAssistant:
        if self._rest_assistant is None:
            self._rest_assistant = await self._api_factory.get_rest_assistant()
        return self._rest_assistant

    async def _trading_rules_polling_loop(self):
        """
        Periodically update trading rule.
        """
        while True:
            try:
                await self._update_trading_rules()
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().network(f"Unexpected error while fetching trading rules. Error: {str(e)}",
                                      exc_info=True,
                                      app_warning_msg="Could not fetch new trading rules from BitMart. "
                                                      "Check network connection.")
                await asyncio.sleep(0.5)

    async def _update_trading_rules(self):
        request = RESTRequest(
            method=RESTMethod.GET,
            url=f"{CONSTANTS.REST_URL}/{CONSTANTS.GET_TRADING_RULES_PATH_URL}",
        )
        rest_assistant = await self._get_rest_assistant()
        response = await rest_assistant.call(request=request)

        symbols_details: Dict[str, Any] = await response.json()
        self._trading_rules.clear()
        self._trading_rules = self._format_trading_rules(symbols_details)

    def _format_trading_rules(self, symbols_details: Dict[str, Any]) -> Dict[str, TradingRule]:
        """
        Converts json API response into a dictionary of trading rules.
        :param symbols_details: The json API response
        :return A dictionary of trading rules.
        Response Example:
        {
            "code": 1000,
            "trace":"886fb6ae-456b-4654-b4e0-d681ac05cea1",
            "message": "OK",
            "data": {
                "symbols": [
                    {
                        "symbol":"GXC_BTC",
                         "symbol_id":1024,
                         "base_currency":"GXC",
                         "quote_currency":"BTC",
                         "quote_increment":"1.00000000",
                         "base_min_size":"1.00000000",
                         "base_max_size":"10000000.00000000",
                         "price_min_precision":6,
                         "price_max_precision":8,
                         "expiration":"NA",
                         "min_buy_amount":"0.00010000",
                         "min_sell_amount":"0.00010000"
                    },
                    ...
                ]
            }
        }
        """
        result = {}
        for rule in symbols_details["data"]["symbols"]:
            try:
                trading_pair = bitmart_utils.convert_from_exchange_trading_pair(rule["symbol"])
                price_decimals = Decimal(str(rule["price_max_precision"]))
                # E.g. a price decimal of 2 means 0.01 incremental.
                price_step = Decimal("1") / Decimal(str(math.pow(10, price_decimals)))
                result[trading_pair] = TradingRule(trading_pair=trading_pair,
                                                   min_order_size=Decimal(str(rule["base_min_size"])),
                                                   max_order_size=Decimal(str(rule["base_max_size"])),
                                                   min_order_value=Decimal(str(rule["min_buy_amount"])),
                                                   min_base_amount_increment=Decimal(str(rule["quote_increment"])),
                                                   min_price_increment=price_step)
            except Exception:
                self.logger().error(f"Error parsing the trading pair rule {rule}. Skipping.", exc_info=True)
        return result

    async def _api_request(self,
                           method: str,
                           path_url: str,
                           params: Optional[Dict[str, Any]] = None,
                           auth_type: str = None) -> Dict[str, Any]:
        """
        Sends an aiohttp request and waits for a response.
        :param method: The HTTP method, e.g. get or post
        :param path_url: The path url or the API end point
        :param params: Request parameters
        :param auth_type: Type of Authorization header to send in request, from {"SIGNED", "KEYED", None}
        :returns A response in json format.
        """
        params = params or {}
        async with self._throttler.execute_task(path_url):
            url = f"{CONSTANTS.REST_URL}/{path_url}"

            headers = self._bitmart_auth.get_headers(bitmart_utils.get_ms_timestamp(), params, auth_type)

            if method == "get":
                request = RESTRequest(
                    method=RESTMethod.GET,
                    url=url,
                    headers=headers,
                    params=params
                )
                rest_assistant = await self._get_rest_assistant()
                response = await rest_assistant.call(request=request)
            elif method == "post":
                post_json = json.dumps(params)
                request = RESTRequest(
                    method=RESTMethod.POST,
                    url=url,
                    headers=headers,
                    data=post_json
                )
                rest_assistant = await self._get_rest_assistant()
                response = await rest_assistant.call(request=request)
            else:
                raise NotImplementedError

            try:
                parsed_response = json.loads(await response.text())
            except Exception as e:
                raise IOError(f"Error parsing data from {url}. Error: {str(e)}")
            if response.status != 200:
                raise IOError(f"Error calling {url}. HTTP status is {response.status}. "
                              f"Message: {parsed_response['message']}")
            if int(parsed_response["code"]) != 1000:
                raise IOError(f"{url} API call failed, error message: {parsed_response['message']}")
            return parsed_response

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

    def buy(self, trading_pair: str, amount: Decimal, order_type=OrderType.MARKET,
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
        order_id: str = bitmart_utils.get_new_client_order_id(True, trading_pair)
        safe_ensure_future(self._create_order(TradeType.BUY, order_id, trading_pair, amount, order_type, price))
        return order_id

    def sell(self, trading_pair: str, amount: Decimal, order_type=OrderType.MARKET,
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
        order_id: str = bitmart_utils.get_new_client_order_id(False, trading_pair)
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
        if not order_type.is_limit_type():
            raise Exception(f"Unsupported order type: {order_type}")
        trading_rule = self._trading_rules[trading_pair]

        try:
            amount = self.quantize_order_amount(trading_pair, amount)
            price = self.quantize_order_price(trading_pair, price)
            if amount < trading_rule.min_order_size:
                raise ValueError(f"Buy order amount {amount} is lower than the minimum order size "
                                 f"{trading_rule.min_order_size}.")
            api_params = {"symbol": bitmart_utils.convert_to_exchange_trading_pair(trading_pair),
                          "side": trade_type.name.lower(),
                          "type": "limit",
                          "size": f"{amount:f}",
                          "price": f"{price:f}"
                          }
            self.start_tracking_order(order_id,
                                      None,
                                      trading_pair,
                                      trade_type,
                                      price,
                                      amount,
                                      order_type
                                      )

            order_result = await self._api_request("post", CONSTANTS.CREATE_ORDER_PATH_URL, api_params, "SIGNED")
            exchange_order_id = str(order_result["data"]["order_id"])
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(f"Created {order_type.name} {trade_type.name} order {order_id} for "
                                   f"{amount} {trading_pair}.")
                tracked_order.update_exchange_order_id(exchange_order_id)

            event_tag = MarketEvent.BuyOrderCreated if trade_type is TradeType.BUY else MarketEvent.SellOrderCreated
            event_class = BuyOrderCreatedEvent if trade_type is TradeType.BUY else SellOrderCreatedEvent
            self.trigger_event(event_tag,
                               event_class(
                                   self.current_timestamp,
                                   order_type,
                                   trading_pair,
                                   amount,
                                   price,
                                   order_id
                               ))
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.stop_tracking_order(order_id)
            self.logger().network(
                f"Error submitting {trade_type.name} {order_type.name} order to BitMart for "
                f"{amount} {trading_pair} "
                f"{price}.",
                exc_info=True,
                app_warning_msg=str(e)
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
        self._in_flight_orders[order_id] = BitmartInFlightOrder(
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

    async def _execute_cancel(self, trading_pair: str, order_id: str) -> str:
        """
        Executes order cancellation process by first calling cancel-order API. The API result doesn't confirm whether
        the cancellation is successful, it simply states it receives the request.
        :param trading_pair: The market trading pair
        :param order_id: The internal order id
        order.last_state to change to CANCELED
        """
        try:
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is None:
                raise ValueError(f"Failed to cancel order - {order_id}. Order not found.")
            if tracked_order.exchange_order_id is None:
                await tracked_order.get_exchange_order_id()
            ex_order_id = tracked_order.exchange_order_id
            response = await self._api_request(
                "post",
                CONSTANTS.CANCEL_ORDER_PATH_URL,
                {"symbol": bitmart_utils.convert_to_exchange_trading_pair(trading_pair),
                 "order_id": int(ex_order_id)},
                "SIGNED"
            )

            # result = True is a successful cancel, False indicates cancel failed due to already cancelled or matched
            if "result" in response["data"] and not response["data"]["result"]:
                raise ValueError(f"Failed to cancel order - {order_id}. Order was already matched or cancelled on the exchange.")
            return order_id
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(
                f"Failed to cancel order {order_id}: {str(e)}",
                exc_info=True,
                app_warning_msg=f"Failed to cancel the order {order_id} on Bitmart. "
                                f"Check API key and network connection."
            )

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
                self._last_poll_timestamp = self.current_timestamp
                self._poll_notifier.clear()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(str(e), exc_info=True)
                self.logger().network("Unexpected error while fetching account updates.",
                                      exc_info=True,
                                      app_warning_msg="Could not fetch account updates from BitMart. "
                                                      "Check API key and network connection.")
                await asyncio.sleep(0.5)

    async def _update_balances(self):
        """
        Calls REST API to update total and available balances.
        """
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()
        account_info = await self._api_request("get", CONSTANTS.GET_ACCOUNT_SUMMARY_PATH_URL, {}, "KEYED")
        for account in account_info["data"]["wallet"]:
            asset_name = account["id"]
            self._account_available_balances[asset_name] = Decimal(str(account["available"]))
            self._account_balances[asset_name] = Decimal(str(account["available"])) + Decimal(str(account["frozen"]))
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

        self._in_flight_orders_snapshot = {k: copy.copy(v) for k, v in self._in_flight_orders.items()}
        self._in_flight_orders_snapshot_timestamp = self.current_timestamp

    async def _update_order_status(self):
        """
        Calls REST API to get status update for each in-flight order.
        """
        last_tick = int(self._last_poll_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL)
        current_tick = int(self.current_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL)

        if current_tick > last_tick and len(self._in_flight_orders) > 0:
            tracked_orders = list(self._in_flight_orders.values())
            tasks = []
            for tracked_order in tracked_orders:
                order_id = await tracked_order.get_exchange_order_id()
                trading_pair = tracked_order.trading_pair
                tasks.append(self._api_request("get",
                                               CONSTANTS.GET_ORDER_DETAIL_PATH_URL,
                                               {"order_id": int(order_id),
                                                "symbol": bitmart_utils.convert_to_exchange_trading_pair(trading_pair)},
                                               "KEYED"
                                               ))
            self.logger().debug(f"Polling for order status updates of {len(tasks)} orders.")
            responses = await safe_gather(*tasks, return_exceptions=True)
            for response in responses:
                if isinstance(response, Exception):
                    raise response
                if "data" not in response:
                    self.logger().info(f"_update_order_status data not in resp: {response}")
                    continue
                result = response["data"]
                await self._process_trade_message_rest(result)
                await self._process_order_message(result)

    async def _process_order_message(self, order_msg: Dict[str, Any]):
        """
        Updates in-flight order and triggers cancellation or failure event if needed.
        :param order_msg: The order response from either REST or web socket API (they are of the same format)
        """
        for order in self._in_flight_orders.values():
            await order.get_exchange_order_id()
        exchange_order_id = str(order_msg["order_id"])
        tracked_orders = list(self._in_flight_orders.values())
        tracked_order = [order for order in tracked_orders if exchange_order_id == order.exchange_order_id]
        if not tracked_order:
            return
        tracked_order = tracked_order[0]
        client_order_id = tracked_order.client_order_id

        # Update order execution status
        if "status" in order_msg:       # REST API
            tracked_order.last_state = CONSTANTS.ORDER_STATUS[int(order_msg["status"])]
        elif "state" in order_msg:      # WebSocket
            tracked_order.last_state = CONSTANTS.ORDER_STATUS[int(order_msg["state"])]

        if tracked_order.is_cancelled:
            self.logger().info(f"Successfully cancelled order {client_order_id}.")
            self.trigger_event(MarketEvent.OrderCancelled,
                               OrderCancelledEvent(
                                   self.current_timestamp,
                                   client_order_id))
            tracked_order.cancelled_event.set()
            self.stop_tracking_order(client_order_id)
        elif tracked_order.is_failure:
            self.logger().info(f"The market order {client_order_id} has failed according to order status API. ")
            self.trigger_event(MarketEvent.OrderFailure,
                               MarketOrderFailureEvent(
                                   self.current_timestamp,
                                   client_order_id,
                                   tracked_order.order_type
                               ))
            self.stop_tracking_order(client_order_id)

    async def _process_trade_message_rest(self, trade_msg: Dict[str, Any]):
        """
        Updates in-flight order and trigger order filled event for trade message received from REST API. Triggers order completed
        event if the total executed amount equals to the specified order amount.
        """
        for order in self._in_flight_orders.values():
            await order.get_exchange_order_id()
        track_order = [o for o in self._in_flight_orders.values() if str(trade_msg["order_id"]) == o.exchange_order_id]
        if not track_order:
            return
        tracked_order = track_order[0]
        (delta_trade_amount, delta_trade_price, trade_id) = tracked_order.update_with_trade_update_rest(trade_msg)
        if not delta_trade_amount:
            return
        self.trigger_event(
            MarketEvent.OrderFilled,
            OrderFilledEvent(
                self.current_timestamp,
                tracked_order.client_order_id,
                tracked_order.trading_pair,
                tracked_order.trade_type,
                tracked_order.order_type,
                delta_trade_price,
                delta_trade_amount,
                # TradeFee(0.0, [(trade_msg["fee_coin_name"], Decimal(str(trade_msg["fees"])))]),
                estimate_fee(self.name, tracked_order.order_type in [OrderType.LIMIT, OrderType.LIMIT_MAKER]),
                exchange_trade_id=trade_id
            )
        )
        if math.isclose(tracked_order.executed_amount_base, tracked_order.amount) or tracked_order.executed_amount_base >= tracked_order.amount:
            tracked_order.last_state = "FILLED"
            self.logger().info(f"The {tracked_order.trade_type.name} order "
                               f"{tracked_order.client_order_id} has completed "
                               f"according to trade status rest API.")
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
                                           tracked_order.order_type))
            self.stop_tracking_order(tracked_order.client_order_id)

    async def _process_trade_message_ws(self, trade_msg: Dict[str, Any]):
        """
        Updates in-flight order and trigger order filled event for order message received from WebSocket API. Triggers order completed
        event if the total executed amount equals to the specified order amount.
        """
        for order in self._in_flight_orders.values():
            await order.get_exchange_order_id()
        track_order = [o for o in self._in_flight_orders.values() if str(trade_msg["order_id"]) == o.exchange_order_id]
        if not track_order:
            return
        tracked_order = track_order[0]
        (delta_trade_amount, delta_trade_price, trade_id) = tracked_order.update_with_order_update_ws(trade_msg)
        if not delta_trade_amount:
            return
        self.trigger_event(
            MarketEvent.OrderFilled,
            OrderFilledEvent(
                self.current_timestamp,
                tracked_order.client_order_id,
                tracked_order.trading_pair,
                tracked_order.trade_type,
                tracked_order.order_type,
                delta_trade_price,
                delta_trade_amount,
                estimate_fee(self.name, tracked_order.order_type in [OrderType.LIMIT, OrderType.LIMIT_MAKER]),
                exchange_trade_id=trade_id
            )
        )
        if math.isclose(tracked_order.executed_amount_base, tracked_order.amount) or tracked_order.executed_amount_base >= tracked_order.amount:
            tracked_order.last_state = "FILLED"
            self.logger().info(f"The {tracked_order.trade_type.name} order "
                               f"{tracked_order.client_order_id} has completed "
                               f"according to trade status ws API.")
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
                                           tracked_order.order_type))
            self.stop_tracking_order(tracked_order.client_order_id)

    async def cancel_all(self, timeout_seconds: float):
        """
        Cancels all in-flight orders and waits for cancellation results.
        Used by bot's top level stop and exit commands (cancelling outstanding orders on exit)
        :param timeout_seconds: The timeout at which the operation will be canceled.
        :returns List of CancellationResult which indicates whether each order is successfully cancelled.
        """
        if self._trading_pairs is None:
            raise Exception("cancel_all can only be used when trading_pairs are specified.")
        for order in self._in_flight_orders.values():
            await order.get_exchange_order_id()
        tracked_orders: Dict[str, BitmartInFlightOrder] = self._in_flight_orders.copy().items()
        cancellation_results = []
        try:
            tasks = []

            for _, order in tracked_orders:
                api_params = {
                    "symbol": bitmart_utils.convert_to_exchange_trading_pair(order.trading_pair),
                    "order_id": int(order.exchange_order_id),
                }
                tasks.append(self._api_request("post",
                                               CONSTANTS.CANCEL_ORDER_PATH_URL,
                                               api_params,
                                               "SIGNED"))

            await safe_gather(*tasks)

            open_orders = await self.get_open_orders()
            for cl_order_id, tracked_order in tracked_orders:
                open_order = [o for o in open_orders if o.client_order_id == cl_order_id]
                if not open_order:
                    cancellation_results.append(CancellationResult(cl_order_id, True))
                    self.trigger_event(MarketEvent.OrderCancelled,
                                       OrderCancelledEvent(self.current_timestamp, cl_order_id))
                    self.stop_tracking_order(cl_order_id)
                else:
                    cancellation_results.append(CancellationResult(cl_order_id, False))
        except Exception:
            self.logger().network(
                "Failed to cancel all orders.",
                exc_info=True,
                app_warning_msg="Failed to cancel all orders on BitMart. Check API key and network connection."
            )
        return cancellation_results

    def tick(self, timestamp: float):
        """
        Is called automatically by the clock for each clock's tick (1 second by default).
        It checks if status polling task is due for execution.
        """
        last_tick = int(self._last_timestamp / self.POLL_INTERVAL)
        current_tick = int(timestamp / self.POLL_INTERVAL)
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
                    app_warning_msg="Could not fetch user events from Bitmart. Check API key and network connection."
                )
                await asyncio.sleep(1.0)

    async def _user_stream_event_listener(self):
        """
        Listens to message in _user_stream_tracker.user_stream queue. The messages are put in by
        BitmartAPIUserStreamDataSource.
        """
        async for event_message in self._iter_user_event_queue():
            try:
                if "data" not in event_message:
                    continue
                for msg in event_message["data"]:     # data is a list
                    await self._process_order_message(msg)
                    await self._process_trade_message_ws(msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await asyncio.sleep(5.0)

    async def get_open_orders(self) -> List[OpenOrder]:
        if self._trading_pairs is None:
            raise Exception("get_open_orders can only be used when trading_pairs are specified.")

        page_len = 100
        responses = []
        for trading_pair in self._trading_pairs:
            page = 1
            while True:
                response = await self._api_request("get", CONSTANTS.GET_OPEN_ORDERS_PATH_URL,
                                                   {"symbol": bitmart_utils.convert_to_exchange_trading_pair(trading_pair),
                                                    "offset": page,
                                                    "limit": page_len,
                                                    "status": "9"},
                                                   "KEYED")
                responses.append(response)
                count = len(response["data"]["orders"])
                if count < page_len:
                    break
                else:
                    page += 1

        for order in self._in_flight_orders.values():
            await order.get_exchange_order_id()

        ret_val = []
        for response in responses:
            for order in response["data"]["orders"]:
                exchange_order_id = str(order["order_id"])
                tracked_orders = list(self._in_flight_orders.values())
                tracked_order = [o for o in tracked_orders if exchange_order_id == o.exchange_order_id]
                if not tracked_order:
                    continue
                tracked_order = tracked_order[0]
                if order["type"] != "limit":
                    raise Exception(f"Unsupported order type {order['type']}")
                ret_val.append(
                    OpenOrder(
                        client_order_id=tracked_order.client_order_id,
                        trading_pair=bitmart_utils.convert_from_exchange_trading_pair(order["symbol"]),
                        price=Decimal(str(order["price"])),
                        amount=Decimal(str(order["size"])),
                        executed_amount=Decimal(str(order["filled_size"])),
                        status=CONSTANTS.ORDER_STATUS[int(order["status"])],
                        order_type=OrderType.LIMIT,
                        is_buy=True if order["side"].lower() == "buy" else False,
                        time=int(order["create_time"]),
                        exchange_order_id=str(order["order_id"])
                    )
                )
        return ret_val
