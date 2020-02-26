import hashlib
import hmac
import time


class BitfinexAuth():
    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key
        self.last_nonce = 0

    def _sign_payload(self, payload) -> str:
        sig = hmac.new(self.secret_key.encode('utf8'),
                       payload.encode('utf8'),
                       hashlib.sha384).hexdigest()
        return sig

    def get_nonce(self) -> int:
        nonce = int(round(time.time() * 1_000_000))

        if self.last_nonce == nonce:
            nonce = nonce + 1
        elif self.last_nonce > nonce:
            nonce = self.last_nonce + 1

        self.last_nonce = nonce

        return nonce

    def generate_auth_payload(self, payload, nonce = None):
        """
        Sign payload
        """
        nonce = nonce if nonce is not None else self.get_nonce()
        sig = self._sign_payload(payload)

        payload = {
            "apiKey": self.api_key,
            "authSig": sig,
            "authNonce": nonce,
            "authPayload": payload,
            "event": 'auth',
        }

        return payload

    def generate_api_headers(self, path, body):
        """
        Generate headers for a signed payload
        """
        nonce = str(self.get_nonce())
        signature = "/api/" + path + nonce + body

        sig = self._sign_payload(signature)

        return {
            "bfx-nonce": nonce,
            "bfx-apikey": self.api_key,
            "bfx-signature": sig,
            "content-type": "application/json"
        }
