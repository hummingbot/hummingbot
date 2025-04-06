from typing import List, Optional

from coinbase.rest.types.base_response import BaseResponse


# List Payment Methods
class ListPaymentMethodsResponse(BaseResponse):
    def __init__(self, response: dict):
        if "payment_methods" in response:
            self.payment_methods: Optional[List[PaymentMethod]] = [
                PaymentMethod(**method) for method in response.pop("payment_methods")
            ]

        super().__init__(**response)


# Get Payment Method
class GetPaymentMethodResponse(BaseResponse):
    def __init__(self, response: dict):
        if "payment_method" in response:
            self.payment_method: Optional[PaymentMethod] = PaymentMethod(
                **response.pop("payment_method")
            )
        super().__init__(**response)


# ----------------------------------------------------------------


class PaymentMethod(BaseResponse):
    def __init__(self, **kwargs):
        if "id" in kwargs:
            self.id: Optional[str] = kwargs.pop("id")
        if "type" in kwargs:
            self.type: Optional[str] = kwargs.pop("type")
        if "name" in kwargs:
            self.name: Optional[str] = kwargs.pop("name")
        if "currency" in kwargs:
            self.currency: Optional[str] = kwargs.pop("currency")
        if "verified" in kwargs:
            self.verified: Optional[bool] = kwargs.pop("verified")
        if "allow_buy" in kwargs:
            self.allow_buy: Optional[bool] = kwargs.pop("allow_buy")
        if "allow_sell" in kwargs:
            self.allow_sell: Optional[bool] = kwargs.pop("allow_sell")
        if "allow_deposit" in kwargs:
            self.allow_deposit: Optional[bool] = kwargs.pop("allow_deposit")
        if "allow_withdraw" in kwargs:
            self.allow_withdraw: Optional[bool] = kwargs.pop("allow_withdraw")
        if "created_at" in kwargs:
            self.created_at: Optional[str] = kwargs.pop("created_at")
        if "updated_at" in kwargs:
            self.updated_at: Optional[str] = kwargs.pop("updated_at")
        super().__init__(**kwargs)
