import asyncio
import copy
import logging
import math
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import TYPE_CHECKING, Any, AsyncIterable, Callable, Dict, List, Optional, Tuple

from async_timeout import timeout

from hummingbot.connector.client_order_tracker import ClientOrderTracker
from hummingbot.connector.constants import MINUTE, TWELVE_HOURS, s_decimal_0, s_decimal_NaN
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import get_new_client_order_id
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_tracker import OrderBookTracker
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee
from hummingbot.core.data_type.user_stream_tracker import UserStreamTracker
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.logger import HummingbotLogger

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class ExchangePyBase(ExchangeBase, ABC):
    _logger = None

    SHORT_POLL_INTERVAL = 5.0
    LONG_POLL_INTERVAL = 120.0
    TRADING_RULES_INTERVAL = 30 * MINUTE
    TRADING_FEES_INTERVAL = TWELVE_HOURS
    TICK_INTERVAL_LIMIT = 60.0

    def __init__(self, client_config_map: "ClientConfigAdapter"):
        super().__init__(client_config_map)

        self._last_poll_timestamp = 0
        self._last_timestamp = 0
        self._trading_rules = {}
        self._trading_fees = {}

        self._status_polling_task: Optional[asyncio.Task] = None
        self._user_stream_tracker_task: Optional[asyncio.Task] = None
        self._user_stream_event_listener_task: Optional[asyncio.Task] = None
        self._trading_rules_polling_task: Optional[asyncio.Task] = None
        self._trading_fees_polling_task: Optional[asyncio.Task] = None
        self._lost_orders_update_task: Optional[asyncio.Task] = None

        self._time_synchronizer = TimeSynchronizer()
        self._throttler = AsyncThrottler(
            rate_limits=self.rate_limits_rules,
            limits_share_percentage=client_config_map.rate_limits_share_pct)
        self._poll_notifier = asyncio.Event()

        # init Auth and Api factory
        self._auth: AuthBase = self.authenticator
        self._web_assistants_factory: WebAssistantsFactory = self._create_web_assistants_factory()

        # init OrderBook Data Source and Tracker
        self._orderbook_ds: OrderBookTrackerDataSource = self._create_order_book_data_source()
        self._set_order_book_tracker(OrderBookTracker(
            data_source=self._orderbook_ds,
            trading_pairs=self.trading_pairs,
            domain=self.domain))

        # init UserStream Data Source and Tracker
        self._user_stream_tracker = self._create_user_stream_tracker()

        self._order_tracker: ClientOrderTracker = self._create_order_tracker()

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(HummingbotLogger.logger_name_for_class(cls))
        return cls._logger

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def authenticator(self) -> AuthBase:
        raise NotImplementedError

    @property
    @abstractmethod
    def rate_limits_rules(self) -> List[RateLimit]:
        raise NotImplementedError

    @property
    @abstractmethod
    def domain(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def client_order_id_max_length(self) -> int:
        raise NotImplementedError

    @property
    @abstractmethod
    def client_order_id_prefix(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def trading_rules_request_path(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def trading_pairs_request_path(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def check_network_request_path(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def trading_pairs(self) -> List[str]:
        raise NotImplementedError

    @property
    @abstractmethod
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        raise NotImplementedError

    @property
    @abstractmethod
    def is_trading_required(self) -> bool:
        raise NotImplementedError

    @property
    def order_books(self) -> Dict[str, OrderBook]:
        return self.order_book_tracker.order_books

    @property
    def in_flight_orders(self) -> Dict[str, InFlightOrder]:
        return self._order_tracker.active_orders

    @property
    def trading_rules(self) -> Dict[str, TradingRule]:
        return self._trading_rules

    @property
    def limit_orders(self) -> List[LimitOrder]:
        return [in_flight_order.to_limit_order() for in_flight_order in self.in_flight_orders.values()]

    @property
    def status_dict(self) -> Dict[str, bool]:
        return {
            "symbols_mapping_initialized": self.trading_pair_symbol_map_ready(),
            "order_books_initialized": self.order_book_tracker.ready,
            "account_balance": not self.is_trading_required or len(self._account_balances) > 0,
            "trading_rule_initialized": len(self._trading_rules) > 0 if self.is_trading_required else True,
            "user_stream_initialized": self._is_user_stream_initialized(),
        }

    @property
    def ready(self) -> bool:
        """
        Returns True if the connector is ready to operate (all connections established with the exchange). If it is
        not ready it returns False.
        """
        return all(self.status_dict.values())

    @property
    def name_cap(self) -> str:
        return self.name.capitalize()

    @property
    def tracking_states(self) -> Dict[str, any]:
        """
        Returns a dictionary associating current active orders client id to their JSON representation
        """
        return {key: value.to_json() for key, value in self._order_tracker.all_updatable_orders.items()}

    @abstractmethod
    def supported_order_types(self) -> List[OrderType]:
        raise NotImplementedError

    @abstractmethod
    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception) -> bool:
        raise NotImplementedError

    @abstractmethod
    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        raise NotImplementedError

    @abstractmethod
    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        raise NotImplementedError

    # === Price logic ===

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

    def get_order_book(self, trading_pair: str) -> OrderBook:
        """
        Returns the current order book for a particular market

        :param trading_pair: the pair of tokens for which the order book should be retrieved
        """
        if trading_pair not in self.order_book_tracker.order_books:
            raise ValueError(f"No order book exists for '{trading_pair}'.")
        return self.order_book_tracker.order_books[trading_pair]

    def tick(self, timestamp: float):
        """
        Includes the logic that has to be processed every time a new tick happens in the bot. Particularly it enables
        the execution of the status update polling loop using an event.
        """
        poll_interval = self._get_poll_interval(timestamp=timestamp)
        last_tick = int(self._last_timestamp / poll_interval)
        current_tick = int(timestamp / poll_interval)
        if current_tick > last_tick:
            self._poll_notifier.set()
        self._last_timestamp = timestamp

    # === Orders placing ===

    def buy(self,
            trading_pair: str,
            amount: Decimal,
            order_type=OrderType.LIMIT,
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
            hbot_order_id_prefix=self.client_order_id_prefix,
            max_id_len=self.client_order_id_max_length
        )
        safe_ensure_future(self._create_order(
            trade_type=TradeType.BUY,
            order_id=order_id,
            trading_pair=trading_pair,
            amount=amount,
            order_type=order_type,
            price=price,
            **kwargs))
        return order_id

    def sell(self,
             trading_pair: str,
             amount: Decimal,
             order_type: OrderType = OrderType.LIMIT,
             price: Decimal = s_decimal_NaN,
             **kwargs) -> str:
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
            hbot_order_id_prefix=self.client_order_id_prefix,
            max_id_len=self.client_order_id_max_length
        )
        safe_ensure_future(self._create_order(
            trade_type=TradeType.SELL,
            order_id=order_id,
            trading_pair=trading_pair,
            amount=amount,
            order_type=order_type,
            price=price,
            **kwargs))
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
        Calculates the fee to pay based on the fee information provided by the exchange for
        the account and the token pair. If exchange info is not available it calculates the estimated
        fee an order would pay based on the connector configuration.

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

    def cancel(self, trading_pair: str, client_order_id: str):
        """
        Creates a promise to cancel an order in the exchange

        :param trading_pair: the trading pair the order to cancel operates with
        :param client_order_id: the client id of the order to cancel

        :return: the client id of the order to cancel
        """
        safe_ensure_future(self._execute_cancel(trading_pair, client_order_id))
        return client_order_id

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
                    client_order_id = cr
                    if client_order_id is not None:
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
                            price: Optional[Decimal] = None,
                            **kwargs):
        """
        Creates an order in the exchange using the parameters to configure it

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
        quantized_amount = self.quantize_order_amount(trading_pair=trading_pair, amount=amount)

        self.start_tracking_order(
            order_id=order_id,
            exchange_order_id=None,
            trading_pair=trading_pair,
            order_type=order_type,
            trade_type=trade_type,
            price=price,
            amount=quantized_amount,
            **kwargs,
        )
        order = self._order_tracker.active_orders[order_id]
        if not price or price.is_nan() or price == s_decimal_0:
            current_price: Decimal = self.get_price(trading_pair, False)
            notional_size = current_price * quantized_amount
        else:
            notional_size = price * quantized_amount

        if order_type not in self.supported_order_types():
            self.logger().error(f"{order_type} is not in the list of supported order types")
            self._update_order_after_failure(order_id=order_id, trading_pair=trading_pair)
            return

        elif quantized_amount < trading_rule.min_order_size:
            self.logger().warning(f"{trade_type.name.title()} order amount {amount} is lower than the minimum order "
                                  f"size {trading_rule.min_order_size}. The order will not be created, increase the "
                                  f"amount to be higher than the minimum order size.")
            self._update_order_after_failure(order_id=order_id, trading_pair=trading_pair)
            return

        elif notional_size < trading_rule.min_notional_size:
            self.logger().warning(f"{trade_type.name.title()} order notional {notional_size} is lower than the "
                                  f"minimum notional size {trading_rule.min_notional_size}. The order will not be "
                                  f"created. Increase the amount or the price to be higher than the minimum notional.")
            self._update_order_after_failure(order_id=order_id, trading_pair=trading_pair)
            return
        try:
            await self._place_order_and_process_update(order=order, **kwargs,)

        except asyncio.CancelledError:
            raise
        except Exception as ex:
            self._on_order_failure(
                order_id=order_id,
                trading_pair=trading_pair,
                amount=quantized_amount,
                trade_type=trade_type,
                order_type=order_type,
                price=price,
                exception=ex,
                **kwargs,
            )

    async def _place_order_and_process_update(self, order: InFlightOrder, **kwargs) -> str:
        exchange_order_id, update_timestamp = await self._place_order(
            order_id=order.client_order_id,
            trading_pair=order.trading_pair,
            amount=order.amount,
            trade_type=order.trade_type,
            order_type=order.order_type,
            price=order.price,
            **kwargs,
        )

        order_update: OrderUpdate = OrderUpdate(
            client_order_id=order.client_order_id,
            exchange_order_id=str(exchange_order_id),
            trading_pair=order.trading_pair,
            update_timestamp=update_timestamp,
            new_state=OrderState.OPEN,
        )
        self._order_tracker.process_order_update(order_update)

        return exchange_order_id

    def _on_order_failure(
        self,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        trade_type: TradeType,
        order_type: OrderType,
        price: Optional[Decimal],
        exception: Exception,
        **kwargs,
    ):
        self.logger().network(
            f"Error submitting {trade_type.name.lower()} {order_type.name.upper()} order to {self.name_cap} for "
            f"{amount} {trading_pair} {price}.",
            exc_info=True,
            app_warning_msg=f"Failed to submit {trade_type.name.upper()} order to {self.name_cap}. Check API key and network connection."
        )
        self._update_order_after_failure(order_id=order_id, trading_pair=trading_pair)

    def _update_order_after_failure(self, order_id: str, trading_pair: str):
        order_update: OrderUpdate = OrderUpdate(
            client_order_id=order_id,
            trading_pair=trading_pair,
            update_timestamp=self.current_timestamp,
            new_state=OrderState.FAILED,
        )
        self._order_tracker.process_order_update(order_update)

    async def _execute_order_cancel(self, order: InFlightOrder) -> str:
        try:
            cancelled = await self._execute_order_cancel_and_process_update(order=order)
            if cancelled:
                return order.client_order_id
        except asyncio.CancelledError:
            raise
        except asyncio.TimeoutError:
            # some exchanges do not allow cancels with the client/user order id
            # so log a warning and wait for the creation of the order to complete
            self.logger().warning(
                f"Failed to cancel the order {order.client_order_id} because it does not have an exchange order id yet"
            )
            await self._order_tracker.process_order_not_found(order.client_order_id)
        except Exception as ex:
            if self._is_order_not_found_during_cancelation_error(cancelation_exception=ex):
                self.logger().warning(f"Failed to cancel order {order.client_order_id} (order not found)")
                await self._order_tracker.process_order_not_found(order.client_order_id)
            else:
                self.logger().error(f"Failed to cancel order {order.client_order_id}", exc_info=True)

    async def _execute_order_cancel_and_process_update(self, order: InFlightOrder) -> bool:
        cancelled = await self._place_cancel(order.client_order_id, order)
        if cancelled:
            update_timestamp = self.current_timestamp
            if update_timestamp is None or math.isnan(update_timestamp):
                update_timestamp = self._time()
            order_update: OrderUpdate = OrderUpdate(
                client_order_id=order.client_order_id,
                trading_pair=order.trading_pair,
                update_timestamp=update_timestamp,
                new_state=(OrderState.CANCELED
                           if self.is_cancel_request_in_exchange_synchronous
                           else OrderState.PENDING_CANCEL),
            )
            self._order_tracker.process_order_update(order_update)
        return cancelled

    async def _execute_cancel(self, trading_pair: str, order_id: str) -> str:
        """
        Requests the exchange to cancel an active order

        :param trading_pair: the trading pair the order to cancel operates with
        :param order_id: the client id of the order to cancel
        """
        result = None
        tracked_order = self._order_tracker.fetch_tracked_order(order_id)
        if tracked_order is not None:
            result = await self._execute_order_cancel(order=tracked_order)

        return result

    # === Order Tracking ===

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
                             order_type: OrderType,
                             **kwargs):
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

    # === Implementation-specific methods ===

    @abstractmethod
    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        raise NotImplementedError

    @abstractmethod
    async def _place_order(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           trade_type: TradeType,
                           order_type: OrderType,
                           price: Decimal,
                           **kwargs,
                           ) -> Tuple[str, float]:
        raise NotImplementedError

    @abstractmethod
    def _get_fee(self,
                 base_currency: str,
                 quote_currency: str,
                 order_type: OrderType,
                 order_side: TradeType,
                 amount: Decimal,
                 price: Decimal = s_decimal_NaN,
                 is_maker: Optional[bool] = None) -> AddedToCostTradeFee:
        raise NotImplementedError

    # === Network-API-related code ===

    # overridden in implementation of exchanges
    #
    web_utils = None

    async def start_network(self):
        """
        Start all required tasks to update the status of the connector. Those tasks include:
        - The order book tracker
        - The polling loops to update the trading rules and trading fees
        - The polling loop to update order status and balance status using REST API (backup for main update process)
        - The background task to process the events received through the user stream tracker (websocket connection)
        """
        self._stop_network()
        self.order_book_tracker.start()
        if self.is_trading_required:
            self._trading_rules_polling_task = safe_ensure_future(self._trading_rules_polling_loop())
            self._trading_fees_polling_task = safe_ensure_future(self._trading_fees_polling_loop())
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())
            self._user_stream_tracker_task = self._create_user_stream_tracker_task()
            self._user_stream_event_listener_task = safe_ensure_future(self._user_stream_event_listener())
            self._lost_orders_update_task = safe_ensure_future(self._lost_orders_update_polling_loop())

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
            await self._make_network_check_request()
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    def _stop_network(self):
        # Resets timestamps and events for status_polling_loop
        self._last_poll_timestamp = 0
        self._last_timestamp = 0
        self._poll_notifier = asyncio.Event()

        self.order_book_tracker.stop()
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
        if self._lost_orders_update_task is not None:
            self._lost_orders_update_task.cancel()
            self._lost_orders_update_task = None

    # === loops and sync related methods ===
    #
    async def _trading_rules_polling_loop(self):
        """
        Updates the trading rules by requesting the latest definitions from the exchange.
        Executes regularly every 30 minutes
        """
        while True:
            try:
                await safe_gather(self._update_trading_rules())
                await self._sleep(self.TRADING_RULES_INTERVAL)
            except NotImplementedError:
                raise
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unexpected error while fetching trading rules.", exc_info=True,
                    app_warning_msg=f"Could not fetch new trading rules from {self.name_cap}"
                                    " Check network connection.")
                await self._sleep(0.5)

    async def _trading_fees_polling_loop(self):
        """
        Only some exchanges provide a fee endpoint.
        If _update_trading_fees() is not defined, we just exit the loop
        """
        while True:
            try:
                await safe_gather(self._update_trading_fees())
                await self._sleep(self.TRADING_FEES_INTERVAL)
            except NotImplementedError:
                raise
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unexpected error while fetching trading fees.", exc_info=True,
                    app_warning_msg=f"Could not fetch new trading fees from {self.name_cap}."
                                    " Check network connection.")
                await self._sleep(0.5)

    async def _status_polling_loop(self):
        """
        Performs all required operation to keep the connector updated and synchronized with the exchange.
        It contains the backup logic to update status using API requests in case the main update source
        (the user stream data source websocket) fails.
        It also updates the time synchronizer. This is necessary because the exchange requires
        the time of the client to be the same as the time in the exchange.
        Executes when the _poll_notifier event is enabled by the `tick` function.
        """
        while True:
            try:
                await self._poll_notifier.wait()
                await self._update_time_synchronizer()

                # the following method is implementation-specific
                await self._status_polling_loop_fetch_updates()

                self._last_poll_timestamp = self.current_timestamp
                self._poll_notifier = asyncio.Event()
            except asyncio.CancelledError:
                raise
            except NotImplementedError:
                raise
            except Exception:
                self.logger().network(
                    "Unexpected error while fetching account updates.",
                    exc_info=True,
                    app_warning_msg=f"Could not fetch account updates from {self.name_cap}. "
                                    "Check API key and network connection.")
                await self._sleep(0.5)

    async def _update_time_synchronizer(self, pass_on_non_cancelled_error: bool = False):
        try:
            await self._time_synchronizer.update_server_time_offset_with_time_provider(
                time_provider=self.web_utils.get_current_server_time(
                    throttler=self._throttler,
                    domain=self.domain,
                )
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            if not pass_on_non_cancelled_error:
                self.logger().exception(f"Error requesting time from {self.name_cap} server")
                raise

    async def _lost_orders_update_polling_loop(self):
        """
        This loop regularly executes the update of lost orders, to keep receiving any new order fill or status change
        until we are totally sure the order is no longer alive in the exchange
        """
        while True:
            try:
                await self._cancel_lost_orders()
                await self._update_lost_orders_status()
                await self._sleep(self.SHORT_POLL_INTERVAL)
            except NotImplementedError:
                raise
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error while updating the time synchronizer")
                await self._sleep(0.5)

    async def _iter_user_event_queue(self) -> AsyncIterable[Dict[str, any]]:
        """
        Called by _user_stream_event_listener.
        """
        while True:
            try:
                yield await self._user_stream_tracker.user_stream.get()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Error while reading user events queue. Retrying in 1s.")
                await self._sleep(1.0)

    def _is_user_stream_initialized(self):
        return self._user_stream_tracker.data_source.last_recv_time > 0 or not self.is_trading_required

    def _create_user_stream_tracker(self):
        return UserStreamTracker(data_source=self._create_user_stream_data_source())

    def _create_user_stream_tracker_task(self):
        return safe_ensure_future(self._user_stream_tracker.start())

    # === Exchange / Trading logic methods that call the API ===

    async def _update_trading_rules(self):
        exchange_info = await self._make_trading_rules_request()
        trading_rules_list = await self._format_trading_rules(exchange_info)
        self._trading_rules.clear()
        for trading_rule in trading_rules_list:
            self._trading_rules[trading_rule.trading_pair] = trading_rule
        self._initialize_trading_pair_symbols_from_exchange_info(exchange_info=exchange_info)

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

    async def _api_request_url(self, path_url: str, is_auth_required: bool = False) -> str:
        if is_auth_required:
            url = self.web_utils.private_rest_url(path_url, domain=self.domain)
        else:
            url = self.web_utils.public_rest_url(path_url, domain=self.domain)

        return url

    async def _api_request(
            self,
            path_url,
            overwrite_url: Optional[str] = None,
            method: RESTMethod = RESTMethod.GET,
            params: Optional[Dict[str, Any]] = None,
            data: Optional[Dict[str, Any]] = None,
            is_auth_required: bool = False,
            return_err: bool = False,
            limit_id: Optional[str] = None,
            headers: Optional[Dict[str, Any]] = None,
            **kwargs,
    ) -> Dict[str, Any]:

        last_exception = None
        rest_assistant = await self._web_assistants_factory.get_rest_assistant()

        url = overwrite_url or await self._api_request_url(path_url=path_url, is_auth_required=is_auth_required)

        for _ in range(2):
            try:
                request_result = await rest_assistant.execute_request(
                    url=url,
                    params=params,
                    data=data,
                    method=method,
                    is_auth_required=is_auth_required,
                    return_err=return_err,
                    throttler_limit_id=limit_id if limit_id else path_url,
                    headers=headers,
                )

                return request_result
            except IOError as request_exception:
                last_exception = request_exception
                if self._is_request_exception_related_to_time_synchronizer(request_exception=request_exception):
                    await self._update_time_synchronizer()
                else:
                    raise

        # Failed even after the last retry
        raise last_exception

    async def _status_polling_loop_fetch_updates(self):
        """
        Called by _status_polling_loop, which executes after each tick() is executed
        """
        await safe_gather(
            self._update_all_balances(),
            self._update_order_status(),
        )

    async def _update_all_balances(self):
        try:
            await self._update_balances()
            if not self.real_time_balance_update:
                # This is only required for exchanges that do not provide balance update notifications through websocket
                self._in_flight_orders_snapshot = {k: copy.copy(v) for k, v in self.in_flight_orders.items()}
                self._in_flight_orders_snapshot_timestamp = self.current_timestamp
        except asyncio.CancelledError:
            raise
        except Exception as request_error:
            self.logger().warning(
                f"Failed to update balances. Error: {request_error}",
                exc_info=request_error,
            )

    async def _update_orders_fills(self, orders: List[InFlightOrder]):
        for order in orders:
            try:
                trade_updates = await self._all_trade_updates_for_order(order=order)
                for trade_update in trade_updates:
                    self._order_tracker.process_trade_update(trade_update)
            except asyncio.CancelledError:
                raise
            except Exception as request_error:
                self.logger().warning(
                    f"Failed to fetch trade updates for order {order.client_order_id}. Error: {request_error}",
                    exc_info=request_error,
                )

    async def _handle_update_error_for_active_order(self, order: InFlightOrder, error: Exception):
        try:
            raise error
        except asyncio.TimeoutError:
            self.logger().debug(
                f"Tracked order {order.client_order_id} does not have an exchange id. "
                f"Attempting fetch in next polling interval."
            )
            await self._order_tracker.process_order_not_found(order.client_order_id)
        except asyncio.CancelledError:
            raise
        except Exception as request_error:
            self.logger().warning(
                f"Error fetching status update for the active order {order.client_order_id}: {request_error}.",
            )
            self.logger().debug(f"Order {order.client_order_id} not found counter: {self._order_tracker._order_not_found_records.get(order.client_order_id, 0)}")
            await self._order_tracker.process_order_not_found(order.client_order_id)

    async def _handle_update_error_for_lost_order(self, order: InFlightOrder, error: Exception):
        is_not_found = self._is_order_not_found_during_status_update_error(status_update_exception=error)
        self.logger().debug(f"Order update error for lost order {order.client_order_id}\n{order}\nIs order not found: {is_not_found} ({error})")
        if is_not_found:
            self._update_order_after_failure(order.client_order_id, order.trading_pair)
        else:
            self.logger().warning(f"Error fetching status update for the lost order {order.client_order_id}: {error}.")

    async def _update_orders_with_error_handler(self, orders: List[InFlightOrder], error_handler: Callable):
        for order in orders:
            try:
                order_update = await self._request_order_status(tracked_order=order)
                self._order_tracker.process_order_update(order_update)
            except asyncio.CancelledError:
                raise
            except Exception as request_error:
                await error_handler(order, request_error)

    async def _update_orders(self):
        orders_to_update = self.in_flight_orders.copy()
        await self._update_orders_with_error_handler(
            orders=list(orders_to_update.values()), error_handler=self._handle_update_error_for_active_order
        )

    async def _update_lost_orders(self):
        orders_to_update = self._order_tracker.lost_orders.copy()
        await self._update_orders_with_error_handler(
            orders=list(orders_to_update.values()), error_handler=self._handle_update_error_for_lost_order
        )

    async def _update_order_status(self):
        await self._update_orders_fills(orders=list(self._order_tracker.all_fillable_orders.values()))
        await self._update_orders()

    async def _update_lost_orders_status(self):
        await self._update_orders_fills(orders=list(self._order_tracker.lost_orders.values()))
        await self._update_lost_orders()

    async def _cancel_lost_orders(self):
        for _, lost_order in self._order_tracker.lost_orders.items():
            await self._execute_order_cancel(order=lost_order)

    # Methods tied to specific API data formats
    #
    @abstractmethod
    async def _update_trading_fees(self):
        raise NotImplementedError

    @abstractmethod
    async def _user_stream_event_listener(self):
        raise NotImplementedError

    @abstractmethod
    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        raise NotImplementedError

    @abstractmethod
    async def _update_balances(self):
        raise NotImplementedError

    @abstractmethod
    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        raise NotImplementedError

    @abstractmethod
    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        raise NotImplementedError

    @abstractmethod
    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        raise NotImplementedError

    @abstractmethod
    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        raise NotImplementedError

    @abstractmethod
    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        raise NotImplementedError

    @abstractmethod
    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        raise NotImplementedError

    def _create_order_tracker(self) -> ClientOrderTracker:
        return ClientOrderTracker(connector=self)

    async def _initialize_trading_pair_symbol_map(self):
        try:
            exchange_info = await self._make_trading_pairs_request()
            self._initialize_trading_pair_symbols_from_exchange_info(exchange_info=exchange_info)
        except Exception:
            self.logger().exception("There was an error requesting exchange info.")

    async def _make_network_check_request(self):
        await self._api_get(path_url=self.check_network_request_path)

    async def _make_trading_rules_request(self) -> Any:
        exchange_info = await self._api_get(path_url=self.trading_rules_request_path)
        return exchange_info

    async def _make_trading_pairs_request(self) -> Any:
        exchange_info = await self._api_get(path_url=self.trading_pairs_request_path)
        return exchange_info

    def _get_poll_interval(self, timestamp: float) -> float:
        last_user_stream_message_time = (
            0 if self._user_stream_tracker is None else self._user_stream_tracker.last_recv_time
        )
        last_recv_diff = timestamp - last_user_stream_message_time
        poll_interval = (
            self.SHORT_POLL_INTERVAL if last_recv_diff > self.TICK_INTERVAL_LIMIT else self.LONG_POLL_INTERVAL
        )
        return poll_interval
