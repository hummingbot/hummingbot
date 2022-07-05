from typing import Dict

from hummingbot.core.web_assistant.auth import AuthBase


class BlockchainComAuth(AuthBase):
    def __init__(self, api_token: str, ) -> None:
        self.api_token = api_token

    def header_for_authentication(self) -> Dict:
        headers = {"X-API-Token": self.api_token}
        return headers
