import base64
import time
import hashlib
import hmac
from typing import (
    Any,
    Dict
)
from urllib.parse import urlencode
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
                           args: Dict[str, Any]=None) -> Dict[str, Any]:
        timestamp = int(time.time() * 1000)
        request = {
            "KC-API-KEY": self.api_key,
            "KC-API-PASSPHRASE": self.passphrase,
            "KC-API-TIMESTAMP": str(timestamp)
        }
        if args is not None:
            query_string = json.dumps(args)
        sorted_request = self.keysort(request)
        payload = "\n".join([str(timestamp), method.upper(), "api/v1/" + path_url, query_string])
        signature = hmac.new(self.secret_key.encode("utf8"), payload.encode("utf8"), hashlib.sha256)
        signature_b64 = base64.b64encode(signature.digest())
        sorted_request["KC-API-SIGN"] = signature_b64
        return sorted_request
	