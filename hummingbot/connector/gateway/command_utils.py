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
            return None, f"No default wallet found for {chain}. Please add one with 'gateway wallet add {chain}'"
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
                    app.notify("\n✓ Transaction completed successfully!")
                    if order.exchange_order_id:
                        app.notify(f"Transaction hash: {order.exchange_order_id}")
                elif order and order.is_failure:
                    app.notify("\n✗ Transaction failed")
                elif order and order.is_cancelled:
                    app.notify("\n✗ Transaction cancelled")

                return result

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
    def format_pool_info_display(
        pool_info: Any,  # Union[AMMPoolInfo, CLMMPoolInfo]
        base_symbol: str,
        quote_symbol: str
    ) -> List[Dict[str, str]]:
        """
        Format pool information for display.

        :param pool_info: Pool information object
        :param base_symbol: Base token symbol
        :param quote_symbol: Quote token symbol
        :return: List of formatted rows
        """
        rows = []

        rows.append({
            "Property": "Pool Address",
            "Value": GatewayCommandUtils.format_address_display(pool_info.address)
        })

        rows.append({
            "Property": "Current Price",
            "Value": f"{pool_info.price:.6f} {quote_symbol}/{base_symbol}"
        })

        rows.append({
            "Property": "Fee Tier",
            "Value": f"{pool_info.fee_pct}%"
        })

        rows.append({
            "Property": "Base Reserves",
            "Value": f"{pool_info.base_token_amount:.6f} {base_symbol}"
        })

        rows.append({
            "Property": "Quote Reserves",
            "Value": f"{pool_info.quote_token_amount:.6f} {quote_symbol}"
        })

        if hasattr(pool_info, 'active_bin_id'):
            rows.append({
                "Property": "Active Bin",
                "Value": str(pool_info.active_bin_id)
            })
        if hasattr(pool_info, 'bin_step'):
            rows.append({
                "Property": "Bin Step",
                "Value": str(pool_info.bin_step)
            })

        return rows

    @staticmethod
    def format_position_info_display(
        position: Any  # Union[AMMPositionInfo, CLMMPositionInfo]
    ) -> List[Dict[str, str]]:
        """
        Format position information for display.

        :param position: Position information object
        :return: List of formatted rows
        """
        rows = []

        if hasattr(position, 'address'):
            rows.append({
                "Property": "Position ID",
                "Value": GatewayCommandUtils.format_address_display(position.address)
            })

        rows.append({
            "Property": "Pool",
            "Value": GatewayCommandUtils.format_address_display(position.pool_address)
        })

        rows.append({
            "Property": "Base Amount",
            "Value": f"{position.base_token_amount:.6f}"
        })

        rows.append({
            "Property": "Quote Amount",
            "Value": f"{position.quote_token_amount:.6f}"
        })

        if hasattr(position, 'lower_price') and hasattr(position, 'upper_price'):
            rows.append({
                "Property": "Price Range",
                "Value": f"{position.lower_price:.6f} - {position.upper_price:.6f}"
            })

            if hasattr(position, 'base_fee_amount') and hasattr(position, 'quote_fee_amount'):
                if position.base_fee_amount > 0 or position.quote_fee_amount > 0:
                    rows.append({
                        "Property": "Uncollected Fees",
                        "Value": f"{position.base_fee_amount:.6f} / {position.quote_fee_amount:.6f}"
                    })

        elif hasattr(position, 'lp_token_amount'):
            rows.append({
                "Property": "LP Tokens",
                "Value": f"{position.lp_token_amount:.6f}"
            })

        return rows
