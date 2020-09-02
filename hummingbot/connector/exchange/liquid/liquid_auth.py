import time
import jwt
from typing import Any, Dict

from hummingbot.connector.exchange.liquid.constants import Constants


class LiquidAuth:
    """
    Auth class required by Liquid API
    Learn more at https://developers.liquid.com/?ruby#authentication
    """
    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key

    def generate_signature(self, path_url: str) -> (Dict[str, Any]):
        """
        Generates authentication signature and return it in a dictionary along with other inputs
        :return: a dictionary of request info including the request signature
        """
        auth_payload = {
            'path': path_url,
            'nonce': str(int(time.time() * 1e3)),
            'token_id': self.api_key
        }
        signature = jwt.encode(auth_payload, self.secret_key, 'HS256')

        return signature

    def get_headers(self, path_url: str) -> (Dict[str, Any]):
        signature = self.generate_signature(path_url)
        return {
            "X-Quoine-API-Version": "2",
            "X-Quoine-Auth": signature.decode("utf-8"),
            "Content-Type": "application/json"
        }

    def get_ws_auth_data(self) -> (Dict[str, Any]):
        signature = self.generate_signature(path_url=Constants.WS_REQUEST_PATH)

        return {
            "headers": {
                'X-Quoine-Auth': signature
            },
            "path": Constants.WS_REQUEST_PATH
        }
