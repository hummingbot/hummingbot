from enum import Enum
from typing import Any, AsyncIterable, Dict, Iterable, List, Mapping, Optional, Protocol, Set, runtime_checkable

from _decimal import Decimal

from hummingbot.connector.client_order_tracker import ClientOrderTracker
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.in_flight_order import InFlightOrder
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.logger import HummingbotLogger


@runtime_checkable
class CoinbaseAdvancedTradeAPIRequestProtocol(Protocol):
    endpoint: str
    method: RESTMethod
    limit_id: str

    def data(self) -> Dict[str, Any]:
        ...

    def params(self) -> Dict[str, Any]:
        ...

    @staticmethod
    def is_auth_required() -> bool:
        ...


@runtime_checkable
class CoinbaseAdvancedTradeAPICallsMixinProtocol(Protocol):
    async def api_post(self, *args, **kwargs) -> Dict[str, Any]:
        ...

    async def api_delete(self, *args, **kwargs) -> Dict[str, Any]:
        ...

    async def api_get(self, *args, **kwargs) -> Dict[str, Any]:
        ...


@runtime_checkable
class CoinbaseAdvancedTradeTradingPairsMixinProtocol(Protocol):
    trading_pairs: List[str]
    trading_rules: Dict[str, TradingRule]

    async def exchange_symbol_associated_to_pair(self, trading_pair: str) -> str:
        ...

    async def trading_pair_associated_to_exchange_symbol(self, symbol: str) -> str:
        ...

    def set_trading_pair_symbol_map(self, trading_pair_and_symbol_map: Optional[Mapping[str, str]]):
        ...


@runtime_checkable
class CoinbaseAdvancedTradeAccountsMixinProtocol(Protocol):
    def get_balances_keys(self) -> Set[str]:
        ...

    def update_balance(self, asset: str, balance: Decimal):
        ...

    def update_available_balance(self, asset: str, balance: Decimal):
        ...

    def remove_balances(self, assets: Iterable[str]):
        ...


@runtime_checkable
class CoinbaseAdvancedTradeWebsocketMixinProtocol(Protocol):
    in_flight_orders: Dict[str, InFlightOrder]
    order_tracker: ClientOrderTracker

    def iter_user_event_queue(self) -> AsyncIterable[Dict[str, Any]]:
        ...


@runtime_checkable
class CoinbaseAdvancedTradeUtilitiesMixinProtocol(Protocol):
    LONG_POLL_INTERVAL: float
    UPDATE_ORDER_STATUS_MIN_INTERVAL: float

    name: str
    display_name: str
    domain: str
    time_synchronizer: TimeSynchronizer
    last_poll_timestamp: float
    current_timestamp: float

    async def _sleep(self, sleep: float):
        ...

    def logger(self) -> HummingbotLogger:
        ...


@runtime_checkable
class CoinbaseAdvancedTradeOrdersMixinProtocol(Protocol):
    exchange_order_ids: Dict
    current_trade_fills: Set

    def is_confirmed_new_order_filled_event(self, exchange_trade_id: str, exchange_order_id: str, trading_pair: str):
        ...

    def trigger_event(self, event_tag: Enum, message: Any):
        ...
