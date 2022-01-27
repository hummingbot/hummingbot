#!/usr/bin/env python

import aiohttp
import asyncio
import logging
import math
import time
import ujson

from decimal import Decimal
from typing import (
    Dict,
    List,
    Optional,
    Any,
    AsyncIterable,
)

from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.connector.exchange.probit import probit_constants as CONSTANTS
from hummingbot.connector.exchange.probit import probit_utils
from hummingbot.connector.exchange.probit.probit_auth import ProbitAuth
from hummingbot.connector.exchange.probit.probit_in_flight_order import ProbitInFlightOrder
from hummingbot.connector.exchange.probit.probit_order_book_tracker import ProbitOrderBookTracker
from hummingbot.connector.exchange.probit.probit_user_stream_tracker import ProbitUserStreamTracker
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.clock import Clock
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.common import OpenOrder
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.event.events import (
    MarketEvent,
    BuyOrderCompletedEvent,
    SellOrderCompletedEvent,
    OrderFilledEvent,
    OrderCancelledEvent,
    BuyOrderCreatedEvent,
    SellOrderCreatedEvent,
    MarketOrderFailureEvent,
    OrderType,
    TradeType
)
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.logger import HummingbotLogger

probit_logger = None
s_decimal_NaN = Decimal("nan")


class ProbitExchange(ExchangeBase):
    """
    ProbitExchange connects with ProBit exchange and provides order book pricing, user account tracking and
    trading functionality.
    """
    API_CALL_TIMEOUT = 10.0
    SHORT_POLL_INTERVAL = 5.0
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0
    LONG_POLL_INTERVAL = 120.0

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global probit_logger
        if probit_logger is None:
            probit_logger = logging.getLogger(__name__)
        return probit_logger

    def __init__(self,
                 probit_api_key: str,
                 probit_secret_key: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True,
                 domain="com"
                 ):
        """
        :param probit_api_key: The API key to connect to private ProBit APIs.
        :param probit_secret_key: The API secret.
        :param trading_pairs: The market trading pairs which to track order book data.
        :param trading_required: Whether actual trading is needed.
        """
        self._domain = domain
        super().__init__()
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._shared_client = aiohttp.ClientSession()
        self._probit_auth = ProbitAuth(probit_api_key, probit_secret_key, domain=domain)
        self._order_book_tracker = ProbitOrderBookTracker(
            trading_pairs=trading_pairs, domain=domain, shared_client=self._shared_client
        )
        self._user_stream_tracker = ProbitUserStreamTracker(
            self._probit_auth, trading_pairs, domain, self._shared_client
        )
        self._poll_notifier = asyncio.Event()
        self._last_timestamp = 0
        self._in_flight_orders = {}  # Dict[client_order_id:str, ProbitInFlightOrder]
        self._order_not_found_records = {}  # Dict[client_order_id:str, count:int]
        self._trading_rules = {}  # Dict[trading_pair:str, TradingRule]
        self._last_poll_timestamp = 0

        self._status_polling_task = None
        self._user_stream_tracker_task = None
        self._user_stream_event_listener_task = None
        self._trading_rules_polling_task = None

    @property
    def name(self) -> str:
        if self._domain == "com":
            return CONSTANTS.EXCHANGE_NAME
        else:
            return f"{CONSTANTS.EXCHANGE_NAME}_{self._domain}"

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        return self._order_book_tracker.order_books

    @property
    def trading_rules(self) -> Dict[str, TradingRule]:
        return self._trading_rules

    @property
    def in_flight_orders(self) -> Dict[str, ProbitInFlightOrder]:
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
            key: ProbitInFlightOrder.from_json(value)
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
            # since there is no ping endpoint, the lowest rate call is to get BTC-USDT ticker
            resp = await self._api_request(
                method="GET",
                path_url=CONSTANTS.TIME_URL
            )
            if "data" not in resp:
                raise
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    async def _http_client(self) -> aiohttp.ClientSession:
        """
        :returns Shared client session instance
        """
        if self._shared_client is None:
            self._shared_client = aiohttp.ClientSession()
        return self._shared_client

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
                                      app_warning_msg="Could not fetch new trading rules from ProBit. "
                                                      "Check network connection.")
                await asyncio.sleep(0.5)

    async def _update_trading_rules(self):
        market_info = await self._api_request(
            method="GET",
            path_url=CONSTANTS.MARKETS_URL
        )
        self._trading_rules.clear()
        self._trading_rules = self._format_trading_rules(market_info)

    def _format_trading_rules(self, market_info: Dict[str, Any]) -> Dict[str, TradingRule]:
        """
        Converts json API response into a dictionary of trading rules.
        :param market_info: The json API response
        :return A dictionary of trading rules.
        Response Example:
        {
            data: [
                {
                    "id":"BCH-BTC",
                    "base_currency_id":"BCH",
                    "quote_currency_id":"BTC",
                    "min_price":"0.00000001",
                    "max_price":"9999999999999999",
                    "price_increment":"0.00000001",
                    "min_quantity":"0.00000001",
                    "max_quantity":"9999999999999999",
                    "quantity_precision":8,
                    "min_cost":"0",
                    "max_cost":"9999999999999999",
                    "cost_precision": 8
                },
                ...
            ]
        }
        """
        result = {}
        for market in market_info["data"]:
            try:
                trading_pair = market["id"]

                quantity_decimals = Decimal(str(market["quantity_precision"]))
                quantity_step = Decimal("1") / Decimal(str(math.pow(10, quantity_decimals)))

                result[trading_pair] = TradingRule(trading_pair=trading_pair,
                                                   min_order_size=Decimal(str(market["min_quantity"])),
                                                   max_order_size=Decimal(str(market["max_quantity"])),
                                                   min_order_value=Decimal(str(market["min_cost"])),
                                                   min_price_increment=Decimal(str(market["price_increment"])),
                                                   min_base_amount_increment=quantity_step)
            except Exception:
                self.logger().error(f"Error parsing the trading pair rule {market}. Skipping.", exc_info=True)
        return result

    async def _api_request(self,
                           method: str,
                           path_url: str,
                           params: Optional[Dict[str, Any]] = None,
                           data: Optional[Dict[str, Any]] = None,
                           is_auth_required: bool = False) -> Dict[str, Any]:
        """
        Sends an aiohttp request and waits for a response.
        :param method: The HTTP method, e.g. get or post
        :param path_url: The path url or the API end point
        :param is_auth_required: Whether an authentication is required, when True the function will add encrypted
        signature to the request.
        :returns A response in json format.
        """
        path_url = path_url.format(self._domain)
        client = await self._http_client()

        try:
            if is_auth_required:
                headers = await self._probit_auth.get_auth_headers(client)
            else:
                headers = self._probit_auth.get_headers()

            if method == "GET":
                response = await client.get(path_url, headers=headers, params=params)
            elif method == "POST":
                response = await client.post(path_url, headers=headers, data=ujson.dumps(data))
            else:
                raise NotImplementedError(f"{method} HTTP Method not implemented. ")

            parsed_response = await response.json()
        except ValueError as e:
            self.logger().error(f"{str(e)}")
            raise ValueError(f"Error authenticating request {method} {path_url}. Error: {str(e)}")
        except Exception as e:
            raise IOError(f"Error parsing data from {path_url}. Error: {str(e)}")
        if response.status != 200:
            raise IOError(f"Error fetching data from {path_url}. HTTP status is {response.status}. "
                          f"Message: {parsed_response} "
                          f"Params: {params} "
                          f"Data: {data}")

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
        order_id: str = probit_utils.get_new_client_order_id(True, trading_pair)
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
        order_id: str = probit_utils.get_new_client_order_id(False, trading_pair)
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

        amount = self.quantize_order_amount(trading_pair, amount)
        price = self.quantize_order_price(trading_pair, price)

        try:
            if amount < trading_rule.min_order_size:
                raise ValueError(f"{trade_type.name} order amount {amount} is lower than the minimum order size "
                                 f"{trading_rule.min_order_size}.")

            order_value: Decimal = amount * price
            if order_value < trading_rule.min_order_value:
                raise ValueError(f"{trade_type.name} order value {order_value} is lower than the minimum order value "
                                 f"{trading_rule.min_order_value}")

            body_params = {
                "market_id": trading_pair,
                "type": "limit",  # ProBit Order Types ["limit", "market"}
                "side": trade_type.name.lower(),  # ProBit Order Sides ["buy", "sell"]
                "time_in_force": "gtc",  # gtc = Good-Til-Cancelled
                "limit_price": str(price),
                "quantity": str(amount),
                "client_order_id": order_id
            }

            self.start_tracking_order(order_id,
                                      None,
                                      trading_pair,
                                      trade_type,
                                      price,
                                      amount,
                                      order_type
                                      )

            order_result = await self._api_request(
                method="POST",
                path_url=CONSTANTS.NEW_ORDER_URL,
                data=body_params,
                is_auth_required=True
            )
            exchange_order_id = str(order_result["data"]["id"])
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
                f"Error submitting {trade_type.name} {order_type.name} order to ProBit for "
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
        self._in_flight_orders[order_id] = ProbitInFlightOrder(
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

            body_params = {
                "market_id": trading_pair,
                "order_id": ex_order_id
            }

            await self._api_request(
                method="POST",
                path_url=CONSTANTS.CANCEL_ORDER_URL,
                data=body_params,
                is_auth_required=True
            )
            return order_id
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(
                f"Failed to cancel order {order_id}: {str(e)}",
                exc_info=True,
                app_warning_msg=f"Failed to cancel the order {order_id} on Probit. "
                                f"Check API key and network connection."
            )

    async def _status_polling_loop(self):
        """
        Periodically update user balances and order status via REST API. This serves as a fallback measure for web
        socket API updates.
        """
        while True:
            try:
                self._poll_notifier = asyncio.Event()
                await self._poll_notifier.wait()
                await safe_gather(
                    self._update_balances(),
                    self._update_order_status(),
                )
                self._last_poll_timestamp = self.current_timestamp
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(str(e), exc_info=True)
                self.logger().network("Unexpected error while fetching account updates.",
                                      exc_info=True,
                                      app_warning_msg="Could not fetch account updates from ProBit. "
                                                      "Check API key and network connection.")
                await asyncio.sleep(0.5)

    async def _update_balances(self):
        """
        Calls REST API to update total and available balances.
        """
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()
        balance_info = await self._api_request(
            method="GET",
            path_url=CONSTANTS.BALANCE_URL,
            is_auth_required=True
        )
        for currency in balance_info["data"]:
            asset_name = currency["currency_id"]
            self._account_available_balances[asset_name] = Decimal(str(currency["available"]))
            self._account_balances[asset_name] = Decimal(str(currency["total"]))
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

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
                ex_order_id = await tracked_order.get_exchange_order_id()

                query_params = {
                    "market_id": tracked_order.trading_pair,
                    "order_id": ex_order_id
                }

                tasks.append(self._api_request(method="GET",
                                               path_url=CONSTANTS.ORDER_URL,
                                               params=query_params,
                                               is_auth_required=True)
                             )
            self.logger().debug(f"Polling for order status updates of {len(tasks)} orders.")
            order_results: List[Dict[str, Any]] = await safe_gather(*tasks, return_exceptions=True)

            # Retrieve start_time and end_time of the earliest and last order.
            # Retrieves all trades between this order creations.
            min_order_ts: str = ""

            min_ts: float = float("inf")
            for order_update in order_results:
                if isinstance(order_update, Exception):
                    raise order_update

                # Order Creation Time
                for update in order_update["data"]:
                    order_ts: float = probit_utils.convert_iso_to_epoch(update["time"])
                    if order_ts < min_ts:
                        min_order_ts = update["time"]
                        min_ts = order_ts

            trade_history_tasks = []
            for trading_pair in self._trading_pairs:
                query_params = {
                    "start_time": min_order_ts,
                    "end_time": probit_utils.get_iso_time_now(),
                    "limit": 1000,
                    "market_id": trading_pair
                }
                trade_history_tasks.append(self._api_request(
                    method="GET",
                    path_url=CONSTANTS.TRADE_HISTORY_URL,
                    params=query_params,
                    is_auth_required=True
                ))
            trade_history_results: List[Dict[str, Any]] = await safe_gather(*trade_history_tasks, return_exceptions=True)

            for t_pair_history in trade_history_results:
                if isinstance(t_pair_history, Exception):
                    raise t_pair_history
                if "data" not in t_pair_history:
                    self.logger().info(f"Unexpected response from GET /trade_history. 'data' field not in resp: {t_pair_history}")
                    continue

                trade_details: List[Dict[str, Any]] = t_pair_history["data"]
                for trade in trade_details:
                    self._process_trade_message(trade)

            for order_update in order_results:
                if isinstance(order_update, Exception):
                    raise order_update
                if "data" not in order_update:
                    self.logger().info(f"Unexpected response from GET /order. 'data' field not in resp: {order_update}")
                    continue

                for order in order_update["data"]:
                    self._process_order_message(order)

    def _process_order_message(self, order_msg: Dict[str, Any]):
        """
        Updates in-flight order and triggers trade, cancellation or failure event if needed.
        :param order_msg: The order response from either REST or web socket API (they are of the same format)
        """
        client_order_id = order_msg["client_order_id"]
        if client_order_id not in self._in_flight_orders:
            return
        tracked_order = self._in_flight_orders[client_order_id]

        # Update order execution status
        tracked_order.last_state = order_msg["status"]

        # NOTE: In ProBit partially-filled orders will retain "filled" status when canceled.
        if tracked_order.is_cancelled or Decimal(str(order_msg["cancelled_quantity"])) > Decimal("0"):
            self.logger().info(f"Successfully cancelled order {client_order_id}.")
            self.trigger_event(MarketEvent.OrderCancelled,
                               OrderCancelledEvent(
                                   self.current_timestamp,
                                   client_order_id))
            tracked_order.cancelled_event.set()
            self.stop_tracking_order(client_order_id)

        # NOTE: ProBit does not have a 'fail' order status
        # elif tracked_order.is_failure:
        #     self.logger().info(f"The market order {client_order_id} has failed according to order status API. "
        #                        f"Order Message: {order_msg}")
        #     self.trigger_event(MarketEvent.OrderFailure,
        #                        MarketOrderFailureEvent(
        #                            self.current_timestamp,
        #                            client_order_id,
        #                            tracked_order.order_type
        #                        ))
        #     self.stop_tracking_order(client_order_id)

    def _process_trade_message(self, order_msg: Dict[str, Any]):
        """
        Updates in-flight order and trigger order filled event for trade message received. Triggers order completed
        event if the total executed amount equals to the specified order amount.
        """
        # Only process trade when trade fees have been accounted for; when trade status is "settled".
        if order_msg["status"] != "settled":
            return

        ex_order_id = order_msg["order_id"]

        client_order_id = None
        for track_order in self.in_flight_orders.values():
            if track_order.exchange_order_id == ex_order_id:
                client_order_id = track_order.client_order_id
                break

        if client_order_id is None:
            return

        tracked_order = self.in_flight_orders[client_order_id]
        updated = tracked_order.update_with_trade_update(order_msg)
        if not updated:
            return

        self.trigger_event(
            MarketEvent.OrderFilled,
            OrderFilledEvent(
                self.current_timestamp,
                tracked_order.client_order_id,
                tracked_order.trading_pair,
                tracked_order.trade_type,
                tracked_order.order_type,
                Decimal(str(order_msg["price"])),
                Decimal(str(order_msg["quantity"])),
                AddedToCostTradeFee(
                    flat_fees=[TokenAmount(order_msg["fee_currency_id"], Decimal(str(order_msg["fee_amount"])))]
                ),
                exchange_trade_id=order_msg["id"]
            )
        )
        if math.isclose(tracked_order.executed_amount_base, tracked_order.amount) or \
                tracked_order.executed_amount_base >= tracked_order.amount:
            tracked_order.last_state = "filled"
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

    async def get_open_orders(self) -> List[OpenOrder]:
        ret_val = []
        for trading_pair in self._trading_pairs:
            query_params = {
                "market_id": trading_pair
            }
            result = await self._api_request(
                method="GET",
                path_url=CONSTANTS.OPEN_ORDER_URL,
                params=query_params,
                is_auth_required=True
            )
            if "data" not in result:
                self.logger().info(f"Unexpected response from GET {CONSTANTS.OPEN_ORDER_URL}. "
                                   f"Params: {query_params} "
                                   f"Response: {result} ")
            for order in result["data"]:
                if order["type"] != "limit":
                    raise Exception(f"Unsupported order type {order['type']}")
                ret_val.append(
                    OpenOrder(
                        client_order_id=order["client_order_id"],
                        trading_pair=order["market_id"],
                        price=Decimal(str(order["limit_price"])),
                        amount=Decimal(str(order["quantity"])),
                        executed_amount=Decimal(str(order["quantity"])) - Decimal(str(order["filled_quantity"])),
                        status=order["status"],
                        order_type=OrderType.LIMIT,
                        is_buy=True if order["side"].lower() == "buy" else False,
                        time=int(probit_utils.convert_iso_to_epoch(order["time"])),
                        exchange_order_id=order["id"]
                    )
                )
        return ret_val

    async def cancel_all(self, timeout_seconds: float):
        """
        Cancels all in-flight orders and waits for cancellation results.
        Used by bot's top level stop and exit commands (cancelling outstanding orders on exit)
        :param timeout_seconds: The timeout at which the operation will be canceled.
        :returns List of CancellationResult which indicates whether each order is successfully cancelled.
        """
        if self._trading_pairs is None:
            raise Exception("cancel_all can only be used when trading_pairs are specified.")
        cancellation_results = []
        try:

            # ProBit does not have cancel_all_order endpoint
            tasks = []
            for tracked_order in self.in_flight_orders.values():
                body_params = {
                    "market_id": tracked_order.trading_pair,
                    "order_id": tracked_order.exchange_order_id
                }
                tasks.append(self._api_request(
                    method="POST",
                    path_url=CONSTANTS.CANCEL_ORDER_URL,
                    data=body_params,
                    is_auth_required=True
                ))

            await safe_gather(*tasks)

            open_orders = await self.get_open_orders()
            for cl_order_id, tracked_order in self._in_flight_orders.items():
                open_order = [o for o in open_orders if o.client_order_id == cl_order_id]
                if not open_order:
                    cancellation_results.append(CancellationResult(cl_order_id, True))
                    self.trigger_event(MarketEvent.OrderCancelled,
                                       OrderCancelledEvent(self.current_timestamp, cl_order_id))
                else:
                    cancellation_results.append(CancellationResult(cl_order_id, False))
        except Exception:
            self.logger().network(
                "Failed to cancel all orders.",
                exc_info=True,
                app_warning_msg="Failed to cancel all orders on ProBit. Check API key and network connection."
            )
        return cancellation_results

    def tick(self, timestamp: float):
        """
        Is called automatically by the clock for each clock's tick (1 second by default).
        It checks if status polling task is due for execution.
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
                    app_warning_msg="Could not fetch user events from Probit. Check API key and network connection."
                )
                await asyncio.sleep(1.0)

    async def _user_stream_event_listener(self):
        """
        Listens to message in _user_stream_tracker.user_stream queue. The messages are put in by
        ProbitAPIUserStreamDataSource.
        """
        async for event_message in self._iter_user_event_queue():
            try:
                if "channel" not in event_message and event_message["channel"] not in CONSTANTS.WS_PRIVATE_CHANNELS:
                    continue
                channel = event_message["channel"]

                if channel == "balance":
                    for asset, balance_details in event_message["data"].items():
                        self._account_balances[asset] = Decimal(str(balance_details["total"]))
                        self._account_available_balances[asset] = Decimal(str(balance_details["available"]))
                elif channel in ["open_order"]:
                    for order_update in event_message["data"]:
                        self._process_order_message(order_update)
                elif channel == "trade_history":
                    for trade_update in event_message["data"]:
                        self._process_trade_message(trade_update)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await asyncio.sleep(5.0)
