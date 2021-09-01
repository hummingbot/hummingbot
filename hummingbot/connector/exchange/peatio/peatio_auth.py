from datetime import datetime
import hashlib
import hmac
from typing import (
    Any,
    Dict
)


class PeatioAuth:
    def __init__(self, access_key: str, secret_key: str):
        self.access_key: str = access_key
        self.secret_key: str = secret_key

    def add_auth_to_headers(self, headers: Dict[str, Any] = None, is_ws: bool = False) -> Dict[str, Any]:
        nonce = str(datetime.now().timestamp() * 1000).split('.')[0]

        if not headers:
            headers = {}

        if is_ws:
            headers.update({
                "X-Auth-Apikey": self.access_key,
                "X-Auth-Nonce": nonce,
                "X-Auth-Signature": self.generate_x_auth_signature(nonce),
            })
        else:
            headers.update({
                "X-Auth-Apikey": self.access_key,
                "X-Auth-Nonce": nonce,
                "X-Auth-Signature": self.generate_x_auth_signature(nonce),
            })

        return headers

    def generate_x_auth_signature(self, nonce: str):
        return hmac.new(self.secret_key.encode('utf-8'), (nonce + self.access_key).encode('utf-8'), hashlib.sha256).hexdigest()
