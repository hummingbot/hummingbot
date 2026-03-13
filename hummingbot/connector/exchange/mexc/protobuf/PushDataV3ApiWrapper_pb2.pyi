from hummingbot.connector.exchange.mexc.protobuf import PublicDealsV3Api_pb2 as _PublicDealsV3Api_pb2
from hummingbot.connector.exchange.mexc.protobuf import PublicIncreaseDepthsV3Api_pb2 as _PublicIncreaseDepthsV3Api_pb2
from hummingbot.connector.exchange.mexc.protobuf import PublicLimitDepthsV3Api_pb2 as _PublicLimitDepthsV3Api_pb2
from hummingbot.connector.exchange.mexc.protobuf import PrivateOrdersV3Api_pb2 as _PrivateOrdersV3Api_pb2
from hummingbot.connector.exchange.mexc.protobuf import PublicBookTickerV3Api_pb2 as _PublicBookTickerV3Api_pb2
from hummingbot.connector.exchange.mexc.protobuf import PrivateDealsV3Api_pb2 as _PrivateDealsV3Api_pb2
from hummingbot.connector.exchange.mexc.protobuf import PrivateAccountV3Api_pb2 as _PrivateAccountV3Api_pb2
from hummingbot.connector.exchange.mexc.protobuf import PublicSpotKlineV3Api_pb2 as _PublicSpotKlineV3Api_pb2
from hummingbot.connector.exchange.mexc.protobuf import PublicMiniTickerV3Api_pb2 as _PublicMiniTickerV3Api_pb2
from hummingbot.connector.exchange.mexc.protobuf import PublicMiniTickersV3Api_pb2 as _PublicMiniTickersV3Api_pb2
from hummingbot.connector.exchange.mexc.protobuf import PublicBookTickerBatchV3Api_pb2 as _PublicBookTickerBatchV3Api_pb2
from hummingbot.connector.exchange.mexc.protobuf import PublicIncreaseDepthsBatchV3Api_pb2 as _PublicIncreaseDepthsBatchV3Api_pb2
from hummingbot.connector.exchange.mexc.protobuf import PublicAggreDepthsV3Api_pb2 as _PublicAggreDepthsV3Api_pb2
from hummingbot.connector.exchange.mexc.protobuf import PublicAggreDealsV3Api_pb2 as _PublicAggreDealsV3Api_pb2
from hummingbot.connector.exchange.mexc.protobuf import PublicAggreBookTickerV3Api_pb2 as _PublicAggreBookTickerV3Api_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class PushDataV3ApiWrapper(_message.Message):
    __slots__ = ("channel", "publicDeals", "publicIncreaseDepths", "publicLimitDepths", "privateOrders", "publicBookTicker", "privateDeals", "privateAccount", "publicSpotKline", "publicMiniTicker", "publicMiniTickers", "publicBookTickerBatch", "publicIncreaseDepthsBatch", "publicAggreDepths", "publicAggreDeals", "publicAggreBookTicker", "symbol", "symbolId", "createTime", "sendTime")
    CHANNEL_FIELD_NUMBER: _ClassVar[int]
    PUBLICDEALS_FIELD_NUMBER: _ClassVar[int]
    PUBLICINCREASEDEPTHS_FIELD_NUMBER: _ClassVar[int]
    PUBLICLIMITDEPTHS_FIELD_NUMBER: _ClassVar[int]
    PRIVATEORDERS_FIELD_NUMBER: _ClassVar[int]
    PUBLICBOOKTICKER_FIELD_NUMBER: _ClassVar[int]
    PRIVATEDEALS_FIELD_NUMBER: _ClassVar[int]
    PRIVATEACCOUNT_FIELD_NUMBER: _ClassVar[int]
    PUBLICSPOTKLINE_FIELD_NUMBER: _ClassVar[int]
    PUBLICMINITICKER_FIELD_NUMBER: _ClassVar[int]
    PUBLICMINITICKERS_FIELD_NUMBER: _ClassVar[int]
    PUBLICBOOKTICKERBATCH_FIELD_NUMBER: _ClassVar[int]
    PUBLICINCREASEDEPTHSBATCH_FIELD_NUMBER: _ClassVar[int]
    PUBLICAGGREDEPTHS_FIELD_NUMBER: _ClassVar[int]
    PUBLICAGGREDEALS_FIELD_NUMBER: _ClassVar[int]
    PUBLICAGGREBOOKTICKER_FIELD_NUMBER: _ClassVar[int]
    SYMBOL_FIELD_NUMBER: _ClassVar[int]
    SYMBOLID_FIELD_NUMBER: _ClassVar[int]
    CREATETIME_FIELD_NUMBER: _ClassVar[int]
    SENDTIME_FIELD_NUMBER: _ClassVar[int]
    channel: str
    publicDeals: _PublicDealsV3Api_pb2.PublicDealsV3Api
    publicIncreaseDepths: _PublicIncreaseDepthsV3Api_pb2.PublicIncreaseDepthsV3Api
    publicLimitDepths: _PublicLimitDepthsV3Api_pb2.PublicLimitDepthsV3Api
    privateOrders: _PrivateOrdersV3Api_pb2.PrivateOrdersV3Api
    publicBookTicker: _PublicBookTickerV3Api_pb2.PublicBookTickerV3Api
    privateDeals: _PrivateDealsV3Api_pb2.PrivateDealsV3Api
    privateAccount: _PrivateAccountV3Api_pb2.PrivateAccountV3Api
    publicSpotKline: _PublicSpotKlineV3Api_pb2.PublicSpotKlineV3Api
    publicMiniTicker: _PublicMiniTickerV3Api_pb2.PublicMiniTickerV3Api
    publicMiniTickers: _PublicMiniTickersV3Api_pb2.PublicMiniTickersV3Api
    publicBookTickerBatch: _PublicBookTickerBatchV3Api_pb2.PublicBookTickerBatchV3Api
    publicIncreaseDepthsBatch: _PublicIncreaseDepthsBatchV3Api_pb2.PublicIncreaseDepthsBatchV3Api
    publicAggreDepths: _PublicAggreDepthsV3Api_pb2.PublicAggreDepthsV3Api
    publicAggreDeals: _PublicAggreDealsV3Api_pb2.PublicAggreDealsV3Api
    publicAggreBookTicker: _PublicAggreBookTickerV3Api_pb2.PublicAggreBookTickerV3Api
    symbol: str
    symbolId: str
    createTime: int
    sendTime: int
    def __init__(self, channel: _Optional[str] = ..., publicDeals: _Optional[_Union[_PublicDealsV3Api_pb2.PublicDealsV3Api, _Mapping]] = ..., publicIncreaseDepths: _Optional[_Union[_PublicIncreaseDepthsV3Api_pb2.PublicIncreaseDepthsV3Api, _Mapping]] = ..., publicLimitDepths: _Optional[_Union[_PublicLimitDepthsV3Api_pb2.PublicLimitDepthsV3Api, _Mapping]] = ..., privateOrders: _Optional[_Union[_PrivateOrdersV3Api_pb2.PrivateOrdersV3Api, _Mapping]] = ..., publicBookTicker: _Optional[_Union[_PublicBookTickerV3Api_pb2.PublicBookTickerV3Api, _Mapping]] = ..., privateDeals: _Optional[_Union[_PrivateDealsV3Api_pb2.PrivateDealsV3Api, _Mapping]] = ..., privateAccount: _Optional[_Union[_PrivateAccountV3Api_pb2.PrivateAccountV3Api, _Mapping]] = ..., publicSpotKline: _Optional[_Union[_PublicSpotKlineV3Api_pb2.PublicSpotKlineV3Api, _Mapping]] = ..., publicMiniTicker: _Optional[_Union[_PublicMiniTickerV3Api_pb2.PublicMiniTickerV3Api, _Mapping]] = ..., publicMiniTickers: _Optional[_Union[_PublicMiniTickersV3Api_pb2.PublicMiniTickersV3Api, _Mapping]] = ..., publicBookTickerBatch: _Optional[_Union[_PublicBookTickerBatchV3Api_pb2.PublicBookTickerBatchV3Api, _Mapping]] = ..., publicIncreaseDepthsBatch: _Optional[_Union[_PublicIncreaseDepthsBatchV3Api_pb2.PublicIncreaseDepthsBatchV3Api, _Mapping]] = ..., publicAggreDepths: _Optional[_Union[_PublicAggreDepthsV3Api_pb2.PublicAggreDepthsV3Api, _Mapping]] = ..., publicAggreDeals: _Optional[_Union[_PublicAggreDealsV3Api_pb2.PublicAggreDealsV3Api, _Mapping]] = ..., publicAggreBookTicker: _Optional[_Union[_PublicAggreBookTickerV3Api_pb2.PublicAggreBookTickerV3Api, _Mapping]] = ..., symbol: _Optional[str] = ..., symbolId: _Optional[str] = ..., createTime: _Optional[int] = ..., sendTime: _Optional[int] = ...) -> None: ...
