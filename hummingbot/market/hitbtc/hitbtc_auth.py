from aiohttp import BasicAuth


class HitBTCAuth:
    """
    Auth Class required by HitBTC API
    Learn more at https://api.hitbtc.com/#authentication
    """

    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key

    @property
    def auth(self):
        return BasicAuth(login=self.api_key, password=self.secret_key)
