from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class PublicAggreDepthsV3Api(_message.Message):
    __slots__ = ("asks", "bids", "eventType", "fromVersion", "toVersion")
    ASKS_FIELD_NUMBER: _ClassVar[int]
    BIDS_FIELD_NUMBER: _ClassVar[int]
    EVENTTYPE_FIELD_NUMBER: _ClassVar[int]
    FROMVERSION_FIELD_NUMBER: _ClassVar[int]
    TOVERSION_FIELD_NUMBER: _ClassVar[int]
    asks: _containers.RepeatedCompositeFieldContainer[PublicAggreDepthV3ApiItem]
    bids: _containers.RepeatedCompositeFieldContainer[PublicAggreDepthV3ApiItem]
    eventType: str
    fromVersion: str
    toVersion: str
    def __init__(self, asks: _Optional[_Iterable[_Union[PublicAggreDepthV3ApiItem, _Mapping]]] = ..., bids: _Optional[_Iterable[_Union[PublicAggreDepthV3ApiItem, _Mapping]]] = ..., eventType: _Optional[str] = ..., fromVersion: _Optional[str] = ..., toVersion: _Optional[str] = ...) -> None: ...

class PublicAggreDepthV3ApiItem(_message.Message):
    __slots__ = ("price", "quantity")
    PRICE_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    price: str
    quantity: str
    def __init__(self, price: _Optional[str] = ..., quantity: _Optional[str] = ...) -> None: ...
