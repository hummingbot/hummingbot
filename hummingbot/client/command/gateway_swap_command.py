#!/usr/bin/env python
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from hummingbot.client.command.command_utils import GatewayCommandUtils
from hummingbot.connector.gateway.gateway import Gateway
from hummingbot.connector.utils import split_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.utils.async_utils import safe_ensure_future

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication  # noqa: F401


class GatewaySwapCommand:
    """Handles gateway swap-related commands"""

    def gateway_swap(self, connector: Optional[str] = None, args: List[str] = None):
        """
        Perform swap operations through gateway - shows quote and asks for confirmation.
        Usage: gateway swap <network> [base-quote] [side] [amount]

        Examples:
            gateway swap solana-mainnet-beta SOL-USDC BUY 1
            gateway swap ethereum-mainnet ETH-USDC SELL 0.5
        """
        # Parse arguments: [base-quote] [side] [amount]
        # Also accept shorthand form: <side> <amount> (pair prompted interactively)
        parsed = list(args) if args else []
        pair: Optional[str] = None
        side: Optional[str] = None
        amount: Optional[str] = None

        if parsed and parsed[0].upper() in ("BUY", "SELL"):
            side = parsed[0]
            if len(parsed) > 1:
                amount = parsed[1]
        else:
            if len(parsed) > 0:
                pair = parsed[0]
            if len(parsed) > 1:
                side = parsed[1]
            if len(parsed) > 2:
                amount = parsed[2]

        safe_ensure_future(self._gateway_swap(connector, pair, side, amount), loop=self.ev_loop)

    async def _gateway_swap(self, connector: Optional[str] = None,
                            pair: Optional[str] = None, side: Optional[str] = None, amount: Optional[str] = None):
        """Unified swap flow - get quote first, then ask for confirmation to execute."""
        swap_connector = None
        try:
            if not connector:
                self.notify("Error: Network is required")
                self.notify("Usage: gateway swap <network> <trading-pair> <side> <amount>")
                self.notify("Example: gateway swap solana-mainnet-beta SOL-USDC BUY 1")
                return

            # Parse network format (e.g., "solana-mainnet-beta" -> chain="solana", network="mainnet-beta")
            if "-" not in connector:
                self.notify(f"Error: Invalid network format '{connector}'.")
                self.notify("Use format like 'solana-mainnet-beta' or 'ethereum-mainnet'")
                return

            # Parse chain and network from connector string
            parts = connector.split("-", 1)
            chain = parts[0]
            network = parts[1] if len(parts) > 1 else "mainnet"

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

            if side not in ("BUY", "SELL"):
                self.notify(f"Error: Invalid side '{side}'. Must be BUY or SELL.")
                return

            # Construct trading pair
            trading_pair = f"{base_token}-{quote_token}"

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

            # Create Gateway connector and start network to get swap_provider
            swap_connector = Gateway(
                connector_name=connector,
                chain=chain,
                network=network,
                address=wallet_address,
                trading_pairs=[trading_pair],
            )
            await swap_connector.start_network()

            # Get swap provider from connector (fetched during start_network)
            swap_provider = swap_connector.swap_provider
            if not swap_provider:
                self.notify(f"Error: No swap provider configured for network '{connector}'")
                self.notify("Make sure Gateway has swapProvider set in the network config")
                await swap_connector.stop_network()
                return

            # Parse swap provider into dex_name and trading_type. A provider without a
            # trading type raises: Gateway answers a guessed one with a 400.
            dex_name, trading_type = Gateway._parse_dex_name(swap_provider)
            self.notify(f"Using swap provider: {dex_name}/{trading_type}")

            self.notify(f"\nFetching swap quote for {trading_pair} on {connector}...")

            # Get quote from gateway
            trade_side = TradeType.BUY if side == "BUY" else TradeType.SELL

            quote_resp = await self._get_gateway_instance().quote_swap(
                network=network,
                chain=chain,
                dex=dex_name,
                trading_type=trading_type,
                base_asset=base_token,
                quote_asset=quote_token,
                amount=amount_decimal,
                side=trade_side,
                slippage_pct=None,  # Use default slippage from connector config
            )

            # Fields below are exactly ChainQuoteSwapResponseSchema (gateway
            # src/schemas/chain-schema.ts). Fastify serializes strictly to that schema,
            # so anything outside it (quoteId, warnings, feeInfo, fee/feeAsset) is
            # stripped by Gateway and would always read as absent here.
            token_in = quote_resp.get('tokenIn')
            token_out = quote_resp.get('tokenOut')
            amount_in = quote_resp.get('amountIn')
            amount_out = quote_resp.get('amountOut')
            min_amount_out = quote_resp.get('minAmountOut')
            max_amount_in = quote_resp.get('maxAmountIn')
            price_impact_pct = quote_resp.get('priceImpactPct')
            slippage_pct = quote_resp.get('slippagePct')
            pool_address = quote_resp.get('poolAddress')
            route_path = quote_resp.get('routePath')

            # Display transaction details
            self.notify("\n=== Swap Transaction ===")

            # Token information
            self.notify(f"Token In: {base_token} ({token_in})")
            self.notify(f"Token Out: {quote_token} ({token_out})")

            # Amount information
            self.notify(f"\nAmount In: {amount_in}")
            self.notify(f"Amount Out: {amount_out}")
            if min_amount_out:
                self.notify(f"Minimum Amount Out: {min_amount_out}")
            if max_amount_in:
                self.notify(f"Maximum Amount In: {max_amount_in}")

            # Route/execution details. The unified quote route carries no fee estimate
            # and no warnings, so there is nothing honest to show for them here - the
            # network fee is reported by the execute response instead.
            if price_impact_pct is not None:
                self.notify(f"Price Impact: {price_impact_pct}%")
            if slippage_pct is not None:
                self.notify(f"Slippage Tolerance: {slippage_pct}%")
            if pool_address:
                self.notify(f"Pool: {pool_address}")
            if route_path:
                self.notify(f"Route: {route_path}")

            # Ask if user wants to execute the swap
            await GatewayCommandUtils.enter_interactive_mode(self)
            try:
                # Show wallet info in prompt
                if not await GatewayCommandUtils.prompt_for_confirmation(
                    self, "Do you want to execute this swap now?"
                ):
                    self.notify("Swap cancelled")
                    await swap_connector.stop_network()
                    return

                self.notify("\nExecuting swap...")

                # Use price from quote for better tracking. price is required by
                # ChainQuoteSwapResponseSchema, so a missing one means the response is
                # not a quote - do not silently trade at 0.
                if quote_resp.get('price') is None:
                    self.notify("\nError: Gateway quote carried no price. Cannot execute swap.")
                    await swap_connector.stop_network()
                    return
                price = Decimal(str(quote_resp['price']))

                # No quote kwargs: the unified route caches no quote (there is no
                # quoteId), so the connector re-quotes and executes in one call.
                if side == "BUY":
                    order_id = swap_connector.buy(
                        trading_pair=trading_pair,
                        amount=amount_decimal,
                        price=price,
                        order_type=OrderType.MARKET,
                    )
                else:
                    order_id = swap_connector.sell(
                        trading_pair=trading_pair,
                        amount=amount_decimal,
                        price=price,
                        order_type=OrderType.MARKET,
                    )

                self.notify(f"Order created: {order_id}")
                self.notify("Monitoring transaction status...")

                # Use the common transaction monitoring helper
                result = await GatewayCommandUtils.monitor_transaction_with_timeout(
                    app=self,
                    connector=swap_connector,
                    order_id=order_id,
                    timeout=60.0,
                    check_interval=1.0,
                    pending_msg_delay=3.0
                )

                if result.get("success"):
                    self.notify("\n=== Swap Completed ===")
                    if result.get("tx_hash"):
                        self.notify(f"Transaction: {result['tx_hash']}")
                    if result.get("executed_price"):
                        self.notify(f"Executed Price: {result['executed_price']}")
                    if result.get("executed_amount"):
                        self.notify(f"Executed Amount: {result['executed_amount']}")
                else:
                    error_msg = result.get("error", "Unknown error")
                    self.notify(f"\nSwap failed: {error_msg}")

                await swap_connector.stop_network()

            finally:
                await GatewayCommandUtils.exit_interactive_mode(self)

        except Exception as e:
            self.notify(f"Error: {str(e)}")
            self.logger().exception("Gateway swap error")
            if swap_connector:
                await swap_connector.stop_network()
