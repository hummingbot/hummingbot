from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class PrivateAccountV3Api(_message.Message):
    __slots__ = ("vcoinName", "coinId", "balanceAmount", "balanceAmountChange", "frozenAmount", "frozenAmountChange", "type", "time")
    VCOINNAME_FIELD_NUMBER: _ClassVar[int]
    COINID_FIELD_NUMBER: _ClassVar[int]
    BALANCEAMOUNT_FIELD_NUMBER: _ClassVar[int]
    BALANCEAMOUNTCHANGE_FIELD_NUMBER: _ClassVar[int]
    FROZENAMOUNT_FIELD_NUMBER: _ClassVar[int]
    FROZENAMOUNTCHANGE_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    TIME_FIELD_NUMBER: _ClassVar[int]
    vcoinName: str
    coinId: str
    balanceAmount: str
    balanceAmountChange: str
    frozenAmount: str
    frozenAmountChange: str
    type: str
    time: int
    def __init__(self, vcoinName: _Optional[str] = ..., coinId: _Optional[str] = ..., balanceAmount: _Optional[str] = ..., balanceAmountChange: _Optional[str] = ..., frozenAmount: _Optional[str] = ..., frozenAmountChange: _Optional[str] = ..., type: _Optional[str] = ..., time: _Optional[int] = ...) -> None: ...
