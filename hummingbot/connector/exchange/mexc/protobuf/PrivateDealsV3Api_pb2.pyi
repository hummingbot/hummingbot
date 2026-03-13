from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class PrivateDealsV3Api(_message.Message):
    __slots__ = ("price", "quantity", "amount", "tradeType", "isMaker", "isSelfTrade", "tradeId", "clientOrderId", "orderId", "feeAmount", "feeCurrency", "time")
    PRICE_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    AMOUNT_FIELD_NUMBER: _ClassVar[int]
    TRADETYPE_FIELD_NUMBER: _ClassVar[int]
    ISMAKER_FIELD_NUMBER: _ClassVar[int]
    ISSELFTRADE_FIELD_NUMBER: _ClassVar[int]
    TRADEID_FIELD_NUMBER: _ClassVar[int]
    CLIENTORDERID_FIELD_NUMBER: _ClassVar[int]
    ORDERID_FIELD_NUMBER: _ClassVar[int]
    FEEAMOUNT_FIELD_NUMBER: _ClassVar[int]
    FEECURRENCY_FIELD_NUMBER: _ClassVar[int]
    TIME_FIELD_NUMBER: _ClassVar[int]
    price: str
    quantity: str
    amount: str
    tradeType: int
    isMaker: bool
    isSelfTrade: bool
    tradeId: str
    clientOrderId: str
    orderId: str
    feeAmount: str
    feeCurrency: str
    time: int
    def __init__(self, price: _Optional[str] = ..., quantity: _Optional[str] = ..., amount: _Optional[str] = ..., tradeType: _Optional[int] = ..., isMaker: bool = ..., isSelfTrade: bool = ..., tradeId: _Optional[str] = ..., clientOrderId: _Optional[str] = ..., orderId: _Optional[str] = ..., feeAmount: _Optional[str] = ..., feeCurrency: _Optional[str] = ..., time: _Optional[int] = ...) -> None: ...
