import asyncio
import logging
from decimal import Decimal
from typing import Any, AsyncIterable, Dict, List, Optional
from urllib.parse import quote, urljoin

import aiohttp
import ujson

from hummingbot.connector.exchange.mexc import mexc_constants as CONSTANTS
from hummingbot.connector.exchange.mexc.mexc_auth import MexcAuth
from hummingbot.connector.exchange.mexc.mexc_in_flight_order import MexcInFlightOrder
from hummingbot.connector.exchange.mexc.mexc_order_book_tracker import MexcOrderBookTracker
from hummingbot.connector.exchange.mexc.mexc_user_stream_tracker import MexcUserStreamTracker
from hummingbot.connector.exchange.mexc.mexc_utils import (
    convert_from_exchange_trading_pair,
    convert_to_exchange_trading_pair,
    num_to_increment,
    ws_order_status_convert_to_str
)
from hummingbot.connector.exchange_base import ExchangeBase, s_decimal_NaN
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.clock import Clock
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_tracker import OrderBookTrackerDataSourceType
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
from hummingbot.core.utils.async_call_scheduler import AsyncCallScheduler
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce
from hummingbot.logger import HummingbotLogger

hm_logger = None
s_decimal_0 = Decimal(0)


class MexcAPIError(IOError):
    def __init__(self, error_payload: Dict[str, Any]):
        super().__init__(str(error_payload))
        self.error_payload = error_payload


