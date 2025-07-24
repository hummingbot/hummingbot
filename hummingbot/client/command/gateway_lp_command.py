#!/usr/bin/env python
import asyncio
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

import pandas as pd

from hummingbot.connector.gateway.command_utils import GatewayCommandUtils
from hummingbot.connector.gateway.common_types import ConnectorType, TransactionStatus, get_connector_type
from hummingbot.connector.gateway.gateway_lp import (
    AMMPoolInfo,
    AMMPositionInfo,
    CLMMPoolInfo,
    CLMMPositionInfo,
    GatewayLp,
)
from hummingbot.core.utils.async_utils import safe_ensure_future

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication  # noqa: F401


class GatewayLPCommand:
    """Handles gateway liquidity provision commands"""

    def gateway_lp(self, connector: Optional[str], action: Optional[str]):
        """
        Main entry point for LP commands.
        Routes to appropriate sub-command handler.
        """
        if not connector:
            self.notify("\nError: Connector is required")
            self.notify("Usage: gateway lp <connector> <action>")
            self.notify("\nExample: gateway lp uniswap/amm add-liquidity")
            return

        if not action:
            self.notify("\nAvailable LP actions:")
            self.notify("  add-liquidity     - Add liquidity to a pool")
            self.notify("  remove-liquidity  - Remove liquidity from a position")
            self.notify("  position-info     - View your liquidity positions")
            self.notify("  collect-fees      - Collect accumulated fees")
            self.notify("\nExample: gateway lp uniswap/amm add-liquidity")
            return

        # Route to appropriate handler
        if action == "add-liquidity":
            safe_ensure_future(self._add_liquidity(connector), loop=self.ev_loop)
        elif action == "remove-liquidity":
            safe_ensure_future(self._remove_liquidity(connector), loop=self.ev_loop)
        elif action == "position-info":
            safe_ensure_future(self._position_info(connector), loop=self.ev_loop)
        elif action == "collect-fees":
            safe_ensure_future(self._collect_fees(connector), loop=self.ev_loop)
        else:
            self.notify(f"\nError: Unknown action '{action}'")
            self.notify("Valid actions: add-liquidity, remove-liquidity, position-info, collect-fees")

    # Helper methods

    def _display_pool_info(
        self,
        pool_info: Union[AMMPoolInfo, CLMMPoolInfo],
        is_clmm: bool
    ):
        """Display pool information in a user-friendly format"""
        self.notify("\n=== Pool Information ===")
        self.notify(f"Pool Address: {pool_info.address}")
        self.notify(f"Current Price: {pool_info.price:.6f}")
        self.notify(f"Fee: {pool_info.fee_pct}%")

        if is_clmm and isinstance(pool_info, CLMMPoolInfo):
            self.notify(f"Active Bin ID: {pool_info.active_bin_id}")
            self.notify(f"Bin Step: {pool_info.bin_step}")

        self.notify("\nPool Reserves:")
        self.notify(f"  Base: {pool_info.base_token_amount:.6f}")
        self.notify(f"  Quote: {pool_info.quote_token_amount:.6f}")

        # Calculate TVL if prices available
        tvl_estimate = (pool_info.base_token_amount * pool_info.price +
                        pool_info.quote_token_amount)
        self.notify(f"  TVL (in quote): ~{tvl_estimate:.2f}")

    def _display_positions_table(
        self,
        positions: List[Union[AMMPositionInfo, CLMMPositionInfo]],
        is_clmm: bool
    ):
        """Display user positions in a formatted table"""
        if is_clmm:
            # CLMM positions table
            rows = []
            for i, pos in enumerate(positions):
                rows.append({
                    "No": i + 1,
                    "ID": self._format_position_id(pos),
                    "Pair": f"{pos.base_token}-{pos.quote_token}",
                    "Range": f"{pos.lower_price:.2f}-{pos.upper_price:.2f}",
                    "Value": f"{pos.base_token_amount:.4f} / {pos.quote_token_amount:.4f}",
                    "Fees": f"{pos.base_fee_amount:.4f} / {pos.quote_fee_amount:.4f}"
                })

            df = pd.DataFrame(rows)
            self.notify("\nYour Concentrated Liquidity Positions:")
        else:
            # AMM positions table
            rows = []
            for i, pos in enumerate(positions):
                rows.append({
                    "No": i + 1,
                    "Pool": self._format_position_id(pos),
                    "Pair": f"{pos.base_token}-{pos.quote_token}",
                    "LP Tokens": f"{pos.lp_token_amount:.6f}",
                    "Value": f"{pos.base_token_amount:.4f} / {pos.quote_token_amount:.4f}",
                    "Price": f"{pos.price:.6f}"
                })

            df = pd.DataFrame(rows)
            self.notify("\nYour Liquidity Positions:")

        lines = ["    " + line for line in df.to_string(index=False).split("\n")]
        self.notify("\n".join(lines))

    def _format_position_id(
        self,
        position: Union[AMMPositionInfo, CLMMPositionInfo]
    ) -> str:
        """Format position identifier for display"""
        if hasattr(position, 'address'):
            # CLMM position with unique address
            return GatewayCommandUtils.format_address_display(position.address)
        else:
            # AMM position identified by pool
            return GatewayCommandUtils.format_address_display(position.pool_address)

    def _calculate_removal_amounts(
        self,
        position: Union[AMMPositionInfo, CLMMPositionInfo],
        percentage: float
    ) -> Tuple[float, float]:
        """Calculate token amounts to receive when removing liquidity"""
        factor = percentage / 100.0

        base_amount = position.base_token_amount * factor
        quote_amount = position.quote_token_amount * factor

        return base_amount, quote_amount

    def _display_positions_summary(
        self,
        positions: List[Union[AMMPositionInfo, CLMMPositionInfo]],
        is_clmm: bool
    ):
        """Display summary of all positions"""
        total_value_base = 0
        total_value_quote = 0
        total_fees_base = 0
        total_fees_quote = 0

        # Calculate totals
        for pos in positions:
            total_value_base += pos.base_token_amount
            total_value_quote += pos.quote_token_amount

            if hasattr(pos, 'base_fee_amount'):
                total_fees_base += pos.base_fee_amount
                total_fees_quote += pos.quote_fee_amount

        self.notify(f"\nTotal Positions: {len(positions)}")
        self.notify("Total Value Locked:")

        # Group by token pair
        positions_by_pair = {}
        for pos in positions:
            pair = f"{pos.base_token}-{pos.quote_token}"
            if pair not in positions_by_pair:
                positions_by_pair[pair] = []
            positions_by_pair[pair].append(pos)

        for pair, pair_positions in positions_by_pair.items():
            base_token, quote_token = pair.split("-")
            pair_base_total = sum(p.base_token_amount for p in pair_positions)
            pair_quote_total = sum(p.quote_token_amount for p in pair_positions)

            self.notify(f"  {pair}: {pair_base_total:.6f} {base_token} / "
                        f"{pair_quote_total:.6f} {quote_token}")

        if total_fees_base > 0 or total_fees_quote > 0:
            self.notify("\nTotal Uncollected Fees:")
            for pair, pair_positions in positions_by_pair.items():
                if any(hasattr(p, 'base_fee_amount') for p in pair_positions):
                    base_token, quote_token = pair.split("-")
                    pair_fees_base = sum(getattr(p, 'base_fee_amount', 0) for p in pair_positions)
                    pair_fees_quote = sum(getattr(p, 'quote_fee_amount', 0) for p in pair_positions)

                    if pair_fees_base > 0 or pair_fees_quote > 0:
                        self.notify(f"  {pair}: {pair_fees_base:.6f} {base_token} / "
                                    f"{pair_fees_quote:.6f} {quote_token}")

        # Display positions table
        self._display_positions_table(positions, is_clmm)

    def _display_positions_with_fees(
        self,
        positions: List[CLMMPositionInfo]
    ):
        """Display positions that have uncollected fees"""
        rows = []
        for i, pos in enumerate(positions):
            rows.append({
                "No": i + 1,
                "Position": self._format_position_id(pos),
                "Pair": f"{pos.base_token}-{pos.quote_token}",
                "Base Fees": f"{pos.base_fee_amount:.6f}",
                "Quote Fees": f"{pos.quote_fee_amount:.6f}"
            })

        df = pd.DataFrame(rows)
        self.notify("\nPositions with Uncollected Fees:")
        lines = ["    " + line for line in df.to_string(index=False).split("\n")]
        self.notify("\n".join(lines))

    def _calculate_total_fees(
        self,
        positions: List[CLMMPositionInfo]
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

    def _calculate_clmm_pair_amount(
        self,
        known_amount: float,
        pool_info: CLMMPoolInfo,
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

    async def _display_position_details(
        self,
        connector: str,
        position: Union[AMMPositionInfo, CLMMPositionInfo],
        is_clmm: bool,
        chain: str,
        network: str,
        wallet_address: str
    ):
        """Display detailed information for a specific position"""
        self.notify("\n=== Position Details ===")

        # Basic info
        self.notify(f"Position ID: {self._format_position_id(position)}")
        self.notify(f"Pool: {position.pool_address}")
        self.notify(f"Pair: {position.base_token}-{position.quote_token}")

        # Token amounts
        self.notify("\nCurrent Holdings:")
        self.notify(f"  {position.base_token}: {position.base_token_amount:.6f}")
        self.notify(f"  {position.quote_token}: {position.quote_token_amount:.6f}")

        # Show token amounts only - no value calculations

        # CLMM specific details
        if is_clmm and isinstance(position, CLMMPositionInfo):
            self.notify("\nPrice Range:")
            self.notify(f"  Lower: {position.lower_price:.6f}")
            self.notify(f"  Upper: {position.upper_price:.6f}")
            self.notify(f"  Current: {position.price:.6f}")

            # Check if in range
            if position.lower_price <= position.price <= position.upper_price:
                self.notify("  Status: ✓ In Range")
            else:
                if position.price < position.lower_price:
                    self.notify("  Status: ⚠️  Below Range")
                else:
                    self.notify("  Status: ⚠️  Above Range")

            # Show fees
            if position.base_fee_amount > 0 or position.quote_fee_amount > 0:
                self.notify("\nUncollected Fees:")
                self.notify(f"  {position.base_token}: {position.base_fee_amount:.6f}")
                self.notify(f"  {position.quote_token}: {position.quote_fee_amount:.6f}")

        # AMM specific details
        elif isinstance(position, AMMPositionInfo):
            self.notify(f"\nLP Token Balance: {position.lp_token_amount:.6f}")

            # Calculate pool share (would need total supply)
            # This is a placeholder calculation
            self.notify(f"Pool Share: ~{position.lp_token_amount / 1000:.2%}")

        # Current price info
        self.notify(f"\nCurrent Pool Price: {position.price:.6f}")

        # Additional pool info
        try:
            trading_pair = f"{position.base_token}-{position.quote_token}"

            # Create temporary connector to fetch pool info
            lp_connector = GatewayLp(
                client_config_map=self.client_config_map,
                connector_name=connector,
                chain=chain,
                network=network,
                address=wallet_address,
                trading_pairs=[trading_pair]
            )
            await lp_connector.start_network()

            pool_info = await lp_connector.get_pool_info(trading_pair)
            if pool_info:
                self.notify("\nPool Statistics:")
                self.notify(f"  Total Liquidity: {pool_info.base_token_amount:.2f} / "
                            f"{pool_info.quote_token_amount:.2f}")
                self.notify(f"  Fee Tier: {pool_info.fee_pct}%")

            await lp_connector.stop_network()

        except Exception as e:
            self.logger().debug(f"Could not fetch additional pool info: {e}")

    async def _monitor_fee_collection_tx(
        self,
        connector: GatewayLp,
        tx_hash: str,
        timeout: float = 60.0
    ) -> Dict[str, Any]:
        """Monitor a fee collection transaction"""
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                tx_status = await self._get_gateway_instance().get_transaction_status(
                    connector.chain,
                    connector.network,
                    tx_hash
                )

                if tx_status.get("txStatus") == TransactionStatus.CONFIRMED.value:
                    return {"success": True, "tx_hash": tx_hash}
                elif tx_status.get("txStatus") == TransactionStatus.FAILED.value:
                    return {"success": False, "error": "Transaction failed"}

            except Exception as e:
                self.logger().debug(f"Error checking tx status: {e}")

            await asyncio.sleep(2.0)

        return {"success": False, "error": "Transaction timeout"}

    # Position Info Implementation
    async def _position_info(
        self,  # type: HummingbotApplication
        connector: str
    ):
        """
        Display detailed information about user's liquidity positions.
        Includes summary and detailed views.
        """
        try:
            # 1. Validate connector and get chain/network info
            if "/" not in connector:
                self.notify(f"Error: Invalid connector format '{connector}'")
                return

            chain, network, error = await GatewayCommandUtils.get_connector_chain_network(
                self._get_gateway_instance(), connector
            )
            if error:
                self.notify(f"Error: {error}")
                return

            # 2. Get wallet address
            wallet_address, error = await GatewayCommandUtils.get_default_wallet(
                self._get_gateway_instance(), chain
            )
            if error:
                self.notify(f"Error: {error}")
                return

            # 3. Determine connector type
            connector_type = get_connector_type(connector)
            is_clmm = connector_type == ConnectorType.CLMM

            self.notify(f"\n=== Liquidity Positions on {connector} ===")
            self.notify(f"Chain: {chain}")
            self.notify(f"Network: {network}")
            self.notify(f"Wallet: {GatewayCommandUtils.format_address_display(wallet_address)}")

            # 4. Create LP connector instance to fetch positions
            lp_connector = GatewayLp(
                client_config_map=self.client_config_map,
                connector_name=connector,
                chain=chain,
                network=network,
                address=wallet_address,
                trading_pairs=[]  # Will be populated as needed
            )
            await lp_connector.start_network()

            try:
                # 5. Get user's positions
                self.notify("\nFetching your liquidity positions...")
                positions = await lp_connector.get_user_positions()

                if not positions:
                    self.notify("\nNo liquidity positions found for this connector")
                    return

                # 5. Display positions summary
                self._display_positions_summary(positions, is_clmm)

                # 6. Enter interactive mode for detailed view
                if len(positions) > 1:
                    self.placeholder_mode = True
                    self.app.hide_input = True

                    try:
                        view_details = await self.app.prompt(
                            prompt="\nView detailed position info? (Yes/No): "
                        )

                        if view_details.lower() in ["y", "yes"]:
                            position_num = await self.app.prompt(
                                prompt=f"Select position number (1-{len(positions)}): "
                            )

                            try:
                                position_idx = int(position_num) - 1
                                if 0 <= position_idx < len(positions):
                                    selected_position = positions[position_idx]
                                    await self._display_position_details(
                                        connector, selected_position, is_clmm,
                                        chain, network, wallet_address
                                    )
                                else:
                                    self.notify("Error: Invalid position number")
                            except ValueError:
                                self.notify("Error: Please enter a valid number")

                    finally:
                        self.placeholder_mode = False
                        self.app.hide_input = False
                        self.app.change_prompt(prompt=">>> ")
                else:
                    # Single position - show details directly
                    await self._display_position_details(
                        connector, positions[0], is_clmm,
                        chain, network, wallet_address
                    )

            finally:
                # Always stop the connector
                if lp_connector:
                    await lp_connector.stop_network()

        except Exception as e:
            self.logger().error(f"Error in position info: {e}", exc_info=True)
            self.notify(f"Error: {str(e)}")

    # Add Liquidity Implementation
    async def _add_liquidity(
        self,  # type: HummingbotApplication
        connector: str
    ):
        """
        Interactive flow for adding liquidity to a pool.
        Supports both AMM and CLMM protocols.
        """
        try:
            # 1. Validate connector and get chain/network info
            if "/" not in connector:
                self.notify(f"Error: Invalid connector format '{connector}'. Use format like 'uniswap/amm'")
                return

            chain, network, error = await GatewayCommandUtils.get_connector_chain_network(
                self._get_gateway_instance(), connector
            )
            if error:
                self.notify(f"Error: {error}")
                return

            # 2. Get wallet address
            wallet_address, error = await GatewayCommandUtils.get_default_wallet(
                self._get_gateway_instance(), chain
            )
            if error:
                self.notify(f"Error: {error}")
                return

            # 3. Determine connector type
            connector_type = get_connector_type(connector)
            is_clmm = connector_type == ConnectorType.CLMM

            self.notify(f"\n=== Add Liquidity to {connector} ===")
            self.notify(f"Chain: {chain}")
            self.notify(f"Network: {network}")
            self.notify(f"Wallet: {GatewayCommandUtils.format_address_display(wallet_address)}")
            self.notify(f"Type: {'Concentrated Liquidity' if is_clmm else 'Standard AMM'}")

            # 4. Enter interactive mode
            self.placeholder_mode = True
            self.app.hide_input = True

            try:
                # 5. Get trading pair
                pair = await self.app.prompt(
                    prompt="Enter trading pair (e.g., ETH-USDC): "
                )
                if self.app.to_stop_config or not pair:
                    self.notify("Add liquidity cancelled")
                    return

                base_token, quote_token = GatewayCommandUtils.parse_trading_pair(pair)
                if not base_token or not quote_token:
                    self.notify("Error: Invalid trading pair format")
                    return

                trading_pair = f"{base_token}-{quote_token}"

                # 6. Create LP connector instance and start network
                lp_connector = GatewayLp(
                    client_config_map=self.client_config_map,
                    connector_name=connector,
                    chain=chain,
                    network=network,
                    address=wallet_address,
                    trading_pairs=[trading_pair]
                )
                await lp_connector.start_network()

                # 7. Get and display pool info
                self.notify(f"\nFetching pool information for {trading_pair}...")
                pool_info = await lp_connector.get_pool_info(trading_pair)

                if not pool_info:
                    self.notify(f"Error: Could not find pool for {trading_pair}")
                    await lp_connector.stop_network()
                    return

                # Display pool information
                self._display_pool_info(pool_info, is_clmm)

                # 8. Get position parameters based on type
                position_params = {}
                lower_price = None
                upper_price = None

                if is_clmm:
                    # For CLMM, get price range
                    current_price = pool_info.price

                    # Ask for price range method
                    range_method = await self.app.prompt(
                        prompt="\nSelect price range method:\n"
                               "1. Percentage from current price (recommended)\n"
                               "2. Custom price range\n"
                               "Enter choice (1 or 2): "
                    )

                    if range_method == "1":
                        spread_pct = await self.app.prompt(
                            prompt="Enter range width percentage (e.g., 10 for ±10%): "
                        )
                        try:
                            spread_pct = float(spread_pct)
                            position_params['spread_pct'] = spread_pct

                            # Calculate and show price range
                            lower_price = current_price * (1 - spread_pct / 100)
                            upper_price = current_price * (1 + spread_pct / 100)

                            self.notify("\nPrice range:")
                            self.notify(f"  Lower: {lower_price:.6f}")
                            self.notify(f"  Current: {current_price:.6f}")
                            self.notify(f"  Upper: {upper_price:.6f}")

                        except ValueError:
                            self.notify("Error: Invalid percentage")
                            return
                    else:
                        # Custom price range
                        lower_price_str = await self.app.prompt(
                            prompt=f"Enter lower price (current: {current_price:.6f}): "
                        )
                        upper_price_str = await self.app.prompt(
                            prompt=f"Enter upper price (current: {current_price:.6f}): "
                        )

                        try:
                            lower_price = float(lower_price_str)
                            upper_price = float(upper_price_str)

                            if lower_price >= upper_price:
                                self.notify("Error: Lower price must be less than upper price")
                                return

                            if lower_price > current_price or upper_price < current_price:
                                self.notify("Warning: Current price is outside your range!")

                            # Calculate spread percentage for the connector
                            mid_price = (lower_price + upper_price) / 2
                            spread_pct = ((upper_price - lower_price) / (2 * mid_price)) * 100
                            position_params['spread_pct'] = spread_pct

                        except ValueError:
                            self.notify("Error: Invalid price values")
                            return

                # 9. Get token amounts
                self.notify("\nEnter token amounts to add (press Enter to skip):")

                base_amount_str = await self.app.prompt(
                    prompt=f"Amount of {base_token} (optional): "
                )
                quote_amount_str = await self.app.prompt(
                    prompt=f"Amount of {quote_token} (optional): "
                )

                # Parse amounts
                base_amount = None
                quote_amount = None

                if base_amount_str:
                    try:
                        base_amount = float(base_amount_str)
                    except ValueError:
                        self.notify("Error: Invalid base token amount")
                        return

                if quote_amount_str:
                    try:
                        quote_amount = float(quote_amount_str)
                    except ValueError:
                        self.notify("Error: Invalid quote token amount")
                        return

                # Validate at least one amount provided
                if base_amount is None and quote_amount is None:
                    self.notify("Error: Must provide at least one token amount")
                    return

                # 10. Calculate optimal amounts if only one provided
                if is_clmm:
                    # For CLMM, calculate based on price range
                    if base_amount and not quote_amount:
                        # Calculate quote amount based on range and liquidity distribution
                        quote_amount = self._calculate_clmm_pair_amount(
                            base_amount, pool_info, lower_price, upper_price, True
                        )
                    elif quote_amount and not base_amount:
                        base_amount = self._calculate_clmm_pair_amount(
                            quote_amount, pool_info, lower_price, upper_price, False
                        )
                else:
                    # For AMM, maintain pool ratio
                    pool_ratio = pool_info.base_token_amount / pool_info.quote_token_amount

                    if base_amount and not quote_amount:
                        quote_amount = base_amount / pool_ratio
                    elif quote_amount and not base_amount:
                        base_amount = quote_amount * pool_ratio

                # Display calculated amounts
                self.notify("\nToken amounts to add:")
                self.notify(f"  {base_token}: {base_amount:.6f}")
                self.notify(f"  {quote_token}: {quote_amount:.6f}")

                # 11. Check balances and calculate impact
                tokens_to_check = [base_token, quote_token]
                native_token = lp_connector.native_currency or chain.upper()

                current_balances = await GatewayCommandUtils.get_wallet_balances(
                    gateway_client=self._get_gateway_instance(),
                    chain=chain,
                    network=network,
                    wallet_address=wallet_address,
                    tokens_to_check=tokens_to_check,
                    native_token=native_token
                )

                # 12. Estimate transaction fee
                self.notify("\nEstimating transaction fees...")
                fee_info = await GatewayCommandUtils.estimate_transaction_fee(
                    self._get_gateway_instance(),
                    chain,
                    network,
                    transaction_type="add_liquidity"
                )

                gas_fee_estimate = fee_info.get("fee_in_native", 0) if fee_info.get("success", False) else 0

                # 13. Calculate balance changes
                balance_changes = {}
                if base_amount:
                    balance_changes[base_token] = -base_amount
                if quote_amount:
                    balance_changes[quote_token] = -quote_amount

                # 14. Display balance impact
                warnings = []
                GatewayCommandUtils.display_balance_impact_table(
                    app=self,
                    wallet_address=wallet_address,
                    current_balances=current_balances,
                    balance_changes=balance_changes,
                    native_token=native_token,
                    gas_fee=gas_fee_estimate,
                    warnings=warnings,
                    title="Balance Impact After Adding Liquidity"
                )

                # 15. Display transaction fee details
                GatewayCommandUtils.display_transaction_fee_details(app=self, fee_info=fee_info)

                # 16. Show position details
                if is_clmm:
                    # For CLMM, show position details
                    self.notify("\nPosition will be created with:")
                    self.notify(f"  Range: {lower_price:.6f} - {upper_price:.6f}")
                    self.notify(f"  Current price: {pool_info.price:.6f}")
                else:
                    # For AMM, just show pool info
                    self.notify(f"\nAdding liquidity to pool at current price: {pool_info.price:.6f}")

                # 17. Display warnings
                if warnings:
                    self.notify("\n⚠️  WARNINGS:")
                    for warning in warnings:
                        self.notify(f"  • {warning}")

                # 18. Show slippage info
                connector_config = await GatewayCommandUtils.get_connector_config(
                    self._get_gateway_instance(), connector
                )
                slippage_pct = connector_config.get("slippagePct", 1.0)
                self.notify(f"\nSlippage tolerance: {slippage_pct}%")

                # 19. Confirmation
                confirm = await self.app.prompt(
                    prompt="\nDo you want to add liquidity? (Yes/No) >>> "
                )

                if confirm.lower() not in ["y", "yes"]:
                    self.notify("Add liquidity cancelled")
                    return

                # 20. Execute transaction
                self.notify("\nAdding liquidity...")

                # Create order ID and execute
                if is_clmm:
                    order_id = lp_connector.open_position(
                        trading_pair=trading_pair,
                        price=pool_info.price,
                        spread_pct=position_params['spread_pct'],
                        base_token_amount=base_amount,
                        quote_token_amount=quote_amount,
                        slippage_pct=slippage_pct
                    )
                else:
                    order_id = lp_connector.open_position(
                        trading_pair=trading_pair,
                        price=pool_info.price,
                        base_token_amount=base_amount,
                        quote_token_amount=quote_amount,
                        slippage_pct=slippage_pct
                    )

                self.notify(f"Transaction submitted. Order ID: {order_id}")
                self.notify("Monitoring transaction status...")

                # 21. Monitor transaction
                result = await GatewayCommandUtils.monitor_transaction_with_timeout(
                    app=self,
                    connector=lp_connector,
                    order_id=order_id,
                    timeout=120.0,  # 2 minutes for LP transactions
                    check_interval=2.0,
                    pending_msg_delay=5.0
                )

                if result["completed"] and result["success"]:
                    self.notify("\n✓ Liquidity added successfully!")
                    self.notify("Use 'gateway lp position-info' to view your position")

                # Stop the connector
                await lp_connector.stop_network()

            finally:
                self.placeholder_mode = False
                self.app.hide_input = False
                self.app.change_prompt(prompt=">>> ")

        except Exception as e:
            self.logger().error(f"Error in add liquidity: {e}", exc_info=True)
            self.notify(f"Error: {str(e)}")

    # Remove Liquidity Implementation
    async def _remove_liquidity(
        self,  # type: HummingbotApplication
        connector: str
    ):
        """
        Interactive flow for removing liquidity from positions.
        Supports partial removal and complete position closing.
        """
        try:
            # 1. Validate connector and get chain/network info
            if "/" not in connector:
                self.notify(f"Error: Invalid connector format '{connector}'")
                return

            chain, network, error = await GatewayCommandUtils.get_connector_chain_network(
                self._get_gateway_instance(), connector
            )
            if error:
                self.notify(f"Error: {error}")
                return

            # 2. Get wallet address
            wallet_address, error = await GatewayCommandUtils.get_default_wallet(
                self._get_gateway_instance(), chain
            )
            if error:
                self.notify(f"Error: {error}")
                return

            # 3. Determine connector type
            connector_type = get_connector_type(connector)
            is_clmm = connector_type == ConnectorType.CLMM

            self.notify(f"\n=== Remove Liquidity from {connector} ===")
            self.notify(f"Chain: {chain}")
            self.notify(f"Network: {network}")
            self.notify(f"Wallet: {GatewayCommandUtils.format_address_display(wallet_address)}")

            # 4. Create LP connector instance (needed for getting positions)
            lp_connector = GatewayLp(
                client_config_map=self.client_config_map,
                connector_name=connector,
                chain=chain,
                network=network,
                address=wallet_address,
                trading_pairs=[]  # Will be populated after we get positions
            )
            await lp_connector.start_network()

            try:
                # 5. Get user's positions using the connector
                self.notify("\nFetching your liquidity positions...")
                positions = await lp_connector.get_user_positions()

                if not positions:
                    self.notify("No liquidity positions found for this connector")
                    return

                # 5. Display positions
                self._display_positions_table(positions, is_clmm)

                # 6. Enter interactive mode
                self.placeholder_mode = True
                self.app.hide_input = True

                try:
                    # 7. Let user select position
                    if len(positions) == 1:
                        selected_position = positions[0]
                        self.notify(f"\nSelected position: {self._format_position_id(selected_position)}")
                    else:
                        position_num = await self.app.prompt(
                            prompt=f"\nSelect position number (1-{len(positions)}): "
                        )

                        try:
                            position_idx = int(position_num) - 1
                            if 0 <= position_idx < len(positions):
                                selected_position = positions[position_idx]
                            else:
                                self.notify("Error: Invalid position number")
                                return
                        except ValueError:
                            self.notify("Error: Please enter a valid number")
                            return

                    # 8. Get removal percentage
                    percentage_str = await self.app.prompt(
                        prompt="\nPercentage to remove (0-100, default 100): "
                    )

                    if not percentage_str:
                        percentage = 100.0
                    else:
                        try:
                            percentage = float(percentage_str)
                            if percentage <= 0 or percentage > 100:
                                self.notify("Error: Percentage must be between 0 and 100")
                                return
                        except ValueError:
                            self.notify("Error: Invalid percentage")
                            return

                    # 9. For 100% removal, ask about closing position
                    close_position = False
                    if percentage == 100.0 and is_clmm:
                        close_prompt = await self.app.prompt(
                            prompt="\nCompletely close this position? (Yes/No): "
                        )
                        close_position = close_prompt.lower() in ["y", "yes"]

                    # 10. Calculate tokens to receive
                    base_to_receive, quote_to_receive = self._calculate_removal_amounts(
                        selected_position, percentage
                    )

                    self.notify("\nYou will receive:")
                    self.notify(f"  {selected_position.base_token}: {base_to_receive:.6f}")
                    self.notify(f"  {selected_position.quote_token}: {quote_to_receive:.6f}")

                    # Show fees if any
                    if hasattr(selected_position, 'base_fee_amount'):
                        total_base_fees = selected_position.base_fee_amount
                        total_quote_fees = selected_position.quote_fee_amount
                        if total_base_fees > 0 or total_quote_fees > 0:
                            self.notify("\nUncollected fees:")
                            self.notify(f"  {selected_position.base_token}: {total_base_fees:.6f}")
                            self.notify(f"  {selected_position.quote_token}: {total_quote_fees:.6f}")
                            self.notify("Note: Fees will be automatically collected")

                    # 11. Update LP connector with the selected trading pair
                    trading_pair = f"{selected_position.base_token}-{selected_position.quote_token}"
                    lp_connector._trading_pairs = [trading_pair]
                    # Reload token data for the selected pair if needed
                    await lp_connector.load_token_data()

                    # 12. Check balances and estimate fees
                    tokens_to_check = [selected_position.base_token, selected_position.quote_token]
                    native_token = lp_connector.native_currency or chain.upper()

                    current_balances = await GatewayCommandUtils.get_wallet_balances(
                        gateway_client=self._get_gateway_instance(),
                        chain=chain,
                        network=network,
                        wallet_address=wallet_address,
                        tokens_to_check=tokens_to_check,
                        native_token=native_token
                    )

                    # 13. Estimate transaction fee
                    self.notify("\nEstimating transaction fees...")
                    tx_type = "close_position" if close_position else "remove_liquidity"
                    fee_info = await GatewayCommandUtils.estimate_transaction_fee(
                        self._get_gateway_instance(),
                        chain,
                        network,
                        transaction_type=tx_type
                    )

                    gas_fee_estimate = fee_info.get("fee_in_native", 0) if fee_info.get("success", False) else 0

                    # 14. Calculate balance changes (positive for receiving tokens)
                    balance_changes = {}
                    balance_changes[selected_position.base_token] = base_to_receive
                    balance_changes[selected_position.quote_token] = quote_to_receive

                    # Add fees to balance changes
                    if hasattr(selected_position, 'base_fee_amount'):
                        balance_changes[selected_position.base_token] += selected_position.base_fee_amount
                        balance_changes[selected_position.quote_token] += selected_position.quote_fee_amount

                    # 15. Display balance impact
                    warnings = []
                    GatewayCommandUtils.display_balance_impact_table(
                        app=self,
                        wallet_address=wallet_address,
                        current_balances=current_balances,
                        balance_changes=balance_changes,
                        native_token=native_token,
                        gas_fee=gas_fee_estimate,
                        warnings=warnings,
                        title="Balance Impact After Removing Liquidity"
                    )

                    # 16. Display transaction fee details
                    GatewayCommandUtils.display_transaction_fee_details(app=self, fee_info=fee_info)

                    # 17. Display warnings
                    if warnings:
                        self.notify("\n⚠️  WARNINGS:")
                        for warning in warnings:
                            self.notify(f"  • {warning}")

                    # 18. Confirmation
                    action_text = "close position" if close_position else f"remove {percentage}% liquidity"
                    confirm = await self.app.prompt(
                        prompt=f"\nDo you want to {action_text}? (Yes/No) >>> "
                    )

                    if confirm.lower() not in ["y", "yes"]:
                        self.notify("Remove liquidity cancelled")
                        return

                    # 20. Execute transaction
                    self.notify(f"\n{'Closing position' if close_position else 'Removing liquidity'}...")

                    # Create order ID and execute
                    position_address = getattr(selected_position, 'address', None) or getattr(selected_position, 'pool_address', None)

                    order_id = lp_connector.close_position(
                        trading_pair=trading_pair,
                        position_address=position_address,
                        percentage=percentage if not close_position else 100.0
                    )

                    self.notify(f"Transaction submitted. Order ID: {order_id}")
                    self.notify("Monitoring transaction status...")

                    # 21. Monitor transaction
                    result = await GatewayCommandUtils.monitor_transaction_with_timeout(
                        app=self,
                        connector=lp_connector,
                        order_id=order_id,
                        timeout=120.0,
                        check_interval=2.0,
                        pending_msg_delay=5.0
                    )

                    if result["completed"] and result["success"]:
                        if close_position:
                            self.notify("\n✓ Position closed successfully!")
                        else:
                            self.notify(f"\n✓ {percentage}% liquidity removed successfully!")
                            self.notify("Use 'gateway lp position-info' to view remaining position")

                finally:
                    self.placeholder_mode = False
                    self.app.hide_input = False
                    self.app.change_prompt(prompt=">>> ")

            finally:
                # Always stop the connector
                if lp_connector:
                    await lp_connector.stop_network()

        except Exception as e:
            self.logger().error(f"Error in remove liquidity: {e}", exc_info=True)
            self.notify(f"Error: {str(e)}")

    # Collect Fees Implementation
    async def _collect_fees(
        self,  # type: HummingbotApplication
        connector: str
    ):
        """
        Interactive flow for collecting accumulated fees from positions.
        Only applicable for CLMM positions that track fees separately.
        """
        try:
            # 1. Validate connector and get chain/network info
            if "/" not in connector:
                self.notify(f"Error: Invalid connector format '{connector}'")
                return

            chain, network, error = await GatewayCommandUtils.get_connector_chain_network(
                self._get_gateway_instance(), connector
            )
            if error:
                self.notify(f"Error: {error}")
                return

            # 2. Check if connector supports fee collection
            connector_type = get_connector_type(connector)
            if connector_type != ConnectorType.CLMM:
                self.notify("Fee collection is only available for concentrated liquidity positions")
                return

            # 3. Get wallet address
            wallet_address, error = await GatewayCommandUtils.get_default_wallet(
                self._get_gateway_instance(), chain
            )
            if error:
                self.notify(f"Error: {error}")
                return

            self.notify(f"\n=== Collect Fees from {connector} ===")
            self.notify(f"Chain: {chain}")
            self.notify(f"Network: {network}")
            self.notify(f"Wallet: {GatewayCommandUtils.format_address_display(wallet_address)}")

            # 4. Create LP connector instance to fetch positions
            lp_connector = GatewayLp(
                client_config_map=self.client_config_map,
                connector_name=connector,
                chain=chain,
                network=network,
                address=wallet_address,
                trading_pairs=[]  # Will be populated as needed
            )
            await lp_connector.start_network()

            try:
                # 5. Get positions with fees
                self.notify("\nFetching positions with uncollected fees...")
                all_positions = await lp_connector.get_user_positions()

                # Filter positions with fees > 0
                positions_with_fees = [
                    pos for pos in all_positions
                    if hasattr(pos, 'base_fee_amount') and
                    (pos.base_fee_amount > 0 or pos.quote_fee_amount > 0)
                ]

                if not positions_with_fees:
                    self.notify("\nNo uncollected fees found in your positions")
                    return

                # 5. Display positions with fees
                self._display_positions_with_fees(positions_with_fees)

                # 6. Calculate total fees
                total_fees = self._calculate_total_fees(positions_with_fees)

                self.notify("\nTotal fees to collect:")
                for token, amount in total_fees.items():
                    if amount > 0:
                        self.notify(f"  {token}: {amount:.6f}")

                # 7. Enter interactive mode
                self.placeholder_mode = True
                self.app.hide_input = True

                try:
                    # 8. Ask which positions to collect from
                    if len(positions_with_fees) == 1:
                        selected_positions = positions_with_fees
                        self.notify("\nCollecting fees from 1 position")
                    else:
                        collect_choice = await self.app.prompt(
                            prompt=f"\nCollect fees from:\n"
                                   f"1. All positions ({len(positions_with_fees)} positions)\n"
                                   f"2. Select specific positions\n"
                                   f"Enter choice (1 or 2): "
                        )

                        if collect_choice == "1":
                            selected_positions = positions_with_fees
                        elif collect_choice == "2":
                            # Let user select specific positions
                            position_nums = await self.app.prompt(
                                prompt="Enter position numbers to collect from "
                                       "(comma-separated, e.g., 1,3,5): "
                            )

                            try:
                                indices = [int(x.strip()) - 1 for x in position_nums.split(",")]
                                selected_positions = [
                                    positions_with_fees[i] for i in indices
                                    if 0 <= i < len(positions_with_fees)
                                ]

                                if not selected_positions:
                                    self.notify("Error: No valid positions selected")
                                    return

                            except (ValueError, IndexError):
                                self.notify("Error: Invalid position selection")
                                return
                        else:
                            self.notify("Invalid choice")
                            return

                    # 9. Calculate fees to collect from selected positions
                    fees_to_collect = self._calculate_total_fees(selected_positions)

                    self.notify(f"\nFees to collect from {len(selected_positions)} position(s):")
                    for token, amount in fees_to_collect.items():
                        if amount > 0:
                            self.notify(f"  {token}: {amount:.6f}")

                    # 10. Check gas costs vs fees
                    # Get native token for gas estimation
                    native_token = lp_connector.native_currency or chain.upper()

                    # Update connector with the trading pairs from selected positions
                    trading_pairs = list(set(
                        f"{pos.base_token}-{pos.quote_token}"
                        for pos in selected_positions
                    ))
                    lp_connector._trading_pairs = trading_pairs
                    await lp_connector.load_token_data()

                    # 11. Estimate transaction fee
                    self.notify("\nEstimating transaction fees...")
                    fee_info = await GatewayCommandUtils.estimate_transaction_fee(
                        self._get_gateway_instance(),
                        chain,
                        network,
                        transaction_type="collect_fees"
                    )

                    gas_fee_estimate = fee_info.get("fee_in_native", 0) if fee_info.get("success", False) else 0

                    # 12. Get current balances
                    tokens_to_check = list(fees_to_collect.keys())
                    if native_token not in tokens_to_check:
                        tokens_to_check.append(native_token)

                    current_balances = await GatewayCommandUtils.get_wallet_balances(
                        gateway_client=self._get_gateway_instance(),
                        chain=chain,
                        network=network,
                        wallet_address=wallet_address,
                        tokens_to_check=tokens_to_check,
                        native_token=native_token
                    )

                    # 13. Display balance impact
                    warnings = []
                    GatewayCommandUtils.display_balance_impact_table(
                        app=self,
                        wallet_address=wallet_address,
                        current_balances=current_balances,
                        balance_changes=fees_to_collect,  # Fees are positive (receiving)
                        native_token=native_token,
                        gas_fee=gas_fee_estimate,
                        warnings=warnings,
                        title="Balance Impact After Collecting Fees"
                    )

                    # 14. Display transaction fee details
                    GatewayCommandUtils.display_transaction_fee_details(app=self, fee_info=fee_info)

                    # 15. Show gas costs
                    self.notify(f"\nEstimated gas cost: ~{gas_fee_estimate:.6f} {native_token}")

                    # 16. Display warnings
                    if warnings:
                        self.notify("\n⚠️  WARNINGS:")
                        for warning in warnings:
                            self.notify(f"  • {warning}")

                    # 17. Confirmation
                    confirm = await self.app.prompt(
                        prompt="\nDo you want to collect these fees? (Yes/No) >>> "
                    )

                    if confirm.lower() not in ["y", "yes"]:
                        self.notify("Fee collection cancelled")
                        return

                    # 18. Execute fee collection
                    self.notify("\nCollecting fees...")

                    # Collect fees for each selected position
                    # This would ideally be batched if the protocol supports it
                    results = []
                    for i, position in enumerate(selected_positions):
                        self.notify(f"Collecting from position {i + 1}/{len(selected_positions)}...")

                        try:
                            # Call gateway to collect fees
                            result = await self._get_gateway_instance().clmm_collect_fees(
                                connector=connector,
                                network=network,
                                wallet_address=wallet_address,
                                position_address=position.address
                            )

                            if result.get("signature"):
                                results.append({
                                    'position': position,
                                    'tx_hash': result["signature"],
                                    'success': True
                                })
                            else:
                                results.append({
                                    'position': position,
                                    'error': result.get('error', 'Unknown error'),
                                    'success': False
                                })

                        except Exception as e:
                            results.append({
                                'position': position,
                                'error': str(e),
                                'success': False
                            })

                    # 19. Monitor transactions
                    successful_txs = [r for r in results if r['success']]

                    if successful_txs:
                        self.notify(f"\nMonitoring {len(successful_txs)} transaction(s)...")

                        # Monitor each transaction
                        for result in successful_txs:
                            tx_hash = result['tx_hash']
                            self.notify(f"Transaction: {tx_hash}")

                            # Simple monitoring - in production would track all
                            tx_status = await self._monitor_fee_collection_tx(
                                lp_connector, tx_hash
                            )

                            if tx_status['success']:
                                pos = result['position']
                                self.notify(f"✓ Fees collected from position "
                                            f"{self._format_position_id(pos)}")

                    # 20. Summary
                    failed_count = len([r for r in results if not r['success']])
                    if failed_count > 0:
                        self.notify(f"\n⚠️  {failed_count} collection(s) failed")

                    if successful_txs:
                        self.notify(f"\n✓ Successfully collected fees from "
                                    f"{len(successful_txs)} position(s)!")

                finally:
                    self.placeholder_mode = False
                    self.app.hide_input = False
                    self.app.change_prompt(prompt=">>> ")

            finally:
                # Always stop the connector
                if lp_connector:
                    await lp_connector.stop_network()

        except Exception as e:
            self.logger().error(f"Error in collect fees: {e}", exc_info=True)
            self.notify(f"Error: {str(e)}")
