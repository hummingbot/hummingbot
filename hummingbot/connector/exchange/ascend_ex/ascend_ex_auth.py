import hmac
import hashlib
from typing import Dict, Any
from hummingbot.connector.exchange.ascend_ex.ascend_ex_utils import get_ms_timestamp


class AscendExAuth:
    """
    Auth class required by AscendEx API
    Learn more at https://ascendex.github.io/ascendex-pro-api/#authenticate-a-restful-request
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

    @staticmethod
    def get_headers() -> Dict[str, Any]:
        """
        Generates generic headers required by AscendEx
        :return: a dictionary of headers
        """

        return {
            "Accept": "application/json",
            "Content-Type": 'application/json',
        }

    @staticmethod
    def get_hb_id_headers() -> Dict[str, Any]:
        """Headers signature to identify user as an HB liquidity provider."""
        return {
            "request-source": "hummingbot-liq-mining",
        }
