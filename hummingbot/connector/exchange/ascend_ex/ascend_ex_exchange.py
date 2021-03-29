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
import json
import aiohttp
import time
from collections import namedtuple

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
from hummingbot.connector.exchange.ascend_ex.ascend_ex_order_book_tracker import AscendExOrderBookTracker
from hummingbot.connector.exchange.ascend_ex.ascend_ex_user_stream_tracker import AscendExUserStreamTracker
from hummingbot.connector.exchange.ascend_ex.ascend_ex_auth import AscendExAuth
from hummingbot.connector.exchange.ascend_ex.ascend_ex_in_flight_order import AscendExInFlightOrder
from hummingbot.connector.exchange.ascend_ex import ascend_ex_utils
from hummingbot.connector.exchange.ascend_ex.ascend_ex_constants import EXCHANGE_NAME, REST_URL
from hummingbot.core.data_type.common import OpenOrder
ctce_logger = None
s_decimal_NaN = Decimal("nan")


AscendExTradingRule = namedtuple("AscendExTradingRule", "minNotional maxNotional")
AscendExOrder = namedtuple("AscendExOrder", "symbol price orderQty orderType avgPx cumFee cumFilledQty errorCode feeAsset lastExecTime orderId seqNum side status stopPrice execInst")
AscendExBalance = namedtuple("AscendExBalance", "asset availableBalance totalBalance")


