import base64
import hashlib
import hmac
import time
from typing import (
    Any,
    Dict
)
from urllib.parse import urlencode


class ExmarketsAuth:
    def __init__(self, api_key: str, secret_key: str):
        self.api_key: str = api_key
        self.secret_key: str = secret_key

    def make_nonce(self) -> int:
        nonce = int(round(time.time() * 100000))
        return nonce

    def make_timestamp(self) -> int:
        timestamp = int(round(time.time())) + 6
        return timestamp

    def generate_headers(self,
                         method: str,
                         path_url: str,
                         args: Dict[str, Any] = None) -> Dict[str, Any]:
        query_string = urlencode(args)
        signature = hmac.new(self.secret_key.encode("utf8"), query_string.encode("utf8"), hashlib.sha512)
        signature_b64 = base64.b64encode(self.api_key.encode("utf8") + ":" + signature.digest()).decode("utf8")

        return {
            "Authorization": "Basic " + signature_b64
        }
