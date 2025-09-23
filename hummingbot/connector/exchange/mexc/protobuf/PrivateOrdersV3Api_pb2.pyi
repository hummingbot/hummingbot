from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class PrivateOrdersV3Api(_message.Message):
    __slots__ = ("id", "clientId", "price", "quantity", "amount", "avgPrice", "orderType", "tradeType", "isMaker", "remainAmount", "remainQuantity", "lastDealQuantity", "cumulativeQuantity", "cumulativeAmount", "status", "createTime", "market", "triggerType", "triggerPrice", "state", "ocoId", "routeFactor", "symbolId", "marketId", "marketCurrencyId", "currencyId")
    ID_FIELD_NUMBER: _ClassVar[int]
    CLIENTID_FIELD_NUMBER: _ClassVar[int]
    PRICE_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    AMOUNT_FIELD_NUMBER: _ClassVar[int]
    AVGPRICE_FIELD_NUMBER: _ClassVar[int]
    ORDERTYPE_FIELD_NUMBER: _ClassVar[int]
    TRADETYPE_FIELD_NUMBER: _ClassVar[int]
    ISMAKER_FIELD_NUMBER: _ClassVar[int]
    REMAINAMOUNT_FIELD_NUMBER: _ClassVar[int]
    REMAINQUANTITY_FIELD_NUMBER: _ClassVar[int]
    LASTDEALQUANTITY_FIELD_NUMBER: _ClassVar[int]
    CUMULATIVEQUANTITY_FIELD_NUMBER: _ClassVar[int]
    CUMULATIVEAMOUNT_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    CREATETIME_FIELD_NUMBER: _ClassVar[int]
    MARKET_FIELD_NUMBER: _ClassVar[int]
    TRIGGERTYPE_FIELD_NUMBER: _ClassVar[int]
    TRIGGERPRICE_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    OCOID_FIELD_NUMBER: _ClassVar[int]
    ROUTEFACTOR_FIELD_NUMBER: _ClassVar[int]
    SYMBOLID_FIELD_NUMBER: _ClassVar[int]
    MARKETID_FIELD_NUMBER: _ClassVar[int]
    MARKETCURRENCYID_FIELD_NUMBER: _ClassVar[int]
    CURRENCYID_FIELD_NUMBER: _ClassVar[int]
    id: str
    clientId: str
    price: str
    quantity: str
    amount: str
    avgPrice: str
    orderType: int
    tradeType: int
    isMaker: bool
    remainAmount: str
    remainQuantity: str
    lastDealQuantity: str
    cumulativeQuantity: str
    cumulativeAmount: str
    status: int
    createTime: int
    market: str
    triggerType: int
    triggerPrice: str
    state: int
    ocoId: str
    routeFactor: str
    symbolId: str
    marketId: str
    marketCurrencyId: str
    currencyId: str
    def __init__(self, id: _Optional[str] = ..., clientId: _Optional[str] = ..., price: _Optional[str] = ..., quantity: _Optional[str] = ..., amount: _Optional[str] = ..., avgPrice: _Optional[str] = ..., orderType: _Optional[int] = ..., tradeType: _Optional[int] = ..., isMaker: bool = ..., remainAmount: _Optional[str] = ..., remainQuantity: _Optional[str] = ..., lastDealQuantity: _Optional[str] = ..., cumulativeQuantity: _Optional[str] = ..., cumulativeAmount: _Optional[str] = ..., status: _Optional[int] = ..., createTime: _Optional[int] = ..., market: _Optional[str] = ..., triggerType: _Optional[int] = ..., triggerPrice: _Optional[str] = ..., state: _Optional[int] = ..., ocoId: _Optional[str] = ..., routeFactor: _Optional[str] = ..., symbolId: _Optional[str] = ..., marketId: _Optional[str] = ..., marketCurrencyId: _Optional[str] = ..., currencyId: _Optional[str] = ...) -> None: ...
