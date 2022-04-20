import asyncio
import logging
from decimal import Decimal
from typing import Any, AsyncIterable, Dict, List, Optional

from async_timeout import timeout

from hummingbot.connector.client_order_tracker import ClientOrderTracker
from hummingbot.connector.exchange.kucoin import (
    kucoin_constants as CONSTANTS,
    kucoin_utils as utils,
    kucoin_web_utils as web_utils,
)
from hummingbot.connector.exchange.kucoin.kucoin_api_order_book_data_source import KucoinAPIOrderBookDataSource
from hummingbot.connector.exchange.kucoin.kucoin_api_user_stream_data_source import KucoinAPIUserStreamDataSource
from hummingbot.connector.exchange.kucoin.kucoin_auth import KucoinAuth
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import get_new_client_order_id, combine_to_hb_trading_pair
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, OrderState, TradeUpdate
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_tracker import OrderBookTracker
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee
from hummingbot.core.data_type.user_stream_tracker import UserStreamTracker
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.logger import HummingbotLogger

s_decimal_0 = Decimal(0)
s_decimal_NaN = Decimal("nan")

MINUTE = 60
TWELVE_HOURS = MINUTE * 60 * 12


class KucoinExchange(ExchangePyBase):
    _logger = None

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
        self._last_poll_timestamp = 0
        self._last_timestamp = 0
        self._trading_pairs = trading_pairs
        self._order_book_tracker = OrderBookTracker(
            data_source=KucoinAPIOrderBookDataSource(
                trading_pairs=trading_pairs,
                domain=self._domain,
                api_factory=self._api_factory,
                throttler=self._throttler,
                time_synchronizer=self._time_synchronizer),
            trading_pairs=trading_pairs,
            domain=self._domain)
        self._user_stream_tracker = UserStreamTracker(
            data_source=KucoinAPIUserStreamDataSource(
                domain=self._domain,
                api_factory=self._api_factory,
                throttler=self._throttler))
        self._poll_notifier = asyncio.Event()
        self._status_polling_task = None
        self._user_stream_tracker_task = None
        self._user_stream_event_listener_task = None
        self._trading_rules_polling_task = None
        self._trading_fees_polling_task = None
        self._trading_required = trading_required
        self._trading_rules = {}
        self._trading_fees = {}
        self._order_tracker: ClientOrderTracker = ClientOrderTracker(connector=self)

    @property
    def name(self) -> str:
        return "kucoin"

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
    def tracking_states(self) -> Dict[str, Any]:
        return {
            key: value.to_json()
            for key, value in self.in_flight_orders.items()
            if not value.is_done
        }

    @property
    def status_dict(self) -> Dict[str, bool]:
        return {
            "symbols_mapping_initialized": KucoinAPIOrderBookDataSource.trading_pair_symbol_map_ready(
                domain=self._domain),
            "order_books_initialized": self._order_book_tracker.ready,
            "account_balance": not self._trading_required or len(self._account_balances) > 0,
            "trading_rule_initialized": len(self._trading_rules) > 0,
            "user_stream_initialized":
                self._user_stream_tracker.data_source.last_recv_time > 0 if self._trading_required else True,
        }

    @property
    def ready(self) -> bool:
        return all(self.status_dict.values())

    def restore_tracking_states(self, saved_states: Dict[str, Any]):
        """
        Restore in-flight orders from saved tracking states, this is st the connector can pick up on where it left off
        when it disconnects.

        :param saved_states: The saved tracking_states.
        """
        self._order_tracker.restore_tracking_states(tracking_states=saved_states)

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
        """
        Includes the logic that has to be processed every time a new tick happens in the bot. Particularly it enables
        the execution of the status update polling loop using an event.
        """
        poll_interval = (self.SHORT_POLL_INTERVAL
                         if timestamp - self._user_stream_tracker.last_recv_time > 60.0
                         else self.LONG_POLL_INTERVAL)
        last_tick = int(self._last_timestamp / poll_interval)
        current_tick = int(timestamp / poll_interval)

        if current_tick > last_tick:
            self._poll_notifier.set()
        self._last_timestamp = timestamp

    def supported_order_types(self):
        return [OrderType.MARKET, OrderType.LIMIT, OrderType.LIMIT_MAKER]

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
            is_buy=True, trading_pair=trading_pair, max_id_len=CONSTANTS.MAX_ORDER_ID_LEN
        )

        safe_ensure_future(self._create_order(
            trade_type=TradeType.BUY,
            order_id=order_id,
            trading_pair=trading_pair,
            amount=amount,
            order_type=order_type,
            price=price))
        return order_id

    def sell(self,
             trading_pair: str,
             amount: Decimal,
             order_type=OrderType.MARKET,
             price: Decimal = s_decimal_NaN,
             **kwargs) -> str:
        """
        Creates a promise to create a sell order using the parameters

        :param trading_pair: the token pair to operate with
        :param amount: the order amount
        :param order_type: the type of order to create (MARKET, LIMIT, LIMIT_MAKER)
        :param price: the order price

        :return: the id assigned by the connector to the order (the client id)
        """
        order_id = get_new_client_order_id(
            is_buy=False, trading_pair=trading_pair, max_id_len=CONSTANTS.MAX_ORDER_ID_LEN
        )

        safe_ensure_future(self._create_order(
            trade_type=TradeType.SELL,
            order_id=order_id,
            trading_pair=trading_pair,
            amount=amount,
            order_type=order_type,
            price=price))
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
                    if cr is not None:
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

        is_maker = is_maker or (order_type is OrderType.LIMIT_MAKER)
        trading_pair = combine_to_hb_trading_pair(base=base_currency, quote=quote_currency)
        if trading_pair in self._trading_fees:
            fees_data = self._trading_fees[trading_pair]
            fee_value = Decimal(fees_data["makerFeeRate"]) if is_maker else Decimal(fees_data["takerFeeRate"])
            fee = AddedToCostTradeFee(percent=fee_value)
        else:
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
            amount = self.quantize_order_amount(trading_pair, amount)

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

            exchange_order_id = await self._place_order(
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
                update_timestamp=self.current_timestamp,
                new_state=OrderState.OPEN,
            )
            self._order_tracker.process_order_update(order_update)

        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().network(
                f"Error submitting {trade_type.name.lower()} {order_type.name.upper()} order to Kucoin for "
                f"{amount} {trading_pair} "
                f"{price}.",
                exc_info=True,
                app_warning_msg="Failed to submit buy order to Kucoin. Check API key and network connection."
            )
            order_update: OrderUpdate = OrderUpdate(
                client_order_id=order_id,
                trading_pair=trading_pair,
                update_timestamp=self.current_timestamp,
                new_state=OrderState.FAILED,
            )
            self._order_tracker.process_order_update(order_update)

    async def _place_order(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           trade_type: TradeType,
                           order_type: OrderType,
                           price: Decimal) -> str:
        path_url = CONSTANTS.ORDERS_PATH_URL
        side = trade_type.name.lower()
        order_type_str = "market" if order_type == OrderType.MARKET else "limit"
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

    async def _execute_cancel(self, trading_pair: str, order_id: str) -> str:
        """
        Requests the exchange to cancel an active order

        :param trading_pair: the trading pair the order to cancel operates with
        :param order_id: the client id of the order to cancel
        """
        tracked_order = self._order_tracker.fetch_tracked_order(order_id)
        if tracked_order is not None:
            try:
                exchange_order_id = await tracked_order.get_exchange_order_id()
                path_url = f"{CONSTANTS.ORDERS_PATH_URL}/{exchange_order_id}"
                cancel_result = await self._api_request(
                    path_url=path_url,
                    method=RESTMethod.DELETE,
                    is_auth_required=True,
                    limit_id=CONSTANTS.DELETE_ORDER_LIMIT_ID
                )

                if tracked_order.exchange_order_id in cancel_result["data"].get("cancelledOrderIds", []):
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
            except asyncio.TimeoutError:
                self.logger().warning(f"Failed to cancel the order {order_id} because it does not have an exchange"
                                      f" order id yet")
                await self._order_tracker.process_order_not_found(order_id)
            except Exception as e:
                self.logger().network(
                    f"Failed to cancel order {order_id}: {str(e)}",
                    exc_info=True,
                    app_warning_msg=f"Failed to cancel the order {order_id} on Kucoin. "
                                    f"Check API key and network connection."
                )

    async def _iter_user_event_queue(self) -> AsyncIterable[Dict[str, any]]:
        while True:
            try:
                yield await self._user_stream_tracker.user_stream.get()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Error while reading user events queue. Retrying after 1 second.")
                await asyncio.sleep(1.0)

    async def _user_stream_event_listener(self):
        """
        This functions runs in background continuously processing the events received from the exchange by the user
        stream data source. It keeps reading events from the queue until the task is interrupted.
        The events received are balance updates, order updates and trade events.
        """
        async for event_message in self._iter_user_event_queue():
            try:
                event_type = event_message.get("type")
                event_subject = event_message.get("subject")
                execution_data = event_message.get("data")

                # Refer to https://docs.kucoin.com/#private-order-change-events
                if event_type == "message" and event_subject == CONSTANTS.ORDER_CHANGE_EVENT_TYPE:
                    order_event_type = execution_data["type"]
                    client_order_id: Optional[str] = execution_data.get("clientOid")

                    tracked_order = self._order_tracker.fetch_order(client_order_id=client_order_id)

                    if tracked_order is not None:
                        event_timestamp = execution_data["ts"] * 1e-9

                        if order_event_type == "match":
                            execute_amount_diff = Decimal(execution_data["matchSize"])
                            execute_price = Decimal(execution_data["matchPrice"])

                            fee = self.get_fee(
                                tracked_order.base_asset,
                                tracked_order.quote_asset,
                                tracked_order.order_type,
                                tracked_order.trade_type,
                                execute_price,
                                execute_amount_diff,
                            )

                            trade_update = TradeUpdate(
                                trade_id=execution_data["tradeId"],
                                client_order_id=client_order_id,
                                exchange_order_id=execution_data["orderId"],
                                trading_pair=tracked_order.trading_pair,
                                fee=fee,
                                fill_base_amount=execute_amount_diff,
                                fill_quote_amount=execute_amount_diff * execute_price,
                                fill_price=execute_price,
                                fill_timestamp=event_timestamp,
                            )
                            self._order_tracker.process_trade_update(trade_update)

                        updated_status = tracked_order.current_state
                        if order_event_type == "open":
                            updated_status = OrderState.OPEN
                        elif order_event_type == "match":
                            updated_status = OrderState.PARTIALLY_FILLED
                        elif order_event_type == "filled":
                            updated_status = OrderState.FILLED
                        elif order_event_type == "canceled":
                            updated_status = OrderState.CANCELLED

                        order_update = OrderUpdate(
                            trading_pair=tracked_order.trading_pair,
                            update_timestamp=event_timestamp,
                            new_state=updated_status,
                            client_order_id=client_order_id,
                            exchange_order_id=execution_data["orderId"],
                        )
                        self._order_tracker.process_order_update(order_update=order_update)

                elif event_type == "message" and event_subject == CONSTANTS.BALANCE_EVENT_TYPE:
                    currency = execution_data["currency"]
                    available_balance = Decimal(execution_data["available"])
                    total_balance = Decimal(execution_data["total"])
                    self._account_balances.update({currency: total_balance})
                    self._account_available_balances.update({currency: available_balance})

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in user stream listener loop.")
                await self._sleep(5.0)

    async def _status_polling_loop(self):
        """
        Performs all required operation to keep the connector updated and synchronized with the exchange.
        It contains the backup logic to update status using API requests in case the main update source (the user stream
        data source websocket) fails.
        It also updates the time synchronizer. This is necessary because Kucoin requires the time of the client to be
        the same as the time in the exchange.
        Executes when the _poll_notifier event is enabled by the `tick` function.
        """
        while True:
            try:
                await self._poll_notifier.wait()
                await self._update_time_synchronizer()
                await safe_gather(
                    self._update_balances(),
                    self._update_order_status(),
                )
                self._last_poll_timestamp = self.current_timestamp

                self._poll_notifier = asyncio.Event()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network("Unexpected error while fetching account updates.",
                                      exc_info=True,
                                      app_warning_msg="Could not fetch account updates from Kucoin. "
                                                      "Check API key and network connection.")
                await self._sleep(0.5)

    async def _trading_rules_polling_loop(self):
        while True:
            try:
                await self._update_trading_rules()
                await self._sleep(30 * MINUTE)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network("Unexpected error while fetching trading rules.",
                                      exc_info=True,
                                      app_warning_msg="Could not fetch new trading rules from Kucoin. "
                                                      "Check network connection.")
                await self._sleep(0.5)

    async def _trading_fees_polling_loop(self):
        while True:
            try:
                await self._update_trading_fees()
                await self._sleep(TWELVE_HOURS)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network("Unexpected error while fetching trading fees.",
                                      exc_info=True,
                                      app_warning_msg="Could not fetch new trading fees from Kucoin. "
                                                      "Check network connection.")
                await self._sleep(0.5)

    async def _update_balances(self):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        response = await self._api_request(
            path_url=CONSTANTS.ACCOUNTS_PATH_URL,
            params={"type": "trade"},
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
        exchange_info = await self._api_request(path_url=CONSTANTS.SYMBOLS_PATH_URL, method=RESTMethod.GET)
        trading_rules_list = await self._format_trading_rules(exchange_info)
        self._trading_rules.clear()
        for trading_rule in trading_rules_list:
            self._trading_rules[trading_rule.trading_pair] = trading_rule

    async def _update_trading_fees(self):
        trading_symbols = [await KucoinAPIOrderBookDataSource.exchange_symbol_associated_to_pair(
            trading_pair=trading_pair,
            domain=self._domain,
            api_factory=self._api_factory,
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer) for trading_pair in self._trading_pairs]

        params = {"symbols": ",".join(trading_symbols)}

        resp = await self._api_request(
            path_url=CONSTANTS.FEE_PATH_URL,
            params=params,
            method=RESTMethod.GET,
            is_auth_required=True,
        )

        fees_json = resp["data"]
        for fee_json in fees_json:
            trading_pair = await KucoinAPIOrderBookDataSource.trading_pair_associated_to_exchange_symbol(
                symbol=fee_json["symbol"],
                domain=self._domain,
                api_factory=self._api_factory,
                throttler=self._throttler,
                time_synchronizer=self._time_synchronizer,
            )
            self._trading_fees[trading_pair] = fee_json

    async def _format_trading_rules(self, raw_trading_pair_info: Dict[str, Any]) -> List[TradingRule]:
        trading_rules = []

        for info in raw_trading_pair_info["data"]:
            if utils.is_pair_information_valid(info):
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
                    self.logger().error(f"Error parsing the trading pair rule {info}. Skipping.", exc_info=True)
        return trading_rules

    async def _update_order_status(self):
        # The poll interval for order status is 10 seconds.
        last_tick = int(self._last_poll_timestamp / self.UPDATE_ORDERS_INTERVAL)
        current_tick = int(self.current_timestamp / self.UPDATE_ORDERS_INTERVAL)

        tracked_orders = list(self.in_flight_orders.values())
        if current_tick > last_tick and len(tracked_orders) > 0:
            reviewed_orders = []
            request_tasks = []

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
                request_tasks.append(asyncio.get_event_loop().create_task(self._api_request(
                    path_url=f"{CONSTANTS.ORDERS_PATH_URL}/{exchange_order_id}",
                    method=RESTMethod.GET,
                    is_auth_required=True,
                    limit_id=CONSTANTS.GET_ORDER_LIMIT_ID)))

            self.logger().debug(f"Polling for order status updates of {len(reviewed_orders)} orders.")
            results = await safe_gather(*request_tasks, return_exceptions=True)

            for update_result, tracked_order in zip(results, reviewed_orders):
                client_order_id = tracked_order.client_order_id

                # If the order has already been cancelled or has failed do nothing
                if client_order_id in self.in_flight_orders:
                    if isinstance(update_result, Exception):
                        self.logger().network(
                            f"Error fetching status update for the order {client_order_id}: {update_result}.",
                            app_warning_msg=f"Failed to fetch status update for the order {client_order_id}."
                        )
                        # Wait until the order not found error have repeated a few times before actually treating
                        # it as failed. See: https://github.com/CoinAlpha/hummingbot/issues/601
                        await self._order_tracker.process_order_not_found(client_order_id)

                    else:
                        # Update order execution status
                        ordered_canceled = update_result["data"]["cancelExist"]
                        is_active = update_result["data"]["isActive"]
                        op_type = update_result["data"]["opType"]

                        new_state = tracked_order.current_state
                        if ordered_canceled or op_type == "CANCEL":
                            new_state = OrderState.CANCELLED
                        elif not is_active:
                            new_state = OrderState.FILLED

                        update = OrderUpdate(
                            client_order_id=client_order_id,
                            exchange_order_id=update_result["data"]["id"],
                            trading_pair=tracked_order.trading_pair,
                            update_timestamp=self.current_timestamp,
                            new_state=new_state,
                        )
                        self._order_tracker.process_order_update(update)

    async def _update_time_synchronizer(self):
        try:
            await self._time_synchronizer.update_server_time_offset_with_time_provider(
                time_provider=web_utils.get_current_server_time(
                    throttler=self._throttler,
                    domain=self._domain,
                )
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().exception("Error requesting time from Kucoin server")
            raise

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

    async def _sleep(self, delay: float):
        await asyncio.sleep(delay)
