#!/usr/bin/env python
from typing import TYPE_CHECKING, List, Optional

import pandas as pd

from hummingbot.connector.gateway.utils.command_utils import GatewayCommandUtils
from hummingbot.core.utils.async_utils import safe_ensure_future

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication  # noqa: F401


class GatewayTokenCommand:
    """Handles gateway token-related commands"""

    @GatewayCommandUtils.ensure_gateway_online
    def gateway_token(self, action: str = None, args: List[str] = None):
        """
        Manage tokens in gateway.
        Usage:
            gateway token list <chain> <network>                    - List tokens
            gateway token show <chain> <network> <symbol_or_address> - Show token details
            gateway token add <chain> <network>                      - Add a new token (interactive)
            gateway token remove <chain> <network> <address>         - Remove token by address
        """
        if action is None:
            self.notify("\nUsage:")
            self.notify("  gateway token list <chain> <network>                       - List tokens")
            self.notify("  gateway token show <chain> <network> <symbol_or_address>  - Show token details")
            self.notify("  gateway token add <chain> <network>                       - Add a new token (interactive)")
            self.notify("  gateway token remove <chain> <network> <address>          - Remove token by address")
            self.notify("\nExamples:")
            self.notify("  gateway token list ethereum mainnet")
            self.notify("  gateway token show ethereum base USDC")
            return

        if action == "list":
            # Parse positional arguments: [chain] [network]
            chain = args[0] if args and len(args) > 0 else None
            network = args[1] if args and len(args) > 1 else None
            safe_ensure_future(self._gateway_token_list(chain, network), loop=self.ev_loop)

        elif action == "add":
            if args is None or len(args) < 2:
                self.notify("Error: chain and network parameters are required for 'add' action")
                return
            chain = args[0]
            network = args[1]
            safe_ensure_future(self._gateway_token_add(chain, network), loop=self.ev_loop)

        elif action == "remove":
            if args is None or len(args) < 3:
                self.notify("Error: chain, network and address parameters are required for 'remove' action")
                return
            chain = args[0]
            network = args[1]
            address = args[2]
            safe_ensure_future(self._gateway_token_remove(chain, network, address), loop=self.ev_loop)

        elif action == "show":
            if args is None or len(args) < 3:
                self.notify("Error: chain, network and symbol_or_address parameters are required for 'show' action")
                return
            chain = args[0]
            network = args[1]
            symbol_or_address = args[2]
            safe_ensure_future(self._gateway_token_show(chain, network, symbol_or_address), loop=self.ev_loop)

        else:
            self.notify(f"Error: Unknown action '{action}'. Use 'list', 'show', 'add', or 'remove'.")

    async def _gateway_token_list(self, chain: Optional[str] = None, network: Optional[str] = None):
        """List tokens from gateway with optional filters."""
        try:
            # If no chain specified, get all chains/networks
            if not chain:
                chains_networks = await GatewayCommandUtils.get_all_chains_networks(self._get_gateway_instance())
                all_tokens = []

                for chain_name, networks in chains_networks.items():
                    for net in networks:
                        if network and net != network:
                            continue
                        try:
                            response = await self._get_gateway_instance().get_tokens(chain_name, net)
                            tokens = response.get("tokens", [])
                            for token in tokens:
                                token["chain"] = chain_name
                                token["network"] = net
                                all_tokens.append(token)
                        except Exception:
                            # Skip if can't get tokens for this chain/network
                            pass

                if not all_tokens:
                    self.notify("No tokens found")
                    return

                # Display tokens in a table
                columns = ["Chain", "Network", "Symbol", "Name", "Address", "Decimals"]
                data = []
                for token in all_tokens:
                    data.append([
                        token.get("chain", ""),
                        token.get("network", ""),
                        token.get("symbol", ""),
                        token.get("name", ""),
                        token.get("address", "")[:10] + "..." if token.get("address") else "",
                        str(token.get("decimals", ""))
                    ])

                df = pd.DataFrame(data, columns=columns)
                self.notify(f"\nTokens ({len(all_tokens)} total):")
                self.notify(df.to_string(index=False))

            else:
                # Validate chain/network combination
                chain, network, error = await GatewayCommandUtils.validate_chain_network(
                    self._get_gateway_instance(), chain, network
                )
                if error:
                    self.notify(error)
                    return

                response = await self._get_gateway_instance().get_tokens(chain, network)
                tokens = response.get("tokens", [])

                if not tokens:
                    self.notify(f"No tokens found for {chain}/{network}")
                    return

                # Display tokens in a table
                columns = ["Symbol", "Name", "Address", "Decimals"]
                data = []
                for token in tokens:
                    data.append([
                        token.get("symbol", ""),
                        token.get("name", ""),
                        token.get("address", "")[:10] + "..." if token.get("address") else "",
                        str(token.get("decimals", ""))
                    ])

                df = pd.DataFrame(data, columns=columns)
                self.notify(f"\nTokens for {chain}/{network} ({len(tokens)} total):")
                self.notify(df.to_string(index=False))

        except Exception as e:
            self.notify(GatewayCommandUtils.format_gateway_exception(e))

    async def _gateway_token_add(self, chain: str, network: str):
        """Add a new token to the gateway."""
        try:
            self.placeholder_mode = True
            self.app.hide_input = True

            self.notify(f"\nAdding a new token to {chain}/{network}")
            self.notify("Please provide the following token information:\n")

            # Prompt for token symbol
            symbol = await self.app.prompt(prompt="Enter token symbol (e.g., USDC) >>> ")
            if self.app.to_stop_config or not symbol:
                self.notify("Token addition cancelled")
                return
            symbol = GatewayCommandUtils.normalize_token_symbol(symbol)

            # Prompt for token name
            name = await self.app.prompt(prompt="Enter token name (e.g., USD Coin) >>> ")
            if self.app.to_stop_config or not name:
                self.notify("Token addition cancelled")
                return

            # Prompt for token address
            address = await self.app.prompt(prompt="Enter token contract address >>> ")
            if self.app.to_stop_config or not address:
                self.notify("Token addition cancelled")
                return

            # Validate address
            address, error = GatewayCommandUtils.validate_address(address)
            if error:
                self.notify(error)
                return

            # Prompt for decimals
            decimals_str = await self.app.prompt(prompt="Enter token decimals (e.g., 6 for USDC, 18 for most tokens) >>> ")
            if self.app.to_stop_config or not decimals_str:
                self.notify("Token addition cancelled")
                return

            try:
                decimals = int(decimals_str)
                if decimals < 0 or decimals > 255:
                    self.notify("Error: decimals must be between 0 and 255")
                    return
            except ValueError:
                self.notify(f"Error: decimals must be an integer, got '{decimals_str}'")
                return

            # Confirm addition
            self.notify("\nToken to be added:")
            self.notify(f"  Chain: {chain}")
            self.notify(f"  Network: {network}")
            self.notify(f"  Name: {name}")
            self.notify(f"  Symbol: {symbol}")
            self.notify(f"  Address: {address}")
            self.notify(f"  Decimals: {decimals}")

            confirm = await self.app.prompt(prompt="\nDo you want to add this token? (Yes/No) >>> ")
            if confirm.lower() not in ["y", "yes"]:
                self.notify("Token addition cancelled")
                return

            # Add token
            token_data = {
                "name": name,
                "symbol": symbol,
                "address": address,
                "decimals": decimals
            }
            response = await self._get_gateway_instance().add_token(chain, network, token_data)

            if "error" in response:
                self.notify(f"Error adding token: {response['error']}")
            else:
                self.notify(f"\n✓ Token {symbol} added successfully to {chain}/{network}.")

        except Exception as e:
            self.notify(GatewayCommandUtils.format_gateway_exception(e))
        finally:
            self.placeholder_mode = False
            self.app.hide_input = False
            self.app.change_prompt(prompt=">>> ")

    async def _gateway_token_remove(self, chain: str, network: str, address: str):
        """Remove a token from the gateway."""
        try:
            # Try to get token details first
            token_info = await self._get_gateway_instance().get_token(address, chain, network)

            if "error" not in token_info and "token" in token_info:
                token = token_info["token"]
                self.notify(f"\nRemoving token from {chain}/{network}:")
                self.notify(f"  Name: {token.get('name', 'Unknown')}")
                self.notify(f"  Symbol: {token.get('symbol', 'Unknown')}")
                self.notify(f"  Address: {address}")
            else:
                self.notify(f"\nRemoving token {address} from {chain}/{network}")

            confirm = await self.app.prompt(prompt="\nDo you want to remove this token? (Yes/No) >>> ")
            if confirm.lower() in ["y", "yes"]:
                # Remove token
                response = await self._get_gateway_instance().remove_token(address, chain, network)

                if "error" in response:
                    self.notify(f"Error removing token: {response['error']}")
                else:
                    self.notify(f"\n✓ Token removed successfully from {chain}/{network}.")
            else:
                self.notify("Token removal cancelled")

        except Exception as e:
            self.notify(GatewayCommandUtils.format_gateway_exception(e))

    async def _gateway_token_show(self, chain: str, network: str, symbol_or_address: str):
        """Show details for a specific token."""
        try:
            # Get token details
            response = await self._get_gateway_instance().get_token(symbol_or_address, chain, network)

            if "error" in response:
                self.notify(f"Error: {response['error']}")
                return

            if "token" not in response:
                self.notify(f"Token '{symbol_or_address}' not found on {chain}/{network}")
                return

            # Display token details
            token = response["token"]
            self.notify("\nToken Details:")
            self.notify(f"  Chain: {response.get('chain', chain)}")
            self.notify(f"  Network: {response.get('network', network)}")
            self.notify(f"  Name: {token.get('name', 'N/A')}")
            self.notify(f"  Symbol: {token.get('symbol', 'N/A')}")
            self.notify(f"  Address: {token.get('address', 'N/A')}")
            self.notify(f"  Decimals: {token.get('decimals', 'N/A')}")

        except Exception as e:
            error_msg = str(e)
            if "NotFoundError" in error_msg or "404" in error_msg:
                self.notify(f"Token '{symbol_or_address}' not found on {chain}/{network}")
                self.notify("Please check the token symbol/address or try adding it with 'gateway token add'")
            else:
                self.notify(GatewayCommandUtils.format_gateway_exception(e))
