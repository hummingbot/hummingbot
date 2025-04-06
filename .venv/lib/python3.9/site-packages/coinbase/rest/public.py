from typing import Any, Dict, List, Optional

from coinbase.constants import API_PREFIX
from coinbase.rest.types.product_types import (
    GetMarketTradesResponse,
    GetProductBookResponse,
    GetProductCandlesResponse,
    GetProductResponse,
    ListProductsResponse,
)
from coinbase.rest.types.public_types import GetServerTimeResponse


def get_unix_time(self, **kwargs) -> GetServerTimeResponse:
    """
    **Get Server Time**
    _________________
    [GET] https://api.coinbase.com/api/v3/brokerage/time

    __________

    **Description:**

    Get the current time from the Coinbase Advanced API. This is a public endpoint.

    __________

    **Read more on the official documentation:** `Get Server Time <https://docs.cdp.coinbase.com/advanced-trade/reference/retailbrokerageapi_getservertime>`_
    """

    endpoint = f"{API_PREFIX}/time"

    return GetServerTimeResponse(self.get(endpoint, public=True, **kwargs))


def get_public_product_book(
    self,
    product_id: str,
    limit: Optional[int] = None,
    aggregation_price_increment: Optional[str] = None,
    **kwargs,
) -> GetProductBookResponse:
    """
    **Get Public Product Book**
    _________________
    [GET] https://api.coinbase.com/api/v3/brokerage/market/product_book

    __________

    **Description:**

    Get a list of bids/asks for a single product. The amount of detail shown can be customized with the limit parameter.

    __________

    **API Key Permissions:**

    This endpoint is public and does not need authentication.

    __________

    **Read more on the official documentation:** `Get Public Product Book <https://docs.cdp.coinbase.com/advanced-trade/reference/retailbrokerageapi_getpublicproductbook>`_
    """

    endpoint = f"{API_PREFIX}/market/product_book"

    params = {
        "product_id": product_id,
        "limit": limit,
        "aggregation_price_increment": aggregation_price_increment,
    }

    return GetProductBookResponse(
        self.get(endpoint, params=params, public=True, **kwargs)
    )


def get_public_products(
    self,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    product_type: Optional[str] = None,
    product_ids: Optional[List[str]] = None,
    contract_expiry_type: Optional[str] = None,
    expiring_contract_status: Optional[str] = None,
    get_all_products: bool = False,
    **kwargs,
) -> ListProductsResponse:
    """
    **List Public Products**
    _________________

    [GET] https://api.coinbase.com/api/v3/brokerage/market/products

    __________

    **Description:**

    Get a list of the available currency pairs for trading.

    __________

    **API Key Permissions:**

    This endpoint is public and does not need authentication.

    __________

    **Read more on the official documentation:** `List Public Products
    <https://docs.cdp.coinbase.com/advanced-trade/reference/retailbrokerageapi_getpublicproducts>`_
    """
    endpoint = f"{API_PREFIX}/market/products"

    params = {
        "limit": limit,
        "offset": offset,
        "product_type": product_type,
        "product_ids": product_ids,
        "contract_expiry_type": contract_expiry_type,
        "expiring_contract_status": expiring_contract_status,
        "get_all_products": get_all_products,
    }

    return ListProductsResponse(
        self.get(endpoint, params=params, public=True, **kwargs)
    )


def get_public_product(self, product_id: str, **kwargs) -> GetProductResponse:
    """
    **Public Get Product**
    _______________

    [GET] https://api.coinbase.com/api/v3/brokerage/market/products/{product_id}

    __________

    **Description:**

    Get information on a single product by product ID.

    __________

    **API Key Permissions:**

    This endpoint is public and does not need authentication.

    __________

    **Read more on the official documentation:** `Get Public Product
    <https://docs.cdp.coinbase.com/advanced-trade/reference/retailbrokerageapi_getpublicproduct>`_
    """
    endpoint = f"{API_PREFIX}/market/products/{product_id}"

    return GetProductResponse(self.get(endpoint, public=True, **kwargs))


def get_public_candles(
    self,
    product_id: str,
    start: str,
    end: str,
    granularity: str,
    limit: Optional[int] = None,
    **kwargs,
) -> GetProductCandlesResponse:
    """
    **Get Public Product Candles**
    __________

    [GET] https://api.coinbase.com/api/v3/brokerage/market/products/{product_id}/candles

    __________

    **Description:**

    Get rates for a single product by product ID, grouped in buckets.

    __________

    **API Key Permissions:**

    This endpoint is public and does not need authentication.

    __________

    **Read more on the official documentation:** `Get Public Product Candles
    <https://docs.cdp.coinbase.com/advanced-trade/reference/retailbrokerageapi_getpubliccandles>`_
    """
    endpoint = f"{API_PREFIX}/market/products/{product_id}/candles"

    params = {"start": start, "end": end, "granularity": granularity, "limit": limit}

    return GetProductCandlesResponse(
        self.get(endpoint, params=params, public=True, **kwargs)
    )


def get_public_market_trades(
    self,
    product_id: str,
    limit: int,
    start: Optional[str] = None,
    end: Optional[str] = None,
    **kwargs,
) -> GetMarketTradesResponse:
    """
    **Get Public Market Trades**
    _____________________

    [GET] https://api.coinbase.com/api/v3/brokerage/market/products/{product_id}/ticker

    __________

    **Description:**

    Get snapshot information, by product ID, about the last trades (ticks), best bid/ask, and 24h volume.

    __________

    **API Key Permissions:**

    This endpoint is public and does not need authentication.

    __________

    **Read more on the official documentation:** `Get Public Market Trades
    <https://docs.cdp.coinbase.com/advanced-trade/reference/retailbrokerageapi_getpublicmarkettrades>`_
    """
    endpoint = f"{API_PREFIX}/market/products/{product_id}/ticker"

    params = {"limit": limit, "start": start, "end": end}

    return GetMarketTradesResponse(
        self.get(endpoint, params=params, public=True, **kwargs)
    )
