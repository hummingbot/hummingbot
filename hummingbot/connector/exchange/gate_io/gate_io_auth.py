import hashlib
import hmac
import time
from typing import Any, Dict

from hummingbot.connector.exchange.gate_io import gate_io_constants as CONSTANTS


class GateIoAuth:
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
        for_ws: bool = False,
    ):
        """
        Generates authentication payload and returns it.
        :return: A base64 encoded payload for the authentication header.
        """
        # Build message payload
        if for_ws:
            payload = f"channel={method}&event={url}&time={params}"
        else:
            # Nonce is standard EPOCH timestamp only accurate to 1s
            self.nonce = str(int(time.time()))
            body, query_string = "", ""
            # Need to build the full URL with query string for HS256 sig
            if params is not None:
                if method == "POST":
                    body = str(params)
                else:
                    query_string = "&".join([f"{k}={v}" for k, v in params.items()]) if isinstance(params, dict) else str(params)
            body_encoded = hashlib.sha512(body.encode()).hexdigest()
            payload = f"{method}\n{url}\n{query_string}\n{body_encoded}\n{self.nonce}"
        # Create HS256 sig
        return hmac.new(self.secret_key.encode(), payload.encode(), hashlib.sha512).hexdigest()

    def generate_auth_dict_ws(self,
                              payload: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Generates an authentication dict for Gate.io websockets login
        :return: a dictionary of auth params
        """
        sig = self.generate_payload(payload['channel'], payload['event'], payload['time'], True)
        headers = {
            "method": "api_key",
            "KEY": f"{self.api_key}",
            "SIGN": f"{sig}",
        }
        return headers

    def get_headers(self,
                    method,
                    url,
                    params = None) -> Dict[str, Any]:
        """
        Generates authentication headers required by Gate.io
        :return: a dictionary of auth headers
        """
        payload = self.generate_payload(method, url, params)
        headers = {
            "X-Gate-Channel-Id": CONSTANTS.HBOT_BROKER_ID,
            "KEY": f"{self.api_key}",
            "Timestamp": f"{self.nonce}",
            "SIGN": f"{payload}",
            "Content-Type": "application/json",
        }
        return headers
