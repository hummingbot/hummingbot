#!/usr/bin/env python
import asyncio
from typing import TYPE_CHECKING, List, Optional

import pandas as pd

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


class GatewayWalletCommand:
    """Handles gateway wallet-related commands"""

    @ensure_gateway_online
    def gateway_wallet(self, action: str = None, args: List[str] = None):
        """
        Manage wallets in gateway.
        Usage:
            gateway wallet list [chain]
            gateway wallet add <chain>
            gateway wallet add-hardware <chain> <address>
            gateway wallet add-read-only <chain> <address>
            gateway wallet remove <chain> <address>
        """
        if action is None:
            self.notify("\nUsage:")
            self.notify("  gateway wallet list [chain]                       - List wallets")
            self.notify("  gateway wallet add <chain>                        - Add a new wallet")
            self.notify("  gateway wallet add-hardware <chain> <address>     - Add a hardware wallet")
            self.notify("  gateway wallet add-read-only <chain> <address>    - Add a read-only wallet")
            self.notify("  gateway wallet remove <chain> <address>           - Remove wallet")
            self.notify("\nExamples:")
            self.notify("  gateway wallet list")
            self.notify("  gateway wallet list ethereum")
            self.notify("  gateway wallet add ethereum")
            self.notify("  gateway wallet add-hardware solana 9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM")
            self.notify("  gateway wallet add-read-only ethereum 0x742d35Cc6634C0532925a3b844Bc9e7595f7aFa")
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

        elif action == "add-read-only":
            if args is None or len(args) < 2:
                self.notify("Error: chain and address parameters are required for 'add-read-only' action")
                return
            chain = args[0]
            address = args[1]
            safe_ensure_future(self._gateway_wallet_add_read_only(chain, address), loop=self.ev_loop)

        elif action == "remove":
            if args is None or len(args) < 2:
                self.notify("Error: chain and address parameters are required for 'remove' action")
                return
            chain = args[0]
            address = args[1]
            safe_ensure_future(self._gateway_wallet_remove(chain, address), loop=self.ev_loop)

        else:
            self.notify(f"Error: Unknown action '{action}'. Use 'list', 'add', 'add-hardware', 'add-read-only', or 'remove'.")

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
                readonly_addresses = wallet.get("readOnlyWalletAddresses", [])
                hardware_addresses = wallet.get("hardwareWalletAddresses", [])

                # Collect all addresses with their types
                all_addresses = []

                for addr in regular_addresses:
                    all_addresses.append(["Regular", addr])

                for addr in readonly_addresses:
                    all_addresses.append(["Read-Only", addr])

                for addr in hardware_addresses:
                    all_addresses.append(["Hardware", addr])

                # Display chain section
                self.notify(f"Chain: {chain}")

                if all_addresses:
                    # Create DataFrame for this chain
                    df = pd.DataFrame(all_addresses, columns=["Type", "Address"])
                    self.notify(df.to_string(index=False))
                else:
                    self.notify("  No wallets configured")

                self.notify("")  # Empty line between chains

            # Show total counts
            total_regular = sum(len(w.get("walletAddresses", [])) for w in wallets)
            total_readonly = sum(len(w.get("readOnlyWalletAddresses", [])) for w in wallets)
            total_hardware = sum(len(w.get("hardwareWalletAddresses", [])) for w in wallets)
            self.notify(f"\nTotal: {total_regular} regular, {total_readonly} read-only, {total_hardware} hardware addresses")

        except Exception as e:
            self.notify(f"Error listing wallets: {str(e)}")

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
            confirm = await self.app.prompt(prompt="\nDo you want to add this wallet? (Yes/No) >>> ")
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
            self.notify(f"Error adding wallet: {str(e)}")
        finally:
            self.placeholder_mode = False
            self.app.hide_input = False
            self.app.change_prompt(prompt=">>> ")

    async def _gateway_wallet_add_read_only(self, chain: str, address: str):
        """Add a read-only wallet to the gateway."""
        try:
            self.notify(f"\nAdding read-only wallet for {chain}")
            self.notify(f"Address: {address}")

            # Add read-only wallet
            response = await self._get_gateway_instance().add_read_only_wallet(chain, address)

            if "error" in response:
                self.notify(f"Error adding read-only wallet: {response['error']}")
            else:
                self.notify("\n✓ Read-only wallet added successfully")
                if "address" in response:
                    self.notify(f"  Address: {response['address']}")

                # Show updated wallet list
                await self._gateway_wallet_list(chain)

        except Exception as e:
            self.notify(f"Error adding read-only wallet: {str(e)}")

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
            self.notify(f"Error removing wallet: {str(e)}")
        finally:
            self.placeholder_mode = False
            self.app.hide_input = False
            self.app.change_prompt(prompt=">>> ")

    async def _gateway_wallet_add_hardware(self, chain: str, address: str):
        """Add a hardware wallet to the gateway."""
        try:
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
            self.notify(f"Error adding hardware wallet: {str(e)}")
