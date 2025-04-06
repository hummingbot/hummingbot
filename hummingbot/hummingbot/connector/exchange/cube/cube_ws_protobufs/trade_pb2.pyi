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

class TimeInForce(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    IMMEDIATE_OR_CANCEL: _ClassVar[TimeInForce]
    GOOD_FOR_SESSION: _ClassVar[TimeInForce]
    FILL_OR_KILL: _ClassVar[TimeInForce]

class OrderType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    LIMIT: _ClassVar[OrderType]
    MARKET_LIMIT: _ClassVar[OrderType]
    MARKET_WITH_PROTECTION: _ClassVar[OrderType]

class SelfTradePrevention(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    CANCEL_RESTING: _ClassVar[SelfTradePrevention]
    CANCEL_AGGRESSING: _ClassVar[SelfTradePrevention]
    ALLOW_SELF_TRADE: _ClassVar[SelfTradePrevention]

class PostOnly(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    DISABLED: _ClassVar[PostOnly]
    ENABLED: _ClassVar[PostOnly]
BID: Side
ASK: Side
IMMEDIATE_OR_CANCEL: TimeInForce
GOOD_FOR_SESSION: TimeInForce
FILL_OR_KILL: TimeInForce
LIMIT: OrderType
MARKET_LIMIT: OrderType
MARKET_WITH_PROTECTION: OrderType
CANCEL_RESTING: SelfTradePrevention
CANCEL_AGGRESSING: SelfTradePrevention
ALLOW_SELF_TRADE: SelfTradePrevention
DISABLED: PostOnly
ENABLED: PostOnly

class Credentials(_message.Message):
    __slots__ = ("access_key_id", "signature", "timestamp")
    ACCESS_KEY_ID_FIELD_NUMBER: _ClassVar[int]
    SIGNATURE_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    access_key_id: str
    signature: str
    timestamp: int
    def __init__(self, access_key_id: _Optional[str] = ..., signature: _Optional[str] = ..., timestamp: _Optional[int] = ...) -> None: ...

class OrderRequest(_message.Message):
    __slots__ = ("new", "cancel", "modify", "heartbeat", "mc")
    NEW_FIELD_NUMBER: _ClassVar[int]
    CANCEL_FIELD_NUMBER: _ClassVar[int]
    MODIFY_FIELD_NUMBER: _ClassVar[int]
    HEARTBEAT_FIELD_NUMBER: _ClassVar[int]
    MC_FIELD_NUMBER: _ClassVar[int]
    new: NewOrder
    cancel: CancelOrder
    modify: ModifyOrder
    heartbeat: Heartbeat
    mc: MassCancel
    def __init__(self, new: _Optional[_Union[NewOrder, _Mapping]] = ..., cancel: _Optional[_Union[CancelOrder, _Mapping]] = ..., modify: _Optional[_Union[ModifyOrder, _Mapping]] = ..., heartbeat: _Optional[_Union[Heartbeat, _Mapping]] = ..., mc: _Optional[_Union[MassCancel, _Mapping]] = ...) -> None: ...

class NewOrder(_message.Message):
    __slots__ = ("client_order_id", "request_id", "market_id", "price", "quantity", "side", "time_in_force", "order_type", "subaccount_id", "self_trade_prevention", "post_only", "cancel_on_disconnect")
    CLIENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    MARKET_ID_FIELD_NUMBER: _ClassVar[int]
    PRICE_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    SIDE_FIELD_NUMBER: _ClassVar[int]
    TIME_IN_FORCE_FIELD_NUMBER: _ClassVar[int]
    ORDER_TYPE_FIELD_NUMBER: _ClassVar[int]
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    SELF_TRADE_PREVENTION_FIELD_NUMBER: _ClassVar[int]
    POST_ONLY_FIELD_NUMBER: _ClassVar[int]
    CANCEL_ON_DISCONNECT_FIELD_NUMBER: _ClassVar[int]
    client_order_id: int
    request_id: int
    market_id: int
    price: int
    quantity: int
    side: Side
    time_in_force: TimeInForce
    order_type: OrderType
    subaccount_id: int
    self_trade_prevention: SelfTradePrevention
    post_only: PostOnly
    cancel_on_disconnect: bool
    def __init__(self, client_order_id: _Optional[int] = ..., request_id: _Optional[int] = ..., market_id: _Optional[int] = ..., price: _Optional[int] = ..., quantity: _Optional[int] = ..., side: _Optional[_Union[Side, str]] = ..., time_in_force: _Optional[_Union[TimeInForce, str]] = ..., order_type: _Optional[_Union[OrderType, str]] = ..., subaccount_id: _Optional[int] = ..., self_trade_prevention: _Optional[_Union[SelfTradePrevention, str]] = ..., post_only: _Optional[_Union[PostOnly, str]] = ..., cancel_on_disconnect: bool = ...) -> None: ...

class CancelOrder(_message.Message):
    __slots__ = ("market_id", "client_order_id", "request_id", "subaccount_id")
    MARKET_ID_FIELD_NUMBER: _ClassVar[int]
    CLIENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    market_id: int
    client_order_id: int
    request_id: int
    subaccount_id: int
    def __init__(self, market_id: _Optional[int] = ..., client_order_id: _Optional[int] = ..., request_id: _Optional[int] = ..., subaccount_id: _Optional[int] = ...) -> None: ...

class ModifyOrder(_message.Message):
    __slots__ = ("market_id", "client_order_id", "request_id", "new_price", "new_quantity", "subaccount_id", "self_trade_prevention", "post_only")
    MARKET_ID_FIELD_NUMBER: _ClassVar[int]
    CLIENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    NEW_PRICE_FIELD_NUMBER: _ClassVar[int]
    NEW_QUANTITY_FIELD_NUMBER: _ClassVar[int]
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    SELF_TRADE_PREVENTION_FIELD_NUMBER: _ClassVar[int]
    POST_ONLY_FIELD_NUMBER: _ClassVar[int]
    market_id: int
    client_order_id: int
    request_id: int
    new_price: int
    new_quantity: int
    subaccount_id: int
    self_trade_prevention: SelfTradePrevention
    post_only: PostOnly
    def __init__(self, market_id: _Optional[int] = ..., client_order_id: _Optional[int] = ..., request_id: _Optional[int] = ..., new_price: _Optional[int] = ..., new_quantity: _Optional[int] = ..., subaccount_id: _Optional[int] = ..., self_trade_prevention: _Optional[_Union[SelfTradePrevention, str]] = ..., post_only: _Optional[_Union[PostOnly, str]] = ...) -> None: ...

class MassCancel(_message.Message):
    __slots__ = ("subaccount_id", "request_id", "market_id", "side")
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    MARKET_ID_FIELD_NUMBER: _ClassVar[int]
    SIDE_FIELD_NUMBER: _ClassVar[int]
    subaccount_id: int
    request_id: int
    market_id: int
    side: Side
    def __init__(self, subaccount_id: _Optional[int] = ..., request_id: _Optional[int] = ..., market_id: _Optional[int] = ..., side: _Optional[_Union[Side, str]] = ...) -> None: ...

class Heartbeat(_message.Message):
    __slots__ = ("request_id", "timestamp")
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    request_id: int
    timestamp: int
    def __init__(self, request_id: _Optional[int] = ..., timestamp: _Optional[int] = ...) -> None: ...

class OrderResponse(_message.Message):
    __slots__ = ("new_ack", "cancel_ack", "modify_ack", "new_reject", "cancel_reject", "modify_reject", "fill", "heartbeat", "position", "mass_cancel_ack")
    NEW_ACK_FIELD_NUMBER: _ClassVar[int]
    CANCEL_ACK_FIELD_NUMBER: _ClassVar[int]
    MODIFY_ACK_FIELD_NUMBER: _ClassVar[int]
    NEW_REJECT_FIELD_NUMBER: _ClassVar[int]
    CANCEL_REJECT_FIELD_NUMBER: _ClassVar[int]
    MODIFY_REJECT_FIELD_NUMBER: _ClassVar[int]
    FILL_FIELD_NUMBER: _ClassVar[int]
    HEARTBEAT_FIELD_NUMBER: _ClassVar[int]
    POSITION_FIELD_NUMBER: _ClassVar[int]
    MASS_CANCEL_ACK_FIELD_NUMBER: _ClassVar[int]
    new_ack: NewOrderAck
    cancel_ack: CancelOrderAck
    modify_ack: ModifyOrderAck
    new_reject: NewOrderReject
    cancel_reject: CancelOrderReject
    modify_reject: ModifyOrderReject
    fill: Fill
    heartbeat: Heartbeat
    position: AssetPosition
    mass_cancel_ack: MassCancelAck
    def __init__(self, new_ack: _Optional[_Union[NewOrderAck, _Mapping]] = ..., cancel_ack: _Optional[_Union[CancelOrderAck, _Mapping]] = ..., modify_ack: _Optional[_Union[ModifyOrderAck, _Mapping]] = ..., new_reject: _Optional[_Union[NewOrderReject, _Mapping]] = ..., cancel_reject: _Optional[_Union[CancelOrderReject, _Mapping]] = ..., modify_reject: _Optional[_Union[ModifyOrderReject, _Mapping]] = ..., fill: _Optional[_Union[Fill, _Mapping]] = ..., heartbeat: _Optional[_Union[Heartbeat, _Mapping]] = ..., position: _Optional[_Union[AssetPosition, _Mapping]] = ..., mass_cancel_ack: _Optional[_Union[MassCancelAck, _Mapping]] = ...) -> None: ...

class NewOrderAck(_message.Message):
    __slots__ = ("msg_seq_num", "client_order_id", "request_id", "exchange_order_id", "market_id", "price", "quantity", "side", "time_in_force", "order_type", "transact_time", "subaccount_id", "cancel_on_disconnect")
    MSG_SEQ_NUM_FIELD_NUMBER: _ClassVar[int]
    CLIENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    EXCHANGE_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    MARKET_ID_FIELD_NUMBER: _ClassVar[int]
    PRICE_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    SIDE_FIELD_NUMBER: _ClassVar[int]
    TIME_IN_FORCE_FIELD_NUMBER: _ClassVar[int]
    ORDER_TYPE_FIELD_NUMBER: _ClassVar[int]
    TRANSACT_TIME_FIELD_NUMBER: _ClassVar[int]
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    CANCEL_ON_DISCONNECT_FIELD_NUMBER: _ClassVar[int]
    msg_seq_num: int
    client_order_id: int
    request_id: int
    exchange_order_id: int
    market_id: int
    price: int
    quantity: int
    side: Side
    time_in_force: TimeInForce
    order_type: OrderType
    transact_time: int
    subaccount_id: int
    cancel_on_disconnect: bool
    def __init__(self, msg_seq_num: _Optional[int] = ..., client_order_id: _Optional[int] = ..., request_id: _Optional[int] = ..., exchange_order_id: _Optional[int] = ..., market_id: _Optional[int] = ..., price: _Optional[int] = ..., quantity: _Optional[int] = ..., side: _Optional[_Union[Side, str]] = ..., time_in_force: _Optional[_Union[TimeInForce, str]] = ..., order_type: _Optional[_Union[OrderType, str]] = ..., transact_time: _Optional[int] = ..., subaccount_id: _Optional[int] = ..., cancel_on_disconnect: bool = ...) -> None: ...

class CancelOrderAck(_message.Message):
    __slots__ = ("msg_seq_num", "client_order_id", "request_id", "transact_time", "subaccount_id", "reason", "market_id", "exchange_order_id")
    class Reason(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        UNCLASSIFIED: _ClassVar[CancelOrderAck.Reason]
        DISCONNECT: _ClassVar[CancelOrderAck.Reason]
        REQUESTED: _ClassVar[CancelOrderAck.Reason]
        IOC: _ClassVar[CancelOrderAck.Reason]
        STP_RESTING: _ClassVar[CancelOrderAck.Reason]
        STP_AGGRESSING: _ClassVar[CancelOrderAck.Reason]
        MASS_CANCEL: _ClassVar[CancelOrderAck.Reason]
        POSITION_LIMIT: _ClassVar[CancelOrderAck.Reason]
    UNCLASSIFIED: CancelOrderAck.Reason
    DISCONNECT: CancelOrderAck.Reason
    REQUESTED: CancelOrderAck.Reason
    IOC: CancelOrderAck.Reason
    STP_RESTING: CancelOrderAck.Reason
    STP_AGGRESSING: CancelOrderAck.Reason
    MASS_CANCEL: CancelOrderAck.Reason
    POSITION_LIMIT: CancelOrderAck.Reason
    MSG_SEQ_NUM_FIELD_NUMBER: _ClassVar[int]
    CLIENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    TRANSACT_TIME_FIELD_NUMBER: _ClassVar[int]
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    MARKET_ID_FIELD_NUMBER: _ClassVar[int]
    EXCHANGE_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    msg_seq_num: int
    client_order_id: int
    request_id: int
    transact_time: int
    subaccount_id: int
    reason: CancelOrderAck.Reason
    market_id: int
    exchange_order_id: int
    def __init__(self, msg_seq_num: _Optional[int] = ..., client_order_id: _Optional[int] = ..., request_id: _Optional[int] = ..., transact_time: _Optional[int] = ..., subaccount_id: _Optional[int] = ..., reason: _Optional[_Union[CancelOrderAck.Reason, str]] = ..., market_id: _Optional[int] = ..., exchange_order_id: _Optional[int] = ...) -> None: ...

class ModifyOrderAck(_message.Message):
    __slots__ = ("msg_seq_num", "client_order_id", "request_id", "transact_time", "remaining_quantity", "subaccount_id", "market_id", "price", "quantity", "cumulative_quantity", "exchange_order_id")
    MSG_SEQ_NUM_FIELD_NUMBER: _ClassVar[int]
    CLIENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    TRANSACT_TIME_FIELD_NUMBER: _ClassVar[int]
    REMAINING_QUANTITY_FIELD_NUMBER: _ClassVar[int]
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    MARKET_ID_FIELD_NUMBER: _ClassVar[int]
    PRICE_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    CUMULATIVE_QUANTITY_FIELD_NUMBER: _ClassVar[int]
    EXCHANGE_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    msg_seq_num: int
    client_order_id: int
    request_id: int
    transact_time: int
    remaining_quantity: int
    subaccount_id: int
    market_id: int
    price: int
    quantity: int
    cumulative_quantity: int
    exchange_order_id: int
    def __init__(self, msg_seq_num: _Optional[int] = ..., client_order_id: _Optional[int] = ..., request_id: _Optional[int] = ..., transact_time: _Optional[int] = ..., remaining_quantity: _Optional[int] = ..., subaccount_id: _Optional[int] = ..., market_id: _Optional[int] = ..., price: _Optional[int] = ..., quantity: _Optional[int] = ..., cumulative_quantity: _Optional[int] = ..., exchange_order_id: _Optional[int] = ...) -> None: ...

class MassCancelAck(_message.Message):
    __slots__ = ("msg_seq_num", "subaccount_id", "request_id", "transact_time", "reason", "total_affected_orders")
    class Reason(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        UNCLASSIFIED: _ClassVar[MassCancelAck.Reason]
        INVALID_MARKET_ID: _ClassVar[MassCancelAck.Reason]
        INVALID_SIDE: _ClassVar[MassCancelAck.Reason]
    UNCLASSIFIED: MassCancelAck.Reason
    INVALID_MARKET_ID: MassCancelAck.Reason
    INVALID_SIDE: MassCancelAck.Reason
    MSG_SEQ_NUM_FIELD_NUMBER: _ClassVar[int]
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    TRANSACT_TIME_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    TOTAL_AFFECTED_ORDERS_FIELD_NUMBER: _ClassVar[int]
    msg_seq_num: int
    subaccount_id: int
    request_id: int
    transact_time: int
    reason: MassCancelAck.Reason
    total_affected_orders: int
    def __init__(self, msg_seq_num: _Optional[int] = ..., subaccount_id: _Optional[int] = ..., request_id: _Optional[int] = ..., transact_time: _Optional[int] = ..., reason: _Optional[_Union[MassCancelAck.Reason, str]] = ..., total_affected_orders: _Optional[int] = ...) -> None: ...

class NewOrderReject(_message.Message):
    __slots__ = ("msg_seq_num", "client_order_id", "request_id", "transact_time", "subaccount_id", "reason", "market_id", "price", "quantity", "side", "time_in_force", "order_type")
    class Reason(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        UNCLASSIFIED: _ClassVar[NewOrderReject.Reason]
        INVALID_QUANTITY: _ClassVar[NewOrderReject.Reason]
        INVALID_MARKET_ID: _ClassVar[NewOrderReject.Reason]
        DUPLICATE_ORDER_ID: _ClassVar[NewOrderReject.Reason]
        INVALID_SIDE: _ClassVar[NewOrderReject.Reason]
        INVALID_TIME_IN_FORCE: _ClassVar[NewOrderReject.Reason]
        INVALID_ORDER_TYPE: _ClassVar[NewOrderReject.Reason]
        INVALID_POST_ONLY: _ClassVar[NewOrderReject.Reason]
        INVALID_SELF_TRADE_PREVENTION: _ClassVar[NewOrderReject.Reason]
        UNKNOWN_TRADER: _ClassVar[NewOrderReject.Reason]
        PRICE_WITH_MARKET_LIMIT_ORDER: _ClassVar[NewOrderReject.Reason]
        POST_ONLY_WITH_MARKET_ORDER: _ClassVar[NewOrderReject.Reason]
        POST_ONLY_WITH_INVALID_TIF: _ClassVar[NewOrderReject.Reason]
        EXCEEDED_SPOT_POSITION: _ClassVar[NewOrderReject.Reason]
        NO_OPPOSING_RESTING_ORDER: _ClassVar[NewOrderReject.Reason]
        POST_ONLY_WOULD_TRADE: _ClassVar[NewOrderReject.Reason]
        DID_NOT_FULLY_FILL: _ClassVar[NewOrderReject.Reason]
        ONLY_ORDER_CANCEL_ACCEPTED: _ClassVar[NewOrderReject.Reason]
        PROTECTION_PRICE_WOULD_NOT_TRADE: _ClassVar[NewOrderReject.Reason]
        NO_REFERENCE_PRICE: _ClassVar[NewOrderReject.Reason]
        SLIPPAGE_TOO_HIGH: _ClassVar[NewOrderReject.Reason]
        OUTSIDE_PRICE_BAND: _ClassVar[NewOrderReject.Reason]
    UNCLASSIFIED: NewOrderReject.Reason
    INVALID_QUANTITY: NewOrderReject.Reason
    INVALID_MARKET_ID: NewOrderReject.Reason
    DUPLICATE_ORDER_ID: NewOrderReject.Reason
    INVALID_SIDE: NewOrderReject.Reason
    INVALID_TIME_IN_FORCE: NewOrderReject.Reason
    INVALID_ORDER_TYPE: NewOrderReject.Reason
    INVALID_POST_ONLY: NewOrderReject.Reason
    INVALID_SELF_TRADE_PREVENTION: NewOrderReject.Reason
    UNKNOWN_TRADER: NewOrderReject.Reason
    PRICE_WITH_MARKET_LIMIT_ORDER: NewOrderReject.Reason
    POST_ONLY_WITH_MARKET_ORDER: NewOrderReject.Reason
    POST_ONLY_WITH_INVALID_TIF: NewOrderReject.Reason
    EXCEEDED_SPOT_POSITION: NewOrderReject.Reason
    NO_OPPOSING_RESTING_ORDER: NewOrderReject.Reason
    POST_ONLY_WOULD_TRADE: NewOrderReject.Reason
    DID_NOT_FULLY_FILL: NewOrderReject.Reason
    ONLY_ORDER_CANCEL_ACCEPTED: NewOrderReject.Reason
    PROTECTION_PRICE_WOULD_NOT_TRADE: NewOrderReject.Reason
    NO_REFERENCE_PRICE: NewOrderReject.Reason
    SLIPPAGE_TOO_HIGH: NewOrderReject.Reason
    OUTSIDE_PRICE_BAND: NewOrderReject.Reason
    MSG_SEQ_NUM_FIELD_NUMBER: _ClassVar[int]
    CLIENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    TRANSACT_TIME_FIELD_NUMBER: _ClassVar[int]
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    MARKET_ID_FIELD_NUMBER: _ClassVar[int]
    PRICE_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    SIDE_FIELD_NUMBER: _ClassVar[int]
    TIME_IN_FORCE_FIELD_NUMBER: _ClassVar[int]
    ORDER_TYPE_FIELD_NUMBER: _ClassVar[int]
    msg_seq_num: int
    client_order_id: int
    request_id: int
    transact_time: int
    subaccount_id: int
    reason: NewOrderReject.Reason
    market_id: int
    price: int
    quantity: int
    side: Side
    time_in_force: TimeInForce
    order_type: OrderType
    def __init__(self, msg_seq_num: _Optional[int] = ..., client_order_id: _Optional[int] = ..., request_id: _Optional[int] = ..., transact_time: _Optional[int] = ..., subaccount_id: _Optional[int] = ..., reason: _Optional[_Union[NewOrderReject.Reason, str]] = ..., market_id: _Optional[int] = ..., price: _Optional[int] = ..., quantity: _Optional[int] = ..., side: _Optional[_Union[Side, str]] = ..., time_in_force: _Optional[_Union[TimeInForce, str]] = ..., order_type: _Optional[_Union[OrderType, str]] = ...) -> None: ...

class CancelOrderReject(_message.Message):
    __slots__ = ("msg_seq_num", "client_order_id", "request_id", "transact_time", "subaccount_id", "reason", "market_id")
    class Reason(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        UNCLASSIFIED: _ClassVar[CancelOrderReject.Reason]
        INVALID_MARKET_ID: _ClassVar[CancelOrderReject.Reason]
        ORDER_NOT_FOUND: _ClassVar[CancelOrderReject.Reason]
    UNCLASSIFIED: CancelOrderReject.Reason
    INVALID_MARKET_ID: CancelOrderReject.Reason
    ORDER_NOT_FOUND: CancelOrderReject.Reason
    MSG_SEQ_NUM_FIELD_NUMBER: _ClassVar[int]
    CLIENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    TRANSACT_TIME_FIELD_NUMBER: _ClassVar[int]
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    MARKET_ID_FIELD_NUMBER: _ClassVar[int]
    msg_seq_num: int
    client_order_id: int
    request_id: int
    transact_time: int
    subaccount_id: int
    reason: CancelOrderReject.Reason
    market_id: int
    def __init__(self, msg_seq_num: _Optional[int] = ..., client_order_id: _Optional[int] = ..., request_id: _Optional[int] = ..., transact_time: _Optional[int] = ..., subaccount_id: _Optional[int] = ..., reason: _Optional[_Union[CancelOrderReject.Reason, str]] = ..., market_id: _Optional[int] = ...) -> None: ...

class ModifyOrderReject(_message.Message):
    __slots__ = ("msg_seq_num", "client_order_id", "request_id", "transact_time", "subaccount_id", "reason", "market_id")
    class Reason(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        UNCLASSIFIED: _ClassVar[ModifyOrderReject.Reason]
        INVALID_QUANTITY: _ClassVar[ModifyOrderReject.Reason]
        INVALID_MARKET_ID: _ClassVar[ModifyOrderReject.Reason]
        ORDER_NOT_FOUND: _ClassVar[ModifyOrderReject.Reason]
        INVALID_IFM: _ClassVar[ModifyOrderReject.Reason]
        INVALID_POST_ONLY: _ClassVar[ModifyOrderReject.Reason]
        INVALID_SELF_TRADE_PREVENTION: _ClassVar[ModifyOrderReject.Reason]
        UNKNOWN_TRADER: _ClassVar[ModifyOrderReject.Reason]
        EXCEEDED_SPOT_POSITION: _ClassVar[ModifyOrderReject.Reason]
        POST_ONLY_WOULD_TRADE: _ClassVar[ModifyOrderReject.Reason]
        ONLY_ORDER_CANCEL_ACCEPTED: _ClassVar[ModifyOrderReject.Reason]
        OUTSIDE_PRICE_BAND: _ClassVar[ModifyOrderReject.Reason]
    UNCLASSIFIED: ModifyOrderReject.Reason
    INVALID_QUANTITY: ModifyOrderReject.Reason
    INVALID_MARKET_ID: ModifyOrderReject.Reason
    ORDER_NOT_FOUND: ModifyOrderReject.Reason
    INVALID_IFM: ModifyOrderReject.Reason
    INVALID_POST_ONLY: ModifyOrderReject.Reason
    INVALID_SELF_TRADE_PREVENTION: ModifyOrderReject.Reason
    UNKNOWN_TRADER: ModifyOrderReject.Reason
    EXCEEDED_SPOT_POSITION: ModifyOrderReject.Reason
    POST_ONLY_WOULD_TRADE: ModifyOrderReject.Reason
    ONLY_ORDER_CANCEL_ACCEPTED: ModifyOrderReject.Reason
    OUTSIDE_PRICE_BAND: ModifyOrderReject.Reason
    MSG_SEQ_NUM_FIELD_NUMBER: _ClassVar[int]
    CLIENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    TRANSACT_TIME_FIELD_NUMBER: _ClassVar[int]
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    MARKET_ID_FIELD_NUMBER: _ClassVar[int]
    msg_seq_num: int
    client_order_id: int
    request_id: int
    transact_time: int
    subaccount_id: int
    reason: ModifyOrderReject.Reason
    market_id: int
    def __init__(self, msg_seq_num: _Optional[int] = ..., client_order_id: _Optional[int] = ..., request_id: _Optional[int] = ..., transact_time: _Optional[int] = ..., subaccount_id: _Optional[int] = ..., reason: _Optional[_Union[ModifyOrderReject.Reason, str]] = ..., market_id: _Optional[int] = ...) -> None: ...

class Fill(_message.Message):
    __slots__ = ("msg_seq_num", "market_id", "client_order_id", "exchange_order_id", "fill_price", "fill_quantity", "leaves_quantity", "transact_time", "subaccount_id", "cumulative_quantity", "side", "aggressor_indicator", "fee_ratio", "trade_id")
    MSG_SEQ_NUM_FIELD_NUMBER: _ClassVar[int]
    MARKET_ID_FIELD_NUMBER: _ClassVar[int]
    CLIENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    EXCHANGE_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    FILL_PRICE_FIELD_NUMBER: _ClassVar[int]
    FILL_QUANTITY_FIELD_NUMBER: _ClassVar[int]
    LEAVES_QUANTITY_FIELD_NUMBER: _ClassVar[int]
    TRANSACT_TIME_FIELD_NUMBER: _ClassVar[int]
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    CUMULATIVE_QUANTITY_FIELD_NUMBER: _ClassVar[int]
    SIDE_FIELD_NUMBER: _ClassVar[int]
    AGGRESSOR_INDICATOR_FIELD_NUMBER: _ClassVar[int]
    FEE_RATIO_FIELD_NUMBER: _ClassVar[int]
    TRADE_ID_FIELD_NUMBER: _ClassVar[int]
    msg_seq_num: int
    market_id: int
    client_order_id: int
    exchange_order_id: int
    fill_price: int
    fill_quantity: int
    leaves_quantity: int
    transact_time: int
    subaccount_id: int
    cumulative_quantity: int
    side: Side
    aggressor_indicator: bool
    fee_ratio: FixedPointDecimal
    trade_id: int
    def __init__(self, msg_seq_num: _Optional[int] = ..., market_id: _Optional[int] = ..., client_order_id: _Optional[int] = ..., exchange_order_id: _Optional[int] = ..., fill_price: _Optional[int] = ..., fill_quantity: _Optional[int] = ..., leaves_quantity: _Optional[int] = ..., transact_time: _Optional[int] = ..., subaccount_id: _Optional[int] = ..., cumulative_quantity: _Optional[int] = ..., side: _Optional[_Union[Side, str]] = ..., aggressor_indicator: bool = ..., fee_ratio: _Optional[_Union[FixedPointDecimal, _Mapping]] = ..., trade_id: _Optional[int] = ...) -> None: ...

class FixedPointDecimal(_message.Message):
    __slots__ = ("mantissa", "exponent")
    MANTISSA_FIELD_NUMBER: _ClassVar[int]
    EXPONENT_FIELD_NUMBER: _ClassVar[int]
    mantissa: int
    exponent: int
    def __init__(self, mantissa: _Optional[int] = ..., exponent: _Optional[int] = ...) -> None: ...

class AssetPosition(_message.Message):
    __slots__ = ("subaccount_id", "asset_id", "total", "available")
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    ASSET_ID_FIELD_NUMBER: _ClassVar[int]
    TOTAL_FIELD_NUMBER: _ClassVar[int]
    AVAILABLE_FIELD_NUMBER: _ClassVar[int]
    subaccount_id: int
    asset_id: int
    total: RawUnits
    available: RawUnits
    def __init__(self, subaccount_id: _Optional[int] = ..., asset_id: _Optional[int] = ..., total: _Optional[_Union[RawUnits, _Mapping]] = ..., available: _Optional[_Union[RawUnits, _Mapping]] = ...) -> None: ...

class RawUnits(_message.Message):
    __slots__ = ("word0", "word1", "word2", "word3")
    WORD0_FIELD_NUMBER: _ClassVar[int]
    WORD1_FIELD_NUMBER: _ClassVar[int]
    WORD2_FIELD_NUMBER: _ClassVar[int]
    WORD3_FIELD_NUMBER: _ClassVar[int]
    word0: int
    word1: int
    word2: int
    word3: int
    def __init__(self, word0: _Optional[int] = ..., word1: _Optional[int] = ..., word2: _Optional[int] = ..., word3: _Optional[int] = ...) -> None: ...

class Bootstrap(_message.Message):
    __slots__ = ("done", "resting", "position")
    DONE_FIELD_NUMBER: _ClassVar[int]
    RESTING_FIELD_NUMBER: _ClassVar[int]
    POSITION_FIELD_NUMBER: _ClassVar[int]
    done: Done
    resting: RestingOrders
    position: AssetPositions
    def __init__(self, done: _Optional[_Union[Done, _Mapping]] = ..., resting: _Optional[_Union[RestingOrders, _Mapping]] = ..., position: _Optional[_Union[AssetPositions, _Mapping]] = ...) -> None: ...

class RestingOrders(_message.Message):
    __slots__ = ("orders",)
    ORDERS_FIELD_NUMBER: _ClassVar[int]
    orders: _containers.RepeatedCompositeFieldContainer[RestingOrder]
    def __init__(self, orders: _Optional[_Iterable[_Union[RestingOrder, _Mapping]]] = ...) -> None: ...

class AssetPositions(_message.Message):
    __slots__ = ("positions",)
    POSITIONS_FIELD_NUMBER: _ClassVar[int]
    positions: _containers.RepeatedCompositeFieldContainer[AssetPosition]
    def __init__(self, positions: _Optional[_Iterable[_Union[AssetPosition, _Mapping]]] = ...) -> None: ...

class Done(_message.Message):
    __slots__ = ("latest_transact_time", "read_only")
    LATEST_TRANSACT_TIME_FIELD_NUMBER: _ClassVar[int]
    READ_ONLY_FIELD_NUMBER: _ClassVar[int]
    latest_transact_time: int
    read_only: bool
    def __init__(self, latest_transact_time: _Optional[int] = ..., read_only: bool = ...) -> None: ...

class RestingOrder(_message.Message):
    __slots__ = ("client_order_id", "exchange_order_id", "market_id", "price", "order_quantity", "side", "time_in_force", "order_type", "remaining_quantity", "rest_time", "subaccount_id", "cumulative_quantity", "cancel_on_disconnect")
    CLIENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    EXCHANGE_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    MARKET_ID_FIELD_NUMBER: _ClassVar[int]
    PRICE_FIELD_NUMBER: _ClassVar[int]
    ORDER_QUANTITY_FIELD_NUMBER: _ClassVar[int]
    SIDE_FIELD_NUMBER: _ClassVar[int]
    TIME_IN_FORCE_FIELD_NUMBER: _ClassVar[int]
    ORDER_TYPE_FIELD_NUMBER: _ClassVar[int]
    REMAINING_QUANTITY_FIELD_NUMBER: _ClassVar[int]
    REST_TIME_FIELD_NUMBER: _ClassVar[int]
    SUBACCOUNT_ID_FIELD_NUMBER: _ClassVar[int]
    CUMULATIVE_QUANTITY_FIELD_NUMBER: _ClassVar[int]
    CANCEL_ON_DISCONNECT_FIELD_NUMBER: _ClassVar[int]
    client_order_id: int
    exchange_order_id: int
    market_id: int
    price: int
    order_quantity: int
    side: Side
    time_in_force: TimeInForce
    order_type: OrderType
    remaining_quantity: int
    rest_time: int
    subaccount_id: int
    cumulative_quantity: int
    cancel_on_disconnect: bool
    def __init__(self, client_order_id: _Optional[int] = ..., exchange_order_id: _Optional[int] = ..., market_id: _Optional[int] = ..., price: _Optional[int] = ..., order_quantity: _Optional[int] = ..., side: _Optional[_Union[Side, str]] = ..., time_in_force: _Optional[_Union[TimeInForce, str]] = ..., order_type: _Optional[_Union[OrderType, str]] = ..., remaining_quantity: _Optional[int] = ..., rest_time: _Optional[int] = ..., subaccount_id: _Optional[int] = ..., cumulative_quantity: _Optional[int] = ..., cancel_on_disconnect: bool = ...) -> None: ...
