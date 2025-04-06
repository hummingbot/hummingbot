from typing import Any, Dict, Optional

from coinbase.constants import API_PREFIX
from coinbase.rest.types.data_api_types import GetAPIKeyPermissionsResponse


def get_api_key_permissions(
    self,
    **kwargs,
) -> GetAPIKeyPermissionsResponse:
    """
    **Get Api Key Permissions**
    _____________________________

    [GET] https://api.coinbase.com/api/v3/brokerage/key_permissions

    __________

    **Description:**

    Get information about your CDP API key permissions

    __________

    **Read more on the official documentation:** `Create Convert Quote <https://docs.cdp.coinbase.com/advanced-trade/reference/retailbrokerageapi_getapikeypermissions>`_
    """
    endpoint = f"{API_PREFIX}/key_permissions"

    return GetAPIKeyPermissionsResponse(self.get(endpoint, **kwargs))
