import hashlib
import hmac
import time
from typing import Any, Dict

class OrderlyAuth:
    def __init__(self, account_id: str, orderly_key: str, orderly_secret: str):
        self.account_id = account_id
        self.orderly_key = orderly_key
        self.orderly_secret = orderly_secret

    def get_auth_headers(self, method: str, path: str, body: str = "") -> Dict[str, str]:
        timestamp = str(int(time.time() * 1000))
        message = f"{timestamp}{method.upper()}{path}{body}"
        signature = hmac.new(
            self.orderly_secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        return {
            "orderly-timestamp": timestamp,
            "orderly-account-id": self.account_id,
            "orderly-key": self.orderly_key,
            "orderly-signature": signature,
            "Content-Type": "application/json"
        }