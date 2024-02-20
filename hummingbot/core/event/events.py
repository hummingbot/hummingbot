from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Dict, List, NamedTuple, Optional

from hummingbot.core.data_type.common import LPType, OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.order_book_row import OrderBookRow
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount, TradeFeeBase

s_decimal_0 = Decimal("0")


class MarketEvent(Enum):
    ReceivedAsset = 101
    BuyOrderCompleted = 102
    SellOrderCompleted = 103
    # Trade = 104  Deprecated
    WithdrawAsset = 105  # Locally Deprecated, but still present in hummingsim
    OrderCancelled = 106
    OrderFilled = 107
    OrderExpired = 108
    OrderUpdate = 109
    TradeUpdate = 110
    OrderFailure = 198
    TransactionFailure = 199
    BuyOrderCreated = 200
    SellOrderCreated = 201
    FundingPaymentCompleted = 202
    FundingInfo = 203
    RangePositionLiquidityAdded = 300
    RangePositionLiquidityRemoved = 301
    RangePositionUpdate = 302
    RangePositionUpdateFailure = 303
    RangePositionFeeCollected = 304
    RangePositionClosed = 305


class OrderBookEvent(int, Enum):
    TradeEvent = 901
    OrderBookDataSourceUpdateEvent = 904


class OrderBookDataSourceEvent(int, Enum):
    SNAPSHOT_EVENT = 1001
    DIFF_EVENT = 1002
    TRADE_EVENT = 1003


class TokenApprovalEvent(Enum):
    ApprovalSuccessful = 1101
    ApprovalFailed = 1102
    ApprovalCancelled = 1103


class HummingbotUIEvent(Enum):
    Start = 1


class AccountEvent(Enum):
    PositionModeChangeSucceeded = 400
    PositionModeChangeFailed = 401
    BalanceEvent = 402
    PositionUpdate = 403
    MarginCall = 404
    LiquidationEvent = 405


class ExecutorEvent(Enum):
    EXECUTOR_INFO_UPDATE = 500


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
    base_asset_amount: Decimal
    quote_asset_amount: Decimal
    order_type: OrderType
    exchange_order_id: Optional[str] = None


@dataclass
class SellOrderCompletedEvent:
    timestamp: float
    order_id: str
    base_asset: str
    quote_asset: str
    base_asset_amount: Decimal
    quote_asset_amount: Decimal
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
class TokenApprovalSuccessEvent:
    timestamp: float
    connector: str
    token_symbol: str


@dataclass
class TokenApprovalFailureEvent:
    timestamp: float
    connector: str
    token_symbol: str


@dataclass
class TokenApprovalCancelledEvent:
    timestamp: float
    connector: str
    token_symbol: str


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
    trade_id: Optional[str] = None
    is_taker: bool = True  # CEXs deliver trade events from the taker's perspective


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
    exchange_order_id: str = ""
    leverage: Optional[int] = 1
    position: Optional[str] = PositionAction.NIL.value

    @classmethod
    def order_filled_events_from_order_book_rows(
        cls,
        timestamp: float,
        order_id: str,
        trading_pair: str,
        trade_type: TradeType,
        order_type: OrderType,
        trade_fee: TradeFeeBase,
        order_book_rows: List[OrderBookRow],
        exchange_trade_id: Optional[str] = None,
    ) -> List["OrderFilledEvent"]:
        if exchange_trade_id is None:
            exchange_trade_id = order_id
        return [
            OrderFilledEvent(
                timestamp,
                order_id,
                trading_pair,
                trade_type,
                order_type,
                Decimal(row.price),
                Decimal(row.amount),
                trade_fee,
                exchange_trade_id=f"{exchange_trade_id}_{index}",
            )
            for index, row in enumerate(order_book_rows)
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
            exchange_trade_id=execution_report["t"],
        )


@dataclass
class BuyOrderCreatedEvent:
    timestamp: float
    type: OrderType
    trading_pair: str
    amount: Decimal
    price: Decimal
    order_id: str
    creation_timestamp: float
    exchange_order_id: Optional[str] = None
    leverage: Optional[int] = 1
    position: Optional[str] = PositionAction.NIL.value


@dataclass
class SellOrderCreatedEvent:
    timestamp: float
    type: OrderType
    trading_pair: str
    amount: Decimal
    price: Decimal
    order_id: str
    creation_timestamp: float
    exchange_order_id: Optional[str] = None
    leverage: Optional[int] = 1
    position: Optional[str] = PositionAction.NIL.value


@dataclass
class RangePositionLiquidityAddedEvent:
    timestamp: float
    order_id: str
    exchange_order_id: str
    trading_pair: str
    lower_price: Decimal
    upper_price: Decimal
    amount: Decimal
    fee_tier: str
    creation_timestamp: float
    trade_fee: TradeFeeBase
    token_id: Optional[int] = 0


@dataclass
class RangePositionLiquidityRemovedEvent:
    timestamp: float
    order_id: str
    exchange_order_id: str
    trading_pair: str
    token_id: str
    trade_fee: TradeFeeBase
    creation_timestamp: float


@dataclass
class RangePositionUpdateEvent:
    timestamp: float
    order_id: str
    exchange_order_id: str
    order_action: LPType
    trading_pair: Optional[str] = ""
    fee_tier: Optional[str] = ""
    lower_price: Optional[Decimal] = s_decimal_0
    upper_price: Optional[Decimal] = s_decimal_0
    amount: Optional[Decimal] = s_decimal_0
    creation_timestamp: float = 0
    token_id: Optional[int] = 0


@dataclass
class RangePositionUpdateFailureEvent:
    timestamp: float
    order_id: str
    order_action: LPType


@dataclass
class RangePositionClosedEvent:
    timestamp: float
    token_id: int
    token_0: str
    token_1: str
    claimed_fee_0: Decimal = s_decimal_0
    claimed_fee_1: Decimal = s_decimal_0


@dataclass
class RangePositionFeeCollectedEvent:
    timestamp: float
    order_id: str
    exchange_order_id: str
    trading_pair: str
    trade_fee: TradeFeeBase
    creation_timestamp: float
    token_id: int = None


class LimitOrderStatus(Enum):
    UNKNOWN = 0
    NEW = 1
    OPEN = 2
    CANCELING = 3
    CANCELED = 4
    COMPLETED = 5
    FAILED = 6


@dataclass
class PositionModeChangeEvent:
    timestamp: float
    trading_pair: str
    position_mode: PositionMode
    message: Optional[str] = None


@dataclass
class BalanceUpdateEvent:
    timestamp: float
    asset_name: str
    total_balance: Optional[Decimal] = None
    available_balance: Optional[Decimal] = None


@dataclass
class PositionUpdateEvent:
    timestamp: float
    trading_pair: str
    position_side: Optional[PositionSide]  # None if the event is for a closed position
    unrealized_pnl: Decimal
    entry_price: Decimal
    amount: Decimal
    leverage: Decimal
