import requests

class Hitbtc:
    """
    Auth Class required by HitBTC API
    Learn more at https://api.hitbtc.com/#authentication
    """
    def _init_(self, url: str, publicKey: str, secretKey: str):
        self.url = url + "/api/2"
        self.publicKey = publicKey
        self.secretKey = secretKey
        self.session = requests.session()
        self.session.auth = (self.publicKey, self.secretKey)