import asyncio
import logging
import time

from decimal import Decimal
from typing import (
    Any,
    AsyncIterable,
    Dict,
    List,
    Optional,
)

from async_timeout import timeout

import hummingbot.connector.exchange.binance.binance_constants as CONSTANTS
from hummingbot.connector.client_order_tracker import ClientOrderTracker
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.connector.exchange.binance import binance_utils
from hummingbot.connector.exchange.binance.binance_api_order_book_data_source import BinanceAPIOrderBookDataSource
from hummingbot.connector.exchange.binance.binance_auth import BinanceAuth
from hummingbot.connector.exchange.binance.binance_order_book_tracker import BinanceOrderBookTracker
from hummingbot.connector.exchange.binance.binance_user_stream_tracker import BinanceUserStreamTracker
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import TradeFillOrderDetails
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, OrderState, TradeUpdate
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.trade_fee import (
    DeductedFromReturnsTradeFee,
    TokenAmount,
    TradeFeeBase,
)
from hummingbot.core.event.events import (
    MarketEvent,
    OrderFilledEvent,
    OrderType,
    TradeType,
)
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest
from hummingbot.core.web_assistant.rest_assistant import RESTAssistant
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.logger import HummingbotLogger

s_logger = None
s_decimal_0 = Decimal(0)
s_decimal_NaN = Decimal("nan")


