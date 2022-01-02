import hashlib
import hmac
import time
from collections import OrderedDict

from typing import (
    Any,
    Dict
)
from urllib.parse import urlencode


class BinanceAuth:
    def __init__(self, api_key: str, secret_key: str):
        self.api_key: str = api_key
        self.secret_key: str = secret_key

    # @staticmethod
    # def keysort(dictionary: Dict[str, str]) -> Dict[str, str]:
    #    return OrderedDict(sorted(dictionary.items(), key=lambda t: t[0]))

    def get_headers(self, request_type: str) -> Dict[str, Any]:
        """
        Generates authentication headers required by ProBit
        :return: a dictionary of auth headers
        """
        content_type = "application/json" if request_type == "post" else "application/x-www-form-urlencoded"
        return {
            "Content-Type": content_type,
        }

    def get_auth_headers(self, request_type: str) -> Dict[str, Any]:
        headers = self.get_headers(request_type=request_type)
        headers["X-MBX-APIKEY"] = self.api_key
        return headers

    def add_auth_to_params(self,
                           params: Dict[str, Any],
                           current_time: float):
        timestamp = int(current_time * 1e3)

        request_params = OrderedDict(params or {})
        request_params["timestamp"] = timestamp

        signature = self._generate_signature(params=request_params)
        request_params["signature"] = signature

        return request_params

    def _generate_signature(self, params: Dict[str, Any]) -> str:

        encoded_params_str = urlencode(params)
        digest = hmac.new(self.secret_key.encode("utf8"), encoded_params_str.encode("utf8"), hashlib.sha256).hexdigest()
        return digest

    def _time(self):
        # This method is added just to make it possible to have deterministic results in test cases
        return time.time()
