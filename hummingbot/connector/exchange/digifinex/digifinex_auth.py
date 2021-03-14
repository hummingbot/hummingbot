import hmac
import hashlib
import base64
import urllib
import aiohttp
from typing import List, Dict, Any
# from hummingbot.connector.exchange.digifinex.digifinex_utils import get_ms_timestamp
from hummingbot.connector.exchange.digifinex import digifinex_constants as Constants
from hummingbot.connector.exchange.digifinex.time_patcher import TimePatcher
# import time

_time_patcher: TimePatcher = None


def time_patcher() -> TimePatcher:
    global _time_patcher
    if _time_patcher is None:
        _time_patcher = TimePatcher('Digifinex', DigifinexAuth.query_time_func)
        _time_patcher.start()
    return _time_patcher


class DigifinexAuth():
    """
    Auth class required by digifinex API
    Learn more at https://docs.digifinex.io/en-ww/v3/#signature-authentication-amp-verification
    """
    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key
        self.time_patcher = time_patcher()
        # self.time_patcher = time

    @classmethod
    async def query_time_func() -> float:
        async with aiohttp.ClientSession() as session:
            async with session.get(Constants.REST_URL + '/time') as resp:
                resp_data: Dict[str, float] = await resp.json()
                return float(resp_data["server_time"])

    def get_private_headers(
        self,
        path_url: str,
        request_id: int,
        data: Dict[str, Any] = None
    ):

        data = data or {}
        payload = urllib.parse.urlencode(data)
        sig = hmac.new(
            self.secret_key.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        nonce = int(self.time_patcher.time())

        header = {
            'ACCESS-KEY': self.api_key,
            'ACCESS-TIMESTAMP': str(nonce),
            'ACCESS-SIGN': sig,
        }

        return header

    def generate_ws_signature(self) -> List[Any]:
        data = [None] * 3
        data[0] = self.api_key
        nonce = int(self.time_patcher.time() * 1000)
        data[1] = str(nonce)

        data[2] = base64.b64encode(hmac.new(
            self.secret_key.encode('latin-1'),
            f"{nonce}".encode('latin-1'),
            hashlib.sha256
        ).digest())

        return data
