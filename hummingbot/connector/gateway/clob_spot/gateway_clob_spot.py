import asyncio
import math
from copy import deepcopy
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional, Tuple

from hummingbot.connector.client_order_tracker import ClientOrderTracker
from hummingbot.connector.constants import s_decimal_0, s_decimal_NaN
from hummingbot.connector.exchange_base import TradeType
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.gateway.clob_spot.data_sources.gateway_clob_api_data_source_base import CLOBAPIDataSourceBase
from hummingbot.connector.gateway.clob_spot.gateway_clob_api_order_book_data_source import (
    GatewayCLOBSPOTAPIOrderBookDataSource,
)
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.connector.gateway.gateway_order_tracker import GatewayOrderTracker
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.data_type.common import OrderType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import (
    AddedToCostTradeFee,
    DeductedFromReturnsTradeFee,
    MakerTakerExchangeFeeRates,
    TradeFeeBase,
)
from hummingbot.core.event.event_forwarder import EventForwarder
from hummingbot.core.event.events import AccountEvent, BalanceUpdateEvent, MarketEvent
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.utils.tracking_nonce import NonceCreator
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class GatewayCLOBSPOT(ExchangePyBase):
    def __init__(
        self,
        client_config_map: "ClientConfigAdapter",
        api_data_source: CLOBAPIDataSourceBase,
        connector_name: str,
        chain: str,
        network: str,
        address: str,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
    ):
        self._name = "_".join([connector_name, chain, network])
        self._connector_name = connector_name

        self._chain = chain
        self._network = network
        self._address = address
        self._trading_pairs = trading_pairs or []
        self._trading_required = trading_required
        self._api_data_source = api_data_source
        self._real_time_balance_update = self._api_data_source.real_time_balance_update
        self._trading_fees: Dict[str, MakerTakerExchangeFeeRates] = {}
        self._last_received_message_timestamp = 0
        self._forwarders: List[EventForwarder] = []
        self._nonce_provider: Optional[NonceCreator] = NonceCreator.for_milliseconds()

        self._add_forwarders()

        self.has_started = False

        super().__init__(client_config_map)

    @property
    def connector_name(self):
        """
        This returns the name of connector/protocol to be connected to on Gateway.
        """
        return self._connector_name

    @property
    def chain(self):
        return self._chain

    @property
    def network(self):
        return self._network

    @property
    def name(self) -> str:
        return self._name

    @property
    def domain(self) -> str:
        return ""

    @property
    def authenticator(self) -> Optional[AuthBase]:
        return None

    @property
    def rate_limits_rules(self) -> List[RateLimit]:
        return []

    @property
    def address(self):
        return self._address

    @property
    def client_order_id_prefix(self) -> str:
        return ""

    @property
    def client_order_id_max_length(self) -> Optional[int]:
        return None

    @property
    def trading_pairs(self) -> List[str]:
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return self._api_data_source.is_cancel_request_in_exchange_synchronous

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    @property
    def check_network_request_path(self):
        """Not used."""
        raise NotImplementedError

    @property
    def trading_pairs_request_path(self):
        """Not used."""
        raise NotImplementedError

    @property
    def trading_rules_request_path(self):
        """Not used."""
        raise NotImplementedError

    @property
    def trading_fees(self) -> Mapping[str, MakerTakerExchangeFeeRates]:
        return deepcopy(self._trading_fees)

    @property
    def status_dict(self) -> Dict[str, bool]:
        sd = super().status_dict
        sd["api_data_source_initialized"] = self._api_data_source.ready
        return sd

    def start(self, *args, **kwargs):
        super().start(**kwargs)
        safe_ensure_future(self.start_network())
        safe_ensure_future(self._api_data_source.start())

    def stop(self, *args, **kwargs):
        super().stop(**kwargs)
        safe_ensure_future(self._api_data_source.stop())

    async def start_network(self):
        if not self.has_started:
            await self._api_data_source.start()
            await super().start_network()
            self.has_started = True

    async def stop_network(self):
        await super().stop_network()
        await self._api_data_source.stop()
        self.has_started = False

    @property
    def ready(self) -> bool:
        return super().ready

    def supported_order_types(self) -> List[OrderType]:
        return self._api_data_source.get_supported_order_types()

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
        order_id = self._api_data_source.get_client_order_id(
            is_buy=True,
            trading_pair=trading_pair,
            hbot_order_id_prefix=self.client_order_id_prefix,
            max_id_len=self.client_order_id_max_length,
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
        order_id = self._api_data_source.get_client_order_id(
            is_buy=False,
            trading_pair=trading_pair,
            hbot_order_id_prefix=self.client_order_id_prefix,
            max_id_len=self.client_order_id_max_length,
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

    def batch_order_create(self, orders_to_create: List[LimitOrder]) -> List[LimitOrder]:
        """
        Issues a batch order creation as a single API request for exchanges that implement this feature. The default
        implementation of this method is to send the requests discretely (one by one).
        :param orders_to_create: A list of LimitOrder objects representing the orders to create. The order IDs
            can be blanc.
        :returns: A tuple composed of LimitOrder objects representing the created orders, complete with the generated
            order IDs.
        """
        orders_with_ids_to_create = []
        for order in orders_to_create:
            client_order_id = self._api_data_source.get_client_order_id(
                is_buy=order.is_buy,
                trading_pair=order.trading_pair,
                hbot_order_id_prefix=self.client_order_id_prefix,
                max_id_len=self.client_order_id_max_length,
            )
            orders_with_ids_to_create.append(
                LimitOrder(
                    client_order_id=client_order_id,
                    trading_pair=order.trading_pair,
                    is_buy=order.is_buy,
                    base_currency=order.base_currency,
                    quote_currency=order.quote_currency,
                    price=order.price,
                    quantity=order.quantity,
                    filled_quantity=order.filled_quantity,
                    creation_timestamp=order.creation_timestamp,
                    status=order.status,
                )
            )
        safe_ensure_future(self._execute_batch_order_create(orders_to_create=orders_with_ids_to_create))
        return orders_with_ids_to_create

    def batch_order_cancel(self, orders_to_cancel: List[LimitOrder]):
        """
        Issues a batch order cancelation as a single API request for exchanges that implement this feature. The default
        implementation of this method is to send the requests discretely (one by one).
        :param orders_to_cancel: A list of the orders to cancel.
        """
        safe_ensure_future(coro=self._execute_batch_cancel(orders_to_cancel=orders_to_cancel))

    async def _execute_batch_order_create(self, orders_to_create: List[LimitOrder]):
        in_flight_orders_to_create = []
        for order in orders_to_create:
            valid_order = await self._start_tracking_and_validate_order(
                trade_type=TradeType.BUY if order.is_buy else TradeType.SELL,
                order_id=order.client_order_id,
                trading_pair=order.trading_pair,
                amount=order.quantity,
                order_type=OrderType.LIMIT,
                price=order.price,
            )
            if valid_order is not None:
                in_flight_orders_to_create.append(valid_order)
        try:
            place_order_results = await self._api_data_source.batch_order_create(
                orders_to_create=in_flight_orders_to_create
            )
            for place_order_result, in_flight_order in (
                zip(place_order_results, in_flight_orders_to_create)
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
                    )
        except asyncio.CancelledError:
            raise
        except Exception as ex:
            self.logger().network("Batch order create failed.")
            for order in orders_to_create:
                self._on_order_creation_failure(
                    order_id=order.client_order_id,
                    trading_pair=order.trading_pair,
                    amount=order.quantity,
                    trade_type=TradeType.BUY if order.is_buy else TradeType.SELL,
                    order_type=OrderType.LIMIT,
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
    ) -> Optional[InFlightOrder]:
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
            self._update_order_after_creation_failure(order_id=order_id, trading_pair=trading_pair)
            order = None

        elif quantized_amount < trading_rule.min_order_size:
            self.logger().warning(f"{trade_type.name.title()} order amount {amount} is lower than the minimum order "
                                  f"size {trading_rule.min_order_size}. The order will not be created, increase the "
                                  f"amount to be higher than the minimum order size.")
            self._update_order_after_creation_failure(order_id=order_id, trading_pair=trading_pair)
            order = None
        elif notional_size < trading_rule.min_notional_size:
            self.logger().warning(f"{trade_type.name.title()} order notional {notional_size} is lower than the "
                                  f"minimum notional size {trading_rule.min_notional_size}. The order will not be "
                                  f"created. Increase the amount or the price to be higher than the minimum notional.")
            self._update_order_after_failure(order_id=order_id, trading_pair=trading_pair)
            order = None

        return order

    def _update_order_after_creation_success(
        self, exchange_order_id: str, order: InFlightOrder, update_timestamp: float
    ):
        order_update: OrderUpdate = OrderUpdate(
            client_order_id=order.client_order_id,
            exchange_order_id=str(exchange_order_id),
            trading_pair=order.trading_pair,
            update_timestamp=update_timestamp,
            new_state=OrderState.OPEN,
        )
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
            tracked_order = self._order_tracker.fetch_tracked_order(client_order_id=order.client_order_id)
            if tracked_order is not None:
                tracked_orders_to_cancel.append(tracked_order)
            else:
                results.append(CancellationResult(order_id=order.client_order_id, success=False))

        results.extend(await self._execute_batch_order_cancel(orders_to_cancel=tracked_orders_to_cancel))

        return results

    async def _execute_batch_order_cancel(self, orders_to_cancel: List[InFlightOrder]) -> List[CancellationResult]:
        try:
            cancel_order_results = await self._api_data_source.batch_order_cancel(orders_to_cancel=orders_to_cancel)
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

    def _update_order_after_cancelation_success(self, order: InFlightOrder):
        order_update: OrderUpdate = OrderUpdate(
            client_order_id=order.client_order_id,
            trading_pair=order.trading_pair,
            update_timestamp=self.current_timestamp,
            new_state=(OrderState.CANCELED
                       if self.is_cancel_request_in_exchange_synchronous
                       else OrderState.PENDING_CANCEL),
        )
        self._order_tracker.process_order_update(order_update)

    def _add_forwarders(self):
        event_forwarder = EventForwarder(to_function=self._process_trade_update)
        self._forwarders.append(event_forwarder)
        self._api_data_source.add_listener(event_tag=MarketEvent.TradeUpdate, listener=event_forwarder)

        event_forwarder = EventForwarder(to_function=self._process_order_update)
        self._forwarders.append(event_forwarder)
        self._api_data_source.add_listener(event_tag=MarketEvent.OrderUpdate, listener=event_forwarder)

        event_forwarder = EventForwarder(to_function=self._process_balance_event)
        self._forwarders.append(event_forwarder)
        self._api_data_source.add_listener(event_tag=AccountEvent.BalanceEvent, listener=event_forwarder)

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        data_source = GatewayCLOBSPOTAPIOrderBookDataSource(
            trading_pairs=self.trading_pairs, api_data_source=self._api_data_source
        )
        return data_source

    def _create_order_tracker(self) -> ClientOrderTracker:
        tracker = GatewayOrderTracker(connector=self, lost_order_count_limit=10)
        self._api_data_source.gateway_order_tracker = tracker
        return tracker

    def _is_user_stream_initialized(self):
        return self.trading_pair_symbol_map_ready()  # if ready, then self._api_data_source is initialized

    def _create_user_stream_tracker_task(self):
        return None

    def _create_user_stream_tracker(self):
        return None

    def _create_user_stream_data_source(self):
        return None

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        price = await self._api_data_source.get_last_traded_price(trading_pair=trading_pair)
        return float(price)

    async def _update_balances(self):
        balances = await self._api_data_source.get_account_balances()
        self._account_balances.clear()
        self._account_available_balances.clear()
        for asset, balance in balances.items():
            self._account_balances[asset] = Decimal(balance["total_balance"])
            self._account_available_balances[asset] = Decimal(balance["available_balance"])

    async def _make_network_check_request(self):
        network_status = await self._api_data_source.check_network_status()
        if network_status != NetworkStatus.CONNECTED:
            raise IOError("The API data source has lost connection.")

    async def _make_trading_rules_request(self) -> Mapping[str, str]:
        return await self._make_trading_pairs_request()

    async def _make_trading_pairs_request(self) -> Mapping[str, str]:
        symbol_map = await self._api_data_source.get_symbol_map()
        return symbol_map

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        trading_rules = await self._api_data_source.get_trading_rules()
        return list(trading_rules.values())

    async def _request_order_status(self, tracked_order: GatewayInFlightOrder) -> OrderUpdate:
        order_update = await self._api_data_source.get_order_status_update(in_flight_order=tracked_order)
        return order_update

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates = await self._api_data_source.get_all_order_fills(in_flight_order=order)
        return trade_updates

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        self._set_trading_pair_symbol_map(exchange_info)

    async def _update_trading_fees(self):
        self._trading_fees = await self._api_data_source.get_trading_fees()

    async def _update_time_synchronizer(self, pass_on_non_cancelled_error: bool = False):
        pass

    def _get_fee(
        self,
        base_currency: str,
        quote_currency: str,
        order_type: OrderType,
        order_side: TradeType,
        amount: Decimal,
        price: Decimal = s_decimal_NaN,
        is_maker: Optional[bool] = None,
    ) -> TradeFeeBase:
        is_maker = is_maker or (order_type is OrderType.LIMIT_MAKER)
        trading_pair = combine_to_hb_trading_pair(base=base_currency, quote=quote_currency)
        if trading_pair in self._trading_fees:
            fees_data = self._trading_fees[trading_pair]
            fee_value = Decimal(fees_data.maker) if is_maker else Decimal(fees_data.taker)
            flat_fees = fees_data.maker_flat_fees if is_maker else fees_data.taker_flat_fees
            if order_side == TradeType.BUY:
                fee = AddedToCostTradeFee(percent=fee_value, percent_token=quote_currency, flat_fees=flat_fees)
            else:
                fee = DeductedFromReturnsTradeFee(percent=fee_value, percent_token=quote_currency, flat_fees=flat_fees)
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

    async def _place_order(
        self,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        trade_type: TradeType,
        order_type: OrderType,
        price: Decimal,
        **kwargs,
    ) -> Tuple[str, float]:
        """Not used."""
        raise NotImplementedError

    async def _place_order_and_process_update(self, order: GatewayInFlightOrder, **kwargs) -> str:
        exchange_order_id, misc_order_updates = await self._api_data_source.place_order(order=order, **kwargs)
        order_update: OrderUpdate = OrderUpdate(
            client_order_id=order.client_order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=order.trading_pair,
            update_timestamp=self.current_timestamp,
            new_state=OrderState.PENDING_CREATE,
            misc_updates=misc_order_updates,
        )
        self._order_tracker.process_order_update(order_update)

        return exchange_order_id

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        """Not used."""
        raise NotImplementedError

    async def _execute_order_cancel_and_process_update(self, order: GatewayInFlightOrder) -> bool:
        cancelled, misc_order_updates = await self._api_data_source.cancel_order(order=order)

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
                misc_updates=misc_order_updates,
            )
            self._order_tracker.process_order_update(order_update)

        return cancelled

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception) -> bool:
        """Not used."""
        return False

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return self._api_data_source.is_order_not_found_during_status_update_error(
            status_update_exception=status_update_exception
        )

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return self._api_data_source.is_order_not_found_during_cancelation_error(
            cancelation_exception=cancelation_exception
        )

    async def _user_stream_event_listener(self):
        """Not used."""
        pass

    def _process_trade_update(self, trade_update: TradeUpdate):
        self._last_received_message_timestamp = self._time()
        self._order_tracker.process_trade_update(trade_update)

    def _process_order_update(self, order_update: OrderUpdate):
        self._last_received_message_timestamp = self._time()
        self._order_tracker.process_order_update(order_update=order_update)

    def _process_balance_event(self, balance_event: BalanceUpdateEvent):
        self._last_received_message_timestamp = self._time()
        if balance_event.total_balance is not None:
            self._account_balances[balance_event.asset_name] = balance_event.total_balance
        if balance_event.available_balance is not None:
            self._account_available_balances[balance_event.asset_name] = balance_event.available_balance

    def _create_web_assistants_factory(self) -> Optional[WebAssistantsFactory]:
        return None

    def _get_poll_interval(self, timestamp: float) -> float:
        last_recv_diff = timestamp - self._last_received_message_timestamp
        poll_interval = (
            self.SHORT_POLL_INTERVAL
            if last_recv_diff > self.TICK_INTERVAL_LIMIT or not self._api_data_source.events_are_streamed
            else self.LONG_POLL_INTERVAL
        )
        return poll_interval

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        timeout = self._api_data_source.cancel_all_orders_timeout \
            if self._api_data_source.cancel_all_orders_timeout is not None \
            else timeout_seconds

        return await super().cancel_all(timeout)
