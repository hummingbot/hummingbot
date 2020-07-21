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

# V3 API
HUOBI_HOST_NAME = "api.huobi.pro"

# passphrase = 'zzUEDcbSo8zX5m8kv6Z2S'
# API KEY '00a1ee09-3fed-43d7-937a-c7598799ea28'
# Secret Key 'EA5E1B61B5D881A207D400F42AEC426D'

class OKExAuth:
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
                           args: Dict[str, Any]=None) -> Dict[str, Any]:
        # timestamp: str = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
        request = {
            "AccessKeyId": self.api_key,
            "SignatureMethod": "HmacSHA256",
            "SignatureVersion": "2",
            "Timestamp": timestamp
        }
        if args is not None:
            request.update(args)

        sorted_request = self.keysort(request)
        query_string = urlencode(sorted_request)
        payload = "\n".join([method.upper(), self.hostname, "/v1/" + path_url, query_string])
        
        signature = hmac.new(self.secret_key.encode("utf8"), payload.encode("utf8"), hashlib.sha256)
        signature_b64 = base64.b64encode(signature.digest()).decode("utf8")
        sorted_request["Signature"] = signature_b64
        return sorted_request
