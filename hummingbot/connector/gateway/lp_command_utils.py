"""
LP-specific utilities for gateway liquidity provision commands.
"""
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

import pandas as pd

from hummingbot.client.command.command_utils import GatewayCommandUtils

if TYPE_CHECKING:
    from hummingbot.connector.gateway.gateway_lp import AMMPoolInfo, AMMPositionInfo, CLMMPoolInfo, CLMMPositionInfo


class LPCommandUtils:
    """Utility functions for LP commands."""

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

    @staticmethod
    async def prompt_for_position_selection(
        app: Any,  # HummingbotApplication
        positions: List[Any],
        prompt_text: str = None
    ) -> Optional[Any]:
        """
        Prompt user to select a position from a list.

        :param app: HummingbotApplication instance
        :param positions: List of positions to choose from
        :param prompt_text: Custom prompt text
        :return: Selected position or None if invalid selection
        """
        if not positions:
            return None

        if len(positions) == 1:
            return positions[0]

        prompt_text = prompt_text or f"Select position number (1-{len(positions)}): "

        try:
            position_num = await app.app.prompt(prompt=prompt_text)

            if app.app.to_stop_config:
                return None

            position_idx = int(position_num) - 1
            if 0 <= position_idx < len(positions):
                return positions[position_idx]
            else:
                app.notify("Error: Invalid position number")
                return None
        except ValueError:
            app.notify("Error: Please enter a valid number")
            return None

    @staticmethod
    def display_position_removal_impact(
        app: Any,  # HummingbotApplication
        position: Any,
        percentage: float,
        base_token: str,
        quote_token: str
    ) -> Tuple[float, float]:
        """
        Display the impact of removing liquidity from a position.

        :param app: HummingbotApplication instance
        :param position: Position to remove liquidity from
        :param percentage: Percentage to remove
        :param base_token: Base token symbol
        :param quote_token: Quote token symbol
        :return: Tuple of (base_to_receive, quote_to_receive)
        """
        factor = percentage / 100.0
        base_to_receive = position.base_token_amount * factor
        quote_to_receive = position.quote_token_amount * factor

        app.notify(f"\nRemoving {percentage}% liquidity")
        app.notify("You will receive:")
        app.notify(f"  {base_token}: {base_to_receive:.6f}")
        app.notify(f"  {quote_token}: {quote_to_receive:.6f}")

        # Show fees if applicable
        if hasattr(position, 'base_fee_amount') and percentage == 100:
            total_base_fees = position.base_fee_amount
            total_quote_fees = position.quote_fee_amount
            if total_base_fees > 0 or total_quote_fees > 0:
                app.notify("\nUncollected fees:")
                app.notify(f"  {base_token}: {total_base_fees:.6f}")
                app.notify(f"  {quote_token}: {total_quote_fees:.6f}")
                app.notify("Note: Fees will be automatically collected")

        return base_to_receive, quote_to_receive

    @staticmethod
    def display_pool_info(
        app: Any,  # HummingbotApplication
        pool_info: Union["AMMPoolInfo", "CLMMPoolInfo"],
        is_clmm: bool,
        base_token: str = None,
        quote_token: str = None
    ):
        """Display pool information in a user-friendly format"""
        app.notify("\n=== Pool Information ===")
        app.notify(f"Pool Address: {pool_info.address}")
        app.notify(f"Current Price: {pool_info.price:.6f}")
        app.notify(f"Fee: {pool_info.fee_pct}%")

        if is_clmm and hasattr(pool_info, 'active_bin_id'):
            app.notify(f"Active Bin ID: {pool_info.active_bin_id}")
            app.notify(f"Bin Step: {pool_info.bin_step}")

        app.notify("\nPool Reserves:")
        # Use actual token symbols if provided, otherwise fallback to Base/Quote
        base_label = base_token if base_token else "Base"
        quote_label = quote_token if quote_token else "Quote"
        app.notify(f"  {base_label}: {pool_info.base_token_amount:.6f}")
        app.notify(f"  {quote_label}: {pool_info.quote_token_amount:.6f}")

        # Calculate TVL if prices available
        tvl_estimate = (pool_info.base_token_amount * pool_info.price +
                        pool_info.quote_token_amount)
        app.notify(f"  TVL (in {quote_label}): ~{tvl_estimate:.2f}")

    @staticmethod
    def format_position_id(
        position: Union["AMMPositionInfo", "CLMMPositionInfo"]
    ) -> str:
        """Format position identifier for display"""
        if hasattr(position, 'address'):
            # CLMM position with unique address
            return GatewayCommandUtils.format_address_display(position.address)
        else:
            # AMM position identified by pool
            return GatewayCommandUtils.format_address_display(position.pool_address)

    @staticmethod
    def calculate_removal_amounts(
        position: Union["AMMPositionInfo", "CLMMPositionInfo"],
        percentage: float
    ) -> Tuple[float, float]:
        """Calculate token amounts to receive when removing liquidity"""
        factor = percentage / 100.0

        base_amount = position.base_token_amount * factor
        quote_amount = position.quote_token_amount * factor

        return base_amount, quote_amount

    @staticmethod
    def format_amm_position_display(
        position: Any,  # AMMPositionInfo
        base_token: str = None,
        quote_token: str = None
    ) -> str:
        """
        Format AMM position for display.

        :param position: AMM position info object
        :param base_token: Base token symbol override
        :param quote_token: Quote token symbol override
        :return: Formatted position string
        """
        # Use provided tokens or fall back to position data
        base = base_token or getattr(position, 'base_token', 'Unknown')
        quote = quote_token or getattr(position, 'quote_token', 'Unknown')

        lines = []
        lines.append("\n=== AMM Position ===")
        lines.append(f"Pool: {GatewayCommandUtils.format_address_display(position.pool_address)}")
        lines.append(f"Pair: {base}-{quote}")
        lines.append(f"Price: {position.price:.6f} {quote}/{base}")
        lines.append("\nHoldings:")
        lines.append(f"  {base}: {position.base_token_amount:.6f}")
        lines.append(f"  {quote}: {position.quote_token_amount:.6f}")
        lines.append(f"\nLP Tokens: {position.lp_token_amount:.6f}")

        return "\n".join(lines)

    @staticmethod
    def format_clmm_position_display(
        position: Any,  # CLMMPositionInfo
        base_token: str = None,
        quote_token: str = None
    ) -> str:
        """
        Format CLMM position for display.

        :param position: CLMM position info object
        :param base_token: Base token symbol override
        :param quote_token: Quote token symbol override
        :return: Formatted position string
        """
        # Use provided tokens or fall back to position data
        base = base_token or getattr(position, 'base_token', 'Unknown')
        quote = quote_token or getattr(position, 'quote_token', 'Unknown')

        lines = []
        lines.append("\n=== CLMM Position ===")
        lines.append(f"Position: {GatewayCommandUtils.format_address_display(position.address)}")
        lines.append(f"Pool: {GatewayCommandUtils.format_address_display(position.pool_address)}")
        lines.append(f"Pair: {base}-{quote}")
        lines.append(f"Current Price: {position.price:.6f} {quote}/{base}")

        # Price range
        lines.append("\nPrice Range:")
        lines.append(f"  Lower: {position.lower_price:.6f}")
        lines.append(f"  Upper: {position.upper_price:.6f}")

        # Range status
        if position.lower_price <= position.price <= position.upper_price:
            lines.append("  Status: ✓ In Range")
        else:
            if position.price < position.lower_price:
                lines.append("  Status: ⚠️  Below Range")
            else:
                lines.append("  Status: ⚠️  Above Range")

        # Holdings
        lines.append("\nHoldings:")
        lines.append(f"  {base}: {position.base_token_amount:.6f}")
        lines.append(f"  {quote}: {position.quote_token_amount:.6f}")

        # Fees if present
        if position.base_fee_amount > 0 or position.quote_fee_amount > 0:
            lines.append("\nUncollected Fees:")
            lines.append(f"  {base}: {position.base_fee_amount:.6f}")
            lines.append(f"  {quote}: {position.quote_fee_amount:.6f}")

        return "\n".join(lines)

    @staticmethod
    def display_positions_with_fees(
        app: Any,  # HummingbotApplication
        positions: List["CLMMPositionInfo"]
    ):
        """Display positions that have uncollected fees"""
        rows = []
        for i, pos in enumerate(positions):
            rows.append({
                "No": i + 1,
                "Position": LPCommandUtils.format_position_id(pos),
                "Pair": f"{pos.base_token}-{pos.quote_token}",
                "Base Fees": f"{pos.base_fee_amount:.6f}",
                "Quote Fees": f"{pos.quote_fee_amount:.6f}"
            })

        df = pd.DataFrame(rows)
        app.notify("\nPositions with Uncollected Fees:")
        lines = ["    " + line for line in df.to_string(index=False).split("\n")]
        app.notify("\n".join(lines))

    @staticmethod
    def calculate_total_fees(
        positions: List["CLMMPositionInfo"]
    ) -> Dict[str, float]:
        """Calculate total fees across positions grouped by token"""
        fees_by_token = {}

        for pos in positions:
            base_token = pos.base_token
            quote_token = pos.quote_token

            if base_token not in fees_by_token:
                fees_by_token[base_token] = 0
            if quote_token not in fees_by_token:
                fees_by_token[quote_token] = 0

            fees_by_token[base_token] += pos.base_fee_amount
            fees_by_token[quote_token] += pos.quote_fee_amount

        return fees_by_token

    @staticmethod
    def calculate_clmm_pair_amount(
        known_amount: float,
        pool_info: "CLMMPoolInfo",
        lower_price: float,
        upper_price: float,
        is_base_known: bool
    ) -> float:
        """
        Calculate the paired token amount for CLMM positions.
        This is a simplified calculation - actual implementation would use
        proper CLMM math based on the protocol.
        """
        current_price = pool_info.price

        if current_price <= lower_price:
            # All quote token
            return known_amount * current_price if is_base_known else 0
        elif current_price >= upper_price:
            # All base token
            return known_amount / current_price if not is_base_known else 0
        else:
            # Calculate based on liquidity distribution in range
            # This is protocol-specific and would need proper implementation
            price_ratio = (current_price - lower_price) / (upper_price - lower_price)

            if is_base_known:
                # Known base, calculate quote
                return known_amount * current_price * (1 - price_ratio)
            else:
                # Known quote, calculate base
                return known_amount / current_price * price_ratio
