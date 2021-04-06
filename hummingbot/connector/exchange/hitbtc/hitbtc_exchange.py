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
from async_timeout import timeout

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
from hummingbot.connector.exchange.hitbtc.hitbtc_order_book_tracker import HitbtcOrderBookTracker
from hummingbot.connector.exchange.hitbtc.hitbtc_user_stream_tracker import HitbtcUserStreamTracker
from hummingbot.connector.exchange.hitbtc.hitbtc_auth import HitbtcAuth
from hummingbot.connector.exchange.hitbtc.hitbtc_in_flight_order import HitbtcInFlightOrder
from hummingbot.connector.exchange.hitbtc.hitbtc_utils import (
    convert_from_exchange_trading_pair,
    convert_to_exchange_trading_pair,
    translate_asset,
    get_new_client_order_id,
    aiohttp_response_with_errors,
    retry_sleep_time,
    str_date_to_ts,
    HitbtcAPIError,
)
from hummingbot.connector.exchange.hitbtc.hitbtc_constants import Constants
from hummingbot.core.data_type.common import OpenOrder
ctce_logger = None
s_decimal_NaN = Decimal("nan")


class HitbtcExchange(ExchangeBase):
    """
    HitbtcExchange connects with HitBTC exchange and provides order book pricing, user account tracking and
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
                 hitbtc_api_key: str,
                 hitbtc_secret_key: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True
                 ):
        """
        :param hitbtc_api_key: The API key to connect to private HitBTC APIs.
        :param hitbtc_secret_key: The API secret.
        :param trading_pairs: The market trading pairs which to track order book data.
        :param trading_required: Whether actual trading is needed.
        """
        super().__init__()
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._hitbtc_auth = HitbtcAuth(hitbtc_api_key, hitbtc_secret_key)
        self._order_book_tracker = HitbtcOrderBookTracker(trading_pairs=trading_pairs)
        self._user_stream_tracker = HitbtcUserStreamTracker(self._hitbtc_auth, trading_pairs)
        self._ev_loop = asyncio.get_event_loop()
        self._shared_client = None
        self._poll_notifier = asyncio.Event()
        self._last_timestamp = 0
        self._in_flight_orders = {}  # Dict[client_order_id:str, HitbtcInFlightOrder]
        self._order_not_found_records = {}  # Dict[client_order_id:str, count:int]
        self._trading_rules = {}  # Dict[trading_pair:str, TradingRule]
        self._status_polling_task = None
        self._user_stream_event_listener_task = None
        self._trading_rules_polling_task = None
        self._last_poll_timestamp = 0

    @property
    def name(self) -> str:
        return "hitbtc"

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        return self._order_book_tracker.order_books

    @property
    def trading_rules(self) -> Dict[str, TradingRule]:
        return self._trading_rules

    @property
    def in_flight_orders(self) -> Dict[str, HitbtcInFlightOrder]:
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
            key: HitbtcInFlightOrder.from_json(value)
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
            # since there is no ping endpoint, the lowest rate call is to get BTC-USD symbol
            await self._api_request("GET",
                                    Constants.ENDPOINT['SYMBOL'],
                                    params={'symbols': 'BTCUSD'})
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
                await asyncio.sleep(Constants.INTERVAL_TRADING_RULES)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().network(f"Unexpected error while fetching trading rules. Error: {str(e)}",
                                      exc_info=True,
                                      app_warning_msg=("Could not fetch new trading rules from "
                                                       f"{Constants.EXCHANGE_NAME}. Check network connection."))
                await asyncio.sleep(0.5)

    async def _update_trading_rules(self):
        symbols_info = await self._api_request("GET", endpoint=Constants.ENDPOINT['SYMBOL'])
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
                id: "BTCUSD",
                baseCurrency: "BTC",
                quoteCurrency: "USD",
                quantityIncrement: "0.00001",
                tickSize: "0.01",
                takeLiquidityRate: "0.0025",
                provideLiquidityRate: "0.001",
                feeCurrency: "USD",
                marginTrading: true,
                maxInitialLeverage: "12.00"
            }
        ]
        """
        result = {}
        for rule in symbols_info:
            try:
                trading_pair = convert_from_exchange_trading_pair(rule["id"])
                price_step = Decimal(str(rule["tickSize"]))
                size_step = Decimal(str(rule["quantityIncrement"]))
                result[trading_pair] = TradingRule(trading_pair,
                                                   min_order_size=size_step,
                                                   min_base_amount_increment=size_step,
                                                   min_price_increment=price_step)
            except Exception:
                self.logger().error(f"Error parsing the trading pair rule {rule}. Skipping.", exc_info=True)
        return result

    async def _api_request(self,
                           method: str,
                           endpoint: str,
                           params: Optional[Dict[str, Any]] = None,
                           is_auth_required: bool = False,
                           try_count: int = 0) -> Dict[str, Any]:
        """
        Sends an aiohttp request and waits for a response.
        :param method: The HTTP method, e.g. get or post
        :param endpoint: The path url or the API end point
        :param params: Additional get/post parameters
        :param is_auth_required: Whether an authentication is required, when True the function will add encrypted
        signature to the request.
        :returns A response in json format.
        """
        url = f"{Constants.REST_URL}/{endpoint}"
        shared_client = await self._http_client()
        # Turn `params` into either GET params or POST body data
        qs_params: dict = params if method.upper() == "GET" else None
        req_form = aiohttp.FormData(params) if method.upper() == "POST" and params is not None else None
        # Generate auth headers if needed.
        headers: dict = {"Content-Type": "application/x-www-form-urlencoded"}
        if is_auth_required:
            headers: dict = self._hitbtc_auth.get_headers(method, f"{Constants.REST_URL_AUTH}/{endpoint}",
                                                          params)
        # Build request coro
        response_coro = shared_client.request(method=method.upper(), url=url, headers=headers,
                                              params=qs_params, data=req_form,
                                              timeout=Constants.API_CALL_TIMEOUT)
        http_status, parsed_response, request_errors = await aiohttp_response_with_errors(response_coro)
        if request_errors or parsed_response is None:
            if try_count < Constants.API_MAX_RETRIES:
                try_count += 1
                time_sleep = retry_sleep_time(try_count)
                self.logger().info(f"Error fetching data from {url}. HTTP status is {http_status}. "
                                   f"Retrying in {time_sleep:.0f}s.")
                await asyncio.sleep(time_sleep)
                return await self._api_request(method=method, endpoint=endpoint, params=params,
                                               is_auth_required=is_auth_required, try_count=try_count)
            else:
                raise HitbtcAPIError({"error": parsed_response, "status": http_status})
        if "error" in parsed_response:
            raise HitbtcAPIError(parsed_response)
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
        order_id: str = get_new_client_order_id(True, trading_pair)
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
        if not order_type.is_limit_type():
            raise Exception(f"Unsupported order type: {order_type}")
        trading_rule = self._trading_rules[trading_pair]

        amount = self.quantize_order_amount(trading_pair, amount)
        price = self.quantize_order_price(trading_pair, price)
        if amount < trading_rule.min_order_size:
            raise ValueError(f"Buy order amount {amount} is lower than the minimum order size "
                             f"{trading_rule.min_order_size}.")
        order_type_str = order_type.name.lower().split("_")[0]
        api_params = {"symbol": convert_to_exchange_trading_pair(trading_pair),
                      "side": trade_type.name.lower(),
                      "type": order_type_str,
                      "price": f"{price:f}",
                      "quantity": f"{amount:f}",
                      "clientOrderId": order_id,
                      # Without strict validate, HitBTC might adjust order prices/sizes.
                      "strictValidate": "true",
                      }
        if order_type is OrderType.LIMIT_MAKER:
            api_params["postOnly"] = "true"
        self.start_tracking_order(order_id, None, trading_pair, trade_type, price, amount, order_type)
        try:
            order_result = await self._api_request("POST", Constants.ENDPOINT["ORDER_CREATE"], api_params, True)
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
                               event_cls(self.current_timestamp, order_type, trading_pair, amount, price, order_id))
        except asyncio.CancelledError:
            raise
        except HitbtcAPIError as e:
            error_reason = e.error_payload.get('error', {}).get('message')
            self.stop_tracking_order(order_id)
            self.logger().network(
                f"Error submitting {trade_type.name} {order_type.name} order to {Constants.EXCHANGE_NAME} for "
                f"{amount} {trading_pair} {price} - {error_reason}.",
                exc_info=True,
                app_warning_msg=(f"Error submitting order to {Constants.EXCHANGE_NAME} - {error_reason}.")
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
        self._in_flight_orders[order_id] = HitbtcInFlightOrder(
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
        :param trading_pair: The market trading pair (Unused during cancel on HitBTC)
        :param order_id: The internal order id
        order.last_state to change to CANCELED
        """
        order_was_cancelled = False
        try:
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is None:
                raise ValueError(f"Failed to cancel order - {order_id}. Order not found.")
            if tracked_order.exchange_order_id is None:
                await tracked_order.get_exchange_order_id()
            # ex_order_id = tracked_order.exchange_order_id
            await self._api_request("DELETE",
                                    Constants.ENDPOINT["ORDER_DELETE"].format(id=order_id),
                                    is_auth_required=True)
            order_was_cancelled = True
        except asyncio.CancelledError:
            raise
        except HitbtcAPIError as e:
            err = e.error_payload.get('error', e.error_payload)
            self._order_not_found_records[order_id] = self._order_not_found_records.get(order_id, 0) + 1
            if err.get('code') == 20002 and \
                    self._order_not_found_records[order_id] >= self.ORDER_NOT_EXIST_CANCEL_COUNT:
                order_was_cancelled = True
        if order_was_cancelled:
            self.logger().info(f"Successfully cancelled order {order_id} on {Constants.EXCHANGE_NAME}.")
            self.stop_tracking_order(order_id)
            self.trigger_event(MarketEvent.OrderCancelled,
                               OrderCancelledEvent(self.current_timestamp, order_id))
            tracked_order.cancelled_event.set()
            return CancellationResult(order_id, True)
        else:
            self.logger().network(
                f"Failed to cancel order {order_id}: {err.get('message', str(err))}",
                exc_info=True,
                app_warning_msg=f"Failed to cancel the order {order_id} on {Constants.EXCHANGE_NAME}. "
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
                warn_msg = (f"Could not fetch account updates from {Constants.EXCHANGE_NAME}. "
                            "Check API key and network connection.")
                self.logger().network("Unexpected error while fetching account updates.", exc_info=True,
                                      app_warning_msg=warn_msg)
                await asyncio.sleep(0.5)

    async def _update_balances(self):
        """
        Calls REST API to update total and available balances.
        """
        account_info = await self._api_request("GET", Constants.ENDPOINT["USER_BALANCES"], is_auth_required=True)
        self._process_balance_message(account_info)

    async def _update_order_status(self):
        """
        Calls REST API to get status update for each in-flight order.
        """
        last_tick = int(self._last_poll_timestamp / Constants.UPDATE_ORDER_STATUS_INTERVAL)
        current_tick = int(self.current_timestamp / Constants.UPDATE_ORDER_STATUS_INTERVAL)

        if current_tick > last_tick and len(self._in_flight_orders) > 0:
            tracked_orders = list(self._in_flight_orders.values())
            tasks = []
            for tracked_order in tracked_orders:
                # exchange_order_id = await tracked_order.get_exchange_order_id()
                order_id = tracked_order.client_order_id
                tasks.append(self._api_request("GET",
                                               Constants.ENDPOINT["ORDER_STATUS"].format(id=order_id),
                                               is_auth_required=True))
            self.logger().debug(f"Polling for order status updates of {len(tasks)} orders.")
            responses = await safe_gather(*tasks, return_exceptions=True)
            for response, tracked_order in zip(responses, tracked_orders):
                client_order_id = tracked_order.client_order_id
                if isinstance(response, HitbtcAPIError):
                    err = response.error_payload.get('error', response.error_payload)
                    if err.get('code') == 20002:
                        self._order_not_found_records[client_order_id] = \
                            self._order_not_found_records.get(client_order_id, 0) + 1
                        if self._order_not_found_records[client_order_id] < self.ORDER_NOT_EXIST_CONFIRMATION_COUNT:
                            # Wait until the order not found error have repeated a few times before actually treating
                            # it as failed. See: https://github.com/CoinAlpha/hummingbot/issues/601
                            continue
                        self.trigger_event(MarketEvent.OrderFailure,
                                           MarketOrderFailureEvent(
                                               self.current_timestamp, client_order_id, tracked_order.order_type))
                        self.stop_tracking_order(client_order_id)
                    else:
                        continue
                elif "clientOrderId" not in response:
                    self.logger().info(f"_update_order_status clientOrderId not in resp: {response}")
                    continue
                else:
                    self._process_order_message(response)

    def _process_order_message(self, order_msg: Dict[str, Any]):
        """
        Updates in-flight order and triggers cancellation or failure event if needed.
        :param order_msg: The order response from either REST or web socket API (they are of the same format)
        Example Order:
        {
            "id": "4345613661",
            "clientOrderId": "57d5525562c945448e3cbd559bd068c3",
            "symbol": "BCCBTC",
            "side": "sell",
            "status": "new",
            "type": "limit",
            "timeInForce": "GTC",
            "quantity": "0.013",
            "price": "0.100000",
            "cumQuantity": "0.000",
            "postOnly": false,
            "createdAt": "2017-10-20T12:17:12.245Z",
            "updatedAt": "2017-10-20T12:17:12.245Z",
            "reportType": "status"
        }
        """
        client_order_id = order_msg["clientOrderId"]
        if client_order_id not in self._in_flight_orders:
            return
        tracked_order = self._in_flight_orders[client_order_id]
        # Update order execution status
        tracked_order.last_state = order_msg["status"]
        # update order
        tracked_order.executed_amount_base = Decimal(order_msg["cumQuantity"])
        tracked_order.executed_amount_quote = Decimal(order_msg["price"]) * Decimal(order_msg["cumQuantity"])

        if tracked_order.is_cancelled:
            self.logger().info(f"Successfully cancelled order {client_order_id}.")
            self.stop_tracking_order(client_order_id)
            self.trigger_event(MarketEvent.OrderCancelled,
                               OrderCancelledEvent(self.current_timestamp, client_order_id))
            tracked_order.cancelled_event.set()
        elif tracked_order.is_failure:
            self.logger().info(f"The market order {client_order_id} has failed according to order status API. ")
            self.trigger_event(MarketEvent.OrderFailure,
                               MarketOrderFailureEvent(
                                   self.current_timestamp, client_order_id, tracked_order.order_type))
            self.stop_tracking_order(client_order_id)

    async def _process_trade_message(self, trade_msg: Dict[str, Any]):
        """
        Updates in-flight order and trigger order filled event for trade message received. Triggers order completed
        event if the total executed amount equals to the specified order amount.
        Example Trade:
        {
            "id": "4345697765",
            "clientOrderId": "53b7cf917963464a811a4af426102c19",
            "symbol": "ETHBTC",
            "side": "sell",
            "status": "filled",
            "type": "limit",
            "timeInForce": "GTC",
            "quantity": "0.001",
            "price": "0.053868",
            "cumQuantity": "0.001",
            "postOnly": false,
            "createdAt": "2017-10-20T12:20:05.952Z",
            "updatedAt": "2017-10-20T12:20:38.708Z",
            "reportType": "trade",
            "tradeQuantity": "0.001",
            "tradePrice": "0.053868",
            "tradeId": 55051694,
            "tradeFee": "-0.000000005"
        }
        """
        tracked_orders = list(self._in_flight_orders.values())
        for order in tracked_orders:
            await order.get_exchange_order_id()
        track_order = [o for o in tracked_orders if trade_msg["id"] == o.exchange_order_id]
        if not track_order:
            return
        tracked_order = track_order[0]
        updated = tracked_order.update_with_trade_update(trade_msg)
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
                Decimal(str(trade_msg.get("tradePrice", "0"))),
                Decimal(str(trade_msg.get("tradeQuantity", "0"))),
                TradeFee(0.0, [(tracked_order.quote_asset, Decimal(str(trade_msg.get("tradeFee", "0"))))]),
                exchange_trade_id=trade_msg["id"]
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
            await asyncio.sleep(0.1)
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

    def _process_balance_message(self, balance_update):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()
        for account in balance_update:
            asset_name = translate_asset(account["currency"])
            self._account_available_balances[asset_name] = Decimal(str(account["available"]))
            self._account_balances[asset_name] = Decimal(str(account["reserved"])) + Decimal(str(account["available"]))
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

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
        try:
            async with timeout(timeout_seconds):
                cancellation_results = await safe_gather(*tasks, return_exceptions=False)
        except Exception:
            self.logger().network(
                "Unexpected error cancelling orders.", exc_info=True,
                app_warning_msg=(f"Failed to cancel all orders on {Constants.EXCHANGE_NAME}. "
                                 "Check API key and network connection.")
            )
        return cancellation_results

    def tick(self, timestamp: float):
        """
        Is called automatically by the clock for each clock's tick (1 second by default).
        It checks if status polling task is due for execution.
        """
        now = time.time()
        poll_interval = (Constants.SHORT_POLL_INTERVAL
                         if now - self._user_stream_tracker.last_recv_time > 60.0
                         else Constants.LONG_POLL_INTERVAL)
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
                    "Unknown error. Retrying after 1 seconds.", exc_info=True,
                    app_warning_msg=(f"Could not fetch user events from {Constants.EXCHANGE_NAME}. "
                                     "Check API key and network connection."))
                await asyncio.sleep(1.0)

    async def _user_stream_event_listener(self):
        """
        Listens to message in _user_stream_tracker.user_stream queue. The messages are put in by
        HitbtcAPIUserStreamDataSource.
        """
        async for event_message in self._iter_user_event_queue():
            try:
                event_methods = [
                    Constants.WS_METHODS["USER_ORDERS"],
                    Constants.WS_METHODS["USER_TRADES"],
                ]
                method: str = event_message.get("method", None)
                params: str = event_message.get("params", None)
                account_balances: list = event_message.get("result", None)

                if method not in event_methods and account_balances is None:
                    self.logger().error(f"Unexpected message in user stream: {event_message}.", exc_info=True)
                    continue
                if method == Constants.WS_METHODS["USER_TRADES"]:
                    await self._process_trade_message(params)
                elif method == Constants.WS_METHODS["USER_ORDERS"]:
                    for order_msg in params:
                        self._process_order_message(order_msg)
                elif isinstance(account_balances, list) and "currency" in account_balances[0]:
                    self._process_balance_message(account_balances)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await asyncio.sleep(5.0)

    # This is currently unused, but looks like a future addition.
    async def get_open_orders(self) -> List[OpenOrder]:
        result = await self._api_request("GET", Constants.ENDPOINT["USER_ORDERS"], is_auth_required=True)
        ret_val = []
        for order in result:
            if Constants.HBOT_BROKER_ID not in order["clientOrderId"]:
                continue
            if order["type"] != OrderType.LIMIT.name.lower():
                self.logger().info(f"Unsupported order type found: {order['type']}")
                continue
            ret_val.append(
                OpenOrder(
                    client_order_id=order["clientOrderId"],
                    trading_pair=convert_from_exchange_trading_pair(order["symbol"]),
                    price=Decimal(str(order["price"])),
                    amount=Decimal(str(order["quantity"])),
                    executed_amount=Decimal(str(order["cumQuantity"])),
                    status=order["status"],
                    order_type=OrderType.LIMIT,
                    is_buy=True if order["side"].lower() == TradeType.BUY.name.lower() else False,
                    time=str_date_to_ts(order["createdAt"]),
                    exchange_order_id=order["id"]
                )
            )
        return ret_val
