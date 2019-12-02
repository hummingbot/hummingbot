import time
import hmac
import hashlib
import base64
from typing import Dict


class CoinbaseProAuth:
    """
    Auth class required by Coinbase Pro API
    Learn more at https://docs.pro.coinbase.com/?python#signing-a-message
    """
    def __init__(self, api_key: str, secret_key: str, passphrase: str):
        self.api_key = api_key
        self.secret_key = secret_key
        self.passphrase = passphrase

    def generate_auth_dict(self, method: str, path_url: str, body: str = "") -> Dict[str, any]:
        """
        Generates authentication signature and return it in a dictionary along with other inputs
        :return: a dictionary of request info including the request signature
        """
        timestamp = str(time.time())
        message = timestamp + method.upper() + path_url + body
        hmac_key = base64.b64decode(self.secret_key)
        signature = hmac.new(hmac_key, message.encode('utf8'), hashlib.sha256)
        signature_b64 = base64.b64encode(bytes(signature.digest())).decode('utf8')

        return {
            "signature": signature_b64,
            "timestamp": timestamp,
            "key": self.api_key,
            "passphrase": self.passphrase,
        }

    def get_headers(self, method: str, path_url: str, body: str = "") -> Dict[str, any]:
        """
        Generates authentication headers required by coinbasse
        :param method: GET / POST / etc.
        :param path_url: e.g. "/accounts"
        :param body: request payload
        :return: a dictionary of auth headers
        """
        header_dict = self.generate_auth_dict(method, path_url, body)
        return {
            "CB-ACCESS-SIGN": header_dict["signature"],
            "CB-ACCESS-TIMESTAMP": header_dict["timestamp"],
            "CB-ACCESS-KEY": header_dict["key"],
            "CB-ACCESS-PASSPHRASE": header_dict["passphrase"],
            "Content-Type": 'application/json',
        }
