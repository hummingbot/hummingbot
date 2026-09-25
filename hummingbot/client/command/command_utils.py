"""
Shared utilities for gateway commands - UI and display functions.
"""
import asyncio
from typing import TYPE_CHECKING, Any, Dict, List

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
        Monitor a transaction until completion or timeout by polling order status.

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
            # Directly update order status for temporary connectors (not on clock)
            tracked_orders = connector.gateway_orders
            if tracked_orders:
                await connector.update_order_status(tracked_orders)

            order = connector.get_order(order_id)

            # Check if transaction is complete (success, failed, or cancelled)
            if order and order.is_done:
                # For LP operations (RANGE orders), is_done=True with state=OPEN means success
                # For swap orders, check is_filled
                is_success = order.is_filled or (not order.is_failure and not order.is_cancelled)

                result = {
                    "completed": True,
                    "success": is_success,
                    "failed": order.is_failure if order else False,
                    "cancelled": order.is_cancelled if order else False,
                    "order": order,
                    "elapsed_time": elapsed
                }

                # Show appropriate message
                if is_success:
                    app.notify("\n✓ Transaction completed successfully!")
                    if order.exchange_order_id:
                        app.notify(f"Transaction hash: {order.exchange_order_id}")
                elif order.is_failure:
                    app.notify("\n✗ Transaction failed")
                elif order.is_cancelled:
                    app.notify("\n✗ Transaction cancelled")

                return result

            # Special handling for PENDING_CREATE state (hardware wallet approval)
            if order and hasattr(order, 'current_state') and str(order.current_state) == "OrderState.PENDING_CREATE":
                if elapsed > 10 and not hardware_wallet_msg_shown:
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
    def handle_transaction_result(
        app: Any,
        result: Dict[str, Any],
        success_msg: str = "Transaction completed successfully!",
        failure_msg: str = "Transaction failed. Please try again.",
        timeout_msg: str = "Transaction timed out. Check your wallet for status."
    ) -> bool:
        """
        Handle transaction result and show appropriate message.

        :param app: HummingbotApplication instance (for notify method)
        :param result: Result dict from monitor_transaction_with_timeout
        :param success_msg: Message to show on success
        :param failure_msg: Message to show on failure
        :param timeout_msg: Message to show on timeout
        :return: True if successful, False otherwise
        """
        if result.get("completed") and result.get("success"):
            app.notify(f"\n✓ {success_msg}")
            return True
        elif result.get("failed") or (result.get("completed") and not result.get("success")):
            app.notify(f"\n✗ {failure_msg}")
            return False
        elif result.get("timeout"):
            app.notify(f"\n⚠️  {timeout_msg}")
            return False
        return False

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
        Shows EIP-1559 fields (maxFeePerGas, maxPriorityFeePerGas) if gasType is eip1559.

        :param app: HummingbotApplication instance (for notify method)
        :param fee_info: Fee information from estimate_transaction_fee
        """
        if not fee_info.get("success", False):
            app.notify("\nWarning: Could not estimate transaction fees")
            return

        denomination = fee_info.get("denomination", "")
        fee_in_native = fee_info["fee_in_native"]
        native_token = fee_info["native_token"]
        gas_type = fee_info.get("gas_type")

        app.notify("\nTransaction Fee Details:")

        # Show EIP-1559 fields if gas type is eip1559
        if gas_type == "eip1559":
            max_fee_per_gas = fee_info.get("max_fee_per_gas")
            max_priority_fee_per_gas = fee_info.get("max_priority_fee_per_gas")

            if max_fee_per_gas is not None and denomination:
                app.notify(f"  Max Fee Per Gas: {max_fee_per_gas:.4f} {denomination}")
            if max_priority_fee_per_gas is not None and denomination:
                app.notify(f"  Max Priority Fee Per Gas: {max_priority_fee_per_gas:.4f} {denomination}")
        else:
            # Show legacy gas price for non-EIP-1559
            fee_per_unit = fee_info.get("fee_per_unit")
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
