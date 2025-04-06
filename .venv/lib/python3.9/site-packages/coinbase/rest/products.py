from typing import Any, Dict, List, Optional

from coinbase.constants import API_PREFIX
from coinbase.rest.types.product_types import (
    GetBestBidAskResponse,
    GetProductBookResponse,
    GetProductResponse,
    ListProductsResponse,
)


def get_products(
    self,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    product_type: Optional[str] = None,
    product_ids: Optional[List[str]] = None,
    contract_expiry_type: Optional[str] = None,
    expiring_contract_status: Optional[str] = None,
    get_tradability_status: Optional[bool] = False,
    get_all_products: Optional[bool] = False,
    **kwargs,
) -> ListProductsResponse:
    """
    **List Products**
    _________________

    [GET] https://api.coinbase.com/api/v3/brokerage/products

    __________

    **Description:**

    Get a list of the available currency pairs for trading.

    __________

    **Read more on the official documentation:** `List Products
    <https://docs.cdp.coinbase.com/advanced-trade/reference/retailbrokerageapi_getproducts>`_
    """
    endpoint = f"{API_PREFIX}/products"

    params = {
        "limit": limit,
        "offset": offset,
        "product_type": product_type,
        "product_ids": product_ids,
        "contract_expiry_type": contract_expiry_type,
        "expiring_contract_status": expiring_contract_status,
        "get_tradability_status": get_tradability_status,
        "get_all_products": get_all_products,
    }

    return ListProductsResponse(self.get(endpoint, params=params, **kwargs))


def get_product(
    self, product_id: str, get_tradability_status: Optional[bool] = False, **kwargs
) -> GetProductResponse:
    """
    **Get Product**
    _______________

    [GET] https://api.coinbase.com/api/v3/brokerage/products/{product_id}

    __________

    **Description:**

    Get information on a single product by product ID.

    __________

    **Read more on the official documentation:** `Get Product
    <https://docs.cdp.coinbase.com/advanced-trade/reference/retailbrokerageapi_getproduct>`_
    """
    endpoint = f"{API_PREFIX}/products/{product_id}"

    params = {
        "get_tradability_status": get_tradability_status,
    }

    return GetProductResponse(self.get(endpoint, params=params, **kwargs))


def get_product_book(
    self,
    product_id: str,
    limit: Optional[int] = None,
    aggregation_price_increment: Optional[str] = None,
    **kwargs,
) -> GetProductBookResponse:
    """
    **Get Product Book**
    ____________________

    [GET] https://api.coinbase.com/api/v3/brokerage/product_book

    __________

    **Description:**

    Get a list of bids/asks for a single product. The amount of detail shown can be customized with the limit parameter.

    __________

    **Read more on the official documentation:** `Get Product Book
    <https://docs.cdp.coinbase.com/advanced-trade/reference/retailbrokerageapi_getproductbook>`_
    """
    endpoint = f"{API_PREFIX}/product_book"

    params = {
        "product_id": product_id,
        "limit": limit,
        "aggregation_price_increment": aggregation_price_increment,
    }

    return GetProductBookResponse(self.get(endpoint, params=params, **kwargs))


def get_best_bid_ask(
    self, product_ids: Optional[List[str]] = None, **kwargs
) -> GetBestBidAskResponse:
    """
    **Get Best Bid/Ask**
    ____________________

    [GET] https://api.coinbase.com/api/v3/brokerage/best_bid_ask

    __________

    **Description:**

    Get the best bid/ask for all products. A subset of all products can be returned instead by using the product_ids input.

    __________

    **Read more on the official documentation:** `Get Best Bid/Ask
    <https://docs.cdp.coinbase.com/advanced-trade/reference/retailbrokerageapi_getproductbook>`_
    """
    endpoint = f"{API_PREFIX}/best_bid_ask"

    params = {
        "product_ids": product_ids,
    }

    return GetBestBidAskResponse(self.get(endpoint, params=params, **kwargs))
