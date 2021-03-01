import hmac
import hashlib
import base64
import urllib
from typing import List, Dict, Any
from hummingbot.connector.exchange.digifinex.digifinex_utils import get_ms_timestamp


class DigifinexAuth():
    """
    Auth class required by digifinex API
    Learn more at https://docs.digifinex.io/en-ww/v3/#signature-authentication-amp-verification
    """
    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key

    def get_private_headers(
        self,
        path_url: str,
        request_id: int,
        nonce: int,
        data: Dict[str, Any] = None
    ):

        data = data or {}
        payload = urllib.parse.urlencode(data)
        sig = hmac.new(
            self.secret_key.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        header = {
            'ACCESS-KEY': self.api_key,
            'ACCESS-TIMESTAMP': str(nonce),
            'ACCESS-SIGN': sig,
        }

        return header

    def generate_ws_signature(self) -> List[Any]:
        data = [None] * 3
        data[0] = self.api_key
        nounce = get_ms_timestamp()
        data[1] = str(nounce)

        data[2] = base64.b64encode(hmac.new(
            self.secret_key.encode('latin-1'),
            f"{nounce}".encode('latin-1'),
            hashlib.sha256
        ).digest())

        return data
