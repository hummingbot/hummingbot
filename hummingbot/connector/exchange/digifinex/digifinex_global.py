import aiohttp
from hummingbot.connector.exchange.digifinex.digifinex_auth import DigifinexAuth
from hummingbot.connector.exchange.digifinex.digifinex_rest_api import DigifinexRestApi


class DigifinexGlobal:

    def __init__(self, key: str, secret: str):
        self.auth = DigifinexAuth(key, secret)
        self.rest_api = DigifinexRestApi(self.auth, self.http_client)
        self._shared_client: aiohttp.ClientSession = None

    async def http_client(self) -> aiohttp.ClientSession:
        """
        :returns Shared client session instance
        """
        if self._shared_client is None:
            self._shared_client = aiohttp.ClientSession()
        return self._shared_client
