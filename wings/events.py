#!/usr/bin/env python

import time
from collections import (
    namedtuple,
    OrderedDict
)
from enum import Enum
from typing import (
    Tuple,
    List,
    Dict,
    NamedTuple,
)

from .order_book_row import OrderBookRow


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
    WithdrawAsset = 105
    OrderCancelled = 106
    OrderFilled = 107
    OrderExpired = 108
    TransactionFailure = 199
    BuyOrderCreated = 200
    SellOrderCreated = 201


class NewBlocksWatcherEvent(Enum):
    NewBlocks = 401


class IncomingEthWatcherEvent(Enum):
    ReceivedEther = 501


class ERC20WatcherEvent(Enum):
    ReceivedToken = 601
    ApprovedToken = 602


class OrderBookEvent(Enum):
    TradeEvent = 901


class MarketTransactionFailureEvent(NamedTuple):
    timestamp: float
    order_id: str


class WalletReceivedAssetEvent(NamedTuple):
    timestamp: float
    tx_hash: str
    from_address: str
    to_address: str
    asset_name: str
    amount_received: float
    raw_amount_received: int


class WalletWrappedEthEvent(NamedTuple):
    timestamp: float
    tx_hash: str
    address: str
    amount: float
    raw_amount: int


class WalletUnwrappedEthEvent(NamedTuple):
    timestamp: float
    tx_hash: str
    address: str
    amount: float
    raw_amount: int


class MarketReceivedAssetEvent(NamedTuple):
    timestamp: float
    tx_hash: str
    from_address: str
    to_address: str
    asset_name: str
    amount_received: float


class BuyOrderCompletedEvent(NamedTuple):
    timestamp: float
    order_id: str
    base_asset: str
    quote_asset: str
    fee_asset: str
    base_asset_amount: float
    quote_asset_amount: float
    fee_amount: float


class SellOrderCompletedEvent(NamedTuple):
    timestamp: float
    order_id: str
    base_asset: str
    quote_asset: str
    fee_asset: str
    base_asset_amount: float
    quote_asset_amount: float
    fee_amount: float


class OrderCancelledEvent(NamedTuple):
    timestamp: float
    order_id: str


class OrderExpiredEvent(NamedTuple):
    timestamp: float
    order_id: str


class MarketWithdrawAssetEvent(NamedTuple):
    timestamp: float
    tracking_id: str
    to_address: str
    asset_name: str
    amount: float
    fee_amount: float


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


class TradeType(Enum):
    BUY = 1
    SELL = 2


class OrderType(Enum):
    MARKET = 1
    LIMIT = 2


class TradeFee(NamedTuple):
    percent: float # 0.1 = 10%
    flat_fees: List[Tuple[str, float]] = [] # list of (symbol, amount) ie: ("ETH", 0.05) 

class OrderBookTradeEvent(NamedTuple):
    symbol: str
    timestamp: float
    type: TradeType
    price: float
    amount: float


class OrderFilledEvent(NamedTuple):
    timestamp: float
    order_id: str
    symbol: str
    trade_type: TradeType
    order_type: OrderType
    price: float
    amount: float

    @classmethod
    def order_filled_events_from_order_book_rows(cls,
                                                 timestamp: float,
                                                 order_id: str,
                                                 symbol: str,
                                                 trade_type: TradeType,
                                                 order_type: OrderType,
                                                 order_book_rows: List[OrderBookRow]) -> List["OrderFilledEvent"]:
        return [
            OrderFilledEvent(timestamp, order_id, symbol, trade_type, order_type, r.price, r.amount)
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
            OrderType.LIMIT if execution_report["o"] == "LIMIT" else OrderType.MARKET,
            float(execution_report["L"]),
            float(execution_report["l"])
        )


class BuyOrderCreatedEvent(NamedTuple):
    timestamp: float
    type: OrderType
    symbol: str
    amount: float
    price: float
    order_id: str


class SellOrderCreatedEvent(NamedTuple):
    timestamp: float
    type: OrderType
    symbol: str
    amount: float
    price: float
    order_id: str
