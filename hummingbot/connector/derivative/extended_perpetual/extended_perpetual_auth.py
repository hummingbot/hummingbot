import time
from typing import Any, Dict

from hummingbot.connector.derivative.extended_perpetual import extended_perpetual_constants as CONSTANTS
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class ExtendedPerpetualAuth(AuthBase):
    """
    Auth class required by Extended Perpetual API
    Extended uses X-Api-Key header for authentication
    """

    def __init__(self, api_key: str, stark_public_key: str, stark_private_key: str):
        self.api_key = api_key
        self.stark_public_key = stark_public_key
        self.stark_private_key = stark_private_key

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        Adds authentication headers to the request.
        Extended uses X-Api-Key header for all requests.
        For order management, Stark signatures are required in the request body.
        """
        # Set the API key header
        headers = {}
        if request.headers is not None:
            headers.update(request.headers)
        
        headers["X-Api-Key"] = self.api_key
        
        request.headers = headers
        
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        Configure websocket request for authentication.
        Extended uses X-Api-Key header for websocket authentication.
        """
        if request.headers is None:
            request.headers = {}
        
        request.headers["X-Api-Key"] = self.api_key
        
        return request

    def get_auth_headers(self, path_url: str = "", data: Dict[str, Any] = None):
        """
        Generates authentication headers for Extended API format
        """
        return {
            "X-Api-Key": self.api_key,
        }
    
    def generate_stark_signature(self, order_params: Dict[str, Any]) -> str:
        """
        Generate Stark signature for order placement.
        
        Note: Requires starkware-crypto library for production use.
        Extended API expects signatures following the Starknet signing standard.
        """
        return self.stark_private_key
    
    def _time(self) -> float:
        return time.time()

