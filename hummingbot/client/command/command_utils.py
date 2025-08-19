"""
Shared utilities for gateway commands - UI and display functions.
"""
import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from hummingbot.connector.gateway.gateway_base import GatewayBase


class GatewayCommandUtils:
    """Utility functions for gateway commands - UI and display functions."""

    @staticmethod
    def is_placeholder_wallet(wallet_address: str) -> bool:
        """
        Check if a wallet address is a placeholder.

        :param wallet_address: Wallet address to check
        :return: True if it's a placeholder, False otherwise
        """
        if not wallet_address:
            return False
        return "wallet-address" in wallet_address.lower()

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
                # Re-fetch the order to get the latest state
                order = connector.get_order(order_id)

                # Special case: if is_done but state is PENDING_CREATE, treat as success
                # This occurs when the transaction is confirmed immediately after submission
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
        token_data: Dict[str, Any],
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
        fee_in_native = fee_info["fee_in_native"]
        native_token = fee_info["native_token"]

        app.notify("\nTransaction Fee Details:")
        if fee_per_unit and denomination:
            app.notify(f"  Current Gas Price: {fee_per_unit:.4f} {denomination}")
        app.notify(f"  Estimated Gas Cost: ~{fee_in_native:.6f} {native_token}")

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
