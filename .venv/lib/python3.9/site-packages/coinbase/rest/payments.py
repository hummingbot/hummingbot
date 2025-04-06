from typing import Any, Dict

from coinbase.constants import API_PREFIX
from coinbase.rest.types.payments_types import (
    GetPaymentMethodResponse,
    ListPaymentMethodsResponse,
)


def list_payment_methods(self, **kwargs) -> ListPaymentMethodsResponse:
    """
    **List Payment Methods**
    _________________
    [GET] https://api.coinbase.com/api/v3/brokerage/payment_methods

    __________

    **Description:**

    Get a list of payment methods for the current user.

    __________

    **Read more on the official documentation:** `List Payment Methods <https://docs.cdp.coinbase.com/advanced-trade/reference/retailbrokerageapi_getpaymentmethods>`_
    """

    endpoint = f"{API_PREFIX}/payment_methods"

    return ListPaymentMethodsResponse(self.get(endpoint, **kwargs))


def get_payment_method(
    self, payment_method_id: str, **kwargs
) -> GetPaymentMethodResponse:
    """
    **Get Payment Method**
    _________________
    [GET] https://api.coinbase.com/api/v3/brokerage/payment_methods/{payment_method_id}

    __________

    **Description:**

    Get information about a payment method for the current user.

    __________

    **Read more on the official documentation:** `Get Payment Method <https://docs.cdp.coinbase.com/advanced-trade/reference/retailbrokerageapi_getpaymentmethod>`_
    """

    endpoint = f"{API_PREFIX}/payment_methods/{payment_method_id}"

    return GetPaymentMethodResponse(self.get(endpoint, **kwargs))
