import base64
from datetime import datetime
import hashlib
import hmac
from typing import (
    Any,
    Dict
)
from urllib.parse import urlencode
from collections import OrderedDict

HUOBI_HOST_NAME = "api.huobi.pro"


class HuobiAuth:
    def __init__(self, api_key: str, secret_key: str):
        self.api_key: str = api_key
        self.hostname: str = HUOBI_HOST_NAME
        self.secret_key: str = secret_key

    @staticmethod
    def keysort(dictionary: Dict[str, str]) -> Dict[str, str]:
        return OrderedDict(sorted(dictionary.items(), key=lambda t: t[0]))

    def add_auth_to_params(self,
                           method: str,
                           path_url: str,
                           params: Dict[str, Any] = None,
                           is_ws: bool = False) -> Dict[str, Any]:
        timestamp: str = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")

        if not params:
            params = {}

        if is_ws:
            params.update({
                "accessKey": self.api_key,
                "signatureMethod": "HmacSHA256",
                "signatureVersion": "2.1",
                "timestamp": timestamp
            })
        else:
            params.update({
                "AccessKeyId": self.api_key,
                "SignatureMethod": "HmacSHA256",
                "SignatureVersion": "2",
                "Timestamp": timestamp
            })

        sorted_params = self.keysort(params)
        signature = self.generate_signature(method=method,
                                            path_url=path_url,
                                            params=sorted_params,
                                            is_ws=is_ws)

        if is_ws:
            sorted_params["signature"] = signature
        else:
            sorted_params["Signature"] = signature
        return sorted_params

    def generate_signature(self,
                           method: str,
                           path_url: str,
                           params: Dict[str, Any],
                           is_ws: bool = False) -> str:

        query_endpoint = f"/v1{path_url}" if not is_ws else path_url
        encoded_params_str = urlencode(params)
        payload = "\n".join([method.upper(), self.hostname, query_endpoint, encoded_params_str])
        digest = hmac.new(self.secret_key.encode("utf8"), payload.encode("utf8"), hashlib.sha256).digest()
        signature_b64 = base64.b64encode(digest).decode()

        return signature_b64
