#!/usr/bin/env python
from decimal import Decimal
from enum import Enum
from typing import (
    Tuple,
    List,
    Dict,
    NamedTuple,
    Optional)
from dataclasses import dataclass
from hummingbot.core.data_type.order_book_row import OrderBookRow


class WalletEvent(Enum):
    ReceivedAsset = 5
    BalanceChanged = 6
    WrappedEth = 7
    UnwrappedEth = 8
    GasUsed = 9
    TokenApproved = 10
    TransactionFailure = 99


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


class NewBlocksWatcherEvent(Enum):
    NewBlocks = 401


class IncomingEthWatcherEvent(Enum):
    ReceivedEther = 501


class ERC20WatcherEvent(Enum):
    ReceivedToken = 601
    ApprovedToken = 602


class OrderBookEvent(Enum):
    TradeEvent = 901


class ZeroExEvent(Enum):
    Fill = 1001


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


class MarketTransactionFailureEvent(NamedTuple):
    timestamp: float
    order_id: str


class MarketOrderFailureEvent(NamedTuple):
    timestamp: float
    order_id: str
    order_type: OrderType


class WalletReceivedAssetEvent(NamedTuple):
    timestamp: float
    tx_hash: str
    from_address: str
    to_address: str
    asset_name: str
    amount_received: Decimal
    raw_amount_received: int


class WalletWrappedEthEvent(NamedTuple):
    timestamp: float
    tx_hash: str
    address: str
    amount: Decimal
    raw_amount: int


class WalletUnwrappedEthEvent(NamedTuple):
    timestamp: float
    tx_hash: str
    address: str
    amount: Decimal
    raw_amount: int


class ZeroExFillEvent(NamedTuple):
    timestamp: float
    tx_hash: str
    maker_address: str
    fee_recipient_address: str
    maker_asset_data: bytes
    taker_asset_data: bytes
    maker_fee_asset_data: bytes
    taker_fee_asset_data: bytes
    order_hash: str
    taker_address: str
    sender_address: str
    maker_asset_filled_amount: Decimal
    taker_asset_filled_amount: Decimal
    maker_fee_paid: Decimal
    taker_fee_paid: Decimal
    protocol_fee_paid: Decimal


class MarketReceivedAssetEvent(NamedTuple):
    timestamp: float
    tx_hash: str
    from_address: str
    to_address: str
    asset_name: str
    amount_received: float


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


class MarketWithdrawAssetEvent(NamedTuple):
    timestamp: float
    tracking_id: str
    to_address: str
    asset_name: str
    amount: Decimal
    fee_amount: Decimal


class EthereumGasUsedEvent(NamedTuple):
    timestamp: float
    tx_hash: str
    gas_price_gwei: float
    gas_price_raw: int
    gas_used: int
    eth_amount: float
    eth_amount_raw: int


class TokenApprovedEvent(NamedTuple):
    timestamp: float
    tx_hash: str
    owner_address: str
    spender_address: str
    asset_name: str
    amount: float
    raw_amount: int


class TradeFeeType(Enum):
    Percent = 1
    FlatFee = 2


def interchangeable(token_a: str, token_b: str) -> bool:
    interchangeable_tokens = {"WETH", "ETH", "WBTC", "BTC"}
    if token_a == token_b:
        return True
    return {token_a, token_b} <= interchangeable_tokens


class TradeFee(NamedTuple):
    percent: Decimal  # 0.1 = 10%
    flat_fees: List[Tuple[str, Decimal]] = []  # list of (asset, amount) ie: ("ETH", 0.05)

    @classmethod
    def to_json(cls, trade_fee: "TradeFee") -> Dict[str, any]:
        return {
            "percent": float(trade_fee.percent),
            "flat_fees": [{"asset": asset, "amount": float(amount)}
                          for asset, amount in trade_fee.flat_fees]
        }

    @classmethod
    def from_json(cls, data: Dict[str, any]) -> "TradeFee":
        return TradeFee(
            Decimal(data["percent"]),
            [(fee_entry["asset"], Decimal(fee_entry["amount"]))
             for fee_entry in data["flat_fees"]]
        )

    def fee_amount_in_quote(self, trading_pair: str, price: Decimal, order_amount: Decimal):
        fee_amount = Decimal("0")
        if self.percent > 0:
            fee_amount = (price * order_amount) * self.percent
        base, quote = trading_pair.split("-")
        for flat_fee in self.flat_fees:
            if interchangeable(flat_fee[0], base):
                fee_amount += (flat_fee[1] * price)
            elif interchangeable(flat_fee[0], quote):
                fee_amount += flat_fee[1]
        return fee_amount


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
    trade_fee: TradeFee
    exchange_trade_id: str = ""
    leverage: Optional[int] = 1
    position: Optional[str] = "NILL"

    @classmethod
    def order_filled_events_from_order_book_rows(cls,
                                                 timestamp: float,
                                                 order_id: str,
                                                 trading_pair: str,
                                                 trade_type: TradeType,
                                                 order_type: OrderType,
                                                 trade_fee: TradeFee,
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
            TradeFee(percent=Decimal(0.0), flat_fees=[(execution_report["N"], Decimal(execution_report["n"]))]),
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
