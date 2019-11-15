import base64
import json
import time
import hashlib
import hmac
from typing import (
    Any,
    Dict
)
from collections import OrderedDict


class KucoinAuth:
    def __init__(self, api_key: str, passphrase: str, secret_key: str):
        self.api_key: str = api_key
        self.passphrase: str = passphrase
        self.secret_key: str = secret_key

    @staticmethod
    def keysort(dictionary: Dict[str, str]) -> Dict[str, str]:
        return OrderedDict(sorted(dictionary.items(), key=lambda t: t[0]))

    def add_auth_to_params(self,
                           method: str,
                           path_url: str,
                           args: Dict[str, Any] = None) -> Dict[str, Any]:
        timestamp = int(time.time() * 1000)
        request = {
            "KC-API-KEY": self.api_key,
            "KC-API-PASSPHRASE": self.passphrase,
            "KC-API-TIMESTAMP": str(timestamp),
            "Content-Type": "application/json"
        }
        if args is not None:
            query_string = json.dumps(args)
            payload = str(timestamp) + method.upper() + path_url + query_string
        else:
            payload = str(timestamp) + method.upper() + path_url
        signature = base64.b64encode(hmac.new(self.secret_key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).digest())
        request["KC-API-SIGN"] = str(signature, "utf-8")
        return request
