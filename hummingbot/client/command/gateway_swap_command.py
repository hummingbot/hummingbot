#!/usr/bin/env python
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from hummingbot.connector.gateway.core.gateway_connector import GatewayConnector
from hummingbot.connector.gateway.utils.command_utils import GatewayCommandUtils
from hummingbot.core.data_type.common import OrderType
from hummingbot.core.utils.async_utils import safe_ensure_future

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication  # noqa: F401


def ensure_gateway_online(func):
    """Decorator to ensure gateway is online before executing commands."""

    def wrapper(self, *args, **kwargs):
        from hummingbot.connector.gateway.core import GatewayStatus
        if hasattr(self, '_gateway_monitor') and self._gateway_monitor.gateway_status is GatewayStatus.OFFLINE:
            self.logger().error("Gateway is offline")
            return
        return func(self, *args, **kwargs)
    return wrapper


class GatewaySwapCommand:
    """Handles gateway swap-related commands"""

    @ensure_gateway_online
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
                        if self.app.to_stop_config:
                            self.notify("Swap cancelled")
                            return
                        if not amount:
                            amount = "1"  # Default amount

                    # Get side if not provided
                    if not side:
                        side = await self.app.prompt(prompt="Enter side (BUY/SELL) [SELL]: ")
                        if self.app.to_stop_config:
                            self.notify("Swap cancelled")
                            return
                        if not side:
                            side = "SELL"  # Default side

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
            if error:
                self.notify(error)
                return

            # Look up pool address if needed (for AMM/CLMM connectors)
            pool_address = None
            if connector_type.endswith("/amm") or connector_type.endswith("/clmm"):
                self.notify(f"\nSearching for {base_token}/{quote_token} pool...")
                base_connector = connector_type.split("/")[0]
                pool_address = await GatewayCommandUtils.find_pool(
                    self._get_gateway_instance(),
                    base_connector,
                    network,
                    base_token,
                    quote_token
                )
                if pool_address:
                    self.notify(f"Found pool: {pool_address[:10]}...")
                else:
                    self.notify(f"Error: No pool found for {base_token}/{quote_token} on {base_connector}")
                    return

            # Get connector config
            connector_config = await GatewayCommandUtils.get_connector_config(
                self._get_gateway_instance(), connector
            )
            slippage_pct = str(connector_config.get("slippagePct", 1))

            self.notify(f"\nGetting swap quote from {connector_type} on {network}...")
            self.notify(f"  Pair: {pair_display}")
            self.notify(f"  Amount: {amount}")
            self.notify(f"  Side: {side}")
            self.notify(f"  Slippage: {slippage_pct}%")

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

            # Add pool address if found
            if pool_address:
                quote_params["poolAddress"] = pool_address

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

            # Token addresses
            token_in = quote_resp.get('tokenIn', 'N/A')
            token_out = quote_resp.get('tokenOut', 'N/A')

            # Amounts
            amount_out = quote_resp.get('amountOut', quote_resp.get('expectedOut'))
            min_amount_out = quote_resp.get('minAmountOut', quote_resp.get('minimumOut'))

            # Display transaction details
            self.notify("\n=== Transaction Details ===")

            # Price and slippage information
            if "price" in quote_resp:
                self.notify(f"\nPrice: {quote_resp['price']} {quote_token}/{base_token}")

            slippage_pct = quote_resp.get('slippagePct', 1.0)  # Default 1% if not provided
            self.notify(f"Slippage: {slippage_pct}%")

            if "priceWithSlippage" in quote_resp:
                self.notify(f"Price with Slippage: {quote_resp['priceWithSlippage']} {quote_token}/{base_token}")

            # Show what user will spend and receive
            if side == "BUY":
                # Buying base with quote
                max_amount_in = quote_resp.get('maxAmountIn')

                self.notify("\nYou will spend:")
                self.notify(f"  Amount: {amount_out} {quote_token} ({token_in})")
                if max_amount_in:
                    self.notify(f"  Maximum (with slippage): {max_amount_in} {quote_token}")

                self.notify("\nYou will receive:")
                self.notify(f"  Amount: {amount} {base_token} ({token_out})")
            else:
                # Selling base for quote
                self.notify("\nYou will spend:")
                self.notify(f"  Amount: {amount} {base_token} ({token_in})")

                self.notify("\nYou will receive:")
                self.notify(f"  Amount: {amount_out} {quote_token} ({token_out})")
                if min_amount_out:
                    self.notify(f"  Minimum (with slippage): {min_amount_out} {quote_token}")

            # Price impact
            if "priceImpact" in quote_resp:
                impact = float(quote_resp["priceImpact"]) * 100
                self.notify(f"  Price Impact: {impact:.2f}%")

            # Execution price (if different from price)
            if "executionPrice" in quote_resp and quote_resp.get('executionPrice') != quote_resp.get('price'):
                self.notify(f"  Execution Price: {quote_resp['executionPrice']} {quote_token}/{base_token}")

            # Display route if available
            if "route" in quote_resp and quote_resp["route"]:
                self.notify("\nRoute:")
                for i, hop in enumerate(quote_resp["route"]):
                    self.notify(f"  {i + 1}. {hop}")

            # Ask if user wants to execute the swap
            self.placeholder_mode = True
            self.app.hide_input = True
            try:
                # Show wallet info in prompt
                chain_name = chain.capitalize()
                execute_now = await self.app.prompt(
                    prompt=f"Do you want to execute this swap now with {chain_name} wallet {wallet_address[:8]}...{wallet_address[-4:]}? (Yes/No) >>> "
                )

                if execute_now.lower() not in ["y", "yes"]:
                    self.notify("Swap cancelled")
                    return

                self.notify("\nExecuting swap...")

                # Create a temporary GatewayConnector instance for this swap
                # This will handle order tracking even without an active strategy
                connector = GatewayConnector(
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
                    "pool_address": pool_address or quote_resp.get("poolAddress"),
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

    # This method is no longer needed since we use GatewayConnector's transaction monitoring
    # Keeping it for backward compatibility but it won't be called
    async def _monitor_swap_transaction(self, chain: str, network: str, tx_hash: str):
        """Monitor a swap transaction until completion - DEPRECATED."""
        pass
