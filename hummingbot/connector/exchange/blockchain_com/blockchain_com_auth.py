from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, RESTMethod, WSRequest
from typing import Dict


class BlockchainAuth(AuthBase):
    def __init__(self, api_token: str, ) -> None:
        self.api_token = api_token

    def header_for_authentication(self) -> Dict:
        headers = {"X-API-Token": self.api_token}
        return headers
