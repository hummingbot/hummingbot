from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class PublicSpotKlineV3Api(_message.Message):
    __slots__ = ("interval", "windowStart", "openingPrice", "closingPrice", "highestPrice", "lowestPrice", "volume", "amount", "windowEnd")
    INTERVAL_FIELD_NUMBER: _ClassVar[int]
    WINDOWSTART_FIELD_NUMBER: _ClassVar[int]
    OPENINGPRICE_FIELD_NUMBER: _ClassVar[int]
    CLOSINGPRICE_FIELD_NUMBER: _ClassVar[int]
    HIGHESTPRICE_FIELD_NUMBER: _ClassVar[int]
    LOWESTPRICE_FIELD_NUMBER: _ClassVar[int]
    VOLUME_FIELD_NUMBER: _ClassVar[int]
    AMOUNT_FIELD_NUMBER: _ClassVar[int]
    WINDOWEND_FIELD_NUMBER: _ClassVar[int]
    interval: str
    windowStart: int
    openingPrice: str
    closingPrice: str
    highestPrice: str
    lowestPrice: str
    volume: str
    amount: str
    windowEnd: int
    def __init__(self, interval: _Optional[str] = ..., windowStart: _Optional[int] = ..., openingPrice: _Optional[str] = ..., closingPrice: _Optional[str] = ..., highestPrice: _Optional[str] = ..., lowestPrice: _Optional[str] = ..., volume: _Optional[str] = ..., amount: _Optional[str] = ..., windowEnd: _Optional[int] = ...) -> None: ...
