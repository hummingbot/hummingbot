#!/usr/bin/env python
import asyncio
from typing import TYPE_CHECKING, List, Optional

import pandas as pd

from hummingbot.connector.gateway.utils.command_utils import GatewayCommandUtils
from hummingbot.core.utils.async_utils import safe_ensure_future

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication  # noqa: F401


class GatewayWalletCommand:
    """Handles gateway wallet-related commands"""

    @GatewayCommandUtils.ensure_gateway_online
    def gateway_wallet(self, action: str = None, args: List[str] = None):
        """
        Manage wallets in gateway.
        Usage:
            gateway wallet list [chain]
            gateway wallet add <chain>
            gateway wallet add-hardware <chain> <address>
            gateway wallet remove <chain> <address>
            gateway wallet setDefault <chain> <address>
        """
        if action is None:
            self.notify("\nUsage:")
            self.notify("  gateway wallet list [chain]                       - List wallets")
            self.notify("  gateway wallet add <chain>                        - Add a new wallet")
            self.notify("  gateway wallet add-hardware <chain> <address>     - Add a hardware wallet")
            self.notify("  gateway wallet remove <chain> <address>           - Remove wallet")
            self.notify("  gateway wallet setDefault <chain> <address>       - Set default wallet for a chain")
            self.notify("\nExamples:")
            self.notify("  gateway wallet list")
            self.notify("  gateway wallet list ethereum")
            self.notify("  gateway wallet add ethereum")
            self.notify("  gateway wallet add-hardware solana 9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM")
            self.notify("  gateway wallet setDefault ethereum 0xDA50C69342216b538Daf06FfECDa7363E0B96684")
            return

        if action == "list":
            if args and len(args) > 0:
                chain = args[0]
            else:
                chain = None
            safe_ensure_future(self._gateway_wallet_list(chain), loop=self.ev_loop)

        elif action == "add":
            if args is None or len(args) < 1:
                self.notify("Error: chain parameter is required for 'add' action")
                return
            chain = args[0]
            safe_ensure_future(self._gateway_wallet_add(chain), loop=self.ev_loop)

        elif action == "add-hardware":
            if args is None or len(args) < 2:
                self.notify("Error: chain and address parameters are required for 'add-hardware' action")
                return
            chain = args[0]
            address = args[1]
            safe_ensure_future(self._gateway_wallet_add_hardware(chain, address), loop=self.ev_loop)

        elif action == "remove":
            if args is None or len(args) < 2:
                self.notify("Error: chain and address parameters are required for 'remove' action")
                return
            chain = args[0]
            address = args[1]
            safe_ensure_future(self._gateway_wallet_remove(chain, address), loop=self.ev_loop)

        elif action == "setDefault":
            if args is None or len(args) < 2:
                self.notify("Error: chain and address parameters are required for 'setDefault' action")
                return
            chain = args[0]
            address = args[1]
            safe_ensure_future(self._gateway_wallet_set_default(chain, address), loop=self.ev_loop)

        else:
            self.notify(f"Error: Unknown action '{action}'. Use 'list', 'add', 'add-hardware', 'remove', or 'setDefault'.")

    async def _gateway_wallet_list(self, chain: Optional[str] = None):
        """List wallets from gateway with optional chain filter."""
        try:
            wallets = await self._get_gateway_instance().get_wallets()

            if not wallets:
                self.notify("No wallets found in gateway")
                return

            # Filter by chain if specified
            if chain:
                filtered_wallets = [w for w in wallets if w.get("chain", "").lower() == chain.lower()]
                if not filtered_wallets:
                    self.notify(f"No wallets found for chain '{chain}'")
                    return
                wallets = filtered_wallets

            # Organize wallets by chain
            self.notify(f"\nGateway Wallets ({len(wallets)} chains):\n")

            # Sort chains alphabetically
            chains = sorted([w.get("chain", "") for w in wallets if w.get("chain", "")])

            for chain in chains:
                # Find wallet data for this chain
                wallet = next((w for w in wallets if w.get("chain") == chain), None)
                if not wallet:
                    continue

                regular_addresses = wallet.get("walletAddresses", [])
                hardware_addresses = wallet.get("hardwareWalletAddresses", [])

                # Get the default wallet for this chain from gateway config
                default_wallet = await self._get_gateway_instance().get_default_wallet_for_chain(chain)

                # Check if default wallet is a placeholder
                is_placeholder = default_wallet in ["<ethereum-wallet-address>", "<solana-wallet-address>"]

                # Collect all addresses with their types and default status
                all_addresses = []

                for addr in regular_addresses:
                    is_default = "✓" if addr == default_wallet else ""
                    all_addresses.append(["Regular", addr, is_default])

                for addr in hardware_addresses:
                    is_default = "✓" if addr == default_wallet else ""
                    all_addresses.append(["Hardware", addr, is_default])

                # Display chain section
                self.notify(f"Chain: {chain}")

                # Show warning if default wallet is placeholder
                if is_placeholder and default_wallet:
                    self.notify(f"  ⚠️  Default wallet not set (currently: {default_wallet})")
                    if all_addresses:
                        self.notify(f"  Please run: gateway wallet setDefault {chain} <address>")

                if all_addresses:
                    # Create DataFrame for this chain
                    df = pd.DataFrame(all_addresses, columns=["Type", "Address", "Default"])
                    self.notify(df.to_string(index=False))
                else:
                    self.notify("  No wallets configured")

                self.notify("")  # Empty line between chains

            # Show total counts
            total_regular = sum(len(w.get("walletAddresses", [])) for w in wallets)
            total_hardware = sum(len(w.get("hardwareWalletAddresses", [])) for w in wallets)
            self.notify(f"\nTotal: {total_regular} regular, {total_hardware} hardware addresses")

        except Exception as e:
            self.notify(GatewayCommandUtils.format_gateway_exception(e))

    async def _gateway_wallet_add(self, chain: str):
        """Add a new wallet to the gateway."""
        try:
            self.placeholder_mode = True
            self.app.hide_input = True

            self.notify(f"\nAdding a new wallet for {chain}")
            self.notify("Please provide the private key for the wallet.")
            self.notify("Note: This will be encrypted using your Hummingbot password and stored securely.\n")

            # Get private key
            private_key = await self.app.prompt(prompt="Enter private key >>> ", is_password=True)

            if self.app.to_stop_config or not private_key:
                self.notify("Wallet addition cancelled")
                return

            # Confirm addition
            confirm = await self.app.prompt(prompt="Do you want to add this wallet? (Yes/No) >>> ")
            if confirm.lower() not in ["y", "yes"]:
                self.notify("Wallet addition cancelled")
                return

            # Add wallet
            response = await self._get_gateway_instance().add_wallet(chain, private_key)

            if "error" in response:
                self.notify(f"Error adding wallet: {response['error']}")
            else:
                self.notify("\n✓ Wallet added successfully")
                if "address" in response:
                    self.notify(f"  Address: {response['address']}")

                # Show updated wallet list
                await self._gateway_wallet_list(chain)

        except Exception as e:
            self.notify(GatewayCommandUtils.format_gateway_exception(e))
        finally:
            self.placeholder_mode = False
            self.app.hide_input = False
            self.app.change_prompt(prompt=">>> ")

    async def _gateway_wallet_remove(self, chain: str, address: str):
        """Remove any type of wallet from the gateway."""
        try:
            self.placeholder_mode = True
            self.app.hide_input = True

            # Confirm removal
            self.notify(f"\nRemoving wallet from {chain}:")
            self.notify(f"  Address: {address}")
            confirm = await self.app.prompt(prompt="\nDo you want to remove this wallet? (Yes/No) >>> ")

            if self.app.to_stop_config:
                self.notify("Wallet removal cancelled")
                return

            if confirm.lower() in ["y", "yes"]:
                # Remove wallet (the API now handles all wallet types with one endpoint)
                response = await self._get_gateway_instance().remove_wallet(chain, address)

                if "error" in response:
                    self.notify(f"Error removing wallet: {response['error']}")
                else:
                    self.notify("\n✓ Wallet removed successfully")

                    # Show updated wallet list
                    await self._gateway_wallet_list(chain)
            else:
                self.notify("Wallet removal cancelled")

        except Exception as e:
            self.notify(GatewayCommandUtils.format_gateway_exception(e))
        finally:
            self.placeholder_mode = False
            self.app.hide_input = False
            self.app.change_prompt(prompt=">>> ")

    async def _gateway_wallet_add_hardware(self, chain: str, address: str):
        """Add a hardware wallet to the gateway."""
        try:
            # Validate address format
            address, error = GatewayCommandUtils.validate_address(address)
            if error:
                self.notify(error)
                return

            self.notify(f"\nAdding hardware wallet for {chain}")
            self.notify(f"Address: {address}")
            self.notify("\nPlease make sure your Ledger device is connected and unlocked.")

            # Add a small delay to allow user to prepare device
            await asyncio.sleep(2)

            # Add hardware wallet
            response = await self._get_gateway_instance().add_hardware_wallet(chain, address)

            if "error" in response:
                self.notify(f"\nError adding hardware wallet: {response['error']}")
            else:
                self.notify("\n✓ Hardware wallet added successfully")
                if "address" in response:
                    self.notify(f"  Address: {response['address']}")
                if "derivationPath" in response:
                    self.notify(f"  Derivation Path: {response['derivationPath']}")

                # Show updated wallet list
                await self._gateway_wallet_list(chain)

        except Exception as e:
            self.notify(GatewayCommandUtils.format_gateway_exception(e))

    async def _gateway_wallet_set_default(self, chain: str, address: str):
        """Set default wallet for a chain."""
        try:
            # First check if the wallet exists
            wallets = await self._get_gateway_instance().get_wallets(chain)
            if not wallets:
                self.notify(f"No wallets found for {chain}")
                return

            wallet = wallets[0]
            all_addresses = wallet.get("walletAddresses", []) + wallet.get("hardwareWalletAddresses", [])

            if address not in all_addresses:
                self.notify(f"Error: Address {address} not found in {chain} wallets")
                self.notify(f"Available addresses: {', '.join(all_addresses)}")
                return

            # Call gateway setDefault endpoint
            response = await self._get_gateway_instance().set_default_wallet(chain, address)

            if "error" in response:
                self.notify(f"Error setting default wallet: {response.get('error', 'Unknown error')}")
            else:
                self.notify(f"✓ Default wallet for {chain} set to: {address}")

        except Exception as e:
            self.notify(GatewayCommandUtils.format_gateway_exception(e))
