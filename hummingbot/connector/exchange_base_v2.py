from typing import Any, AsyncIterable, Dict, List, Optional
import asyncio
import logging

from decimal import Decimal
from async_timeout import timeout

from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.connector.constants import s_decimal_NaN, s_decimal_0, MINUTE, TWELVE_HOURS
from hummingbot.connector.client_order_tracker import ClientOrderTracker
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.utils import get_new_client_order_id
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, OrderState
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_tracker import OrderBookTracker
from hummingbot.core.data_type.user_stream_tracker import UserStreamTracker
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.logger import HummingbotLogger


class ExchangeApiMixin(object):
    # overridden in implementation of exchanges
    web_utils = None

    async def start_network(self):
        """
        Start all required tasks to update the status of the connector. Those tasks include:
        - The order book tracker
        - The polling loop to update the trading rules
        - The polling loop to update order status and balance status using REST API (backup for main update process)
        - The background task to process the events received through the user stream tracker (websocket connection)
        """
        self._stop_network()
        self._order_book_tracker.start()
        self._trading_rules_polling_task = safe_ensure_future(self._trading_rules_polling_loop())
        try:
            # this is only present in kucoin so far, so if the method is not defined, we simply ignore it
            self._trading_fees_polling_task = safe_ensure_future(self._trading_fees_polling_loop())
        except NotImplementedError:
            pass
        if self._trading_required:
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())
            self._user_stream_tracker_task = safe_ensure_future(self._user_stream_tracker.start())
            self._user_stream_event_listener_task = safe_ensure_future(self._user_stream_event_listener())

    # TODO in binance and gate io it's async
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
        """
        This function is executed when the connector is stopped. It perform a general cleanup and stops all background
        tasks that require the connection with the exchange to work.
        """
        self._stop_network()

    async def check_network(self) -> NetworkStatus:
        """
        Checks connectivity with the exchange using the API
        """
        try:
            await self._api_get(path_url=self.CHECK_NETWORK_URL)
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    # loops and sync related methods
    #
    async def _iter_user_event_queue(self) -> AsyncIterable[Dict[str, any]]:
        while True:
            try:
                yield await self._user_stream_tracker.user_stream.get()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Error while reading user events queue. Retrying after 1 second.")
                await asyncio.sleep(1.0)

    async def _trading_rules_polling_loop(self):
        """
        Updates the trading rules by requesting the latest definitions from the exchange.
        Executes regularly every 30 minutes
        """
        while True:
            try:
                await safe_gather(self._update_trading_rules())
                await asyncio.sleep(self.TRADING_RULES_INTERVAL)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network("Unexpected error while fetching trading rules.", exc_info=True,
                                      app_warning_msg=f"Could not fetch new trading rules from {self.name_cap}"
                                                      "Check network connection.")
                await asyncio.sleep(0.5)

    async def _trading_fees_polling_loop(self):
        while True:
            try:
                await safe_gather(self._update_trading_fees())
                await self._sleep(TWELVE_HOURS)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network("Unexpected error while fetching trading fees.", exc_info=True,
                                      app_warning_msg=f"Could not fetch new trading fees from {self.name_cap}. "
                                                      "Check network connection.")
                await self._sleep(0.5)

    async def _status_polling_loop(self):
        """
        Performs all required operation to keep the connector updated and synchronized with the exchange.
        It contains the backup logic to update status using API requests in case the main update source (the user stream
        data source websocket) fails.
        It also updates the time synchronizer. This is necessary because the exchange requires the time of the client to be
        the same as the time in the exchange.
        Executes when the _poll_notifier event is enabled by the `tick` function.
        """
        while True:
            try:
                await self._poll_notifier.wait()
                await self._update_time_synchronizer()
                # the following method is implementation-specific
                await self._status_polling_loop_updates()
                self._last_poll_timestamp = self.current_timestamp
                self._poll_notifier = asyncio.Event()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network("Unexpected error while fetching account updates.", exc_info=True,
                                      app_warning_msg="Could not fetch account updates from {self.name_cap}. "
                                                      "Check API key and network connection.")
                await self._sleep(0.5)

    async def _update_time_synchronizer(self):
        try:
            await self._time_synchronizer.update_server_time_offset_with_time_provider(
                time_provider=self.web_utils.get_current_server_time(
                    throttler=self._throttler,
                    domain=self._domain,
                )
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception(f"Error requesting time from {self.name_cap} server")
            raise

    # Exchange / Trading logic methods
    # that call the API
    #
    async def _update_trading_rules(self):
        exchange_info = await self._api_get(path_url=self.SYMBOLS_PATH_URL)
        trading_rules_list = await self._format_trading_rules(exchange_info)
        self._trading_rules.clear()
        for trading_rule in trading_rules_list:
            self._trading_rules[trading_rule.trading_pair] = trading_rule

    async def _update_trading_fees(self):
        trading_symbols = [await self._orderbook_ds.exchange_symbol_associated_to_pair(
            trading_pair=trading_pair,
            domain=self._domain,
            api_factory=self._api_factory,
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer) for trading_pair in self._trading_pairs]
        params = {"symbols": ",".join(trading_symbols)}
        resp = await self._api_get(
            path_url=self.FEE_PATH_URL,
            params=params,
            is_auth_required=True,
        )
        fees_json = resp["data"]
        for fee_json in fees_json:
            trading_pair = await self._orderbook_ds.trading_pair_associated_to_exchange_symbol(
                symbol=fee_json["symbol"],
                domain=self._domain,
                api_factory=self._api_factory,
                throttler=self._throttler,
                time_synchronizer=self._time_synchronizer,
            )
            self._trading_fees[trading_pair] = fee_json

    async def _api_get(self, *args, **kwargs):
        kwargs["method"] = RESTMethod.GET
        return await self._api_request(*args, **kwargs)

    async def _api_post(self, *args, **kwargs):
        kwargs["method"] = RESTMethod.POST
        return await self._api_request(*args, **kwargs)

    async def _api_put(self, *args, **kwargs):
        kwargs["method"] = RESTMethod.PUT
        return await self._api_request(*args, **kwargs)

    async def _api_delete(self, *args, **kwargs):
        kwargs["method"] = RESTMethod.DELETE
        return await self._api_request(*args, **kwargs)

    async def _api_request(self,
                           path_url,
                           method: RESTMethod = RESTMethod.GET,
                           params: Optional[Dict[str, Any]] = None,
                           data: Optional[Dict[str, Any]] = None,
                           is_auth_required: bool = False,
                           limit_id: Optional[str] = None) -> Dict[str, Any]:

        return await self.web_utils.api_request(
            path=path_url,
            api_factory=self._api_factory,
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            domain=self._domain,
            params=params,
            data=data,
            method=method,
            is_auth_required=is_auth_required,
            limit_id=limit_id)

    # tied to specific data format
    # seem different between kucoin and binance,
    # but in the end they both instantiate TradeUpdate and OrderUpdate
    def _user_stream_event_listener(self):
        raise NotImplementedError

    # NOTE the following methods are tightly coupled
    # exchange and api logics; should probably be in ExchangeBaseV2

    # coupled with ob ds; could be generalised if
    # raw_trading_pair_info is normalised
    def _format_trading_rules(self):
        raise NotImplementedError

    # calls api, 80% of logic is the same between kucoin and binance
    # could be generalised if data is normalised
    def _update_order_status(self):
        raise NotImplementedError

    # calls api, similar scenario as _update_order_status above
    def _update_balances(self):
        raise NotImplementedError


class ExchangeBaseV2(ExchangeApiMixin, ExchangeBase):
    _logger = None

    DEFAULT_DOMAIN = ""
    RATE_LIMITS = None
    SUPPORTED_ORDER_TYPES = []

    MAX_ORDER_ID_LEN = None
    HBOT_ORDER_ID_PREFIX = None
    SYMBOLS_PATH_URL = ""
    FEE_PATH_URL = ""
    CHECK_NETWORK_URL = ""

    SHORT_POLL_INTERVAL = 5.0
    LONG_POLL_INTERVAL = 120.0
    TRADING_RULES_INTERVAL = 30 * MINUTE
    UPDATE_ORDERS_INTERVAL = 10.0
    TICK_INTERVAL_LIMIT = 60.0

    def __init__(self):
        super().__init__()

        self._last_poll_timestamp = 0
        self._last_timestamp = 0
        self._trading_rules = {}
        self._trading_fees = {}

        self._status_polling_task = None
        self._user_stream_tracker_task = None
        self._user_stream_event_listener_task = None
        self._trading_rules_polling_task = None
        self._trading_fees_polling_task = None

        self._time_synchronizer = TimeSynchronizer()
        self._throttler = AsyncThrottler(self.RATE_LIMITS)
        self._poll_notifier = asyncio.Event()

        # init Auth and Api factory
        self._auth = self.init_auth()
        self._api_factory = self.web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            domain=self._domain,
            auth=self._auth)

        # init OrderBook Data Source and Tracker
        self._orderbook_ds = self.ORDERBOOK_DS_CLASS(
            trading_pairs=self._trading_pairs,
            domain=self._domain,
            api_factory=self._api_factory,
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer)
        self._order_book_tracker = OrderBookTracker(
            data_source=self._orderbook_ds,
            trading_pairs=self._trading_pairs,
            domain=self._domain)

        # init UserStream Data Source and Tracker
        self._userstream_ds = self.USERSTREAM_DS_CLASS(
            auth=self._auth,
            domain=self._domain,
            api_factory=self._api_factory,
            throttler=self._throttler)
        self._user_stream_tracker = UserStreamTracker(
            data_source=self._userstream_ds)

        self._order_tracker: ClientOrderTracker = ClientOrderTracker(connector=self)

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    # Price logic
    # TODO trading rules creation should have logic to ensure Decimal
    #
    @staticmethod
    def quantize_value(value: Decimal, quantum: Decimal) -> Decimal:
        return (value // quantum) * quantum

    def quantize_order_price(self, trading_pair: str, price: Decimal) -> Decimal:
        if price.is_nan():
            return price
        price_quantum = self.get_order_price_quantum(trading_pair, price)
        return ExchangeBaseV2.quantize_value(price, price_quantum)

    def get_order_price_quantum(self, trading_pair: str, price: Decimal) -> Decimal:
        """
        Used by quantize_order_price() in _create_order()
        Returns a price step, a minimum price increment for a given trading pair.

        :param trading_pair: the trading pair to check for market conditions
        :param price: the starting point price
        """
        trading_rule = self._trading_rules[trading_pair]
        return Decimal(trading_rule.min_price_increment)

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

    # Exchange / Trading logic
    #
    def supported_order_types(self):
        return self.SUPPORTED_ORDER_TYPES

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        return self._order_book_tracker.order_books

    @property
    def in_flight_orders(self) -> Dict[str, InFlightOrder]:
        return self._order_tracker.active_orders

    @property
    def trading_rules(self) -> Dict[str, TradingRule]:
        return self._trading_rules

    @property
    def limit_orders(self) -> List[LimitOrder]:
        return [
            in_flight_order.to_limit_order()
            for in_flight_order in self.in_flight_orders.values()
        ]

    def get_order_book(self, trading_pair: str) -> OrderBook:
        """
        Returns the current order book for a particular market

        :param trading_pair: the pair of tokens for which the order book should be retrieved
        """
        if trading_pair not in self._order_book_tracker.order_books:
            raise ValueError(f"No order book exists for '{trading_pair}'.")
        return self._order_book_tracker.order_books[trading_pair]

    @property
    def status_dict(self) -> Dict[str, bool]:
        return {
            "symbols_mapping_initialized": self._orderbook_ds.trading_pair_symbol_map_ready(
                domain=self._domain),
            "order_books_initialized": self._order_book_tracker.ready,
            "account_balance": not self._trading_required or len(self._account_balances) > 0,
            "trading_rule_initialized": len(self._trading_rules) > 0 if self._trading_required else True,
            "user_stream_initialized":
                self._user_stream_tracker.data_source.last_recv_time > 0 if self._trading_required else True,
        }

    @property
    def ready(self) -> bool:
        """
        Returns True if the connector is ready to operate (all connections established with the exchange). If it is
        not ready it returns False.
        """
        return all(self.status_dict.values())

    def tick(self, timestamp: float):
        """
        Includes the logic that has to be processed every time a new tick happens in the bot. Particularly it enables
        the execution of the status update polling loop using an event.
        """
        last_recv_diff = timestamp - self._user_stream_tracker.last_recv_time
        poll_interval = (self.SHORT_POLL_INTERVAL
                         if last_recv_diff > self.TICK_INTERVAL_LIMIT
                         else self.LONG_POLL_INTERVAL)
        last_tick = int(self._last_timestamp / poll_interval)
        current_tick = int(timestamp / poll_interval)
        if current_tick > last_tick:
            if not self._poll_notifier.is_set():
                self._poll_notifier.set()
        self._last_timestamp = timestamp

    # Orders placing
    #
    def buy(self,
            trading_pair: str,
            amount: Decimal,
            order_type=OrderType.MARKET,
            price: Decimal = s_decimal_NaN,
            **kwargs) -> str:
        """
        Creates a promise to create a buy order using the parameters

        :param trading_pair: the token pair to operate with
        :param amount: the order amount
        :param order_type: the type of order to create (MARKET, LIMIT, LIMIT_MAKER)
        :param price: the order price

        :return: the id assigned by the connector to the order (the client id)
        """
        order_id = get_new_client_order_id(
            is_buy=True,
            trading_pair=trading_pair,
            hbot_order_id_prefix=self.HBOT_ORDER_ID_PREFIX,
            max_id_len=self.MAX_ORDER_ID_LEN
        )
        safe_ensure_future(self._create_order(
            trade_type=TradeType.BUY,
            order_id=order_id,
            trading_pair=trading_pair,
            amount=amount,
            order_type=order_type,
            price=price))
        return order_id

    def sell(self, trading_pair: str, amount: Decimal, order_type: OrderType = OrderType.MARKET,
             price: Decimal = s_decimal_NaN, **kwargs) -> str:
        """
        Creates a promise to create a sell order using the parameters.
        :param trading_pair: the token pair to operate with
        :param amount: the order amount
        :param order_type: the type of order to create (MARKET, LIMIT, LIMIT_MAKER)
        :param price: the order price
        :return: the id assigned by the connector to the order (the client id)
        """
        order_id = get_new_client_order_id(
            is_buy=False,
            trading_pair=trading_pair,
            hbot_order_id_prefix=self.HBOT_ORDER_ID_PREFIX,
            max_id_len=self.MAX_ORDER_ID_LEN
        )
        safe_ensure_future(self._create_order(
            trade_type=TradeType.SELL,
            order_id=order_id,
            trading_pair=trading_pair,
            amount=amount,
            order_type=order_type,
            price=price))
        return order_id

    def get_fee(self,
                base_currency: str,
                quote_currency: str,
                order_type: OrderType,
                order_side: TradeType,
                amount: Decimal,
                price: Decimal = s_decimal_NaN,
                is_maker: Optional[bool] = None) -> AddedToCostTradeFee:
        """
        Calculates the fee to pay based on the fee information provided by the exchange for the account and the token pair.
        If exchange info is not available it calculates the estimated fee an order would pay based on the connector
            configuration

        :param base_currency: the order base currency
        :param quote_currency: the order quote currency
        :param order_type: the type of order (MARKET, LIMIT, LIMIT_MAKER)
        :param order_side: if the order is for buying or selling
        :param amount: the order amount
        :param price: the order price
        :param is_maker: True if the order is a maker order, False if it is a taker order

        :return: the calculated or estimated fee
        """
        return self._get_fee(base_currency, quote_currency, order_type, order_side, amount, price, is_maker)

    def cancel(self, trading_pair: str, order_id: str):
        """
        Creates a promise to cancel an order in the exchange

        :param trading_pair: the trading pair the order to cancel operates with
        :param order_id: the client id of the order to cancel

        :return: the client id of the order to cancel
        """
        safe_ensure_future(self._execute_cancel(trading_pair, order_id))
        return order_id

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        """
        Cancels all currently active orders. The cancellations are performed in parallel tasks.

        :param timeout_seconds: the maximum time (in seconds) the cancel logic should run

        :return: a list of CancellationResult instances, one for each of the orders to be cancelled
        """
        incomplete_orders = [o for o in self.in_flight_orders.values() if not o.is_done]
        tasks = [self._execute_cancel(o.trading_pair, o.client_order_id) for o in incomplete_orders]
        order_id_set = set([o.client_order_id for o in incomplete_orders])
        successful_cancellations = []

        try:
            async with timeout(timeout_seconds):
                cancellation_results = await safe_gather(*tasks, return_exceptions=True)
                for cr in cancellation_results:
                    if isinstance(cr, Exception):
                        continue

                    client_order_id = None
                    # Binance allows cancellations only by using its own order id, not ours
                    # TODO this should go to an implementation specific method that is
                    # overridden by Binance and in other cases where applicable
                    if isinstance(cr, dict) and "origClientOrderId" in cr:
                        client_order_id = cr.get("origClientOrderId")
                    if cr is not None:
                        if not client_order_id:
                            client_order_id = cr
                        order_id_set.remove(client_order_id)
                        successful_cancellations.append(CancellationResult(client_order_id, True))
        except Exception:
            self.logger().network(
                "Unexpected error cancelling orders.",
                exc_info=True,
                app_warning_msg="Failed to cancel order. Check API key and network connection."
            )
        failed_cancellations = [CancellationResult(oid, False) for oid in order_id_set]
        return successful_cancellations + failed_cancellations

    async def _create_order(self,
                            trade_type: TradeType,
                            order_id: str,
                            trading_pair: str,
                            amount: Decimal,
                            order_type: OrderType,
                            price: Optional[Decimal] = None):
        """
        Creates a an order in the exchange using the parameters to configure it

        :param trade_type: the side of the order (BUY of SELL)
        :param order_id: the id that should be assigned to the order (the client id)
        :param trading_pair: the token pair to operate with
        :param amount: the order amount
        :param order_type: the type of order to create (MARKET, LIMIT, LIMIT_MAKER)
        :param price: the order price
        """
        trading_rule = self._trading_rules[trading_pair]

        if order_type in [OrderType.LIMIT, OrderType.LIMIT_MAKER]:
            price = self.quantize_order_price(trading_pair, price)
            amount = self.quantize_order_amount(trading_pair=trading_pair, amount=amount, price=price)
        else:
            amount = self.quantize_order_amount(trading_pair=trading_pair, amount=amount)
        # TODO binance
        if "binance" in self.name:
            price = self.quantize_order_price(trading_pair, price)
            quantize_amount_price = Decimal("0") if price.is_nan() else price
            amount = self.quantize_order_amount(trading_pair=trading_pair, amount=amount, price=quantize_amount_price)

        self.start_tracking_order(
            order_id=order_id,
            exchange_order_id=None,
            trading_pair=trading_pair,
            order_type=order_type,
            trade_type=trade_type,
            price=price,
            amount=amount
        )

        if amount < trading_rule.min_order_size:
            self.logger().warning(f"{trade_type.name.title()} order amount {amount} is lower than the minimum order"
                                  f" size {trading_rule.min_order_size}. The order will not be created.")
            order_update: OrderUpdate = OrderUpdate(
                client_order_id=order_id,
                trading_pair=trading_pair,
                update_timestamp=self.current_timestamp,
                new_state=OrderState.FAILED,
            )
            self._order_tracker.process_order_update(order_update)
            return

        try:
            exchange_order_id, update_timestamp = await self._place_order(
                order_id=order_id,
                trading_pair=trading_pair,
                amount=amount,
                trade_type=trade_type,
                order_type=order_type,
                price=price)

            order_update: OrderUpdate = OrderUpdate(
                client_order_id=order_id,
                exchange_order_id=exchange_order_id,
                trading_pair=trading_pair,
                update_timestamp=update_timestamp,
                new_state=OrderState.OPEN,
            )
            self._order_tracker.process_order_update(order_update)

        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().network(
                f"Error submitting {trade_type.name.lower()} {order_type.name.upper()} order to {self.name_cap} for "
                f"{amount} {trading_pair} "
                f"{price}.",
                exc_info=True,
                app_warning_msg=f"Failed to submit buy order to {self.name_cap}. Check API key and network connection."
            )
            order_update: OrderUpdate = OrderUpdate(
                client_order_id=order_id,
                trading_pair=trading_pair,
                update_timestamp=self.current_timestamp,
                new_state=OrderState.FAILED,
            )
            self._order_tracker.process_order_update(order_update)

    async def _execute_cancel(self, trading_pair: str, order_id: str) -> str:
        """
        Requests the exchange to cancel an active order

        :param trading_pair: the trading pair the order to cancel operates with
        :param order_id: the client id of the order to cancel
        """
        tracked_order = self._order_tracker.fetch_tracked_order(order_id)
        if tracked_order is not None:
            try:
                cancelled = await self._place_cancel(order_id, tracked_order)
                if cancelled:
                    order_update: OrderUpdate = OrderUpdate(
                        client_order_id=order_id,
                        trading_pair=tracked_order.trading_pair,
                        update_timestamp=self.current_timestamp,
                        new_state=OrderState.CANCELLED,
                    )
                    self._order_tracker.process_order_update(order_update)
                    return order_id
            except asyncio.CancelledError:
                raise
            # TODO is this logic applicable to binance?
            except asyncio.TimeoutError:
                self.logger().warning(f"Failed to cancel the order {order_id} because it does not have an exchange"
                                      f" order id yet")
                await self._order_tracker.process_order_not_found(order_id)
            # TODO kucoin
            # except Exception as e:
            #    self.logger().network(
            #        f"Failed to cancel order {order_id}: {str(e)}", exc_info=True,
            #        app_warning_msg=f"Failed to cancel the order {order_id} on {self.name_cap}. "
            #                        f"Check API key and network connection."
            #    )
            except Exception:
                self.logger().exception(f"There was an error when requesting cancellation of order {order_id}")
                raise
        return None

    # Order Tracking
    #
    @property
    def tracking_states(self) -> Dict[str, any]:
        """
        Returns a dictionary associating current active orders client id to their JSON representation
        """
        return {
            key: value.to_json()
            for key, value in self.in_flight_orders.items()
            if not value.is_done
            # TODO this line is not there in the binance exchange
            # but it is on gate io
        }

    def restore_tracking_states(self, saved_states: Dict[str, Any]):
        """
        Restore in-flight orders from saved tracking states, this is st the connector can pick up on where it left off
        when it disconnects.

        :param saved_states: The saved tracking_states.
        """
        self._order_tracker.restore_tracking_states(tracking_states=saved_states)

    def start_tracking_order(self,
                             order_id: str,
                             exchange_order_id: Optional[str],
                             trading_pair: str,
                             trade_type: TradeType,
                             price: Decimal,
                             amount: Decimal,
                             order_type: OrderType):
        """
        Starts tracking an order by adding it to the order tracker.

        :param order_id: the order identifier
        :param exchange_order_id: the identifier for the order in the exchange
        :param trading_pair: the token pair for the operation
        :param trade_type: the type of order (buy or sell)
        :param price: the price for the order
        :param amount: the amount for the order
        :param order_type: type of execution for the order (MARKET, LIMIT, LIMIT_MAKER)
        """
        self._order_tracker.start_tracking_order(
            InFlightOrder(
                client_order_id=order_id,
                exchange_order_id=exchange_order_id,
                trading_pair=trading_pair,
                order_type=order_type,
                trade_type=trade_type,
                amount=amount,
                price=price,
                creation_timestamp=self.current_timestamp
            )
        )

    def stop_tracking_order(self, order_id: str):
        """
        Stops tracking an order

        :param order_id: The id of the order that will not be tracked any more
        """
        self._order_tracker.stop_tracking_order(client_order_id=order_id)

    async def _sleep(self, delay: float):
        await asyncio.sleep(delay)

    @property
    def name_cap(self) -> str:
        return self.name.capitalize()

    # Implementation-specific methods
    #
    def name(self):
        raise NotImplementedError

    def init_auth(self):
        raise NotImplementedError

    def _place_cancel(self):
        raise NotImplementedError

    def _place_order(self):
        raise NotImplementedError

    def _get_fee(self):
        raise NotImplementedError
