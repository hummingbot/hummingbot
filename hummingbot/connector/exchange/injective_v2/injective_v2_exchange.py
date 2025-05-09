import asyncio
from collections import defaultdict
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple, Union

from async_timeout import timeout

from hummingbot.connector.client_order_tracker import ClientOrderTracker
from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.injective_v2 import (
    injective_constants as CONSTANTS,
    injective_v2_web_utils as web_utils,
)
from hummingbot.connector.exchange.injective_v2.injective_events import InjectiveEvent
from hummingbot.connector.exchange.injective_v2.injective_v2_api_order_book_data_source import (
    InjectiveV2APIOrderBookDataSource,
)
from hummingbot.connector.exchange.injective_v2.injective_v2_utils import InjectiveConfigMap
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.connector.gateway.gateway_order_tracker import GatewayOrderTracker
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair, get_new_client_order_id
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.market_order import MarketOrder
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TradeFeeBase, TradeFeeSchema
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.event.event_forwarder import EventForwarder
from hummingbot.core.event.events import AccountEvent, BalanceUpdateEvent, MarketEvent
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class InjectiveV2Exchange(ExchangePyBase):
    web_utils = web_utils

    def __init__(
            self,
            client_config_map: "ClientConfigAdapter",
            connector_configuration: InjectiveConfigMap,
            trading_pairs: Optional[List[str]] = None,
            trading_required: bool = True,
            **kwargs,
    ):
        self._orders_processing_delta_time = 0.5

        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._data_source = connector_configuration.create_data_source()
        self._rate_limits = connector_configuration.network.rate_limits()

        super().__init__(client_config_map=client_config_map)
        self._data_source.configure_throttler(throttler=self._throttler)
        self._forwarders = []
        self._configure_event_forwarders()
        self._latest_polled_order_fill_time: float = self._time()
        self._orders_transactions_check_task: Optional[asyncio.Task] = None
        self._orders_queued_to_create: List[GatewayInFlightOrder] = []
        self._orders_queued_to_cancel: List[GatewayInFlightOrder] = []

        self._orders_transactions_check_task = None
        self._queued_orders_task = None
        self._all_trading_events_queue = asyncio.Queue()

    @property
    def name(self) -> str:
        return CONSTANTS.EXCHANGE_NAME

    @property
    def authenticator(self) -> AuthBase:
        return None

    @property
    def rate_limits_rules(self) -> List[RateLimit]:
        return self._rate_limits

    @property
    def domain(self) -> str:
        return self._data_source.network_name

    @property
    def client_order_id_max_length(self) -> int:
        return CONSTANTS.MAX_ORDER_ID_LEN

    @property
    def client_order_id_prefix(self) -> str:
        return CONSTANTS.HBOT_ORDER_ID_PREFIX

    @property
    def trading_rules_request_path(self) -> str:
        raise NotImplementedError

    @property
    def trading_pairs_request_path(self) -> str:
        raise NotImplementedError

    @property
    def check_network_request_path(self) -> str:
        raise NotImplementedError

    @property
    def trading_pairs(self) -> List[str]:
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return False

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    @property
    def status_dict(self) -> Dict[str, bool]:
        status = super().status_dict
        status["data_source_initialized"] = self._data_source.is_started()
        return status

    async def start_network(self):
        await super().start_network()

        market_ids = [
            await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
            for trading_pair in self._trading_pairs
        ]
        await self._data_source.start(market_ids=market_ids)

        if self.is_trading_required:
            self._orders_transactions_check_task = safe_ensure_future(self._check_orders_transactions())
            self._queued_orders_task = safe_ensure_future(self._process_queued_orders())

    async def stop_network(self):
        """
        This function is executed when the connector is stopped. It performs a general cleanup and stops all background
        tasks that require the connection with the exchange to work.
        """
        await super().stop_network()
        await self._data_source.stop()
        self._forwarders = []
        if self._orders_transactions_check_task is not None:
            self._orders_transactions_check_task.cancel()
            self._orders_transactions_check_task = None
        if self._queued_orders_task is not None:
            self._queued_orders_task.cancel()
            self._queued_orders_task = None

    def supported_order_types(self) -> List[OrderType]:
        return self._data_source.supported_order_types()

    def start_tracking_order(
        self,
        order_id: str,
        exchange_order_id: Optional[str],
        trading_pair: str,
        trade_type: TradeType,
        price: Decimal,
        amount: Decimal,
        order_type: OrderType,
        **kwargs,
    ):
        self._order_tracker.start_tracking_order(
            GatewayInFlightOrder(
                client_order_id=order_id,
                exchange_order_id=exchange_order_id,
                trading_pair=trading_pair,
                order_type=order_type,
                trade_type=trade_type,
                amount=amount,
                price=price,
                creation_timestamp=self.current_timestamp,
            )
        )

    def batch_order_create(self, orders_to_create: List[Union[MarketOrder, LimitOrder]]) -> List[LimitOrder]:
        """
        Issues a batch order creation as a single API request for exchanges that implement this feature. The default
        implementation of this method is to send the requests discretely (one by one).
        :param orders_to_create: A list of LimitOrder or MarketOrder objects representing the orders to create. The order IDs
            can be blanc.
        :returns: A tuple composed of LimitOrder or MarketOrder objects representing the created orders, complete with the generated
            order IDs.
        """
        orders_with_ids_to_create = []
        for order in orders_to_create:
            client_order_id = get_new_client_order_id(
                is_buy=order.is_buy,
                trading_pair=order.trading_pair,
                hbot_order_id_prefix=self.client_order_id_prefix,
                max_id_len=self.client_order_id_max_length,
            )
            orders_with_ids_to_create.append(order.copy_with_id(client_order_id=client_order_id))
        safe_ensure_future(self._execute_batch_order_create(orders_to_create=orders_with_ids_to_create))
        return orders_with_ids_to_create

    def batch_order_cancel(self, orders_to_cancel: List[LimitOrder]):
        """
        Issues a batch order cancelation as a single API request for exchanges that implement this feature. The default
        implementation of this method is to send the requests discretely (one by one).
        :param orders_to_cancel: A list of the orders to cancel.
        """
        safe_ensure_future(coro=self._execute_batch_cancel(orders_to_cancel=orders_to_cancel))

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        """
        Cancels all currently active orders. The cancellations are performed in parallel tasks.

        :param timeout_seconds: the maximum time (in seconds) the cancel logic should run

        :return: a list of CancellationResult instances, one for each of the orders to be cancelled
        """
        incomplete_orders = {}
        limit_orders = []
        successful_cancellations = []

        for order in self.in_flight_orders.values():
            if not order.is_done:
                incomplete_orders[order.client_order_id] = order
                limit_orders.append(order.to_limit_order())

        if len(limit_orders) > 0:
            try:
                async with timeout(timeout_seconds):
                    cancellation_results = await self._execute_batch_cancel(orders_to_cancel=limit_orders)
                    for cr in cancellation_results:
                        if cr.success:
                            del incomplete_orders[cr.order_id]
                            successful_cancellations.append(CancellationResult(cr.order_id, True))
            except Exception:
                self.logger().network(
                    "Unexpected error cancelling orders.",
                    exc_info=True,
                    app_warning_msg="Failed to cancel order. Check API key and network connection."
                )
        failed_cancellations = [CancellationResult(oid, False) for oid in incomplete_orders.keys()]
        return successful_cancellations + failed_cancellations

    async def cancel_all_subaccount_orders(self):
        markets_ids = [await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                       for trading_pair in self.trading_pairs]
        await self._data_source.cancel_all_subaccount_orders(spot_markets_ids=markets_ids)

    async def check_network(self) -> NetworkStatus:
        """
        Checks connectivity with the exchange using the API
        """
        try:
            status = await self._data_source.check_network()
        except asyncio.CancelledError:
            raise
        except Exception:
            status = NetworkStatus.NOT_CONNECTED
        return status

    def trigger_event(self, event_tag: Enum, message: any):
        # Reimplemented because Injective connector has trading pairs with modified token names, because market tickers
        # are not always unique.
        # We need to change the original trading pair in all events to the real tokens trading pairs to not impact the
        # bot events processing
        trading_pair = getattr(message, "trading_pair", None)
        if trading_pair is not None:
            new_trading_pair = self._data_source.real_tokens_spot_trading_pair(unique_trading_pair=trading_pair)
            if isinstance(message, tuple):
                message = message._replace(trading_pair=new_trading_pair)
            else:
                setattr(message, "trading_pair", new_trading_pair)

        super().trigger_event(event_tag=event_tag, message=message)

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception) -> bool:
        return False

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return CONSTANTS.ORDER_NOT_FOUND_ERROR_MESSAGE in str(status_update_exception)

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        # For Injective the cancelation is done by sending a transaction to the chain.
        # The cancel request is not validated until the transaction is included in a block, and so this does not apply
        return False

    async def _place_cancel(self, order_id: str, tracked_order: GatewayInFlightOrder):
        # Not required because of _execute_order_cancel redefinition
        raise NotImplementedError

    async def _execute_order_cancel(self, order: GatewayInFlightOrder) -> str:
        # Order cancelation requests for single orders are queued to be executed in batch if possible
        self._orders_queued_to_cancel.append(order)
        return None

    async def _place_order(self, order_id: str, trading_pair: str, amount: Decimal, trade_type: TradeType,
                           order_type: OrderType, price: Decimal, **kwargs) -> Tuple[str, float]:
        # Not required because of _place_order_and_process_update redefinition
        raise NotImplementedError

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
        try:
            if price is None or price.is_nan():
                calculated_price = self.get_price_for_volume(
                    trading_pair=trading_pair,
                    is_buy=trade_type == TradeType.BUY,
                    volume=amount,
                ).result_price
            else:
                calculated_price = price

            calculated_price = self.quantize_order_price(trading_pair, calculated_price)

            await super()._create_order(
                trade_type=trade_type,
                order_id=order_id,
                trading_pair=trading_pair,
                amount=amount,
                order_type=order_type,
                price=calculated_price,
                ** kwargs
            )

        except asyncio.CancelledError:
            raise
        except Exception as ex:
            self._on_order_failure(
                order_id=order_id,
                trading_pair=trading_pair,
                amount=amount,
                trade_type=trade_type,
                order_type=order_type,
                price=price,
                exception=ex,
                **kwargs,
            )

    async def _place_order_and_process_update(self, order: GatewayInFlightOrder, **kwargs) -> str:
        # Order creation requests for single orders are queued to be executed in batch if possible
        self._orders_queued_to_create.append(order)
        return None

    async def _execute_batch_order_create(self, orders_to_create: List[Union[MarketOrder, LimitOrder]]):
        inflight_orders_to_create = []
        for order in orders_to_create:
            valid_order = await self._start_tracking_and_validate_order(
                trade_type=TradeType.BUY if order.is_buy else TradeType.SELL,
                order_id=order.client_order_id,
                trading_pair=order.trading_pair,
                amount=order.quantity,
                order_type=order.order_type(),
                price=order.price,
            )
            if valid_order is not None:
                inflight_orders_to_create.append(valid_order)
        await self._execute_batch_inflight_order_create(inflight_orders_to_create=inflight_orders_to_create)

    async def _execute_batch_inflight_order_create(self, inflight_orders_to_create: List[GatewayInFlightOrder]):
        try:
            place_order_results = await self._data_source.create_orders(
                spot_orders=inflight_orders_to_create
            )
            for place_order_result, in_flight_order in (
                zip(place_order_results, inflight_orders_to_create)
            ):
                if place_order_result.exception:
                    self._on_order_creation_failure(
                        order_id=in_flight_order.client_order_id,
                        trading_pair=in_flight_order.trading_pair,
                        amount=in_flight_order.amount,
                        trade_type=in_flight_order.trade_type,
                        order_type=in_flight_order.order_type,
                        price=in_flight_order.price,
                        exception=place_order_result.exception,
                    )
                else:
                    self._update_order_after_creation_success(
                        exchange_order_id=place_order_result.exchange_order_id,
                        order=in_flight_order,
                        update_timestamp=self.current_timestamp,
                        misc_updates=place_order_result.misc_updates,
                    )
        except asyncio.CancelledError:
            raise
        except Exception as ex:
            self.logger().network("Batch order create failed.")
            for order in inflight_orders_to_create:
                self._on_order_creation_failure(
                    order_id=order.client_order_id,
                    trading_pair=order.trading_pair,
                    amount=order.amount,
                    trade_type=order.trade_type,
                    order_type=order.order_type,
                    price=order.price,
                    exception=ex,
                )

    async def _start_tracking_and_validate_order(
        self,
        trade_type: TradeType,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        order_type: OrderType,
        price: Optional[Decimal] = None,
        **kwargs
    ) -> Optional[GatewayInFlightOrder]:
        trading_rule = self._trading_rules[trading_pair]

        if price is None:
            calculated_price = self.get_price_for_volume(
                trading_pair=trading_pair,
                is_buy=trade_type == TradeType.BUY,
                volume=amount,
            ).result_price
            calculated_price = self.quantize_order_price(trading_pair, calculated_price)
        else:
            calculated_price = price

        price = self.quantize_order_price(trading_pair, calculated_price)
        amount = self.quantize_order_amount(trading_pair=trading_pair, amount=amount)

        self.start_tracking_order(
            order_id=order_id,
            exchange_order_id=None,
            trading_pair=trading_pair,
            order_type=order_type,
            trade_type=trade_type,
            price=price,
            amount=amount,
            **kwargs,
        )
        order = self._order_tracker.active_orders[order_id]

        if order_type not in self.supported_order_types():
            self.logger().error(f"{order_type} is not in the list of supported order types")
            self._update_order_after_creation_failure(order_id=order_id, trading_pair=trading_pair)
            order = None
        elif amount < trading_rule.min_order_size:
            self.logger().warning(f"{trade_type.name.title()} order amount {amount} is lower than the minimum order"
                                  f" size {trading_rule.min_order_size}. The order will not be created.")
            self._update_order_after_creation_failure(order_id=order_id, trading_pair=trading_pair)
            order = None
        elif price is not None and amount * price < trading_rule.min_notional_size:
            self.logger().warning(f"{trade_type.name.title()} order notional {amount * price} is lower than the "
                                  f"minimum notional size {trading_rule.min_notional_size}. "
                                  "The order will not be created.")
            self._update_order_after_creation_failure(order_id=order_id, trading_pair=trading_pair)
            order = None

        return order

    def _update_order_after_creation_success(
        self,
        exchange_order_id: Optional[str],
        order: GatewayInFlightOrder,
        update_timestamp: float,
        misc_updates: Optional[Dict[str, Any]] = None
    ):
        order_update: OrderUpdate = OrderUpdate(
            client_order_id=order.client_order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=order.trading_pair,
            update_timestamp=update_timestamp,
            new_state=order.current_state,
            misc_updates=misc_updates,
        )
        self.logger().debug(f"\nCreated order {order.client_order_id} ({exchange_order_id}) with TX {misc_updates}")
        self._order_tracker.process_order_update(order_update)

    def _on_order_creation_failure(
        self,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        trade_type: TradeType,
        order_type: OrderType,
        price: Optional[Decimal],
        exception: Exception,
    ):
        self.logger().network(
            f"Error submitting {trade_type.name.lower()} {order_type.name.upper()} order to {self.name_cap} for "
            f"{amount} {trading_pair} {price}.",
            exc_info=exception,
            app_warning_msg=f"Failed to submit buy order to {self.name_cap}. Check API key and network connection."
        )
        self._update_order_after_creation_failure(order_id=order_id, trading_pair=trading_pair)

    def _update_order_after_creation_failure(self, order_id: str, trading_pair: str):
        order_update: OrderUpdate = OrderUpdate(
            client_order_id=order_id,
            trading_pair=trading_pair,
            update_timestamp=self.current_timestamp,
            new_state=OrderState.FAILED,
        )
        self._order_tracker.process_order_update(order_update)

    async def _execute_batch_cancel(self, orders_to_cancel: List[LimitOrder]) -> List[CancellationResult]:
        results = []
        tracked_orders_to_cancel = []

        for order in orders_to_cancel:
            tracked_order = self._order_tracker.all_updatable_orders.get(order.client_order_id)
            if tracked_order is not None:
                tracked_orders_to_cancel.append(tracked_order)
            else:
                results.append(CancellationResult(order_id=order.client_order_id, success=False))

        if len(tracked_orders_to_cancel) > 0:
            results.extend(await self._execute_batch_order_cancel(orders_to_cancel=tracked_orders_to_cancel))

        return results

    async def _execute_batch_order_cancel(self, orders_to_cancel: List[GatewayInFlightOrder]) -> List[CancellationResult]:
        try:
            cancel_order_results = await self._data_source.cancel_orders(spot_orders=orders_to_cancel)
            cancelation_results = []
            for cancel_order_result in cancel_order_results:
                success = True
                if cancel_order_result.not_found:
                    self.logger().warning(
                        f"Failed to cancel the order {cancel_order_result.client_order_id} due to the order"
                        f" not being found."
                    )
                    await self._order_tracker.process_order_not_found(
                        client_order_id=cancel_order_result.client_order_id
                    )
                    success = False
                elif cancel_order_result.exception is not None:
                    self.logger().error(
                        f"Failed to cancel order {cancel_order_result.client_order_id}",
                        exc_info=cancel_order_result.exception,
                    )
                    success = False
                else:
                    order_update: OrderUpdate = OrderUpdate(
                        client_order_id=cancel_order_result.client_order_id,
                        trading_pair=cancel_order_result.trading_pair,
                        update_timestamp=self.current_timestamp,
                        new_state=(OrderState.CANCELED
                                   if self.is_cancel_request_in_exchange_synchronous
                                   else OrderState.PENDING_CANCEL),
                        misc_updates=cancel_order_result.misc_updates,
                    )
                    self._order_tracker.process_order_update(order_update)
                cancelation_results.append(
                    CancellationResult(order_id=cancel_order_result.client_order_id, success=success)
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                f"Failed to cancel orders {', '.join([o.client_order_id for o in orders_to_cancel])}",
                exc_info=True,
            )
            cancelation_results = [
                CancellationResult(order_id=order.client_order_id, success=False)
                for order in orders_to_cancel
            ]

        return cancelation_results

    def _update_order_after_cancelation_success(self, order: GatewayInFlightOrder):
        order_update: OrderUpdate = OrderUpdate(
            client_order_id=order.client_order_id,
            trading_pair=order.trading_pair,
            update_timestamp=self.current_timestamp,
            new_state=(OrderState.CANCELED
                       if self.is_cancel_request_in_exchange_synchronous
                       else OrderState.PENDING_CANCEL),
        )
        self._order_tracker.process_order_update(order_update)

    def _get_fee(self, base_currency: str, quote_currency: str, order_type: OrderType, order_side: TradeType,
                 amount: Decimal, price: Decimal = s_decimal_NaN,
                 is_maker: Optional[bool] = None) -> TradeFeeBase:
        is_maker = is_maker or (order_type is OrderType.LIMIT_MAKER)
        trading_pair = combine_to_hb_trading_pair(base=base_currency, quote=quote_currency)
        if trading_pair in self._trading_fees:
            fee_schema: TradeFeeSchema = self._trading_fees[trading_pair]
            fee_rate = fee_schema.maker_percent_fee_decimal if is_maker else fee_schema.taker_percent_fee_decimal
            fee = TradeFeeBase.new_spot_fee(
                fee_schema=fee_schema,
                trade_type=order_side,
                percent=fee_rate,
                percent_token=fee_schema.percent_fee_token,
            )
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

    async def _update_trading_fees(self):
        self._trading_fees = await self._data_source.get_spot_trading_fees()

    async def _user_stream_event_listener(self):
        while True:
            try:
                event_message = await self._all_trading_events_queue.get()
                channel = event_message["channel"]
                event_data = event_message["data"]

                if channel == "transaction":
                    transaction_hash = event_data["hash"]
                    await self._check_created_orders_status_for_transaction(transaction_hash=transaction_hash)
                elif channel == "trade":
                    trade_update = event_data
                    self._order_tracker.process_trade_update(trade_update)
                elif channel == "order":
                    order_update = event_data
                    tracked_order = self._order_tracker.all_updatable_orders.get(order_update.client_order_id)
                    if tracked_order is not None:
                        is_partial_fill = order_update.new_state == OrderState.FILLED and not tracked_order.is_filled
                        if not is_partial_fill:
                            self._order_tracker.process_order_update(order_update=order_update)
                elif channel == "balance":
                    if event_data.total_balance is not None:
                        self._account_balances[event_data.asset_name] = event_data.total_balance
                    if event_data.available_balance is not None:
                        self._account_available_balances[event_data.asset_name] = event_data.available_balance

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error in user stream listener loop")

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        # Not used in Injective
        raise NotImplementedError  # pragma: no cover

    async def _update_trading_rules(self):
        await self._data_source.update_markets()
        await self._initialize_trading_pair_symbol_map()
        trading_rules_list = await self._data_source.spot_trading_rules()
        trading_rules = {}
        for trading_rule in trading_rules_list:
            trading_rules[trading_rule.trading_pair] = trading_rule
        self._trading_rules.clear()
        self._trading_rules.update(trading_rules)

    async def _update_balances(self):
        all_balances = await self._data_source.all_account_balances()

        self._account_available_balances.clear()
        self._account_balances.clear()

        for token, token_balance_info in all_balances.items():
            self._account_balances[token] = token_balance_info["total_balance"]
            self._account_available_balances[token] = token_balance_info["available_balance"]

    async def _all_trade_updates_for_order(self, order: GatewayInFlightOrder) -> List[TradeUpdate]:
        # Not required because of _update_orders_fills redefinition
        raise NotImplementedError

    async def _update_orders_fills(self, orders: List[GatewayInFlightOrder]):
        oldest_order_creation_time = self.current_timestamp
        all_market_ids = set()

        for order in orders:
            oldest_order_creation_time = min(oldest_order_creation_time, order.creation_timestamp)
            all_market_ids.add(await self.exchange_symbol_associated_to_pair(trading_pair=order.trading_pair))

        try:
            start_time = min(oldest_order_creation_time, self._latest_polled_order_fill_time)
            trade_updates = await self._data_source.spot_trade_updates(market_ids=all_market_ids, start_time=start_time)
            for trade_update in trade_updates:
                self._latest_polled_order_fill_time = max(self._latest_polled_order_fill_time, trade_update.fill_timestamp)
                self._order_tracker.process_trade_update(trade_update)
        except asyncio.CancelledError:
            raise
        except Exception as ex:
            self.logger().warning(
                f"Failed to fetch trade updates. Error: {ex}",
                exc_info=ex,
            )

    async def _request_order_status(self, tracked_order: GatewayInFlightOrder) -> OrderUpdate:
        # Not required due to the redefinition of _update_orders_with_error_handler
        raise NotImplementedError

    async def _update_orders_with_error_handler(self, orders: List[GatewayInFlightOrder], error_handler: Callable):
        oldest_order_creation_time = self.current_timestamp
        all_market_ids = set()
        orders_by_id = {}

        for order in orders:
            oldest_order_creation_time = min(oldest_order_creation_time, order.creation_timestamp)
            all_market_ids.add(await self.exchange_symbol_associated_to_pair(trading_pair=order.trading_pair))
            orders_by_id[order.client_order_id] = order

        try:
            order_updates = await self._data_source.spot_order_updates(
                market_ids=all_market_ids,
                start_time=oldest_order_creation_time - self.LONG_POLL_INTERVAL
            )

            for order_update in order_updates:
                tracked_order = orders_by_id.get(order_update.client_order_id)
                if tracked_order is not None:
                    try:
                        if tracked_order.current_state == OrderState.PENDING_CREATE and order_update.new_state != OrderState.OPEN:
                            open_update = OrderUpdate(
                                trading_pair=order_update.trading_pair,
                                update_timestamp=order_update.update_timestamp,
                                new_state=OrderState.OPEN,
                                client_order_id=order_update.client_order_id,
                                exchange_order_id=order_update.exchange_order_id,
                                misc_updates=order_update.misc_updates,
                            )
                            self._order_tracker.process_order_update(open_update)

                        del orders_by_id[order_update.client_order_id]
                        self._order_tracker.process_order_update(order_update)
                    except asyncio.CancelledError:
                        raise
                    except Exception as ex:
                        await error_handler(tracked_order, ex)

            for order in orders_by_id.values():
                not_found_error = RuntimeError(
                    f"There was a problem updating order {order.client_order_id} "
                    f"({CONSTANTS.ORDER_NOT_FOUND_ERROR_MESSAGE})"
                )
                await error_handler(order, not_found_error)
        except asyncio.CancelledError:
            raise
        except Exception as request_error:
            for order in orders_by_id.values():
                await error_handler(order, request_error)

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return WebAssistantsFactory(throttler=self._throttler)

    def _create_order_tracker(self) -> ClientOrderTracker:
        tracker = GatewayOrderTracker(connector=self)
        return tracker

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return InjectiveV2APIOrderBookDataSource(
            trading_pairs=self.trading_pairs,
            connector=self,
            data_source=self._data_source,
            domain=self.domain
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        # Not used in Injective
        raise NotImplementedError  # pragma: no cover

    def _is_user_stream_initialized(self):
        # Injective does not have private websocket endpoints
        return self._data_source.is_started()

    def _create_user_stream_tracker(self):
        # Injective does not use a tracker for the private streams
        return None

    def _create_user_stream_tracker_task(self):
        # Injective does not use a tracker for the private streams
        return None

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        # Not used in Injective
        raise NotImplementedError()  # pragma: no cover

    async def _initialize_trading_pair_symbol_map(self):
        exchange_info = None
        try:
            mapping = await self._data_source.spot_market_and_trading_pair_map()
            self._set_trading_pair_symbol_map(mapping)
        except Exception:
            self.logger().exception("There was an error requesting exchange info.")
        return exchange_info

    def _configure_event_forwarders(self):
        event_forwarder = EventForwarder(to_function=self._process_user_trade_update)
        self._forwarders.append(event_forwarder)
        self._data_source.add_listener(event_tag=MarketEvent.TradeUpdate, listener=event_forwarder)

        event_forwarder = EventForwarder(to_function=self._process_user_order_update)
        self._forwarders.append(event_forwarder)
        self._data_source.add_listener(event_tag=MarketEvent.OrderUpdate, listener=event_forwarder)

        event_forwarder = EventForwarder(to_function=self._process_balance_event)
        self._forwarders.append(event_forwarder)
        self._data_source.add_listener(event_tag=AccountEvent.BalanceEvent, listener=event_forwarder)

        event_forwarder = EventForwarder(to_function=self._process_transaction_event)
        self._forwarders.append(event_forwarder)
        self._data_source.add_listener(event_tag=InjectiveEvent.ChainTransactionEvent, listener=event_forwarder)

    def _process_balance_event(self, event: BalanceUpdateEvent):
        self._all_trading_events_queue.put_nowait(
            {"channel": "balance", "data": event}
        )

    def _process_user_order_update(self, order_update: OrderUpdate):
        self._all_trading_events_queue.put_nowait(
            {"channel": "order", "data": order_update}
        )

    def _process_user_trade_update(self, trade_update: TradeUpdate):
        self._all_trading_events_queue.put_nowait(
            {"channel": "trade", "data": trade_update}
        )

    def _process_transaction_event(self, transaction_event: Dict[str, Any]):
        self._all_trading_events_queue.put_nowait(
            {"channel": "transaction", "data": transaction_event}
        )

    async def _check_orders_transactions(self):
        while True:
            try:
                # Executing the process shielded from this async task to isolate it from network disconnections
                # (network disconnections cancel this task)
                task = asyncio.create_task(self._check_orders_creation_transactions())
                await asyncio.shield(task)
                await self._sleep(CONSTANTS.TRANSACTIONS_CHECK_INTERVAL)
            except NotImplementedError:
                raise
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error while running the transactions check process", exc_info=True)
                await self._sleep(0.5)

    async def _check_orders_creation_transactions(self):
        orders: List[GatewayInFlightOrder] = self._order_tracker.active_orders.values()
        orders_by_creation_tx = defaultdict(list)

        for order in orders:
            if order.creation_transaction_hash is not None and order.is_pending_create:
                orders_by_creation_tx[order.creation_transaction_hash].append(order)

        for transaction_hash, orders in orders_by_creation_tx.items():
            try:
                order_updates = await self._data_source.order_updates_for_transaction(
                    transaction_hash=transaction_hash, spot_orders=orders
                )
                for order_update in order_updates:
                    self._order_tracker.process_order_update(order_update=order_update)

            except ValueError:
                self.logger().debug(f"Transaction not included in a block yet ({transaction_hash})")

    async def _check_created_orders_status_for_transaction(self, transaction_hash: str):
        transaction_orders = []
        order: GatewayInFlightOrder
        for order in self.in_flight_orders.values():
            if order.creation_transaction_hash == transaction_hash and order.is_pending_create:
                transaction_orders.append(order)

        if len(transaction_orders) > 0:
            order_updates = await self._data_source.order_updates_for_transaction(
                transaction_hash=transaction_hash, spot_orders=transaction_orders
            )

            for order_update in order_updates:
                self._order_tracker.process_order_update(order_update=order_update)

    async def _process_queued_orders(self):
        while True:
            try:
                # Executing the batch cancelation and creation process shielded from this async task to isolate the
                # creation/cancelation process from network disconnections (network disconnections cancel this task)
                task = asyncio.create_task(self._cancel_and_create_queued_orders())
                await asyncio.shield(task)
                sleep_time = (self.clock.tick_size * 0.5
                              if self.clock is not None
                              else self._orders_processing_delta_time)
                await self._sleep(sleep_time)
            except NotImplementedError:
                raise
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error while processing queued individual orders", exc_info=True)
                await self._sleep(self.clock.tick_size * 0.5)

    async def _cancel_and_create_queued_orders(self):
        if len(self._orders_queued_to_cancel) > 0:
            orders = [order.to_limit_order() for order in self._orders_queued_to_cancel]
            self._orders_queued_to_cancel = []
            await self._execute_batch_cancel(orders_to_cancel=orders)
        if len(self._orders_queued_to_create) > 0:
            orders = self._orders_queued_to_create
            self._orders_queued_to_create = []
            await self._execute_batch_inflight_order_create(inflight_orders_to_create=orders)

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        market_id = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        last_price = await self._data_source.last_traded_price(market_id=market_id)
        return float(last_price)

    def _get_poll_interval(self, timestamp: float) -> float:
        last_recv_diff = timestamp - self._data_source.last_received_message_timestamp
        poll_interval = (
            self.SHORT_POLL_INTERVAL
            if last_recv_diff > self.TICK_INTERVAL_LIMIT
            else self.LONG_POLL_INTERVAL
        )
        return poll_interval
