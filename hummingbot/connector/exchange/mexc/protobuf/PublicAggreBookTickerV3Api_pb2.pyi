from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class PublicAggreBookTickerV3Api(_message.Message):
    __slots__ = ("bidPrice", "bidQuantity", "askPrice", "askQuantity")
    BIDPRICE_FIELD_NUMBER: _ClassVar[int]
    BIDQUANTITY_FIELD_NUMBER: _ClassVar[int]
    ASKPRICE_FIELD_NUMBER: _ClassVar[int]
    ASKQUANTITY_FIELD_NUMBER: _ClassVar[int]
    bidPrice: str
    bidQuantity: str
    askPrice: str
    askQuantity: str
    def __init__(self, bidPrice: _Optional[str] = ..., bidQuantity: _Optional[str] = ..., askPrice: _Optional[str] = ..., askQuantity: _Optional[str] = ...) -> None: ...
