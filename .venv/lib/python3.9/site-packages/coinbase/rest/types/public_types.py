from typing import Optional

from coinbase.rest.types.base_response import BaseResponse


# Get Server Time Response
class GetServerTimeResponse(BaseResponse):
    def __init__(self, response: dict):
        if "iso" in response:
            self.iso: Optional[str] = response.pop("iso")
        if "epochSeconds" in response:
            self.epoch_seconds: Optional[int] = response.pop("epochSeconds")
        if "epochMillis" in response:
            self.epoch_millis: Optional[int] = response.pop("epochMillis")
        super().__init__(**response)
