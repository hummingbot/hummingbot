from typing import Any, Dict, List, Optional

from coinbase.rest.types.base_response import BaseResponse
from coinbase.rest.types.common_types import Amount


# Get Account
class GetAccountResponse(BaseResponse):
    def __init__(self, response: dict):
        if "account" in response:
            self.account: Optional[Account] = Account(**(response.pop("account")))
        super().__init__(**response)


# List Accounts
class ListAccountsResponse(BaseResponse):
    def __init__(self, response: dict):
        if "accounts" in response:
            self.accounts: Optional[List[Account]] = [
                Account(**account) for account in response.pop("accounts")
            ]
        if "has_next" in response:
            self.has_next: Optional[bool] = response.pop("has_next")
        if "cursor" in response:
            self.cursor: Optional[str] = response.pop("cursor")
        if "size" in response:
            self.size: Optional[int] = response.pop("size")
        super().__init__(**response)


# ----------------------------------------------------------------


class Account(BaseResponse):
    def __init__(self, **kwargs):
        if "uuid" in kwargs:
            self.uuid: Optional[str] = kwargs.pop("uuid")
        if "name" in kwargs:
            self.name: Optional[str] = kwargs.pop("name")
        if "currency" in kwargs:
            self.currency: Optional[str] = kwargs.pop("currency")
        if "available_balance" in kwargs:
            self.available_balance: Optional[Amount] = kwargs.pop("available_balance")
        if "default" in kwargs:
            self.default: Optional[bool] = kwargs.pop("default")
        if "active" in kwargs:
            self.active: Optional[bool] = kwargs.pop("active")
        if "created_at" in kwargs:
            self.created_at: Optional[str] = kwargs.pop("created_at")
        if "updated_at" in kwargs:
            self.updated_at: Optional[str] = kwargs.pop("updated_at")
        if "deleted_at" in kwargs:
            self.deleted_at: Optional[str] = kwargs.pop("deleted_at")
        if "type" in kwargs:
            self.type: Optional[str] = kwargs.pop("type")
        if "ready" in kwargs:
            self.ready: Optional[bool] = kwargs.pop("ready")
        if "hold" in kwargs:
            self.hold: Optional[Dict[str, Any]] = kwargs.pop("hold")
        if "retail_portfolio_id" in kwargs:
            self.retail_portfolio_id: Optional[str] = kwargs.pop("retail_portfolio_id")
        if "platform" in kwargs:
            self.platform: Optional[str] = kwargs.pop("platform")
        super().__init__(**kwargs)
