import asyncio
import json
import logging
import time

from decimal import Decimal
from typing import (
    Any,
    AsyncIterable,
    Callable,
    Coroutine,
    Dict,
    List,
    Optional,
)

from async_timeout import timeout

import hummingbot.connector.exchange.binance.binance_constants as CONSTANTS
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.connector.exchange.binance import binance_utils
from hummingbot.connector.exchange.binance.binance_api_order_book_data_source import BinanceAPIOrderBookDataSource
from hummingbot.connector.exchange.binance.binance_auth import BinanceAuth
from hummingbot.connector.exchange.binance.binance_in_flight_order import BinanceInFlightOrder
from hummingbot.connector.exchange.binance.binance_order_book_tracker import BinanceOrderBookTracker
from hummingbot.connector.exchange.binance.binance_time import BinanceTime
from hummingbot.connector.exchange.binance.binance_user_stream_tracker import BinanceUserStreamTracker
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import build_api_factory
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.clock import Clock
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.common import OpenOrder
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.trade import Trade
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
    TradeFee,
    TradeType,
)
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils import async_ttl_cache
from hummingbot.core.utils.async_call_scheduler import AsyncCallScheduler
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from hummingbot.core.utils.estimate_fee import estimate_fee
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest
from hummingbot.core.web_assistant.rest_assistant import RESTAssistant
from hummingbot.logger import HummingbotLogger

s_logger = None
s_decimal_0 = Decimal(0)
s_decimal_NaN = Decimal("nan")


