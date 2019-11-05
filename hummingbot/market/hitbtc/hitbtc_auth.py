import base64

from typing import Dict
import requests


class HitbtcAuth:
    """
    Auth Class required by HitBTC API
    Learn more at https://api.hitbtc.com/#authentication
    """

    def _init_(self, publicKey: str, secretKey: str):
        self.publicKey = publicKey
        self.secretKey = secretKey
        # self.session = requests.session()
        # self.session.auth = (self.publicKey, self.secretKey)

    def generate_auth_dict(self) -> Dict[str, str]:
        """
        Generates authentication signature and return it in a dictionary
        :return: a dictionary of request info including the request signature
        """
        message = self.publickey + ":" + self.secretkey
        signature = base64.b64encode(bytes(message, "utf8")).decode("utf8")

        return {
            "signature": signature
        }

    def get_headers(self) -> Dict[str, str]:
        """
        Generates authentication headers required by bitcoin_com
        :return: a dictionary of auth headers
        """
        header_dict = self.generate_auth_dict()

        return {
            "Authorization": "Basic " + header_dict["signature"],
            "Content-Type": 'application/json',
        }