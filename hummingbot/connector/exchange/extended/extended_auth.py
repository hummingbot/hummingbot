import time
from typing import Any, Dict

from hummingbot.connector.exchange.extended import extended_constants as CONSTANTS
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class ExtendedAuth(AuthBase):
    """
    Auth class required by Extended API
    Learn more at https://api.docs.extended.exchange/
    
    Extended uses:
    - API Key for authentication (X-Api-Key header)
    - Stark Key Pair for signing order management requests
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
        :param request: the request to be configured for authenticated interaction
        """
        # Set the API key header (Extended uses X-Api-Key)
        headers = {}
        if request.headers is not None:
            headers.update(request.headers)
        headers["X-Api-Key"] = self.api_key
        request.headers = headers
        
        # For order management endpoints, Stark signature will be added to request body
        # The signature generation happens in the exchange class before calling this method
        # This is because the signature depends on the order parameters

        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        This method is intended to configure a websocket request to be authenticated.
        Extended uses X-Api-Key header for websocket authentication.
        """
        # For Extended, authentication is done via X-Api-Key header
        if request.headers is None:
            request.headers = {}
        
        request.headers["X-Api-Key"] = self.api_key
        
        return request

    def get_auth_headers(self, path_url: str, data: Dict[str, Any] = None):
        """
        Generates authentication headers for Extended API format
        :param path_url: URL of the auth API endpoint
        :param data: data to be included in the headers
        :return: a dictionary of request headers
        """
        return {
            "X-Api-Key": self.api_key,
        }
    
    def generate_stark_signature(self, order_params: Dict[str, Any]) -> str:
        """
        Generate Stark signature for order placement
        :param order_params: Order parameters to sign
        :return: Stark signature as hex string
        
        Note: This is a placeholder. The actual Stark signature implementation
        requires the starkware-crypto library and proper message hashing.
        Extended API expects signatures following the Starknet signing standard.
        """
        # TODO: Implement proper Stark signature generation
        # For now, return the stark_private_key as a placeholder
        # In production, this should use starkware.crypto.signature.sign
        # to properly sign the order message hash
        return self.stark_private_key
    
    def _time(self) -> float:
        return time.time()

