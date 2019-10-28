import requests

class HitbtcAuth:
    """
    Auth Class required by HitBTC API
    Learn more at https://api.hitbtc.com/#authentication
    """
    url = "https://api.hitbtc.com"
    
    def _init_(self, publicKey: str, secretKey: str):
        self.url = url + "/api/2"
        self.publicKey = publicKey
        self.secretKey = secretKey
        self.session = requests.session()
        self.session.auth = (self.publicKey, self.secretKey)