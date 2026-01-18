from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class PublicIncreaseDepthsV3Api(_message.Message):
    __slots__ = ("asks", "bids", "eventType", "version")
    ASKS_FIELD_NUMBER: _ClassVar[int]
    BIDS_FIELD_NUMBER: _ClassVar[int]
    EVENTTYPE_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    asks: _containers.RepeatedCompositeFieldContainer[PublicIncreaseDepthV3ApiItem]
    bids: _containers.RepeatedCompositeFieldContainer[PublicIncreaseDepthV3ApiItem]
    eventType: str
    version: str
    def __init__(self, asks: _Optional[_Iterable[_Union[PublicIncreaseDepthV3ApiItem, _Mapping]]] = ..., bids: _Optional[_Iterable[_Union[PublicIncreaseDepthV3ApiItem, _Mapping]]] = ..., eventType: _Optional[str] = ..., version: _Optional[str] = ...) -> None: ...

class PublicIncreaseDepthV3ApiItem(_message.Message):
    __slots__ = ("price", "quantity")
    PRICE_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    price: str
    quantity: str
    def __init__(self, price: _Optional[str] = ..., quantity: _Optional[str] = ...) -> None: ...
