import hmac
import hashlib
import time
from typing import Dict, Any


class GateIoAuth():
    """
    Auth class required by Gate.io API
    Learn more at https://exchange-docs.crypto.com/#digital-signature
    """
    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key
        self.nonce = None

    def generate_payload(
        self,
        method: str,
        url: str,
        params: Dict[str, Any] = None,
        post_params: str = None,
    ):
        """
        Generates authentication payload and returns it.
        :return: A base64 encoded payload for the authentication header.
        """
        # Nonce is standard EPOCH timestamp only accurate to 1s
        self.nonce = str(int(time.time()))
        body = ""
        query_string = ""
        # Need to build the full URL with query string for HS256 sig
        if params is not None and len(params) > 0 and method == "GET":
            query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        elif post_params is not None:
            body = post_params
        body_encoded = hashlib.sha512(body.encode()).hexdigest()
        # Concat payload
        payload = f"{method}\n{url}\n{query_string}\n{body_encoded}\n{self.nonce}"
        # Create HS256 sig
        return hmac.new(self.secret_key.encode(), payload.encode(), hashlib.sha512).hexdigest()

    def generate_auth_dict_ws(self,
                              nonce: int):
        """
        Generates an authentication params for Gate.io websockets login
        :return: a dictionary of auth params
        """
        return {
            "algo": "HS256",
            "pKey": str(self.api_key),
            "nonce": str(nonce),
            "signature": hmac.new(self.secret_key.encode('utf-8'),
                                  str(nonce).encode('utf-8'),
                                  hashlib.sha512).hexdigest()
        }

    def get_headers(self,
                    method,
                    url,
                    params,
                    post_params = None) -> Dict[str, Any]:
        """
        Generates authentication headers required by Gate.io
        :return: a dictionary of auth headers
        """
        payload = self.generate_payload(method, url, params, post_params)
        headers = {
            "X-Gate-Channel-Id": "hummingbot",
            "KEY": f"{self.api_key}",
            "Timestamp": f"{self.nonce}",
            "SIGN": f"{payload}",
            "Content-Type": "application/json",
        }
        return headers
