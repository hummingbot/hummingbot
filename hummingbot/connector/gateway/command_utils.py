"""
Shared utilities for gateway commands.
"""
import asyncio
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from hummingbot.connector.gateway.gateway_base import GatewayBase
    from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient


class GatewayCommandUtils:
    """Utility functions for gateway commands."""

    @staticmethod
    async def get_network_for_chain(
        gateway_client: "GatewayHttpClient",
        chain: str,
        network: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Get network for a chain, using default if not provided.

        :param gateway_client: Gateway client instance
        :param chain: Chain name
        :param network: Optional network name
        :return: Tuple of (network, error_message)
        """
        if not network:
            network = await gateway_client.get_default_network_for_chain(chain)
            if not network:
                return None, f"Error: Could not determine default network for {chain}."
        return network, None

    @staticmethod
    def parse_trading_pair(pair: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
        """
        Parse trading pair string into base and quote tokens.

        :param pair: Trading pair string (e.g., "ETH-USDC")
        :return: Tuple of (base_token, quote_token)
        """
        if not pair:
            return None, None

        if "-" not in pair:
            return None, None

        parts = pair.split("-", 1)
        if len(parts) != 2:
            return None, None

        base_token = parts[0].strip()
        quote_token = parts[1].strip()

        # Only uppercase if they're symbols (short strings), not addresses
        if len(base_token) <= 10:
            base_token = base_token.upper()
        if len(quote_token) <= 10:
            quote_token = quote_token.upper()

        return base_token, quote_token

    @staticmethod
    def validate_amount(amount: str) -> Tuple[Optional[Decimal], Optional[str]]:
        """
        Validate and convert amount string to Decimal.

        :param amount: Amount string
        :return: Tuple of (amount_decimal, error_message)
        """
        try:
            amount_decimal = Decimal(amount)
            if amount_decimal <= 0:
                return None, "Error: Amount must be greater than 0"
            return amount_decimal, None
        except Exception:
            return None, f"Error: Invalid amount '{amount}'"

    @staticmethod
    def validate_side(side: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Validate and normalize trade side.

        :param side: Trade side string
        :return: Tuple of (normalized_side, error_message)
        """
        if not side:
            return None, "Error: Side is required"

        side_upper = side.upper()
        if side_upper not in ["BUY", "SELL"]:
            return None, f"Error: Invalid side '{side}'. Must be BUY or SELL."

        return side_upper, None

    @staticmethod
    async def get_default_wallet(
        gateway_client: "GatewayHttpClient",
        chain: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Get default wallet for a chain.

        :param gateway_client: Gateway client instance
        :param chain: Chain name
        :return: Tuple of (wallet_address, error_message)
        """
        wallet_address = await gateway_client.get_default_wallet_for_chain(chain)
        if not wallet_address:
            return None, f"No default wallet found for {chain}. Please add one with 'gateway wallet add {chain}'"
        return wallet_address, None

    @staticmethod
    async def find_pool(
        gateway_client: "GatewayHttpClient",
        connector_name: str,
        network: str,
        base_token: str,
        quote_token: str
    ) -> Optional[str]:
        """
        Find pool address for a trading pair.

        :param gateway_client: Gateway client instance
        :param connector_name: Base connector name (without type suffix)
        :param network: Network name
        :param base_token: Base token symbol or address
        :param quote_token: Quote token symbol or address
        :return: Pool address or None
        """
        try:
            # Search for pools with the trading pair
            pools = await gateway_client.get_pools(
                connector_name, network, search=f"{base_token}/{quote_token}"
            )
            if not pools:
                # Try reverse search
                pools = await gateway_client.get_pools(
                    connector_name, network, search=f"{quote_token}/{base_token}"
                )

            if pools:
                # Use the first matching pool
                return pools[0].get("address")

        except Exception:
            pass

        return None

    @staticmethod
    async def get_connector_config(
        gateway_client: "GatewayHttpClient",
        connector: str
    ) -> Dict:
        """
        Get connector configuration.

        :param gateway_client: Gateway client instance
        :param connector: Connector name (with or without type suffix)
        :return: Configuration dictionary
        """
        try:
            # Use base connector name for config (strip type suffix)
            base_connector = connector.split("/")[0] if "/" in connector else connector
            return await gateway_client.get_configuration(namespace=base_connector)
        except Exception:
            return {}

    @staticmethod
    async def get_connector_chain_network(
        gateway_client: "GatewayHttpClient",
        connector: str
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Get chain and default network for a connector.

        :param gateway_client: Gateway client instance
        :param connector: Connector name in format 'name/type' (e.g., 'uniswap/amm')
        :return: Tuple of (chain, network, error_message)
        """
        # Parse connector format
        connector_parts = connector.split('/')
        if len(connector_parts) != 2:
            return None, None, "Invalid connector format. Use format like 'uniswap/amm' or 'jupiter/router'"

        connector_name = connector_parts[0]

        # Get all connectors to find chain info
        try:
            connectors_resp = await gateway_client.get_connectors()
            if "error" in connectors_resp:
                return None, None, f"Error getting connectors: {connectors_resp['error']}"

            # Find the connector info
            connector_info = None
            for conn in connectors_resp.get("connectors", []):
                if conn.get("name") == connector_name:
                    connector_info = conn
                    break

            if not connector_info:
                return None, None, f"Connector '{connector_name}' not found"

            # Get chain from connector info
            chain = connector_info.get("chain")
            if not chain:
                return None, None, f"Could not determine chain for connector '{connector_name}'"

            # Get default network for the chain
            network = await gateway_client.get_default_network_for_chain(chain)
            if not network:
                return None, None, f"Could not get default network for chain '{chain}'"

            return chain, network, None

        except Exception as e:
            return None, None, f"Error getting connector info: {str(e)}"

    @staticmethod
    def format_token_display(token: str) -> str:
        """
        Format token for display (truncate addresses).

        :param token: Token symbol or address
        :return: Formatted display string
        """
        if len(token) <= 10:
            return token
        return f"{token[:8]}...{token[-4:]}"

    @staticmethod
    async def get_available_tokens(
        gateway_client: "GatewayHttpClient",
        chain: str,
        network: str
    ) -> list:
        """
        Get list of available token symbols.

        :param gateway_client: Gateway client instance
        :param chain: Chain name
        :param network: Network name
        :return: List of token symbols
        """
        try:
            tokens_resp = await gateway_client.get_tokens(chain, network)
            tokens = tokens_resp.get("tokens", [])
            return sorted(list(set([t.get("symbol", "") for t in tokens if t.get("symbol")])))
        except Exception:
            return []

    @staticmethod
    def parse_connector_trading_type(connector_name: str) -> Tuple[str, Optional[str]]:
        """
        Extract base connector and trading type from connector name.

        :param connector_name: Connector name (e.g., "raydium/amm", "uniswap")
        :return: Tuple of (base_connector, trading_type)
        """
        if "/" in connector_name:
            parts = connector_name.split("/", 1)
            return parts[0], parts[1]
        return connector_name, None

    @staticmethod
    def normalize_token_symbol(symbol: str) -> str:
        """
        Normalize token symbol for consistency.

        :param symbol: Token symbol
        :return: Normalized symbol (uppercase)
        """
        if not symbol:
            return ""
        # Only uppercase if it's a symbol (short string), not an address
        if len(symbol) <= 10:
            return symbol.upper().strip()
        return symbol.strip()

    @staticmethod
    async def validate_chain_network(
        gateway_client: "GatewayHttpClient",
        chain: Optional[str],
        network: Optional[str]
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Validate chain and network combination.

        :param gateway_client: Gateway client instance
        :param chain: Chain name
        :param network: Network name
        :return: Tuple of (chain, network, error_message)
        """
        if not chain:
            return None, None, "Error: Chain is required"

        # Get available chains
        try:
            chains_info = await gateway_client.get_chains()
            chain_found = False
            available_networks = []

            for chain_info in chains_info:
                if chain_info.get("chain", "").lower() == chain.lower():
                    chain_found = True
                    available_networks = chain_info.get("networks", [])
                    break

            if not chain_found:
                return None, None, f"Error: Chain '{chain}' not found"

            # If network not provided, use default
            if not network:
                network = await gateway_client.get_default_network_for_chain(chain)
                if not network and available_networks:
                    network = available_networks[0]  # Use first available

            # Validate network
            if network and network not in available_networks:
                error_msg = f"Error: Network '{network}' not available for {chain}\n"
                error_msg += f"Available networks: {', '.join(available_networks)}"
                return None, None, error_msg

        except Exception as e:
            return None, None, f"Error validating chain/network: {str(e)}"

        return chain, network, None

    @staticmethod
    def validate_address(address: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Basic validation for blockchain addresses.

        :param address: Blockchain address
        :return: Tuple of (address, error_message)
        """
        if not address:
            return None, "Error: Address is required"

        address = address.strip()

        # Basic validation - check if it looks like an address
        if len(address) < 20:
            return None, "Error: Invalid address format"

        # Ethereum-style addresses
        if address.startswith("0x") and len(address) != 42:
            return None, "Error: Invalid Ethereum address length"

        return address, None

    @staticmethod
    def format_gateway_exception(exception: Exception) -> str:
        """
        Format Gateway-related exceptions for user display.

        :param exception: Exception to format
        :return: Formatted error message
        """
        error_msg = str(exception)

        # Common Gateway errors
        if "ECONNREFUSED" in error_msg:
            return "Gateway is not running. Please start Gateway first."
        elif "404" in error_msg:
            return "Gateway endpoint not found. Please check your Gateway version."
        elif "timeout" in error_msg:
            return "Gateway request timed out. Please check your connection."
        elif "500" in error_msg:
            return "Gateway internal error. Please check Gateway logs."

        return f"Gateway error: {error_msg}"

    @staticmethod
    async def get_all_chains_networks(gateway_client: "GatewayHttpClient") -> Dict[str, List[str]]:
        """
        Get all available chains and their networks.

        :param gateway_client: Gateway client instance
        :return: Dictionary mapping chain names to list of networks
        """
        try:
            chains_info = await gateway_client.get_chains()
            result = {}

            for chain_info in chains_info:
                chain = chain_info.get("chain", "")
                networks = chain_info.get("networks", [])
                if chain:
                    result[chain] = networks

            return result
        except Exception:
            return {}

    @staticmethod
    async def monitor_transaction_with_timeout(
        connector: "GatewayBase",
        order_id: str,
        notify_fn: Callable[[str], None],
        timeout: float = 60.0,
        check_interval: float = 1.0,
        pending_msg_delay: float = 3.0
    ) -> Dict[str, Any]:
        """
        Monitor a transaction until completion or timeout.

        :param connector: Gateway connector instance
        :param order_id: Order ID to monitor
        :param notify_fn: Function to call for notifications
        :param timeout: Maximum time to wait in seconds
        :param check_interval: How often to check status in seconds
        :param pending_msg_delay: When to show pending message
        :return: Dictionary with status information
        """
        elapsed = 0
        pending_shown = False

        while elapsed < timeout:
            order = connector.get_order(order_id)

            if order and order.is_done:
                # Give a small delay to ensure order state is fully updated
                await asyncio.sleep(0.5)

                # Re-fetch the order to get the latest state
                order = connector.get_order(order_id)

                result = {
                    "completed": True,
                    "success": order.is_filled if order else False,
                    "failed": order.is_failure if order else False,
                    "cancelled": order.is_cancelled if order else False,
                    "order": order,
                    "elapsed_time": elapsed
                }

                # Show appropriate message
                if order and order.is_filled:
                    notify_fn("\n✓ Transaction completed successfully!")
                    if order.exchange_order_id:
                        notify_fn(f"Transaction hash: {order.exchange_order_id}")
                elif order and order.is_failure:
                    notify_fn("\n✗ Transaction failed")
                elif order and order.is_cancelled:
                    notify_fn("\n✗ Transaction cancelled")

                return result

            await asyncio.sleep(check_interval)
            elapsed += check_interval

            # Show pending message after delay
            if elapsed >= pending_msg_delay and not pending_shown:
                notify_fn("Transaction pending...")
                pending_shown = True

        # Timeout reached
        order = connector.get_order(order_id)
        result = {
            "completed": False,
            "timeout": True,
            "order": order,
            "elapsed_time": elapsed
        }

        notify_fn("\n⚠️  Transaction may still be pending.")
        if order and order.exchange_order_id:
            notify_fn(f"You can check the transaction manually: {order.exchange_order_id}")

        return result
