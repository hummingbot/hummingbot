import logging
from typing import Callable, Tuple, Union

from hummingbot.core.utils.class_registry import ClassRegistry

from ..cat_utilities.cat_dict_mockable_from_json_mixin import DictMethodMockableFromJsonDocMixin
from ..cat_utilities.cat_pydantic_for_json import PydanticForJsonConfig, PydanticMockableForJson
from .cat_api_v3_enums import (
    CoinbaseAdvancedTradeWSSChannel,
    CoinbaseAdvancedTradeWSSEventType,
    CoinbaseAdvancedTradeWSSOrderBidAskSide,
    CoinbaseAdvancedTradeWSSOrderMakerSide,
    CoinbaseAdvancedTradeWSSOrderStatus,
    CoinbaseAdvancedTradeWSSOrderType,
    CoinbaseAdvancedTradeWSSProductType,
)
from .cat_data_types_utilities import DataIterableMixin


class CoinbaseAdvancedTradeMessageError(Exception):
    pass


class CoinbaseAdvancedTradeEventMessage(
    ClassRegistry,
    DictMethodMockableFromJsonDocMixin,
):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class _MarketTrades(PydanticForJsonConfig):
    """
    Market Trades channel messages
    https://docs.cloud.coinbase.com/advanced-trade-api/docs/ws-channels#market-trades-channel
    ```json
    {
      "trade_id": "000000000",
      "product_id": "ETH-USD",
      "price": "1260.01",
      "size": "0.3",
      "side": "BUY",
      "time": "2019-08-14T20:42:27.265Z",
    }
    ```
    """
    trade_id: str
    product_id: str
    price: str
    size: str
    side: CoinbaseAdvancedTradeWSSOrderMakerSide
    time: str


class CoinbaseAdvancedTradeMarketTradesEventMessage(
    PydanticMockableForJson,
    CoinbaseAdvancedTradeEventMessage,
    DataIterableMixin[_MarketTrades]
):
    """
    Market Trades channel messages
    https://docs.cloud.coinbase.com/advanced-trade-api/docs/ws-channels#market-trades-channel
    ```json
    {
      "type": "snapshot",
      "trades":
      [
        {
          "trade_id": "000000000",
          "product_id": "ETH-USD",
          "price": "1260.01",
          "size": "0.3",
          "side": "BUY",
          "time": "2019-08-14T20:42:27.265Z"
        }
      ]
    }
    ```
    """
    type: CoinbaseAdvancedTradeWSSEventType
    trades: Tuple[_MarketTrades, ...]

    @property
    def iter_field_name(self) -> str:
        return "trades"


# User channel messages
class CoinbaseAdvancedTradeWSSUserFill(PydanticForJsonConfig):
    """
    User channel messages
    https://docs.cloud.coinbase.com/advanced-trade-api/docs/ws-channels#user-channel
    ```json
    {
      "order_id": "XXX",
      "client_order_id": "YYY",
      "cumulative_quantity": "0",
      "leaves_quantity": "0.000994",
      "avg_price": "0",
      "total_fees": "0",
      "status": "OPEN",
      "product_id": "BTC-USD",
      "creation_time": "2022-12-07T19:42:18.719312Z",
      "order_side": "BUY",
      "order_type": "Limit"
    }
    ```
    """
    order_id: str
    client_order_id: str
    cumulative_quantity: str
    leaves_quantity: str
    avg_price: str
    total_fees: str
    status: CoinbaseAdvancedTradeWSSOrderStatus
    product_id: str
    creation_time: str
    order_side: CoinbaseAdvancedTradeWSSOrderMakerSide
    order_type: CoinbaseAdvancedTradeWSSOrderType


