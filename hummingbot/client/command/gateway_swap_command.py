#!/usr/bin/env python
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from hummingbot.connector.gateway.command_utils import GatewayCommandUtils
from hummingbot.connector.gateway.gateway_swap import GatewaySwap
from hummingbot.core.data_type.common import OrderType
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

        safe_ensure_future(self._gateway_unified_swap(connector, pair, side, amount), loop=self.ev_loop)

    async def _gateway_unified_swap(self, connector: Optional[str] = None,
                                    pair: Optional[str] = None, side: Optional[str] = None, amount: Optional[str] = None):
        """Unified swap flow - get quote first, then ask for confirmation to execute."""
        try:
            # Check if connector is provided
            if not connector:
                self.notify("Usage: gateway swap <connector> [base-quote] [side] [amount]")
                self.notify("\nExamples:")
                self.notify("  gateway swap uniswap/amm")
                self.notify("  gateway swap raydium/amm SOL-USDC SELL 1.5")
                self.notify("  gateway swap jupiter/router ETH-USDC BUY 0.1")
                return

            # Get chain and network info for the connector
            chain, network, error = await GatewayCommandUtils.get_connector_chain_network(
                self._get_gateway_instance(), connector
            )
            if error:
                self.notify(f"Error: {error}")
                return

            # Parse trading pair
            base_token, quote_token = GatewayCommandUtils.parse_trading_pair(pair)

            # Only enter interactive mode if parameters are missing
            if not all([base_token, quote_token, side, amount]):
                self.placeholder_mode = True
                self.app.hide_input = True

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
                    self.placeholder_mode = False
                    self.app.hide_input = False
                    self.app.change_prompt(prompt=">>> ")

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

            # Get default wallet from gateway
            wallet_address = await self._get_gateway_instance().get_default_wallet_for_chain(chain)
            if not wallet_address:
                self.notify(f"Error: No default wallet found for chain '{chain}'. Please add a wallet first.")
                return

            wallet_display_address = f"{wallet_address[:4]}...{wallet_address[-4:]}" if len(wallet_address) > 8 else wallet_address

            self.notify(f"\nGetting swap quote from {connector} on {chain} {network}...")
            self.notify(f"  Pair: {pair_display}")
            self.notify(f"  Amount: {amount}")
            self.notify(f"  Side: {side}")

            # Get quote from gateway
            from hummingbot.core.data_type.common import TradeType
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

            # Price and impact information
            self.notify(f"\nPrice: {quote_resp['price']} {quote_token}/{base_token}")
            if "priceImpactPct" in quote_resp:
                impact = float(quote_resp["priceImpactPct"]) * 100
                self.notify(f"Price Impact: {impact:.2f}%")

            # Show what user will spend and receive
            if side == "BUY":
                # Buying base with quote
                self.notify("\nYou will spend:")
                self.notify(f"  Amount: {amount_in} {quote_token}")
                self.notify(f"  {quote_token} {token_in}")

                self.notify("\nYou will receive:")
                self.notify(f"  Amount: {amount_out} {base_token}")
                self.notify(f"  Max Amount w/slippage): {max_amount_in} {quote_token}")

            else:
                # Selling base for quote
                self.notify("\nYou will spend:")
                self.notify(f"  Amount: {amount_in} {base_token}")

                self.notify("\nYou will receive:")
                self.notify(f"  Amount: {amount_out} {quote_token}")
                self.notify(f"  Min Amount w/ slippage: {min_amount_out} {quote_token}")

            # Fetch current balances before showing confirmation
            self.notify(f"\n=== Wallet {wallet_display_address} Balances ===")
            try:
                # Fetch balances for both tokens
                tokens_to_check = [base_token, quote_token]
                balances_resp = await self._get_gateway_instance().get_balances(
                    chain, network, wallet_address, tokens_to_check
                )
                balances = balances_resp.get("balances", {})

                # Get current balances
                base_balance = Decimal(balances.get(base_token))
                quote_balance = Decimal(balances.get(quote_token))
                if base_balance is None or quote_balance is None:
                    raise ValueError("Could not fetch balances for one or both tokens")

                # Display current balances
                self.notify("\nCurrent Balances:")
                self.notify(f"  {base_token}: {base_balance:.4f}")
                self.notify(f"  {quote_token}: {quote_balance:.4f}")

                # Calculate and display impact on balances
                self.notify("\nAfter Swap:")
                amount_in_decimal = Decimal(amount_in)
                amount_out_decimal = Decimal(amount_out)

                if side == "BUY":
                    # Buying base with quote
                    new_base_balance = base_balance + amount_out_decimal
                    new_quote_balance = quote_balance - amount_in_decimal
                    self.notify(f"  {base_token}: {new_base_balance:.4f}")
                    self.notify(f"  {quote_token}: {new_quote_balance:.4f}")

                    # Check if user has enough quote tokens
                    if quote_balance < amount_in_decimal:
                        self.notify(f"\n⚠️  WARNING: Insufficient {quote_token} balance! You need {amount_in_decimal:.4f} but only have {quote_balance:.4f}")
                else:
                    # Selling base for quote
                    new_base_balance = base_balance - amount_in_decimal
                    new_quote_balance = quote_balance + amount_out_decimal
                    self.notify(f"  {base_token}: {new_base_balance:.4f}")
                    self.notify(f"  {quote_token}: {new_quote_balance:.4f}")

                    # Check if user has enough base tokens
                    if base_balance < amount_in_decimal:
                        self.notify(f"\n⚠️  WARNING: Insufficient {base_token} balance! You need {amount_in_decimal:.4f} but only have {base_balance:.4f}")

            except Exception as e:
                self.notify(f"\nWarning: Could not fetch balances: {str(e)}")
                # Continue anyway - let the swap fail if there are insufficient funds

            # Ask if user wants to execute the swap
            self.placeholder_mode = True
            self.app.hide_input = True
            try:
                # Show wallet info in prompt
                execute_now = await self.app.prompt(
                    prompt="Do you want to execute this swap now? (Yes/No) >>> "
                )

                # Restore normal prompt immediately after getting user input
                self.placeholder_mode = False
                self.app.hide_input = False

                if execute_now.lower() not in ["y", "yes"]:
                    self.notify("Swap cancelled")
                    return

                self.notify("\nExecuting swap...")

                # Create trading pair first
                trading_pair = f"{base_token}-{quote_token}"

                # Create a GatewaySwap instance for this swap
                # Pass the trading pair so it loads the correct token data
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

                # Ensure token data is loaded for these specific tokens
                # This is needed in case the tokens aren't in the gateway's token list
                if base_token not in swap_connector._amount_quantum_dict:
                    # Try to get token info from gateway
                    token_info = await self._get_gateway_instance().get_token(base_token, chain, network)
                    if "decimals" in token_info:
                        swap_connector._amount_quantum_dict[base_token] = Decimal(str(10 ** -token_info["decimals"]))
                    else:
                        # Default to 9 decimals for unknown tokens
                        swap_connector._amount_quantum_dict[base_token] = Decimal("1e-9")

                if quote_token not in swap_connector._amount_quantum_dict:
                    # Try to get token info from gateway
                    token_info = await self._get_gateway_instance().get_token(quote_token, chain, network)
                    if "decimals" in token_info:
                        swap_connector._amount_quantum_dict[quote_token] = Decimal(str(10 ** -token_info["decimals"]))
                    else:
                        # Default to 9 decimals for unknown tokens
                        swap_connector._amount_quantum_dict[quote_token] = Decimal("1e-9")

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
                    connector=swap_connector,
                    order_id=order_id,
                    notify_fn=self.notify,
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
                self.placeholder_mode = False
                self.app.hide_input = False
                self.app.change_prompt(prompt=">>> ")

        except Exception as e:
            self.notify(f"Error executing swap: {str(e)}")

    def _get_gateway_instance(self) -> GatewayHttpClient:
        """Get the gateway HTTP client instance"""
        gateway_instance = GatewayHttpClient.get_instance(self.client_config_map)
        return gateway_instance
