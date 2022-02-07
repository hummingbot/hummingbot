import base64
import hashlib
import hmac
import time
from typing import Dict

from hummingbot.connector.exchange.coinbase_pro import coinbase_pro_constants as CONSTANTS
from hummingbot.connector.exchange.coinbase_pro.coinbase_pro_utils import CoinbaseProRESTRequest
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class CoinbaseProAuth(AuthBase):
    """
    Auth class required by Coinbase Pro API
    Learn more at https://docs.pro.coinbase.com/?python#signing-a-message
    """
    def __init__(self, api_key: str, secret_key: str, passphrase: str):
        self.api_key = api_key
        self.secret_key = secret_key
        self.passphrase = passphrase

    async def rest_authenticate(self, request: CoinbaseProRESTRequest) -> RESTRequest:
        request.headers = self._get_headers(
            method_str=request.method.value, path_url=request.endpoint, body=request.data
        )
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        auth_dict = self._generate_auth_dict("GET", CONSTANTS.VERIFY_PATH_URL, "")
        request.payload.update(auth_dict)
        return request

    def _get_headers(self, method_str: str, path_url: str, body: str = "") -> Dict[str, any]:
        """
        Generates authentication headers required by coinbase
        :param method_str: GET / POST / etc.
        :param path_url: e.g. "/accounts"
        :param body: request payload
        :return: a dictionary of auth headers
        """
        header_dict = self._generate_auth_dict(method_str, path_url, body)
        return {
            "CB-ACCESS-SIGN": header_dict["signature"],
            "CB-ACCESS-TIMESTAMP": header_dict["timestamp"],
            "CB-ACCESS-KEY": header_dict["key"],
            "CB-ACCESS-PASSPHRASE": header_dict["passphrase"],
            "Content-Type": 'application/json',
        }

    def _generate_auth_dict(self, method_str: str, path_url: str, body: str = "") -> Dict[str, any]:
        """
        Generates authentication signature and return it in a dictionary along with other inputs
        :return: a dictionary of request info including the request signature
        """
        timestamp = str(time.time())
        message = timestamp + method_str + path_url + body
        hmac_key = base64.b64decode(self.secret_key)
        signature = hmac.new(hmac_key, message.encode('utf8'), hashlib.sha256)
        signature_b64 = base64.b64encode(bytes(signature.digest())).decode('utf8')

        return {
            "signature": signature_b64,
            "timestamp": timestamp,
            "key": self.api_key,
            "passphrase": self.passphrase,
        }
