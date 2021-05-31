from typing import (
    # Optional,
    Dict,
    Any
)


class DydxAuth:
    def __init__(self, wallet_address: str):
        self.wallet_address = wallet_address

    def generate_auth_dict(self) -> Dict[str, Any]:
        """
        Generates authentication signature and returns it in a dictionary
        :return: a dictionary of request info including the request signature and post data
        """

        return {
            "wallet_address": self.wallet_address
        }
