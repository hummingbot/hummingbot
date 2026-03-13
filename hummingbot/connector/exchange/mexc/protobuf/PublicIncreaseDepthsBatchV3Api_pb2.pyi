from hummingbot.connector.exchange.mexc.protobuf import PublicIncreaseDepthsV3Api_pb2 as _PublicIncreaseDepthsV3Api_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class PublicIncreaseDepthsBatchV3Api(_message.Message):
    __slots__ = ("items", "eventType")
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    EVENTTYPE_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[_PublicIncreaseDepthsV3Api_pb2.PublicIncreaseDepthsV3Api]
    eventType: str
    def __init__(self, items: _Optional[_Iterable[_Union[_PublicIncreaseDepthsV3Api_pb2.PublicIncreaseDepthsV3Api, _Mapping]]] = ..., eventType: _Optional[str] = ...) -> None: ...
