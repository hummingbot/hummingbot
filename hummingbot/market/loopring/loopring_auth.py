from typing import (
    Optional,
    Dict,
    Any
)

class LoopringAuth:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def generate_auth_dict(self) -> Dict[str, Any]: 
        # TODO: remove the uri and data parameters unless we end up doing something with them
        """
        Generates authentication signature and returns it in a dictionary
        :return: a dictionary of request info including the request signature and post data
        """

        return {
            "X-API-KEY": self.api_key
        }