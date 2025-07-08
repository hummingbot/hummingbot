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
            gateway swap quote <connector> <network> [pair] [amount] [side]     - Get swap quote
            gateway swap execute <connector> <network> [pair] [amount] [side]   - Execute swap
        """
        if action is None:
            self.notify("\nUsage:")
            self.notify("  gateway swap quote <connector> <network> [pair] [amount] [side]     - Get swap quote")
            self.notify("  gateway swap execute <connector> <network> [pair] [amount] [side]   - Execute swap")
            self.notify("\nExamples:")
            self.notify("  gateway swap quote uniswap mainnet ETH/USDC 1 BUY")
            self.notify("  gateway swap quote raydium mainnet-beta")
            self.notify("  gateway swap execute jupiter mainnet-beta SOL/USDC 0.5 SELL")
            return

        if action == "quote":
            # Parse arguments: [connector] [network] [pair] [amount] [side]
            connector = args[0] if args and len(args) > 0 else None
            network = args[1] if args and len(args) > 1 else None
            pair = args[2] if args and len(args) > 2 else None
            amount = args[3] if args and len(args) > 3 else None
            side = args[4] if args and len(args) > 4 else None
            safe_ensure_future(self._gateway_swap_quote(connector, network, pair, amount, side), loop=self.ev_loop)

        elif action == "execute":
            connector = args[0] if args and len(args) > 0 else None
            network = args[1] if args and len(args) > 1 else None
            pair = args[2] if args and len(args) > 2 else None
            amount = args[3] if args and len(args) > 3 else None
            side = args[4] if args and len(args) > 4 else None
            safe_ensure_future(self._gateway_swap_execute(connector, network, pair, amount, side), loop=self.ev_loop)

        else:
            self.notify(f"Error: Unknown action '{action}'. Use 'quote' or 'execute'.")

    async def _gateway_swap_quote(self, connector: Optional[str] = None, network: Optional[str] = None,
                                  pair: Optional[str] = None, amount: Optional[str] = None, side: Optional[str] = None):
        """Get a swap quote from gateway."""
        try:
            # Validate required parameters
            if not all([connector, network]):
                self.notify("\nError: connector and network are required parameters.")
                self.notify("Usage: gateway swap quote <connector> <network> [pair] [amount] [side]")
                return

            # Get connector info to determine chain
            connector_info = await self._get_gateway_instance().get_connector_info(connector)
            if not connector_info:
                self.notify(f"\nError: Connector '{connector}' not found.")
                return

            chain = connector_info.get("chain", "")
            trading_types = connector_info.get("trading_types", [])

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

            # Enter interactive mode if pair, amount, or side not provided
            if not all([pair, amount, side]):
                self.placeholder_mode = True
                self.app.hide_input = True

                try:
                    # Get pair if not provided
                    if not pair:
                        # Show available tokens
                        tokens_resp = await self._get_gateway_instance().get_tokens(chain, network)
                        tokens = tokens_resp.get("tokens", [])
                        if tokens:
                            self.notify(f"\nAvailable tokens on {chain}/{network}:")
                            token_symbols = sorted(list(set([t.get("symbol", "") for t in tokens if t.get("symbol")])))
                            # Display tokens in columns
                            cols = 5
                            for i in range(0, len(token_symbols), cols):
                                row = "  " + "  ".join(f"{sym:10}" for sym in token_symbols[i:i + cols])
                                self.notify(row)

                        pair = await self.app.prompt(prompt="\nEnter trading pair (e.g., ETH/USDC): ")
                        if self.app.to_stop_config or not pair:
                            self.notify("Quote cancelled")
                            return

                    # Get amount if not provided
                    if not amount:
                        amount = await self.app.prompt(prompt="Enter amount to trade: ")
                        if self.app.to_stop_config or not amount:
                            self.notify("Quote cancelled")
                            return

                    # Get side if not provided
                    if not side:
                        self.notify("\nSelect trade side:")
                        self.notify("  BUY  - Buy base token with quote token")
                        self.notify("  SELL - Sell base token for quote token")
                        side = await self.app.prompt(prompt="Enter side (BUY/SELL): ")
                        if self.app.to_stop_config or not side:
                            self.notify("Quote cancelled")
                            return
                        side = side.upper()
                        if side not in ["BUY", "SELL"]:
                            self.notify(f"Error: Invalid side '{side}'. Must be BUY or SELL.")
                            return

                finally:
                    self.placeholder_mode = False
                    self.app.hide_input = False
                    self.app.change_prompt(prompt=">>> ")

            # Validate amount
            try:
                amount_decimal = Decimal(amount)
                if amount_decimal <= 0:
                    self.notify("Error: Amount must be greater than 0")
                    return
            except Exception:
                self.notify(f"Error: Invalid amount '{amount}'")
                return

            # Parse pair
            if "/" in pair:
                base_token, quote_token = pair.split("/")
            else:
                self.notify(f"Error: Invalid pair format '{pair}'. Use format like ETH/USDC")
                return

            # Get wallet address
            wallets_resp = await self._get_gateway_instance().get_wallets(chain)
            if not wallets_resp or not wallets_resp[0].get("walletAddresses"):
                self.notify(f"No wallet found for {chain}. Please add one with 'gateway wallet add {chain}'")
                return
            wallet_address = wallets_resp[0]["walletAddresses"][0]

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

            self.notify(f"\nGetting swap quote from {connector} on {network}...")
            self.notify(f"  Pair: {pair}")
            self.notify(f"  Amount: {amount}")
            self.notify(f"  Side: {side}")

            # Get quote from gateway
            quote_params = {
                "chain": chain,
                "network": network,
                "connector": connector_type,
                "baseToken": base_token,
                "quoteToken": quote_token,
                "amount": str(amount_decimal),
                "side": side,
                "address": wallet_address
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
            self.notify(f"Connector: {connector}")
            self.notify(f"Network: {network}")
            self.notify(f"Pair: {pair}")

            if side == "BUY":
                self.notify(f"Buying: {amount} {base_token}")
                self.notify(f"Cost: {quote_resp.get('expectedOut', 'N/A')} {quote_token}")
            else:
                self.notify(f"Selling: {amount} {base_token}")
                self.notify(f"Receive: {quote_resp.get('expectedOut', 'N/A')} {quote_token}")

            # Display price information
            if "price" in quote_resp:
                self.notify(f"Price: {quote_resp['price']} {quote_token}/{base_token}")

            if "executionPrice" in quote_resp:
                self.notify(f"Execution Price: {quote_resp['executionPrice']} {quote_token}/{base_token}")

            # Display additional details
            if "priceImpact" in quote_resp:
                impact = float(quote_resp["priceImpact"]) * 100
                self.notify(f"Price Impact: {impact:.2f}%")

            if "minimumOut" in quote_resp:
                self.notify(f"Minimum Received: {quote_resp['minimumOut']}")

            if "gasCost" in quote_resp:
                self.notify(f"Estimated Gas: {quote_resp['gasCost']}")

            # Display route if available
            if "route" in quote_resp and quote_resp["route"]:
                self.notify("\nRoute:")
                for i, hop in enumerate(quote_resp["route"]):
                    self.notify(f"  {i + 1}. {hop}")

        except Exception as e:
            self.notify(f"Error getting swap quote: {str(e)}")

    async def _gateway_swap_execute(self, connector: Optional[str] = None, network: Optional[str] = None,
                                    pair: Optional[str] = None, amount: Optional[str] = None, side: Optional[str] = None):
        """Execute a swap through gateway."""
        try:
            # Validate required parameters
            if not all([connector, network]):
                self.notify("\nError: connector and network are required parameters.")
                self.notify("Usage: gateway swap execute <connector> <network> [pair] [amount] [side]")
                return

            # Get connector info to determine chain
            connector_info = await self._get_gateway_instance().get_connector_info(connector)
            if not connector_info:
                self.notify(f"\nError: Connector '{connector}' not found.")
                return

            chain = connector_info.get("chain", "")
            trading_types = connector_info.get("trading_types", [])

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

            # Enter interactive mode if pair, amount, or side not provided
            if not all([pair, amount, side]):
                self.placeholder_mode = True
                self.app.hide_input = True

                try:
                    # Get pair if not provided
                    if not pair:
                        # Show available tokens
                        tokens_resp = await self._get_gateway_instance().get_tokens(chain, network)
                        tokens = tokens_resp.get("tokens", [])
                        if tokens:
                            self.notify(f"\nAvailable tokens on {chain}/{network}:")
                            token_symbols = sorted(list(set([t.get("symbol", "") for t in tokens if t.get("symbol")])))
                            # Display tokens in columns
                            cols = 5
                            for i in range(0, len(token_symbols), cols):
                                row = "  " + "  ".join(f"{sym:10}" for sym in token_symbols[i:i + cols])
                                self.notify(row)

                        pair = await self.app.prompt(prompt="\nEnter trading pair (e.g., ETH/USDC): ")
                        if self.app.to_stop_config or not pair:
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
                        self.notify("\nSelect trade side:")
                        self.notify("  BUY  - Buy base token with quote token")
                        self.notify("  SELL - Sell base token for quote token")
                        side = await self.app.prompt(prompt="Enter side (BUY/SELL): ")
                        if self.app.to_stop_config or not side:
                            self.notify("Swap cancelled")
                            return
                        side = side.upper()
                        if side not in ["BUY", "SELL"]:
                            self.notify(f"Error: Invalid side '{side}'. Must be BUY or SELL.")
                            return

                finally:
                    self.placeholder_mode = False
                    self.app.hide_input = False
                    self.app.change_prompt(prompt=">>> ")

            # Validate amount
            try:
                amount_decimal = Decimal(amount)
                if amount_decimal <= 0:
                    self.notify("Error: Amount must be greater than 0")
                    return
            except Exception:
                self.notify(f"Error: Invalid amount '{amount}'")
                return

            # Parse pair
            if "/" in pair:
                base_token, quote_token = pair.split("/")
            else:
                self.notify(f"Error: Invalid pair format '{pair}'. Use format like ETH/USDC")
                return

            # Get wallet address
            wallets_resp = await self._get_gateway_instance().get_wallets(chain)
            if not wallets_resp or not wallets_resp[0].get("walletAddresses"):
                self.notify(f"No wallet found for {chain}. Please add one with 'gateway wallet add {chain}'")
                return
            wallet_address = wallets_resp[0]["walletAddresses"][0]

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
                "address": wallet_address
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
            self.notify(f"Connector: {connector}")
            self.notify(f"Network: {network}")
            self.notify(f"Wallet: {wallet_address}")
            self.notify(f"Pair: {pair}")

            if side == "BUY":
                self.notify(f"Buying: {amount} {base_token}")
                self.notify(f"Cost: {quote_resp.get('expectedOut', 'N/A')} {quote_token}")
            else:
                self.notify(f"Selling: {amount} {base_token}")
                self.notify(f"Receive: {quote_resp.get('expectedOut', 'N/A')} {quote_token}")

            # Display price information
            if "price" in quote_resp:
                self.notify(f"Price: {quote_resp['price']} {quote_token}/{base_token}")

            if "executionPrice" in quote_resp:
                self.notify(f"Execution Price: {quote_resp['executionPrice']} {quote_token}/{base_token}")

            # Display additional details
            if "priceImpact" in quote_resp:
                impact = float(quote_resp["priceImpact"]) * 100
                self.notify(f"Price Impact: {impact:.2f}%")

            if "minimumOut" in quote_resp:
                self.notify(f"Minimum Received: {quote_resp['minimumOut']}")

            if "gasCost" in quote_resp:
                self.notify(f"Estimated Gas: {quote_resp['gasCost']}")

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
                "address": wallet_address,
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
            if tx_hash:
                self.notify("\n✓ Swap submitted successfully!")
                self.notify(f"Transaction hash: {tx_hash}")

                # Monitor transaction if on supported chain
                if chain in ["ethereum", "solana"]:
                    self.notify("\nMonitoring transaction...")
                    import asyncio
                    displayed_pending = False

                    while True:
                        try:
                            poll_resp = await self._get_gateway_instance().get_transaction_status(chain, network, tx_hash)
                            tx_status = poll_resp.get("txStatus")

                            if tx_status == 1:  # Confirmed
                                self.notify("\n✓ Swap confirmed!")
                                if poll_resp.get("txBlock"):
                                    self.notify(f"Block: {poll_resp['txBlock']}")
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
                        except Exception:
                            await asyncio.sleep(2)
            else:
                self.notify("\n✓ Swap request submitted (no transaction hash returned)")

        except Exception as e:
            self.notify(f"Error executing swap: {str(e)}")
