"""
Shared utilities for gateway commands.
"""
import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from hummingbot.connector.gateway.common_types import Token

if TYPE_CHECKING:
    from hummingbot.connector.gateway.gateway_base import GatewayBase
    from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient


class GatewayCommandUtils:
    """Utility functions for gateway commands."""

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
            return None, f"No default wallet found for {chain}. Please add one with 'gateway connect {chain}'"

        # Check if wallet address is a placeholder
        if "wallet-address" in wallet_address.lower():
            return None, f"{chain} wallet not configured (found placeholder: {wallet_address}). Please add a real wallet with: gateway connect {chain}"

        return wallet_address, None

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
    async def get_available_tokens(
        gateway_client: "GatewayHttpClient",
        chain: str,
        network: str
    ) -> List[Token]:
        """
        Get list of available tokens with full information.

        :param gateway_client: Gateway client instance
        :param chain: Chain name
        :param network: Network name
        :return: List of Token objects containing symbol, address, decimals, and name
        """
        try:
            tokens_resp = await gateway_client.get_tokens(chain, network)
            tokens = tokens_resp.get("tokens", [])
            # Return the full token objects
            return tokens
        except Exception:
            return []

    @staticmethod
    async def validate_tokens(
        gateway_client: "GatewayHttpClient",
        chain: str,
        network: str,
        token_symbols: List[str]
    ) -> Tuple[List[str], List[str]]:
        """
        Validate that tokens exist in the available token list.

        :param gateway_client: Gateway client instance
        :param chain: Chain name
        :param network: Network name
        :param token_symbols: List of token symbols to validate
        :return: Tuple of (valid_tokens, invalid_tokens)
        """
        if not token_symbols:
            return [], []

        # Get available tokens
        available_tokens = await GatewayCommandUtils.get_available_tokens(gateway_client, chain, network)
        available_symbols = {token["symbol"].upper() for token in available_tokens}

        # Check which tokens are valid/invalid
        valid_tokens = []
        invalid_tokens = []

        for token in token_symbols:
            token_upper = token.upper()
            if token_upper in available_symbols:
                valid_tokens.append(token_upper)
            else:
                invalid_tokens.append(token)

        return valid_tokens, invalid_tokens

    @staticmethod
    async def monitor_transaction_with_timeout(
        app: Any,  # HummingbotApplication
        connector: "GatewayBase",
        order_id: str,
        timeout: float = 60.0,
        check_interval: float = 1.0,
        pending_msg_delay: float = 3.0
    ) -> Dict[str, Any]:
        """
        Monitor a transaction until completion or timeout.

        :param app: HummingbotApplication instance (for notify method)
        :param connector: GatewayBase connector instance
        :param order_id: Order ID to monitor
        :param timeout: Maximum time to wait in seconds
        :param check_interval: How often to check status in seconds
        :param pending_msg_delay: When to show pending message
        :return: Dictionary with status information
        """
        elapsed = 0
        pending_shown = False
        hardware_wallet_msg_shown = False

        while elapsed < timeout:
            order = connector.get_order(order_id)

            # Check if transaction is complete (success, failed, or cancelled)
            if order and order.is_done:
                # Give a longer delay to ensure order state is fully updated
                await asyncio.sleep(2.0)

                # Re-fetch the order to get the latest state
                order = connector.get_order(order_id)

                # Special case: if is_done but state is PENDING_CREATE, treat as success
                is_pending_create = (
                    order and
                    hasattr(order, 'current_state') and
                    str(order.current_state) == "OrderState.PENDING_CREATE"
                )

                result = {
                    "completed": True,
                    "success": order.is_filled or is_pending_create if order else False,
                    "failed": order.is_failure if order else False,
                    "cancelled": order.is_cancelled if order else False,
                    "order": order,
                    "elapsed_time": elapsed
                }

                # Show appropriate message
                if order and (order.is_filled or is_pending_create):
                    app.notify("\n✓ Transaction completed successfully!")
                    if order.exchange_order_id:
                        app.notify(f"Transaction hash: {order.exchange_order_id}")
                elif order and order.is_failure:
                    app.notify("\n✗ Transaction failed")
                elif order and order.is_cancelled:
                    app.notify("\n✗ Transaction cancelled")
                else:
                    # Log the actual order state for debugging
                    state = order.current_state if order else "No order"
                    app.notify(f"\n⚠ Transaction completed with state: {state}")

                return result

            # Special handling for PENDING_CREATE state
            if order and hasattr(order, 'current_state') and str(order.current_state) == "OrderState.PENDING_CREATE":
                if not pending_shown:
                    app.notify("\n⏳ Waiting for wallet signature...")
                    pending_shown = True
                if elapsed > 10 and not hardware_wallet_msg_shown:  # After 10 seconds, provide more guidance
                    app.notify("If using a hardware wallet, please approve the transaction on your device.")
                    hardware_wallet_msg_shown = True

            await asyncio.sleep(check_interval)
            elapsed += check_interval

            # Show pending message after delay
            if elapsed >= pending_msg_delay and not pending_shown:
                app.notify("Transaction pending...")
                pending_shown = True

        # Timeout reached
        order = connector.get_order(order_id)
        result = {
            "completed": False,
            "timeout": True,
            "order": order,
            "elapsed_time": elapsed
        }

        app.notify("\n⚠️  Transaction may still be pending.")
        if order and order.exchange_order_id:
            app.notify(f"You can check the transaction manually: {order.exchange_order_id}")

        return result

    @staticmethod
    def format_address_display(address: str) -> str:
        """
        Format wallet/token address for display.

        :param address: Full address
        :return: Shortened address format (e.g., "0x1234...5678")
        """
        if not address:
            return "Unknown"
        if len(address) > 10:
            return f"{address[:6]}...{address[-4:]}"
        return address

    @staticmethod
    def format_allowance_display(
        allowances: Dict[str, Any],
        token_data: Dict[str, Token],
        connector_name: str = None
    ) -> List[Dict[str, str]]:
        """
        Format allowance data for display.

        :param allowances: Dictionary with token symbols as keys and allowance values
        :param token_data: Dictionary with token symbols as keys and Token info as values
        :param connector_name: Optional connector name for display
        :return: List of formatted rows for display
        """
        rows = []

        for token, allowance in allowances.items():
            # Get token info with fallback
            token_info = token_data.get(token, {})

            # Format allowance - show "Unlimited" for very large values
            try:
                allowance_val = float(allowance)
                # Check if it's larger than 10^10 (10 billion)
                if allowance_val >= 10**10:
                    formatted_allowance = "Unlimited"
                else:
                    # Show up to 4 decimal places
                    if allowance_val == int(allowance_val):
                        formatted_allowance = f"{int(allowance_val):,}"
                    else:
                        formatted_allowance = f"{allowance_val:,.4f}".rstrip('0').rstrip('.')
            except (ValueError, TypeError):
                formatted_allowance = str(allowance)

            # Format address for display
            address = token_info.get("address", "Unknown")
            formatted_address = GatewayCommandUtils.format_address_display(address)

            row = {
                "Symbol": token.upper(),
                "Address": formatted_address,
                "Allowance": formatted_allowance
            }

            rows.append(row)

        return rows

    @staticmethod
    async def get_wallet_balances(
        gateway_client: "GatewayHttpClient",
        chain: str,
        network: str,
        wallet_address: str,
        tokens_to_check: List[str],
        native_token: str
    ) -> Dict[str, float]:
        """
        Get wallet balances for specified tokens.

        :param gateway_client: Gateway client instance
        :param chain: Chain name
        :param network: Network name
        :param wallet_address: Wallet address
        :param tokens_to_check: List of tokens to check
        :param native_token: Native token symbol (e.g., ETH, SOL)
        :return: Dictionary of token balances
        """
        # Ensure native token is in the list
        if native_token not in tokens_to_check:
            tokens_to_check = tokens_to_check + [native_token]

        # Fetch balances
        try:
            balances_resp = await gateway_client.get_balances(
                chain, network, wallet_address, tokens_to_check
            )
            balances = balances_resp.get("balances", {})

            # Convert to float
            balance_dict = {}
            for token in tokens_to_check:
                balance = float(balances.get(token, 0))
                balance_dict[token] = balance

            return balance_dict

        except Exception:
            return {}

    @staticmethod
    def display_balance_impact_table(
        app: Any,  # HummingbotApplication
        wallet_address: str,
        current_balances: Dict[str, float],
        balance_changes: Dict[str, float],
        native_token: str,
        gas_fee: float,
        warnings: List[str],
        title: str = "Balance Impact"
    ):
        """
        Display a unified balance impact table showing current and projected balances.

        :param app: HummingbotApplication instance (for notify method)
        :param wallet_address: Wallet address
        :param current_balances: Current token balances
        :param balance_changes: Expected balance changes (positive for increase, negative for decrease)
        :param native_token: Native token symbol
        :param gas_fee: Gas fee in native token
        :param warnings: List to append warnings to
        :param title: Title for the table
        """
        # Format wallet address
        wallet_display = GatewayCommandUtils.format_address_display(wallet_address)

        app.notify(f"\n=== {title} ===")
        app.notify(f"Wallet: {wallet_display}")
        app.notify("\nToken     Current Balance → After Transaction")
        app.notify("-" * 50)

        # Display all tokens
        all_tokens = set(current_balances.keys()) | set(balance_changes.keys())

        for token in sorted(all_tokens):
            current = current_balances.get(token, 0)
            change = balance_changes.get(token, 0)

            # Apply gas fee to native token
            if token == native_token and gas_fee > 0:
                change -= gas_fee

            new_balance = current + change

            # Format the display
            if change != 0:
                app.notify(f"  {token:<8} {current:>14.6f} → {new_balance:>14.6f}")

                # Check for insufficient balance
                if new_balance < 0:
                    warnings.append(f"Insufficient {token} balance! You have {current:.6f} but need {abs(change):.6f}")
            else:
                app.notify(f"  {token:<8} {current:>14.6f}")

    @staticmethod
    async def estimate_transaction_fee(
        gateway_client: "GatewayHttpClient",
        chain: str,
        network: str,
        transaction_type: str = "swap"
    ) -> Dict[str, Any]:
        """
        Estimate transaction fee using gateway's estimate-gas endpoint.

        :param gateway_client: Gateway client instance
        :param chain: Chain name (e.g., "ethereum", "solana")
        :param network: Network name
        :param transaction_type: Type of transaction ("swap" or "approve")
        :return: Dictionary with fee estimation details
        """
        try:
            # Determine compute/gas units based on chain and transaction type
            if chain.lower() == "solana":
                # Solana uses compute units
                if transaction_type == "swap":
                    estimated_units = 300000  # 300k for swaps
                else:
                    estimated_units = 100000  # 100k for other transactions
                unit_name = "compute units"
                native_token = "SOL"
            else:
                # Ethereum-based chains use gas
                if transaction_type == "swap":
                    estimated_units = 200000  # 200k for swaps
                elif transaction_type == "approve":
                    estimated_units = 50000   # 50k for approvals
                else:
                    estimated_units = 100000  # 100k default
                unit_name = "gas"
                native_token = "ETH" if chain.lower() == "ethereum" else chain.upper()

            # Get gas estimation from gateway (returns fee per unit)
            gas_resp = await gateway_client.estimate_gas(chain, network)

            # Extract fee info from response
            fee_per_unit = gas_resp.get("feePerComputeUnit", 0)
            denomination = gas_resp.get("denomination", "")

            # Calculate fee based on denomination
            if denomination.lower() == "gwei":
                # Convert gwei to ETH (1 ETH = 1e9 gwei)
                fee_in_native = (fee_per_unit * estimated_units) / 1e9
            elif denomination.lower() == "lamports":
                # Convert lamports to SOL (1 SOL = 1e9 lamports)
                fee_in_native = (fee_per_unit * estimated_units) / 1e9
            else:
                # Assume price is already in native token
                fee_in_native = fee_per_unit * estimated_units

            return {
                "success": True,
                "fee_per_unit": fee_per_unit,
                "denomination": denomination,
                "estimated_units": estimated_units,
                "unit_name": unit_name,
                "fee_in_native": fee_in_native,
                "native_token": native_token
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "fee_per_unit": 0,
                "denomination": "",
                "estimated_units": 0,
                "unit_name": "units",
                "fee_in_native": 0,
                "native_token": chain.upper()
            }

    @staticmethod
    def display_transaction_fee_details(
        app: Any,  # HummingbotApplication
        fee_info: Dict[str, Any]
    ):
        """
        Display transaction fee details from fee estimation.

        :param app: HummingbotApplication instance (for notify method)
        :param fee_info: Fee information from estimate_transaction_fee
        """
        if not fee_info.get("success", False):
            app.notify("\nWarning: Could not estimate transaction fees")
            return

        fee_per_unit = fee_info["fee_per_unit"]
        denomination = fee_info["denomination"]
        estimated_units = fee_info["estimated_units"]
        unit_name = fee_info["unit_name"]
        fee_in_native = fee_info["fee_in_native"]
        native_token = fee_info["native_token"]

        app.notify("\nTransaction Fee Details:")
        app.notify(f"  Price per {unit_name}: {fee_per_unit:.4f} {denomination}")
        app.notify(f"  Estimated {unit_name}: {estimated_units:,}")
        app.notify(f"  Total Fee: ~{fee_in_native:.6f} {native_token}")

    @staticmethod
    async def prompt_for_confirmation(
        app: Any,  # HummingbotApplication
        message: str,
        is_warning: bool = False
    ) -> bool:
        """
        Prompt user for yes/no confirmation.

        :param app: HummingbotApplication instance
        :param message: Confirmation message to display
        :param is_warning: Whether this is a warning confirmation
        :return: True if confirmed, False otherwise
        """
        prefix = "⚠️  " if is_warning else ""
        response = await app.app.prompt(
            prompt=f"{prefix}{message} (Yes/No) >>> "
        )
        return response.lower() in ["y", "yes"]

    @staticmethod
    def display_warnings(
        app: Any,  # HummingbotApplication
        warnings: List[str],
        title: str = "WARNINGS"
    ):
        """
        Display a list of warnings to the user.

        :param app: HummingbotApplication instance
        :param warnings: List of warning messages
        :param title: Title for the warnings section
        """
        if not warnings:
            return

        app.notify(f"\n⚠️  {title}:")
        for warning in warnings:
            app.notify(f"  • {warning}")

    @staticmethod
    def calculate_and_display_fees(
        app: Any,  # HummingbotApplication
        positions: List[Any],
        base_token: str = None,
        quote_token: str = None
    ) -> Dict[str, float]:
        """
        Calculate total fees across positions and display them.

        :param app: HummingbotApplication instance
        :param positions: List of positions with fee information
        :param base_token: Base token symbol (optional, extracted from positions if not provided)
        :param quote_token: Quote token symbol (optional, extracted from positions if not provided)
        :return: Dictionary of total fees by token
        """
        fees_by_token = {}

        for pos in positions:
            # Extract tokens from position if not provided
            if not base_token and hasattr(pos, 'base_token'):
                base_token = pos.base_token
            if not quote_token and hasattr(pos, 'quote_token'):
                quote_token = pos.quote_token

            # Skip if no fee attributes
            if not hasattr(pos, 'base_fee_amount'):
                continue

            # Use position tokens if available
            pos_base = getattr(pos, 'base_token', base_token)
            pos_quote = getattr(pos, 'quote_token', quote_token)

            if pos_base and pos_base not in fees_by_token:
                fees_by_token[pos_base] = 0
            if pos_quote and pos_quote not in fees_by_token:
                fees_by_token[pos_quote] = 0

            if pos_base:
                fees_by_token[pos_base] += getattr(pos, 'base_fee_amount', 0)
            if pos_quote:
                fees_by_token[pos_quote] += getattr(pos, 'quote_fee_amount', 0)

        # Display fees if any
        if any(amount > 0 for amount in fees_by_token.values()):
            app.notify("\nTotal Uncollected Fees:")
            for token, amount in fees_by_token.items():
                if amount > 0:
                    app.notify(f"  {token}: {amount:.6f}")

        return fees_by_token

    @staticmethod
    async def prompt_for_percentage(
        app: Any,  # HummingbotApplication
        prompt_text: str = "Enter percentage (0-100): ",
        default: float = 100.0
    ) -> Optional[float]:
        """
        Prompt user for a percentage value.

        :param app: HummingbotApplication instance
        :param prompt_text: Custom prompt text
        :param default: Default value if user presses enter
        :return: Percentage value or None if invalid
        """
        try:
            response = await app.app.prompt(prompt=prompt_text)

            if app.app.to_stop_config:
                return None

            if not response.strip():
                return default

            percentage = float(response)
            if 0 <= percentage <= 100:
                return percentage
            else:
                app.notify("Error: Percentage must be between 0 and 100")
                return None
        except ValueError:
            app.notify("Error: Please enter a valid number")
            return None

    @staticmethod
    async def enter_interactive_mode(app: Any) -> Any:
        """
        Enter interactive mode for prompting.

        :param app: HummingbotApplication instance
        :return: Context manager handle
        """
        app.placeholder_mode = True
        app.app.hide_input = True
        return app

    @staticmethod
    async def exit_interactive_mode(app: Any):
        """
        Exit interactive mode and restore normal prompt.

        :param app: HummingbotApplication instance
        """
        app.placeholder_mode = False
        app.app.hide_input = False
        app.app.change_prompt(prompt=">>> ")
