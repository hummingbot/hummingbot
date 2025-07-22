#!/usr/bin/env python
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from hummingbot.connector.gateway.command_utils import GatewayCommandUtils
from hummingbot.connector.gateway.gateway_base import GatewayBase
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

        safe_ensure_future(self._gateway_unified_swap(connector, None, pair, side, amount), loop=self.ev_loop)

    async def _gateway_unified_swap(self, connector: Optional[str] = None, network: Optional[str] = None,
                                    pair: Optional[str] = None, side: Optional[str] = None, amount: Optional[str] = None):
        """Unified swap flow - get quote first, then ask for confirmation to execute."""
        try:
            # Use utility to validate connector
            connector_type, connector_info, error = await GatewayCommandUtils.validate_connector(
                self._get_gateway_instance(),
                connector,
                required_trading_types=["router", "amm", "clmm"]  # Swap-capable types
            )

            if error:
                self.notify(f"\n{error}")
                if not connector:
                    self.notify("Usage: gateway swap <connector> [base-quote] [side] [amount]")
                    self.notify("\nExamples:")
                    self.notify("  gateway swap uniswap/router")
                    self.notify("  gateway swap raydium/amm SOL-USDC SELL 1.5")
                    self.notify("  gateway swap jupiter/router ETH-USDC BUY 0.1")
                return

            chain = connector_info.get("chain", "")

            # Get network
            network, error = await GatewayCommandUtils.get_network_for_chain(
                self._get_gateway_instance(), chain, network
            )
            if error:
                self.notify(f"\n{error}")
                return
            if not network:
                self.notify(f"Using default network: {network}")

            # Parse trading pair
            base_token, quote_token = GatewayCommandUtils.parse_trading_pair(pair)

            # Only enter interactive mode if parameters are missing
            if not all([base_token, quote_token, side, amount]):
                self.placeholder_mode = True
                self.app.hide_input = True

                try:
                    # Get available tokens
                    token_symbols = await GatewayCommandUtils.get_available_tokens(
                        self._get_gateway_instance(), chain, network
                    )

                    # Update completer's token cache
                    if hasattr(self.app.input_field.completer, '_gateway_token_symbols'):
                        self.app.input_field.completer._gateway_token_symbols = token_symbols

                    # Get base token if not provided
                    if not base_token:
                        self.notify(f"\nAvailable tokens on {chain}/{network}: {', '.join(token_symbols[:10])}{'...' if len(token_symbols) > 10 else ''}")
                        base_token = await self.app.prompt(prompt="Enter base token (symbol or address): ")
                        if self.app.to_stop_config or not base_token:
                            self.notify("Swap cancelled")
                            return
                        # Only uppercase if it's a symbol (short string), not an address
                        if len(base_token) <= 10:
                            base_token = base_token.upper()

                    # Get quote token if not provided
                    if not quote_token:
                        quote_token = await self.app.prompt(prompt="Enter quote token (symbol or address): ")
                        if self.app.to_stop_config or not quote_token:
                            self.notify("Swap cancelled")
                            return
                        # Only uppercase if it's a symbol (short string), not an address
                        if len(quote_token) <= 10:
                            quote_token = quote_token.upper()

                    # Get amount if not provided
                    if not amount:
                        amount = await self.app.prompt(prompt="Enter amount to trade [1]: ")
                        if self.app.to_stop_config or not amount:
                            self.notify("Swap cancelled")
                            return

                    # Get side if not provided
                    if not side:
                        side = await self.app.prompt(prompt="Enter side (BUY/SELL) [SELL]: ")
                        if self.app.to_stop_config or not side:
                            self.notify("Swap cancelled")
                            return

                finally:
                    self.placeholder_mode = False
                    self.app.hide_input = False
                    self.app.change_prompt(prompt=">>> ")

            # Validate side
            side, error = GatewayCommandUtils.validate_side(side)
            if error:
                self.notify(error)
                return

            # Construct pair for display
            base_display = GatewayCommandUtils.format_token_display(base_token)
            quote_display = GatewayCommandUtils.format_token_display(quote_token)
            pair_display = f"{base_display}-{quote_display}"

            # Validate amount
            amount_decimal, error = GatewayCommandUtils.validate_amount(amount)
            if error:
                self.notify(error)
                return

            # Get default wallet
            wallet_address, error = await GatewayCommandUtils.get_default_wallet(
                self._get_gateway_instance(), chain
            )
            wallet_display_address = f"{wallet_address[:4]}...{wallet_address[-4:]}" if len(wallet_address) > 8 else wallet_address
            if error:
                self.notify(error)
                return

            self.notify(f"\nGetting swap quote from {connector_type} on {chain} {network}...")
            self.notify(f"  Pair: {pair_display}")
            self.notify(f"  Amount: {amount}")
            self.notify(f"  Side: {side}")

            # Get connector config and display slippage if available
            connector_config = await GatewayCommandUtils.get_connector_config(
                self._get_gateway_instance(), connector
            )
            if "slippagePct" in connector_config:
                slippage_pct = str(connector_config.get("slippagePct", "0"))
                self.notify(f"  Slippage: {slippage_pct}% ({connector_type} default)")

            # Get quote from gateway
            quote_params = {
                "chain": chain,
                "network": network,
                "connector": connector_type,
                "baseToken": base_token,
                "quoteToken": quote_token,
                "amount": str(amount_decimal),
                "side": side,
                "walletAddress": wallet_address
            }

            quote_resp = await self._get_gateway_instance().connector_request(
                "GET", connector_type, "quote-swap", params=quote_params
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

                # Create a GatewayConnector instance for this swap
                # We need a proper connector instance to execute the swap through its trading handlers
                connector = GatewayBase(
                    connector_name=connector_type,
                    network=network,
                    wallet_address=wallet_address,
                    trading_required=True
                )

                # Initialize the connector
                await connector._initialize()

                # Create trading pair
                trading_pair = f"{base_token}-{quote_token}"

                # Use price from quote for better tracking
                price_value = quote_resp.get('price', '0')
                # Handle both string and numeric price values
                try:
                    price = Decimal(str(price_value))
                except (ValueError, TypeError):
                    self.notify("\nError: Invalid price received from gateway. Cannot execute swap.")
                    return

                # Store quote data in kwargs for the swap handler
                swap_kwargs = {
                    "quote_id": quote_id,
                    "quote_response": quote_resp,
                    "pool_address": quote_resp.get("poolAddress"),
                    "route": quote_resp.get("route"),
                    "minimum_out": quote_resp.get("minimumOut") or quote_resp.get("minAmountOut")
                }

                # Use connector's buy/sell methods which create inflight orders
                if side == "BUY":
                    order_id = connector.buy(
                        trading_pair=trading_pair,
                        amount=amount_decimal,
                        order_type=OrderType.MARKET,
                        price=price,
                        **swap_kwargs
                    )
                else:
                    order_id = connector.sell(
                        trading_pair=trading_pair,
                        amount=amount_decimal,
                        order_type=OrderType.MARKET,
                        price=price,
                        **swap_kwargs
                    )

                self.notify(f"Order created: {order_id}")

                # Register the connector temporarily so events can be processed
                # This allows MarketsRecorder to capture order events if it's running
                if hasattr(self, 'connector_manager') and self.connector_manager:
                    self.connector_manager.connectors[connector.name] = connector

                # Wait for order completion
                import asyncio
                max_wait_time = 60  # seconds
                check_interval = 2  # seconds
                elapsed_time = 0

                while elapsed_time < max_wait_time:
                    order = connector.get_order(order_id)
                    if order and order.is_done:
                        if order.is_filled:
                            self.notify("\n✓ Swap completed successfully!")
                            if order.exchange_order_id:
                                self.notify(f"Transaction hash: {order.exchange_order_id}")
                        elif order.is_failure:
                            self.notify("\n✗ Swap failed")
                        elif order.is_cancelled:
                            self.notify("\n✗ Swap cancelled")
                        break

                    await asyncio.sleep(check_interval)
                    elapsed_time += check_interval

                    if elapsed_time == 10:  # Show status after 10 seconds
                        self.notify("Transaction pending...")

                if elapsed_time >= max_wait_time:
                    self.notify("\n⚠️  Transaction monitoring timed out.")
                    if order and order.exchange_order_id:
                        self.notify(f"You can check the transaction manually: {order.exchange_order_id}")

                # Clean up - remove temporary connector
                if hasattr(self, 'connector_manager') and self.connector_manager:
                    self.connector_manager.connectors.pop(connector.name, None)

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
