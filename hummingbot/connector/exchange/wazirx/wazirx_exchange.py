import asyncio
import json
import logging
import math
import time
from decimal import Decimal
from typing import Any, AsyncIterable, Dict, List, Optional

import aiohttp
from async_timeout import timeout

from hummingbot.connector.exchange.wazirx import wazirx_constants as CONSTANTS
from hummingbot.connector.exchange.wazirx import wazirx_utils
from hummingbot.connector.exchange.wazirx.wazirx_auth import WazirxAuth
from hummingbot.connector.exchange.wazirx.wazirx_in_flight_order import WazirxInFlightOrder
from hummingbot.connector.exchange.wazirx.wazirx_order_book_tracker import WazirxOrderBookTracker
from hummingbot.connector.exchange.wazirx.wazirx_user_stream_tracker import WazirxUserStreamTracker
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.clock import Clock
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount
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
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather, wait_til
from hummingbot.logger import HummingbotLogger

ctce_logger = None
s_decimal_NaN = Decimal("nan")


class WazirxExchange(ExchangeBase):
    """
    WazirxExchange connects with Wazirx exchange and provides order book pricing, user account tracking and
    trading functionality.
    """
    API_CALL_TIMEOUT = 10.0
    SHORT_POLL_INTERVAL = 5.0
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0
    LONG_POLL_INTERVAL = 120.0

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global ctce_logger
        if ctce_logger is None:
            ctce_logger = logging.getLogger(__name__)
        return ctce_logger

    def __init__(self,
                 wazirx_api_key: str,
                 wazirx_secret_key: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True
                 ):
        """
        :param wazirx_api_key: The API key to connect to private Wazirx APIs.
        :param wazirx_secret_key: The API secret.
        :param trading_pairs: The market trading pairs which to track order book data.
        :param trading_required: Whether actual trading is needed.
        """
        super().__init__()
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._wazirx_auth = WazirxAuth(wazirx_api_key, wazirx_secret_key)
        self._order_book_tracker = WazirxOrderBookTracker(trading_pairs=trading_pairs)
        self._user_stream_tracker = WazirxUserStreamTracker(self._wazirx_auth, trading_pairs)
        self._ev_loop = asyncio.get_event_loop()
        self._shared_client = None
        self._poll_notifier = asyncio.Event()
        self._last_timestamp = 0
        self._in_flight_orders = {}  # Dict[client_order_id:str, WazirxInFlightOrder]
        self._order_not_found_records = {}  # Dict[client_order_id:str, count:int]
        self._trading_rules = {}  # Dict[trading_pair:str, TradingRule]
        self._status_polling_task = None
        self._user_stream_event_listener_task = None
        self._trading_rules_polling_task = None
        self._last_poll_timestamp = 0
        self._throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)

    @property
    def name(self) -> str:
        return CONSTANTS.EXCHANGE_NAME

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        return self._order_book_tracker.order_books

    @property
    def trading_rules(self) -> Dict[str, TradingRule]:
        return self._trading_rules

    @property
    def in_flight_orders(self) -> Dict[str, WazirxInFlightOrder]:
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
                self._user_stream_tracker.data_source.ready > 0 if self._trading_required else True,
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
            key: WazirxInFlightOrder.from_json(value)
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
            await self._api_request("get", CONSTANTS.CHECK_NETWORK_PATH_URL)
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
                                      app_warning_msg="Could not fetch new trading rules from Wazirx. "
                                                      "Check network connection.")
                await asyncio.sleep(0.5)

    async def _update_trading_rules(self):
        instruments_info = await self._api_request("get", path_url=CONSTANTS.GET_TRADING_RULES_PATH_URL)
        self._trading_rules.clear()
        self._trading_rules = self._format_trading_rules(instruments_info)

    def _format_trading_rules(self, instruments_info: Dict[str, Any]) -> Dict[str, TradingRule]:
        """
        Converts json API response into a dictionary of trading rules.
        :param instruments_info: The json API response
        :return A dictionary of trading rules.
        Response Example:
        {
            "timezone": "UTC",
            "serverTime": 1631531599247,
            "symbols": [
                {
                    "symbol": "btcinr",
                    "status": "trading",
                    "baseAsset": "btc",
                    "quoteAsset": "inr",
                    "baseAssetPrecision": 5,
                    "quoteAssetPrecision": 0,
                    "orderTypes": [
                        "limit",
                        "stop_limit"
                    ],
                    "isSpotTradingAllowed": true,
                    "filters": [
                        {
                            "filterType": "PRICE_FILTER",
                            "minPrice": "1",
                            "tickSize": "1"
                        }
                    ]
                }
            ]
        }
        """
        result = {}
        if "symbols" in instruments_info:
            for rule in instruments_info["symbols"]:
                if rule["isSpotTradingAllowed"] is True:
                    try:
                        trading_pair = wazirx_utils.convert_from_exchange_trading_pair(rule["symbol"])
                        price_decimals = Decimal(str(rule["quoteAssetPrecision"]))
                        quantity_decimals = Decimal(str(rule["baseAssetPrecision"]))
                        # E.g. a price decimal of 2 means 0.01 incremental.
                        price_step = Decimal("1") / Decimal(str(math.pow(10, price_decimals)))
                        quantity_step = Decimal("1") / Decimal(str(math.pow(10, quantity_decimals)))
                        min_order_value = Decimal(wazirx_utils.get_min_order_value(trading_pair))
                        result[trading_pair] = TradingRule(
                            trading_pair,
                            min_price_increment=price_step,
                            min_base_amount_increment=quantity_step,
                            min_order_value=min_order_value,
                        )
                    except Exception:
                        self.logger().error(f"Error parsing the trading pair rule {rule}. Skipping.", exc_info=True)

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
        async with self._throttler.execute_task(path_url):
            url = f"{CONSTANTS.WAZIRX_API_BASE}/{path_url}"
            client = await self._http_client()
            if is_auth_required:
                params = self._wazirx_auth.get_auth(params)
                headers = self._wazirx_auth.get_headers()
            else:
                headers = {"Content-Type": "application/json"}

            if method == "get":
                response = await client.get(url, headers=headers, data=params)
            elif method == "post":
                response = await client.post(url, headers=headers, data=params)
            elif method == "delete":
                response = await client.delete(url, headers=headers, data=params)
            else:
                raise NotImplementedError

            try:
                parsed_response = json.loads(await response.text())
            except Exception as e:
                raise IOError(f"Error parsing data from {url}. Error: {str(e)}")
            if response.status != 200 and response.status != 201:
                raise IOError(f"Error fetching data from {url}. HTTP status is {response.status}. "
                              f"Message: {parsed_response}, {params}")
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
        order_id: str = wazirx_utils.get_new_client_order_id(True, trading_pair)
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
        order_id: str = wazirx_utils.get_new_client_order_id(False, trading_pair)
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
            self.trigger_event(MarketEvent.OrderFailure,
                               MarketOrderFailureEvent(self.current_timestamp, order_id, order_type))
            raise ValueError(f"Buy order amount {amount} is lower than the minimum order size "
                             f"{trading_rule.min_order_size}.")

        order_value: Decimal = amount * price
        if order_value < trading_rule.min_order_value:
            self.trigger_event(MarketEvent.OrderFailure,
                               MarketOrderFailureEvent(self.current_timestamp, order_id, order_type))
            raise ValueError(f"{trade_type.name} order value {order_value} is lower than the minimum order value "
                             f"{trading_rule.min_order_value}.")

        api_params = {
            "symbol": wazirx_utils.convert_to_exchange_trading_pair(trading_pair),
            "side": trade_type.name.lower(),
            "type": "limit",
            "price": f"{price:f}",
            "quantity": f"{amount:f}",
            # "client_oid": f"{order_id}"
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
            order_result = await self._api_request("post", CONSTANTS.ORDER_PATH_URL, api_params, True)
            self.logger().info(order_result)
            exchange_order_id = str(order_result["id"])
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
                f"Error submitting {trade_type.name} {order_type.name} order to Wazirx for "
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
        self._in_flight_orders[order_id] = WazirxInFlightOrder(
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
                "symbol": wazirx_utils.convert_to_exchange_trading_pair(trading_pair),
                "orderId": ex_order_id
            }
            result = await self._api_request(
                "delete",
                CONSTANTS.ORDER_PATH_URL,
                api_params,
                True
            )

            if result["status"] == "wait":
                await wait_til(lambda: tracked_order.is_cancelled)
                return order_id
            else:
                tracked_order.last_state = result["status"]
                if tracked_order.is_cancelled:
                    self._process_order_message(result)
                    return order_id
                elif tracked_order.is_done:
                    api_params = {
                        "limit": 100,
                        "symbol": wazirx_utils.convert_to_exchange_trading_pair(trading_pair),
                        "orderId": ex_order_id,
                    }
                    order_trades = await self._api_request("get", CONSTANTS.MY_TRADES_PATH_URL, api_params, True)
                    for order_trade in order_trades:
                        trade_msg = {
                            "order_id": ex_order_id,
                            "trade_id": str(order_trade["id"]),
                            "traded_price": order_trade["price"],
                            "traded_quantity": order_trade["qty"],
                            "quote_quantity": order_trade["quoteQty"],
                            "fee": order_trade["fee"],
                            "fee_currency": order_trade["feeCurrency"].upper(),
                        }
                        await self._process_trade_message(trade_msg)
                    return order_id

        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(
                f"Failed to cancel order {order_id}: {str(e)}",
                exc_info=True,
                app_warning_msg=f"Failed to cancel the order {order_id} on Wazirx. "
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
                                      app_warning_msg="Could not fetch account updates from Wazirx. "
                                                      "Check API key and network connection.")
                await asyncio.sleep(0.5)

    async def _update_balances(self):
        """
        Calls REST API to update total and available balances.
        """
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()
        account_info = await self._api_request("get", CONSTANTS.FUND_DETAILS_PATH_URL, {}, True)
        for account in account_info:
            asset_name = account["asset"].upper()
            self._account_available_balances[asset_name] = Decimal(str(account["free"]))
            self._account_balances[asset_name] = self._account_available_balances[asset_name] + Decimal(str(account["locked"]))
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
                order_id = await tracked_order.get_exchange_order_id()
                api_params = {"orderId": order_id}
                tasks.append(self._api_request("get",
                                               CONSTANTS.ORDER_PATH_URL,
                                               api_params,
                                               True))
            self.logger().debug(f"Polling for order status updates of {len(tasks)} orders.")
            responses = await safe_gather(*tasks, return_exceptions=True)

            for response in responses:
                if isinstance(response, Exception):
                    raise response
                elif "status" not in response:
                    self.logger().info(f"_update_order_status result not in resp: {response}")
                    continue
                else:
                    api_params = {
                        "limit": 100,
                        "symbol": response["symbol"],
                        "orderId": response["id"],
                    }
                    order_trades = await self._api_request("get", CONSTANTS.MY_TRADES_PATH_URL, api_params, True)
                    for order_trade in order_trades:
                        trade_msg = {
                            "order_id": str(response["id"]),
                            "trade_id": str(order_trade["id"]),
                            "traded_price": order_trade["price"],
                            "traded_quantity": order_trade["qty"],
                            "quote_quantity": order_trade["quoteQty"],
                        }
                        await self._process_trade_message(trade_msg)
                    self._process_order_message(response)

    def _process_order_message(self, order_msg: Dict[str, Any]):
        """
        Updates in-flight order and triggers cancellation or failure event if needed.
        :param order_msg: The order response from either REST or web socket API (they are of the same format)
        """
        exchange_order_id = str(order_msg['id'])
        """
        Currently wazirx api are not supporting client_order_id, so looping through
        each in flight order and matching exchange order id.
        """
        for order in list(self._in_flight_orders.values()):
            if str(order.exchange_order_id) == str(exchange_order_id):
                client_order_id = order.client_order_id
                tracked_order = self._in_flight_orders[client_order_id]
                tracked_order.last_state = order_msg["status"]

                if tracked_order.is_cancelled:
                    self.logger().info(f"Successfully cancelled order {client_order_id}.")
                    self.trigger_event(
                        MarketEvent.OrderCancelled,
                        OrderCancelledEvent(
                            self.current_timestamp,
                            client_order_id
                        )
                    )
                    tracked_order.cancelled_event.set()
                    self.stop_tracking_order(client_order_id)
                elif tracked_order.is_failure:
                    self.logger().info(f"The market order {client_order_id} has failed according to order status API. ")
                    self.trigger_event(
                        MarketEvent.OrderFailure,
                        MarketOrderFailureEvent(
                            self.current_timestamp,
                            client_order_id,
                            tracked_order.order_type
                        )
                    )
                    self.stop_tracking_order(client_order_id)

    async def _process_trade_message(self, trade_msg: Dict[str, Any]):
        """
        Updates in-flight order and trigger order filled event for trade message received. Triggers order completed
        event if the total executed amount equals to the specified order amount.
        """
        for order in self._in_flight_orders.values():
            await order.get_exchange_order_id()
        track_order = [o for o in self._in_flight_orders.values() if trade_msg["order_id"] == o.exchange_order_id]
        if not track_order:
            return
        tracked_order = track_order[0]

        updated = tracked_order.update_with_trade_update(trade_msg)
        if not updated:
            return
        self.logger().info("_process_trade_message")
        self.logger().info(trade_msg)
        self.trigger_event(
            MarketEvent.OrderFilled,
            OrderFilledEvent(
                self.current_timestamp,
                tracked_order.client_order_id,
                tracked_order.trading_pair,
                tracked_order.trade_type,
                tracked_order.order_type,
                Decimal(str(trade_msg["traded_price"])),
                Decimal(str(trade_msg["traded_quantity"])),
                AddedToCostTradeFee(flat_fees=[TokenAmount(trade_msg["fee_currency"], Decimal(str(trade_msg["fee"])))]),
                exchange_trade_id=trade_msg["trade_id"]
            )
        )
        if math.isclose(tracked_order.executed_amount_base, tracked_order.amount) or \
                tracked_order.executed_amount_base >= tracked_order.amount:
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
                                           tracked_order.order_type))
            self.stop_tracking_order(tracked_order.client_order_id)

    async def cancel_all(self, timeout_seconds: float):
        """
        Cancels all in-flight orders and waits for cancellation results.
        Used by bot's top level stop and exit commands (cancelling outstanding orders on exit)
        :param timeout_seconds: The timeout at which the operation will be canceled.
        :returns List of CancellationResult which indicates whether each order is successfully cancelled.
        """
        incomplete_orders = [o for o in self._in_flight_orders.values() if not o.is_done]
        tasks = [self._execute_cancel(o.trading_pair, o.client_order_id) for o in incomplete_orders]
        order_id_set = set([o.client_order_id for o in incomplete_orders])
        successful_cancellations = []
        try:
            self.logger().info("Start Cancel ALL ................")
            async with timeout(timeout_seconds):
                results = await safe_gather(*tasks, return_exceptions=True)
                for result in results:
                    if result is not None and not isinstance(result, Exception):
                        order_id_set.remove(result)
                        successful_cancellations.append(CancellationResult(result, True))
        except Exception:
            self.logger().error("Cancel all failed.", exc_info=True)
            self.logger().network(
                "Unexpected error cancelling orders.",
                exc_info=True,
                app_warning_msg="Failed to cancel order on Wazirx. Check API key and network connection."
            )

        failed_cancellations = [CancellationResult(oid, False) for oid in order_id_set]
        return successful_cancellations + failed_cancellations

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
                    app_warning_msg="Could not fetch user events from Wazirx. Check API key and network connection."
                )
                await asyncio.sleep(1.0)

    async def _user_stream_event_listener(self):
        """
        Listens to message in _user_stream_tracker.user_stream queue. The messages are put in by
        WazirxAPIUserStreamDataSource.
        """
        async for event_message in self._iter_user_event_queue():
            try:
                self.logger().info(event_message)
                if "data" not in event_message or "stream" not in event_message:
                    continue
                stream = event_message["stream"]
                if "ownTrade" in stream:
                    trade_evt = event_message["data"]
                    trade_msg = {
                        "trade_id": str(trade_evt["t"]),
                        "order_id": str(trade_evt["o"]),
                        "traded_price": trade_evt["p"],
                        "traded_quantity": trade_evt["q"],
                        "fee_currency": trade_evt["U"].upper(),
                        "fee": trade_evt["f"]
                    }
                    await self._process_trade_message(trade_msg)
                elif "orderUpdate" in stream:
                    order_evt = event_message["data"]
                    order_msg = {
                        "id": order_evt["i"],
                        "status": order_evt["X"],
                    }
                    self._process_order_message(order_msg)
                elif "outboundAccountPosition" in stream:
                    balances = event_message["data"]["B"]
                    for balance_entry in balances:
                        asset_name = balance_entry["a"].upper()
                        free_balance = Decimal(str(balance_entry["b"]))
                        locked_balance = Decimal(str(balance_entry["l"]))
                        self._account_balances[asset_name] = free_balance + locked_balance
                        self._account_available_balances[asset_name] = free_balance
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await asyncio.sleep(5.0)
