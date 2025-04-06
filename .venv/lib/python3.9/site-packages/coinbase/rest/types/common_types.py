from typing import Optional

from coinbase.rest.types.base_response import BaseResponse


class Amount(BaseResponse):
    def __init__(self, **kwargs):
        if "value" in kwargs:
            self.value: Optional[str] = kwargs.pop("value")
        if "currency" in kwargs:
            self.currency: Optional[str] = kwargs.pop("currency")
        super().__init__(**kwargs)
