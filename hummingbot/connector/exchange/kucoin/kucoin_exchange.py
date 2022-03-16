import asyncio
import logging
from decimal import Decimal
from typing import (
    Any,
    AsyncIterable,
    Dict,
    List,
    Optional,
)

import aiohttp

from hummingbot.connector.exchange.kucoin import (
    kucoin_constants as CONSTANTS,
    kucoin_web_utils as web_utils,
)
from hummingbot.connector.exchange.kucoin.kucoin_api_order_book_data_source import KucoinAPIOrderBookDataSource
from hummingbot.connector.exchange.kucoin.kucoin_auth import KucoinAuth
from hummingbot.connector.exchange.kucoin.kucoin_in_flight_order import (
    KucoinInFlightOrder,
    KucoinInFlightOrderNotCreated,
)
from hummingbot.connector.exchange.kucoin.kucoin_order_book_tracker import KucoinOrderBookTracker
from hummingbot.connector.exchange.kucoin.kucoin_user_stream_tracker import KucoinUserStreamTracker
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.utils import get_new_client_order_id
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.common import OrderType, TradeType
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
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.logger import HummingbotLogger

s_decimal_0 = Decimal(0)
s_decimal_NaN = Decimal("nan")

MINUTE = 60
TWELVE_HOURS = MINUTE * 60 * 12


class KucoinAPIError(IOError):
    def __init__(self, error_payload: Dict[str, Any]):
        super().__init__()
        self.error_payload = error_payload


