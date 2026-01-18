from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class PublicMiniTickerV3Api(_message.Message):
    __slots__ = ("symbol", "price", "rate", "zonedRate", "high", "low", "volume", "quantity", "lastCloseRate", "lastCloseZonedRate", "lastCloseHigh", "lastCloseLow")
    SYMBOL_FIELD_NUMBER: _ClassVar[int]
    PRICE_FIELD_NUMBER: _ClassVar[int]
    RATE_FIELD_NUMBER: _ClassVar[int]
    ZONEDRATE_FIELD_NUMBER: _ClassVar[int]
    HIGH_FIELD_NUMBER: _ClassVar[int]
    LOW_FIELD_NUMBER: _ClassVar[int]
    VOLUME_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    LASTCLOSERATE_FIELD_NUMBER: _ClassVar[int]
    LASTCLOSEZONEDRATE_FIELD_NUMBER: _ClassVar[int]
    LASTCLOSEHIGH_FIELD_NUMBER: _ClassVar[int]
    LASTCLOSELOW_FIELD_NUMBER: _ClassVar[int]
    symbol: str
    price: str
    rate: str
    zonedRate: str
    high: str
    low: str
    volume: str
    quantity: str
    lastCloseRate: str
    lastCloseZonedRate: str
    lastCloseHigh: str
    lastCloseLow: str
    def __init__(self, symbol: _Optional[str] = ..., price: _Optional[str] = ..., rate: _Optional[str] = ..., zonedRate: _Optional[str] = ..., high: _Optional[str] = ..., low: _Optional[str] = ..., volume: _Optional[str] = ..., quantity: _Optional[str] = ..., lastCloseRate: _Optional[str] = ..., lastCloseZonedRate: _Optional[str] = ..., lastCloseHigh: _Optional[str] = ..., lastCloseLow: _Optional[str] = ...) -> None: ...
