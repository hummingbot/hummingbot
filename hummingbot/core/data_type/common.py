from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Generic, List, NamedTuple, Optional, Set, TypeVar

from pydantic_core import core_schema


class OrderType(Enum):
    MARKET = 1
    LIMIT = 2
    LIMIT_MAKER = 3
    AMM_SWAP = 4
    IOC = 5  # Immediate-Or-Cancel (CLOB-specific)
    FOK = 6  # Fill-Or-Kill (CLOB-specific)
    PREDICTION_LIMIT = 7  # Limit order for prediction markets
    PREDICTION_MARKET = 8  # Market order for prediction markets

    def is_limit_type(self):
        return self in (
            OrderType.LIMIT,
            OrderType.LIMIT_MAKER,
            OrderType.IOC,
            OrderType.FOK,
            OrderType.PREDICTION_LIMIT,
        )

    def is_prediction_type(self):
        return self in (
            OrderType.PREDICTION_LIMIT,
            OrderType.PREDICTION_MARKET,
        )


class OpenOrder(NamedTuple):
    client_order_id: str
    trading_pair: str
    price: Decimal
    amount: Decimal
    executed_amount: Decimal
    status: str
    order_type: OrderType
    is_buy: bool
    time: int
    exchange_order_id: str


class PositionAction(Enum):
    OPEN = "OPEN"
    CLOSE = "CLOSE"
    NIL = "NIL"


# For Derivatives Exchanges
class PositionSide(Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    BOTH = "BOTH"


# For Derivatives Exchanges
class PositionMode(Enum):
    HEDGE = "HEDGE"
    ONEWAY = "ONEWAY"


class PriceType(Enum):
    MidPrice = 1
    BestBid = 2
    BestAsk = 3
    LastTrade = 4
    LastOwnTrade = 5
    InventoryCost = 6
    Custom = 7


class TradeType(Enum):
    BUY = 1
    SELL = 2
    RANGE = 3


class OutcomeType(Enum):
    """
    Outcome direction for event-based markets (e.g., prediction markets).
    Typical outcomes are YES/NO.
    """
    YES = 1
    NO = 2


class EventResolution(Enum):
    """
    Resolution states for event markets once the oracle/outcome is known.
    Values align with common prediction-market semantics.
    """
    YES = "YES"
    NO = "NO"
    INVALID = "INVALID"
    CANCELLED = "CANCELLED"
    PENDING = "PENDING"  # Market not yet resolved


class LPType(Enum):
    ADD = 1
    REMOVE = 2
    COLLECT = 3


_KT = TypeVar('_KT')
_VT = TypeVar('_VT')


class GroupedSetDict(dict[_KT, Set[_VT]]):
    def add_or_update(self, key: _KT, *args: _VT) -> "GroupedSetDict":
        if key in self:
            self[key].update(args)
        else:
            self[key] = set(args)
        return self

    def remove(self, key: _KT, value: _VT) -> "GroupedSetDict":
        if key in self:
            self[key].discard(value)
            if not self[key]:  # If set becomes empty, remove the key
                del self[key]
        return self

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source_type: Any,
        _handler: Any,
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls,
            core_schema.dict_schema(
                core_schema.any_schema(),
                core_schema.set_schema(core_schema.any_schema())
            )
        )


MarketDict = GroupedSetDict[str, Set[str]]


# TODO? : Allow pulling the hash for _KT via a lambda so that things like type can be a key?
class LazyDict(dict[_KT, _VT], Generic[_KT, _VT]):
    def __init__(self, default_value_factory: Callable[[_KT], _VT] = None):
        super().__init__()
        self.default_value_factory = default_value_factory

    def __missing__(self, key: _KT) -> _VT:
        if self.default_value_factory is None:
            raise KeyError(f"Key {key} not found in {self} and no default value factory is set")
        self[key] = self.default_value_factory(key)
        return self[key]

    def get(self, key: _KT) -> _VT:
        if key in self:
            return self[key]
        return self.__missing__(key)

    def get_or_add(self, key: _KT, value_factory: Callable[[], _VT]) -> _VT:
        if key not in self:
            self[key] = value_factory()
        return self[key]


# Event Market Data Structures
class OutcomeInfo(NamedTuple):
    """Information about a specific outcome in a prediction market."""
    outcome_id: str  # Token ID for the outcome
    outcome_name: str  # "YES" or "NO"
    current_price: Decimal  # Current price (0-1)
    token_address: str  # Conditional token address
    volume_24h: Decimal = Decimal("0")
    liquidity: Decimal = Decimal("0")


class EventMarketInfo(NamedTuple):
    """Information about a prediction/event market."""
    market_id: str  # Unique identifier (condition_id in Polymarket)
    question: str  # Event question/description
    outcomes: List[OutcomeInfo]  # Possible outcomes (YES/NO)
    resolution_date: Optional[float] = None  # Expected resolution time (timestamp)
    resolution_source: str = ""  # Oracle/source for resolution
    tags: List[str] = []  # Market categories
    volume_24h: Decimal = Decimal("0")  # 24h trading volume
    liquidity: Decimal = Decimal("0")  # Available liquidity
    status: EventResolution = EventResolution.PENDING  # Current resolution status


class EventPosition(NamedTuple):
    """Position in an event/prediction market."""
    market_id: str  # Associated market
    outcome: OutcomeType  # YES or NO position
    shares: Decimal  # Number of shares held
    average_price: Decimal  # Average entry price (0-1)
    current_price: Decimal  # Current market price
    unrealized_pnl: Decimal  # Based on current market price
    realized_pnl: Decimal = Decimal("0")  # From closed positions
    timestamp: float = 0  # Position open time