class BinanceExchange(ExchangeBase):
    SHORT_POLL_INTERVAL = 5.0
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0
    LONG_POLL_INTERVAL = 120.0

    MAX_ORDER_UPDATE_RETRIEVAL_RETRIES_WITH_FAILURES = 3

    def __init__(self,
                 binance_api_key: str,
                 binance_api_secret: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True,
                 domain="com"
                 ):
        self._domain = domain
        self._binance_time_synchronizer = TimeSynchronizer()
        super().__init__()
        self._trading_required = trading_required
        self._auth = BinanceAuth(
            api_key=binance_api_key,
            secret_key=binance_api_secret,
            time_provider=self._binance_time_synchronizer)
        self._api_factory = WebAssistantsFactory(auth=self._auth)
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
        self._order_not_found_records = {}  # Dict[client_order_id:str, count:int]
        self._trading_rules = {}  # Dict[trading_pair:str, TradingRule]
        self._trade_fees = {}  # Dict[trading_pair:str, (maker_fee_percent:Decimal, taken_fee_percent:Decimal)]
        self._last_update_trade_fees_timestamp = 0
        self._status_polling_task = None
        self._user_stream_event_listener_task = None
        self._trading_rules_polling_task = None
        self._last_poll_timestamp = 0
        self._last_trades_poll_binance_timestamp = 0
        self._order_tracker: ClientOrderTracker = ClientOrderTracker(connector=self)

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(__name__)
        return s_logger

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
    def in_flight_orders(self) -> Dict[str, InFlightOrder]:
        return self._order_tracker.active_orders

    @property
    def limit_orders(self) -> List[LimitOrder]:
        return [
            in_flight_order.to_limit_order()
            for in_flight_order in self.in_flight_orders.values()
        ]

    @property
    def tracking_states(self) -> Dict[str, any]:
        """
        Returns a dictionary associating current active orders client id to their JSON representation
        """
        return {
            key: value.to_json()
            for key, value in self.in_flight_orders.items()
        }

    @property
    def order_book_tracker(self) -> BinanceOrderBookTracker:
        return self._order_book_tracker

    @property
    def user_stream_tracker(self) -> BinanceUserStreamTracker:
        return self._user_stream_tracker

    @property
    def status_dict(self) -> Dict[str, bool]:
        """
        Returns a dictionary with the values of all the conditions that determine if the connector is ready to operate.
        The key of each entry is the condition name, and the value is True if condition is ready, False otherwise.
        """
        return {
            "symbols_mapping_initialized": BinanceAPIOrderBookDataSource.trading_pair_symbol_map_ready(
                domain=self._domain),
            "order_books_initialized": self._order_book_tracker.ready,
            "account_balance": len(self._account_balances) > 0 if self._trading_required else True,
            "trading_rule_initialized": len(self._trading_rules) > 0,
        }

    @property
    def ready(self) -> bool:
        """
        Returns True if the connector is ready to operate (all connections established with the exchange). If it is
        not ready it returns False.
        """
        return all(self.status_dict.values())

    @staticmethod
    def binance_order_type(order_type: OrderType) -> str:
        return order_type.name.upper()

    @staticmethod
    def to_hb_order_type(binance_type: str) -> OrderType:
        return OrderType[binance_type]

    def supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER]

    async def start_network(self):
        """
        Start all required tasks to update the status of the connector. Those tasks include:
        - The order book tracker
        - The polling loop to update the trading rules
        - The polling loop to update order status and balance status using REST API (backup for main update process)
        - The background task to process the events received through the user stream tracker (websocket connection)
        """
        self._order_book_tracker.start()
        self._trading_rules_polling_task = safe_ensure_future(self._trading_rules_polling_loop())
        if self._trading_required:
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())
            self._user_stream_tracker_task = safe_ensure_future(self._user_stream_tracker.start())
            self._user_stream_event_listener_task = safe_ensure_future(self._user_stream_event_listener())

    async def stop_network(self):
        """
        This function is executed when the connector is stopped. It perform a general cleanup and stops all background
        tasks that require the connection with the exchange to work.
        """
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

    async def check_network(self) -> NetworkStatus:
        """
        Checks connectivity with the exchange using the API
        """
        try:
            await self._api_request(
                method=RESTMethod.GET,
                path_url=CONSTANTS.PING_PATH_URL,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    def restore_tracking_states(self, saved_states: Dict[str, any]):
        """
        Restore in-flight orders from saved tracking states, this is st the connector can pick up on where it left off
        when it disconnects.
        :param saved_states: The saved tracking_states.
        """
        for data in saved_states.values():
            self._order_tracker.start_tracking_order(InFlightOrder.from_json(data))

    def tick(self, timestamp: float):
        """
        Includes the logic that has to be processed every time a new tick happens in the bot. Particularly it enables
        the execution of the status update polling loop using an event.
        """
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

    def get_order_book(self, trading_pair: str) -> OrderBook:
        """
        Returns the current order book for a particular market
        :param trading_pair: the pair of tokens for which the order book should be retrieved
        """
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
        Starts tracking an order by adding it to the order tracker.
        :param order_id: the order identifier
        :param exchange_order_id: the identifier for the order in the exchange
        :param trading_pair: the token pair for the operation
        :param trade_type: the type of order (buy or sell)
        :param price: the price for the order
        :param amount: the amount for the order
        :order type: type of execution for the order (MARKET, LIMIT, LIMIT_MAKER)
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
            )
        )

    def stop_tracking_order(self, order_id: str):
        """
        Stops tracking an order
        :param order_id: The id of the order that will not be tracked any more
        """
        self._order_tracker.stop_tracking_order(client_order_id=order_id)

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
        return trading_rule.min_base_amount_increment

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
                is_maker: Optional[bool] = None) -> TradeFeeBase:
        """
        Calculates the estimated fee an order would pay based on the connector configuration
        :param base_currency: the order base currency
        :param quote_currency: the order quote currency
        :param order_type: the type of order (MARKET, LIMIT, LIMIT_MAKER)
        :param order_side: if the order is for buying or selling
        :param amount: the order amount
        :param price: the order price
        :return: the estimated fee for the order
        """

        """
        To get trading fee, this function is simplified by using fee override configuration. Most parameters to this
        function are ignore except order_type. Use OrderType.LIMIT_MAKER to specify you want trading fee for
        maker order.
        """
        is_maker = order_type is OrderType.LIMIT_MAKER
        return DeductedFromReturnsTradeFee(percent=self.estimate_fee_pct(is_maker))

    def buy(self, trading_pair: str, amount: Decimal, order_type: OrderType = OrderType.LIMIT,
            price: Decimal = s_decimal_NaN, **kwargs) -> str:
        """
        Creates a promise to create a buy order using the parameters.
        :param trading_pair: the token pair to operate with
        :param amount: the order amount
        :param order_type: the type of order to create (MARKET, LIMIT, LIMIT_MAKER)
        :param price: the order price
        :return: the id assigned by the connector to the order (the client id)
        """
        new_order_id = binance_utils.get_new_client_order_id(is_buy=True, trading_pair=trading_pair)
        safe_ensure_future(self._create_order(TradeType.BUY, new_order_id, trading_pair, amount, order_type, price))
        return new_order_id

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
        order_id = binance_utils.get_new_client_order_id(is_buy=False, trading_pair=trading_pair)
        safe_ensure_future(self._create_order(TradeType.SELL, order_id, trading_pair, amount, order_type, price))
        return order_id

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

    async def _create_order(self,
                            trade_type: TradeType,
                            order_id: str,
                            trading_pair: str,
                            amount: Decimal,
                            order_type: OrderType,
                            price: Optional[Decimal] = Decimal("NaN")):
        """
        Creates a an order in the exchange using the parameters to configure it
        :param trade_type: the side of the order (BUY of SELL)
        :param order_id: the id that should be assigned to the order (the client id)
        :param trading_pair: the token pair to operate with
        :param amount: the order amount
        :param order_type: the type of order to create (MARKET, LIMIT, LIMIT_MAKER)
        :param price: the order price
        """
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        price = self.quantize_order_price(trading_pair, price)
        quantize_amount_price = Decimal("0") if price.is_nan() else price
        amount = self.quantize_order_amount(trading_pair=trading_pair, amount=amount, price=quantize_amount_price)

        self.start_tracking_order(
            order_id=order_id,
            exchange_order_id=None,
            trading_pair=trading_pair,
            trade_type=trade_type,
            price=price,
            amount=amount,
            order_type=order_type)

        if amount < trading_rule.min_order_size:
            self.logger().warning(f"{trade_type.name.title()} order amount {amount} is lower than the minimum order"
                                  f" size {trading_rule.min_order_size}. The order will not be created.")
            order_update: OrderUpdate = OrderUpdate(
                client_order_id=order_id,
                trading_pair=trading_pair,
                update_timestamp=int(self.current_timestamp * 1e3),
                new_state=OrderState.FAILED,
            )
            self._order_tracker.process_order_update(order_update)
            return

        order_result = None
        amount_str = f"{amount:f}"
        price_str = f"{price:f}"
        type_str = BinanceExchange.binance_order_type(order_type)
        side_str = CONSTANTS.SIDE_BUY if trade_type is TradeType.BUY else CONSTANTS.SIDE_SELL
        symbol = await BinanceAPIOrderBookDataSource.exchange_symbol_associated_to_pair(
            trading_pair=trading_pair,
            domain=self._domain,
            api_factory=self._api_factory,
            throttler=self._throttler)
        api_params = {"symbol": symbol,
                      "side": side_str,
                      "quantity": amount_str,
                      "type": type_str,
                      "newClientOrderId": order_id,
                      "price": price_str}
        if order_type == OrderType.LIMIT:
            api_params["timeInForce"] = CONSTANTS.TIME_IN_FORCE_GTC

        try:
            order_result = await self._api_request(
                method=RESTMethod.POST,
                path_url=CONSTANTS.ORDER_PATH_URL,
                data=api_params,
                is_auth_required=True)

            exchange_order_id = str(order_result["orderId"])

            order_update: OrderUpdate = OrderUpdate(
                client_order_id=order_id,
                exchange_order_id=exchange_order_id,
                trading_pair=trading_pair,
                update_timestamp=int(order_result["transactTime"]),
                new_state=OrderState.OPEN,
            )
            self._order_tracker.process_order_update(order_update)

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
            order_update: OrderUpdate = OrderUpdate(
                client_order_id=order_id,
                trading_pair=trading_pair,
                update_timestamp=int(self.current_timestamp * 1e3),
                new_state=OrderState.FAILED,
            )
            self._order_tracker.process_order_update(order_update)

    async def _execute_cancel(self, trading_pair: str, order_id: str):
        """
        Requests the exchange to cancel an active order
        :param trading_pair: the trading pair the order to cancel operates with
        :param order_id: the client id of the order to cancel
        """
        tracked_order = self._order_tracker.fetch_tracked_order(order_id)
        if tracked_order is not None:
            try:
                symbol = await BinanceAPIOrderBookDataSource.exchange_symbol_associated_to_pair(
                    trading_pair=trading_pair,
                    domain=self._domain,
                    api_factory=self._api_factory,
                    throttler=self._throttler)
                api_params = {
                    "symbol": symbol,
                    "origClientOrderId": order_id,
                }
                cancel_result = await self._api_request(
                    method=RESTMethod.DELETE,
                    path_url=CONSTANTS.ORDER_PATH_URL,
                    params=api_params,
                    is_auth_required=True)

                if cancel_result.get("status") == "CANCELED":
                    order_update: OrderUpdate = OrderUpdate(
                        client_order_id=order_id,
                        trading_pair=tracked_order.trading_pair,
                        update_timestamp=int(self.current_timestamp * 1e3),
                        new_state=OrderState.CANCELLED,
                    )
                    self._order_tracker.process_order_update(order_update)
                return cancel_result

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception(f"There was a an error when requesting cancellation of order {order_id}")
                raise

    async def _status_polling_loop(self):
        """
        Performs all required operation to keep the connector updated and synchronized with the exchange.
        It contains the backup logic to update status using API requests in case the main update source (the user stream
        data source websocket) fails.
        It also updates the time synchronizer. This is necessary because Binance require the time of the client to be
        the same as the time in the exchange.
        Executes when the _poll_notifier event is enabled by the `tick` function.
        """
        while True:
            try:
                await self._poll_notifier.wait()
                await self._update_time_synchronizer()
                await safe_gather(
                    self._update_balances(),
                    self._update_order_fills_from_trades(),
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
        """
        Updates the trading rules by requesting the latest definitions from the exchange.
        Executes regularly every 30 minutes
        """
        while True:
            try:
                await safe_gather(
                    self._update_trading_rules(),
                )
                await asyncio.sleep(30 * 60)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network("Unexpected error while fetching trading rules.", exc_info=True,
                                      app_warning_msg="Could not fetch new trading rules from Binance. "
                                                      "Check network connection.")
                await asyncio.sleep(0.5)

    async def _update_trading_rules(self):
        exchange_info = await self._api_request(
            method=RESTMethod.GET,
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
                    symbol=rule.get("symbol"),
                    domain=self._domain,
                    api_factory=self._api_factory,
                    throttler=self._throttler)
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

    async def _user_stream_event_listener(self):
        """
        This functions runs in background continuously processing the events received from the exchange by the user
        stream data source. It keeps reading events from the queue until the task is interrupted.
        The events received are balance updates, order updates and trade events.
        """
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

                    if execution_type == "TRADE":
                        tracked_order = self._order_tracker.fetch_order(client_order_id=client_order_id)
                        if tracked_order is not None:
                            trade_update = TradeUpdate(
                                trade_id=str(event_message["t"]),
                                client_order_id=client_order_id,
                                exchange_order_id=str(event_message["i"]),
                                trading_pair=tracked_order.trading_pair,
                                fee_asset=event_message["N"],
                                fee_paid=Decimal(event_message["n"]),
                                fill_base_amount=Decimal(event_message["l"]),
                                fill_quote_amount=Decimal(event_message["l"]) * Decimal(event_message["L"]),
                                fill_price=Decimal(event_message["L"]),
                                fill_timestamp=int(event_message["T"]),
                            )
                            self._order_tracker.process_trade_update(trade_update)

                    tracked_order = self.in_flight_orders.get(client_order_id)
                    if tracked_order is not None:
                        order_update = OrderUpdate(
                            trading_pair=tracked_order.trading_pair,
                            update_timestamp=int(event_message["E"]),
                            new_state=CONSTANTS.ORDER_STATE[event_message["X"]],
                            client_order_id=client_order_id,
                            exchange_order_id=str(event_message["i"]),
                        )
                        self._order_tracker.process_order_update(order_update=order_update)

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

    async def _update_order_fills_from_trades(self):
        """
        This is intended to be a backup measure to get filled events with trade ID for orders,
        in case Binance's user stream events are not working.
        NOTE: It is not required to copy this functionality in other connectors.
        This is separated from _update_order_status which only updates the order status without producing filled
        events, since Binance's get order endpoint does not return trade IDs.
        The minimum poll interval for order status is 10 seconds.
        """
        small_interval_last_tick = self._last_poll_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL
        small_interval_current_tick = self.current_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL
        long_interval_last_tick = self._last_poll_timestamp / self.LONG_POLL_INTERVAL
        long_interval_current_tick = self.current_timestamp / self.LONG_POLL_INTERVAL

        if (long_interval_current_tick > long_interval_last_tick
                or (self.in_flight_orders and small_interval_current_tick > small_interval_last_tick)):
            query_time = int(self._last_trades_poll_binance_timestamp * 1e3)
            self._last_trades_poll_binance_timestamp = self._binance_time_synchronizer.time()
            order_by_exchange_id_map = {}
            for order in self._order_tracker.all_orders.values():
                order_by_exchange_id_map[order.exchange_order_id] = order

            tasks = []
            trading_pairs = self._order_book_tracker._trading_pairs
            for trading_pair in trading_pairs:
                params = {
                    "symbol": await BinanceAPIOrderBookDataSource.exchange_symbol_associated_to_pair(
                        trading_pair=trading_pair,
                        domain=self._domain,
                        api_factory=self._api_factory,
                        throttler=self._throttler)
                }
                if self._last_poll_timestamp > 0:
                    params["startTime"] = query_time
                tasks.append(self._api_request(
                    method=RESTMethod.GET,
                    path_url=CONSTANTS.MY_TRADES_PATH_URL,
                    params=params,
                    is_auth_required=True))

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
                        trade_update = TradeUpdate(
                            trade_id=str(trade["id"]),
                            client_order_id=tracked_order.client_order_id,
                            exchange_order_id=exchange_order_id,
                            trading_pair=trading_pair,
                            fee_asset=trade["commissionAsset"],
                            fee_paid=Decimal(trade["commission"]),
                            fill_base_amount=Decimal(trade["qty"]),
                            fill_quote_amount=Decimal(trade["quoteQty"]),
                            fill_price=Decimal(trade["price"]),
                            fill_timestamp=int(trade["time"]),
                        )
                        self._order_tracker.process_trade_update(trade_update)
                    elif self.is_confirmed_new_order_filled_event(str(trade["id"]), exchange_order_id, trading_pair):
                        # This is a fill of an order registered in the DB but not tracked any more
                        self._current_trade_fills.add(TradeFillOrderDetails(
                            market=self.display_name,
                            exchange_trade_id=str(trade["id"]),
                            symbol=trading_pair))
                        self.trigger_event(
                            MarketEvent.OrderFilled,
                            OrderFilledEvent(
                                timestamp=float(trade["time"]) * 1e-3,
                                order_id=self._exchange_order_ids.get(str(trade["orderId"]), None),
                                trading_pair=trading_pair,
                                trade_type=TradeType.BUY if trade["isBuyer"] else TradeType.SELL,
                                order_type=OrderType.LIMIT_MAKER if trade["isMaker"] else OrderType.LIMIT,
                                price=Decimal(trade["price"]),
                                amount=Decimal(trade["qty"]),
                                trade_fee=DeductedFromReturnsTradeFee(
                                    flat_fees=[
                                        TokenAmount(
                                            trade["commissionAsset"],
                                            Decimal(trade["commission"])
                                        )
                                    ]
                                ),
                                exchange_trade_id=str(trade["id"])
                            ))
                        self.logger().info(f"Recreating missing trade in TradeFill: {trade}")

    async def _update_order_status(self):
        # This is intended to be a backup measure to close straggler orders, in case Binance's user stream events
        # are not working.
        # The minimum poll interval for order status is 10 seconds.
        last_tick = self._last_poll_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL
        current_tick = self.current_timestamp / self.UPDATE_ORDER_STATUS_MIN_INTERVAL

        tracked_orders: List[InFlightOrder] = list(self.in_flight_orders.values())
        if current_tick > last_tick and len(tracked_orders) > 0:

            tasks = [self._api_request(
                     method=RESTMethod.GET,
                     path_url=CONSTANTS.ORDER_PATH_URL,
                     params={
                         "symbol": await BinanceAPIOrderBookDataSource.exchange_symbol_associated_to_pair(
                             trading_pair=o.trading_pair,
                             domain=self._domain,
                             api_factory=self._api_factory,
                             throttler=self._throttler),
                         "origClientOrderId": o.client_order_id},
                     is_auth_required=True) for o in tracked_orders]
            self.logger().debug(f"Polling for order status updates of {len(tasks)} orders.")
            results = await safe_gather(*tasks, return_exceptions=True)
            for order_update, tracked_order in zip(results, tracked_orders):
                client_order_id = tracked_order.client_order_id

                # If the order has already been cancelled or has failed do nothing
                if client_order_id not in self.in_flight_orders:
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

                        order_update: OrderUpdate = OrderUpdate(
                            client_order_id=client_order_id,
                            trading_pair=tracked_order.trading_pair,
                            update_timestamp=int(self.current_timestamp * 1e3),
                            new_state=OrderState.FAILED,
                        )
                        self._order_tracker.process_order_update(order_update)

                else:
                    # Update order execution status
                    new_state = CONSTANTS.ORDER_STATE[order_update["status"]]

                    update = OrderUpdate(
                        client_order_id=client_order_id,
                        exchange_order_id=str(order_update["orderId"]),
                        trading_pair=tracked_order.trading_pair,
                        update_timestamp=int(order_update["updateTime"]),
                        new_state=new_state,
                    )
                    self._order_tracker.process_order_update(update)

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

    async def _update_balances(self):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        try:
            account_info = await self._api_request(
                method=RESTMethod.GET,
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

    async def _api_request(self,
                           method: RESTMethod,
                           path_url: str,
                           params: Optional[Dict[str, Any]] = None,
                           data: Optional[Dict[str, Any]] = None,
                           is_auth_required: bool = False) -> Dict[str, Any]:

        headers = {
            "Content-Type": "application/json" if method == RESTMethod.POST else "application/x-www-form-urlencoded"}
        client = await self._get_rest_assistant()

        if is_auth_required:
            url = binance_utils.private_rest_url(path_url, domain=self._domain)
        else:
            url = binance_utils.public_rest_url(path_url, domain=self._domain)

        request = RESTRequest(method=method,
                              url=url,
                              data=data,
                              params=params,
                              headers=headers,
                              is_auth_required=is_auth_required)

        async with self._throttler.execute_task(limit_id=path_url):
            response = await client.call(request)

            if response.status != 200:
                data = await response.text()
                raise IOError(f"Error fetching data from {url}. HTTP status is {response.status} ({data}).")
            try:
                parsed_response = await response.json()
            except Exception:
                raise IOError(f"Error parsing data from {response}.")

            if "code" in parsed_response and "msg" in parsed_response:
                raise IOError(f"The request to Binance failed. Error: {parsed_response}. Request: {request}")

        return parsed_response

    async def _get_current_server_time(self):
        response = await self._api_request(
            method=RESTMethod.GET,
            path_url=CONSTANTS.SERVER_TIME_PATH_URL,
        )
        return response["serverTime"]

    async def _get_rest_assistant(self) -> RESTAssistant:
        if self._rest_assistant is None:
            self._rest_assistant = await self._api_factory.get_rest_assistant()
        return self._rest_assistant