class BinanceExchange(ExchangeBase):
    API_CALL_TIMEOUT = 10.0
    SHORT_POLL_INTERVAL = 5.0
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0
    LONG_POLL_INTERVAL = 120.0

    MAX_ORDER_UPDATE_RETRIEVAL_RETRIES_WITH_FAILURES = 3

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(__name__)
        return s_logger

    def __init__(self,
                 binance_api_key: str,
                 binance_api_secret: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True,
                 domain="com"
                 ):
        self._domain = domain
        self._binance_time_synchronizer = BinanceTime()
        super().__init__()
        self._trading_required = trading_required
        self._auth = BinanceAuth(api_key=binance_api_key, secret_key=binance_api_secret)
        self._api_factory = build_api_factory()
        self._rest_assistant = None
        self._throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        self._order_book_tracker = BinanceOrderBookTracker(
            trading_pairs=trading_pairs,
            domain=domain,
            api_factory=self._api_factory,
            throttler=self._throttler)
        self._user_stream_tracker = BinanceUserStreamTracker(auth=self._auth, domain=domain, throttler=self._throttler)
        self._ev_loop = asyncio.get_event_loop()
        self._poll_notifier = asyncio.Event()
        self._last_timestamp = 0
        self._in_flight_orders = {}  # Dict[client_order_id:str, BinanceInFlightOrder]
        self._order_not_found_records = {}  # Dict[client_order_id:str, count:int]
        self._trading_rules = {}  # Dict[trading_pair:str, TradingRule]
        self._trade_fees = {}  # Dict[trading_pair:str, (maker_fee_percent:Decimal, taken_fee_percent:Decimal)]
        self._last_update_trade_fees_timestamp = 0
        self._status_polling_task = None
        self._user_stream_event_listener_task = None
        self._trading_rules_polling_task = None
        self._async_scheduler = AsyncCallScheduler(call_interval=0.5)
        self._last_poll_timestamp = 0

    @property
    def name(self) -> str:
        if self._domain == "com":
            return "binance"
        else:
            return f"binance_{self._domain}"

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        return self._order_book_tracker.order_books

    @property
    def trading_rules(self) -> Dict[str, TradingRule]:
        return self._trading_rules

    @property
    def in_flight_orders(self) -> Dict[str, BinanceInFlightOrder]:
        return self._in_flight_orders

    @property
    def limit_orders(self) -> List[LimitOrder]:
        return [
            in_flight_order.to_limit_order()
            for in_flight_order in self._in_flight_orders.values()
        ]

    @property
    def tracking_states(self) -> Dict[str, any]:
        return {
            key: value.to_json()
            for key, value in self._in_flight_orders.items()
        }

    @property
    def order_book_tracker(self) -> BinanceOrderBookTracker:
        return self._order_book_tracker

    @property
    def user_stream_tracker(self) -> BinanceUserStreamTracker:
        return self._user_stream_tracker

    def restore_tracking_states(self, saved_states: Dict[str, any]):
        self._in_flight_orders.update({
            key: BinanceInFlightOrder.from_json(value)
            for key, value in saved_states.items()
        })

    async def schedule_async_call(
            self,
            coro: Coroutine,
            timeout_seconds: float,
            app_warning_msg: str = "Binance API call failed. Check API key and network connection.") -> any:
        return await self._async_scheduler.schedule_async_call(coro, timeout_seconds, app_warning_msg=app_warning_msg)

    @property
    def status_dict(self) -> Dict[str, bool]:
        return {
            "order_books_initialized": self._order_book_tracker.ready,
            "account_balance": len(self._account_balances) > 0 if self._trading_required else True,
            "trading_rule_initialized": len(self._trading_rules) > 0,
        }

    @property
    def ready(self) -> bool:
        return all(self.status_dict.values())

    def stop(self, clock: Clock):
        self._async_scheduler.stop()
        super().stop()

    async def start_network(self):
        self._order_book_tracker.start()
        self._trading_rules_polling_task = safe_ensure_future(self._trading_rules_polling_loop())
        if self._trading_required:
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())
            self._user_stream_tracker_task = safe_ensure_future(self._user_stream_tracker.start())
            self._user_stream_event_listener_task = safe_ensure_future(self._user_stream_event_listener())

    async def stop_network(self):
        self._stop_network()

    async def check_network(self) -> NetworkStatus:
        try:
            await self._api_request(
                method="get",
                path_url=CONSTANTS.PING_PATH_URL,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    def tick(self, timestamp: float):
        now = time.time()
        poll_interval = (self.SHORT_POLL_INTERVAL
                         if now - self.user_stream_tracker.last_recv_time > 60.0
                         else self.LONG_POLL_INTERVAL)
        last_tick = int(self._last_timestamp / poll_interval)
        current_tick = int(timestamp / poll_interval)

        if current_tick > last_tick:
            if not self._poll_notifier.is_set():
                self._poll_notifier.set()
        self._last_timestamp = timestamp

    async def execute_buy(self,
                          order_id: str,
                          trading_pair: str,
                          amount: Decimal,
                          order_type: OrderType,
                          price: Optional[Decimal] = s_decimal_NaN):
        return await self.create_order(TradeType.BUY, order_id, trading_pair, amount, order_type, price)

    def buy(self, trading_pair: str, amount: Decimal, order_type: OrderType = OrderType.MARKET,
            price: Decimal = s_decimal_NaN, **kwargs) -> str:
        new_order_id = binance_utils.get_new_client_order_id(is_buy=True, trading_pair=trading_pair)
        safe_ensure_future(self.execute_buy(new_order_id, trading_pair, amount, order_type, price))
        return new_order_id

    async def _api_request(self,
                           method,
                           path_url,
                           params: Optional[Dict[str, Any]] = None,
                           data=None,
                           is_auth_required: bool = False) -> Dict[str, Any]:

        headers = {}
        client = await self._get_rest_assistant()

        if is_auth_required:
            url = binance_utils.private_rest_url(path_url, domain=self._domain)
            headers = self._auth.get_auth_headers(request_type=method)
            params = self._auth.add_auth_to_params(params, current_time=self._binance_time_synchronizer.time())
        else:
            url = binance_utils.public_rest_url(path_url, domain=self._domain)
            headers = self._auth.get_headers(request_type=method)

        request = RESTRequest(method=RESTMethod[method.upper()],
                              url=url,
                              data=json.dumps(data) if data else None,
                              params=params,
                              headers=headers,
                              is_auth_required=is_auth_required)

        async with self._throttler.execute_task(limit_id=path_url):
            response = await client.call(request)

            if response.status != 200:
                raise IOError(f"Error fetching data from {url}. HTTP status is {response.status}.")
            try:
                parsed_response = await response.json()
            except Exception:
                raise IOError(f"Error parsing data from {response}.")

            if "code" in parsed_response and "msg" in parsed_response:
                raise IOError(f"The request to Binance failed. Error: {parsed_response}. Request: {request}")

        return parsed_response

    async def _update_balances(self):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        try:
            account_info = await self._api_request(
                method="get",
                path_url=CONSTANTS.ACCOUNTS_PATH_URL,
                is_auth_required=True)

            balances = account_info["balances"]
            for balance_entry in balances:
                asset_name = balance_entry["asset"]
                free_balance = Decimal(balance_entry["free"])
                total_balance = Decimal(balance_entry["free"]) + Decimal(balance_entry["locked"])
                self._account_available_balances[asset_name] = free_balance
                self._account_balances[asset_name] = total_balance
                remote_asset_names.add(asset_name)

            asset_names_to_remove = local_asset_names.difference(remote_asset_names)
            for asset_name in asset_names_to_remove:
                del self._account_available_balances[asset_name]
                del self._account_balances[asset_name]
        except IOError:
            self.logger().exception("Error getting account balances from server")

    def get_fee(self,
                base_currency: str,
                quote_currency: str,
                order_type: OrderType,
                order_side: TradeType,
                amount: Decimal,
                price: Decimal = s_decimal_NaN) -> TradeFee:

        is_maker = order_type is OrderType.LIMIT_MAKER
        return estimate_fee(self.name, is_maker)

    async def _update_trading_rules(self):
        exchange_info = await self._api_request(
            method="get",
            path_url=CONSTANTS.EXCHANGE_INFO_PATH_URL)
        trading_rules_list = await self._format_trading_rules(exchange_info)
        self._trading_rules.clear()
        for trading_rule in trading_rules_list:
            self._trading_rules[trading_rule.trading_pair] = trading_rule

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        """
        Example:
        {
            "symbol": "ETHBTC",
            "baseAssetPrecision": 8,
            "quotePrecision": 8,
            "orderTypes": ["LIMIT", "MARKET"],
            "filters": [
                {
                    "filterType": "PRICE_FILTER",
                    "minPrice": "0.00000100",
                    "maxPrice": "100000.00000000",
                    "tickSize": "0.00000100"
                }, {
                    "filterType": "LOT_SIZE",
                    "minQty": "0.00100000",
                    "maxQty": "100000.00000000",
                    "stepSize": "0.00100000"
                }, {
                    "filterType": "MIN_NOTIONAL",
                    "minNotional": "0.00100000"
                }
            ]
        }
        """
        trading_pair_rules = exchange_info_dict.get("symbols", [])
        retval = []
        for rule in filter(binance_utils.is_exchange_information_valid, trading_pair_rules):
            try:
                trading_pair = await BinanceAPIOrderBookDataSource.trading_pair_associated_to_exchange_symbol(
                    rule.get("symbol"))
                filters = rule.get("filters")
                price_filter = [f for f in filters if f.get("filterType") == "PRICE_FILTER"][0]
                lot_size_filter = [f for f in filters if f.get("filterType") == "LOT_SIZE"][0]
                min_notional_filter = [f for f in filters if f.get("filterType") == "MIN_NOTIONAL"][0]

                min_order_size = Decimal(lot_size_filter.get("minQty"))
                tick_size = price_filter.get("tickSize")
                step_size = Decimal(lot_size_filter.get("stepSize"))
                min_notional = Decimal(min_notional_filter.get("minNotional"))

                retval.append(
                    TradingRule(trading_pair,
                                min_order_size=min_order_size,
                                min_price_increment=Decimal(tick_size),
                                min_base_amount_increment=Decimal(step_size),
                                min_notional_size=Decimal(min_notional)))

            except Exception:
                self.logger().exception(f"Error parsing the trading pair rule {rule}. Skipping.")
        return retval

    async def _update_order_fills_from_trades(self):
        # This is intended to be a backup measure to get filled events with trade ID for orders,
        # in case Binance's user stream events are not working.
        # This is separated from _update_order_status which only updates the order status without producing filled
        # events, since Binance's get order endpoint does not return trade IDs.
        # The minimum poll interval for order status is 10 seconds.
        small_interval_last_tick = self._last_poll_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL
        small_interval_current_tick = self.current_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL
        long_interval_last_tick = self._last_poll_timestamp / self.LONG_POLL_INTERVAL
        long_interval_current_tick = self.current_timestamp / self.LONG_POLL_INTERVAL

        if (long_interval_current_tick > long_interval_last_tick
                or (self.in_flight_orders and small_interval_current_tick > small_interval_last_tick)):

            order_by_exchange_id_map = {}
            for order in self._in_flight_orders.values():
                order_by_exchange_id_map[order.exchange_order_id] = order

            trading_pairs = self._order_book_tracker._trading_pairs
            tasks = [self._api_request(
                method="get",
                path_url=CONSTANTS.MY_TRADES_PATH_URL,
                params={
                    "symbol": await BinanceAPIOrderBookDataSource.exchange_symbol_associated_to_pair(trading_pair)},
                is_auth_required=True)
                for trading_pair in trading_pairs]
            self.logger().debug(f"Polling for order fills of {len(tasks)} trading pairs.")
            results = await safe_gather(*tasks, return_exceptions=True)

            for trades, trading_pair in zip(results, trading_pairs):

                if isinstance(trades, Exception):
                    self.logger().network(
                        f"Error fetching trades update for the order {trading_pair}: {trades}.",
                        app_warning_msg=f"Failed to fetch trade update for {trading_pair}."
                    )
                    continue
                for trade in trades:
                    exchange_order_id = str(trade["orderId"])
                    if exchange_order_id in order_by_exchange_id_map:
                        # This is a fill for a tracked order
                        tracked_order = order_by_exchange_id_map[exchange_order_id]
                        order_type = tracked_order.order_type
                        applied_trade = tracked_order.update_with_trade_update(trade)
                        if applied_trade:
                            self.trigger_event(
                                MarketEvent.OrderFilled,
                                OrderFilledEvent(
                                    self.current_timestamp,
                                    tracked_order.client_order_id,
                                    tracked_order.trading_pair,
                                    tracked_order.trade_type,
                                    order_type,
                                    Decimal(trade["price"]),
                                    Decimal(trade["qty"]),
                                    TradeFee(
                                        percent=Decimal(0.0),
                                        flat_fees=[(trade["commissionAsset"],
                                                    Decimal(trade["commission"]))]
                                    ),
                                    exchange_trade_id=trade["id"]
                                ))
                    elif self.is_confirmed_new_order_filled_event(str(trade["id"]), exchange_order_id, trading_pair):
                        # This is a fill of an order registered in the DB but not tracked any more
                        self.trigger_event(
                            MarketEvent.OrderFilled,
                            OrderFilledEvent(
                                float(trade["time"]) * 1e-3,
                                self._exchange_order_ids.get(str(trade["orderId"]), None),
                                trading_pair,
                                TradeType.BUY if trade["isBuyer"] else TradeType.SELL,
                                OrderType.LIMIT_MAKER if trade["isMaker"] else OrderType.LIMIT,
                                # defaulting to this value since trade info lacks field
                                Decimal(trade["price"]),
                                Decimal(trade["qty"]),
                                TradeFee(
                                    percent=Decimal(0.0),
                                    flat_fees=[(trade["commissionAsset"],
                                                Decimal(trade["commission"]))]
                                ),
                                exchange_trade_id=trade["id"]
                            ))
                        self.logger().info(f"Recreating missing trade in TradeFill: {trade}")

    async def _update_order_status(self):
        # This is intended to be a backup measure to close straggler orders, in case Binance's user stream events
        # are not working.
        # The minimum poll interval for order status is 10 seconds.
        last_tick = self._last_poll_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL
        current_tick = self.current_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL

        if current_tick > last_tick and len(self._in_flight_orders) > 0:
            tracked_orders = list(self._in_flight_orders.values())

            tasks = [self._api_request(
                method="get",
                path_url=CONSTANTS.ORDER_PATH_URL,
                params={
                    "symbol": await BinanceAPIOrderBookDataSource.exchange_symbol_associated_to_pair(o.trading_pair),
                    "origClientOrderId": o.client_order_id},
                is_auth_required=True) for o in tracked_orders]
            self.logger().debug(f"Polling for order status updates of {len(tasks)} orders.")
            results = await safe_gather(*tasks, return_exceptions=True)
            for order_update, tracked_order in zip(results, tracked_orders):
                client_order_id = tracked_order.client_order_id

                # If the order has already been cancelled or has failed do nothing
                if client_order_id not in self._in_flight_orders:
                    continue

                if isinstance(order_update, Exception):
                    self.logger().network(
                        f"Error fetching status update for the order {client_order_id}: {order_update}.",
                        app_warning_msg=f"Failed to fetch status update for the order {client_order_id}."
                    )
                    self._order_not_found_records[client_order_id] = (
                        self._order_not_found_records.get(client_order_id, 0) + 1)
                    if (self._order_not_found_records[client_order_id] >=
                            self.MAX_ORDER_UPDATE_RETRIEVAL_RETRIES_WITH_FAILURES):
                        # Wait until the order not found error have repeated a few times before actually treating
                        # it as failed. See: https://github.com/CoinAlpha/hummingbot/issues/601

                        self.trigger_event(
                            MarketEvent.OrderFailure,
                            MarketOrderFailureEvent(self.current_timestamp, client_order_id, tracked_order.order_type)
                        )
                        self.stop_tracking_order(client_order_id)

                else:
                    # Update order execution status
                    tracked_order.last_state = order_update["status"]

                    if tracked_order.is_cancelled:
                        exchange_order_id = await tracked_order.get_exchange_order_id()
                        self.logger().info(f"Successfully cancelled order {client_order_id}.")
                        self.trigger_event(MarketEvent.OrderCancelled,
                                           OrderCancelledEvent(
                                               self.current_timestamp,
                                               client_order_id,
                                               exchange_order_id=exchange_order_id))
                        self.stop_tracking_order(client_order_id)
                    elif tracked_order.is_failure:
                        self.logger().info(f"The market order {client_order_id} has failed according to "
                                           f"order status API.")
                        self.trigger_event(MarketEvent.OrderFailure,
                                           MarketOrderFailureEvent(
                                               self.current_timestamp,
                                               client_order_id,
                                               tracked_order.order_type
                                           ))
                        self.stop_tracking_order(client_order_id)
                    elif tracked_order.is_done:
                        exchange_order_id = await tracked_order.get_exchange_order_id()
                        executed_amount_base = Decimal(order_update["executedQty"])
                        executed_amount_quote = Decimal(order_update["cummulativeQuoteQty"])
                        event_tag = (MarketEvent.BuyOrderCompleted if tracked_order.trade_type is TradeType.BUY
                                     else MarketEvent.SellOrderCompleted)
                        event_class: Callable = (BuyOrderCompletedEvent if tracked_order.trade_type is TradeType.BUY
                                                 else SellOrderCompletedEvent)
                        alternative_fee_asset = (tracked_order.base_asset if tracked_order.trade_type is TradeType.BUY
                                                 else tracked_order.quote_asset)

                        self.logger().info(f"The market {tracked_order.trade_type.name.lower()} order "
                                           f"{tracked_order.client_order_id} has completed according to "
                                           f"order status API.")
                        self.trigger_event(
                            event_tag,
                            event_class(self.current_timestamp,
                                        client_order_id,
                                        tracked_order.base_asset,
                                        tracked_order.quote_asset,
                                        (tracked_order.fee_asset or alternative_fee_asset),
                                        executed_amount_base,
                                        executed_amount_quote,
                                        tracked_order.fee_paid,
                                        tracked_order.order_type,
                                        exchange_order_id=exchange_order_id))

                        self.stop_tracking_order(client_order_id)

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
                event_type = event_message.get("e")
                # Refer to https://github.com/binance-exchange/binance-official-api-docs/blob/master/user-data-stream.md
                # As per the order update section in Binance the ID of the order being cancelled is under the "C" key
                if event_type == "executionReport":
                    execution_type = event_message.get("x")
                    if execution_type != "CANCELED":
                        client_order_id = event_message.get("c")
                    else:
                        client_order_id = event_message.get("C")

                    tracked_order = self._in_flight_orders.get(client_order_id)

                    if tracked_order is None:
                        # Hiding the messages for now. Root cause to be investigated in later sprints.
                        self.logger().debug(f"Unrecognized order ID from user stream: {client_order_id}.")
                        self.logger().debug(f"Event: {event_message}")
                        continue

                    unique_update = tracked_order.update_with_execution_report(event_message)

                    if execution_type == "TRADE":
                        order_filled_event = OrderFilledEvent.order_filled_event_from_binance_execution_report(
                            event_message)
                        order_filled_event = order_filled_event._replace(
                            trading_pair=await BinanceAPIOrderBookDataSource.trading_pair_associated_to_exchange_symbol(
                                order_filled_event.trading_pair))
                        if unique_update:
                            self.trigger_event(MarketEvent.OrderFilled, order_filled_event)

                    if tracked_order.is_done:
                        if not tracked_order.is_failure:
                            if tracked_order.trade_type is TradeType.BUY:
                                self.logger().info(
                                    f"The market buy order {tracked_order.client_order_id} has completed "
                                    f"according to user stream.")
                                self.trigger_event(MarketEvent.BuyOrderCompleted,
                                                   BuyOrderCompletedEvent(self.current_timestamp,
                                                                          tracked_order.client_order_id,
                                                                          tracked_order.base_asset,
                                                                          tracked_order.quote_asset,
                                                                          (tracked_order.fee_asset
                                                                           or tracked_order.base_asset),
                                                                          tracked_order.executed_amount_base,
                                                                          tracked_order.executed_amount_quote,
                                                                          tracked_order.fee_paid,
                                                                          tracked_order.order_type))
                            else:
                                self.logger().info(
                                    f"The market sell order {tracked_order.client_order_id} has completed "
                                    f"according to user stream.")
                                self.trigger_event(MarketEvent.SellOrderCompleted,
                                                   SellOrderCompletedEvent(self.current_timestamp,
                                                                           tracked_order.client_order_id,
                                                                           tracked_order.base_asset,
                                                                           tracked_order.quote_asset,
                                                                           (tracked_order.fee_asset
                                                                            or tracked_order.quote_asset),
                                                                           tracked_order.executed_amount_base,
                                                                           tracked_order.executed_amount_quote,
                                                                           tracked_order.fee_paid,
                                                                           tracked_order.order_type))
                        else:
                            # check if its a cancelled order
                            # if its a cancelled order, check in flight orders
                            # if present in in flight orders issue cancel and stop tracking order
                            if tracked_order.is_cancelled:
                                if tracked_order.client_order_id in self._in_flight_orders:
                                    self.logger().info(f"Successfully cancelled order {tracked_order.client_order_id}.")
                                    self.trigger_event(MarketEvent.OrderCancelled,
                                                       OrderCancelledEvent(
                                                           self.current_timestamp,
                                                           tracked_order.client_order_id))
                            else:
                                self.logger().info(
                                    f"The market order {tracked_order.client_order_id} has failed according to "
                                    f"order status API.")
                                self.trigger_event(MarketEvent.OrderFailure,
                                                   MarketOrderFailureEvent(
                                                       self.current_timestamp,
                                                       tracked_order.client_order_id,
                                                       tracked_order.order_type
                                                   ))
                        self.stop_tracking_order(tracked_order.client_order_id)

                elif event_type == "outboundAccountPosition":
                    balances = event_message["B"]
                    for balance_entry in balances:
                        asset_name = balance_entry["a"]
                        free_balance = Decimal(balance_entry["f"])
                        total_balance = Decimal(balance_entry["f"]) + Decimal(balance_entry["l"])
                        self._account_available_balances[asset_name] = free_balance
                        self._account_balances[asset_name] = total_balance

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await asyncio.sleep(5.0)

    async def _status_polling_loop(self):
        while True:
            try:
                await self._poll_notifier.wait()
                await safe_gather(
                    self._update_balances(),
                    self._update_order_fills_from_trades(),
                    self._update_time_synchronizer(),
                )
                await self._update_order_status()
                self._last_poll_timestamp = self.current_timestamp
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network("Unexpected error while fetching account updates.", exc_info=True,
                                      app_warning_msg="Could not fetch account updates from Binance. "
                                                      "Check API key and network connection.")
                await asyncio.sleep(0.5)
            finally:
                self._poll_notifier = asyncio.Event()

    async def _trading_rules_polling_loop(self):
        while True:
            try:
                await safe_gather(
                    self._update_trading_rules(),
                )
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network("Unexpected error while fetching trading rules.", exc_info=True,
                                      app_warning_msg="Could not fetch new trading rules from Binance. "
                                                      "Check network connection.")
                await asyncio.sleep(0.5)

    def _stop_network(self):
        # Reset timestamps and _poll_notifier for status_polling_loop
        self._last_poll_timestamp = 0
        self._last_timestamp = 0
        self._poll_notifier = asyncio.Event()

        self._order_book_tracker.stop()
        if self._status_polling_task is not None:
            self._status_polling_task.cancel()
        if self._user_stream_tracker_task is not None:
            self._user_stream_tracker_task.cancel()
        if self._user_stream_event_listener_task is not None:
            self._user_stream_event_listener_task.cancel()
        if self._trading_rules_polling_task is not None:
            self._trading_rules_polling_task.cancel()
        self._status_polling_task = self._user_stream_tracker_task = self._user_stream_event_listener_task = None

    @staticmethod
    def binance_order_type(order_type: OrderType) -> str:
        return order_type.name.upper()

    @staticmethod
    def to_hb_order_type(binance_type: str) -> OrderType:
        return OrderType[binance_type]

    def supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER]

    async def create_order(self,
                           trade_type: TradeType,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           order_type: OrderType,
                           price: Optional[Decimal] = Decimal("NaN")):

        trading_rule: TradingRule = self._trading_rules[trading_pair]
        price = self.quantize_order_price(trading_pair, price)
        quantize_amount_price = Decimal("0") if price.is_nan() else price
        amount = self.quantize_order_amount(trading_pair=trading_pair, amount=amount, price=quantize_amount_price)

        if amount < trading_rule.min_order_size:
            self.logger().warning(f"Buy order amount {amount} is lower than the minimum order size "
                                  f"{trading_rule.min_order_size}. The order will not be created.")
            return

        order_result = None
        amount_str = f"{amount:f}"
        price_str = f"{price:f}"
        type_str = BinanceExchange.binance_order_type(order_type)
        side_str = CONSTANTS.SIDE_BUY if trade_type is TradeType.BUY else CONSTANTS.SIDE_SELL
        symbol = await BinanceAPIOrderBookDataSource.exchange_symbol_associated_to_pair(trading_pair)
        api_params = {"symbol": symbol,
                      "side": side_str,
                      "quantity": amount_str,
                      "type": type_str,
                      "newClientOrderId": order_id,
                      "price": price_str}
        if order_type == OrderType.LIMIT:
            api_params["timeInForce"] = CONSTANTS.TIME_IN_FORCE_GTC
        self.start_tracking_order(order_id,
                                  "",
                                  trading_pair,
                                  trade_type,
                                  price,
                                  amount,
                                  order_type
                                  )
        try:
            order_result = await self._api_request(
                method="post",
                path_url=CONSTANTS.ORDER_PATH_URL,
                data=api_params,
                is_auth_required=True)
            exchange_order_id = str(order_result["orderId"])
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(f"Created {type_str} {side_str} order {order_id} for "
                                   f"{amount} {trading_pair}.")
                tracked_order.exchange_order_id = exchange_order_id

            event_tag = MarketEvent.BuyOrderCreated if trade_type is TradeType.BUY \
                else MarketEvent.SellOrderCreated
            event_class: Callable = BuyOrderCreatedEvent if trade_type is TradeType.BUY else SellOrderCreatedEvent
            self.trigger_event(event_tag,
                               event_class(
                                   self.current_timestamp,
                                   order_type,
                                   trading_pair,
                                   amount,
                                   price,
                                   order_id,
                                   exchange_order_id
                               ))
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(
                f"Error submitting {side_str} {type_str} order to Binance for "
                f"{amount} {trading_pair} "
                f"{price}.",
                exc_info=True,
                app_warning_msg=str(e)
            )
            self.stop_tracking_order(order_id)
            self.trigger_event(MarketEvent.OrderFailure,
                               MarketOrderFailureEvent(self.current_timestamp, order_id, order_type))

    async def execute_sell(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           order_type: OrderType,
                           price: Optional[Decimal] = Decimal("NaN")):
        return await self.create_order(TradeType.SELL, order_id, trading_pair, amount, order_type, price)

    def sell(self, trading_pair: str, amount: Decimal, order_type: OrderType = OrderType.MARKET,
             price: Decimal = s_decimal_NaN, **kwargs) -> str:
        order_id = binance_utils.get_new_client_order_id(is_buy=False, trading_pair=trading_pair)
        safe_ensure_future(self.execute_sell(order_id, trading_pair, amount, order_type, price))
        return order_id

    async def execute_cancel(self, trading_pair: str, order_id: str):
        if order_id in self.in_flight_orders:
            try:
                symbol = await BinanceAPIOrderBookDataSource.exchange_symbol_associated_to_pair(trading_pair)
                api_params = {
                    "symbol": symbol,
                    "origClientOrderId": order_id,
                }
                cancel_result = await self._api_request(
                    method="delete",
                    path_url=CONSTANTS.ORDER_PATH_URL,
                    params=api_params,
                    is_auth_required=True)

                if cancel_result.get("status") == "CANCELED":
                    self.logger().info(f"Successfully cancelled order {order_id}.")
                    self.stop_tracking_order(order_id)
                    self.trigger_event(MarketEvent.OrderCancelled,
                                       OrderCancelledEvent(self.current_timestamp, order_id))
                return cancel_result

            except asyncio.CancelledError:
                raise
            except IOError as error:
                self.logger().warning(f"The order {order_id} could not be cancelled ({error})")
                if order_id not in self.in_flight_orders:
                    self.trigger_event(MarketEvent.OrderFailure,
                                       MarketOrderFailureEvent(self.current_timestamp, order_id, OrderType.LIMIT))
                else:
                    raise
            except Exception:
                self.logger().exception(f"There was a an error when requesting cancellation of order {order_id}")
                raise

    def cancel(self, trading_pair: str, order_id: str):
        safe_ensure_future(self.execute_cancel(trading_pair, order_id))
        return order_id

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        incomplete_orders = [o for o in self._in_flight_orders.values() if not o.is_done]
        tasks = [self.execute_cancel(o.trading_pair, o.client_order_id) for o in incomplete_orders]
        order_id_set = set([o.client_order_id for o in incomplete_orders])
        successful_cancellations = []

        try:
            async with timeout(timeout_seconds):
                cancellation_results = await safe_gather(*tasks, return_exceptions=True)
                for cr in cancellation_results:
                    if isinstance(cr, Exception):
                        continue
                    if isinstance(cr, dict) and "origClientOrderId" in cr:
                        client_order_id = cr.get("origClientOrderId")
                        order_id_set.remove(client_order_id)
                        successful_cancellations.append(CancellationResult(client_order_id, True))
        except Exception:
            self.logger().network(
                "Unexpected error cancelling orders.",
                exc_info=True,
                app_warning_msg="Failed to cancel order with Binance. Check API key and network connection."
            )

        failed_cancellations = [CancellationResult(oid, False) for oid in order_id_set]
        return successful_cancellations + failed_cancellations

    def get_order_book(self, trading_pair: str) -> OrderBook:
        if trading_pair not in self._order_book_tracker.order_books:
            raise ValueError(f"No order book exists for '{trading_pair}'.")
        return self._order_book_tracker.order_books[trading_pair]

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
        self._in_flight_orders[order_id] = BinanceInFlightOrder(
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

    def quantize_order_amount(self, trading_pair: str, amount: Decimal, price: Decimal = s_decimal_0) -> Decimal:
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

    async def get_open_orders(self) -> List[OpenOrder]:
        orders = await self._api_request(
            method="get",
            path_url=CONSTANTS.OPEN_ORDERS_PATH_URL,
            is_auth_required=True)
        ret_val = []
        for order in orders:
            if CONSTANTS.HBOT_ORDER_ID_PREFIX in order["clientOrderId"]:
                ret_val.append(
                    OpenOrder(
                        client_order_id=order["clientOrderId"],
                        trading_pair=await BinanceAPIOrderBookDataSource.trading_pair_associated_to_exchange_symbol(
                            order["symbol"]),
                        price=Decimal(str(order["price"])),
                        amount=Decimal(str(order["origQty"])),
                        executed_amount=Decimal(str(order["executedQty"])),
                        status=order["status"],
                        order_type=self.to_hb_order_type(order["type"]),
                        is_buy=True if order["side"].lower() == "buy" else False,
                        time=int(order["time"]),
                        exchange_order_id=str(order["orderId"])
                    )
                )
        return ret_val

    @async_ttl_cache(ttl=30, maxsize=1000)
    async def get_all_my_trades(self, trading_pair: str) -> List[Trade]:
        # Ths Binance API call rate is 5, so we cache to make sure we don't go over rate limit
        symbol = await BinanceAPIOrderBookDataSource.exchange_symbol_associated_to_pair(trading_pair)
        trades = await self._api_request(
            method="get",
            path_url=CONSTANTS.MY_TRADES_PATH_URL,
            params={"symbol": symbol},
            is_auth_required=True)
        return await self._format_trades(trades)

    async def get_my_trades(self, trading_pair: str, days_ago: float) -> List[Trade]:
        trades = await self.get_all_my_trades(trading_pair)

        if days_ago is not None:
            time = binance_utils.get_utc_timestamp(days_ago) * 1e3
            trades = [t for t in trades if t.timestamp > time]
        return trades

    async def _get_rest_assistant(self) -> RESTAssistant:
        if self._rest_assistant is None:
            self._rest_assistant = await self._api_factory.get_rest_assistant()
        return self._rest_assistant

    async def _update_time_synchronizer(self):
        try:
            await self._binance_time_synchronizer.update_server_time_offset_with_time_provider(
                time_provider=self._get_current_server_time()
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Error requesting time from Binance server")
            raise

    async def _get_current_server_time(self):
        response = await self._api_request(
            method="get",
            path_url=CONSTANTS.SERVER_TIME_PATH_URL,
        )
        return response["serverTime"]

    async def _format_trades(trades):
        ret_val = []
        processed_keys = set()
        for trade in trades:
            trade_symbol = trade["symbol"]
            trade_order_id = trade["orderId"]
            trade_price = trade["price"]
            trade_key = f"{trade_symbol}{trade_order_id}{trade_price}"

            if trade_key not in processed_keys:
                sum_trades = [t for t in trades if t["symbol"] == trade_symbol
                              and t["orderId"] == trade_order_id
                              and t["price"] == trade_price]
                if not sum_trades:
                    continue
                processed_keys.add(f"{trade_symbol}{trade_order_id}{trade_price}")
                amount = sum(Decimal(str(t["qty"])) for t in sum_trades)
                time = sum_trades[-1]["time"]
                commission = sum(Decimal(str(t["commission"])) for t in sum_trades)

                ret_val.append(
                    Trade(
                        trading_pair=await BinanceAPIOrderBookDataSource.trading_pair_associated_to_exchange_symbol(
                            trade["symbol"]),
                        side=TradeType.BUY if trade["isBuyer"] else TradeType.SELL,
                        price=Decimal(str(trade["price"])),
                        amount=amount,
                        order_type=None,
                        market=await BinanceAPIOrderBookDataSource.trading_pair_associated_to_exchange_symbol(
                            trade["symbol"]),
                        timestamp=int(time),
                        trade_fee=TradeFee(0.0, [(trade["commissionAsset"], commission)]),
                    )
                )

        return ret_val
