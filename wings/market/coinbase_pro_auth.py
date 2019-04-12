import time
import hmac
import hashlib
import base64
from typing import Dict


class CoinbaseProAuth:
    def __init__(self, api_key, secret_key, passphrase):
        self.api_key = api_key
        self.secret_key = secret_key
        self.passphrase = passphrase

    def generate_auth_dict(self, method: str, path_url: str, body: str = "") -> Dict[str, any]:
        timestamp = str(time.time())
        message = timestamp + method.upper() + path_url + body
        hmac_key = base64.b64decode(self.secret_key)
        signature = hmac.new(hmac_key, message.encode('utf8'), hashlib.sha256)
        signature_b64 = base64.b64encode(bytes(signature.digest())).decode('utf8')

        return {
            'signature': signature_b64,
            'timestamp': timestamp,
            'key': self.api_key,
            'passphrase': self.passphrase,
        }

    def get_headers(self, method: str, path_url: str, body: str = "") -> Dict[str, any]:
        header_dict = self.generate_auth_dict(method, path_url, body)
        return {
            'CB-ACCESS-SIGN': header_dict["signature"],
            'CB-ACCESS-TIMESTAMP': header_dict["timestamp"],
            'CB-ACCESS-KEY': header_dict["key"],
            'CB-ACCESS-PASSPHRASE': header_dict["passphrase"],
            'Content-Type': 'application/json',
        }
