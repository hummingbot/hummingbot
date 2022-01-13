#!/usr/bin/env python
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Dict, List, NamedTuple, Optional

from hummingbot.core.data_type.order_book_row import OrderBookRow
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase


class MarketEvent(Enum):
    ReceivedAsset = 101
    BuyOrderCompleted = 102
    SellOrderCompleted = 103
    # Trade = 104  Deprecated
    WithdrawAsset = 105  # Locally Deprecated, but still present in hummingsim
    OrderCancelled = 106
    OrderFilled = 107
    OrderExpired = 108
    OrderFailure = 198
    TransactionFailure = 199
    BuyOrderCreated = 200
    SellOrderCreated = 201
    FundingPaymentCompleted = 202
    RangePositionInitiated = 300
    RangePositionCreated = 301
    RangePositionRemoved = 302
    RangePositionUpdated = 303
    RangePositionFailure = 304


class OrderBookEvent(Enum):
    TradeEvent = 901


class TradeType(Enum):
    BUY = 1
    SELL = 2
    RANGE = 3


class OrderType(Enum):
    MARKET = 1
    LIMIT = 2
    LIMIT_MAKER = 3

    def is_limit_type(self):
        return self in (OrderType.LIMIT, OrderType.LIMIT_MAKER)


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
    HEDGE = True
    ONEWAY = False


class FundingInfo(NamedTuple):
    trading_pair: str
    index_price: Decimal
    mark_price: Decimal
    next_funding_utc_timestamp: int
    rate: Decimal


class PriceType(Enum):
    MidPrice = 1
    BestBid = 2
    BestAsk = 3
    LastTrade = 4
    LastOwnTrade = 5
    InventoryCost = 6
    Custom = 7


class MarketTransactionFailureEvent(NamedTuple):
    timestamp: float
    order_id: str


class MarketOrderFailureEvent(NamedTuple):
    timestamp: float
    order_id: str
    order_type: OrderType


@dataclass
class BuyOrderCompletedEvent:
    timestamp: float
    order_id: str
    base_asset: str
    quote_asset: str
    fee_asset: str
    base_asset_amount: Decimal
    quote_asset_amount: Decimal
    fee_amount: Decimal
    order_type: OrderType
    exchange_order_id: Optional[str] = None


@dataclass
class SellOrderCompletedEvent:
    timestamp: float
    order_id: str
    base_asset: str
    quote_asset: str
    fee_asset: str
    base_asset_amount: Decimal
    quote_asset_amount: Decimal
    fee_amount: Decimal
    order_type: OrderType
    exchange_order_id: Optional[str] = None


@dataclass
class OrderCancelledEvent:
    timestamp: float
    order_id: str
    exchange_order_id: Optional[str] = None


class OrderExpiredEvent(NamedTuple):
    timestamp: float
    order_id: str


@dataclass
class FundingPaymentCompletedEvent:
    timestamp: float
    market: str
    trading_pair: str
    amount: Decimal
    funding_rate: Decimal


class OrderBookTradeEvent(NamedTuple):
    trading_pair: str
    timestamp: float
    type: TradeType
    price: Decimal
    amount: Decimal


class OrderFilledEvent(NamedTuple):
    timestamp: float
    order_id: str
    trading_pair: str
    trade_type: TradeType
    order_type: OrderType
    price: Decimal
    amount: Decimal
    trade_fee: TradeFeeBase
    exchange_trade_id: str = ""
    leverage: Optional[int] = 1
    position: Optional[str] = "NIL"

    @classmethod
    def order_filled_events_from_order_book_rows(cls,
                                                 timestamp: float,
                                                 order_id: str,
                                                 trading_pair: str,
                                                 trade_type: TradeType,
                                                 order_type: OrderType,
                                                 trade_fee: TradeFeeBase,
                                                 order_book_rows: List[OrderBookRow],
                                                 exchange_trade_id: str = "") -> List["OrderFilledEvent"]:
        return [
            OrderFilledEvent(timestamp, order_id, trading_pair, trade_type, order_type,
                             Decimal(r.price), Decimal(r.amount), trade_fee, exchange_trade_id=exchange_trade_id)
            for r in order_book_rows
        ]

    @classmethod
    def order_filled_event_from_binance_execution_report(cls, execution_report: Dict[str, any]) -> "OrderFilledEvent":
        execution_type: str = execution_report.get("x")
        if execution_type != "TRADE":
            raise ValueError(f"Invalid execution type '{execution_type}'.")
        return OrderFilledEvent(
            execution_report["E"] * 1e-3,
            execution_report["c"],
            execution_report["s"],
            TradeType.BUY if execution_report["S"] == "BUY" else TradeType.SELL,
            OrderType[execution_report["o"]],
            Decimal(execution_report["L"]),
            Decimal(execution_report["l"]),
            AddedToCostTradeFee(flat_fees=[TokenAmount(execution_report["N"], Decimal(execution_report["n"]))]),
            exchange_trade_id=execution_report["t"]
        )


@dataclass
class BuyOrderCreatedEvent:
    timestamp: float
    type: OrderType
    trading_pair: str
    amount: Decimal
    price: Decimal
    order_id: str
    exchange_order_id: Optional[str] = None
    leverage: Optional[int] = 1
    position: Optional[str] = "NILL"


@dataclass
class SellOrderCreatedEvent:
    timestamp: float
    type: OrderType
    trading_pair: str
    amount: Decimal
    price: Decimal
    order_id: str
    exchange_order_id: Optional[str] = None
    leverage: Optional[int] = 1
    position: Optional[str] = "NILL"


@dataclass
class RangePositionInitiatedEvent:
    timestamp: float
    hb_id: str
    tx_hash: str
    trading_pair: str
    fee_tier: str
    lower_price: Decimal
    upper_price: Decimal
    base_amount: Decimal
    quote_amount: Decimal
    status: str
    gas_price: Decimal


@dataclass
class RangePositionCreatedEvent:
    timestamp: float
    hb_id: str
    tx_hash: str
    token_id: str
    trading_pair: str
    fee_tier: str
    lower_price: Decimal
    upper_price: Decimal
    base_amount: Decimal
    quote_amount: Decimal
    status: str
    gas_price: Decimal


@dataclass
class RangePositionUpdatedEvent:
    timestamp: float
    hb_id: str
    tx_hash: str
    token_id: str
    base_amount: Decimal
    quote_amount: Decimal
    status: str


@dataclass
class RangePositionRemovedEvent:
    timestamp: float
    hb_id: str
    token_id: Optional[str] = None


@dataclass
class RangePositionFailureEvent:
    timestamp: float
    hb_id: str


class LimitOrderStatus(Enum):
    UNKNOWN = 0
    NEW = 1
    OPEN = 2
    CANCELING = 3
    CANCELED = 4
    COMPLETED = 5
    FAILED = 6
