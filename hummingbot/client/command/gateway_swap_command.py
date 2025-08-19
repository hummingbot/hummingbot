#!/usr/bin/env python
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from hummingbot.client.command.command_utils import GatewayCommandUtils
from hummingbot.connector.gateway.gateway_swap import GatewaySwap
from hummingbot.connector.utils import split_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.utils.async_utils import safe_ensure_future

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication  # noqa: F401


class GatewaySwapCommand:
    """Handles gateway swap-related commands"""

    def gateway_swap(self, connector: Optional[str] = None, args: List[str] = None):
        """
        Perform swap operations through gateway - shows quote and asks for confirmation.
        Usage: gateway swap <connector> [base-quote] [side] [amount]
        """
        # Parse arguments: [base-quote] [side] [amount]
        pair = args[0] if args and len(args) > 0 else None
        side = args[1] if args and len(args) > 1 else None
        amount = args[2] if args and len(args) > 2 else None

        safe_ensure_future(self._gateway_swap(connector, pair, side, amount), loop=self.ev_loop)

    async def _gateway_swap(self, connector: Optional[str] = None,
                            pair: Optional[str] = None, side: Optional[str] = None, amount: Optional[str] = None):
        """Unified swap flow - get quote first, then ask for confirmation to execute."""
        try:
            # Parse connector format (e.g., "uniswap/amm")
            if "/" not in connector:
                self.notify(f"Error: Invalid connector format '{connector}'. Use format like 'uniswap/amm'")
                return

            # Get chain and network info for the connector
            chain, network, error = await self._get_gateway_instance().get_connector_chain_network(
                connector
            )
            if error:
                self.notify(f"Error: {error}")
                return

            # Parse trading pair
            try:
                base_token, quote_token = split_hb_trading_pair(pair)
            except (ValueError, AttributeError):
                base_token, quote_token = None, None

            # Only enter interactive mode if parameters are missing
            if not all([base_token, quote_token, side, amount]):
                await GatewayCommandUtils.enter_interactive_mode(self)

                try:
                    # Get base token if not provided
                    if not base_token:
                        base_token = await self.app.prompt(prompt="Enter base token (symbol or address): ")
                        if self.app.to_stop_config or not base_token:
                            self.notify("Swap cancelled")
                            return

                    # Get quote token if not provided
                    if not quote_token:
                        quote_token = await self.app.prompt(prompt="Enter quote token (symbol or address): ")
                        if self.app.to_stop_config or not quote_token:
                            self.notify("Swap cancelled")
                            return

                    # Get amount if not provided
                    if not amount:
                        amount = await self.app.prompt(prompt="Enter amount to trade: ")
                        if self.app.to_stop_config or not amount:
                            self.notify("Swap cancelled")
                            return

                    # Get side if not provided
                    if not side:
                        side = await self.app.prompt(prompt="Enter side (BUY/SELL): ")
                        if self.app.to_stop_config or not side:
                            self.notify("Swap cancelled")
                            return

                finally:
                    await GatewayCommandUtils.exit_interactive_mode(self)

            # Convert side to uppercase for consistency
            if side:
                side = side.upper()

            # Construct pair for display
            pair_display = f"{base_token}-{quote_token}"

            # Convert amount to decimal
            try:
                amount_decimal = Decimal(amount) if amount else Decimal("1")
            except (ValueError, TypeError):
                self.notify("Error: Invalid amount. Please enter a valid number.")
                return

            # Get default wallet for the chain
            wallet_address, error = await self._get_gateway_instance().get_default_wallet(
                chain
            )
            if error:
                self.notify(error)
                return

            self.notify(f"\nFetching swap quote for {pair_display} from {connector}...")

            # Get quote from gateway
            trade_side = TradeType.BUY if side == "BUY" else TradeType.SELL

            quote_resp = await self._get_gateway_instance().quote_swap(
                network=network,
                connector=connector,
                base_asset=base_token,
                quote_asset=quote_token,
                amount=amount_decimal,
                side=trade_side,
                slippage_pct=None,  # Use default slippage from connector config
                pool_address=None   # Let gateway find the best pool
            )

            if "error" in quote_resp:
                self.notify(f"\nError getting quote: {quote_resp['error']}")
                return

            # Store quote ID for logging only
            quote_id = quote_resp.get('quoteId')
            if quote_id:
                self.logger().info(f"Swap quote ID: {quote_id}")

            # Extract relevant details from quote response
            token_in = quote_resp.get('tokenIn')
            token_out = quote_resp.get('tokenOut')
            amount_in = quote_resp.get('amountIn')
            amount_out = quote_resp.get('amountOut')
            min_amount_out = quote_resp.get('minAmountOut')
            max_amount_in = quote_resp.get('maxAmountIn')

            # Display transaction details
            self.notify("\n=== Swap Transaction ===")

            # Token information
            self.notify(f"Token In: {base_token} ({token_in})")
            self.notify(f"Token Out: {quote_token} ({token_out})")

            # Get connector config to show slippage
            connector_config = await self._get_gateway_instance().get_connector_config(
                connector
            )
            slippage_pct = connector_config.get("slippagePct")

            # Price and impact information
            self.notify(f"\nPrice: {quote_resp['price']} {quote_token}/{base_token}")
            if slippage_pct is not None:
                self.notify(f"Slippage: {slippage_pct}%")

            if "priceImpactPct" in quote_resp:
                impact = float(quote_resp["priceImpactPct"]) * 100
                self.notify(f"Price Impact: {impact:.2f}%")

            # Show what user will spend and receive
            if side == "BUY":
                # Buying base with quote
                self.notify("\nYou will spend:")
                self.notify(f"  Amount: {amount_in} {quote_token}")
                self.notify(f"  Max Amount (w/ slippage): {max_amount_in} {quote_token}")

                self.notify("\nYou will receive:")
                self.notify(f"  Amount: {amount_out} {base_token}")

            else:
                # Selling base for quote
                self.notify("\nYou will spend:")
                self.notify(f"  Amount: {amount_in} {base_token}")

                self.notify("\nYou will receive:")
                self.notify(f"  Amount: {amount_out} {quote_token}")
                self.notify(f"  Min Amount (w/ slippage): {min_amount_out} {quote_token}")

            # Get fee estimation from gateway
            self.notify(f"\nEstimating transaction fees for {chain} {network}...")
            fee_info = await self._get_gateway_instance().estimate_transaction_fee(

                chain,
                network,
                transaction_type="swap"
            )

            native_token = fee_info.get("native_token", chain.upper())
            gas_fee_estimate = fee_info.get("fee_in_native", 0) if fee_info.get("success", False) else None

            # Get all tokens to check (include native token for gas)
            tokens_to_check = [base_token, quote_token]
            if native_token and native_token.upper() not in [base_token.upper(), quote_token.upper()]:
                tokens_to_check.append(native_token)

            # Collect warnings throughout the command
            warnings = []

            # Get current balances
            current_balances = await self._get_gateway_instance().get_wallet_balances(

                chain=chain,
                network=network,
                wallet_address=wallet_address,
                tokens_to_check=tokens_to_check,
                native_token=native_token
            )

            # Calculate balance changes from the swap
            balance_changes = {}
            try:
                amount_in_decimal = Decimal(amount_in)
                amount_out_decimal = Decimal(amount_out)

                if side == "BUY":
                    # Buying base with quote
                    balance_changes[base_token] = float(amount_out_decimal)  # Receiving base
                    balance_changes[quote_token] = -float(amount_in_decimal)  # Spending quote
                else:
                    # Selling base for quote
                    balance_changes[base_token] = -float(amount_in_decimal)  # Spending base
                    balance_changes[quote_token] = float(amount_out_decimal)  # Receiving quote

            except Exception as e:
                self.notify(f"\nWarning: Could not calculate balance changes: {str(e)}")
                balance_changes = {}

            # Display unified balance impact table
            GatewayCommandUtils.display_balance_impact_table(
                app=self,
                wallet_address=wallet_address,
                current_balances=current_balances,
                balance_changes=balance_changes,
                native_token=native_token,
                gas_fee=gas_fee_estimate or 0,
                warnings=warnings,
                title="Balance Impact After Swap"
            )

            # Display transaction fee details
            GatewayCommandUtils.display_transaction_fee_details(app=self, fee_info=fee_info)

            # Display any warnings
            GatewayCommandUtils.display_warnings(self, warnings)

            # Ask if user wants to execute the swap
            await GatewayCommandUtils.enter_interactive_mode(self)
            try:
                # Show wallet info in prompt
                if not await GatewayCommandUtils.prompt_for_confirmation(
                    self, "Do you want to execute this swap now?"
                ):
                    self.notify("Swap cancelled")
                    return

                self.notify("\nExecuting swap...")

                # Create trading pair first
                trading_pair = f"{base_token}-{quote_token}"

                # Create a new GatewaySwap instance for this swap
                # (The temporary one was already stopped)
                swap_connector = GatewaySwap(
                    client_config_map=self.client_config_map,
                    connector_name=connector,  # DEX connector (e.g., 'uniswap/amm', 'raydium/clmm')
                    chain=chain,
                    network=network,
                    address=wallet_address,
                    trading_pairs=[trading_pair]
                )

                # Start the network connection
                await swap_connector.start_network()

                # Use price from quote for better tracking
                price_value = quote_resp.get('price', '0')
                # Handle both string and numeric price values
                try:
                    price = Decimal(str(price_value))
                except (ValueError, TypeError):
                    self.notify("\nError: Invalid price received from gateway. Cannot execute swap.")
                    await swap_connector.stop_network()
                    return

                # Store quote data in kwargs for the swap handler
                swap_kwargs = {
                    "quote_id": quote_id,
                    "quote_response": quote_resp,
                    "pool_address": quote_resp.get("poolAddress"),
                }

                # Use connector's buy/sell methods which create inflight orders
                if side == "BUY":
                    order_id = swap_connector.buy(
                        trading_pair=trading_pair,
                        amount=amount_decimal,
                        price=price,
                        order_type=OrderType.MARKET,
                        **swap_kwargs
                    )
                else:
                    order_id = swap_connector.sell(
                        trading_pair=trading_pair,
                        amount=amount_decimal,
                        price=price,
                        order_type=OrderType.MARKET,
                        **swap_kwargs
                    )

                self.notify(f"Order created: {order_id}")
                self.notify("Monitoring transaction status...")

                # Register the connector temporarily so events can be processed
                # This allows MarketsRecorder to capture order events if it's running
                if hasattr(self, 'connector_manager') and self.connector_manager:
                    self.connector_manager.connectors[swap_connector.name] = swap_connector

                # Use the common transaction monitoring helper
                await GatewayCommandUtils.monitor_transaction_with_timeout(
                    app=self,
                    connector=swap_connector,
                    order_id=order_id,
                    timeout=60.0,
                    check_interval=1.0,
                    pending_msg_delay=3.0
                )

                # Clean up - remove temporary connector and stop network
                if hasattr(self, 'connector_manager') and self.connector_manager:
                    self.connector_manager.connectors.pop(swap_connector.name, None)

                # Stop the network connection
                await swap_connector.stop_network()

            finally:
                await GatewayCommandUtils.exit_interactive_mode(self)

        except Exception as e:
            self.notify(f"Error executing swap: {str(e)}")

    def _get_gateway_instance(self) -> GatewayHttpClient:
        """Get the gateway HTTP client instance"""
        gateway_instance = GatewayHttpClient.get_instance(self.client_config_map)
        return gateway_instance
