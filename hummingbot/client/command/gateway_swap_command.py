#!/usr/bin/env python
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

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
    def gateway_swap(self, action: str = None, args: List[str] = None):
        """
        Perform swap operations through gateway.
        Usage:
            gateway swap quote <connector> [network] [base-quote] [side] [amount]   - Get swap quote
            gateway swap execute <connector> [network] [base-quote] [side] [amount] - Execute swap
        """
        if action is None:
            self.notify("\nUsage:")
            self.notify("  gateway swap quote <connector> [network] [base-quote] [side] [amount]   - Get swap quote")
            self.notify("  gateway swap execute <connector> [network] [base-quote] [side] [amount] - Execute swap")
            self.notify("\nExamples:")
            self.notify("  gateway swap quote uniswap")
            self.notify("  gateway swap quote raydium mainnet-beta SOL-USDC SELL 1.5")
            self.notify("  gateway swap execute jupiter mainnet-beta ETH-USDC BUY 0.1")
            return

        if action == "quote":
            # Parse arguments: [connector] [network] [base-quote] [side] [amount]
            connector = args[0] if args and len(args) > 0 else None
            network = args[1] if args and len(args) > 1 else None
            pair = args[2] if args and len(args) > 2 else None
            side = args[3] if args and len(args) > 3 else None
            amount = args[4] if args and len(args) > 4 else None
            safe_ensure_future(self._gateway_swap_quote(connector, network, pair, side, amount), loop=self.ev_loop)

        elif action == "execute":
            # Parse arguments: [connector] [network] [base-quote] [side] [amount]
            connector = args[0] if args and len(args) > 0 else None
            network = args[1] if args and len(args) > 1 else None
            pair = args[2] if args and len(args) > 2 else None
            side = args[3] if args and len(args) > 3 else None
            amount = args[4] if args and len(args) > 4 else None
            safe_ensure_future(self._gateway_swap_execute(connector, network, pair, side, amount), loop=self.ev_loop)

        else:
            self.notify(f"Error: Unknown action '{action}'. Use 'quote' or 'execute'.")

    async def _gateway_swap_quote(self, connector: Optional[str] = None, network: Optional[str] = None,
                                  pair: Optional[str] = None, side: Optional[str] = None, amount: Optional[str] = None):
        """Get a swap quote from gateway."""
        try:
            # Validate required parameters
            if not connector:
                self.notify("\nError: connector is a required parameter.")
                self.notify("Usage: gateway swap quote <connector> [network]")
                return

            # Get connector info to determine chain
            connector_info = await self._get_gateway_instance().get_connector_info(connector)
            if not connector_info:
                self.notify(f"\nError: Connector '{connector}' not found.")
                return

            chain = connector_info.get("chain", "")
            trading_types = connector_info.get("trading_types", [])

            # Get default network if not provided
            if not network:
                network = await self._get_default_network_for_chain(chain)
                if not network:
                    self.notify(f"\nError: Could not determine default network for {chain}.")
                    return
                self.notify(f"Using default network: {network}")

            # Determine connector type (AMM, CLMM, or router)
            connector_type = None
            if "amm" in trading_types:
                connector_type = f"{connector}/amm"
            elif "clmm" in trading_types:
                connector_type = f"{connector}/clmm"
            elif "router" in trading_types:
                connector_type = f"{connector}/router"
            else:
                self.notify(f"\nError: Connector '{connector}' does not support swaps.")
                return

            # Parse pair if provided
            base_token = None
            quote_token = None
            if pair:
                if "-" in pair:
                    parts = pair.split("-", 1)
                    if len(parts) == 2:
                        base_token = parts[0].strip()
                        quote_token = parts[1].strip()
                        # Only uppercase if they're symbols (short strings), not addresses
                        if len(base_token) <= 10:
                            base_token = base_token.upper()
                        if len(quote_token) <= 10:
                            quote_token = quote_token.upper()

            # Only enter interactive mode if parameters are missing
            if not all([base_token, quote_token, side, amount]):
                self.placeholder_mode = True
                self.app.hide_input = True

                try:
                    # Get available tokens
                    tokens_resp = await self._get_gateway_instance().get_tokens(chain, network)
                    tokens = tokens_resp.get("tokens", [])
                    token_symbols = sorted(list(set([t.get("symbol", "") for t in tokens if t.get("symbol")])))

                    # Update completer's token cache
                    if hasattr(self.app.input_field.completer, '_gateway_token_symbols'):
                        self.app.input_field.completer._gateway_token_symbols = token_symbols

                    # Get base token if not provided
                    if not base_token:
                        self.notify(f"\nAvailable tokens on {chain}/{network}: {', '.join(token_symbols[:10])}{'...' if len(token_symbols) > 10 else ''}")
                        base_token = await self.app.prompt(prompt="\nEnter base token (symbol or address): ")
                        if self.app.to_stop_config or not base_token:
                            self.notify("Quote cancelled")
                            return
                        # Only uppercase if it's a symbol (short string), not an address
                        if len(base_token) <= 10:
                            base_token = base_token.upper()

                    # Get quote token if not provided
                    if not quote_token:
                        quote_token = await self.app.prompt(prompt="Enter quote token (symbol or address): ")
                        if self.app.to_stop_config or not quote_token:
                            self.notify("Quote cancelled")
                            return
                        # Only uppercase if it's a symbol (short string), not an address
                        if len(quote_token) <= 10:
                            quote_token = quote_token.upper()

                    # Get amount if not provided
                    if not amount:
                        amount = await self.app.prompt(prompt="Enter amount to trade [1]: ")
                        if self.app.to_stop_config:
                            self.notify("Quote cancelled")
                            return
                        if not amount:
                            amount = "1"  # Default amount

                    # Get side if not provided
                    if not side:
                        side = await self.app.prompt(prompt="Enter side (BUY/SELL) [SELL]: ")
                        if self.app.to_stop_config:
                            self.notify("Quote cancelled")
                            return
                        if not side:
                            side = "SELL"  # Default side

                finally:
                    self.placeholder_mode = False
                    self.app.hide_input = False
                    self.app.change_prompt(prompt=">>> ")

            # Validate side
            if side:
                side = side.upper()
                if side not in ["BUY", "SELL"]:
                    self.notify(f"Error: Invalid side '{side}'. Must be BUY or SELL.")
                    return

            # Construct pair for display (truncate addresses for readability)
            base_display = base_token if len(base_token) <= 10 else f"{base_token[:8]}...{base_token[-4:]}"
            quote_display = quote_token if len(quote_token) <= 10 else f"{quote_token[:8]}...{quote_token[-4:]}"
            pair_display = f"{base_display}-{quote_display}"

            # Validate amount
            try:
                amount_decimal = Decimal(amount)
                if amount_decimal <= 0:
                    self.notify("Error: Amount must be greater than 0")
                    return
            except Exception:
                self.notify(f"Error: Invalid amount '{amount}'")
                return

            # Get wallet address
            wallets_resp = await self._get_gateway_instance().get_wallets(chain)
            if not wallets_resp or not wallets_resp[0].get("signingAddresses"):
                self.notify(f"No wallet found for {chain}. Please add one with 'gateway wallet add {chain}'")
                return
            wallet_address = wallets_resp[0]["signingAddresses"][0]

            # Look up pool address if needed (for AMM/CLMM connectors)
            pool_address = None
            if connector_type in [f"{connector}/amm", f"{connector}/clmm"]:
                self.notify(f"\nSearching for {base_token}/{quote_token} pool...")
                try:
                    # Search for pools with the trading pair
                    pools = await self._get_gateway_instance().get_pools(
                        connector, network, search=f"{base_token}/{quote_token}"
                    )
                    if not pools:
                        # Try reverse search
                        pools = await self._get_gateway_instance().get_pools(
                            connector, network, search=f"{quote_token}/{base_token}"
                        )

                    if pools:
                        # Use the first matching pool
                        pool_address = pools[0].get("address")
                        self.notify(f"Found pool: {pool_address[:10]}...")
                    else:
                        self.notify(f"Error: No pool found for {base_token}/{quote_token} on {connector}")
                        return
                except Exception as e:
                    self.notify(f"Error searching for pool: {str(e)}")
                    return

            # Get connector config to show actual slippage
            slippage_pct = "1"  # Default
            try:
                connector_config = await self._get_gateway_instance().get_config(namespace=connector)
                slippage_pct = str(connector_config.get("slippagePct", 1))
            except Exception:
                pass

            self.notify(f"\nGetting swap quote from {connector} on {network}...")
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

            # Display quote details
            self.notify("\n=== Swap Quote ===")

            # Display Quote ID prominently
            quote_id = quote_resp.get('quoteId')
            if quote_id:
                self.notify(f"Quote ID: {quote_id}")
                self.logger().info(f"Swap quote ID: {quote_id}")

            self.notify(f"Connector: {connector}")
            self.notify(f"Network: {network}")
            self.notify(f"Pair: {pair_display}")
            self.notify(f"Side: {side}")

            # Token addresses
            token_in = quote_resp.get('tokenIn', 'N/A')
            token_out = quote_resp.get('tokenOut', 'N/A')

            # Amounts
            amount_out = quote_resp.get('amountOut', quote_resp.get('expectedOut'))
            min_amount_out = quote_resp.get('minAmountOut', quote_resp.get('minimumOut'))

            if side == "BUY":
                self.notify(f"\nBuying: {amount} {base_token}")
                if token_out != 'N/A':
                    short_token_out = f"{token_out[:6]}...{token_out[-4:]}" if len(token_out) > 12 else token_out
                    self.notify(f"  Token: {short_token_out}")
                if amount_out:
                    self.notify(f"Cost: {amount_out} {quote_token}")
                if token_in != 'N/A':
                    short_token_in = f"{token_in[:6]}...{token_in[-4:]}" if len(token_in) > 12 else token_in
                    self.notify(f"  Token: {short_token_in}")
            else:
                self.notify(f"\nSelling: {amount} {base_token}")
                if token_in != 'N/A':
                    short_token_in = f"{token_in[:6]}...{token_in[-4:]}" if len(token_in) > 12 else token_in
                    self.notify(f"  Token: {short_token_in}")
                if amount_out:
                    self.notify(f"Receive: {amount_out} {quote_token}")
                if token_out != 'N/A':
                    short_token_out = f"{token_out[:6]}...{token_out[-4:]}" if len(token_out) > 12 else token_out
                    self.notify(f"  Token: {short_token_out}")
                if min_amount_out:
                    self.notify(f"Minimum Receive: {min_amount_out} {quote_token}")

            # Price information
            self.notify("\nPrice Information:")
            if "price" in quote_resp:
                self.notify(f"  Current Price: {quote_resp['price']} {quote_token}/{base_token}")

            # Slippage information
            slippage_pct = quote_resp.get('slippagePct', 1.0)  # Default 1% if not provided
            self.notify(f"  Slippage: {slippage_pct}%")

            if "priceWithSlippage" in quote_resp:
                self.notify(f"  Price with Slippage: {quote_resp['priceWithSlippage']} {quote_token}/{base_token}")

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

            # Reminder about quote ID
            if quote_id:
                self.notify(f"\nTo execute this swap, use the quote ID: {quote_id}")

        except Exception as e:
            self.notify(f"Error getting swap quote: {str(e)}")

    async def _gateway_swap_execute(self, connector: Optional[str] = None, network: Optional[str] = None,
                                    pair: Optional[str] = None, side: Optional[str] = None, amount: Optional[str] = None):
        """Execute a swap through gateway."""
        try:
            # Validate required parameters
            if not connector:
                self.notify("\nError: connector is a required parameter.")
                self.notify("Usage: gateway swap execute <connector> [network]")
                return

            # Get connector info to determine chain
            connector_info = await self._get_gateway_instance().get_connector_info(connector)
            if not connector_info:
                self.notify(f"\nError: Connector '{connector}' not found.")
                return

            chain = connector_info.get("chain", "")
            trading_types = connector_info.get("trading_types", [])

            # Get default network if not provided
            if not network:
                network = await self._get_default_network_for_chain(chain)
                if not network:
                    self.notify(f"\nError: Could not determine default network for {chain}.")
                    return
                self.notify(f"Using default network: {network}")

            # Determine connector type
            connector_type = None
            if "amm" in trading_types:
                connector_type = f"{connector}/amm"
            elif "clmm" in trading_types:
                connector_type = f"{connector}/clmm"
            elif "router" in trading_types:
                connector_type = f"{connector}/router"
            else:
                self.notify(f"\nError: Connector '{connector}' does not support swaps.")
                return

            # Always enter interactive mode
            self.placeholder_mode = True
            self.app.hide_input = True

            try:
                # First, ask for quote ID
                quote_id = await self.app.prompt(prompt="\nEnter quote ID (leave blank for new swap): ")
                if self.app.to_stop_config:
                    self.notify("Swap cancelled")
                    return

                # If quote ID provided, use execute-quote endpoint
                if quote_id:
                    # Get wallet address
                    wallets_resp = await self._get_gateway_instance().get_wallets(chain)
                    if not wallets_resp or not wallets_resp[0].get("signingAddresses"):
                        self.notify(f"No wallet found for {chain}. Please add one with 'gateway wallet add {chain}'")
                        return
                    wallet_address = wallets_resp[0]["signingAddresses"][0]

                    self.notify(f"\nExecuting swap with quote ID: {quote_id}")
                    self.logger().info(f"Executing swap with quote ID: {quote_id}")

                    # Execute with quote ID
                    execute_params = {
                        "walletAddress": wallet_address,
                        "network": network,
                        "quoteId": quote_id
                    }

                    # Execute swap using quote
                    execute_resp = await self._get_gateway_instance().connector_request(
                        "POST", connector_type, "execute-quote", data=execute_params
                    )

                    if "error" in execute_resp:
                        self.notify(f"\nError executing swap: {execute_resp['error']}")
                        return

                    # Process response
                    tx_hash = execute_resp.get("signature") or execute_resp.get("hash")
                    tx_status = execute_resp.get("status")

                    if tx_hash:
                        self.notify("\n✓ Swap submitted successfully!")
                        self.notify(f"Transaction hash: {tx_hash}")

                        # Check initial status
                        if tx_status == 1:  # Already confirmed
                            self.notify("\n✓ Swap confirmed!")
                            if execute_resp.get("data"):
                                data = execute_resp["data"]
                                amount_out = data.get('amountOut', 'N/A')
                                self.notify(f"Amount out: {amount_out}")
                                self.logger().info(
                                    f"Swap confirmed - Quote ID: {quote_id}, "
                                    f"Tx Hash: {tx_hash}, "
                                    f"Amount Out: {amount_out}"
                                )
                        elif tx_status == -1:  # Failed
                            self.notify("\n✗ Swap failed")
                        else:  # Pending or not provided, monitor it
                            await self._monitor_swap_transaction(chain, network, tx_hash)
                    else:
                        self.notify("\n✓ Swap request submitted (no transaction hash returned)")

                    return  # Exit early if using quote ID

                # Otherwise, continue with interactive swap flow
                # Parse pair if provided
                base_token = None
                quote_token = None
                if pair:
                    if "-" in pair:
                        parts = pair.split("-", 1)
                        if len(parts) == 2:
                            base_token = parts[0].strip()
                            quote_token = parts[1].strip()
                            # Only uppercase if they're symbols (short strings), not addresses
                            if len(base_token) <= 10:
                                base_token = base_token.upper()
                            if len(quote_token) <= 10:
                                quote_token = quote_token.upper()

                # Only enter interactive mode if parameters are missing
                if not all([base_token, quote_token, side, amount]):
                    # Get available tokens
                    tokens_resp = await self._get_gateway_instance().get_tokens(chain, network)
                    tokens = tokens_resp.get("tokens", [])
                    token_symbols = sorted(list(set([t.get("symbol", "") for t in tokens if t.get("symbol")])))

                    # Update completer's token cache
                    if hasattr(self.app.input_field.completer, '_gateway_token_symbols'):
                        self.app.input_field.completer._gateway_token_symbols = token_symbols

                    # Get base token if not provided
                    if not base_token:
                        self.notify(f"\nAvailable tokens on {chain}/{network}: {', '.join(token_symbols[:10])}{'...' if len(token_symbols) > 10 else ''}")
                        base_token = await self.app.prompt(prompt="\nEnter base token (symbol or address): ")
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
            if side:
                side = side.upper()
                if side not in ["BUY", "SELL"]:
                    self.notify(f"Error: Invalid side '{side}'. Must be BUY or SELL.")
                    return

            # Construct pair for display (truncate addresses for readability)
            base_display = base_token if len(base_token) <= 10 else f"{base_token[:8]}...{base_token[-4:]}"
            quote_display = quote_token if len(quote_token) <= 10 else f"{quote_token[:8]}...{quote_token[-4:]}"
            pair = f"{base_display}-{quote_display}"

            # Validate amount
            try:
                amount_decimal = Decimal(amount)
                if amount_decimal <= 0:
                    self.notify("Error: Amount must be greater than 0")
                    return
            except Exception:
                self.notify(f"Error: Invalid amount '{amount}'")
                return

            # Get wallet address
            wallets_resp = await self._get_gateway_instance().get_wallets(chain)
            if not wallets_resp or not wallets_resp[0].get("signingAddresses"):
                self.notify(f"No wallet found for {chain}. Please add one with 'gateway wallet add {chain}'")
                return
            wallet_address = wallets_resp[0]["signingAddresses"][0]

            # Look up pool address if needed (for AMM/CLMM connectors)
            pool_address = None
            if connector_type in [f"{connector}/amm", f"{connector}/clmm"]:
                self.notify(f"\nSearching for {base_token}/{quote_token} pool...")
                try:
                    # Search for pools with the trading pair
                    pools = await self._get_gateway_instance().get_pools(
                        connector, network, search=f"{base_token}/{quote_token}"
                    )
                    if not pools:
                        # Try reverse search
                        pools = await self._get_gateway_instance().get_pools(
                            connector, network, search=f"{quote_token}/{base_token}"
                        )

                    if pools:
                        # Use the first matching pool
                        pool_address = pools[0].get("address")
                        self.notify(f"Found pool: {pool_address[:10]}...")
                    else:
                        self.notify(f"Error: No pool found for {base_token}/{quote_token} on {connector}")
                        return
                except Exception as e:
                    self.notify(f"Error searching for pool: {str(e)}")
                    return

            # First get a quote to show the user
            self.notify(f"\nGetting swap quote from {connector} on {network}...")

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

            # Display quote and ask for confirmation
            self.notify("\n=== Swap Details ===")

            # Display Quote ID if available
            quote_id = quote_resp.get('quoteId')
            if quote_id:
                self.notify(f"Quote ID: {quote_id}")
                self.logger().info(f"Executing swap with quote ID: {quote_id}")

            self.notify(f"Connector: {connector}")
            self.notify(f"Network: {network}")
            self.notify(f"Wallet: {wallet_address}")
            self.notify(f"Pair: {pair}")
            self.notify(f"Side: {side}")

            # Amounts
            amount_out = quote_resp.get('amountOut', quote_resp.get('expectedOut'))
            min_amount_out = quote_resp.get('minAmountOut', quote_resp.get('minimumOut'))
            max_amount_in = quote_resp.get('maxAmountIn')

            if side == "BUY":
                self.notify(f"\nBuying: {amount} {base_token}")
                if amount_out:
                    self.notify(f"Cost: {amount_out} {quote_token}")
                if max_amount_in:
                    self.notify(f"Maximum Cost: {max_amount_in} {quote_token}")
            else:
                self.notify(f"\nSelling: {amount} {base_token}")
                if amount_out:
                    self.notify(f"Receive: {amount_out} {quote_token}")
                if min_amount_out:
                    self.notify(f"Minimum Receive: {min_amount_out} {quote_token}")

            # Price information
            self.notify("\nPrice Information:")
            if "price" in quote_resp:
                self.notify(f"  Current Price: {quote_resp['price']} {quote_token}/{base_token}")

            # Slippage information
            slippage_pct = quote_resp.get('slippagePct', 1.0)  # Default 1% if not provided
            self.notify(f"  Slippage: {slippage_pct}%")

            if "priceWithSlippage" in quote_resp:
                self.notify(f"  Price with Slippage: {quote_resp['priceWithSlippage']} {quote_token}/{base_token}")

            # Price impact
            if "priceImpact" in quote_resp:
                impact = float(quote_resp["priceImpact"]) * 100
                self.notify(f"  Price Impact: {impact:.2f}%")

            # Prompt for confirmation
            self.placeholder_mode = True
            self.app.hide_input = True
            try:
                confirm = await self.app.prompt(prompt="\nDo you want to execute this swap? (Yes/No) >>> ")
                if confirm.lower() not in ["y", "yes"]:
                    self.notify("Swap cancelled")
                    return
            finally:
                self.placeholder_mode = False
                self.app.hide_input = False
                self.app.change_prompt(prompt=">>> ")

            # Execute the swap
            self.notify("\nExecuting swap...")

            # Add slippage tolerance
            slippage = 0.01  # 1% default slippage
            if "minimumOut" in quote_resp:
                minimum_out = quote_resp["minimumOut"]
            else:
                # Calculate minimum out based on expected out and slippage
                expected_out = Decimal(quote_resp.get("expectedOut", "0"))
                minimum_out = str(expected_out * Decimal(1 - slippage))

            execute_params = {
                "chain": chain,
                "network": network,
                "connector": connector_type,
                "baseToken": base_token,
                "quoteToken": quote_token,
                "amount": str(amount_decimal),
                "side": side,
                "walletAddress": wallet_address,
                "minimumOut": minimum_out
            }

            # Add pool address if we found one
            if pool_address:
                execute_params["poolAddress"] = pool_address
            # Or use pool address from quote response
            elif "poolAddress" in quote_resp:
                execute_params["poolAddress"] = quote_resp["poolAddress"]

            # Add route if available
            if "route" in quote_resp:
                execute_params["route"] = quote_resp["route"]

            # Execute swap
            execute_resp = await self._get_gateway_instance().connector_request(
                "POST", connector_type, "execute-swap", data=execute_params
            )

            if "error" in execute_resp:
                self.notify(f"\nError executing swap: {execute_resp['error']}")
                return

            # Display transaction details
            tx_hash = execute_resp.get("signature") or execute_resp.get("hash")
            tx_status = execute_resp.get("status")

            if tx_hash:
                self.notify("\n✓ Swap submitted successfully!")
                self.notify(f"Transaction hash: {tx_hash}")

                # Check initial status
                if tx_status == 1:  # Already confirmed
                    self.notify("\n✓ Swap confirmed!")
                    if execute_resp.get("data"):
                        data = execute_resp["data"]
                        amount_out = data.get('amountOut', 'N/A')
                        self.notify(f"Amount out: {amount_out}")
                        self.logger().info(
                            f"Swap confirmed - Pair: {pair}, "
                            f"Side: {side}, "
                            f"Amount: {amount}, "
                            f"Tx Hash: {tx_hash}, "
                            f"Amount Out: {amount_out}"
                        )
                elif tx_status == -1:  # Failed
                    self.notify("\n✗ Swap failed")
                else:  # Pending or not provided, monitor it
                    await self._monitor_swap_transaction(chain, network, tx_hash)
            else:
                self.notify("\n✓ Swap request submitted (no transaction hash returned)")

        except Exception as e:
            self.notify(f"Error executing swap: {str(e)}")

    async def _monitor_swap_transaction(self, chain: str, network: str, tx_hash: str):
        """Monitor a swap transaction until completion."""
        if chain not in ["ethereum", "solana"]:
            return

        self.notify("\nMonitoring transaction...")
        import asyncio

        # Small delay to allow transaction to propagate
        await asyncio.sleep(2)

        displayed_pending = False
        error_count = 0
        max_errors = 3

        while True:
            try:
                poll_resp = await self._get_gateway_instance().get_transaction_status(chain, network, tx_hash)
                tx_status = poll_resp.get("txStatus")

                if tx_status == 1:  # Confirmed
                    self.notify("\n✓ Swap confirmed!")
                    block = poll_resp.get("txBlock", "unknown")
                    if block != "unknown":
                        self.notify(f"Block: {block}")
                    self.logger().info(
                        f"Swap confirmed - Tx Hash: {tx_hash}, "
                        f"Block: {block}"
                    )
                    break
                elif tx_status == 2:  # Pending
                    if not displayed_pending:
                        self.notify("Transaction pending...")
                        displayed_pending = True
                    await asyncio.sleep(2)
                else:  # Failed or unknown
                    self.notify("\n✗ Swap failed")
                    if poll_resp.get("txReceipt"):
                        self.notify(f"Receipt: {poll_resp['txReceipt']}")
                    break
            except Exception as e:
                error_count += 1
                self.logger().error(f"Error polling transaction {tx_hash}: {str(e)}")
                if error_count >= max_errors:
                    self.notify("\n⚠️  Transaction monitoring stopped due to repeated errors.")
                    self.notify(f"You can check the transaction manually: {tx_hash}")
                    break
                await asyncio.sleep(2)
