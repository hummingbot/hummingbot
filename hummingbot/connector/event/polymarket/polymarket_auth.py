"""
Polymarket authentication using py-clob-client SDK with AuthBase integration.
Provides proper hummingbot integration while leveraging SDK capabilities.
"""

from typing import Dict, Optional

from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest
from hummingbot.logger import HummingbotLogger

try:
    from py_clob_client.client import ClobClient
    from py_clob_client.clob_types import BalanceAllowanceParams, MarketOrderArgs, OrderArgs
    PY_CLOB_CLIENT_AVAILABLE = True
except ImportError:
    PY_CLOB_CLIENT_AVAILABLE = False
    ClobClient = None
    OrderArgs = None
    MarketOrderArgs = None
    BalanceAllowanceParams = None

from .polymarket_constants import POLYGON_CHAIN_ID, REST_BASE_URL


class PolymarketAuth(AuthBase):
    """
    AuthBase wrapper for py-clob-client SDK with improved hummingbot integration.
    Handles SDK initialization and provides standard hummingbot auth interface.
    """

    _logger: Optional[HummingbotLogger] = None

    def __init__(self, private_key: str, wallet_address: str, signature_type: int = 0):
        # Remove 0x prefix if present for SDK compatibility
        self._private_key = private_key[2:] if private_key.startswith('0x') else private_key
        self._wallet_address = wallet_address
        self._signature_type = signature_type
        self._client = None
        self._credentials = None
        self._initialization_complete = False

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = HummingbotLogger(__name__)
        return cls._logger

    async def _initialize_sdk(self):
        """Initialize py-clob-client SDK"""
        if not PY_CLOB_CLIENT_AVAILABLE:
            raise ImportError("py-clob-client is not installed. Run: pip install py-clob-client")

        try:
            # Initialize client
            self._client = ClobClient(
                host=REST_BASE_URL,
                key=self._private_key,
                chain_id=POLYGON_CHAIN_ID,
                signature_type=self._signature_type,
                funder=self._wallet_address
            )

            # Create and set API credentials
            self._credentials = self._client.create_or_derive_api_creds()
            self._client.set_api_creds(self._credentials)

            self._initialization_complete = True
            self.logger().info("Polymarket SDK initialized successfully")

        except ImportError:
            self.logger().error("py-clob-client not installed. Install with: pip install py-clob-client>=0.20.0")
            raise
        except Exception as e:
            self.logger().error(f"Failed to initialize Polymarket SDK: {e}")
            raise

    async def ensure_initialized(self):
        """Ensure SDK is initialized before use"""
        if not self._initialization_complete:
            await self._initialize_sdk()

    @property
    def client(self):
        """Get the SDK client"""
        return self._client

    @property
    def credentials(self):
        """Get API credentials"""
        return self._credentials

    @property
    def wallet_address(self) -> str:
        """Get wallet address"""
        return self._wallet_address

    def get_headers(self) -> Dict[str, str]:
        """Get authentication headers for hummingbot compatibility"""
        if not self._credentials:
            return {}

        return {
            "CLOB-API-KEY": self._credentials.api_key,
            "CLOB-SECRET": self._credentials.api_secret,
            "CLOB-PASSPHRASE": self._credentials.api_passphrase
        }

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """Add authentication headers to REST requests"""
        await self.ensure_initialized()

        if self._credentials:
            headers = self.get_headers()
            if request.headers:
                request.headers.update(headers)
            else:
                request.headers = headers

        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """Add authentication to WebSocket requests"""
        await self.ensure_initialized()

        if hasattr(request, 'payload') and request.payload and self._credentials:
            # Add API credentials to WebSocket auth payload
            auth_data = {
                "type": "user",
                "auth": {
                    "apiKey": self._credentials.api_key,
                    "secret": self._credentials.api_secret,
                    "passphrase": self._credentials.api_passphrase
                }
            }
            request.payload.update(auth_data)

        return request

    # SDK method wrappers for direct access
    def get_order_book(self, token_id: str):
        """Get order book using SDK"""
        if not self._client:
            raise RuntimeError("SDK not initialized")
        return self._client.get_order_book(token_id)

    def get_balance_allowance(self, params):
        """Get balance using SDK"""
        if not self._client:
            raise RuntimeError("SDK not initialized")
        return self._client.get_balance_allowance(params)

    def create_order(self, order_args):
        """Create order using SDK"""
        if not self._client:
            raise RuntimeError("SDK not initialized")
        return self._client.create_order(order_args)

    def create_market_order(self, market_order_args):
        """Create market order using SDK"""
        if not self._client:
            raise RuntimeError("SDK not initialized")
        return self._client.create_market_order(market_order_args)

    def post_order(self, signed_order, order_type):
        """Post order using SDK"""
        if not self._client:
            raise RuntimeError("SDK not initialized")
        return self._client.post_order(signed_order, order_type)

    def cancel_order(self, order_id):
        """Cancel order using SDK"""
        if not self._client:
            raise RuntimeError("SDK not initialized")
        return self._client.cancel_order(order_id)

    def get_simplified_markets(self):
        """Get markets using SDK"""
        if not self._client:
            raise RuntimeError("SDK not initialized")
        return self._client.get_simplified_markets()

    def get_price(self, token_id, side):
        """Get price using SDK"""
        if not self._client:
            raise RuntimeError("SDK not initialized")
        return self._client.get_price(token_id, side)

    def get_midpoint(self, token_id):
        """Get midpoint using SDK"""
        if not self._client:
            raise RuntimeError("SDK not initialized")
        return self._client.get_midpoint(token_id)
