import hmac
import hashlib
import time
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

    def generate_payload(
        self,
        method: str,
        url: str,
        params: Dict[str, Any] = None,
    ):
        """
        Generates authentication payload and returns it.
        :return: A base64 encoded payload for the authentication header.
        """
        # Nonce is standard EPOCH timestamp only accurate to 1s
        nonce = str(int(time.time()))
        body = ""
        # Need to build the full URL with query string for HS256 sig
        if params is not None and len(params) > 0:
            query_string = "&".join([f"{k}={v}" for k, v in params.items()])
            if method == "GET":
                url = f"{url}?{query_string}"
            else:
                body = query_string
        # Concat payload
        payload = f"{method}{nonce}{url}{body}"
        # Create HS256 sig
        sig = hmac.new(self.secret_key.encode(), payload.encode(), hashlib.sha256).hexdigest()
        # Base64 encode it with public key and nonce
        return b64encode(f"{self.api_key}:{nonce}:{sig}".encode()).decode().strip()

    def generate_auth_dict_ws(self,
                              nonce: int):
        """
        Generates an authentication params for HitBTC websockets login
        :return: a dictionary of auth params
        """
        return {
            "algo": "HS256",
            "pKey": str(self.api_key),
            "nonce": str(nonce),
            "signature": hmac.new(self.secret_key.encode('utf-8'),
                                  str(nonce).encode('utf-8'),
                                  hashlib.sha256).hexdigest()
        }

    def get_headers(self,
                    method,
                    url,
                    params) -> Dict[str, Any]:
        """
        Generates authentication headers required by HitBTC
        :return: a dictionary of auth headers
        """
        payload = self.generate_payload(method, url, params)
        headers = {
            "Authorization": f"HS256 {payload}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        return headers
