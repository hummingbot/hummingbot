import logging
from typing import (
    Dict,
    List,
    Optional,
    Any,
    AsyncIterable,
)
from decimal import Decimal
import asyncio
import aiohttp
import math
import time
import ujson

from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.logger import HummingbotLogger
from hummingbot.core.clock import Clock
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.cancellation_result import CancellationResult
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
    TradeType,
    TradeFee
)
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.connector.exchange.k2.k2_order_book_tracker import K2OrderBookTracker
from hummingbot.connector.exchange.k2.k2_user_stream_tracker import K2UserStreamTracker
from hummingbot.connector.exchange.k2.k2_auth import K2Auth
from hummingbot.connector.exchange.k2.k2_in_flight_order import K2InFlightOrder
from hummingbot.connector.exchange.k2 import k2_utils
from hummingbot.connector.exchange.k2 import k2_constants as constants
from hummingbot.core.data_type.common import OpenOrder
k2_logger = None
s_decimal_NaN = Decimal("nan")


class K2Exchange(ExchangeBase):
    """
    This class connects with K2 exchange and provides order book pricing, user account tracking and
    trading functionality.
    """
    API_CALL_TIMEOUT = 10.0
    SHORT_POLL_INTERVAL = 5.0
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0
    LONG_POLL_INTERVAL = 120.0

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global k2_logger
        if k2_logger is None:
            k2_logger = logging.getLogger(__name__)
        return k2_logger

    def __init__(self,
                 k2_api_key: str,
                 k2_secret_key: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True
                 ):
        """
        :param k2_api_key: The API key to connect to private K2 APIs.
        :param k2_secret_key: The API secret.
        :param trading_pairs: The market trading pairs which to track order book data.
        :param trading_required: Whether actual trading is needed.
        """
        super().__init__()
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._k2_auth = K2Auth(k2_api_key, k2_secret_key)
        self._order_book_tracker = K2OrderBookTracker(trading_pairs=trading_pairs)
        self._user_stream_tracker = K2UserStreamTracker(self._k2_auth, trading_pairs)
        self._ev_loop = asyncio.get_event_loop()
        self._shared_client = None
        self._poll_notifier = asyncio.Event()
        self._last_timestamp = 0
        self._in_flight_orders = {}  # Dict[client_order_id:str, K2InFlightOrder]
        self._order_not_found_records = {}  # Dict[client_order_id:str, count:int]
        self._trading_rules = {}  # Dict[trading_pair:str, TradingRule]
        self._status_polling_task = None
        self._user_stream_event_listener_task = None
        self._trading_rules_polling_task = None
        self._last_poll_timestamp = 0

    @property
    def name(self) -> str:
        return constants.EXCHANGE_NAME

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        return self._order_book_tracker.order_books

    @property
    def trading_rules(self) -> Dict[str, TradingRule]:
        return self._trading_rules

    @property
    def in_flight_orders(self) -> Dict[str, K2InFlightOrder]:
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
        Restore in-flight orders from saved tracking states, this is so the connector can pick up on where it left off
        when it disconnects.
        :param saved_states: The saved tracking_states.
        """
        self._in_flight_orders.update({
            key: K2InFlightOrder.from_json(value)
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
            # since there is no ping endpoint, the lowest rate call is to get BTC-USDT ticker
            await self._api_request(method="GET",
                                    path_url=constants.GET_TRADING_PAIRS_STATS,
                                    params={"symbol": "BTC-USD"})
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
                                      app_warning_msg="Could not fetch new trading rules from K2. "
                                                      "Check network connection.")
                await asyncio.sleep(0.5)

    async def _update_trading_rules(self):
        response = await self._api_request("GET", path_url=constants.GET_TRADING_PAIRS_STATS)
        self._trading_rules.clear()
        self._trading_rules = self._format_trading_rules(response)

    def _format_trading_rules(self, data: Dict[str, Any]) -> Dict[str, TradingRule]:
        """
        Converts json API response into a dictionary of trading rules.
        :param instruments_info: The json API response
        :return A dictionary of trading rules.
        Response Example:
        {
            "success": true,
            "data": [
                {
                    "symbol": "BEAM/BTC",
                    "buymakerfee": 0.00000000,
                    "sellmakerfee": 0.00000000,
                    "buytakerfee": 0.00200000,
                    "selltakerfee": 0.00020000,
                    "mintradevalue": 0.00010000,
                    "decimals": {
                        "price": 8,
                        "amount": 8
                    }
                },...
        """
        result = {}
        for trading_pair_stat in data["data"]:
            try:
                trading_pair = k2_utils.convert_from_exchange_trading_pair(trading_pair_stat["symbol"])
                price_decimals = Decimal(str(trading_pair_stat["decimal"]["price"]))
                quantity_decimals = Decimal(str(trading_pair_stat["decimal"]["amount"]))
                min_trade_value = Decimal(str(trading_pair_stat["decimal"]["mintradevalue"]))
                # E.g. a price decimal of 2 means 0.01 incremental.
                price_step = Decimal("1") / Decimal(str(math.pow(10, price_decimals)))
                quantity_step = Decimal("1") / Decimal(str(math.pow(10, quantity_decimals)))
                result[trading_pair] = TradingRule(trading_pair,
                                                   min_price_increment=price_step,
                                                   min_base_amount_increment=quantity_step,
                                                   min_order_value=min_trade_value
                                                   )
            except Exception:
                self.logger().error(f"Error parsing the trading pair rule {data}. Skipping.", exc_info=True)
        return result

    async def _api_request(self,
                           method: str,
                           path_url: str,
                           params: Dict[str, Any] = {},
                           is_auth_required: bool = False) -> Dict[str, Any]:
        """
        Sends an aiohttp request and waits for a response.
        :param method: The HTTP method, e.g. get or post
        :param path_url: The path url or the API end point
        :param is_auth_required: Whether an authentication is required, when True the function will add encrypted
        signature to the request.
        :returns A response in json format.
        """

        url = constants.REST_URL + path_url
        if is_auth_required is True:
            headers = self._k2_auth.generate_auth_dict(path_url=path_url)
        else:
            headers = self._k2_auth.get_headers()

        if method == "GET":
            response = await self._http_client().get(url, headers=headers, params=params)
        elif method == "POST":
            response = await self._http_client().post(url, headers=headers, params=params)
        else:
            raise NotImplementedError

        try:
            parsed_response = await ujson.loads(response)
        except Exception as e:
            raise IOError(f"Error parsing data from {method} {url}. Error: {str(e)}")

        if response.status != 200:
            raise IOError(f"Error fetching data from {method} {url}. HTTP status is {response.status}. "
                          f"Message: {parsed_response}")

        if parsed_response["success"] is not True:
            raise IOError(f"{method} {url} API call failed, response: {parsed_response}")

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
        # TODO: Determine if there is a way to assign client_order_id as indicated by `tempid` parameter
        order_id: str = k2_utils.get_new_client_order_id(True, trading_pair)
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
        order_id: str = k2_utils.get_new_client_order_id(False, trading_pair)
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
        if amount < trading_rule.min_order_size:
            raise ValueError(f"Order amount {amount} is lower than the minimum order size "
                             f"{trading_rule.min_order_size}.")

        api_params = {
            # TODO: Determine if there is a way to assign client_order_id as indicated by `tempid` parameter
            # "tempid": order_id
            "symbol": k2_utils.convert_to_exchange_trading_pair(trading_pair),
            "price": f"{price:f}",
            "quantity": f"{amount:f}",
            "type": trade_type.name,  # `type` parameter here refers to Side i.e. Buy or Sell
        }

        self.start_tracking_order(order_id,
                                  None,
                                  trading_pair,
                                  trade_type,
                                  price,
                                  amount,
                                  order_type
                                  )
        try:
            order_result = await self._api_request("POST", constants.PLACE_ORDER, api_params, True)
            exchange_order_id = str(order_result["orderids"][0]["id"])
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
                f"Error submitting {trade_type.name} {order_type.name} order to K2 for "
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
        self._in_flight_orders[order_id] = K2InFlightOrder(
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

            api_params = {
                "orderid": ex_order_id
            }
            await self._api_request(
                "POST",
                constants.CANCEL_ORDER,
                api_params,
                True
            )
            return order_id
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(
                f"Failed to cancel order {order_id}: {str(e)}",
                exc_info=True,
                app_warning_msg=f"Failed to cancel the order {order_id} on K2. "
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
                                      app_warning_msg="Could not fetch account updates from K2. "
                                                      "Check API key and network connection.")
                await asyncio.sleep(0.5)

    async def _update_balances(self):
        """
        Calls REST API to update total and available balances.
        """
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()
        balance = await self._api_request("POST", constants.GET_DETAILED_BALANCES, {}, True)
        for asset_entry in balance["data"]:
            asset_name = asset_entry["coin"]
            available_balance: Decimal = Decimal(str(asset_entry["availablebalance"]))
            total_balance: Decimal = Decimal(str(sum(list(asset_entry.values())[1:])))
            self._account_available_balances[asset_name] = available_balance
            self._account_balances[asset_name] = total_balance
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
            tracked_orders: List[K2InFlightOrder] = list(self._in_flight_orders.values())

            order_ids: str = ",".join([await order.get_exchange_order_id() for order in tracked_orders])

            params = {
                "orderids": order_ids
            }
            self.logger().debug(f"Polling for order status updates of {len(order_ids)} orders.")
            resp = await self._api_request("POST",
                                           constants.GET_ORDERS,
                                           params,
                                           True)

            if isinstance(resp, Exception):
                raise resp

            order_data: List[Dict[str, Any]] = resp["data"]
            for order in order_data:
                if order["orderid"] not in self._in_flight_orders:
                    continue
                if constants.ORDER_STATUS[order["status"]] in ["Partially Filled", "Filled"]:
                    await self._process_trade_message(order)
                self._process_order_message(order)

    def _process_order_message(self, order_msg: Dict[str, Any]):
        """
        Updates in-flight order and triggers cancellation or failure event if needed.
        :param order_msg: The order response from either REST or web socket API (they are of the same format)
        """
        client_order_id = order_msg["orderid"]
        if client_order_id not in self._in_flight_orders:
            return
        tracked_order = self._in_flight_orders[client_order_id]
        # Update order execution status
        tracked_order.last_state = constants.ORDER_STATUS[order_msg["status"]]
        if tracked_order.is_cancelled:
            self.logger().info(f"Successfully cancelled order {client_order_id}.")
            self.trigger_event(MarketEvent.OrderCancelled,
                               OrderCancelledEvent(
                                   self.current_timestamp,
                                   client_order_id))
            tracked_order.cancelled_event.set()
            self.stop_tracking_order(client_order_id)
        elif tracked_order.is_failure:
            self.logger().info(f"The order {client_order_id} has failed according to order status API. ")
            self.trigger_event(MarketEvent.OrderFailure,
                               MarketOrderFailureEvent(
                                   self.current_timestamp,
                                   client_order_id,
                                   tracked_order.order_type
                               ))
            self.stop_tracking_order(client_order_id)

    async def _process_trade_message(self, trade_msg: Dict[str, Any]):
        """
        Updates in-flight order and trigger order filled event for trade message received. Triggers order completed
        event if the total executed amount equals to the specified order amount.
        """
        client_order_id = trade_msg["orderid"]
        tracked_order: K2InFlightOrder = self._in_flight_orders.get(client_order_id, None)

        if tracked_order is None:
            return

        last_executed_amount: Decimal = tracked_order.executed_amount_base

        updated = tracked_order.update_with_trade_update(trade_msg)
        if not updated:
            return

        current_executed_amount: Decimal = tracked_order.executed_amount_base - last_executed_amount

        # TODO: Check in with K2 dev for a possible "Traded Qty & Price" and "Cumulative Qty & Price" entry
        self.trigger_event(
            MarketEvent.OrderFilled,
            OrderFilledEvent(
                self.current_timestamp,
                tracked_order.client_order_id,
                tracked_order.trading_pair,
                tracked_order.trade_type,
                tracked_order.order_type,
                Decimal(str(trade_msg["price"])),
                current_executed_amount,
                TradeFee(0.0, [(trade_msg["fee_currency"], Decimal(str(trade_msg["fee"])))]),
                exchange_trade_id=trade_msg["orderid"]
            )
        )
        if math.isclose(tracked_order.executed_amount_base, tracked_order.amount) or \
                tracked_order.executed_amount_base >= tracked_order.amount:
            tracked_order.last_state = "Filled"
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
        cancellation_results = []
        try:
            for trading_pair in self._trading_pairs:
                await self._api_request(
                    "POST",
                    constants.CANCEL_ALL_ORDERS,
                    None,
                    True
                )
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
                app_warning_msg="Failed to cancel all orders on K2. Check API key and network connection."
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
                price: Decimal = s_decimal_NaN) -> TradeFee:
        """
        To get trading fee, this function is simplified by using fee override configuration. Most parameters to this
        function are ignore except order_type. Use OrderType.LIMIT_MAKER to specify you want trading fee for
        maker order.
        """
        is_maker = order_type is OrderType.LIMIT_MAKER
        return TradeFee(percent=self.estimate_fee_pct(is_maker))

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
                    app_warning_msg="Could not fetch user events from K2. Check API key and network connection."
                )
                await asyncio.sleep(1.0)

    async def _user_stream_event_listener(self):
        """
        Listens to message in _user_stream_tracker.user_stream queue. The messages are put in by
        K2APIUserStreamDataSource.
        """
        async for event_message in self._iter_user_event_queue():
            try:
                if "result" not in event_message or "channel" not in event_message["result"]:
                    continue
                channel = event_message["result"]["channel"]
                if "user.trade" in channel:
                    for trade_msg in event_message["result"]["data"]:
                        await self._process_trade_message(trade_msg)
                elif "user.order" in channel:
                    for order_msg in event_message["result"]["data"]:
                        self._process_order_message(order_msg)
                elif channel == "user.balance":
                    balances = event_message["result"]["data"]
                    for balance_entry in balances:
                        asset_name = balance_entry["currency"]
                        self._account_balances[asset_name] = Decimal(str(balance_entry["balance"]))
                        self._account_available_balances[asset_name] = Decimal(str(balance_entry["available"]))
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await asyncio.sleep(5.0)

    async def get_open_orders(self) -> List[OpenOrder]:
        result = await self._api_request(
            "GET",
            constants.GET_OPEN_ORDERS,
            {},
            True
        )
        ret_val = []
        for order in result["data"]:
            # TradeType is not provided by v1/Private/GetOpenOrders endpoint
            # if order["type"] != "LIMIT":
            #     raise Exception(f"Unsupported order type {order['type']}")
            ret_val.append(
                OpenOrder(
                    client_order_id=order["orderid"],  # TODO: Check in with K2 for client specified order id
                    trading_pair=k2_utils.convert_from_exchange_trading_pair(order["symbol"]),
                    price=Decimal(str(order["price"])),
                    amount=Decimal(str(order["quantity"])),
                    executed_amount=Decimal(str(order["quantity"])) - Decimal(str(order["leaveqty"])),
                    status=constants.ORDER_STATUS[order["status"]],
                    order_type=OrderType.LIMIT,
                    is_buy=True if order["side"].lower() == "Buy" else False,
                    time=int(time.time() * 1e3),  # TODO: Check in with K2 for order creation ts, order update ts
                    exchange_order_id=order["orderid"]  # TODO: Check in with K2 for unique order id
                )
            )
        return ret_val
