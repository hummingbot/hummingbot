from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class PublicAggreDealsV3Api(_message.Message):
    __slots__ = ("deals", "eventType")
    DEALS_FIELD_NUMBER: _ClassVar[int]
    EVENTTYPE_FIELD_NUMBER: _ClassVar[int]
    deals: _containers.RepeatedCompositeFieldContainer[PublicAggreDealsV3ApiItem]
    eventType: str
    def __init__(self, deals: _Optional[_Iterable[_Union[PublicAggreDealsV3ApiItem, _Mapping]]] = ..., eventType: _Optional[str] = ...) -> None: ...

class PublicAggreDealsV3ApiItem(_message.Message):
    __slots__ = ("price", "quantity", "tradeType", "time")
    PRICE_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    TRADETYPE_FIELD_NUMBER: _ClassVar[int]
    TIME_FIELD_NUMBER: _ClassVar[int]
    price: str
    quantity: str
    tradeType: int
    time: int
    def __init__(self, price: _Optional[str] = ..., quantity: _Optional[str] = ..., tradeType: _Optional[int] = ..., time: _Optional[int] = ...) -> None: ...