class KucoinExchange(ExchangePyBase):
    _logger = None

    API_CALL_TIMEOUT = 10.0
    UPDATE_ORDERS_INTERVAL = 10.0
    SHORT_POLL_INTERVAL = 5.0
    LONG_POLL_INTERVAL = 120.0

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self,
                 kucoin_api_key: str,
                 kucoin_passphrase: str,
                 kucoin_secret_key: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN):

        self._domain = domain
        self._time_synchronizer = TimeSynchronizer()
        super().__init__()
        self._auth = KucoinAuth(
            api_key=kucoin_api_key,
            passphrase=kucoin_passphrase,
            secret_key=kucoin_secret_key,
            time_provider=self._time_synchronizer)
        self._throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        self._api_factory = web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            domain=self._domain,
            auth=self._auth)
        # TODO: remove _rest_assistant
        self._rest_assistant = None
        self._in_flight_orders = {}
        self._last_poll_timestamp = 0
        self._last_timestamp = 0
        self._trading_pairs = trading_pairs
        self._order_book_tracker = KucoinOrderBookTracker(
            trading_pairs=trading_pairs,
            domain=self._domain,
            api_factory=self._api_factory,
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer)
        self._poll_notifier = asyncio.Event()
        self._shared_client = None
        self._status_polling_task = None
        self._trading_required = trading_required
        self._trading_rules = {}
        self._trading_rules_polling_task = None
        self._trading_fees = {}
        self._trading_fees_polling_task = None
        self._user_stream_tracker = KucoinUserStreamTracker(
            domain=self._domain,
            throttler=self._throttler,
            api_factory=self._api_factory)

    @property
    def name(self) -> str:
        return "kucoin"

    @property
    def order_book_tracker(self) -> KucoinOrderBookTracker:
        return self._order_book_tracker

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        return self._order_book_tracker.order_books

    @property
    def trading_rules(self) -> Dict[str, TradingRule]:
        return self._trading_rules

    @property
    def in_flight_orders(self) -> Dict[str, KucoinInFlightOrder]:
        return self._in_flight_orders

    @property
    def limit_orders(self) -> List[LimitOrder]:
        return [
            in_flight_order.to_limit_order()
            for in_flight_order in self._in_flight_orders.values()
        ]

    @property
    def tracking_states(self) -> Dict[str, Any]:
        return {
            key: value.to_json()
            for key, value in self._in_flight_orders.items()
            if not value.is_done
        }

    def restore_tracking_states(self, saved_states: Dict[str, Any]):
        self._in_flight_orders.update({
            key: KucoinInFlightOrder.from_json(value)
            for key, value in saved_states.items()
        })

    @property
    def user_stream_tracker(self) -> KucoinUserStreamTracker:
        return self._user_stream_tracker

    async def start_network(self):
        self._stop_network()
        self._order_book_tracker.start()
        self._trading_rules_polling_task = safe_ensure_future(self._trading_rules_polling_loop())
        self._trading_fees_polling_task = safe_ensure_future(self._trading_fees_polling_loop())
        if self._trading_required:
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())
            self._user_stream_tracker_task = safe_ensure_future(self._user_stream_tracker.start())
            self._user_stream_event_listener_task = safe_ensure_future(self._user_stream_event_listener())
            await self._update_balances()

    def _stop_network(self):
        # Resets timestamps and events for status_polling_loop
        self._last_poll_timestamp = 0
        self._last_timestamp = 0
        self._poll_notifier = asyncio.Event()

        self._order_book_tracker.stop()
        if self._status_polling_task is not None:
            self._status_polling_task.cancel()
            self._status_polling_task = None
        if self._trading_rules_polling_task is not None:
            self._trading_rules_polling_task.cancel()
            self._trading_rules_polling_task = None
        if self._trading_fees_polling_task is not None:
            self._trading_fees_polling_task.cancel()
            self._trading_fees_polling_task = None
        if self._user_stream_tracker_task is not None:
            self._user_stream_tracker_task.cancel()
            self._user_stream_tracker_task = None
        if self._user_stream_event_listener_task is not None:
            self._user_stream_event_listener_task.cancel()
            self._user_stream_event_listener_task = None

    async def stop_network(self):
        self._stop_network()

    async def check_network(self) -> NetworkStatus:
        try:
            await self._api_request(path_url=CONSTANTS.SERVER_TIME_PATH_URL, method=RESTMethod.GET)
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    def tick(self, timestamp: float):
        super().tick()

        poll_interval = (self.SHORT_POLL_INTERVAL
                         if timestamp - self.user_stream_tracker.last_recv_time > 60.0
                         else self.LONG_POLL_INTERVAL)
        last_tick = int(self._last_timestamp / poll_interval)
        current_tick = int(timestamp / poll_interval)

        if current_tick > last_tick:
            self._poll_notifier.set()
        self._last_timestamp = timestamp

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
                    app_warning_msg="Could not fetch user events from Binance. Check API key and network connection."
                )
                await asyncio.sleep(1.0)

    async def _user_stream_event_listener(self):
        async for event_message in self._iter_user_event_queue():
            try:
                event_type = event_message.get("type")
                event_topic = event_message.get("topic")
                execution_data = event_message.get("data")

                # Refer to https://docs.kucoin.com/#private-order-change-events
                if event_type == "message" and event_topic == "/spotMarket/tradeOrders":
                    execution_status = execution_data["status"]
                    execution_type = execution_data["type"]
                    client_order_id: Optional[str] = execution_data.get("clientOid")

                    tracked_order = self._in_flight_orders.get(client_order_id)

                    if tracked_order is None:
                        self.logger().debug(f"Unrecognized order ID from user stream: {client_order_id}.")
                        self.logger().debug(f"Event: {event_message}")
                        continue
                elif event_type == "message" and event_topic == "/account/balance":
                    if "trade" in execution_data["relationEvent"]:
                        currency = execution_data["currency"]
                        available_balance = Decimal(execution_data["available"])
                        total_balance = Decimal(execution_data["total"])
                        self._account_balances.update({currency: total_balance})
                        self._account_available_balances.update({currency: available_balance})
                        continue
                else:
                    continue

                if (execution_status == "open" or execution_status == "match") and execution_type != "open":
                    if Decimal(execution_data["matchSize"]) > 0:
                        execute_amount_diff = Decimal(execution_data["matchSize"])
                        execute_price = Decimal(execution_data["price"])
                        tracked_order.executed_amount_base = Decimal(execution_data["filledSize"])
                        tracked_order.executed_amount_quote = Decimal(execution_data["filledSize"]) * Decimal(
                            execute_price)
                        self.logger().info(f"Filled {execute_amount_diff} out of {tracked_order.amount} of the "
                                           f"order {tracked_order.client_order_id}.")
                        self.trigger_event(MarketEvent.OrderFilled,
                                           OrderFilledEvent(
                                               self.current_timestamp,
                                               tracked_order.client_order_id,
                                               tracked_order.trading_pair,
                                               tracked_order.trade_type,
                                               tracked_order.order_type,
                                               execute_price,
                                               execute_amount_diff,
                                               self.get_fee(
                                                   tracked_order.base_asset,
                                                   tracked_order.quote_asset,
                                                   tracked_order.order_type,
                                                   tracked_order.trade_type,
                                                   execute_price,
                                                   execute_amount_diff,
                                               ),
                                               str(execution_data["ts"])
                                           ))
                if (execution_status == "done" or execution_status == "match") and (
                        execution_type == "match" or execution_type == "filled"):
                    tracked_order.last_state = "DONE"
                    tracked_order.executed_amount_base = Decimal(execution_data["filledSize"])
                    tracked_order.executed_amount_quote = Decimal(execution_data["filledSize"]) * Decimal(
                        execution_data["price"])
                    if tracked_order.trade_type == TradeType.BUY:
                        self.logger().info(f"The market buy order {tracked_order.client_order_id} has completed "
                                           f"according to KuCoin user stream.")
                        self.trigger_event(MarketEvent.BuyOrderCompleted,
                                             BuyOrderCompletedEvent(self.current_timestamp,
                                                                    tracked_order.client_order_id,
                                                                    tracked_order.base_asset,
                                                                    tracked_order.quote_asset,
                                                                    tracked_order.executed_amount_base,
                                                                    tracked_order.executed_amount_quote,
                                                                    tracked_order.order_type,
                                                                    exchange_order_id=tracked_order.exchange_order_id))
                    else:
                        self.logger().info(f"The market sell order {tracked_order.client_order_id} has completed "
                                           f"according to KuCoin user stream.")
                        self.trigger_event(MarketEvent.SellOrderCompleted,
                                             SellOrderCompletedEvent(self.current_timestamp,
                                                                     tracked_order.client_order_id,
                                                                     tracked_order.base_asset,
                                                                     tracked_order.quote_asset,
                                                                     tracked_order.executed_amount_base,
                                                                     tracked_order.executed_amount_quote,
                                                                     tracked_order.order_type,
                                                                     exchange_order_id=tracked_order.exchange_order_id))
                    self.stop_tracking_order(tracked_order.client_order_id)
                elif execution_status == "done" and execution_type == "canceled":
                    tracked_order.last_state = "CANCEL"
                    self.logger().info(f"Successfully cancelled order {tracked_order.client_order_id}.")
                    self.trigger_event(MarketEvent.OrderCancelled,
                                       OrderCancelledEvent(self.current_timestamp,
                                                           tracked_order.client_order_id,
                                                           exchange_order_id=tracked_order.exchange_order_id))
                    self.stop_tracking_order(tracked_order.client_order_id)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await asyncio.sleep(5.0)

    async def _http_client(self) -> aiohttp.ClientSession:
        if self._shared_client is None:
            self._shared_client = aiohttp.ClientSession()
        return self._shared_client

    async def _api_request(self,
                           path_url,
                           method: RESTMethod = RESTMethod.GET,
                           params: Optional[Dict[str, Any]] = None,
                           data: Optional[Dict[str, Any]] = None,
                           is_auth_required: bool = False,
                           limit_id: Optional[str] = None) -> Dict[str, Any]:

        return await web_utils.api_request(
            path=path_url,
            api_factory=self._api_factory,
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            domain=self._domain,
            params=params,
            data=data,
            method=method,
            is_auth_required=is_auth_required,
            limit_id=limit_id
        )

    async def _update_balances(self):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        response = await self._api_request(
            path_url=CONSTANTS.ACCOUNTS_PATH_URL,
            method=RESTMethod.GET,
            is_auth_required=True)

        if response:
            for balance_entry in response["data"]:
                asset_name = balance_entry["currency"]
                self._account_available_balances[asset_name] = Decimal(balance_entry["available"])
                self._account_balances[asset_name] = Decimal(balance_entry["balance"])
                remote_asset_names.add(asset_name)

            asset_names_to_remove = local_asset_names.difference(remote_asset_names)
            for asset_name in asset_names_to_remove:
                del self._account_available_balances[asset_name]
                del self._account_balances[asset_name]

    async def _update_trading_rules(self):
        # The poll interval for trade rules is 60 seconds.
        last_tick = int(self._last_timestamp / 60.0)
        current_tick = int(self.current_timestamp / 60.0)

        if current_tick > last_tick or len(self._trading_rules) < 1:
            exchange_info = await self._api_request(path_url=CONSTANTS.SYMBOLS_PATH_URL, method=RESTMethod.GET)
            trading_rules_list = await self._format_trading_rules(exchange_info)
            self._trading_rules.clear()
            for trading_rule in trading_rules_list:
                self._trading_rules[trading_rule.trading_pair] = trading_rule

    async def _update_trading_fees(self):
        for trading_pair in self._trading_pairs:
            await self._update_trading_fee(trading_pair)

    async def _update_trading_fee(self, trading_pair: str):
        resp = await self._api_request(
            path_url=CONSTANTS.FEE_PATH_URL,
            params={"symbols": trading_pair},
            method=RESTMethod.GET,
            is_auth_required=True,
        )
        fees_data = resp["data"][0]
        self._trading_fees[trading_pair] = fees_data

    async def _format_trading_rules(self, raw_trading_pair_info: List[Dict[str, Any]]) -> List[TradingRule]:
        trading_rules = []

        for info in raw_trading_pair_info["data"]:
            try:
                trading_pair = await KucoinAPIOrderBookDataSource.trading_pair_associated_to_exchange_symbol(
                    symbol=info.get("symbol"),
                    domain=self._domain,
                    api_factory=self._api_factory,
                    throttler=self._throttler)
                trading_rules.append(
                    TradingRule(trading_pair=trading_pair,
                                min_order_size=Decimal(info["baseMinSize"]),
                                max_order_size=Decimal(info["baseMaxSize"]),
                                min_price_increment=Decimal(info['priceIncrement']),
                                min_base_amount_increment=Decimal(info['baseIncrement']),
                                min_quote_amount_increment=Decimal(info['quoteIncrement']),
                                min_notional_size=Decimal(info["quoteMinSize"]))
                )
            except Exception:
                self.logger().error(f"Error parsing the trading_pair rule {info}. Skipping.", exc_info=True)
        return trading_rules

    async def get_order_status(self, exchange_order_id: str) -> Dict[str, Any]:
        path_url = f"{CONSTANTS.ORDERS_PATH_URL}/{exchange_order_id}"
        return await self._api_request(
            path_url=path_url,
            method=RESTMethod.GET,
            is_auth_required=True,
            limit_id=CONSTANTS.GET_ORDER_LIMIT_ID
        )

    async def _update_order_status(self):
        # The poll interval for order status is 10 seconds.
        last_tick = int(self._last_poll_timestamp / self.UPDATE_ORDERS_INTERVAL)
        current_tick = int(self.current_timestamp / self.UPDATE_ORDERS_INTERVAL)

        if current_tick > last_tick and len(self._in_flight_orders) > 0:
            tracked_orders = list(self._in_flight_orders.values())
            for tracked_order in tracked_orders:
                exchange_order_id = await tracked_order.get_exchange_order_id()
                order_update = await self.get_order_status(exchange_order_id)
                if tracked_order.client_order_id not in self.in_flight_orders:
                    continue  # asynchronously removed in _user_stream_event_listener
                if order_update is None:
                    self.logger().network(
                        f"Error fetching status update for the order {tracked_order.client_order_id}: "
                        f"{order_update}.",
                        app_warning_msg=f"Could not fetch updates for the order {tracked_order.client_order_id}. "
                                        f"The order has either been filled or canceled."
                    )
                    continue

                order_state = order_update["data"]["isActive"]
                if order_state:
                    continue

                # Calculate the newly executed amount for this update.
                if order_update["data"]["opType"] == "DEAL":
                    if order_state:
                        tracked_order.last_state = "DEAL"
                    else:
                        tracked_order.last_state = "DONE"
                else:
                    tracked_order.last_state = "CANCEL"
                new_confirmed_amount = Decimal(
                    order_update["data"]["dealFunds"])  # API isn't detailed enough assuming dealSize
                execute_amount_diff = Decimal(order_update["data"]["dealSize"])

                if execute_amount_diff > s_decimal_0:
                    tracked_order.executed_amount_base = Decimal(order_update["data"]["dealSize"])
                    tracked_order.executed_amount_quote = new_confirmed_amount
                    tracked_order.fee_paid = Decimal(order_update["data"]["fee"])
                    execute_price = Decimal(order_update["data"]["dealFunds"]) / execute_amount_diff
                    order_filled_event = OrderFilledEvent(
                        self.current_timestamp,
                        tracked_order.client_order_id,
                        tracked_order.trading_pair,
                        tracked_order.trade_type,
                        tracked_order.order_type,
                        float(execute_price),
                        float(execute_amount_diff),
                        self.get_fee(
                            tracked_order.base_asset,
                            tracked_order.quote_asset,
                            tracked_order.order_type,
                            tracked_order.trade_type,
                            float(execute_price),
                            float(execute_amount_diff),
                        ),
                        exchange_trade_id=str(int(self._time() * 1e6)),
                    )
                    self.logger().info(f"Filled {execute_amount_diff} out of {tracked_order.amount} of the "
                                       f"order {tracked_order.client_order_id}.")
                    self.trigger_event(MarketEvent.OrderFilled, order_filled_event)

                if order_state is False and order_update["data"]["cancelExist"] is False:
                    self.stop_tracking_order(tracked_order.client_order_id)
                    if tracked_order.trade_type is TradeType.BUY:
                        self.logger().info(f"The market buy order {tracked_order.client_order_id} has completed "
                                           f"according to order status API.")
                        self.trigger_event(MarketEvent.BuyOrderCompleted,
                                             BuyOrderCompletedEvent(self.current_timestamp,
                                                                    tracked_order.client_order_id,
                                                                    tracked_order.base_asset,
                                                                    tracked_order.quote_asset,
                                                                    float(tracked_order.executed_amount_base),
                                                                    float(tracked_order.executed_amount_quote),
                                                                    tracked_order.order_type,
                                                                    exchange_order_id=tracked_order.exchange_order_id))
                    else:
                        self.logger().info(f"The market sell order {tracked_order.client_order_id} has completed "
                                           f"according to order status API.")
                        self.trigger_event(MarketEvent.SellOrderCompleted,
                                             SellOrderCompletedEvent(self.current_timestamp,
                                                                     tracked_order.client_order_id,
                                                                     tracked_order.base_asset,
                                                                     tracked_order.quote_asset,
                                                                     float(tracked_order.executed_amount_base),
                                                                     float(tracked_order.executed_amount_quote),
                                                                     tracked_order.order_type,
                                                                     exchange_order_id=tracked_order.exchange_order_id))

                if order_state is False and order_update["data"]["cancelExist"] is True:
                    self.stop_tracking_order(tracked_order.client_order_id)
                    self.logger().info(f"The market order {tracked_order.client_order_id} has been cancelled according"
                                       f" to order status API.")
                    self.trigger_event(MarketEvent.OrderCancelled,
                                       OrderCancelledEvent(self.current_timestamp,
                                                           tracked_order.client_order_id,
                                                           exchange_order_id=tracked_order.exchange_order_id))

    async def _status_polling_loop(self):
        while True:
            try:
                await self._poll_notifier.wait()

                await safe_gather(
                    self._update_balances(),
                    self._update_order_status(),
                )
                self._last_poll_timestamp = self.current_timestamp
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network("Unexpected error while fetching account updates.",
                                      exc_info=True,
                                      app_warning_msg="Could not fetch account updates from Kucoin. "
                                                      "Check API key and network connection.")
                await asyncio.sleep(0.5)
            finally:
                self._poll_notifier = asyncio.Event()

    async def _trading_rules_polling_loop(self):
        while True:
            try:
                await self._update_trading_rules()
                await asyncio.sleep(MINUTE)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network("Unexpected error while fetching trading rules.",
                                      exc_info=True,
                                      app_warning_msg="Could not fetch new trading rules from Kucoin. "
                                                      "Check network connection.")
                await asyncio.sleep(0.5)

    async def _trading_fees_polling_loop(self):
        while True:
            try:
                await self._update_trading_fees()
                await asyncio.sleep(TWELVE_HOURS)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network("Unexpected error while fetching trading fees.",
                                      exc_info=True,
                                      app_warning_msg="Could not fetch new trading fees from Kucoin. "
                                                      "Check network connection.")
                await asyncio.sleep(0.5)

    @property
    def status_dict(self) -> Dict[str, bool]:
        return {
            "order_books_initialized": self._order_book_tracker.ready,
            "account_balance": self._account_balances if self._trading_required else True,
            "trading_rule_initialized": len(self._trading_rules) > 0,
            "user_stream_initialized":
                self._user_stream_tracker.data_source.last_recv_time > 0 if self._trading_required else True,
        }

    @property
    def ready(self) -> bool:
        return all(self.status_dict.values())

    def supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER]

    async def place_order(self,
                          order_id: str,
                          trading_pair: str,
                          amount: Decimal,
                          is_buy: bool,
                          order_type: OrderType,
                          price: Decimal) -> str:
        path_url = CONSTANTS.ORDERS_PATH_URL
        side = "buy" if is_buy else "sell"
        order_type_str = "limit"
        data = {
            "size": str(amount),
            "clientOid": order_id,
            "side": side,
            "symbol": await KucoinAPIOrderBookDataSource.exchange_symbol_associated_to_pair(
                trading_pair=trading_pair,
                domain=self._domain,
                api_factory=self._api_factory,
                throttler=self._throttler),
            "type": order_type_str,
        }
        if order_type is OrderType.LIMIT:
            data["price"] = str(price)
        elif order_type is OrderType.LIMIT_MAKER:
            data["price"] = str(price)
            data["postOnly"] = True
        exchange_order_id = await self._api_request(
            path_url=path_url,
            method=RESTMethod.POST,
            data=data,
            is_auth_required=True,
            limit_id=CONSTANTS.POST_ORDER_LIMIT_ID,
        )
        return str(exchange_order_id["data"]["orderId"])

    async def execute_buy(self,
                          order_id: str,
                          trading_pair: str,
                          amount: Decimal,
                          order_type: OrderType,
                          price: Decimal):
        trading_rule = self._trading_rules[trading_pair]

        if order_type is OrderType.LIMIT or order_type is OrderType.LIMIT_MAKER:
            decimal_amount = self.quantize_order_amount(trading_pair, amount)
            decimal_price = self.quantize_order_price(trading_pair, price)
            if decimal_amount < trading_rule.min_order_size:
                raise ValueError(f"Buy order amount {decimal_amount} is lower than the minimum order size "
                                 f"{trading_rule.min_order_size}.")
        try:
            self.start_tracking_order(
                client_order_id=order_id,
                exchange_order_id=None,
                trading_pair=trading_pair,
                order_type=order_type,
                trade_type=TradeType.BUY,
                price=decimal_price,
                amount=decimal_amount
            )
            exchange_order_id = await self.place_order(order_id, trading_pair, decimal_amount, True, order_type,
                                                       decimal_price)
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(f"Created {order_type} buy order {order_id} for {decimal_amount} {trading_pair}.")
                tracked_order.last_state = "DEAL"
                tracked_order.update_exchange_order_id(exchange_order_id)
                self.trigger_event(MarketEvent.BuyOrderCreated,
                                   BuyOrderCreatedEvent(
                                       self.current_timestamp,
                                       order_type,
                                       trading_pair,
                                       float(decimal_amount),
                                       float(decimal_price),
                                       order_id,
                                       tracked_order.creation_timestamp,
                                       exchange_order_id=tracked_order.exchange_order_id
                                   ))
        except asyncio.CancelledError:
            raise
        except Exception:
            self.stop_tracking_order(order_id)
            order_type_str = order_type.name.lower()
            self.logger().network(
                f"Error submitting buy {order_type_str} order to Kucoin for "
                f"{decimal_amount} {trading_pair} "
                f"{decimal_price}.",
                exc_info=True,
                app_warning_msg="Failed to submit buy order to Kucoin. Check API key and network connection."
            )
            self.trigger_event(MarketEvent.OrderFailure,
                               MarketOrderFailureEvent(self.current_timestamp, order_id, order_type))

    def buy(self, trading_pair: str, amount: Decimal, order_type=OrderType.MARKET,
            price: Decimal = s_decimal_NaN, **kwargs) -> str:

        order_id = get_new_client_order_id(
            is_buy=True, trading_pair=trading_pair, max_id_len=CONSTANTS.MAX_ORDER_ID_LEN
        )

        safe_ensure_future(self.execute_buy(order_id, trading_pair, amount, order_type, price))
        return order_id

    async def execute_sell(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           order_type: OrderType,
                           price: Decimal):
        trading_rule = self._trading_rules[trading_pair]

        decimal_amount = self.quantize_order_amount(trading_pair, amount)
        decimal_price = self.quantize_order_price(trading_pair, price)
        if decimal_amount < trading_rule.min_order_size:
            raise ValueError(f"Sell order amount {decimal_amount} is lower than the minimum order size "
                             f"{trading_rule.min_order_size}.")

        try:
            self.start_tracking_order(
                client_order_id=order_id,
                exchange_order_id=None,
                trading_pair=trading_pair,
                order_type=order_type,
                trade_type=TradeType.SELL,
                price=decimal_price,
                amount=decimal_amount
            )
            exchange_order_id = await self.place_order(order_id, trading_pair, decimal_amount, False, order_type,
                                                       decimal_price)
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(f"Created {order_type} sell order {order_id} for {decimal_amount} {trading_pair}.")
                tracked_order.last_state = "DEAL"
                tracked_order.update_exchange_order_id(exchange_order_id)
                self.trigger_event(MarketEvent.SellOrderCreated,
                                   SellOrderCreatedEvent(
                                       self.current_timestamp,
                                       order_type,
                                       trading_pair,
                                       float(decimal_amount),
                                       float(decimal_price),
                                       order_id,
                                       tracked_order.creation_timestamp,
                                       exchange_order_id=exchange_order_id
                                   ))
        except asyncio.CancelledError:
            raise
        except Exception:
            self.stop_tracking_order(order_id)
            order_type_str = order_type.name.lower()
            self.logger().network(
                f"Error submitting sell {order_type_str} order to Kucoin for "
                f"{decimal_amount} {trading_pair} "
                f"{decimal_price}.",
                exc_info=True,
                app_warning_msg="Failed to submit sell order to Kucoin. Check API key and network connection."
            )
            self.trigger_event(MarketEvent.OrderFailure,
                               MarketOrderFailureEvent(self.current_timestamp, order_id, order_type))

    def sell(self, trading_pair: str, amount: Decimal, order_type=OrderType.MARKET,
             price: Decimal = s_decimal_NaN, **kwargs) -> str:

        order_id = get_new_client_order_id(
                is_buy=False, trading_pair=trading_pair, max_id_len=CONSTANTS.MAX_ORDER_ID_LEN
            )
        safe_ensure_future(self.execute_sell(order_id, trading_pair, amount, order_type, price))
        return order_id

    async def execute_cancel(self, trading_pair: str, order_id: str):
        try:
            tracked_order: KucoinInFlightOrder = self._in_flight_orders.get(order_id)
            if tracked_order is None:
                raise ValueError(f"Failed to cancel order - {order_id}. Order not found.")
            if tracked_order.is_local:
                raise KucoinInFlightOrderNotCreated(
                    f"Failed to cancel order - {order_id}. Order not yet created."
                    f" This is most likely due to rate-limiting."
                )
            path_url = f"{CONSTANTS.ORDERS_PATH_URL}/{tracked_order.exchange_order_id}"
            await self._api_request(
                path_url=path_url,
                method=RESTMethod.DELETE,
                is_auth_required=True,
                limit_id=CONSTANTS.DELETE_ORDER_LIMIT_ID
            )
        except KucoinInFlightOrderNotCreated:
            raise
        except Exception as e:
            self.logger().network(
                f"Failed to cancel order {order_id}: {str(e)}",
                exc_info=True,
                app_warning_msg=f"Failed to cancel the order {order_id} on Kucoin. "
                                f"Check API key and network connection."
            )

    def cancel(self, trading_pair: str, client_order_id: str):
        safe_ensure_future(self.execute_cancel(trading_pair, client_order_id))
        return client_order_id

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        cancellation_results = []
        tracked_orders = {order.exchange_order_id: order for order in self._in_flight_orders.copy().values()}
        try:
            cancellation_tasks = []
            for oid, order in tracked_orders.items():
                cancellation_tasks.append(self._api_request(
                    path_url=f"{CONSTANTS.ORDERS_PATH_URL}/{oid}",
                    method=RESTMethod.DELETE,
                    is_auth_required=True,
                    limit_id=CONSTANTS.DELETE_ORDER_LIMIT_ID,
                ))
            responses = await safe_gather(*cancellation_tasks)

            for tracked_order, response in zip(tracked_orders.values(), responses):
                # Handle failed cancelled orders
                if isinstance(response, Exception) or "data" not in response:
                    self.logger().error(f"Failed to cancel order {tracked_order.client_order_id}. Response: {response}",
                                        exc_info=True,
                                        )
                    cancellation_results.append(CancellationResult(tracked_order.client_order_id, False))
                # Handles successfully cancelled orders
                elif tracked_order.exchange_order_id == response['data']['cancelledOrderIds'][0]:
                    if tracked_order.client_order_id in self._in_flight_orders:
                        tracked_order.last_state = "CANCEL"
                        self.logger().info(f"Successfully cancelled order {tracked_order.client_order_id}.")
                        self.trigger_event(MarketEvent.OrderCancelled,
                                           OrderCancelledEvent(self.current_timestamp,
                                                               tracked_order.client_order_id,
                                                               exchange_order_id=tracked_order.exchange_order_id))
                        self.stop_tracking_order(tracked_order.client_order_id)
                    cancellation_results.append(CancellationResult(tracked_order.client_order_id, True))
                else:
                    continue

        except Exception:
            self.logger().network(
                "Failed to cancel all orders.",
                exc_info=True,
                app_warning_msg="Failed to cancel all orders on Kucoin. Check API key and network connection."
            )
        return cancellation_results

    def get_order_book(self, trading_pair: str) -> OrderBook:
        """
        Returns the current order book for a particular market

        :param trading_pair: the pair of tokens for which the order book should be retrieved
        """
        if trading_pair not in self._order_book_tracker.order_books:
            raise ValueError(f"No order book exists for '{trading_pair}'.")
        return self._order_book_tracker.order_books[trading_pair]

    def start_tracking_order(self,
                             client_order_id: str,
                             exchange_order_id: Optional[str],
                             trading_pair: str,
                             order_type: OrderType,
                             trade_type: TradeType,
                             price: Decimal,
                             amount: Decimal):
        self._in_flight_orders[client_order_id] = KucoinInFlightOrder(
            client_order_id=client_order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=trading_pair,
            order_type=order_type,
            trade_type=trade_type,
            price=price,
            amount=amount,
            creation_timestamp=self.current_timestamp
        )

    def stop_tracking_order(self, order_id: str):
        if order_id in self._in_flight_orders:
            del self._in_flight_orders[order_id]

    def get_order_price_quantum(self, trading_pair: str, price: Decimal) -> Decimal:
        """
        Used by quantize_order_price() in _create_order()
        Returns a price step, a minimum price increment for a given trading pair.

        :param trading_pair: the trading pair to check for market conditions
        :param price: the starting point price
        """
        trading_rule = self._trading_rules[trading_pair]
        return trading_rule.min_price_increment

    def get_order_size_quantum(self, trading_pair: str, order_size: Decimal) -> Decimal:
        """
        Used by quantize_order_price() in _create_order()
        Returns an order amount step, a minimum amount increment for a given trading pair.

        :param trading_pair: the trading pair to check for market conditions
        :param order_size: the starting point order price
        """
        trading_rule = self._trading_rules[trading_pair]
        return Decimal(trading_rule.min_base_amount_increment)

    def quantize_order_amount(self, trading_pair: str, amount: Decimal, price: Decimal = s_decimal_0) -> Decimal:
        """
        Applies the trading rules to calculate the correct order amount for the market
        :param trading_pair: the token pair for which the order will be created
        :param amount: the intended amount for the order
        :param price: the intended price for the order
        :return: the quantized order amount after applying the trading rules
        """
        trading_rule = self._trading_rules[trading_pair]
        quantized_amount: Decimal = super().quantize_order_amount(trading_pair, amount)

        # Check against min_order_size and min_notional_size. If not passing either check, return 0.
        if quantized_amount < trading_rule.min_order_size:
            return s_decimal_0

        if price == s_decimal_0:
            current_price: Decimal = self.get_price(trading_pair, False)
            notional_size = current_price * quantized_amount
        else:
            notional_size = price * quantized_amount

        # Add 1% as a safety factor in case the prices changed while making the order.
        if notional_size < trading_rule.min_notional_size * Decimal("1.01"):
            return s_decimal_0

        return quantized_amount

    def get_fee(self,
                base_currency: str,
                quote_currency: str,
                order_type: OrderType,
                order_side: TradeType,
                amount: Decimal,
                price: Decimal = s_decimal_NaN,
                is_maker: Optional[bool] = None) -> AddedToCostTradeFee:

        is_maker = is_maker or (order_type is OrderType.LIMIT_MAKER)
        trading_pair = f"{base_currency}-{quote_currency}"
        if trading_pair in self._trading_fees:
            fees_data = self._trading_fees[trading_pair]
            fee_value = Decimal(fees_data["makerFeeRate"]) if is_maker else Decimal(fees_data["takerFeeRate"])
            fee = AddedToCostTradeFee(percent=fee_value)
        else:
            safe_ensure_future(self._update_trading_fee(trading_pair))
            fee = build_trade_fee(
                self.name,
                is_maker,
                base_currency=base_currency,
                quote_currency=quote_currency,
                order_type=order_type,
                order_side=order_side,
                amount=amount,
                price=price,
            )
        return fee
