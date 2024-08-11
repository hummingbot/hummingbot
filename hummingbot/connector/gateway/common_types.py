from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class Chain(Enum):
    ETHEREUM = ('ethereum', 'ETH')
    TEZOS = ('tezos', 'XTZ')
    TELOS = ('telos', 'TLOS')

    def __init__(self, chain: str, native_currency: str):
        self.chain = chain
        self.native_currency = native_currency


class Connector(Enum):
    def __int__(self, chain: Chain, connector: str):
        self.chain = chain
        self.connector = connector


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
