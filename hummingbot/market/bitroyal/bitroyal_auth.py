import time
import hmac
import hashlib
import base64
from typing import Dict


<<<<<<< HEAD
class bitroyalAuth:
    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key
=======
class CoinbaseProAuth:
    def __init__(self, api_key: str, secret_key: str, passphrase: str):
        self.api_key = api_key
        self.secret_key = secret_key
        self.passphrase = passphrase
>>>>>>> Created bitroyal connector folder and files in hummingbot>market

    def generate_auth_dict(self, method: str, path_url: str, body: str = "") -> Dict[str, any]:
        timestamp = str(time.time())
        message = timestamp + method.upper() + path_url + body
        hmac_key = base64.b64decode(self.secret_key)
<<<<<<< HEAD
        signature = hmac.new(hmac_key, message.encode("utf8"), hashlib.sha256)
        signature_b64 = base64.b64encode(bytes(signature.digest())).decode("utf8")

        return {"signature": signature_b64, "timestamp": timestamp, "key": self.api_key}
=======
        signature = hmac.new(hmac_key, message.encode('utf8'), hashlib.sha256)
        signature_b64 = base64.b64encode(bytes(signature.digest())).decode('utf8')

        return {
            "signature": signature_b64,
            "timestamp": timestamp,
            "key": self.api_key,
            "passphrase": self.passphrase,
        }
>>>>>>> Created bitroyal connector folder and files in hummingbot>market

    def get_headers(self, method: str, path_url: str, body: str = "") -> Dict[str, any]:
        header_dict = self.generate_auth_dict(method, path_url, body)
        return {
            "CB-ACCESS-SIGN": header_dict["signature"],
            "CB-ACCESS-TIMESTAMP": header_dict["timestamp"],
            "CB-ACCESS-KEY": header_dict["key"],
<<<<<<< HEAD
            "Content-Type": "application/json",
=======
            "CB-ACCESS-PASSPHRASE": header_dict["passphrase"],
            "Content-Type": 'application/json',
>>>>>>> Created bitroyal connector folder and files in hummingbot>market
        }
