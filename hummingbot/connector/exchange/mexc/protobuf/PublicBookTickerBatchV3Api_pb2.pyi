from hummingbot.connector.exchange.mexc.protobuf import PublicBookTickerV3Api_pb2 as _PublicBookTickerV3Api_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class PublicBookTickerBatchV3Api(_message.Message):
    __slots__ = ("items",)
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[_PublicBookTickerV3Api_pb2.PublicBookTickerV3Api]
    def __init__(self, items: _Optional[_Iterable[_Union[_PublicBookTickerV3Api_pb2.PublicBookTickerV3Api, _Mapping]]] = ...) -> None: ...
