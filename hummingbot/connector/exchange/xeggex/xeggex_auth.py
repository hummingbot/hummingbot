import hashlib
import hmac
import json
import logging
from typing import Any, Dict

from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.logger import HummingbotLogger

ctce_logger = None


class XeggexAuth():
    """
    Auth class required by Xeggex API
    Learn more at https://exchange-docs.crypto.com/#digital-signature
    """

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global ctce_logger
        if ctce_logger is None:
            ctce_logger = logging.getLogger(__name__)
        return ctce_logger

    def __init__(self, api_key: str, secret_key: str, time_provider: TimeSynchronizer):
        self.api_key = api_key
        self.secret_key = secret_key
        self.time_provider = time_provider

    def generate_signature(
        self,
        method: str,
        url: str,
        nonce: int,
        params: Dict[str, Any] = None,
    ):
        """
        Generates authentication payload and returns it.
        :return: A base64 encoded payload for the authentication header.
        """
        # Nonce is standard EPOCH timestamp only accurate to 1s
        noncestr = str(nonce)
        body = ""
        # Need to build the full URL with query string for HS256 sig
        if params is not None and len(params) > 0:
            if method == "GET":
                query_string = "&".join([f"{k}={v}" for k, v in params.items()])
                url = f"{url}?{query_string}"
            else:
                body_json = {}
                for k, v in params.items():
                    body_json[k] = v
                body = json.dumps(body_json, separators=(',', ':'))
        # Concat payload
        self.logger().info(f"Test Body {method}-{self.api_key}-{url}-{body}-{noncestr}")
        payload = f"{self.api_key}{url}{body}{noncestr}"
        # Create HS256 sig
        sig = hmac.new(self.secret_key.encode(), payload.encode(), hashlib.sha256).hexdigest()
        return sig

    def generate_auth_dict_ws(self,
                              nonce: int):
        """
        Generates an authentication params for Xeggex websockets login
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
        Generates authentication headers required by Xeggex
        :return: a dictionary of auth headers
        """
        nonce = int(self.time_provider.time() * 1e3)
        signature = self.generate_signature(method, url, nonce, params)
        headers = {
            "Content-Type": "application/json",
            "X-API-KEY": str(self.api_key),
            "X-API-NONCE": str(nonce),
            "X-API-SIGN": signature
        }
        return headers
