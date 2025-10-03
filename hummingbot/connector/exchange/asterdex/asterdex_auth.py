import hashlib
import hmac
import time
from typing import Any, Dict

from hummingbot.connector.exchange.asterdex import asterdex_constants as CONSTANTS
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class AsterdexAuth(AuthBase):
    """
    Auth class required by Asterdex API
    Learn more at https://asterdex.github.io/asterdex-pro-api/#authenticate-a-restful-request
    """

    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        Adds the server time and the signature to the request, required for authenticated interactions.
        Uses AsterDex format: X-MBX-APIKEY header and query parameters for signature.
        :param request: the request to be configured for authenticated interaction
        """
        # Generate timestamp and signature
        timestamp = str(int(self._time() * 1000))
        
        # For AsterDex, we need to add timestamp and signature as query parameters
        # and use X-MBX-APIKEY header
        if request.params is None:
            request.params = {}
        elif isinstance(request.params, list):
            # Convert list to dict if needed
            request.params = {}
        
        # Add timestamp to query parameters
        request.params["timestamp"] = timestamp
        
        # Generate signature using the query string
        query_string = self._build_query_string(request.params)
        signature = hmac.new(self.secret_key.encode("utf-8"), query_string.encode("utf-8"), hashlib.sha256).hexdigest()
        request.params["signature"] = signature
        
        # Set the API key header (AsterDex format)
        headers = {}
        if request.headers is not None:
            headers.update(request.headers)
        headers["X-MBX-APIKEY"] = self.api_key
        request.headers = headers

        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        This method is intended to configure a websocket request to be authenticated. Asterdex does not use this
        functionality
        """
        return request  # pass-through

    def get_auth_headers(self, path_url: str, data: Dict[str, Any] = None):
        """
        Generates authentication headers for AsterDex API format
        :param path_url: URL of the auth API endpoint
        :param data: data to be included in the headers
        :return: a dictionary of request headers
        """
        return {
            "X-MBX-APIKEY": self.api_key,
        }
    
    def _build_query_string(self, params: Dict[str, Any]) -> str:
        """
        Build query string from parameters for signature generation
        :param params: dictionary of parameters
        :return: URL-encoded query string
        """
        import urllib.parse
        return urllib.parse.urlencode(params)

    def _time(self) -> float:
        return time.time()
