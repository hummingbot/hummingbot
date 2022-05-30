import hashlib
import hmac
import json
from typing import Any, Dict


class BitmartAuth():
    """
    Auth class required by BitMart API
    Learn more at https://developer-pro.bitmart.com/en/part2/auth.html
    """
    def __init__(self, api_key: str, secret_key: str, memo: str):
        self.api_key = api_key
        self.secret_key = secret_key
        self.memo = memo

    def get_headers(
        self,
        timestamp: int = None,
        params: Dict[str, Any] = None,
        auth_type: str = None
    ):
        """
        Generates context appropriate headers({SIGNED, KEYED, None}) for the request.
        :return: a dictionary of auth headers
        """

        if auth_type == "SIGNED":

            params = json.dumps(params)
            payload = f'{str(timestamp)}#{self.memo}#{params}'

            sign = hmac.new(
                self.secret_key.encode('utf-8'),
                payload.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()

            return {
                "Content-Type": 'application/json',
                "X-BM-KEY": self.api_key,
                "X-BM-SIGN": sign,
                "X-BM-TIMESTAMP": str(timestamp),
            }

        elif auth_type == "KEYED":
            return {
                "Content-Type": 'application/json',
                "X-BM-KEY": self.api_key,
            }

        else:
            return {
                "Content-Type": 'application/json',
            }

    def get_ws_auth_payload(self, timestamp: int = None):
        """
        Generates websocket payload.
        :return: a dictionary of auth headers with api_key, timestamp, signature
        """

        payload = f'{str(timestamp)}#{self.memo}#bitmart.WebSocket'

        sign = hmac.new(
            self.secret_key.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        return {
            "op": "login",
            "args": [
                self.api_key,
                str(timestamp),
                sign
            ]
        }
