from typing import Any, Dict, Optional

from coinbase.constants import API_PREFIX
from coinbase.rest.types.product_types import (
    GetMarketTradesResponse,
    GetProductCandlesResponse,
)


def get_candles(
    self,
    product_id: str,
    start: str,
    end: str,
    granularity: str,
    limit: Optional[int] = None,
    **kwargs,
) -> GetProductCandlesResponse:
    """
    **Get Product Candles**
    __________

    [GET] https://api.coinbase.com/api/v3/brokerage/products/{product_id}/candles

    __________

    **Description:**

    Get rates for a single product by product ID, grouped in buckets.

    __________

    **Read more on the official documentation:** `Get Product Candles
    <https://docs.cdp.coinbase.com/advanced-trade/reference/retailbrokerageapi_getcandles>`_
    """
    endpoint = f"{API_PREFIX}/products/{product_id}/candles"

    params = {"start": start, "end": end, "granularity": granularity, "limit": limit}

    return GetProductCandlesResponse(self.get(endpoint, params=params, **kwargs))


def get_market_trades(
    self,
    product_id: str,
    limit: int,
    start: Optional[str] = None,
    end: Optional[str] = None,
    **kwargs,
) -> GetMarketTradesResponse:
    """
    **Get Market Trades**
    _____________________

    [GET] https://api.coinbase.com/api/v3/brokerage/products/{product_id}/ticker

    __________

    **Description:**

    Get snapshot information, by product ID, about the last trades (ticks), best bid/ask, and 24h volume.

    __________

    **Read more on the official documentation:** `Get Market Trades
    <https://docs.cdp.coinbase.com/advanced-trade/reference/retailbrokerageapi_getmarkettrades>`_
    """
    endpoint = f"{API_PREFIX}/products/{product_id}/ticker"

    params = {"limit": limit, "start": start, "end": end}

    return GetMarketTradesResponse(self.get(endpoint, params=params, **kwargs))
