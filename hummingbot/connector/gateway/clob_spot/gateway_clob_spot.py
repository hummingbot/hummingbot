from copy import deepcopy
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional, Tuple

from hummingbot.connector.client_order_tracker import ClientOrderTracker
from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange_base import TradeType
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.gateway.clob_spot.data_sources.gateway_clob_api_data_source_base import (
    GatewayCLOBAPIDataSourceBase,
)
from hummingbot.connector.gateway.clob_spot.gateway_clob_api_order_book_data_source import (
    GatewayCLOBSPOTAPIOrderBookDataSource,
)
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.connector.gateway.gateway_order_tracker import GatewayOrderTracker
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
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
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class GatewayCLOBSPOT(ExchangePyBase):
    def __init__(
        self,
        client_config_map: "ClientConfigAdapter",
        api_data_source: GatewayCLOBAPIDataSourceBase,
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
        self._trading_fees: Dict[str, MakerTakerExchangeFeeRates] = {}
        self._last_received_message_timestamp = 0
        self._forwarders: List[EventForwarder] = []

        self._add_forwarders()

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

    async def start_network(self):
        await self._api_data_source.start()
        await super().start_network()

    async def stop_network(self):
        await super().stop_network()
        await self._api_data_source.stop()

    def tick(self, timestamp: float):
        """
        Includes the logic that has to be processed every time a new tick happens in the bot. Particularly it enables
        the execution of the status update polling loop using an event.
        """
        last_recv_diff = timestamp - self._last_received_message_timestamp
        poll_interval = (self.SHORT_POLL_INTERVAL
                         if last_recv_diff > self.TICK_INTERVAL_LIMIT
                         else self.LONG_POLL_INTERVAL)
        last_tick = int(self._last_timestamp / poll_interval)
        current_tick = int(timestamp / poll_interval)
        if current_tick > last_tick:
            self._poll_notifier.set()
        self._last_timestamp = timestamp

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
            order_update: OrderUpdate = OrderUpdate(
                client_order_id=order.client_order_id,
                trading_pair=order.trading_pair,
                update_timestamp=self.current_timestamp,
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
