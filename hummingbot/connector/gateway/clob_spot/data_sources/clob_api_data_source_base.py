import logging
from abc import ABC, abstractmethod
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

from bidict import bidict

from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.gateway.common_types import CancelOrderResult, PlaceOrderResult
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.connector.gateway.gateway_order_tracker import GatewayOrderTracker
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import get_new_client_order_id
from hummingbot.core.data_type.common import OrderType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.trade_fee import MakerTakerExchangeFeeRates
from hummingbot.core.event.event_forwarder import EventForwarder
from hummingbot.core.event.event_listener import EventListener
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.pubsub import HummingbotLogger, PubSub


class CLOBAPIDataSourceBase(ABC):
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(HummingbotLogger.logger_name_for_class(cls))
        return cls._logger

    def __init__(
        self,
        trading_pairs: List[str],
        connector_spec: Dict[str, Any],
        client_config_map: ClientConfigAdapter,
    ):
        self._trading_pairs = trading_pairs
        self._connector_spec = connector_spec
        self._client_config = client_config_map
        self._publisher = PubSub()
        self._forwarders_map: Dict[Tuple[Enum, Callable], EventForwarder] = {}
        self._gateway_order_tracker: Optional[GatewayOrderTracker] = None
        self._markets_info: Dict[str, Any] = {}
        self.cancel_all_orders_timeout = None

    @property
    @abstractmethod
    def real_time_balance_update(self) -> bool:
        ...

    @property
    @abstractmethod
    def events_are_streamed(self) -> bool:
        """Set this to False if the exchange does not offer event streams."""
        ...

    @staticmethod
    @abstractmethod
    def supported_stream_events() -> List[Enum]:
        """This method serves as a guide to what events a client of this class expects an implementation to
        provide.
        """
        ...

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
    async def get_last_traded_price(self, trading_pair: str) -> Decimal:
        ...

    @abstractmethod
    async def get_order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        ...

    @abstractmethod
    async def get_account_balances(self) -> Dict[str, Dict[str, Decimal]]:
        """Returns a dictionary like

                {
                    asset_name: {
                        "total_balance": Decimal,
                        "available_balance": Decimal,
                    }
                }
        """
        ...

    @abstractmethod
    async def get_order_status_update(self, in_flight_order: InFlightOrder) -> OrderUpdate:
        ...

    @abstractmethod
    async def get_all_order_fills(self, in_flight_order: InFlightOrder) -> List[TradeUpdate]:
        ...

    @abstractmethod
    def is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        ...

    @abstractmethod
    def is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        ...

    @abstractmethod
    async def check_network_status(self) -> NetworkStatus:
        ...

    @abstractmethod
    def _check_markets_initialized(self) -> bool:
        ...

    @abstractmethod
    async def _update_markets(self):
        ...

    @abstractmethod
    def _parse_trading_rule(self, trading_pair: str, market_info: Any) -> TradingRule:
        ...

    @abstractmethod
    def _get_exchange_trading_pair_from_market_info(self, market_info: Any) -> str:
        ...

    @abstractmethod
    def _get_maker_taker_exchange_fee_rates_from_market_info(self, market_info: Any) -> MakerTakerExchangeFeeRates:
        ...

    @property
    def gateway_order_tracker(self):
        return self._gateway_order_tracker

    @property
    def ready(self) -> bool:
        return self._check_markets_initialized()

    @gateway_order_tracker.setter
    def gateway_order_tracker(self, tracker: GatewayOrderTracker):
        if self._gateway_order_tracker is not None:
            raise RuntimeError("Attempted to re-assign the order tracker.")
        self._gateway_order_tracker = tracker

    @staticmethod
    def get_client_order_id(
        is_buy: bool, trading_pair: str, hbot_order_id_prefix: str, max_id_len: Optional[int]
    ) -> str:
        return get_new_client_order_id(is_buy, trading_pair, hbot_order_id_prefix, max_id_len)

    async def get_trading_rules(self) -> Dict[str, TradingRule]:
        self._check_markets_initialized() or await self._update_markets()

        trading_rules = {
            trading_pair: self._parse_trading_rule(trading_pair=trading_pair, market_info=market)
            for trading_pair, market in self._markets_info.items()
        }
        return trading_rules

    async def get_symbol_map(self) -> bidict[str, str]:
        self._check_markets_initialized() or await self._update_markets()

        mapping = bidict()
        for trading_pair, market_info in self._markets_info.items():
            exchange_symbol = self._get_exchange_trading_pair_from_market_info(market_info=market_info)
            mapping[exchange_symbol] = trading_pair

        return mapping

    async def get_trading_fees(self) -> Mapping[str, MakerTakerExchangeFeeRates]:
        self._check_markets_initialized() or await self._update_markets()

        trading_fees = {}
        for trading_pair, market_inf in self._markets_info.items():
            trading_fees[trading_pair] = self._get_maker_taker_exchange_fee_rates_from_market_info(
                market_info=market_inf
            )
        return trading_fees

    def add_listener(self, event_tag: Enum, listener: EventListener):
        self._publisher.add_listener(event_tag=event_tag, listener=listener)

    def remove_listener(self, event_tag: Enum, listener: EventListener):
        self._publisher.remove_listener(event_tag=event_tag, listener=listener)

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return False