class MexcExchange(ExchangeBase):
    MARKET_RECEIVED_ASSET_EVENT_TAG = MarketEvent.ReceivedAsset
    MARKET_BUY_ORDER_COMPLETED_EVENT_TAG = MarketEvent.BuyOrderCompleted
    MARKET_SELL_ORDER_COMPLETED_EVENT_TAG = MarketEvent.SellOrderCompleted
    MARKET_WITHDRAW_ASSET_EVENT_TAG = MarketEvent.WithdrawAsset
    MARKET_ORDER_CANCELLED_EVENT_TAG = MarketEvent.OrderCancelled
    MARKET_TRANSACTION_FAILURE_EVENT_TAG = MarketEvent.TransactionFailure
    MARKET_ORDER_FAILURE_EVENT_TAG = MarketEvent.OrderFailure
    MARKET_ORDER_FILLED_EVENT_TAG = MarketEvent.OrderFilled
    MARKET_BUY_ORDER_CREATED_EVENT_TAG = MarketEvent.BuyOrderCreated
    MARKET_SELL_ORDER_CREATED_EVENT_TAG = MarketEvent.SellOrderCreated
    API_CALL_TIMEOUT = 10.0
    UPDATE_ORDERS_INTERVAL = 10.0
    SHORT_POLL_INTERVAL = 5.0
    MORE_SHORT_POLL_INTERVAL = 1.0
    LONG_POLL_INTERVAL = 120.0
    ORDER_LEN_LIMIT = 20

    _logger = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self,
                 mexc_api_key: str,
                 mexc_secret_key: str,
                 poll_interval: float = 5.0,
                 order_book_tracker_data_source_type: OrderBookTrackerDataSourceType = OrderBookTrackerDataSourceType.EXCHANGE_API,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True):

        super().__init__()
        self._throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        self._shared_client = aiohttp.ClientSession()
        self._async_scheduler = AsyncCallScheduler(call_interval=0.5)
        self._data_source_type = order_book_tracker_data_source_type
        self._ev_loop = asyncio.get_event_loop()
        self._mexc_auth = MexcAuth(api_key=mexc_api_key, secret_key=mexc_secret_key)
        self._in_flight_orders = {}
        self._last_poll_timestamp = 0
        self._last_timestamp = 0
        self._order_book_tracker = MexcOrderBookTracker(
            throttler=self._throttler, trading_pairs=trading_pairs, shared_client=self._shared_client)
        self._poll_notifier = asyncio.Event()
        self._poll_interval = poll_interval
        self._status_polling_task = None
        self._trading_required = trading_required
        self._trading_rules = {}
        self._trading_rules_polling_task = None
        self._user_stream_tracker = MexcUserStreamTracker(throttler=self._throttler,
                                                          mexc_auth=self._mexc_auth,
                                                          trading_pairs=trading_pairs,
                                                          shared_client=self._shared_client)
        self._user_stream_tracker_task = None
        self._user_stream_event_listener_task = None

    @property
    def name(self) -> str:
        return "mexc"

    @property
    def order_book_tracker(self) -> MexcOrderBookTracker:
        return self._order_book_tracker

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        return self._order_book_tracker.order_books

    @property
    def trading_rules(self) -> Dict[str, TradingRule]:
        return self._trading_rules

    @property
    def in_flight_orders(self) -> Dict[str, MexcInFlightOrder]:
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
            client_oid: order.to_json()
            for client_oid, order in self._in_flight_orders.items()
            if not order.is_done
        }

    def restore_tracking_states(self, saved_states: Dict[str, Any]):
        self._in_flight_orders.update({
            key: MexcInFlightOrder.from_json(value)
            for key, value in saved_states.items()
        })

    @property
    def shared_client(self) -> aiohttp.ClientSession:
        return self._shared_client

    @property
    def user_stream_tracker(self) -> MexcUserStreamTracker:
        return self._user_stream_tracker

    @shared_client.setter
    def shared_client(self, client: aiohttp.ClientSession):
        self._shared_client = client

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
        await self.stop_network()
        self._order_book_tracker.start()
        self._trading_rules_polling_task = safe_ensure_future(self._trading_rules_polling_loop())

        if self._trading_required:
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())
            self._user_stream_tracker_task = safe_ensure_future(self._user_stream_tracker.start())
            self._user_stream_event_listener_task = safe_ensure_future(self._user_stream_event_listener())
            await self._update_balances()

    async def stop_network(self):
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
        try:
            resp = await self._api_request(method="GET", path_url=CONSTANTS.MEXC_PING_URL)
            if 'code' not in resp or resp['code'] != 200:
                raise Exception()
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    def tick(self, timestamp: float):
        """
        Is called automatically by the clock for each clock's tick (1 second by default).
        It checks if status polling task is due for execution.
        """
        # now = time.time()
        poll_interval = self.MORE_SHORT_POLL_INTERVAL
        last_tick = int(self._last_timestamp / poll_interval)
        current_tick = int(timestamp / poll_interval)
        if current_tick > last_tick:
            if not self._poll_notifier.is_set():
                self._poll_notifier.set()
        self._last_timestamp = timestamp

    async def _http_client(self) -> aiohttp.ClientSession:
        if self._shared_client is None:
            self._shared_client = aiohttp.ClientSession()
        return self._shared_client

    async def _api_request(self,
                           method: str,
                           path_url: str,
                           params: Optional[Dict[str, Any]] = {},
                           data={},
                           is_auth_required: bool = False,
                           limit_id: Optional[str] = None) -> Dict[str, Any]:

        headers = {"Content-Type": "application/json"}
        if path_url in CONSTANTS.MEXC_PLACE_ORDER:
            headers.update({'source': 'HUMBOT'})
        client = await self._http_client()
        text_data = ujson.dumps(data) if data else None
        limit_id = limit_id or path_url
        path_url = self._mexc_auth.add_auth_to_params(method, path_url, params, is_auth_required)
        url = urljoin(CONSTANTS.MEXC_BASE_URL, path_url)
        async with self._throttler.execute_task(limit_id):
            response_core = await client.request(
                method=method.upper(),
                url=url,
                headers=headers,
                # params=params if params else None, #mexc`s params  is already in the url
                data=text_data,
            )

        # async with response_core as response:
        if response_core.status != 200:
            raise IOError(f"Error request from {url}. Response: {await response_core.json()}.")
        try:
            parsed_response = await response_core.json()
            return parsed_response
        except Exception as ex:
            raise IOError(f"Error parsing data from {url}." + repr(ex))

    async def _update_balances(self):
        path_url = CONSTANTS.MEXC_BALANCE_URL
        msg = await self._api_request("GET", path_url=path_url, is_auth_required=True)
        if msg['code'] == 200:
            balances = msg['data']
        else:
            raise Exception(msg)
            self.logger().info(f" _update_balances error: {msg} ")
            return

        self._account_available_balances.clear()
        self._account_balances.clear()
        for k, balance in balances.items():
            # if Decimal(balance['frozen']) + Decimal(balance['available']) > Decimal(0.0001):
            self._account_balances[k] = Decimal(balance['frozen']) + Decimal(balance['available'])
            self._account_available_balances[k] = Decimal(balance['available'])

    async def _update_trading_rules(self):
        try:
            last_tick = int(self._last_timestamp / 60.0)
            current_tick = int(self.current_timestamp / 60.0)
            if current_tick > last_tick or len(self._trading_rules) < 1:
                exchange_info = await self._api_request("GET", path_url=CONSTANTS.MEXC_SYMBOL_URL)
                trading_rules_list = self._format_trading_rules(exchange_info['data'])
                self._trading_rules.clear()
                for trading_rule in trading_rules_list:
                    self._trading_rules[trading_rule.trading_pair] = trading_rule
        except Exception as ex:
            self.logger().error("Error _update_trading_rules:" + str(ex), exc_info=True)

    def _format_trading_rules(self, raw_trading_pair_info: List[Dict[str, Any]]) -> List[TradingRule]:
        trading_rules = []
        for info in raw_trading_pair_info:
            try:
                trading_rules.append(
                    TradingRule(trading_pair=convert_from_exchange_trading_pair(info['symbol']),
                                # min_order_size=Decimal(info["min_amount"]),
                                # max_order_size=Decimal(info["max_amount"]),
                                min_price_increment=Decimal(num_to_increment(info["price_scale"])),
                                min_base_amount_increment=Decimal(num_to_increment(info["quantity_scale"])),
                                # min_quote_amount_increment=Decimal(info["1e-{info['value-precision']}"]),
                                # min_notional_size=Decimal(info["min-order-value"])
                                min_notional_size=Decimal(info["min_amount"]),
                                # max_notional_size=Decimal(info["max_amount"]),

                                )
                )
            except Exception:
                self.logger().error(f"Error parsing the trading pair rule {info}. Skipping.", exc_info=True)
        return trading_rules

    async def get_order_status(self, exchangge_order_id: str, trading_pair: str) -> Dict[str, Any]:
        params = {"order_ids": exchangge_order_id}
        msg = await self._api_request("GET",
                                      path_url=CONSTANTS.MEXC_ORDER_DETAILS_URL,
                                      params=params,
                                      is_auth_required=True)

        if msg["code"] == 200:
            return msg['data'][0]

    async def _update_order_status(self):
        last_tick = int(self._last_poll_timestamp / self.UPDATE_ORDERS_INTERVAL)
        current_tick = int(self.current_timestamp / self.UPDATE_ORDERS_INTERVAL)
        if current_tick > last_tick and len(self._in_flight_orders) > 0:
            tracked_orders = list(self._in_flight_orders.values())
            for tracked_order in tracked_orders:
                try:
                    exchange_order_id = await tracked_order.get_exchange_order_id()
                    try:
                        order_update = await self.get_order_status(exchange_order_id, tracked_order.trading_pair)
                    except MexcAPIError as ex:
                        err_code = ex.error_payload.get("error").get('err-code')
                        self.stop_tracking_order(tracked_order.client_order_id)
                        self.logger().info(f"The limit order {tracked_order.client_order_id} "
                                           f"has failed according to order status API. - {err_code}")
                        self.trigger_event(
                            self.MARKET_ORDER_FAILURE_EVENT_TAG,
                            MarketOrderFailureEvent(
                                self.current_timestamp,
                                tracked_order.client_order_id,
                                tracked_order.order_type
                            )
                        )
                        continue

                    if order_update is None:
                        self.logger().network(
                            f"Error fetching status update for the order {tracked_order.client_order_id}: "
                            f"{exchange_order_id}.",
                            app_warning_msg=f"Could not fetch updates for the order {tracked_order.client_order_id}. "
                                            f"The order has either been filled or canceled."
                        )
                        continue
                    tracked_order.last_state = order_update['state']
                    order_status = order_update['state']
                    new_confirmed_amount = Decimal(order_update['deal_quantity'])
                    execute_amount_diff = new_confirmed_amount - tracked_order.executed_amount_base

                    if execute_amount_diff > s_decimal_0:
                        execute_price = Decimal(
                            Decimal(order_update['deal_amount']) / Decimal(order_update['deal_quantity']))
                        tracked_order.executed_amount_base = Decimal(order_update['deal_quantity'])
                        tracked_order.executed_amount_quote = Decimal(order_update['deal_amount'])

                        order_filled_event = OrderFilledEvent(
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
                                execute_amount_diff,
                                execute_price,
                            ),
                            exchange_trade_id=exchange_order_id
                        )
                        self.logger().info(f"Filled {execute_amount_diff} out of {tracked_order.amount} of the "
                                           f"order {tracked_order.client_order_id}.")
                        self.trigger_event(self.MARKET_ORDER_FILLED_EVENT_TAG, order_filled_event)
                    if order_status == "FILLED":
                        fee_paid, fee_currency = await self.get_deal_detail_fee(tracked_order.exchange_order_id)
                        tracked_order.fee_paid = fee_paid
                        tracked_order.fee_asset = fee_currency
                        tracked_order.last_state = order_status
                        self.stop_tracking_order(tracked_order.client_order_id)
                        if tracked_order.trade_type is TradeType.BUY:
                            self.logger().info(
                                f"The BUY {tracked_order.order_type} order {tracked_order.client_order_id} has completed "
                                f"according to order delta restful API.")
                            self.trigger_event(self.MARKET_BUY_ORDER_COMPLETED_EVENT_TAG,
                                               BuyOrderCompletedEvent(self.current_timestamp,
                                                                      tracked_order.client_order_id,
                                                                      tracked_order.base_asset,
                                                                      tracked_order.quote_asset,
                                                                      tracked_order.fee_asset or tracked_order.quote_asset,
                                                                      tracked_order.executed_amount_base,
                                                                      tracked_order.executed_amount_quote,
                                                                      tracked_order.fee_paid,
                                                                      tracked_order.order_type))
                        elif tracked_order.trade_type is TradeType.SELL:
                            self.logger().info(
                                f"The SELL {tracked_order.order_type} order {tracked_order.client_order_id} has completed "
                                f"according to order delta restful API.")
                            self.trigger_event(self.MARKET_SELL_ORDER_COMPLETED_EVENT_TAG,
                                               SellOrderCompletedEvent(self.current_timestamp,
                                                                       tracked_order.client_order_id,
                                                                       tracked_order.base_asset,
                                                                       tracked_order.quote_asset,
                                                                       tracked_order.fee_asset or tracked_order.quote_asset,
                                                                       tracked_order.executed_amount_base,
                                                                       tracked_order.executed_amount_quote,
                                                                       tracked_order.fee_paid,
                                                                       tracked_order.order_type))
                        continue
                    if order_status == "CANCELED" or order_status == "PARTIALLY_CANCELED":
                        tracked_order.last_state = order_status
                        self.stop_tracking_order(tracked_order.client_order_id)
                        self.logger().info(f"Order {tracked_order.client_order_id} has been cancelled "
                                           f"according to order delta restful API.")
                        self.trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                           OrderCancelledEvent(self.current_timestamp,
                                                               tracked_order.client_order_id))
                except Exception as ex:
                    self.logger().error("_update_order_status error ..." + repr(ex), exc_info=True)

    def _reset_poll_notifier(self):
        self._poll_notifier = asyncio.Event()

    async def _status_polling_loop(self):
        while True:
            try:
                self._reset_poll_notifier()
                await self._poll_notifier.wait()
                await safe_gather(
                    self._update_balances(),
                    self._update_order_status(),
                )
                self._last_poll_timestamp = self.current_timestamp
            except asyncio.CancelledError:
                raise
            except Exception as ex:
                self.logger().network("Unexpected error while fetching account updates." + repr(ex),
                                      exc_info=True,
                                      app_warning_msg="Could not fetch account updates from MEXC. "
                                                      "Check API key and network connection.")
                await asyncio.sleep(0.5)

    async def _trading_rules_polling_loop(self):
        while True:
            try:
                await self._update_trading_rules()
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                raise
            except Exception as ex:
                self.logger().network("Unexpected error while fetching trading rules." + repr(ex),
                                      exc_info=True,
                                      app_warning_msg="Could not fetch new trading rules from MEXC. "
                                                      "Check network connection.")
                await asyncio.sleep(0.5)

    async def _iter_user_event_queue(self) -> AsyncIterable[Dict[str, Any]]:
        while True:
            try:
                yield await self._user_stream_tracker.user_stream.get()
            except asyncio.CancelledError:
                raise
            except Exception as ex:
                self.logger().error(f"Unknown error. Retrying after 1 second. {ex}", exc_info=True)
                await asyncio.sleep(1.0)

    async def _user_stream_event_listener(self):
        async for stream_message in self._iter_user_event_queue():
            # self.logger().info(f"stream_message:{stream_message}")
            try:
                if 'channel' in stream_message.keys() and stream_message['channel'] == 'push.personal.account':
                    continue
                elif 'channel' in stream_message.keys() and stream_message['channel'] == 'push.personal.order':
                    await self._process_order_message(stream_message)
                else:
                    self.logger().debug(f"Unknown event received from the connector ({stream_message})")
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(f"Unexpected error in user stream listener lopp. {e}", exc_info=True)
                await asyncio.sleep(5.0)

    async def _process_order_message(self, stream_message: Dict[str, Any]):
        client_order_id = stream_message["data"]["clientOrderId"]
        # trading_pair = convert_from_exchange_trading_pair(stream_message["symbol"])
        # 1:NEW,2:FILLED,3:PARTIALLY_FILLED,4:CANCELED,5:PARTIALLY_CANCELED
        order_status = ws_order_status_convert_to_str(stream_message["data"]["status"])
        tracked_order = self._in_flight_orders.get(client_order_id, None)
        if tracked_order is None:
            return
        # Update balance in time
        await self._update_balances()

        if order_status in {"FILLED", "PARTIALLY_FILLED"}:
            executed_amount = Decimal(str(stream_message["data"]['quantity'])) - Decimal(
                str(stream_message["data"]['remainQuantity']))
            execute_price = Decimal(str(stream_message["data"]['price']))
            execute_amount_diff = executed_amount - tracked_order.executed_amount_base
            if execute_amount_diff > s_decimal_0:
                tracked_order.executed_amount_base = executed_amount
                tracked_order.executed_amount_quote = Decimal(
                    str(stream_message["data"]['amount'])) - Decimal(
                    str(stream_message["data"]['remainAmount']))

                current_fee = self.get_fee(tracked_order.base_asset,
                                           tracked_order.quote_asset,
                                           tracked_order.order_type,
                                           tracked_order.trade_type,
                                           execute_amount_diff,
                                           execute_price)
                self.logger().info(f"Filled {execute_amount_diff} out of {tracked_order.amount} of ")
                self.trigger_event(self.MARKET_ORDER_FILLED_EVENT_TAG,
                                   OrderFilledEvent(self.current_timestamp,
                                                    tracked_order.client_order_id,
                                                    tracked_order.trading_pair,
                                                    tracked_order.trade_type,
                                                    tracked_order.order_type,
                                                    execute_price,
                                                    execute_amount_diff,
                                                    current_fee,
                                                    exchange_trade_id=tracked_order.exchange_order_id))
        if order_status == "FILLED":
            fee_paid, fee_currency = await self.get_deal_detail_fee(tracked_order.exchange_order_id)
            tracked_order.fee_paid = fee_paid
            tracked_order.fee_asset = fee_currency
            tracked_order.last_state = order_status
            if tracked_order.trade_type is TradeType.BUY:
                self.logger().info(
                    f"The BUY {tracked_order.order_type} order {tracked_order.client_order_id} has completed "
                    f"according to order delta websocket API.")
                self.trigger_event(self.MARKET_BUY_ORDER_COMPLETED_EVENT_TAG,
                                   BuyOrderCompletedEvent(self.current_timestamp,
                                                          tracked_order.client_order_id,
                                                          tracked_order.base_asset,
                                                          tracked_order.quote_asset,
                                                          tracked_order.fee_asset or tracked_order.quote_asset,
                                                          tracked_order.executed_amount_base,
                                                          tracked_order.executed_amount_quote,
                                                          tracked_order.fee_paid,
                                                          tracked_order.order_type))
            elif tracked_order.trade_type is TradeType.SELL:
                self.logger().info(
                    f"The SELL {tracked_order.order_type} order {tracked_order.client_order_id} has completed "
                    f"according to order delta websocket API.")
                self.trigger_event(self.MARKET_SELL_ORDER_COMPLETED_EVENT_TAG,
                                   SellOrderCompletedEvent(self.current_timestamp,
                                                           tracked_order.client_order_id,
                                                           tracked_order.base_asset,
                                                           tracked_order.quote_asset,
                                                           tracked_order.fee_asset or tracked_order.quote_asset,
                                                           tracked_order.executed_amount_base,
                                                           tracked_order.executed_amount_quote,
                                                           tracked_order.fee_paid,
                                                           tracked_order.order_type))
            self.stop_tracking_order(tracked_order.client_order_id)
            return

        if order_status == "CANCELED" or order_status == "PARTIALLY_CANCELED":
            tracked_order.last_state = order_status
            self.logger().info(f"Order {tracked_order.client_order_id} has been cancelled "
                               f"according to order delta websocket API.")
            self.trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                               OrderCancelledEvent(self.current_timestamp,
                                                   tracked_order.client_order_id))
            self.stop_tracking_order(tracked_order.client_order_id)

    @property
    def status_dict(self) -> Dict[str, bool]:
        return {
            "order_books_initialized": self._order_book_tracker.ready,
            "acount_balance": len(self._account_balances) > 0 if self._trading_required else True,
            "trading_rule_initialized": len(self._trading_rules) > 0
        }

    def supported_order_types(self):
        return [OrderType.LIMIT, OrderType.MARKET]

    @property
    def ready(self) -> bool:
        return all(self.status_dict.values())

    async def place_order(self,
                          order_id: str,
                          trading_pair: str,
                          amount: Decimal,
                          is_buy: bool,
                          order_type: OrderType,
                          price: Decimal) -> str:

        if order_type is OrderType.LIMIT:
            order_type_str = "LIMIT_ORDER"
        elif order_type is OrderType.LIMIT_MAKER:
            order_type_str = "POST_ONLY"

        data = {
            'client_order_id': order_id,
            'order_type': order_type_str,
            'trade_type': "BID" if is_buy else "ASK",
            'symbol': convert_to_exchange_trading_pair(trading_pair),
            'quantity': str(amount),
            'price': str(price)
        }

        exchange_order_id = await self._api_request(
            "POST",
            path_url=CONSTANTS.MEXC_PLACE_ORDER,
            params={},
            data=data,
            is_auth_required=True
        )

        return str(exchange_order_id.get('data'))

    async def execute_buy(self,
                          order_id: str,
                          trading_pair: str,
                          amount: Decimal,
                          order_type: OrderType,
                          price: Optional[Decimal] = s_decimal_0):

        trading_rule = self._trading_rules[trading_pair]

        if not order_type.is_limit_type():
            self.trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                               MarketOrderFailureEvent(self.current_timestamp, order_id, order_type))
            raise Exception(f"Unsupported order type: {order_type}")

        decimal_price = self.quantize_order_price(trading_pair, price)
        decimal_amount = self.quantize_order_amount(trading_pair, amount, decimal_price)
        if decimal_price * decimal_amount < trading_rule.min_notional_size:
            self.trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                               MarketOrderFailureEvent(self.current_timestamp, order_id, order_type))
            raise ValueError(f"Buy order amount {decimal_amount} is lower than the notional size ")
        try:
            exchange_order_id = await self.place_order(order_id, trading_pair, decimal_amount, True, order_type,
                                                       decimal_price)
            self.start_tracking_order(
                order_id=order_id,
                exchange_order_id=exchange_order_id,
                trading_pair=trading_pair,
                order_type=order_type,
                trade_type=TradeType.BUY,
                price=decimal_price,
                amount=decimal_amount
            )
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(
                    f"Created {order_type.name.upper()} buy order {order_id} for {decimal_amount} {trading_pair}.")
            self.trigger_event(self.MARKET_BUY_ORDER_CREATED_EVENT_TAG,
                               BuyOrderCreatedEvent(
                                   self.current_timestamp,
                                   order_type,
                                   trading_pair,
                                   decimal_amount,
                                   decimal_price,
                                   order_id
                               ))
        except asyncio.CancelledError:
            raise
        except Exception as ex:
            self.stop_tracking_order(order_id)
            order_type_str = order_type.name.lower()

            self.logger().network(
                f"Error submitting buy {order_type_str} order to Mexc for "
                f"{decimal_amount} {trading_pair} "
                f"{decimal_price if order_type is OrderType.LIMIT else ''}."
                f"{decimal_price}." + repr(ex),
                exc_info=True,
                app_warning_msg="Failed to submit buy order to Mexc. Check API key and network connection."
            )
            self.trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                               MarketOrderFailureEvent(self.current_timestamp, order_id, order_type))

    def buy(self, trading_pair: str, amount: Decimal, order_type=OrderType.MARKET,
            price: Decimal = s_decimal_NaN, **kwargs) -> str:
        tracking_nonce = int(get_tracking_nonce())
        order_id = str(f"buy-{trading_pair}-{tracking_nonce}")
        safe_ensure_future(self.execute_buy(order_id, trading_pair, amount, order_type, price))
        return order_id

    async def execute_sell(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           order_type: OrderType,
                           price: Optional[Decimal] = s_decimal_0):

        trading_rule = self._trading_rules[trading_pair]

        if not order_type.is_limit_type():
            self.trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                               MarketOrderFailureEvent(self.current_timestamp, order_id, order_type))
            raise Exception(f"Unsupported order type: {order_type}")

        decimal_price = self.quantize_order_price(trading_pair, price)
        decimal_amount = self.quantize_order_amount(trading_pair, amount, decimal_price)

        if decimal_price * decimal_amount < trading_rule.min_notional_size:
            self.trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                               MarketOrderFailureEvent(self.current_timestamp, order_id, order_type))
            raise ValueError(f"Sell order amount {decimal_amount} is lower than the notional size ")

        try:
            exchange_order_id = await self.place_order(order_id, trading_pair, decimal_amount, False, order_type,
                                                       decimal_price)
            self.start_tracking_order(
                order_id=order_id,
                exchange_order_id=exchange_order_id,
                trading_pair=trading_pair,
                order_type=order_type,
                trade_type=TradeType.SELL,
                price=decimal_price,
                amount=decimal_amount
            )
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(
                    f"Created {order_type.name.upper()} sell order {order_id} for {decimal_amount} {trading_pair}.")
            self.trigger_event(self.MARKET_SELL_ORDER_CREATED_EVENT_TAG,
                               SellOrderCreatedEvent(
                                   self.current_timestamp,
                                   order_type,
                                   trading_pair,
                                   decimal_amount,
                                   decimal_price,
                                   order_id
                               ))
        except asyncio.CancelledError:
            raise
        except Exception as ex:
            self.stop_tracking_order(order_id)
            order_type_str = order_type.name.lower()
            self.logger().network(
                f"Error submitting sell {order_type_str} order to Mexc for "
                f"{decimal_amount} {trading_pair} "
                f"{decimal_price if order_type is OrderType.LIMIT else ''}."
                f"{decimal_price}." + ",ex:" + repr(ex),
                exc_info=True,
                app_warning_msg="Failed to submit sell order to Mexc. Check API key and network connection."
            )
            self.trigger_event(self.MARKET_ORDER_FAILURE_EVENT_TAG,
                               MarketOrderFailureEvent(self.current_timestamp, order_id, order_type))

    def sell(self, trading_pair: str, amount: Decimal, order_type: OrderType = OrderType.MARKET,
             price: Decimal = s_decimal_NaN, **kwargs) -> str:

        tracking_nonce = int(get_tracking_nonce())
        order_id = str(f"sell-{trading_pair}-{tracking_nonce}")

        safe_ensure_future(self.execute_sell(order_id, trading_pair, amount, order_type, price))
        return order_id

    async def execute_cancel(self, trading_pair: str, client_order_id: str):
        try:
            tracked_order = self._in_flight_orders.get(client_order_id)
            if tracked_order is None:
                # raise ValueError(f"Failed to cancel order - {client_order_id}. Order not found.")
                self.logger().network(f"Failed to cancel order - {client_order_id}. Order not found.")
                return
            params = {
                "client_order_ids": client_order_id,
            }
            response = await self._api_request("DELETE", path_url=CONSTANTS.MEXC_ORDER_CANCEL, params=params,
                                               is_auth_required=True)

            if not response['code'] == 200:
                raise MexcAPIError("Order could not be canceled")

        except MexcAPIError as ex:
            self.logger().network(
                f"Failed to cancel order {client_order_id} : {repr(ex)}",
                exc_info=True,
                app_warning_msg=f"Failed to cancel the order {client_order_id} on Mexc. "
                                f"Check API key and network connection."
            )

    def cancel(self, trading_pair: str, order_id: str):
        safe_ensure_future(self.execute_cancel(trading_pair, order_id))
        return order_id

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        orders_by_trading_pair = {}

        for order in self._in_flight_orders.values():
            orders_by_trading_pair[order.trading_pair] = orders_by_trading_pair.get(order.trading_pair, [])
            orders_by_trading_pair[order.trading_pair].append(order)

        if len(orders_by_trading_pair) == 0:
            return []

        for trading_pair in orders_by_trading_pair:
            cancel_order_ids = [o.exchange_order_id for o in orders_by_trading_pair[trading_pair]]
            is_need_loop = True
            while is_need_loop:
                if len(cancel_order_ids) > self.ORDER_LEN_LIMIT:
                    is_need_loop = True
                    this_turn_cancel_order_ids = cancel_order_ids[:self.ORDER_LEN_LIMIT]
                    cancel_order_ids = cancel_order_ids[self.ORDER_LEN_LIMIT:]
                else:
                    this_turn_cancel_order_ids = cancel_order_ids
                    is_need_loop = False
                self.logger().debug(
                    f"cancel_order_ids {this_turn_cancel_order_ids} orders_by_trading_pair[trading_pair]")
                params = {
                    'order_ids': quote(','.join([o for o in this_turn_cancel_order_ids])),
                }

                cancellation_results = []
                try:
                    cancel_all_results = await self._api_request(
                        "DELETE",
                        path_url=CONSTANTS.MEXC_ORDER_CANCEL,
                        params=params,
                        is_auth_required=True
                    )

                    for order_result_client_order_id, order_result_value in cancel_all_results['data'].items():
                        for o in orders_by_trading_pair[trading_pair]:
                            if o.client_order_id == order_result_client_order_id:
                                result_bool = True if order_result_value == "invalid order state" or order_result_value == "success" else False
                                cancellation_results.append(CancellationResult(o.client_order_id, result_bool))
                                if result_bool:
                                    self.trigger_event(self.MARKET_ORDER_CANCELLED_EVENT_TAG,
                                                       OrderCancelledEvent(self.current_timestamp,
                                                                           order_id=o.client_order_id,
                                                                           exchange_order_id=o.exchange_order_id))
                                    self.stop_tracking_order(o.client_order_id)

                except Exception as ex:

                    self.logger().network(
                        f"Failed to cancel all orders: {this_turn_cancel_order_ids}" + repr(ex),
                        exc_info=True,
                        app_warning_msg="Failed to cancel all orders on Mexc. Check API key and network connection."
                    )
        return cancellation_results

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
        self._in_flight_orders[order_id] = MexcInFlightOrder(
            client_order_id=order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=trading_pair,
            order_type=order_type,
            trade_type=trade_type,
            price=price,
            amount=amount
        )

    def stop_tracking_order(self, order_id: str):
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

        quantized_amount = ExchangeBase.quantize_order_amount(self, trading_pair, amount)
        current_price = self.get_price(trading_pair, False)

        calc_price = current_price if price == s_decimal_0 else price

        notional_size = calc_price * quantized_amount

        if notional_size < trading_rule.min_notional_size * Decimal("1"):
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
        is_maker = order_type is OrderType.LIMIT_MAKER
        return AddedToCostTradeFee(percent=self.estimate_fee_pct(is_maker))

    async def get_deal_detail_fee(self, order_id: str) -> Dict[str, Any]:
        params = {
            'order_id': order_id,
        }
        msg = await self._api_request("GET", path_url=CONSTANTS.MEXC_DEAL_DETAIL, params=params, is_auth_required=True)
        fee = s_decimal_0
        fee_currency = None
        if msg['code'] == 200:
            balances = msg['data']
        else:
            raise Exception(msg)
        for order in balances:
            fee += Decimal(order['fee'])
            fee_currency = order['fee_currency']
        return fee, fee_currency
