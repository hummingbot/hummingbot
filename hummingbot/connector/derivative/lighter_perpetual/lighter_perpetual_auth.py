import time
from typing import Any, Dict, Optional

from hummingbot.connector.derivative.lighter_perpetual import lighter_perpetual_constants as CONSTANTS
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class LighterPerpetualAuth(AuthBase):
    """
    Auth class required by Lighter Perpetual API
    Lighter uses public key and private key for authentication
    and requires api_key_index for identification
    """

    def __init__(self, public_key: str, private_key: str, api_key_index: int):
        self.public_key = public_key
        self.private_key = private_key
        self.api_key_index = api_key_index
        self._current_nonce: Optional[int] = None
        self._nonce_lock = False

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        Adds authentication headers to the request.
        Lighter uses public and private keys for authentication.
        """
        # Set the authentication headers
        headers = {}
        if request.headers is not None:
            headers.update(request.headers)
        
        # Use Bearer token authentication with private key
        headers["Authorization"] = f"Bearer {self.private_key}"
        headers["X-Lighter-Public-Key"] = self.public_key
        headers["X-Api-Key-Index"] = str(self.api_key_index)
        
        # Debug logging
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"🔑 Lighter Auth: Adding Authorization header")
        logger.info(f"🔑 Public Key: {self.public_key[:10]}..., API Key Index: {self.api_key_index}")
        logger.info(f"🔑 Request URL: {request.url if hasattr(request, 'url') else 'N/A'}")
        
        request.headers = headers
        
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        Configure websocket request for authentication.
        Lighter uses similar headers for websocket authentication.
        """
        if request.headers is None:
            request.headers = {}
        
        request.headers["Authorization"] = f"Bearer {self.private_key}"
        request.headers["X-Lighter-Public-Key"] = self.public_key
        request.headers["X-Api-Key-Index"] = str(self.api_key_index)
        
        return request

    def get_auth_headers(self, path_url: str = "", data: Dict[str, Any] = None):
        """
        Generates authentication headers for Lighter API format
        """
        return {
            "Authorization": f"Bearer {self.private_key}",
            "X-Lighter-Public-Key": self.public_key,
            "X-Api-Key-Index": str(self.api_key_index),
        }
    
    def get_current_nonce(self) -> Optional[int]:
        """
        Get the current nonce value
        """
        return self._current_nonce
    
    def set_nonce(self, nonce: int):
        """
        Set the nonce to a specific value (typically from API)
        """
        self._current_nonce = nonce
    
    def increment_nonce(self) -> int:
        """
        Increment and return the next nonce
        Each nonce is used once per API_KEY
        """
        if self._current_nonce is None:
            # If nonce not initialized, return 0 and caller should fetch from API
            return 0
        
        self._current_nonce += 1
        return self._current_nonce
    
    def generate_transaction_signature(self, order_params: Dict[str, Any], nonce: int) -> str:
        """
        Generate transaction signature for order placement
        
        Lighter requires signing transactions with the private key.
        The signature format follows Lighter's SignerClient specification.
        
        Note: This is a simplified implementation. In production, you may need
        to integrate with Lighter's actual SignerClient or signing library.
        
        Args:
            order_params: Order parameters to sign
            nonce: Current nonce value
            
        Returns:
            Signature string
        """
        # TODO: Implement proper Lighter signature generation
        # This would typically involve:
        # 1. Serialize order parameters in Lighter's expected format
        # 2. Include nonce, public_key, api_key_index
        # 3. Sign with private_key using Lighter's signing algorithm
        # 4. Return hex-encoded signature
        
        # Placeholder: In real implementation, use Lighter SDK or crypto library
        import hashlib
        import json
        
        # Create signing payload
        signing_data = {
            "nonce": nonce,
            "public_key": self.public_key,
            "api_key_index": self.api_key_index,
            **order_params
        }
        
        # Simple placeholder signature (replace with actual signing logic)
        signing_string = json.dumps(signing_data, sort_keys=True)
        signature = hashlib.sha256(
            f"{signing_string}{self.private_key}".encode()
        ).hexdigest()
        
        return signature
    
    def _time(self) -> float:
        return time.time()

