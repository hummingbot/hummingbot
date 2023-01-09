from typing import Dict
import json

from bxsolana import provider

from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest
from hummingbot.connector.time_synchronizer import TimeSynchronizer


class BloxrouteOpenbookAuth(AuthBase):
    """
    Auth class required to use bloxRoute Labs Solana Trader API
    Needed for web assistants factory
    """

    def __init__(self, auth_header: str, time_provider: TimeSynchronizer):
        self.auth_header = auth_header
        self.time_provider: TimeSynchronizer = time_provider

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        Adds the Bloxroute authentication header to the HTTP request
        """

        headers = {}
        if request.headers is not None:
            headers.update(request.headers)
        headers.update(self.authentication_headers(request=request))
        request.headers = headers

        print("blox route auth header")
        print(self.auth_header)

        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        This method is intended to configure a websocket request to be authenticated. Bloxroute does not use this
        functionality
        """

        return request  # pass-through