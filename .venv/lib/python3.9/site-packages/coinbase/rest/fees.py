from typing import Any, Dict, Optional

from coinbase.constants import API_PREFIX
from coinbase.rest.types.fees_types import GetTransactionSummaryResponse


def get_transaction_summary(
    self,
    product_type: Optional[str] = None,
    contract_expiry_type: Optional[str] = None,
    product_venue: Optional[str] = None,
    **kwargs,
) -> GetTransactionSummaryResponse:
    """
    **Get Transactions Summary**
    _____________________________

    [GET] https://api.coinbase.com/api/v3/brokerage/transaction_summary

    __________

    **Description:**

    Get a summary of transactions with fee tiers, total volume, and fees.

    __________

    **Read more on the official documentation:** `Create Convert Quote <https://docs.cdp.coinbase.com/advanced-trade/reference/retailbrokerageapi_createconvertquote>`_
    """
    endpoint = f"{API_PREFIX}/transaction_summary"

    params = {
        "product_type": product_type,
        "contract_expiry_type": contract_expiry_type,
        "product_venue": product_venue,
    }

    return GetTransactionSummaryResponse(self.get(endpoint, params=params, **kwargs))
