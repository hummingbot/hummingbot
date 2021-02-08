import hmac
import hashlib
from typing import Dict, Any
from hummingbot.connector.exchange.bitmax.bitmax_utils import get_ms_timestamp


class BitmaxAuth():
    """
    Auth class required by bitmax API
    Learn more at https://bitmax-exchange.github.io/bitmax-pro-api/#authenticate-a-restful-request
    """
    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key

    def get_auth_headers(
        self,
        path_url: str,
        data: Dict[str, Any] = None
    ):
        """
        Generates authentication signature and return it in a dictionary along with other inputs
        :return: a dictionary of request info including the request signature
        """

        timestamp = str(get_ms_timestamp())
        message = timestamp + path_url
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        return {
            "x-auth-key": self.api_key,
            "x-auth-signature": signature,
            "x-auth-timestamp": timestamp,
        }

    def get_headers(self) -> Dict[str, Any]:
        """
        Generates generic headers required by bitmax
        :return: a dictionary of headers
        """

        return {
            "Accept": "application/json",
            "Content-Type": 'application/json',
        }
