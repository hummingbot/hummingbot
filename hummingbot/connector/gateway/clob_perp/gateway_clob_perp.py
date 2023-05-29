from copy import deepcopy
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional, Tuple

from hummingbot.connector.client_order_tracker import ClientOrderTracker
from hummingbot.connector.constants import FUNDING_FEE_POLL_INTERVAL, s_decimal_NaN
from hummingbot.connector.derivative.position import Position
from hummingbot.connector.gateway.clob_perp.data_sources.clob_perp_api_data_source_base import CLOBPerpAPIDataSourceBase
from hummingbot.connector.gateway.clob_perp.gateway_clob_perp_api_order_book_data_source import (
    GatewayCLOBPerpAPIOrderBookDataSource,
)
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayPerpetualInFlightOrder
from hummingbot.connector.gateway.gateway_order_tracker import GatewayOrderTracker
from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, TradeType
from hummingbot.core.data_type.funding_info import FundingInfoUpdate
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.perpetual_api_order_book_data_source import PerpetualAPIOrderBookDataSource
from hummingbot.core.data_type.trade_fee import (
    AddedToCostTradeFee,
    DeductedFromReturnsTradeFee,
    MakerTakerExchangeFeeRates,
    TradeFeeBase,
)
from hummingbot.core.event.event_forwarder import EventForwarder
from hummingbot.core.event.events import AccountEvent, BalanceUpdateEvent, MarketEvent, PositionUpdateEvent
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.auth import AuthBase

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class GatewayCLOBPerp(PerpetualDerivativePyBase):
    def __init__(
        self,
        client_config_map: "ClientConfigAdapter",
        api_data_source: CLOBPerpAPIDataSourceBase,
        connector_name: str,
        chain: str,
        network: str,
        address: str,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
    ) -> None:

        self._name = "_".join([connector_name, chain, network])
        self._connector_name = connector_name
        self._chain = chain
        self._network = network
        self._address = address
        self._trading_pairs = trading_pairs or []
        self._trading_required = trading_required
        self._api_data_source = api_data_source

        self._last_received_message_timestamp = 0
        self._forwarders: List[EventForwarder] = []

        self._add_forwarders()

        super().__init__(client_config_map)

    # region >>> Objective Attributes >>>

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
        return False

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

    @property
    def funding_fee_poll_interval(self) -> int:
        return FUNDING_FEE_POLL_INTERVAL

    @property
    def supported_position_modes(self) -> List[PositionMode]:
        return self._api_data_source.supported_position_modes

    # endregion

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

        event_forwarder = EventForwarder(to_function=self._process_funding_info_event)
        self._forwarders.append(event_forwarder)
        self._api_data_source.add_listener(event_tag=MarketEvent.FundingInfo, listener=event_forwarder)

        event_forwarder = EventForwarder(to_function=self._process_position_update_event)
        self._forwarders.append(event_forwarder)
        self._api_data_source.add_listener(event_tag=AccountEvent.PositionUpdate, listener=event_forwarder)

    def _create_order_book_data_source(self) -> PerpetualAPIOrderBookDataSource:
        data_source = GatewayCLOBPerpAPIOrderBookDataSource(
            trading_pairs=self.trading_pairs, api_data_source=self._api_data_source
        )
        return data_source

    def _create_order_tracker(self) -> ClientOrderTracker:
        tracker = GatewayOrderTracker(connector=self, lost_order_count_limit=10)
        self._api_data_source.gateway_order_tracker = tracker
        return tracker

    def _create_user_stream_tracker_task(self):
        return None

    def _create_user_stream_tracker(self):
        return None

    def _create_user_stream_data_source(self):
        return None

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        price = await self._api_data_source.get_last_traded_price(trading_pair=trading_pair)
        return float(price)

    def _create_web_assistants_factory(self):
        return None

    def _is_user_stream_initialized(self):
        return self.trading_pair_symbol_map_ready()  # if ready, then self._api_data_source is initialized

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception) -> bool:
        """
        Not used.
        """
        return False

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return self._api_data_source.is_order_not_found_during_status_update_error(status_update_exception)

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return self._api_data_source.is_order_not_found_during_cancelation_error(cancelation_exception)

    async def start_network(self):
        await self._api_data_source.start()
        await super().start_network()

    async def stop_network(self):
        await super().stop_network()
        await self._api_data_source.stop()

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
        position_action: PositionAction = PositionAction.NIL,
        **kwargs,
    ):
        leverage = self.get_leverage(trading_pair=trading_pair)
        self._order_tracker.start_tracking_order(
            GatewayPerpetualInFlightOrder(
                client_order_id=order_id,
                exchange_order_id=exchange_order_id,
                trading_pair=trading_pair,
                order_type=order_type,
                trade_type=trade_type,
                amount=amount,
                price=price,
                creation_timestamp=self.current_timestamp,
                leverage=leverage,
                position=position_action,
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

    def get_buy_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.buy_order_collateral_token

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        trading_rule: TradingRule = self._trading_rules[trading_pair]
        return trading_rule.sell_order_collateral_token

    async def _update_time_synchronizer(self, pass_on_non_cancelled_error: bool = False):
        pass

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        self._set_trading_pair_symbol_map(exchange_info)

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

    async def _place_order(
        self,
        order_id: str,
        trading_pair: str,
        amount: Decimal,
        trade_type: TradeType,
        order_type: OrderType,
        price: Decimal,
        position_action: PositionAction = PositionAction.NIL,
        **kwargs,
    ) -> Tuple[str, float]:
        """
        Not used.
        """
        raise NotImplementedError

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        """
        Not used.
        """
        raise NotImplementedError

    async def _user_stream_event_listener(self):
        """
        Not used.
        """
        pass

    async def _update_positions(self):
        positions: List[Position] = await self._api_data_source.fetch_positions()
        for position in positions:
            position_key = self._perpetual_trading.position_key(position.trading_pair, position.position_side)
            if position.amount != Decimal("0"):
                position._leverage = self._perpetual_trading.get_leverage(trading_pair=position.trading_pair)
                self._perpetual_trading.set_position(pos_key=position_key, position=position)
            else:
                self._perpetual_trading.remove_position(post_key=position_key)

    async def _update_balances(self):
        balances = await self._api_data_source.get_account_balances()
        self._account_balances.clear()
        self._account_available_balances.clear()
        for asset, balance in balances.items():
            self._account_balances[asset] = Decimal(balance["total_balance"])
            self._account_available_balances[asset] = Decimal(balance["available_balance"])

    async def _update_trading_fees(self):
        self._trading_fees = await self._api_data_source.get_trading_fees()

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        status_update = await self._api_data_source.get_order_status_update(in_flight_order=tracked_order)
        return status_update

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        return await self._api_data_source.get_all_order_fills(in_flight_order=order)

    async def _trading_pair_position_mode_set(self, mode: PositionMode, trading_pair: str) -> Tuple[bool, str]:
        return await self._api_data_source.trading_pair_position_mode_set(mode=mode, trading_pair=trading_pair)

    async def _set_trading_pair_leverage(self, trading_pair: str, leverage: int) -> Tuple[bool, str]:
        return await self._api_data_source.set_trading_pair_leverage(trading_pair=trading_pair, leverage=leverage)

    async def _fetch_last_fee_payment(self, trading_pair: str) -> Tuple[float, Decimal, Decimal]:
        return await self._api_data_source.fetch_last_fee_payment(trading_pair=trading_pair)

    def _get_fee(
        self,
        base_currency: str,
        quote_currency: str,
        order_type: OrderType,
        order_side: TradeType,
        position_action: PositionAction,
        amount: Decimal,
        price: Decimal = ...,
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

    async def _place_order_and_process_update(self, order: GatewayPerpetualInFlightOrder, **kwargs) -> str:
        order.leverage = self._perpetual_trading.get_leverage(trading_pair=order.trading_pair)
        exchange_order_id, misc_order_updates = await self._api_data_source.place_order(order, **kwargs)
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

    async def _execute_order_cancel_and_process_update(self, order: GatewayPerpetualInFlightOrder) -> bool:
        cancelled, misc_order_updates = await self._api_data_source.cancel_order(order=order)

        if cancelled:
            order_update: OrderUpdate = OrderUpdate(
                client_order_id=order.client_order_id,
                trading_pair=order.trading_pair,
                update_timestamp=self.current_timestamp,
                new_state=(
                    OrderState.CANCELED if self.is_cancel_request_in_exchange_synchronous else OrderState.PENDING_CANCEL
                ),
                misc_updates=misc_order_updates,
            )
            self._order_tracker.process_order_update(order_update)

        return cancelled

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

    def _process_position_update_event(self, position_update_event: PositionUpdateEvent):
        self._last_received_message_timestamp = self._time()
        position_key = self._perpetual_trading.position_key(
            position_update_event.trading_pair, position_update_event.position_side
        )
        if position_update_event.amount != Decimal("0"):
            position: Position = self._perpetual_trading.get_position(
                trading_pair=position_update_event.trading_pair, side=position_update_event.position_side
            )
            if position is not None:
                leverage: Decimal = (
                    # If event leverage is set to -1, the initial leverage is used. This is for specific cases when the
                    # DataSource does not provide any leverage information in the position stream response
                    position.leverage if position_update_event.leverage == Decimal("-1") else position_update_event.leverage
                )
                position.update_position(
                    position_side=position_update_event.position_side,
                    unrealized_pnl=position_update_event.unrealized_pnl,
                    entry_price=position_update_event.entry_price,
                    amount=position_update_event.amount,
                    leverage=leverage,
                )
            else:
                safe_ensure_future(coro=self._update_positions())
        else:
            self._perpetual_trading.remove_position(post_key=position_key)

    def _process_funding_info_event(self, funding_info_event: FundingInfoUpdate):
        self._last_received_message_timestamp = self._time()
        self._perpetual_trading.funding_info_stream.put_nowait(funding_info_event)

    def _get_poll_interval(self, timestamp: float) -> float:
        last_recv_diff = timestamp - self._last_received_message_timestamp
        poll_interval = (
            self.SHORT_POLL_INTERVAL
            if last_recv_diff > self.TICK_INTERVAL_LIMIT or not self._api_data_source.events_are_streamed
            else self.LONG_POLL_INTERVAL
        )
        return poll_interval
