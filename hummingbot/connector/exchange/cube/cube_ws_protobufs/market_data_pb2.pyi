from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Side(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    BID: _ClassVar[Side]
    ASK: _ClassVar[Side]

class KlineInterval(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    S1: _ClassVar[KlineInterval]
    M1: _ClassVar[KlineInterval]
    M15: _ClassVar[KlineInterval]
    H1: _ClassVar[KlineInterval]
    H4: _ClassVar[KlineInterval]
    D1: _ClassVar[KlineInterval]

class RateUpdateSide(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    BASE: _ClassVar[RateUpdateSide]
    QUOTE: _ClassVar[RateUpdateSide]
BID: Side
ASK: Side
S1: KlineInterval
M1: KlineInterval
M15: KlineInterval
H1: KlineInterval
H4: KlineInterval
D1: KlineInterval
BASE: RateUpdateSide
QUOTE: RateUpdateSide

class MdMessage(_message.Message):
    __slots__ = ("heartbeat", "summary", "trades", "mbo_snapshot", "mbo_diff", "mbp_snapshot", "mbp_diff", "kline")
    HEARTBEAT_FIELD_NUMBER: _ClassVar[int]
    SUMMARY_FIELD_NUMBER: _ClassVar[int]
    TRADES_FIELD_NUMBER: _ClassVar[int]
    MBO_SNAPSHOT_FIELD_NUMBER: _ClassVar[int]
    MBO_DIFF_FIELD_NUMBER: _ClassVar[int]
    MBP_SNAPSHOT_FIELD_NUMBER: _ClassVar[int]
    MBP_DIFF_FIELD_NUMBER: _ClassVar[int]
    KLINE_FIELD_NUMBER: _ClassVar[int]
    heartbeat: Heartbeat
    summary: Summary
    trades: Trades
    mbo_snapshot: MarketByOrder
    mbo_diff: MarketByOrderDiff
    mbp_snapshot: MarketByPrice
    mbp_diff: MarketByPriceDiff
    kline: Kline
    def __init__(self, heartbeat: _Optional[_Union[Heartbeat, _Mapping]] = ..., summary: _Optional[_Union[Summary, _Mapping]] = ..., trades: _Optional[_Union[Trades, _Mapping]] = ..., mbo_snapshot: _Optional[_Union[MarketByOrder, _Mapping]] = ..., mbo_diff: _Optional[_Union[MarketByOrderDiff, _Mapping]] = ..., mbp_snapshot: _Optional[_Union[MarketByPrice, _Mapping]] = ..., mbp_diff: _Optional[_Union[MarketByPriceDiff, _Mapping]] = ..., kline: _Optional[_Union[Kline, _Mapping]] = ...) -> None: ...

class MarketByPrice(_message.Message):
    __slots__ = ("levels", "chunk", "num_chunks")
    class Level(_message.Message):
        __slots__ = ("price", "quantity", "side")
        PRICE_FIELD_NUMBER: _ClassVar[int]
        QUANTITY_FIELD_NUMBER: _ClassVar[int]
        SIDE_FIELD_NUMBER: _ClassVar[int]
        price: int
        quantity: int
        side: Side
        def __init__(self, price: _Optional[int] = ..., quantity: _Optional[int] = ..., side: _Optional[_Union[Side, str]] = ...) -> None: ...
    LEVELS_FIELD_NUMBER: _ClassVar[int]
    CHUNK_FIELD_NUMBER: _ClassVar[int]
    NUM_CHUNKS_FIELD_NUMBER: _ClassVar[int]
    levels: _containers.RepeatedCompositeFieldContainer[MarketByPrice.Level]
    chunk: int
    num_chunks: int
    def __init__(self, levels: _Optional[_Iterable[_Union[MarketByPrice.Level, _Mapping]]] = ..., chunk: _Optional[int] = ..., num_chunks: _Optional[int] = ...) -> None: ...

class MarketByPriceDiff(_message.Message):
    __slots__ = ("diffs", "total_bid_levels", "total_ask_levels")
    class DiffOp(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        ADD: _ClassVar[MarketByPriceDiff.DiffOp]
        REMOVE: _ClassVar[MarketByPriceDiff.DiffOp]
        REPLACE: _ClassVar[MarketByPriceDiff.DiffOp]
    ADD: MarketByPriceDiff.DiffOp
    REMOVE: MarketByPriceDiff.DiffOp
    REPLACE: MarketByPriceDiff.DiffOp
    class Diff(_message.Message):
        __slots__ = ("price", "quantity", "side", "op")
        PRICE_FIELD_NUMBER: _ClassVar[int]
        QUANTITY_FIELD_NUMBER: _ClassVar[int]
        SIDE_FIELD_NUMBER: _ClassVar[int]
        OP_FIELD_NUMBER: _ClassVar[int]
        price: int
        quantity: int
        side: Side
        op: MarketByPriceDiff.DiffOp
        def __init__(self, price: _Optional[int] = ..., quantity: _Optional[int] = ..., side: _Optional[_Union[Side, str]] = ..., op: _Optional[_Union[MarketByPriceDiff.DiffOp, str]] = ...) -> None: ...
    DIFFS_FIELD_NUMBER: _ClassVar[int]
    TOTAL_BID_LEVELS_FIELD_NUMBER: _ClassVar[int]
    TOTAL_ASK_LEVELS_FIELD_NUMBER: _ClassVar[int]
    diffs: _containers.RepeatedCompositeFieldContainer[MarketByPriceDiff.Diff]
    total_bid_levels: int
    total_ask_levels: int
    def __init__(self, diffs: _Optional[_Iterable[_Union[MarketByPriceDiff.Diff, _Mapping]]] = ..., total_bid_levels: _Optional[int] = ..., total_ask_levels: _Optional[int] = ...) -> None: ...

class MarketByOrder(_message.Message):
    __slots__ = ("orders", "chunk", "num_chunks")
    class Order(_message.Message):
        __slots__ = ("price", "quantity", "exchange_order_id", "side", "priority")
        PRICE_FIELD_NUMBER: _ClassVar[int]
        QUANTITY_FIELD_NUMBER: _ClassVar[int]
        EXCHANGE_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
        SIDE_FIELD_NUMBER: _ClassVar[int]
        PRIORITY_FIELD_NUMBER: _ClassVar[int]
        price: int
        quantity: int
        exchange_order_id: int
        side: Side
        priority: int
        def __init__(self, price: _Optional[int] = ..., quantity: _Optional[int] = ..., exchange_order_id: _Optional[int] = ..., side: _Optional[_Union[Side, str]] = ..., priority: _Optional[int] = ...) -> None: ...
    ORDERS_FIELD_NUMBER: _ClassVar[int]
    CHUNK_FIELD_NUMBER: _ClassVar[int]
    NUM_CHUNKS_FIELD_NUMBER: _ClassVar[int]
    orders: _containers.RepeatedCompositeFieldContainer[MarketByOrder.Order]
    chunk: int
    num_chunks: int
    def __init__(self, orders: _Optional[_Iterable[_Union[MarketByOrder.Order, _Mapping]]] = ..., chunk: _Optional[int] = ..., num_chunks: _Optional[int] = ...) -> None: ...

class MarketByOrderDiff(_message.Message):
    __slots__ = ("diffs", "total_bid_levels", "total_ask_levels", "total_bid_orders", "total_ask_orders")
    class DiffOp(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        ADD: _ClassVar[MarketByOrderDiff.DiffOp]
        REMOVE: _ClassVar[MarketByOrderDiff.DiffOp]
        REPLACE: _ClassVar[MarketByOrderDiff.DiffOp]
    ADD: MarketByOrderDiff.DiffOp
    REMOVE: MarketByOrderDiff.DiffOp
    REPLACE: MarketByOrderDiff.DiffOp
    class Diff(_message.Message):
        __slots__ = ("price", "quantity", "exchange_order_id", "side", "op", "priority")
        PRICE_FIELD_NUMBER: _ClassVar[int]
        QUANTITY_FIELD_NUMBER: _ClassVar[int]
        EXCHANGE_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
        SIDE_FIELD_NUMBER: _ClassVar[int]
        OP_FIELD_NUMBER: _ClassVar[int]
        PRIORITY_FIELD_NUMBER: _ClassVar[int]
        price: int
        quantity: int
        exchange_order_id: int
        side: Side
        op: MarketByOrderDiff.DiffOp
        priority: int
        def __init__(self, price: _Optional[int] = ..., quantity: _Optional[int] = ..., exchange_order_id: _Optional[int] = ..., side: _Optional[_Union[Side, str]] = ..., op: _Optional[_Union[MarketByOrderDiff.DiffOp, str]] = ..., priority: _Optional[int] = ...) -> None: ...
    DIFFS_FIELD_NUMBER: _ClassVar[int]
    TOTAL_BID_LEVELS_FIELD_NUMBER: _ClassVar[int]
    TOTAL_ASK_LEVELS_FIELD_NUMBER: _ClassVar[int]
    TOTAL_BID_ORDERS_FIELD_NUMBER: _ClassVar[int]
    TOTAL_ASK_ORDERS_FIELD_NUMBER: _ClassVar[int]
    diffs: _containers.RepeatedCompositeFieldContainer[MarketByOrderDiff.Diff]
    total_bid_levels: int
    total_ask_levels: int
    total_bid_orders: int
    total_ask_orders: int
    def __init__(self, diffs: _Optional[_Iterable[_Union[MarketByOrderDiff.Diff, _Mapping]]] = ..., total_bid_levels: _Optional[int] = ..., total_ask_levels: _Optional[int] = ..., total_bid_orders: _Optional[int] = ..., total_ask_orders: _Optional[int] = ...) -> None: ...

class Trades(_message.Message):
    __slots__ = ("trades",)
    class Trade(_message.Message):
        __slots__ = ("tradeId", "price", "aggressing_side", "resting_exchange_order_id", "fill_quantity", "transact_time", "aggressing_exchange_order_id")
        TRADEID_FIELD_NUMBER: _ClassVar[int]
        PRICE_FIELD_NUMBER: _ClassVar[int]
        AGGRESSING_SIDE_FIELD_NUMBER: _ClassVar[int]
        RESTING_EXCHANGE_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
        FILL_QUANTITY_FIELD_NUMBER: _ClassVar[int]
        TRANSACT_TIME_FIELD_NUMBER: _ClassVar[int]
        AGGRESSING_EXCHANGE_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
        tradeId: int
        price: int
        aggressing_side: Side
        resting_exchange_order_id: int
        fill_quantity: int
        transact_time: int
        aggressing_exchange_order_id: int
        def __init__(self, tradeId: _Optional[int] = ..., price: _Optional[int] = ..., aggressing_side: _Optional[_Union[Side, str]] = ..., resting_exchange_order_id: _Optional[int] = ..., fill_quantity: _Optional[int] = ..., transact_time: _Optional[int] = ..., aggressing_exchange_order_id: _Optional[int] = ...) -> None: ...
    TRADES_FIELD_NUMBER: _ClassVar[int]
    trades: _containers.RepeatedCompositeFieldContainer[Trades.Trade]
    def __init__(self, trades: _Optional[_Iterable[_Union[Trades.Trade, _Mapping]]] = ...) -> None: ...

class Summary(_message.Message):
    __slots__ = ("open", "close", "low", "high", "base_volume_lo", "base_volume_hi", "quote_volume_lo", "quote_volume_hi")
    OPEN_FIELD_NUMBER: _ClassVar[int]
    CLOSE_FIELD_NUMBER: _ClassVar[int]
    LOW_FIELD_NUMBER: _ClassVar[int]
    HIGH_FIELD_NUMBER: _ClassVar[int]
    BASE_VOLUME_LO_FIELD_NUMBER: _ClassVar[int]
    BASE_VOLUME_HI_FIELD_NUMBER: _ClassVar[int]
    QUOTE_VOLUME_LO_FIELD_NUMBER: _ClassVar[int]
    QUOTE_VOLUME_HI_FIELD_NUMBER: _ClassVar[int]
    open: int
    close: int
    low: int
    high: int
    base_volume_lo: int
    base_volume_hi: int
    quote_volume_lo: int
    quote_volume_hi: int
    def __init__(self, open: _Optional[int] = ..., close: _Optional[int] = ..., low: _Optional[int] = ..., high: _Optional[int] = ..., base_volume_lo: _Optional[int] = ..., base_volume_hi: _Optional[int] = ..., quote_volume_lo: _Optional[int] = ..., quote_volume_hi: _Optional[int] = ...) -> None: ...

class Kline(_message.Message):
    __slots__ = ("interval", "start_time", "open", "close", "high", "low", "volume_lo", "volume_hi")
    INTERVAL_FIELD_NUMBER: _ClassVar[int]
    START_TIME_FIELD_NUMBER: _ClassVar[int]
    OPEN_FIELD_NUMBER: _ClassVar[int]
    CLOSE_FIELD_NUMBER: _ClassVar[int]
    HIGH_FIELD_NUMBER: _ClassVar[int]
    LOW_FIELD_NUMBER: _ClassVar[int]
    VOLUME_LO_FIELD_NUMBER: _ClassVar[int]
    VOLUME_HI_FIELD_NUMBER: _ClassVar[int]
    interval: KlineInterval
    start_time: int
    open: int
    close: int
    high: int
    low: int
    volume_lo: int
    volume_hi: int
    def __init__(self, interval: _Optional[_Union[KlineInterval, str]] = ..., start_time: _Optional[int] = ..., open: _Optional[int] = ..., close: _Optional[int] = ..., high: _Optional[int] = ..., low: _Optional[int] = ..., volume_lo: _Optional[int] = ..., volume_hi: _Optional[int] = ...) -> None: ...

class Heartbeat(_message.Message):
    __slots__ = ("request_id", "timestamp")
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    request_id: int
    timestamp: int
    def __init__(self, request_id: _Optional[int] = ..., timestamp: _Optional[int] = ...) -> None: ...

class MdMessages(_message.Message):
    __slots__ = ("messages",)
    MESSAGES_FIELD_NUMBER: _ClassVar[int]
    messages: _containers.RepeatedCompositeFieldContainer[MdMessage]
    def __init__(self, messages: _Optional[_Iterable[_Union[MdMessage, _Mapping]]] = ...) -> None: ...

class AggMessage(_message.Message):
    __slots__ = ("heartbeat", "top_of_books", "rate_updates")
    HEARTBEAT_FIELD_NUMBER: _ClassVar[int]
    TOP_OF_BOOKS_FIELD_NUMBER: _ClassVar[int]
    RATE_UPDATES_FIELD_NUMBER: _ClassVar[int]
    heartbeat: Heartbeat
    top_of_books: TopOfBooks
    rate_updates: RateUpdates
    def __init__(self, heartbeat: _Optional[_Union[Heartbeat, _Mapping]] = ..., top_of_books: _Optional[_Union[TopOfBooks, _Mapping]] = ..., rate_updates: _Optional[_Union[RateUpdates, _Mapping]] = ...) -> None: ...

class TopOfBook(_message.Message):
    __slots__ = ("market_id", "transact_time", "bid_price", "bid_quantity", "ask_price", "ask_quantity", "last_price", "rolling24h_price")
    MARKET_ID_FIELD_NUMBER: _ClassVar[int]
    TRANSACT_TIME_FIELD_NUMBER: _ClassVar[int]
    BID_PRICE_FIELD_NUMBER: _ClassVar[int]
    BID_QUANTITY_FIELD_NUMBER: _ClassVar[int]
    ASK_PRICE_FIELD_NUMBER: _ClassVar[int]
    ASK_QUANTITY_FIELD_NUMBER: _ClassVar[int]
    LAST_PRICE_FIELD_NUMBER: _ClassVar[int]
    ROLLING24H_PRICE_FIELD_NUMBER: _ClassVar[int]
    market_id: int
    transact_time: int
    bid_price: int
    bid_quantity: int
    ask_price: int
    ask_quantity: int
    last_price: int
    rolling24h_price: int
    def __init__(self, market_id: _Optional[int] = ..., transact_time: _Optional[int] = ..., bid_price: _Optional[int] = ..., bid_quantity: _Optional[int] = ..., ask_price: _Optional[int] = ..., ask_quantity: _Optional[int] = ..., last_price: _Optional[int] = ..., rolling24h_price: _Optional[int] = ...) -> None: ...

class TopOfBooks(_message.Message):
    __slots__ = ("tops",)
    TOPS_FIELD_NUMBER: _ClassVar[int]
    tops: _containers.RepeatedCompositeFieldContainer[TopOfBook]
    def __init__(self, tops: _Optional[_Iterable[_Union[TopOfBook, _Mapping]]] = ...) -> None: ...

class RateUpdate(_message.Message):
    __slots__ = ("asset_id", "timestamp", "rate", "side")
    ASSET_ID_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    RATE_FIELD_NUMBER: _ClassVar[int]
    SIDE_FIELD_NUMBER: _ClassVar[int]
    asset_id: int
    timestamp: int
    rate: int
    side: RateUpdateSide
    def __init__(self, asset_id: _Optional[int] = ..., timestamp: _Optional[int] = ..., rate: _Optional[int] = ..., side: _Optional[_Union[RateUpdateSide, str]] = ...) -> None: ...

class RateUpdates(_message.Message):
    __slots__ = ("updates",)
    UPDATES_FIELD_NUMBER: _ClassVar[int]
    updates: _containers.RepeatedCompositeFieldContainer[RateUpdate]
    def __init__(self, updates: _Optional[_Iterable[_Union[RateUpdate, _Mapping]]] = ...) -> None: ...

class ClientMessage(_message.Message):
    __slots__ = ("heartbeat", "config")
    HEARTBEAT_FIELD_NUMBER: _ClassVar[int]
    CONFIG_FIELD_NUMBER: _ClassVar[int]
    heartbeat: Heartbeat
    config: Config
    def __init__(self, heartbeat: _Optional[_Union[Heartbeat, _Mapping]] = ..., config: _Optional[_Union[Config, _Mapping]] = ...) -> None: ...

class Config(_message.Message):
    __slots__ = ("mbp", "mbo", "trades", "summary", "klines")
    MBP_FIELD_NUMBER: _ClassVar[int]
    MBO_FIELD_NUMBER: _ClassVar[int]
    TRADES_FIELD_NUMBER: _ClassVar[int]
    SUMMARY_FIELD_NUMBER: _ClassVar[int]
    KLINES_FIELD_NUMBER: _ClassVar[int]
    mbp: bool
    mbo: bool
    trades: bool
    summary: bool
    klines: _containers.RepeatedScalarFieldContainer[KlineInterval]
    def __init__(self, mbp: bool = ..., mbo: bool = ..., trades: bool = ..., summary: bool = ..., klines: _Optional[_Iterable[_Union[KlineInterval, str]]] = ...) -> None: ...
