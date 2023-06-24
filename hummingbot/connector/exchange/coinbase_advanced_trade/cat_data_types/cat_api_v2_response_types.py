from typing import NamedTuple

from hummingbot.connector.exchange.coinbase_advanced_trade.cat_utilities.cat_dict_mockable_from_json_mixin import (
    DictMethodMockableFromJsonDocMixin,
)
from hummingbot.core.utils.class_registry import ClassRegistry


class CoinbaseAdvancedTradeV2ResponseException(Exception):
    pass


class CoinbaseAdvancedTradeV2Response(
    ClassRegistry,
    DictMethodMockableFromJsonDocMixin,
):
    def __init__(self, **kwargs):
        if super().__class__ != object:
            super().__init__(**kwargs)


class _TimeResponse(NamedTuple):
    iso: str
    epoch: int


class CoinbaseAdvancedTradeTimeResponse(NamedTuple, CoinbaseAdvancedTradeV2Response):
    """
    https://docs.cloud.coinbase.com/sign-in-with-coinbase/docs/api-time
    ```json
     {
        "data": {
            "iso": "2015-06-23T18:02:51Z",
            "epoch": 1435082571
        }
    }
    ```
    """
    data: _TimeResponse
