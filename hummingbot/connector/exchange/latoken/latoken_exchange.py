import asyncio
import datetime
import logging
import time
from decimal import Decimal
from typing import Any, AsyncIterable, Dict, List, Optional

import ujson
from async_timeout import timeout

import hummingbot.connector.exchange.latoken.latoken_constants as CONSTANTS
import hummingbot.connector.exchange.latoken.latoken_web_utils as web_utils
from hummingbot.connector.client_order_tracker import ClientOrderTracker
from hummingbot.connector.exchange.latoken.latoken_api_order_book_data_source import LatokenAPIOrderBookDataSource
from hummingbot.connector.exchange.latoken.latoken_api_user_stream_data_source import LatokenAPIUserStreamDataSource
from hummingbot.connector.exchange.latoken.latoken_auth import LatokenAuth
from hummingbot.connector.exchange.latoken.latoken_utils import (
    LatokenCommissionType,
    LatokenFeeSchema,
    LatokenTakeType,
    is_exchange_information_valid,
)
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import TradeFillOrderDetails, combine_to_hb_trading_pair, get_new_client_order_id
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_tracker import OrderBookTracker
from hummingbot.core.data_type.trade_fee import (
    AddedToCostTradeFee,
    DeductedFromReturnsTradeFee,
    TokenAmount,
    TradeFeeBase,
)
from hummingbot.core.data_type.user_stream_tracker import UserStreamTracker
from hummingbot.core.event.events import MarketEvent, OrderFilledEvent, OrderType, TradeType
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.rest_assistant import RESTAssistant
from hummingbot.logger import HummingbotLogger

s_logger = None
s_decimal_0 = Decimal(0)
s_decimal_NaN = Decimal("nan")


