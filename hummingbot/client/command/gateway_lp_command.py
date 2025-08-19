#!/usr/bin/env python
import asyncio
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

from hummingbot.client.command.command_utils import GatewayCommandUtils
from hummingbot.client.command.lp_command_utils import LPCommandUtils
from hummingbot.connector.gateway.common_types import ConnectorType, TransactionStatus, get_connector_type
from hummingbot.connector.gateway.gateway_lp import (
    AMMPoolInfo,
    AMMPositionInfo,
    CLMMPoolInfo,
    CLMMPositionInfo,
    GatewayLp,
)
from hummingbot.connector.utils import split_hb_trading_pair
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
            self.notify("  collect-fees      - Collect accumulated fees (CLMM only)")
            self.notify("\nExample: gateway lp uniswap/amm add-liquidity")
            return

        # Check if collect-fees is being called on non-CLMM connector
        if action == "collect-fees":
            try:
                connector_type = get_connector_type(connector)
                if connector_type != ConnectorType.CLMM:
                    self.notify("\nError: Fee collection is only available for concentrated liquidity (CLMM) connectors")
                    self.notify("AMM connectors collect fees automatically when removing liquidity")
                    return
            except Exception:
                # If we can't determine connector type, let _collect_fees handle it
                pass

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
        is_clmm: bool,
        base_token: str = None,
        quote_token: str = None
    ):
        """Display pool information in a user-friendly format"""
        LPCommandUtils.display_pool_info(self, pool_info, is_clmm, base_token, quote_token)

    def _format_position_id(
        self,
        position: Union[AMMPositionInfo, CLMMPositionInfo]
    ) -> str:
        """Format position identifier for display"""
        return LPCommandUtils.format_position_id(position)

    def _calculate_removal_amounts(
        self,
        position: Union[AMMPositionInfo, CLMMPositionInfo],
        percentage: float
    ) -> Tuple[float, float]:
        """Calculate token amounts to receive when removing liquidity"""
        return LPCommandUtils.calculate_removal_amounts(position, percentage)

    def _display_positions_with_fees(
        self,
        positions: List[CLMMPositionInfo]
    ):
        """Display positions that have uncollected fees"""
        LPCommandUtils.display_positions_with_fees(self, positions)

    def _calculate_total_fees(
        self,
        positions: List[CLMMPositionInfo]
    ) -> Dict[str, float]:
        """Calculate total fees across positions grouped by token"""
        return LPCommandUtils.calculate_total_fees(positions)

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
        return LPCommandUtils.calculate_clmm_pair_amount(
            known_amount, pool_info, lower_price, upper_price, is_base_known
        )

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
                self.notify(f"Error: Invalid connector format '{connector}'. Use format like 'uniswap/amm'")
                return

            chain, network, error = await self._get_gateway_instance().get_connector_chain_network(
                connector
            )
            if error:
                self.notify(f"Error: {error}")
                return

            # 2. Get wallet address
            wallet_address, error = await self._get_gateway_instance().get_default_wallet(
                chain
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
                positions = []

                # Ask for trading pair for both AMM and CLMM to filter by pool
                await GatewayCommandUtils.enter_interactive_mode(self)

                try:
                    pair_input = await self.app.prompt(
                        prompt="Enter trading pair (e.g., SOL-USDC): "
                    )

                    if self.app.to_stop_config:
                        return

                    if not pair_input.strip():
                        self.notify("Error: Trading pair is required")
                        return

                    trading_pair = pair_input.strip().upper()

                    # Validate trading pair format
                    if "-" not in trading_pair:
                        self.notify("Error: Invalid trading pair format. Use format like 'SOL-USDC'")
                        return

                    self.notify(f"\nFetching positions for {trading_pair}...")

                    # Get pool address for the trading pair
                    pool_address = await lp_connector.get_pool_address(trading_pair)
                    if not pool_address:
                        self.notify(f"No pool found for {trading_pair}")
                        return

                    # Get positions for this pool
                    positions = await lp_connector.get_user_positions(pool_address=pool_address)

                finally:
                    await GatewayCommandUtils.exit_interactive_mode(self)

                if not positions:
                    self.notify("\nNo liquidity positions found")
                    return

                # Extract base and quote tokens from trading pair
                base_token, quote_token = trading_pair.split("-")

                # 5. Display positions
                for i, position in enumerate(positions):
                    if len(positions) > 1:
                        self.notify(f"\n--- Position {i + 1} of {len(positions)} ---")

                    # Display position using the appropriate formatter
                    if is_clmm:
                        position_display = LPCommandUtils.format_clmm_position_display(
                            position, base_token, quote_token
                        )
                    else:
                        position_display = LPCommandUtils.format_amm_position_display(
                            position, base_token, quote_token
                        )

                    self.notify(position_display)

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

            chain, network, error = await self._get_gateway_instance().get_connector_chain_network(
                connector
            )
            if error:
                self.notify(f"Error: {error}")
                return

            # 2. Get wallet address
            wallet_address, error = await self._get_gateway_instance().get_default_wallet(
                chain
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
            await GatewayCommandUtils.enter_interactive_mode(self)

            try:
                # 5. Get trading pair
                pair = await self.app.prompt(
                    prompt="Enter trading pair (e.g., SOL-USDC): "
                )
                if self.app.to_stop_config or not pair:
                    self.notify("Add liquidity cancelled")
                    return

                try:
                    base_token, quote_token = split_hb_trading_pair(pair)
                except (ValueError, AttributeError):
                    self.notify("Error: Invalid trading pair format. Use format like 'SOL-USDC'")
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
                self._display_pool_info(pool_info, is_clmm, base_token, quote_token)

                # 8. Get position parameters based on type
                position_params = {}
                lower_price = None
                upper_price = None

                if is_clmm:
                    # For CLMM, get price range
                    current_price = pool_info.price

                    self.notify(f"\nCurrent pool price: {current_price:.6f}")
                    self.notify("Enter your price range for liquidity provision:")

                    # Get lower price bound
                    lower_price_str = await self.app.prompt(
                        prompt="Lower price bound: "
                    )

                    # Get upper price bound
                    upper_price_str = await self.app.prompt(
                        prompt="Upper price bound: "
                    )

                    try:
                        lower_price = float(lower_price_str)
                        upper_price = float(upper_price_str)

                        if lower_price >= upper_price:
                            self.notify("Error: Lower price must be less than upper price")
                            return

                        if lower_price > current_price or upper_price < current_price:
                            self.notify("\nWarning: Current price is outside your range!")
                            self.notify("You will only earn fees when price is within your range.")

                        # Display selected range
                        self.notify("\nSelected price range:")
                        self.notify(f"  Lower: {lower_price:.6f}")
                        self.notify(f"  Current: {current_price:.6f}")
                        self.notify(f"  Upper: {upper_price:.6f}")

                        # Calculate spread percentage for internal use
                        mid_price = (lower_price + upper_price) / 2
                        spread_pct = ((upper_price - lower_price) / (2 * mid_price)) * 100
                        position_params['spread_pct'] = spread_pct

                    except ValueError:
                        self.notify("Error: Invalid price values")
                        return

                # 9. Get token amounts
                self.notify("Enter token amounts to add (press Enter to skip):")

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

                # 10. Get quote for optimal amounts
                self.notify("\nCalculating optimal token amounts...")

                # Get slippage from connector config
                connector_config = await self._get_gateway_instance().get_connector_config(
                    connector
                )
                slippage_pct = connector_config.get("slippagePct", 1.0)

                if is_clmm:
                    # For CLMM, use quote_position
                    quote_result = await self._get_gateway_instance().clmm_quote_position(
                        connector=connector,
                        network=network,
                        pool_address=pool_info.address,
                        lower_price=lower_price,
                        upper_price=upper_price,
                        base_token_amount=base_amount,
                        quote_token_amount=quote_amount,
                        slippage_pct=slippage_pct
                    )

                    # Update amounts based on quote
                    base_amount = quote_result.get("baseTokenAmount", base_amount)
                    quote_amount = quote_result.get("quoteTokenAmount", quote_amount)

                    # Show if position is base or quote limited
                    if quote_result.get("baseLimited"):
                        self.notify("Note: Position size is limited by base token amount")
                    else:
                        self.notify("Note: Position size is limited by quote token amount")

                else:
                    # For AMM, need both amounts for quote
                    if not base_amount or not quote_amount:
                        # If only one amount provided, calculate the other based on pool ratio
                        pool_ratio = pool_info.base_token_amount / pool_info.quote_token_amount
                        if base_amount and not quote_amount:
                            quote_amount = base_amount / pool_ratio
                        elif quote_amount and not base_amount:
                            base_amount = quote_amount * pool_ratio

                    # Get quote for AMM
                    quote_result = await self._get_gateway_instance().amm_quote_liquidity(
                        connector=connector,
                        network=network,
                        pool_address=pool_info.address,
                        base_token_amount=base_amount,
                        quote_token_amount=quote_amount,
                        slippage_pct=slippage_pct
                    )

                    # Update amounts based on quote
                    base_amount = quote_result.get("baseTokenAmount", base_amount)
                    quote_amount = quote_result.get("quoteTokenAmount", quote_amount)

                    # Show if position is base or quote limited
                    if quote_result.get("baseLimited"):
                        self.notify("Note: Liquidity will be limited by base token amount")
                    else:
                        self.notify("Note: Liquidity will be limited by quote token amount")

                # Display calculated amounts
                self.notify("\nToken amounts to add:")
                self.notify(f"  {base_token}: {base_amount:.6f}")
                self.notify(f"  {quote_token}: {quote_amount:.6f}")

                # 11. Check balances and calculate impact
                tokens_to_check = [base_token, quote_token]
                native_token = lp_connector.native_currency or chain.upper()

                current_balances = await self._get_gateway_instance().get_wallet_balances(

                    chain=chain,
                    network=network,
                    wallet_address=wallet_address,
                    tokens_to_check=tokens_to_check,
                    native_token=native_token
                )

                # 12. Estimate transaction fee
                self.notify("\nEstimating transaction fees...")
                fee_info = await self._get_gateway_instance().estimate_transaction_fee(

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
                GatewayCommandUtils.display_warnings(self, warnings)

                # 18. Show slippage info
                self.notify(f"\nSlippage tolerance: {slippage_pct}%")

                # 19. Confirmation
                if not await GatewayCommandUtils.prompt_for_confirmation(
                    self, "Do you want to add liquidity?"
                ):
                    self.notify("Add liquidity cancelled")
                    return

                # 20. Execute transaction
                self.notify("\nAdding liquidity...")

                # Create order ID and execute
                if is_clmm:
                    order_id = lp_connector.add_liquidity(
                        trading_pair=trading_pair,
                        price=pool_info.price,
                        spread_pct=position_params['spread_pct'],
                        base_token_amount=base_amount,
                        quote_token_amount=quote_amount,
                        slippage_pct=slippage_pct
                    )
                else:
                    order_id = lp_connector.add_liquidity(
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
                    self.notify(f"Use 'gateway lp {connector} position-info' to view your position")

            finally:
                await GatewayCommandUtils.exit_interactive_mode(self)
                # Always stop the connector
                if lp_connector:
                    await lp_connector.stop_network()

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
                self.notify(f"Error: Invalid connector format '{connector}'. Use format like 'uniswap/amm'")
                return

            chain, network, error = await self._get_gateway_instance().get_connector_chain_network(
                connector
            )
            if error:
                self.notify(f"Error: {error}")
                return

            # 2. Get wallet address
            wallet_address, error = await self._get_gateway_instance().get_default_wallet(
                chain
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
                # 5. Enter interactive mode for all user inputs
                await GatewayCommandUtils.enter_interactive_mode(self)

                try:
                    # Get trading pair from user
                    pair_input = await self.app.prompt(
                        prompt="Enter trading pair (e.g., SOL-USDC): "
                    )

                    if self.app.to_stop_config:
                        return

                    if not pair_input.strip():
                        self.notify("Error: Trading pair is required")
                        return

                    trading_pair = pair_input.strip().upper()

                    # Validate trading pair format
                    if "-" not in trading_pair:
                        self.notify("Error: Invalid trading pair format. Use format like 'SOL-USDC'")
                        return

                    self.notify(f"\nFetching positions for {trading_pair}...")

                    # Get pool address for the trading pair
                    pool_address = await lp_connector.get_pool_address(trading_pair)
                    if not pool_address:
                        self.notify(f"No pool found for {trading_pair}")
                        return

                    # Get positions for this pool
                    positions = await lp_connector.get_user_positions(pool_address=pool_address)

                    if not positions:
                        self.notify(f"\nNo liquidity positions found for {trading_pair}")
                        return

                    # Extract base and quote tokens
                    base_token, quote_token = trading_pair.split("-")

                    # Display positions
                    for i, position in enumerate(positions):
                        if len(positions) > 1:
                            self.notify(f"\n--- Position {i + 1} of {len(positions)} ---")

                        # Display position using the appropriate formatter
                        if is_clmm:
                            position_display = LPCommandUtils.format_clmm_position_display(
                                position, base_token, quote_token
                            )
                        else:
                            position_display = LPCommandUtils.format_amm_position_display(
                                position, base_token, quote_token
                            )

                        self.notify(position_display)
                    # 7. Let user select position
                    selected_position = await LPCommandUtils.prompt_for_position_selection(
                        self, positions, prompt_text=f"\nSelect position number (1-{len(positions)}): "
                    )

                    if not selected_position:
                        return

                    if len(positions) == 1:
                        self.notify(f"\nSelected position: {self._format_position_id(selected_position)}")

                    # 8. Get removal percentage
                    percentage = await GatewayCommandUtils.prompt_for_percentage(
                        self, prompt_text="Percentage to remove (0-100, default 100): "
                    )

                    if percentage is None:
                        return

                    # 9. For 100% removal on CLMM, always close position
                    close_position = percentage == 100.0 and is_clmm

                    # 10. Calculate and display removal impact
                    base_to_receive, quote_to_receive = LPCommandUtils.display_position_removal_impact(
                        self, selected_position, percentage,
                        base_token, quote_token
                    )

                    # 11. Update LP connector with the selected trading pair
                    lp_connector._trading_pairs = [trading_pair]
                    # Reload token data for the selected pair if needed
                    await lp_connector.load_token_data()

                    # 12. Check balances and estimate fees
                    tokens_to_check = [base_token, quote_token]
                    native_token = lp_connector.native_currency or chain.upper()

                    current_balances = await self._get_gateway_instance().get_wallet_balances(

                        chain=chain,
                        network=network,
                        wallet_address=wallet_address,
                        tokens_to_check=tokens_to_check,
                        native_token=native_token
                    )

                    # 13. Estimate transaction fee
                    self.notify("\nEstimating transaction fees...")
                    tx_type = "close_position" if close_position else "remove_liquidity"
                    fee_info = await self._get_gateway_instance().estimate_transaction_fee(

                        chain,
                        network,
                        transaction_type=tx_type
                    )

                    gas_fee_estimate = fee_info.get("fee_in_native", 0) if fee_info.get("success", False) else 0

                    # 14. Calculate balance changes (positive for receiving tokens)
                    balance_changes = {}
                    balance_changes[base_token] = base_to_receive
                    balance_changes[quote_token] = quote_to_receive

                    # Add fees to balance changes
                    if hasattr(selected_position, 'base_fee_amount'):
                        balance_changes[base_token] += selected_position.base_fee_amount
                        balance_changes[quote_token] += selected_position.quote_fee_amount

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
                    GatewayCommandUtils.display_warnings(self, warnings)

                    # 18. Confirmation
                    action_text = "close position" if close_position else f"remove {percentage}% liquidity"
                    if not await GatewayCommandUtils.prompt_for_confirmation(
                        self, f"Do you want to {action_text}?"
                    ):
                        self.notify("Remove liquidity cancelled")
                        return

                    # 20. Execute transaction
                    self.notify(f"\n{'Closing position' if close_position else 'Removing liquidity'}...")

                    # Get position address
                    position_address = getattr(selected_position, 'address', None) or getattr(selected_position, 'pool_address', None)

                    # The remove_liquidity method now handles the routing correctly:
                    # - For CLMM: uses clmm_close_position if 100%, clmm_remove_liquidity otherwise
                    # - For AMM: always uses amm_remove_liquidity
                    order_id = lp_connector.remove_liquidity(
                        trading_pair=trading_pair,
                        position_address=position_address,
                        percentage=percentage
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
                            self.notify(f"Use 'gateway lp {connector} position-info' to view remaining position")

                finally:
                    await GatewayCommandUtils.exit_interactive_mode(self)

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
                self.notify(f"Error: Invalid connector format '{connector}'. Use format like 'uniswap/amm'")
                return

            chain, network, error = await self._get_gateway_instance().get_connector_chain_network(
                connector
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
            wallet_address, error = await self._get_gateway_instance().get_default_wallet(
                chain
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
                # 5. Enter interactive mode to get trading pair
                await GatewayCommandUtils.enter_interactive_mode(self)

                try:
                    pair_input = await self.app.prompt(
                        prompt="Enter trading pair (e.g., SOL-USDC): "
                    )

                    if self.app.to_stop_config:
                        return

                    if not pair_input.strip():
                        self.notify("Error: Trading pair is required")
                        return

                    trading_pair = pair_input.strip().upper()

                    # Validate trading pair format
                    if "-" not in trading_pair:
                        self.notify("Error: Invalid trading pair format. Use format like 'SOL-USDC'")
                        return

                    self.notify(f"\nFetching positions for {trading_pair}...")

                    # Get pool address for the trading pair
                    pool_address = await lp_connector.get_pool_address(trading_pair)
                    if not pool_address:
                        self.notify(f"No pool found for {trading_pair}")
                        return

                    # Get positions for this pool
                    all_positions = await lp_connector.get_user_positions(pool_address=pool_address)

                    # Filter positions with fees > 0
                    positions_with_fees = [
                        pos for pos in all_positions
                        if hasattr(pos, 'base_fee_amount') and
                        (pos.base_fee_amount > 0 or pos.quote_fee_amount > 0)
                    ]

                    if not positions_with_fees:
                        self.notify(f"\nNo uncollected fees found in your {trading_pair} positions")
                        return

                    # 5. Display positions with fees
                    self._display_positions_with_fees(positions_with_fees)

                    # 6. Calculate and display total fees
                    GatewayCommandUtils.calculate_and_display_fees(
                        self, positions_with_fees
                    )

                    # 8. Select position to collect fees from
                    selected_position = await LPCommandUtils.prompt_for_position_selection(
                        self, positions_with_fees,
                        prompt_text=f"\nSelect position to collect fees from (1-{len(positions_with_fees)}): "
                    )

                    if not selected_position:
                        return

                    if len(positions_with_fees) == 1:
                        self.notify(f"\nSelected position: {self._format_position_id(selected_position)}")

                    # 9. Show fees to collect from selected position
                    self.notify("\nFees to collect:")
                    self.notify(f"  {selected_position.base_token}: {selected_position.base_fee_amount:.6f}")
                    self.notify(f"  {selected_position.quote_token}: {selected_position.quote_fee_amount:.6f}")

                    # 10. Check gas costs vs fees
                    # Get native token for gas estimation
                    native_token = lp_connector.native_currency or chain.upper()

                    # Update connector with the trading pair from selected position
                    trading_pair = f"{selected_position.base_token}-{selected_position.quote_token}"
                    lp_connector._trading_pairs = [trading_pair]
                    await lp_connector.load_token_data()

                    # 11. Estimate transaction fee
                    self.notify("\nEstimating transaction fees...")
                    fee_info = await self._get_gateway_instance().estimate_transaction_fee(

                        chain,
                        network,
                        transaction_type="collect_fees"
                    )

                    gas_fee_estimate = fee_info.get("fee_in_native", 0) if fee_info.get("success", False) else 0

                    # 12. Get current balances
                    tokens_to_check = [selected_position.base_token, selected_position.quote_token]
                    if native_token not in tokens_to_check:
                        tokens_to_check.append(native_token)

                    current_balances = await self._get_gateway_instance().get_wallet_balances(

                        chain=chain,
                        network=network,
                        wallet_address=wallet_address,
                        tokens_to_check=tokens_to_check,
                        native_token=native_token
                    )

                    # 13. Display balance impact
                    warnings = []
                    # Calculate fees to receive
                    fees_to_receive = {
                        selected_position.base_token: selected_position.base_fee_amount,
                        selected_position.quote_token: selected_position.quote_fee_amount
                    }

                    GatewayCommandUtils.display_balance_impact_table(
                        app=self,
                        wallet_address=wallet_address,
                        current_balances=current_balances,
                        balance_changes=fees_to_receive,  # Fees are positive (receiving)
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
                    GatewayCommandUtils.display_warnings(self, warnings)

                    # 17. Confirmation
                    if not await GatewayCommandUtils.prompt_for_confirmation(
                        self, "Do you want to collect these fees?"
                    ):
                        self.notify("Fee collection cancelled")
                        return

                    # 18. Execute fee collection
                    self.notify("\nCollecting fees...")

                    try:
                        # Call gateway to collect fees
                        result = await self._get_gateway_instance().clmm_collect_fees(
                            connector=connector,
                            network=network,
                            wallet_address=wallet_address,
                            position_address=selected_position.address
                        )

                        if result.get("signature"):
                            tx_hash = result["signature"]
                            self.notify(f"Transaction submitted: {tx_hash}")
                            self.notify("Monitoring transaction status...")

                            # Monitor transaction
                            tx_status = await self._monitor_fee_collection_tx(
                                lp_connector, tx_hash
                            )

                            if tx_status['success']:
                                self.notify(f"\n✓ Fees collected successfully from position "
                                            f"{self._format_position_id(selected_position)}!")
                            else:
                                self.notify(f"\n✗ Transaction failed: {tx_status.get('error', 'Unknown error')}")
                        else:
                            self.notify(f"\n✗ Failed to submit transaction: {result.get('error', 'Unknown error')}")

                    except Exception as e:
                        self.notify(f"\n✗ Error collecting fees: {str(e)}")
                        self.logger().error(f"Error collecting fees: {e}", exc_info=True)

                finally:
                    await GatewayCommandUtils.exit_interactive_mode(self)

            finally:
                # Always stop the connector
                if lp_connector:
                    await lp_connector.stop_network()

        except Exception as e:
            self.logger().error(f"Error in collect fees: {e}", exc_info=True)
            self.notify(f"Error: {str(e)}")