class CoinbaseAdvancedTradeUserEventMessage(
    PydanticMockableForJson,
    CoinbaseAdvancedTradeEventMessage,
    DataIterableMixin[CoinbaseAdvancedTradeWSSUserFill]
):
    """
    User channel messages
    https://docs.cloud.coinbase.com/advanced-trade-api/docs/ws-channels#user-channel
    ```json
    {
        "type": "snapshot",
        "orders":
        [
            {
              "order_id": "XXX",
              "client_order_id": "YYY",
              "cumulative_quantity": "0",
              "leaves_quantity": "0.000994",
              "avg_price": "0",
              "total_fees": "0",
              "status": "OPEN",
              "product_id": "BTC-USD",
              "creation_time": "2022-12-07T19:42:18.719312Z",
              "order_side": "BUY",
              "order_type": "Limit"
            }
        ]
    }
    ```
    """
    type: CoinbaseAdvancedTradeWSSEventType
    orders: Tuple[CoinbaseAdvancedTradeWSSUserFill, ...]

    @property
    def iter_field_name(self) -> str:
        return "orders"


# Status channel messages
class _StatusProduct(PydanticForJsonConfig):
    """
    Status channel messages
    https://docs.cloud.coinbase.com/advanced-trade-api/docs/ws-channels#status-channel
    ```json
    {
      "product_type": "SPOT",
      "id": "BTC-USD",
      "base_currency": "BTC",
      "quote_currency": "USD",
      "base_increment": "0.00000001",
      "quote_increment": "0.01",
      "display_name": "BTC/USD",
      "status": "online",
      "status_message": "",
      "min_market_funds": "1"
    }
    ```
    """
    product_type: CoinbaseAdvancedTradeWSSProductType
    id: str
    base_currency: str
    quote_currency: str
    base_increment: str
    quote_increment: str
    display_name: str
    status: str
    status_message: str
    min_market_funds: str


class CoinbaseAdvancedTradeStatusEventMessage(
    PydanticMockableForJson,
    CoinbaseAdvancedTradeEventMessage,
    DataIterableMixin[_StatusProduct]
):
    """
    Status channel messages
    https://docs.cloud.coinbase.com/advanced-trade-api/docs/ws-channels#status-channel
    ```json
    {
        "type": "snapshot",
        "products":
        [
            {
              "product_type": "SPOT",
              "id": "BTC-USD",
              "base_currency": "BTC",
              "quote_currency": "USD",
              "base_increment": "0.00000001",
              "quote_increment": "0.01",
              "display_name": "BTC/USD",
              "status": "online",
              "status_message": "",
              "min_market_funds": "1"
            }
        ]
    }
    ```
    """
    type: CoinbaseAdvancedTradeWSSEventType
    products: Tuple[_StatusProduct, ...]

    @property
    def iter_field_name(self) -> str:
        return "products"


# Ticker channel messages
class _Ticker(PydanticForJsonConfig):
    """
    Ticker channel messages
    https://docs.cloud.coinbase.com/advanced-trade-api/docs/ws-channels#ticker-channel
    ```json
    {
      "type": "ticker",
      "product_id": "BTC-USD",
      "price": "21932.98",
      "volume_24_h": "16038.28770938",
      "low_24_h": "21835.29",
      "high_24_h": "23011.18",
      "low_52_w": "15460",
      "high_52_w": "48240",
      "price_percent_chg_24_h": "-4.15775596190603"
    }
    ```
    """
    type: str
    product_id: str
    price: str
    volume_24_h: str
    low_24_h: str
    high_24_h: str
    low_52_w: str
    high_52_w: str
    price_percent_chg_24_h: str


class CoinbaseAdvancedTradeTickerEventMessage(
    PydanticMockableForJson,
    CoinbaseAdvancedTradeEventMessage,
    DataIterableMixin[_Ticker]
):
    """
    Ticker channel messages
    https://docs.cloud.coinbase.com/advanced-trade-api/docs/ws-channels#ticker-channel
    ```json
    {
        "type": "snapshot",
        "tickers":
        [
            {
                "type": "ticker",
                "product_id": "BTC-USD",
                "price": "21932.98",
                "volume_24_h": "16038.28770938",
                "low_24_h": "21835.29",
                "high_24_h": "23011.18",
                "low_52_w": "15460",
                "high_52_w": "48240",
                "price_percent_chg_24_h": "-4.15775596190603"
            }
        ]
    }
    ```
    """
    type: CoinbaseAdvancedTradeWSSEventType
    tickers: Tuple[_Ticker, ...]

    @property
    def iter_field_name(self) -> str:
        return "tickers"


