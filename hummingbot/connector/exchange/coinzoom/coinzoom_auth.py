from typing import Dict, Any


class CoinzoomAuth():
    """
    Auth class required by CoinZoom API
    Learn more at https://exchange-docs.crypto.com/#digital-signature
    """
    def __init__(self, api_key: str, secret_key: str, username: str):
        self.api_key = api_key
        self.secret_key = secret_key
        self.username = username

    def get_ws_params(self) -> Dict[str, str]:
        return {
            "apiKey": str(self.api_key),
            "secretKey": str(self.secret_key),
        }

    def get_headers(self) -> Dict[str, Any]:
        """
        Generates authentication headers required by CoinZoom
        :return: a dictionary of auth headers
        """
        headers = {
            "Content-Type": "application/json",
            "Coinzoom-Api-Key": str(self.api_key),
            "Coinzoom-Api-Secret": str(self.secret_key),
            "User-Agent": f"hummingbot ZoomMe: {self.username}"
        }
        return headers
