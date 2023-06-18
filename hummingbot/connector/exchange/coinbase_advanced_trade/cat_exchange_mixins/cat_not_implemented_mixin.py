from typing import Any, Dict, List, Protocol

from hummingbot.connector.trading_rule import TradingRule


class _NameProtocol(Protocol):
    name: str


class CoinbaseAdvancedTradeNotImplementedMixin:
    def __init__(self, **kwargs):
        if super().__class__ is not object:
            super().__init__(**kwargs)

    @property
    def trading_rules_request_path(self: _NameProtocol) -> str:
        raise NotImplementedError(f"This method is not implemented by {self.name} connector")

    @property
    def trading_pairs_request_path(self: _NameProtocol) -> str:
        raise NotImplementedError(f"This method is not implemented by {self.name} connector")

    @property
    def check_network_request_path(self: _NameProtocol) -> str:
        raise NotImplementedError(f"This method is not implemented by {self.name} connector")

    async def _format_trading_rules(self: _NameProtocol, e: Dict[str, Any]) -> List[TradingRule]:
        raise NotImplementedError(f"This method is not implemented by {self.name} connector")

    def _initialize_trading_pair_symbols_from_exchange_info(self: _NameProtocol, exchange_info: Dict[str, Any]):
        raise NotImplementedError(f"This method is not implemented by {self.name} connector")

    def _make_trading_rules_request(self: _NameProtocol) -> Any:
        raise NotImplementedError(f"This method is not implemented by {self.name} connector")

    def _make_trading_pairs_request(self: _NameProtocol) -> Any:
        raise NotImplementedError(f"This method is not implemented by {self.name} connector")
