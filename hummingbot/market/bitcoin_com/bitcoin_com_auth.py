import base64

from typing import Dict


class BitcoinComAuth:
    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key

    def generate_auth_dict(self) -> Dict[str, str]:
        """
        Generates authentication signature and return it in a dictionary
        :return: a dictionary of request info including the request signature
        """

        # api.exchange.bitcoin.com uses Basic Authentication https://api.exchange.bitcoin.com/#authentication
        message = self.api_key + ":" + self.secret_key
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
