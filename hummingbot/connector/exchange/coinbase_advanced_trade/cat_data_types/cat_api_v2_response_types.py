from typing import NamedTuple


class _TimeResponse(NamedTuple):
    iso: str
    epoch: int


class CoinbaseAdvancedTradeTimeResponse(NamedTuple):
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
