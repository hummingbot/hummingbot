import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

from bidict import bidict

from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.connector.gateway.gateway_order_tracker import GatewayOrderTracker
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.trade_fee import MakerTakerExchangeFeeRates
from hummingbot.core.event.event_forwarder import EventForwarder
from hummingbot.core.event.event_listener import EventListener
from hummingbot.core.event.events import AccountEvent, MarketEvent, OrderBookDataSourceEvent
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.pubsub import HummingbotLogger, PubSub


@dataclass
class PlaceOrderResult:
    update_timestamp: float
    client_order_id: str
    exchange_order_id: Optional[str]
    trading_pair: str
    misc_updates: Dict[str, Any] = field(default_factory=lambda: {})
    exception: Optional[Exception] = None


@dataclass
class CancelOrderResult:
    client_order_id: str
    trading_pair: str
    misc_updates: Dict[str, Any] = field(default_factory=lambda: {})
    not_found: bool = False
    exception: Optional[Exception] = None


class GatewayCLOBAPIDataSourceBase(ABC):
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(HummingbotLogger.logger_name_for_class(cls))
        return cls._logger

    def __init__(self):
        self._publisher = PubSub()
        self._forwarders_map: Dict[Tuple[Enum, Callable], EventForwarder] = {}
        self._gateway_order_tracker: Optional[GatewayOrderTracker] = None

    @property
    def gateway_order_tracker(self):
        return self._gateway_order_tracker

    @gateway_order_tracker.setter
    def gateway_order_tracker(self, tracker: GatewayOrderTracker):
        if self._gateway_order_tracker is not None:
            raise RuntimeError("Attempted to re-assign the order tracker.")
        self._gateway_order_tracker = tracker

    @staticmethod
    def supported_stream_events() -> List[Enum]:
        return [
            MarketEvent.TradeUpdate,
            MarketEvent.OrderUpdate,
            AccountEvent.BalanceEvent,
            OrderBookDataSourceEvent.TRADE_EVENT,
            OrderBookDataSourceEvent.DIFF_EVENT,
            OrderBookDataSourceEvent.SNAPSHOT_EVENT,
        ]

    def add_listener(self, event_tag: Enum, listener: EventListener):
        self._publisher.add_listener(event_tag=event_tag, listener=listener)

    def remove_listener(self, event_tag: Enum, listener: EventListener):
        self._publisher.remove_listener(event_tag=event_tag, listener=listener)

    @abstractmethod
    def get_supported_order_types(self) -> List[OrderType]:
        ...

    @abstractmethod
    async def start(self):
        ...

    @abstractmethod
    async def stop(self):
        ...

    @abstractmethod
    async def place_order(
        self, order: GatewayInFlightOrder, **kwargs
    ) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """
        :return: A tuple of the exchange order ID and any misc order updates.
        """
        ...

    @abstractmethod
    async def batch_order_create(self, orders_to_create: List[InFlightOrder]) -> List[PlaceOrderResult]:
        """
        :param orders_to_create: The collection of orders to create.
        :return: The result of the batch order create attempt.
        """
        ...

    @abstractmethod
    async def cancel_order(self, order: GatewayInFlightOrder) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        :return: A tuple of the boolean indicating the cancelation success and any misc order updates.
        """
        ...

    @abstractmethod
    async def batch_order_cancel(self, orders_to_cancel: List[InFlightOrder]) -> List[CancelOrderResult]:
        """
        :param orders_to_cancel: The collection of orders to cancel.
        :return: The result of the batch order cancel attempt.
        """
        ...

    @abstractmethod
    async def get_trading_rules(self) -> Dict[str, TradingRule]:
        ...

    @abstractmethod
    async def get_symbol_map(self) -> bidict[str, str]:
        ...

    @abstractmethod
    async def get_last_traded_price(self, trading_pair: str) -> Decimal:
        ...

    @abstractmethod
    async def get_order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        ...

    @abstractmethod
    async def get_account_balances(self) -> Dict[str, Dict[str, Decimal]]:
        ...

    @abstractmethod
    async def get_order_status_update(self, in_flight_order: InFlightOrder) -> OrderUpdate:
        ...

    @abstractmethod
    async def get_all_order_fills(self, in_flight_order: InFlightOrder) -> List[TradeUpdate]:
        ...

    @abstractmethod
    async def check_network_status(self) -> NetworkStatus:
        ...

    @abstractmethod
    async def get_trading_fees(self) -> Mapping[str, MakerTakerExchangeFeeRates]:
        ...

    @abstractmethod
    def is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        ...

    @abstractmethod
    def is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        ...