# Level2 channel messages
class CoinbaseAdvancedTradeWSSLevel2Update(PydanticForJsonConfig):
    """
    Level2 channel messages
    https://docs.cloud.coinbase.com/advanced-trade-api/docs/ws-channels#level2-channel
    ```json
    {
        "side": "bid",
        "event_time": "1970-01-01T00:00:00Z",
        "price_level": "21921.73",
        "new_quantity": "0.00000000"
    }
    ```
    """
    side: CoinbaseAdvancedTradeWSSOrderBidAskSide
    event_time: str
    price_level: str
    new_quantity: str


class CoinbaseAdvancedTradeLevel2EventMessage(
    PydanticMockableForJson,
    CoinbaseAdvancedTradeEventMessage,
    DataIterableMixin[CoinbaseAdvancedTradeWSSLevel2Update]
):
    """
    Level2 channel messages
    https://docs.cloud.coinbase.com/advanced-trade-api/docs/ws-channels#level2-channel
    ```json
    {
        "type": "snapshot",
        "product_id": "BTC-USD",
        "updates":
        [
            {
                "side": "bid",
                "event_time": "1970-01-01T00:00:00Z",
                "price_level": "21921.73",
                "new_quantity": "0.00000000"
            }
        ]
    }
    ```
    """
    type: CoinbaseAdvancedTradeWSSEventType
    product_id: str
    updates: Tuple[CoinbaseAdvancedTradeWSSLevel2Update, ...]

    @property
    def iter_field_name(self) -> str:
        return "updates"


_EventTypes = Union[
    CoinbaseAdvancedTradeMarketTradesEventMessage,
    CoinbaseAdvancedTradeTickerEventMessage,
    CoinbaseAdvancedTradeLevel2EventMessage,
    CoinbaseAdvancedTradeStatusEventMessage,
    CoinbaseAdvancedTradeUserEventMessage
]


class CoinbaseAdvancedTradeWSSMessage(
    PydanticMockableForJson,
    DataIterableMixin[CoinbaseAdvancedTradeEventMessage]
):
    """
    Coinbase Advanced Trade Websocket API message
    https://docs.cloud.coinbase.com/advanced-trade-api/docs/ws-channels
    ```json
    {
      "channel": "market_trades",
      "client_id": "",
      "timestamp": "2023-02-09T20:19:35.39625135Z",
      "sequence_num": 0,
      "events": [
        ...
      ]
    }
    ```
    """

    class Config:
        arbitrary_types_allowed = True

    channel: CoinbaseAdvancedTradeWSSChannel
    client_id: str
    timestamp: str
    sequence_num: int
    events: Tuple[_EventTypes, ...]

    @property
    def iter_field_name(self) -> str:
        return "events"


class CoinbaseAdvancedTradeWSSMessageSequence:
    def __init__(self, logger: Callable[[], logging.Logger]):
        self.logger: Callable[[], logging.Logger] = logger
        self._last_sequence_num = {event_type: -1 for event_type in CoinbaseAdvancedTradeWSSChannel}

    def validate_sequence(self, message: CoinbaseAdvancedTradeWSSMessage) -> bool:
        last_sequence_num = self._last_sequence_num[message.channel]

        # Verify that the new message sequence number is the expected one
        if message.sequence_num != last_sequence_num + 1:
            self.logger().warning(
                f"Out of order message for {message.channel}. "
                f"Expected {last_sequence_num + 1} but got {message.sequence_num}")
            return False

        # Update the last sequence number for this event type
        self._last_sequence_num[message.channel] = message.sequence_num
        return True
