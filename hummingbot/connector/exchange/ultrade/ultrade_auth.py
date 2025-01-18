from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class UltradeAuth(AuthBase):
    def __init__(self, trading_key: str, wallet_address: str, mnemonic_key: str, time_provider: TimeSynchronizer):
        self.trading_key = trading_key
        self.wallet_address = wallet_address
        self.mnemonic_key = mnemonic_key
        self.time_provider = time_provider

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        Adds the server time and the signature to the request, required for authenticated interactions. It also adds
        the required parameter in the request header.
        :param request: the request to be configured for authenticated interaction
        """
        return request  # pass-through

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        This method is intended to configure a websocket request to be authenticated. Ultrade does not use this
        functionality
        """
        return request  # pass-through
