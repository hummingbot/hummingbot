import hashlib
import hmac
from hummingbot.connector.exchange.bitstamp.bitstamp_tracking_nonce import get_tracking_nonce
from typing import Dict


class BitstampAuth:
    def __init__(self, client_id: str, api_key: str, secret_key: str):
        self.client_id = client_id
        self.api_key = api_key
        self.secret_key = secret_key

    def generate_auth_dict(self) -> Dict[str, str]:
        """
        Generates authentication signature and returns it in request parameters
        :return: a string of request parameters including the signature
        """

        # Get next nonce
        api_nonce: str = get_tracking_nonce()
        # Compile message
        message: str = api_nonce + self.client_id + self.api_key
        # Calculate signature
        api_signature: str = hmac.new(
            self.secret_key.encode(),
            message.encode(),
            hashlib.sha256).hexdigest().upper()

        return {
            "key": self.api_key,
            "signature": api_signature,
            "nonce": api_nonce
        }