class AscendExExchange(ExchangeBase):
    """
    AscendExExchange connects with AscendEx exchange and provides order book pricing, user account tracking and
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
                 ascend_ex_api_key: str,
                 ascend_ex_secret_key: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True
                 ):
        """
        :param ascend_ex_api_key: The API key to connect to private AscendEx APIs.
        :param ascend_ex_secret_key: The API secret.
        :param trading_pairs: The market trading pairs which to track order book data.
        :param trading_required: Whether actual trading is needed.
        """
        super().__init__()
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._ascend_ex_auth = AscendExAuth(ascend_ex_api_key, ascend_ex_secret_key)
        self._order_book_tracker = AscendExOrderBookTracker(trading_pairs=trading_pairs)
        self._user_stream_tracker = AscendExUserStreamTracker(self._ascend_ex_auth, trading_pairs)
        self._ev_loop = asyncio.get_event_loop()
        self._shared_client = None
        self._poll_notifier = asyncio.Event()
        self._last_timestamp = 0
        self._in_flight_orders = {}  # Dict[client_order_id:str, AscendExInFlightOrder]
        self._order_not_found_records = {}  # Dict[client_order_id:str, count:int]
        self._trading_rules = {}  # Dict[trading_pair:str, TradingRule]
        self._ascend_ex_trading_rules = {}  # Dict[trading_pair:str, AscendExTradingRule]
        self._status_polling_task = None
        self._user_stream_event_listener_task = None
        self._trading_rules_polling_task = None
        self._last_poll_timestamp = 0
        self._account_group = None  # required in order to make post requests
        self._account_uid = None  # required in order to produce deterministic order ids

    @property
    def name(self) -> str:
        return EXCHANGE_NAME

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        return self._order_book_tracker.order_books

    @property
    def trading_rules(self) -> Dict[str, TradingRule]:
        return self._trading_rules

    @property
    def in_flight_orders(self) -> Dict[str, AscendExInFlightOrder]:
        return self._in_flight_orders

    @property
    def status_dict(self) -> Dict[str, bool]:
        """
        A dictionary of statuses of various connector's components.
        """
        return {
            "order_books_initialized": self._order_book_tracker.ready,
            "account_balance": len(self._account_balances) > 0 if self._trading_required else True,
            "trading_rule_initialized": len(self._trading_rules) > 0 and len(self._ascend_ex_trading_rules) > 0,
            "user_stream_initialized":
                self._user_stream_tracker.data_source.last_recv_time > 0 if self._trading_required else True,
            "account_data": self._account_group is not None and self._account_uid is not None
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
            key: AscendExInFlightOrder.from_json(value)
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
        await self._update_account_data()
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
            await self._api_request("get", "ticker")
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
                                      app_warning_msg="Could not fetch new trading rules from AscendEx. "
                                                      "Check network connection.")
                await asyncio.sleep(0.5)

    async def _update_trading_rules(self):
        instruments_info = await self._api_request("get", path_url="products")
        [trading_rules, ascend_ex_trading_rules] = self._format_trading_rules(instruments_info)
        self._trading_rules.clear()
        self._trading_rules = trading_rules
        self._ascend_ex_trading_rules.clear()
        self._ascend_ex_trading_rules = ascend_ex_trading_rules

    def _format_trading_rules(
        self,
        instruments_info: Dict[str, Any]
    ) -> [Dict[str, TradingRule], Dict[str, Dict[str, AscendExTradingRule]]]:
        """
        Converts json API response into a dictionary of trading rules.
        :param instruments_info: The json API response
        :return A dictionary of trading rules.
        Response Example:
        {
            "code": 0,
            "data": [
                {
                    "symbol":                "BTMX/USDT",
                    "baseAsset":             "BTMX",
                    "quoteAsset":            "USDT",
                    "status":                "Normal",
                    "minNotional":           "5",
                    "maxNotional":           "100000",
                    "marginTradable":         true,
                    "commissionType":        "Quote",
                    "commissionReserveRate": "0.001",
                    "tickSize":              "0.000001",
                    "lotSize":               "0.001"
                }
            ]
        }
        """
        trading_rules = {}
        ascend_ex_trading_rules = {}
        for rule in instruments_info["data"]:
            try:
                trading_pair = ascend_ex_utils.convert_from_exchange_trading_pair(rule["symbol"])
                trading_rules[trading_pair] = TradingRule(
                    trading_pair,
                    min_price_increment=Decimal(rule["tickSize"]),
                    min_base_amount_increment=Decimal(rule["lotSize"])
                )
                ascend_ex_trading_rules[trading_pair] = AscendExTradingRule(
                    minNotional=Decimal(rule["minNotional"]),
                    maxNotional=Decimal(rule["maxNotional"])
                )
            except Exception:
                self.logger().error(f"Error parsing the trading pair rule {rule}. Skipping.", exc_info=True)
        return [trading_rules, ascend_ex_trading_rules]

    async def _update_account_data(self):
        headers = {
            **self._ascend_ex_auth.get_headers(),
            **self._ascend_ex_auth.get_auth_headers("info"),
        }
        url = f"{REST_URL}/info"
        response = await aiohttp.ClientSession().get(url, headers=headers)

        try:
            parsed_response = json.loads(await response.text())
        except Exception as e:
            raise IOError(f"Error parsing data from {url}. Error: {str(e)}")
        if response.status != 200:
            raise IOError(f"Error fetching data from {url}. HTTP status is {response.status}. "
                          f"Message: {parsed_response}")
        if parsed_response["code"] != 0:
            raise IOError(f"{url} API call failed, response: {parsed_response}")

        self._account_group = parsed_response["data"]["accountGroup"]
        self._account_uid = parsed_response["data"]["userUID"]

    async def _api_request(self,
                           method: str,
                           path_url: str,
                           params: Dict[str, Any] = {},
                           is_auth_required: bool = False,
                           force_auth_path_url: Optional[str] = None
                           ) -> Dict[str, Any]:
        """
        Sends an aiohttp request and waits for a response.
        :param method: The HTTP method, e.g. get or post
        :param path_url: The path url or the API end point
        :param is_auth_required: Whether an authentication is required, when True the function will add encrypted
        signature to the request.
        :returns A response in json format.
        """
        url = None
        headers = None

        if is_auth_required:
            if (self._account_group) is None:
                await self._update_account_data()

            url = f"{ascend_ex_utils.get_rest_url_private(self._account_group)}/{path_url}"
            headers = {
                **self._ascend_ex_auth.get_headers(),
                **self._ascend_ex_auth.get_auth_headers(
                    path_url if force_auth_path_url is None else force_auth_path_url
                ),
            }
        else:
            url = f"{REST_URL}/{path_url}"
            headers = self._ascend_ex_auth.get_headers()

        client = await self._http_client()
        if method == "get":
            response = await client.get(
                url,
                headers=headers
            )
        elif method == "post":
            response = await client.post(
                url,
                headers=headers,
                data=json.dumps(params)
            )
        elif method == "delete":
            response = await client.delete(
                url,
                headers=headers,
                data=json.dumps(params)
            )
        else:
            raise NotImplementedError

        try:
            parsed_response = json.loads(await response.text())
        except Exception as e:
            raise IOError(f"Error parsing data from {url}. Error: {str(e)}")
        if response.status != 200:
            raise IOError(f"Error fetching data from {url}. HTTP status is {response.status}. "
                          f"Message: {parsed_response}")
        if parsed_response["code"] != 0:
            raise IOError(f"{url} API call failed, response: {parsed_response}")

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
        client_order_id = ascend_ex_utils.gen_client_order_id(True, trading_pair)
        safe_ensure_future(self._create_order(TradeType.BUY, client_order_id, trading_pair, amount, order_type, price))
        return client_order_id

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
        client_order_id = ascend_ex_utils.gen_client_order_id(False, trading_pair)
        safe_ensure_future(self._create_order(TradeType.SELL, client_order_id, trading_pair, amount, order_type, price))
        return client_order_id

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
        :param order_id: Internal order id (aka client_order_id)
        :param trading_pair: The market to place order
        :param amount: The order amount (in base token value)
        :param order_type: The order type
        :param price: The order price
        """
        if not order_type.is_limit_type():
            raise Exception(f"Unsupported order type: {order_type}")
        ascend_ex_trading_rule = self._ascend_ex_trading_rules[trading_pair]

        amount = self.quantize_order_amount(trading_pair, amount)
        price = self.quantize_order_price(trading_pair, price)

        try:
            # ascend_ex has a unique way of determening if the order has enough "worth" to be posted
            # see https://ascendex.github.io/ascendex-pro-api/#place-order
            notional = Decimal(price * amount)
            if notional < ascend_ex_trading_rule.minNotional or notional > ascend_ex_trading_rule.maxNotional:
                raise ValueError(f"Notional amount {notional} is not withing the range of {ascend_ex_trading_rule.minNotional}-{ascend_ex_trading_rule.maxNotional}.")

            # TODO: check balance
            [exchange_order_id, timestamp] = ascend_ex_utils.gen_exchange_order_id(self._account_uid, order_id)

            api_params = {
                "id": exchange_order_id,
                "time": timestamp,
                "symbol": ascend_ex_utils.convert_to_exchange_trading_pair(trading_pair),
                "orderPrice": f"{price:f}",
                "orderQty": f"{amount:f}",
                "orderType": "limit",
                "side": trade_type.name
            }

            self.start_tracking_order(
                order_id,
                exchange_order_id,
                trading_pair,
                trade_type,
                price,
                amount,
                order_type
            )

            await self._api_request("post", "cash/order", api_params, True, force_auth_path_url="order")
            tracked_order = self._in_flight_orders.get(order_id)

            if tracked_order is not None:
                self.logger().info(f"Created {order_type.name} {trade_type.name} order {order_id} for "
                                   f"{amount} {trading_pair}.")

            event_tag = MarketEvent.BuyOrderCreated if trade_type is TradeType.BUY else MarketEvent.SellOrderCreated
            event_class = BuyOrderCreatedEvent if trade_type is TradeType.BUY else SellOrderCreatedEvent
            self.trigger_event(event_tag,
                               event_class(
                                   self.current_timestamp,
                                   order_type,
                                   trading_pair,
                                   amount,
                                   price,
                                   order_id,
                                   exchange_order_id=exchange_order_id
                               ))
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.stop_tracking_order(order_id)
            self.logger().network(
                f"Error submitting {trade_type.name} {order_type.name} order to AscendEx for "
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
        self._in_flight_orders[order_id] = AscendExInFlightOrder(
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
            await self._api_request(
                "delete",
                "cash/order",
                {
                    "symbol": ascend_ex_utils.convert_to_exchange_trading_pair(trading_pair),
                    "orderId": ex_order_id,
                    "time": ascend_ex_utils.get_ms_timestamp()
                },
                True,
                force_auth_path_url="order"
            )

            return order_id
        except asyncio.CancelledError:
            raise
        except Exception as e:
            if str(e).find("Order not found") != -1:
                self.stop_tracking_order(order_id)
                return

            self.logger().network(
                f"Failed to cancel order {order_id}: {str(e)}",
                exc_info=True,
                app_warning_msg=f"Failed to cancel the order {order_id} on AscendEx. "
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
                                      app_warning_msg="Could not fetch account updates from AscendEx. "
                                                      "Check API key and network connection.")
                await asyncio.sleep(0.5)

    async def _update_balances(self):
        """
        Calls REST API to update total and available balances.
        """
        response = await self._api_request("get", "cash/balance", {}, True, force_auth_path_url="balance")
        balances = list(map(
            lambda balance: AscendExBalance(
                balance["asset"],
                balance["availableBalance"],
                balance["totalBalance"]
            ),
            response.get("data", list())
        ))
        self._process_balances(balances)

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
                tasks.append(self._api_request(
                    "get",
                    f"cash/order/status?orderId={order_id}",
                    {},
                    True,
                    force_auth_path_url="order/status")
                )
            self.logger().debug(f"Polling for order status updates of {len(tasks)} orders.")
            responses = await safe_gather(*tasks, return_exceptions=True)
            for response in responses:
                if isinstance(response, Exception):
                    raise response
                if "data" not in response:
                    self.logger().info(f"_update_order_status result not in resp: {response}")
                    continue

                order_data = response.get("data")
                self._process_order_message(AscendExOrder(
                    order_data["symbol"],
                    order_data["price"],
                    order_data["orderQty"],
                    order_data["orderType"],
                    order_data["avgPx"],
                    order_data["cumFee"],
                    order_data["cumFilledQty"],
                    order_data["errorCode"],
                    order_data["feeAsset"],
                    order_data["lastExecTime"],
                    order_data["orderId"],
                    order_data["seqNum"],
                    order_data["side"],
                    order_data["status"],
                    order_data["stopPrice"],
                    order_data["execInst"]
                ))

    async def cancel_all(self, timeout_seconds: float):
        """
        Cancels all in-flight orders and waits for cancellation results.
        Used by bot's top level stop and exit commands (cancelling outstanding orders on exit)
        :param timeout_seconds: The timeout at which the operation will be canceled.
        :returns List of CancellationResult which indicates whether each order is successfully cancelled.
        """
        cancellation_results = []
        try:
            await self._api_request(
                "delete",
                "cash/order/all",
                {},
                True,
                force_auth_path_url="order/all"
            )

            open_orders = await self.get_open_orders()

            for cl_order_id, tracked_order in self._in_flight_orders.copy().items():
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
                app_warning_msg="Failed to cancel all orders on AscendEx. Check API key and network connection."
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
                    app_warning_msg="Could not fetch user events from AscendEx. Check API key and network connection."
                )
                await asyncio.sleep(1.0)

    async def _user_stream_event_listener(self):
        """
        Listens to message in _user_stream_tracker.user_stream queue. The messages are put in by
        AscendExAPIUserStreamDataSource.
        """
        async for event_message in self._iter_user_event_queue():
            try:
                if event_message.get("m") == "order":
                    order_data = event_message.get("data")
                    trading_pair = order_data["s"]
                    base_asset, quote_asset = tuple(asset for asset in trading_pair.split("/"))
                    self._process_order_message(AscendExOrder(
                        trading_pair,
                        order_data["p"],
                        order_data["q"],
                        order_data["ot"],
                        order_data["ap"],
                        order_data["cf"],
                        order_data["cfq"],
                        order_data["err"],
                        order_data["fa"],
                        order_data["t"],
                        order_data["orderId"],
                        order_data["sn"],
                        order_data["sd"],
                        order_data["st"],
                        order_data["sp"],
                        order_data["ei"]
                    ))
                    # Handles balance updates from orders.
                    base_asset_balance = AscendExBalance(
                        base_asset,
                        order_data["bab"],
                        order_data["btb"]
                    )
                    quote_asset_balance = AscendExBalance(
                        quote_asset,
                        order_data["qab"],
                        order_data["qtb"]
                    )
                    self._process_balances([base_asset_balance, quote_asset_balance])
                elif event_message.get("m") == "balance":
                    # Handles balance updates from Deposits/Withdrawals, Transfers between Cash and Margin Accounts
                    balance_data = event_message.get("data")
                    balance = AscendExBalance(
                        balance_data["a"],
                        balance_data["ab"],
                        balance_data["tb"]
                    )
                    self._process_balances(list(balance))

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await asyncio.sleep(5.0)

    async def get_open_orders(self) -> List[OpenOrder]:
        result = await self._api_request(
            "get",
            "cash/order/open",
            {},
            True,
            force_auth_path_url="order/open"
        )
        ret_val = []
        for order in result["data"]:
            if order["type"] != "LIMIT":
                raise Exception(f"Unsupported order type {order['type']}")

            exchange_order_id = order["orderId"]
            client_order_id = None
            for in_flight_order in self._in_flight_orders.values():
                if in_flight_order.exchange_order_id == exchange_order_id:
                    client_order_id = in_flight_order.client_order_id

            if client_order_id is None:
                raise Exception(f"Client order id for {exchange_order_id} not found.")

            ret_val.append(
                OpenOrder(
                    client_order_id=client_order_id,
                    trading_pair=ascend_ex_utils.convert_from_exchange_trading_pair(order["symbol"]),
                    price=Decimal(str(order["price"])),
                    amount=Decimal(str(order["orderQty"])),
                    executed_amount=Decimal(str(order["cumFilledQty"])),
                    status=order["status"],
                    order_type=OrderType.LIMIT,
                    is_buy=True if order["side"].lower() == "buy" else False,
                    time=int(order["lastExecTime"]),
                    exchange_order_id=exchange_order_id
                )
            )
        return ret_val

    def _process_order_message(self, order_msg: AscendExOrder):
        """
        Updates in-flight order and triggers cancellation or failure event if needed.
        :param order_msg: The order response from either REST or web socket API (they are of the same format)
        """
        exchange_order_id = order_msg.orderId
        client_order_id = None

        for in_flight_order in self._in_flight_orders.values():
            if in_flight_order.exchange_order_id == exchange_order_id:
                client_order_id = in_flight_order.client_order_id

        if client_order_id is None:
            return

        tracked_order = self._in_flight_orders[client_order_id]

        # update order
        tracked_order.last_state = order_msg.status
        tracked_order.fee_paid = Decimal(order_msg.cumFee)
        tracked_order.fee_asset = order_msg.feeAsset
        tracked_order.executed_amount_base = Decimal(order_msg.cumFilledQty)
        tracked_order.executed_amount_quote = Decimal(order_msg.price) * Decimal(order_msg.cumFilledQty)

        if tracked_order.is_cancelled:
            self.logger().info(f"Successfully cancelled order {client_order_id}.")
            self.trigger_event(MarketEvent.OrderCancelled,
                               OrderCancelledEvent(
                                   self.current_timestamp,
                                   client_order_id,
                                   exchange_order_id))
            tracked_order.cancelled_event.set()
            self.stop_tracking_order(client_order_id)
        elif tracked_order.is_failure:
            self.logger().info(f"The market order {client_order_id} has failed according to order status API. "
                               f"Reason: {ascend_ex_utils.get_api_reason(order_msg.errorCode)}")
            self.trigger_event(MarketEvent.OrderFailure,
                               MarketOrderFailureEvent(
                                   self.current_timestamp,
                                   client_order_id,
                                   tracked_order.order_type
                               ))
            self.stop_tracking_order(client_order_id)
        elif tracked_order.is_done:
            price = Decimal(order_msg.price)
            tracked_order.executed_amount_base = Decimal(order_msg.cumFilledQty)
            tracked_order.executed_amount_quote = price * tracked_order.executed_amount_base
            tracked_order.fee_paid = Decimal(order_msg.cumFee)
            tracked_order.fee_asset = order_msg.feeAsset

            self.trigger_event(
                MarketEvent.OrderFilled,
                OrderFilledEvent(
                    self.current_timestamp,
                    client_order_id,
                    tracked_order.trading_pair,
                    tracked_order.trade_type,
                    tracked_order.order_type,
                    price,
                    tracked_order.executed_amount_base,
                    TradeFee(0.0, [(tracked_order.fee_asset, tracked_order.fee_paid)]),
                    exchange_order_id
                )
            )
            event_tag = MarketEvent.BuyOrderCompleted if tracked_order.trade_type is TradeType.BUY else MarketEvent.SellOrderCompleted
            event_class = BuyOrderCompletedEvent if tracked_order.trade_type is TradeType.BUY else SellOrderCompletedEvent
            self.trigger_event(
                event_tag,
                event_class(
                    self.current_timestamp,
                    client_order_id,
                    tracked_order.base_asset,
                    tracked_order.quote_asset,
                    tracked_order.fee_asset,
                    tracked_order.executed_amount_base,
                    tracked_order.executed_amount_quote,
                    tracked_order.fee_paid,
                    tracked_order.order_type,
                    exchange_order_id
                )
            )
            self.stop_tracking_order(client_order_id)

    def _process_balances(self, balances: List[AscendExBalance]):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        for balance in balances:
            asset_name = balance.asset
            self._account_available_balances[asset_name] = Decimal(balance.availableBalance)
            self._account_balances[asset_name] = Decimal(balance.totalBalance)
            remote_asset_names.add(asset_name)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]
