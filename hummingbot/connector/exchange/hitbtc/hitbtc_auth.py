import hmac
import hashlib
import time
import ujson
from base64 import b64encode
from typing import Dict, Any


class HitbtcAuth():
    """
    Auth class required by HitBTC API
    Learn more at https://exchange-docs.crypto.com/#digital-signature
    """
    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key

    def generate_auth(
        self,
        method: str,
        url: str,
        params: Dict[str, Any] = None
    ):
        """
        Generates authentication signature and return it with the nonce used
        :return: a tuple of the nonce used and the request signature
        """
        nonce = str(int(time.time()))
        full_url = f"{url}"
        body = ""
        if params is not None and len(params) > 0 and method.upper() == "GET":
            query_string = "&".join([f"{k}={v}" for k, v in params.items()])
            full_url = f"{url}?{query_string}"
        elif params is not None and len(params) > 0 and method.upper() == "POST":
            body = ujson.dumps(params)
        payload = f"{method.upper()}{nonce}{full_url}{body}"

        sig = hmac.new(
            self.secret_key.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()

        return (nonce, sig)

    def generate_auth_dict_ws(self,
                              nonce: int):
        data = {
            "algo": "HS256",
            "pKey": self.api_key,
            "nonce": nonce,
        }
        data['signature'] = hmac.new(
            self.secret_key.encode('utf-8'),
            str(nonce).encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return data

    def get_headers(self,
                    method,
                    url,
                    params) -> Dict[str, Any]:
        """
        Generates authentication headers required by HitBTC
        :return: a dictionary of auth headers
        """
        nonce, sig = self.generate_auth(method, url, params)
        payload = b64encode(f"{self.api_key}:{nonce}:{sig}".encode()).decode().strip()
        headers = {
            "Authorization": f"HS256 {payload}"
        }
        if params is not None and len(params) > 0:
            headers["Content-Type"] = "application/json"
        return headers
