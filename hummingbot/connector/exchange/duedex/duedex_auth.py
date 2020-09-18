import base64
import hashlib
import hmac
import time


class DuedexAuth:
    def __init__(self, api_key: str, secret_key: str):
        self.api_key: str = api_key
        self.secret_key: str = secret_key

    def get_rest_signature_dict(self, method: str, path: str, query: str, body: str):
        timestamp = int(time.time() * 1000)
        expiration = timestamp + 5 * 1000
        timestamp = str(timestamp)
        expiration = str(expiration)
        message = method.upper() + '|' + path + '|' + timestamp + '|' + expiration + '|' + query + '|' + body
        signature = hmac.new(base64.b64decode(self.secret_key), message.encode(),
                             hashlib.sha256).hexdigest()
        return {
            'Ddx-Timestamp': timestamp,
            'Ddx-Expiration': expiration,
            'Ddx-Key': self.api_key,
            'Ddx-Signature': signature,
        }

    def get_ws_signature_dict(self, challenge: str):
        signature = hmac.new(base64.b64decode(self.secret_key), challenge.encode(),
                             digestmod = hashlib.sha256).hexdigest()
        return {
            "type": "auth",
            "key": self.api_key,
            "answer": signature,
        }
