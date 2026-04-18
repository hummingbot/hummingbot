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
        pair = args[0] if args and len(args) > 0 else None
        side = args[1] if args and len(args) > 1 else None
        amount = args[2] if args and len(args) > 2 else None

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

            # Parse swap provider into dex_name and trading_type
            if "/" in swap_provider:
                dex_name, trading_type = swap_provider.split("/", 1)
            else:
                dex_name, trading_type = swap_provider, "router"
            self.notify(f"Using swap provider: {dex_name}/{trading_type}")

            self.notify(f"\nFetching swap quote for {trading_pair} on {connector}...")

            # Get quote from gateway
            trade_side = TradeType.BUY if side == "BUY" else TradeType.SELL

            quote_resp = await self._get_gateway_instance().quote_swap(
                network=network,
                dex=dex_name,
                trading_type=trading_type,
                base_asset=base_token,
                quote_asset=quote_token,
                amount=amount_decimal,
                side=trade_side,
                slippage_pct=None,  # Use default slippage from connector config
                pool_address=None   # Let gateway find the best pool
            )

            if "error" in quote_resp:
                self.notify(f"\nError getting quote: {quote_resp['error']}")
                await swap_connector.stop_network()
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

            # Amount information
            self.notify(f"\nAmount In: {amount_in}")
            self.notify(f"Amount Out: {amount_out}")
            if min_amount_out:
                self.notify(f"Minimum Amount Out: {min_amount_out}")
            if max_amount_in:
                self.notify(f"Maximum Amount In: {max_amount_in}")

            # Display warnings and fee information
            warnings = quote_resp.get("warnings", [])

            # Extract and display fee info
            fee_info = quote_resp.get('feeInfo', {})
            if not fee_info:
                # Try to construct basic fee info from response
                fee_info = {
                    "transactionFee": quote_resp.get('fee', 'N/A'),
                    "transactionFeeSymbol": quote_resp.get('feeAsset', chain.upper())
                }

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
                    await swap_connector.stop_network()
                    return

                self.notify("\nExecuting swap...")

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
                # Note: dex_name not needed since connector already has swap_provider
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
