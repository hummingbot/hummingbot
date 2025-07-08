#!/usr/bin/env python
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
            gateway wallet add <chain> <network>
            gateway wallet add-read-only <chain> <network> [address]
            gateway wallet remove <chain> <network> <address>
            gateway wallet remove-read-only <chain> <network> <address>
        """
        if action is None:
            self.notify("\nUsage:")
            self.notify("  gateway wallet list [chain]                                    - List wallets")
            self.notify("  gateway wallet add <chain> <network>                          - Add a new wallet")
            self.notify("  gateway wallet add-read-only <chain> <network> [address]      - Add a read-only wallet")
            self.notify("  gateway wallet remove <chain> <network> <address>             - Remove wallet")
            self.notify("  gateway wallet remove-read-only <chain> <network> <address>   - Remove read-only wallet")
            self.notify("\nExamples:")
            self.notify("  gateway wallet list")
            self.notify("  gateway wallet list ethereum")
            self.notify("  gateway wallet add ethereum mainnet")
            self.notify("  gateway wallet add-read-only solana mainnet-beta")
            return

        if action == "list":
            if args and len(args) > 0:
                chain = args[0]
            else:
                chain = None
            safe_ensure_future(self._gateway_wallet_list(chain), loop=self.ev_loop)

        elif action == "add":
            if args is None or len(args) < 2:
                self.notify("Error: chain and network parameters are required for 'add' action")
                return
            chain = args[0]
            network = args[1]
            safe_ensure_future(self._gateway_wallet_add(chain, network), loop=self.ev_loop)

        elif action == "add-read-only":
            if args is None or len(args) < 2:
                self.notify("Error: chain and network parameters are required for 'add-read-only' action")
                return
            chain = args[0]
            network = args[1]
            address = args[2] if len(args) > 2 else None
            safe_ensure_future(self._gateway_wallet_add_read_only(chain, network, address), loop=self.ev_loop)

        elif action == "remove":
            if args is None or len(args) < 3:
                self.notify("Error: chain, network and address parameters are required for 'remove' action")
                return
            chain = args[0]
            network = args[1]
            address = args[2]
            safe_ensure_future(self._gateway_wallet_remove(chain, network, address), loop=self.ev_loop)

        elif action == "remove-read-only":
            if args is None or len(args) < 3:
                self.notify("Error: chain, network and address parameters are required for 'remove-read-only' action")
                return
            chain = args[0]
            network = args[1]
            address = args[2]
            safe_ensure_future(self._gateway_wallet_remove_read_only(chain, network, address), loop=self.ev_loop)

        else:
            self.notify(f"Error: Unknown action '{action}'. Use 'list', 'add', 'add-read-only', 'remove', or 'remove-read-only'.")

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

            # Display wallets in a table
            columns = ["Chain", "Regular Addresses", "Read-Only Addresses"]
            data = []

            for wallet in wallets:
                chain_name = wallet.get("chain", "")
                regular_addresses = wallet.get("walletAddresses", [])
                readonly_addresses = wallet.get("readOnlyWalletAddresses", [])

                # Format addresses
                regular_str = ", ".join(regular_addresses) if regular_addresses else "None"
                readonly_str = ", ".join(readonly_addresses) if readonly_addresses else "None"

                # Truncate long address lists
                if len(regular_str) > 50:
                    regular_str = regular_str[:47] + "..."
                if len(readonly_str) > 50:
                    readonly_str = readonly_str[:47] + "..."

                data.append([chain_name, regular_str, readonly_str])

            df = pd.DataFrame(data, columns=columns)
            self.notify(f"\nGateway Wallets ({len(wallets)} chains):")
            self.notify(df.to_string(index=False))

            # Show total counts
            total_regular = sum(len(w.get("walletAddresses", [])) for w in wallets)
            total_readonly = sum(len(w.get("readOnlyWalletAddresses", [])) for w in wallets)
            self.notify(f"\nTotal: {total_regular} regular addresses, {total_readonly} read-only addresses")

        except Exception as e:
            self.notify(f"Error listing wallets: {str(e)}")

    async def _gateway_wallet_add(self, chain: str, network: str):
        """Add a new wallet to the gateway."""
        try:
            self.placeholder_mode = True
            self.app.hide_input = True

            self.notify(f"\nAdding a new wallet for {chain}/{network}")
            self.notify("Please provide the private key or mnemonic phrase for the wallet.")
            self.notify("Note: This will be encrypted and stored securely in the gateway.\n")

            if chain.lower() in ["ethereum", "avalanche", "polygon", "bsc", "arbitrum", "optimism", "base", "celo"]:
                # EVM chains support both private key and mnemonic
                self.notify("You can provide either:")
                self.notify("  1. A private key (64 hex characters)")
                self.notify("  2. A mnemonic phrase (12-24 words)")
                secret_type = await self.app.prompt(prompt="\nEnter type (1 for private key, 2 for mnemonic) >>> ")
                if self.app.to_stop_config or secret_type not in ["1", "2"]:
                    self.notify("Wallet addition cancelled")
                    return

                if secret_type == "1":
                    secret = await self.app.prompt(prompt="Enter private key (without 0x prefix) >>> ", is_password=True)
                else:
                    secret = await self.app.prompt(prompt="Enter mnemonic phrase >>> ", is_password=True)
            else:
                # Non-EVM chains (e.g., Solana) typically use private keys
                secret = await self.app.prompt(prompt="Enter private key >>> ", is_password=True)

            if self.app.to_stop_config or not secret:
                self.notify("Wallet addition cancelled")
                return

            # Confirm addition
            confirm = await self.app.prompt(prompt="\nDo you want to add this wallet? (Yes/No) >>> ")
            if confirm.lower() not in ["y", "yes"]:
                self.notify("Wallet addition cancelled")
                return

            # Add wallet
            response = await self._get_gateway_instance().add_wallet(chain, network, secret)

            if "error" in response:
                self.notify(f"Error adding wallet: {response['error']}")
            else:
                self.notify("\n✓ Wallet added successfully")
                if "address" in response:
                    self.notify(f"  Address: {response['address']}")

        except Exception as e:
            self.notify(f"Error adding wallet: {str(e)}")
        finally:
            self.placeholder_mode = False
            self.app.hide_input = False
            self.app.change_prompt(prompt=">>> ")

    async def _gateway_wallet_add_read_only(self, chain: str, network: str, address: Optional[str] = None):
        """Add a read-only wallet to the gateway."""
        try:
            self.placeholder_mode = True
            self.app.hide_input = True

            self.notify(f"\nAdding a read-only wallet for {chain}/{network}")

            if not address:
                self.notify("Please provide the wallet address to track.\n")
                address = await self.app.prompt(prompt="Enter wallet address >>> ")
                if self.app.to_stop_config or not address:
                    self.notify("Read-only wallet addition cancelled")
                    return

            # Confirm addition
            self.notify(f"\nAdding read-only wallet: {address}")
            confirm = await self.app.prompt(prompt="Do you want to add this read-only wallet? (Yes/No) >>> ")
            if confirm.lower() not in ["y", "yes"]:
                self.notify("Read-only wallet addition cancelled")
                return

            # Add read-only wallet
            response = await self._get_gateway_instance().add_read_only_wallet(chain, network, address)

            if "error" in response:
                self.notify(f"Error adding read-only wallet: {response['error']}")
            else:
                self.notify("\n✓ Read-only wallet added successfully")
                self.notify(f"  Address: {address}")

        except Exception as e:
            self.notify(f"Error adding read-only wallet: {str(e)}")
        finally:
            self.placeholder_mode = False
            self.app.hide_input = False
            self.app.change_prompt(prompt=">>> ")

    async def _gateway_wallet_remove(self, chain: str, network: str, address: str):
        """Remove a wallet from the gateway."""
        try:
            # Confirm removal
            self.notify(f"\nRemoving wallet from {chain}/{network}:")
            self.notify(f"  Address: {address}")
            confirm = await self.app.prompt(prompt="\nDo you want to remove this wallet? (Yes/No) >>> ")
            if confirm.lower() in ["y", "yes"]:
                # Remove wallet
                response = await self._get_gateway_instance().remove_wallet(chain, network, address)

                if "error" in response:
                    self.notify(f"Error removing wallet: {response['error']}")
                else:
                    self.notify("\n✓ Wallet removed successfully")
            else:
                self.notify("Wallet removal cancelled")

        except Exception as e:
            self.notify(f"Error removing wallet: {str(e)}")

    async def _gateway_wallet_remove_read_only(self, chain: str, network: str, address: str):
        """Remove a read-only wallet from the gateway."""
        try:
            # Confirm removal
            self.notify(f"\nRemoving read-only wallet from {chain}/{network}:")
            self.notify(f"  Address: {address}")
            confirm = await self.app.prompt(prompt="\nDo you want to remove this read-only wallet? (Yes/No) >>> ")
            if confirm.lower() in ["y", "yes"]:
                # Remove read-only wallet
                response = await self._get_gateway_instance().remove_read_only_wallet(chain, network, address)

                if "error" in response:
                    self.notify(f"Error removing read-only wallet: {response['error']}")
                else:
                    self.notify("\n✓ Read-only wallet removed successfully")
            else:
                self.notify("Read-only wallet removal cancelled")

        except Exception as e:
            self.notify(f"Error removing read-only wallet: {str(e)}")
