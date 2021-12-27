import hashlib
import hmac

from datetime import time
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

    def add_auth_to_params(self,
                           params: Dict[str, Any] = None):
        timestamp = int(self._time() * 1000)

        if not params:
            params = {}

        params.update({"timestamp": timestamp})

        # sorted_params = self.keysort(params)
        # signature = self.generate_signature(method=method,
        #                                    path_url=path_url,
        #                                    params=sorted_params)
        # sorted_params["signature"] = signature
        signature = self._generate_signature(params=params)
        params["signature"] = signature

        return params

    def _generate_signature(self, params: Dict[str, Any]) -> str:

        encoded_params_str = urlencode(params)
        digest = hmac.new(self.secret_key.encode("utf8"), encoded_params_str.encode("utf8"), hashlib.sha256).hexdigest()
        return digest

    def _time(self):
        # This method is added just to make it possible to have deterministic results in test cases
        return time.time()
