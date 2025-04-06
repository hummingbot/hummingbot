from typing import Optional

from coinbase.rest.types.base_response import BaseResponse


# Get API Key Permissions
class GetAPIKeyPermissionsResponse(BaseResponse):
    def __init__(self, response: dict):
        if "can_view" in response:
            self.can_view: Optional[bool] = response.pop("can_view")
        if "can_trade" in response:
            self.can_trade: Optional[bool] = response.pop("can_trade")
        if "can_transfer" in response:
            self.can_transfer: Optional[bool] = response.pop("can_transfer")
        if "portfolio_uuid" in response:
            self.portfolio_uuid: Optional[str] = response.pop("portfolio_uuid")
        if "portfolio_type" in response:
            self.portfolio_type: Optional[str] = response.pop("portfolio_type")
        super().__init__(**response)