class LatokenExchange(ExchangeBase):
    def __init__(self,
                 latoken_api_key: str,
                 latoken_api_secret: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True,
                 domain=CONSTANTS.DEFAULT_DOMAIN
                 ):

        self._domain = domain  # it is required to have this placed before calling super
        super().__init__()
        self._latoken_time_synchronizer = TimeSynchronizer()

        self._auth = LatokenAuth(
            api_key=latoken_api_key,
            secret_key=latoken_api_secret,
            time_provider=self._latoken_time_synchronizer)
        self._throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        self._api_factory = web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._latoken_time_synchronizer,
            domain=self._domain,
            auth=self._auth)
        self._rest_assistant = None
        self._order_book_tracker = OrderBookTracker(
            data_source=LatokenAPIOrderBookDataSource(
                trading_pairs=trading_pairs,
                domain=self._domain,
                api_factory=self._api_factory,
                throttler=self._throttler),
            trading_pairs=trading_pairs,
            domain=self._domain)
        self._user_stream_tracker = UserStreamTracker(
            data_source=LatokenAPIUserStreamDataSource(
                auth=self._auth,
                domain=self._domain,
                throttler=self._throttler,
                api_factory=self._api_factory,
                time_synchronizer=self._latoken_time_synchronizer))
        self._poll_notifier = asyncio.Event()
        self._last_timestamp = 0
        self._last_poll_timestamp = 0
        self._last_update_trade_fees_timestamp = 0  # not really used atm
        self._trading_pairs = trading_pairs
        self._status_polling_task = None
        self._user_stream_tracker_task = None
        self._user_stream_event_listener_task = None
        self._trading_rules_polling_task = None
        self._trading_fees_polling_task = None
        self._trading_required = trading_required
        self._trading_rules = {}  # Dict[trading_pair:str, TradingRule]
        self._trading_fees = {}  # Dict[trading_pair:str, (maker_fee_percent:Decimal, taken_fee_percent:Decimal)]
        self._order_tracker: ClientOrderTracker = ClientOrderTracker(connector=self)

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global s_logger
        return logging.getLogger(__name__) if s_logger is None else s_logger

    @property
    def name(self) -> str:
        return "latoken" if self._domain == CONSTANTS.DEFAULT_DOMAIN else f"latoken_{self._domain}"

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        return self._order_book_tracker.order_books

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
    def status_dict(self) -> Dict[str, bool]:
        """
        Returns a dictionary with the values of all the conditions that determine if the connector is ready to operate.
        The key of each entry is the condition name, and the value is True if condition is ready, False otherwise.
        """
        return {
            "symbols_mapping_initialized": LatokenAPIOrderBookDataSource.trading_pair_symbol_map_ready(
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

    def latoken_order_type(self, order_type: OrderType) -> str:
        return order_type.name.upper()

    @staticmethod
    def to_hb_order_type(latoken_type: str) -> OrderType:
        return OrderType[latoken_type]

    def supported_order_types(self):
        return [OrderType.LIMIT]

    async def start_network(self):
        """
        Start all required tasks to update the status of the connector. Those tasks include:
        - The order book tracker
        - The polling loop to update the trading rules
        - The polling loop to update order status and balance status using REST API (backup for main update process)
        - The background task to process the events received through the user stream tracker (websocket connection)
        """
        await self.stop_network()
        self._order_book_tracker.start()
        self._trading_rules_polling_task = safe_ensure_future(self._trading_rules_polling_loop())
        self._trading_fees_polling_task = safe_ensure_future(self._trading_fees_polling_loop())
        if self._trading_required:
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())
            self._user_stream_tracker_task = safe_ensure_future(self._user_stream_tracker.start())
            self._user_stream_event_listener_task = safe_ensure_future(self._user_stream_event_listener())
            await self._update_balances()

    async def stop_network(self):
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
        if self._trading_fees_polling_task is not None:
            self._trading_fees_polling_task.cancel()
        if self._trading_rules_polling_task is not None:
            self._trading_rules_polling_task.cancel()

        self._status_polling_task = self._user_stream_tracker_task = self._user_stream_event_listener_task = \
            self._trading_fees_polling_task = self._trading_rules_polling_task = None

    async def check_network(self) -> NetworkStatus:
        """
        Checks connectivity with the exchange using the API
        """
        try:
            _ = await self._api_request(
                method=RESTMethod.GET,
                path_url=CONSTANTS.PING_PATH_URL,
                return_err=False)  # for Latoken ping path is time request

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
        self._order_tracker.restore_tracking_states(tracking_states=saved_states)

    def tick(self, timestamp: float):
        """
        Includes the logic that has to be processed every time a new tick happens in the bot. Particularly it enables
        the execution of the status update polling loop using an event.
        """
        now = time.time()
        poll_interval = (CONSTANTS.SHORT_POLL_INTERVAL
                         if now - self._user_stream_tracker.last_recv_time > 60.0
                         else CONSTANTS.LONG_POLL_INTERVAL)
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
        :param order_type: type of execution for the order (MARKET, LIMIT, LIMIT_MAKER) -> for Latoken only LIMIT support
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
        return self._trading_rules[trading_pair].min_base_amount_increment

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

        current_price: Decimal = self.get_price(trading_pair, False) if price == s_decimal_0 else price
        notional_size = current_price * quantized_amount

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
        :param is_maker: if we take into account maker fee (True) or taker fee (None, False)
        :return: the estimated fee for the order
        """
        trading_pair = combine_to_hb_trading_pair(base=base_currency, quote=quote_currency)
        fee_schema = self._trading_fees.get(trading_pair, None)
        if fee_schema is None:
            self.logger().warning(f"For trading pair = {trading_pair} there is no fee schema loaded, using presets!")
            fee = build_trade_fee(
                self.name,
                is_maker,
                base_currency=base_currency,
                quote_currency=quote_currency,
                order_type=order_type,
                order_side=order_side,
                amount=amount,
                price=price)
        else:
            if fee_schema.type == LatokenTakeType.PROPORTION or fee_schema.take == LatokenCommissionType.PERCENT:
                pass  # currently not implemented but is nice to have in next release(s)
            percent = fee_schema.maker_fee if order_type is OrderType.LIMIT_MAKER or (is_maker is not None and is_maker) else fee_schema.taker_fee
            fee = AddedToCostTradeFee(
                percent=percent) if order_side == TradeType.BUY else DeductedFromReturnsTradeFee(percent=percent)

        return fee

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
        client_order_id = get_new_client_order_id(
            is_buy=True,
            trading_pair=trading_pair,
            hbot_order_id_prefix=CONSTANTS.HBOT_ORDER_ID_PREFIX,
            max_id_len=CONSTANTS.MAX_ORDER_ID_LEN,
        )
        safe_ensure_future(self._create_order(TradeType.BUY, client_order_id, trading_pair, amount, order_type, price))
        return client_order_id

    def sell(self, trading_pair: str, amount: Decimal, order_type: OrderType = OrderType.LIMIT,
             price: Decimal = s_decimal_NaN, **kwargs) -> str:
        """
        Creates a promise to create a sell order using the parameters.
        :param trading_pair: the token pair to operate with
        :param amount: the order amount
        :param order_type: the type of order to create (MARKET, LIMIT, LIMIT_MAKER)
        :param price: the order price
        :return: the id assigned by the connector to the order (the client id)
        """
        client_order_id = get_new_client_order_id(
            is_buy=False,
            trading_pair=trading_pair,
            hbot_order_id_prefix=CONSTANTS.HBOT_ORDER_ID_PREFIX,
            max_id_len=CONSTANTS.MAX_ORDER_ID_LEN,
        )
        safe_ensure_future(self._create_order(TradeType.SELL, client_order_id, trading_pair, amount, order_type, price))
        return client_order_id

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
                    if cr is not None:
                        client_order_id = cr
                        order_id_set.remove(client_order_id)
                        successful_cancellations.append(CancellationResult(client_order_id, True))
        except Exception:
            self.logger().network(
                "Unexpected error cancelling orders.",
                exc_info=True,
                app_warning_msg="Failed to cancel order with Latoken. Check API key and network connection."
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
        quantized_price = self.quantize_order_price(trading_pair, price)
        quantize_amount_price = Decimal("0") if quantized_price.is_nan() else quantized_price
        quantized_amount = self.quantize_order_amount(trading_pair=trading_pair, amount=amount,
                                                      price=quantize_amount_price)

        self.start_tracking_order(
            order_id=order_id,
            exchange_order_id=None,
            trading_pair=trading_pair,
            trade_type=trade_type,
            price=quantized_price,
            amount=quantized_amount,
            order_type=order_type)

        if quantized_amount < trading_rule.min_order_size:
            self.logger().warning(
                f"{trade_type.name.title()} order amount {quantized_amount} is lower than the minimum order"
                f" size {trading_rule.min_order_size}. The order will not be created.")
            order_update: OrderUpdate = OrderUpdate(
                client_order_id=order_id,
                trading_pair=trading_pair,
                update_timestamp=self.current_timestamp,
                new_state=OrderState.FAILED,
            )
            self._order_tracker.process_order_update(order_update)
            return

        amount_str = f"{quantized_amount:f}"
        price_str = f"{quantized_price:f}"
        type_str = self.latoken_order_type(order_type)
        side_str = CONSTANTS.SIDE_BUY if trade_type is TradeType.BUY else CONSTANTS.SIDE_SELL
        symbol = await LatokenAPIOrderBookDataSource.exchange_symbol_associated_to_pair(
            trading_pair=trading_pair,
            domain=self._domain,
            api_factory=self._api_factory,
            throttler=self._throttler,
            time_synchronizer=self._latoken_time_synchronizer)

        if type_str == OrderType.LIMIT_MAKER.name:
            self.logger().info('_create_order LIMIT_MAKER order not supported by Latoken, using LIMIT instead')

        base, quote = symbol.split('/')
        api_params = {
            'baseCurrency': base,
            'quoteCurrency': quote,
            "side": side_str,
            "clientOrderId": order_id,
            "quantity": amount_str,
            "type": OrderType.LIMIT.name if type_str == OrderType.LIMIT_MAKER.name else type_str,
            "price": price_str,
            "timestamp": int(datetime.datetime.now().timestamp() * 1000),
            'condition': CONSTANTS.TIME_IN_FORCE_GTC
        }

        try:
            order_result = await self._api_request(
                method=RESTMethod.POST,
                path_url=CONSTANTS.ORDER_PLACE_PATH_URL,
                data=api_params,
                is_auth_required=True)

            if order_result["status"] == "SUCCESS":
                exchange_order_id = str(order_result["id"])

                order_update: OrderUpdate = OrderUpdate(
                    trading_pair=trading_pair,
                    update_timestamp=self.current_timestamp,
                    new_state=OrderState.OPEN,
                    client_order_id=order_id,
                    exchange_order_id=exchange_order_id,
                )
                self._order_tracker.process_order_update(order_update)
            else:
                raise ValueError(f"Place order failed, no SUCCESS message {order_result}")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(
                f"Error submitting {side_str} {type_str} order to Latoken for "
                f"{quantized_amount} {trading_pair} "
                f"{quantized_price}.",
                exc_info=True,
                app_warning_msg=str(e)
            )
            order_update: OrderUpdate = OrderUpdate(
                client_order_id=order_id,
                trading_pair=trading_pair,
                update_timestamp=self.current_timestamp,
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
                exchange_order_id = await tracked_order.get_exchange_order_id()
                api_json = {"id": exchange_order_id}
                cancel_result = await self._api_request(
                    method=RESTMethod.POST,
                    path_url=CONSTANTS.ORDER_CANCEL_PATH_URL,
                    data=api_json,
                    is_auth_required=True)

                order_cancel_status = cancel_result.get("status")
                if order_cancel_status == "SUCCESS":

                    order_update: OrderUpdate = OrderUpdate(
                        client_order_id=order_id,
                        trading_pair=tracked_order.trading_pair,
                        update_timestamp=self.current_timestamp,
                        new_state=OrderState.CANCELED,
                    )

                    self._order_tracker.process_order_update(order_update)
                    return order_id
                else:  # order_cancel_status == "FAILURE":
                    raise ValueError(f"Cancel order failed, no SUCCESS message {order_cancel_status}")

            except asyncio.CancelledError:
                raise
            except asyncio.TimeoutError:
                self.logger().warning(f"Failed to cancel the order {order_id} because it does not have an exchange"
                                      f" order id yet")
                await self._order_tracker.process_order_not_found(order_id)
            except Exception:
                self.logger().network(
                    f"Unexpected error canceling order {order_id}.",
                    exc_info=True,
                    app_warning_msg="Failed to cancel order. Check API key and network connection."
                )

    async def _status_polling_loop(self):
        """
        Performs all required operation to keep the connector updated and synchronized with the exchange.
        It contains the backup logic to update status using API requests in case the main update source (the user stream
        data source websocket) fails.
        It also updates the time synchronizer. This is necessary because Latoken require the time of the client to be
        the same as the time in the exchange.
        Executes when the _poll_notifier event is enabled by the `tick` function.
        """
        while True:
            try:
                await self._poll_notifier.wait()
                await self._update_time_synchronizer()
                await safe_gather(
                    self._update_balances(),
                )
                await self._update_order_status()
                self._last_poll_timestamp = self.current_timestamp

                self._poll_notifier = asyncio.Event()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unexpected error while fetching account updates.", exc_info=True, app_warning_msg=
                    "Could not fetch account updates from Latoken. Check API key and network connection.")
                await asyncio.sleep(0.5)

    async def _trading_rules_polling_loop(self):
        """
        Updates the trading rules by requesting the latest definitions from the exchange.
        Executes regularly every 30 minutes
        """
        while True:
            try:
                await self._update_trading_rules()
                await asyncio.sleep(CONSTANTS.THIRTY_MINUTES)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unexpected error while fetching trading rules.", exc_info=True,
                    app_warning_msg="Could not fetch new trading rules from Latoken. Check network connection.")
                await asyncio.sleep(0.5)

    async def _trading_fees_polling_loop(self):
        while True:
            try:
                await self._update_trading_fees()
                await asyncio.sleep(CONSTANTS.TWELVE_HOURS)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unexpected error while fetching trading fees.", exc_info=True,
                    app_warning_msg="Could not fetch new trading fees from Latoken. Check network connection.")
                await asyncio.sleep(0.5)

    async def _update_trading_rules(self):
        ticker_list, currency_list, pair_list = await safe_gather(
            self._api_request(method=RESTMethod.GET, path_url=CONSTANTS.TICKER_PATH_URL),
            self._api_request(method=RESTMethod.GET, path_url=CONSTANTS.CURRENCY_PATH_URL),
            self._api_request(method=RESTMethod.GET, path_url=CONSTANTS.PAIR_PATH_URL),
            return_exceptions=True)

        pairs = web_utils.create_full_mapping(ticker_list, currency_list, pair_list)
        trading_rules_list = await self._format_trading_rules(pairs)

        self._trading_rules.clear()
        for trading_rule in trading_rules_list:
            self._trading_rules[trading_rule.trading_pair] = trading_rule

    async def _update_trading_fees(self):
        fee_requests = [self._api_request(
            method=RESTMethod.GET,
            path_url=f"{CONSTANTS.FEES_PATH_URL}/{trading_pair.replace('-', '/')}",
            is_auth_required=True) for trading_pair in self._trading_pairs]
        responses = zip(self._trading_pairs, await safe_gather(*fee_requests, return_exceptions=True))
        for trading_pair, response in responses:
            self._trading_fees[trading_pair] = None if isinstance(response, Exception) else LatokenFeeSchema(response)

    async def _update_order_status(self):
        # This is intended to be a backup measure to close straggler orders, in case Latoken's user stream events
        # are not working.
        # The minimum poll interval for order status is 10 seconds.
        last_tick = self._last_poll_timestamp / CONSTANTS.UPDATE_ORDER_STATUS_MIN_INTERVAL
        current_tick = self.current_timestamp / CONSTANTS.UPDATE_ORDER_STATUS_MIN_INTERVAL

        tracked_orders: List[InFlightOrder] = list(self.in_flight_orders.values())

        if current_tick <= last_tick or len(tracked_orders) == 0:
            return
        # if current_tick > last_tick and len(tracked_orders) > 0:
        # not sure if the exchange order id is always up-to-date on the moment this function is called (?)

        reviewed_orders = []
        tasks = []

        for tracked_order in tracked_orders:
            try:
                exchange_order_id = await tracked_order.get_exchange_order_id()
            except asyncio.TimeoutError:
                self.logger().debug(
                    f"Tracked order {tracked_order.client_order_id} does not have an exchange id. "
                    f"Attempting fetch in next polling interval."
                )
                await self._order_tracker.process_order_not_found(tracked_order.client_order_id)
                continue
            reviewed_orders.append(tracked_order)
            tasks.append(
                self._api_request(
                    method=RESTMethod.GET,
                    path_url=f"{CONSTANTS.GET_ORDER_PATH_URL}/{exchange_order_id}",
                    is_auth_required=True,
                    return_err=False))

        self.logger().debug(f"Polling for order status updates of {len(tasks)} orders.")
        results = await safe_gather(*tasks, return_exceptions=True)
        for order_update, tracked_order in zip(results, reviewed_orders):
            client_order_id = tracked_order.client_order_id

            # If the order has already been cancelled or has failed do nothing
            if client_order_id not in self.in_flight_orders:
                continue

            if isinstance(order_update, Exception):
                self.logger().network(
                    f"Error fetching status update for the order {client_order_id}: {order_update}.",
                    app_warning_msg=f"Failed to fetch status update for the order {client_order_id}."
                )
                # Wait until the order not found error have repeated a few times before actually treating
                # it as failed. See: https://github.com/CoinAlpha/hummingbot/issues/601
                await self._order_tracker.process_order_not_found(client_order_id)
            else:
                # Update order execution status
                status = order_update["status"]
                filled = Decimal(order_update["filled"])
                quantity = Decimal(order_update["quantity"])

                new_state = web_utils.get_order_status_rest(status=status, filled=filled, quantity=quantity)

                update = OrderUpdate(
                    client_order_id=client_order_id,
                    exchange_order_id=order_update["id"],
                    trading_pair=tracked_order.trading_pair,
                    update_timestamp=float(order_update["timestamp"]) * 1e-3,
                    new_state=new_state,
                )
                self._order_tracker.process_order_update(update)

    async def _update_balances(self):
        try:
            params = {'zeros': 'false'}  # if not testing this can be set to the default of false
            balances = await self._api_request(
                method=RESTMethod.GET, path_url=CONSTANTS.ACCOUNTS_PATH_URL, is_auth_required=True, params=params)
            remote_asset_names = await self._process_account_balance_update(balances)
            self._process_full_account_balances_refresh(remote_asset_names, balances)
        except IOError:
            self.logger().exception("Error getting account balances from server")

    async def _update_time_synchronizer(self):
        try:
            await self._latoken_time_synchronizer.update_server_time_offset_with_time_provider(
                time_provider=web_utils.get_current_server_time(
                    throttler=self._throttler,
                    domain=self._domain,
                )
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Error requesting time from Latoken server")
            raise

    async def _format_trading_rules(self, pairs_list: List[Any]) -> List[TradingRule]:
        """
        Example: https://api.latoken.com/doc/v2/#tag/Pair
        [
            {
            "id": "263d5e99-1413-47e4-9215-ce4f5dec3556",
            "status": "PAIR_STATUS_ACTIVE",
            "baseCurrency": "6ae140a9-8e75-4413-b157-8dd95c711b23",
            "quoteCurrency": "23fa548b-f887-4f48-9b9b-7dd2c7de5ed0",
            "priceTick": "0.010000000",
            "priceDecimals": 2,
            "quantityTick": "0.010000000",
            "quantityDecimals": 2,
            "costDisplayDecimals": 3,
            "created": 1571333313871,
            "minOrderQuantity": "0",
            "maxOrderCostUsd": "999999999999999999",
            "minOrderCostUsd": "0",
            "externalSymbol": ""
            }
        ]
        """
        trading_rules = []
        for rule in filter(is_exchange_information_valid, pairs_list):
            try:
                symbol = f"{rule['id']['baseCurrency']}/{rule['id']['quoteCurrency']}"
                trading_pair = await LatokenAPIOrderBookDataSource.trading_pair_associated_to_exchange_symbol(
                    symbol=symbol, domain=self._domain, api_factory=self._api_factory, throttler=self._throttler)

                min_order_size = Decimal(rule["minOrderQuantity"])
                price_tick = Decimal(rule["priceTick"])
                quantity_tick = Decimal(rule["quantityTick"])
                min_order_value = Decimal(rule["minOrderCostUsd"])
                min_order_quantity = Decimal(rule["minOrderQuantity"])

                trading_rule = TradingRule(
                    trading_pair,
                    min_order_size=max(min_order_size, quantity_tick),
                    min_price_increment=price_tick,
                    min_base_amount_increment=quantity_tick,
                    min_quote_amount_increment=price_tick,
                    min_notional_size=min_order_quantity,
                    min_order_value=min_order_value,
                    # max_price_significant_digits=len(rule["maxOrderCostUsd"])
                    # supports_market_orders = False,
                )

                trading_rules.append(trading_rule)

            except Exception:
                self.logger().exception(f"Error parsing the trading pair rule {rule}. Skipping.")
        return trading_rules

    def _get_trade_update(self, trade, trading_pair: str):
        trade_update = None
        timestamp = trade["timestamp"]
        if timestamp < self._last_update_trade_fees_timestamp:  # currently always true
            return trade_update
        exchange_order_id = trade["order"]
        tracked_order = self._order_tracker.fetch_order(exchange_order_id=exchange_order_id)
        if tracked_order is None:
            return trade_update

        trade_id = trade["id"]
        fee = Decimal(trade["fee"])
        price = Decimal(trade["price"])
        quantity = Decimal(trade["quantity"])

        spot_fee = TradeFeeBase.new_spot_fee(
            fee_schema=self.trade_fee_schema(), trade_type=tracked_order.trade_type,
            percent_token=tracked_order.quote_asset,
            flat_fees=[TokenAmount(amount=fee, token=tracked_order.quote_asset)])
        # This is a fill for a tracked order
        trade_update = TradeUpdate(
            trade_id=trade_id,
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=trading_pair,  # or tracked_order.trading_pair
            fill_timestamp=int(timestamp),
            fill_price=price,
            fill_base_amount=quantity,
            fill_quote_amount=Decimal(trade["cost"]),
            fee=spot_fee,
        )
        return trade_update

    def _db_tracked_order_candidate(self, trade, trading_pair: str):
        # This is a fill of an order registered in the DB but not tracked any more
        base_currency, quote_currency = trading_pair.split('-')
        trade_type = TradeType.BUY if trade["makerBuyer"] else TradeType.SELL
        order_type = OrderType.LIMIT
        amount = Decimal(trade["quantity"])
        price = Decimal(trade["price"])
        trade_id = trade["id"]
        exchange_order_id = trade["order"]
        client_order_id = self._exchange_order_ids.get(exchange_order_id, None)
        fee = Decimal(trade["fee"])
        trade_fee = TradeFeeBase.new_spot_fee(
            fee_schema=self.trade_fee_schema(), trade_type=trade_type,
            percent_token=quote_currency,
            flat_fees=[TokenAmount(amount=fee, token=quote_currency)])

        # trade_fee = self.get_fee(base_currency, quote_currency, order_type, trade_type, amount, price, is_maker)
        self._current_trade_fills.add(TradeFillOrderDetails(
            market=self.display_name,
            exchange_trade_id=trade_id,
            symbol=trading_pair))

        self.trigger_event(
            MarketEvent.OrderFilled,
            OrderFilledEvent(
                timestamp=float(trade["timestamp"]) * 1e-3,
                order_id=client_order_id,
                trading_pair=trading_pair,
                trade_type=trade_type,
                order_type=order_type,
                price=price,
                amount=amount,
                trade_fee=trade_fee,
                exchange_trade_id=trade_id
            ))
        self.logger().info(f"Recreating missing trade in TradeFill: {trade}")

    async def _process_account_balance_update(self, balances):
        remote_asset_names = set()

        balance_to_gather = [
            self._api_request(
                method=RESTMethod.GET, path_url=f"{CONSTANTS.CURRENCY_PATH_URL}/{balance['currency']}")
            for balance in balances]

        # maybe request every currency if len(account_balance) > 5
        currency_lists = await safe_gather(*balance_to_gather, return_exceptions=True)

        currencies = {currency["id"]: currency["tag"] for currency in currency_lists if
                      isinstance(currency, dict) and currency["status"] != 'FAILURE'}

        for balance in balances:
            if balance['status'] == "FAILURE" and balance['error'] == 'NOT_FOUND':
                self.logger().error(f"Could not resolve currency details for balance={balance}")
                continue
            asset_name = currencies.get(balance["currency"], None)
            if asset_name is None or balance["type"] != "ACCOUNT_TYPE_SPOT":
                if asset_name is None:
                    self.logger().error(f"Could not resolve currency details for balance={balance}")
                continue
            free_balance = Decimal(balance["available"])
            total_balance = free_balance + Decimal(balance["blocked"])
            self._account_available_balances[asset_name] = free_balance
            self._account_balances[asset_name] = total_balance
            remote_asset_names.add(asset_name)

        return remote_asset_names

    def _process_full_account_balances_refresh(self, remote_asset_names, balances):
        """ use this for rest call and not ws because ws does not send entire account balance list"""
        local_asset_names = set(self._account_balances.keys())
        if not balances:
            self.logger().warning("Fund your latoken account, no balances in your account!")
        has_spot_balances = any(filter(lambda b: b["type"] == "ACCOUNT_TYPE_SPOT", balances))
        if balances and not has_spot_balances:
            self.logger().warning(
                "No latoken SPOT balance! Account has balances but no SPOT balance! Transfer to Latoken SPOT account!")
        # clean-up balances that are not present anymore
        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

    def _process_trade_update_ws(self, trade_update, trading_pair: str):
        tu = self._get_trade_update(trade_update, trading_pair)
        if tu is not None:
            self._order_tracker.process_trade_update(tu)
        elif self.is_confirmed_new_order_filled_event(trade_update["id"], trade_update["order"], trading_pair):
            self._db_tracked_order_candidate(trade_update, trading_pair)

    def _process_order_update_ws(self, order):
        client_order_id = order['clientOrderId']

        change_type = order['changeType']
        status = order['status']
        quantity = Decimal(order["quantity"])
        filled = Decimal(order['filled'])
        delta_filled = Decimal(order['deltaFilled'])

        state = web_utils.get_order_status_ws(change_type, status, quantity, filled, delta_filled)
        if state is None:
            return

        timestamp = float(order["timestamp"]) * 1e-3

        tracked_order = self._order_tracker.fetch_tracked_order(client_order_id)

        if tracked_order is not None:
            order_update = OrderUpdate(
                trading_pair=tracked_order.trading_pair,
                update_timestamp=timestamp,
                new_state=state,
                client_order_id=client_order_id,
                exchange_order_id=tracked_order.exchange_order_id,
            )
            self._order_tracker.process_order_update(order_update=order_update)

    async def _user_stream_event_listener(self):
        """
        This functions runs in background continuously processing the events received from the exchange by the user
        stream data source. It keeps reading events from the queue until the task is interrupted.
        The events received are balance updates, order updates and trade events.
        """
        async for event_message in self._iter_user_event_queue():
            try:
                cmd = event_message.get('cmd', None)
                if cmd and cmd == 'MESSAGE':
                    subscription_id = int(event_message['headers']['subscription'].split('_')[0])
                    body = ujson.loads(event_message["body"])

                    if subscription_id == CONSTANTS.SUBSCRIPTION_ID_ORDERS:
                        for order in body["payload"]:  # self.logger().error(str(orders))
                            self._process_order_update_ws(order)
                    elif subscription_id == CONSTANTS.SUBSCRIPTION_ID_TRADE_UPDATE:
                        for trade_update in body["payload"]:
                            self._process_trade_update_ws(
                                trade_update,
                                trading_pair=await LatokenAPIOrderBookDataSource.trading_pair_associated_to_exchange_symbol(
                                    symbol=f"{trade_update['baseCurrency']}/{trade_update['quoteCurrency']}",
                                    domain=self._domain, api_factory=self._api_factory, throttler=self._throttler))
                    elif subscription_id == CONSTANTS.SUBSCRIPTION_ID_ACCOUNT:
                        _ = await self._process_account_balance_update(balances=body["payload"])
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Unexpected error in user stream listener loop.", exc_info=True)
                await asyncio.sleep(5.0)

    async def _iter_user_event_queue(self) -> AsyncIterable[Dict[str, any]]:
        while True:
            try:
                yield await self._user_stream_tracker.user_stream.get()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Error while reading user events queue. Retrying after 1 second.")
                await asyncio.sleep(1.0)

    async def _api_request(self,
                           method: RESTMethod,
                           path_url: str,
                           params: Optional[Dict[str, Any]] = None,
                           data: Optional[Dict[str, Any]] = None,
                           is_auth_required: bool = False,
                           return_err=True) -> Dict[str, Any]:

        return await web_utils.api_request(
            path=path_url,
            api_factory=self._api_factory,
            throttler=self._throttler,
            time_synchronizer=self._latoken_time_synchronizer,
            domain=self._domain,
            params=params,
            data=data,
            method=method,
            is_auth_required=is_auth_required,
            return_err=return_err,
            limit_id=CONSTANTS.GLOBAL_RATE_LIMIT
        )

    async def _get_rest_assistant(self) -> RESTAssistant:
        if self._rest_assistant is None:
            self._rest_assistant = await self._api_factory.get_rest_assistant()
        return self._rest_assistant
