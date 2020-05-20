import hashlib
import hmac
import time


class BitfinexAuth:
    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key

    def generate_auth_payload(self):
        nonce = self._make_nonce()
        auth_payload = 'AUTH{nonce}'.format(nonce=nonce)
        sig = self._auth_sig(auth_payload)

        payload = {
            "apiKey": self.api_key,
            "authSig": sig,
            "authNonce": nonce,
            "authPayload": auth_payload,
            "event": 'auth',
        }
        return payload

    def generate_api_headers(self, path, body):
        """
        Generate headers for a signed payload
        """
        nonce = str(self._make_nonce())
        signature = "/api/" + path + nonce + body

        sig = self._auth_sig(signature)

        return {
            "bfx-nonce": nonce,
            "bfx-apikey": self.api_key,
            "bfx-signature": sig,
            "content-type": "application/json"
        }

    # private methods
    def _make_nonce(self) -> int:
        nonce = int(round(time.time() * 1000000))
        return nonce

    def _auth_sig(self, auth_payload) -> str:
        sig = hmac.new(self.secret_key.encode('utf8'),
                       auth_payload.encode('utf8'),
                       hashlib.sha384).hexdigest()
        return sig
