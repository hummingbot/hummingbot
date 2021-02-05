import hmac
import time
import hashlib


class BlocktaneAuth:
    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key

    def generate_auth_dict(self) -> dict:
        """
        Returns headers for authenticated api request.
        """
        nonce = self.make_nonce()
        signature = self.auth_sig(nonce)

        payload = {
            "X-Auth-Apikey": self.api_key,
            "X-Auth-Nonce": nonce,
            "X-Auth-Signature": signature,
            "Content-Type": "application/json"
        }
        return payload

    def make_nonce(self) -> str:
        return str(round(time.time() * 1000))

    def auth_sig(self, nonce: str) -> str:
        sig = hmac.new(
            self.secret_key.encode('utf8'),
            '{}{}'.format(nonce, self.api_key).encode('utf8'),
            hashlib.sha256
        ).hexdigest()
        return sig
