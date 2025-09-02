"""
Polymarket SDK-based authentication for hummingbot integration.
Uses py-clob-client for reliable authentication and order signing.
"""

from decimal import Decimal
from typing import Dict, Optional

from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.logger import HummingbotLogger

from .polymarket_constants import CHAIN_ID, REST_BASE_URL, SIGNATURE_TYPE_EOA


class PolymarketSDKAuth(AuthBase):
    """
    SDK-based authentication handler for Polymarket using py-clob-client.
    Provides robust authentication, credential management, and order signing.
    """

    _logger: Optional[HummingbotLogger] = None

    def __init__(
        self,
        private_key: str,
        wallet_address: str,
        signature_type: int = SIGNATURE_TYPE_EOA
    ):
        """
        Initialize SDK authentication.

        Args:
            private_key: Ethereum private key (without 0x prefix)
            wallet_address: Ethereum wallet address
            signature_type: Signature type (0=EOA, 1=PROXY, 2=GNOSIS)
        """
        self._private_key = private_key
        self._wallet_address = wallet_address.lower()
        self._signature_type = signature_type

        # Initialize py-clob-client
        self._client = None
        self._creds = None
        self._initialize_client()

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = HummingbotLogger(__name__)
        return cls._logger

    def _initialize_client(self):
        """Initialize the py-clob-client with proper configuration."""
        try:
            # Import here to handle missing dependency gracefully
            from py_clob_client.client import ClobClient

            # Add 0x prefix if not present
            key = self._private_key
            if not key.startswith('0x'):
                key = '0x' + key

            self._client = ClobClient(
                host=REST_BASE_URL,
                key=key,
                chain_id=CHAIN_ID,
                signature_type=self._signature_type,
                funder=self._wallet_address
            )

            # Create and set API credentials
            self._creds = self._client.create_or_derive_api_creds()
            self._client.set_api_creds(self._creds)

            self.logger().info(f"Initialized Polymarket SDK client for address {self._wallet_address}")

        except ImportError as e:
            self.logger().error(
                "py-clob-client not installed. Please install with: pip install py-clob-client>=0.20.0"
            )
            raise e
        except Exception as e:
            self.logger().error(f"Failed to initialize SDK client: {e}")
            raise e

    @property
    def client(self):
        """Get the py-clob-client instance."""
        return self._client

    @property
    def wallet_address(self) -> str:
        return self._wallet_address

    def get_headers(self) -> Dict[str, str]:
        """
        Get authentication headers for REST API requests.

        Returns:
            Headers compatible with Polymarket API
        """
        if not self._creds:
            return {}

        return {
            "CLOB-API-KEY": self._creds.api_key,
            "CLOB-SECRET": self._creds.api_secret,
            "CLOB-PASSPHRASE": self._creds.api_passphrase,
            "Content-Type": "application/json"
        }

    def get_ws_auth_payload(self) -> Dict[str, any]:
        """
        Get WebSocket authentication payload.

        Returns:
            Authentication payload for WebSocket connections
        """
        if not self._creds:
            return {}

        return {
            "type": "user",
            "auth": {
                "apiKey": self._creds.api_key,
                "secret": self._creds.api_secret,
                "passphrase": self._creds.api_passphrase
            }
        }

    def create_order_signature(
        self,
        token_id: str,
        side: str,
        price: Decimal,
        size: Decimal,
        order_type: str = "GTC",
        **kwargs
    ) -> dict:
        """
        Create order using SDK (replaces manual EIP-712 signing).

        Args:
            token_id: Token ID for the market outcome
            side: BUY or SELL
            price: Order price (0-1 range)
            size: Order size in shares
            order_type: Order type (GTC, FOK, FAK, GTD)
            **kwargs: Additional order parameters

        Returns:
            Signed order ready for submission
        """
        try:
            from py_clob_client.clob_types import MarketOrderArgs, OrderArgs
            from py_clob_client.order_builder.constants import BUY, SELL

            # Map side string to SDK constants
            sdk_side = BUY if side.upper() == "BUY" else SELL

            # Check if this should be a market order
            is_market_order = kwargs.get("is_market_order", False)

            if is_market_order:
                # Market order - amount is in dollars for BUY, shares for SELL
                amount = float(size * price) if side.upper() == "BUY" else float(size)
                order_args = MarketOrderArgs(
                    token_id=token_id,
                    amount=amount,
                    side=sdk_side
                )
                signed_order = self._client.create_market_order(order_args)
            else:
                # Limit order
                order_args = OrderArgs(
                    token_id=token_id,
                    price=float(price),
                    size=float(size),
                    side=sdk_side,
                    fee_rate_bps=kwargs.get("fee_rate_bps", 0),
                    nonce=kwargs.get("nonce", 0),
                    expiration=kwargs.get("expiration", 0)
                )
                signed_order = self._client.create_order(order_args)

            return {
                "signed_order": signed_order,
                "order_type": order_type
            }

        except Exception as e:
            self.logger().error(f"Error creating order signature: {e}")
            raise e

    def submit_order(self, signed_order_data: dict) -> dict:
        """
        Submit a signed order to the exchange.

        Args:
            signed_order_data: Result from create_order_signature()

        Returns:
            Order submission response
        """
        try:
            from py_clob_client.clob_types import OrderType

            signed_order = signed_order_data["signed_order"]
            order_type = signed_order_data["order_type"]

            # Map string order type to SDK OrderType
            sdk_order_type = getattr(OrderType, order_type, OrderType.GTC)

            response = self._client.post_order(signed_order, sdk_order_type)
            return response

        except Exception as e:
            self.logger().error(f"Error submitting order: {e}")
            raise e

    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order by ID.

        Args:
            order_id: Exchange order ID to cancel

        Returns:
            True if successful
        """
        try:
            self._client.cancel(order_id)
            return True
        except Exception as e:
            self.logger().error(f"Error canceling order {order_id}: {e}")
            return False

    def cancel_all_orders(self) -> bool:
        """
        Cancel all open orders.

        Returns:
            True if successful
        """
        try:
            self._client.cancel_all()
            return True
        except Exception as e:
            self.logger().error(f"Error canceling all orders: {e}")
            return False

    def cancel_market_orders(self, market: str = None, asset_id: str = None) -> bool:
        """
        Cancel orders for a specific market or asset.

        Args:
            market: Market ID to cancel orders for
            asset_id: Asset/token ID to cancel orders for

        Returns:
            True if successful
        """
        try:
            if asset_id:
                self._client.cancel_market_orders(asset_id=asset_id)
            elif market:
                self._client.cancel_market_orders(market=market)
            else:
                self.logger().warning("No market or asset_id specified for cancel_market_orders")
                return False
            return True
        except Exception as e:
            self.logger().error(f"Error canceling market orders: {e}")
            return False

    def is_connected(self) -> bool:
        """Check if the SDK client is properly initialized and connected."""
        try:
            if not self._client or not self._creds:
                return False

            # Test connection with a simple API call
            self._client.get_ok()
            return True
        except Exception:
            return False
