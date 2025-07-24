# Gateway LP Command Technical Design Document

## Table of Contents
1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Command Infrastructure](#command-infrastructure)
4. [Add Liquidity Implementation](#add-liquidity-implementation)
5. [Remove Liquidity Implementation](#remove-liquidity-implementation)
6. [Position Info Implementation](#position-info-implementation)
7. [Collect Fees Implementation](#collect-fees-implementation)
8. [Common Utilities](#common-utilities)
9. [Error Handling](#error-handling)
10. [Testing Strategy](#testing-strategy)

## Overview

The `gateway lp` command provides liquidity provision functionality for both AMM (Automated Market Maker) and CLMM (Concentrated Liquidity Market Maker) protocols through Gateway.

### Command Structure
```
gateway lp <connector> add-liquidity
gateway lp <connector> remove-liquidity
gateway lp <connector> position-info
gateway lp <connector> collect-fees
```

### Key Design Principles
- **Interactive-only mode**: All sub-commands use interactive prompts for better UX
- **Connector agnostic**: Support both AMM and CLMM through polymorphic design
- **Consistent UX**: Follow patterns established by swap and approve commands
- **Error resilience**: Comprehensive validation and clear error messages
- **Transaction safety**: Show balance impacts and require confirmations

## Architecture

### File Structure
```
hummingbot/
├── client/
│   ├── command/
│   │   ├── gateway_lp_command.py          # Main LP command implementation
│   │   └── gateway_command.py             # Add LP command routing
│   └── parser.py                          # Add LP command parsing
├── connector/
│   └── gateway/
│       ├── command_utils.py               # Add LP-specific utilities
│       ├── gateway_lp.py                  # Existing LP connector
│       └── common_types.py                # Ensure LP types are defined
└── docs/
    └── gateway-lp-command-design.md       # This document
```

### Class Hierarchy
```python
GatewayCommand (existing)
    └── delegates to → GatewayLPCommand
                         ├── _add_liquidity()
                         ├── _remove_liquidity()
                         ├── _position_info()
                         └── _collect_fees()

GatewayLPCommand uses:
    - GatewayCommandUtils (for common operations)
    - GatewayLp connector (for LP operations)
    - GatewayHttpClient (for direct API calls)
```

## Command Infrastructure

### 1. Parser Updates (parser.py)

```python
# In parser.py, within the gateway_subparsers section:

# Add gateway LP parser
gateway_lp_parser = gateway_subparsers.add_parser(
    "lp",
    help="Manage liquidity positions on DEX protocols"
)
gateway_lp_parser.add_argument(
    "connector",
    nargs="?",
    type=str,
    help="Gateway connector name (e.g., 'uniswap/amm', 'raydium/clmm')"
)
gateway_lp_parser.add_argument(
    "action",
    nargs="?",
    type=str,
    choices=["add-liquidity", "remove-liquidity", "position-info", "collect-fees"],
    help="LP action to perform"
)
gateway_lp_parser.set_defaults(func=hummingbot.gateway_lp)
```

### 2. Completer Updates (completer.py)

```python
# In completer.py __init__ method, add these completers:

# Update the main gateway completer to include "lp"
self._gateway_completer = WordCompleter(
    ["list", "balance", "config", "generate-certs", "ping", "allowance", "approve", "swap", "lp"],
    ignore_case=True
)

# Add LP-specific completers
self._gateway_lp_completer = WordCompleter(GATEWAY_CONNECTORS, ignore_case=True)
self._gateway_lp_action_completer = WordCompleter(
    ["add-liquidity", "remove-liquidity", "position-info", "collect-fees"],
    ignore_case=True
)

# Add completion methods:

def _complete_gateway_lp_connector(self, document: Document) -> bool:
    text_before_cursor: str = document.text_before_cursor
    if not text_before_cursor.startswith("gateway lp "):
        return False
    # Only complete if we're at the first argument (connector)
    args_after_lp = text_before_cursor[11:].strip()  # Remove "gateway lp "
    # If there's no space after removing "gateway lp ", we're completing the connector
    return " " not in args_after_lp

def _complete_gateway_lp_action(self, document: Document) -> bool:
    text_before_cursor: str = document.text_before_cursor
    if not text_before_cursor.startswith("gateway lp "):
        return False
    # Complete action if we have connector but not action yet
    args_after_lp = text_before_cursor[11:].strip()  # Remove "gateway lp "
    parts = args_after_lp.split()
    # Complete action if we have exactly one part (connector) and are starting the second
    return len(parts) == 1 or (len(parts) == 2 and not args_after_lp.endswith(" "))

# In get_completions method, add:

elif self._complete_gateway_lp_connector(document):
    for c in self._gateway_lp_completer.get_completions(document, complete_event):
        yield c

elif self._complete_gateway_lp_action(document):
    for c in self._gateway_lp_action_completer.get_completions(document, complete_event):
        yield c
```

### 3. Update gateway_command.py

```python
# In gateway_command.py

def gateway(self):
    """Show gateway help when no subcommand is provided."""
    # ... existing help text ...
    self.notify("  gateway lp <connector> <action>                   - Manage liquidity positions")
    # ... rest of help ...

@ensure_gateway_online
def gateway_lp(self, connector: Optional[str] = None, action: Optional[str] = None):
    """
    Gateway liquidity provision management.
    Usage:
        gateway lp <connector> add-liquidity
        gateway lp <connector> remove-liquidity
        gateway lp <connector> position-info
        gateway lp <connector> collect-fees
    """
    # Delegate to the LP command handler
    from hummingbot.client.command.gateway_lp_command import GatewayLPCommand
    GatewayLPCommand.gateway_lp(self, connector, action)
```

### 4. Integration with Existing Gateway Infrastructure

The gateway LP command follows the same patterns as other gateway commands:

- **Connector Format**: Uses the same `connector/type` format (e.g., `uniswap/amm`, `raydium/clmm`)
- **Chain/Network Detection**: Auto-detects chain and network from connector configuration
- **Wallet Management**: Uses default wallet for the chain or prompts if not set
- **Transaction Monitoring**: Reuses the same transaction monitoring utilities
- **Balance Impact**: Shows consistent balance impact tables like swap and approve commands
- **Error Handling**: Follows the same error handling patterns with clear user messages

### 5. Command Examples

```bash
# Add liquidity to Uniswap V2 (AMM)
>>> gateway lp uniswap/amm add-liquidity

# Remove liquidity from Raydium CLMM pool
>>> gateway lp raydium/clmm remove-liquidity

# Check positions on Jupiter
>>> gateway lp jupiter/clmm position-info

# Collect fees from Uniswap V3 position
>>> gateway lp uniswap/clmm collect-fees
```

### 6. Create gateway_lp_command.py

```python
#!/usr/bin/env python
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

import pandas as pd

from hummingbot.connector.gateway.command_utils import GatewayCommandUtils
from hummingbot.connector.gateway.common_types import ConnectorType, get_connector_type
from hummingbot.connector.gateway.gateway_lp import (
    AMMPoolInfo, AMMPositionInfo, CLMMPoolInfo, CLMMPositionInfo, GatewayLp
)
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.utils.async_utils import safe_ensure_future

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication


class GatewayLPCommand:
    """Handles gateway liquidity provision commands"""

    def gateway_lp(self, connector: Optional[str], action: Optional[str], args: List[str] = None):
        """
        Main entry point for LP commands.
        Routes to appropriate sub-command handler.
        """
        if not connector:
            self.notify("\nError: Connector is required")
            self.notify("Usage: gateway lp <connector> <action>")
            return

        if not action:
            self.notify("\nAvailable LP actions:")
            self.notify("  add-liquidity     - Add liquidity to a pool")
            self.notify("  remove-liquidity  - Remove liquidity from a position")
            self.notify("  position-info     - View your liquidity positions")
            self.notify("  collect-fees      - Collect accumulated fees")
            return

        # Route to appropriate handler
        if action == "add-liquidity":
            safe_ensure_future(self._add_liquidity(connector), loop=self.ev_loop)
        elif action == "remove-liquidity":
            safe_ensure_future(self._remove_liquidity(connector), loop=self.ev_loop)
        elif action == "position-info":
            safe_ensure_future(self._position_info(connector), loop=self.ev_loop)
        elif action == "collect-fees":
            safe_ensure_future(self._collect_fees(connector), loop=self.ev_loop)
        else:
            self.notify(f"\nError: Unknown action '{action}'")
            self.notify("Valid actions: add-liquidity, remove-liquidity, position-info, collect-fees")
```

### 3. Update Parser

```python
# In parser.py, add to gateway parser

gateway_lp_parser = gateway_parser._subcommands._group_actions[0].add_parser(
    "lp",
    help="Manage liquidity positions"
)
gateway_lp_parser.add_argument(
    "connector",
    nargs="?",
    type=str,
    help="Gateway connector name (e.g., 'uniswap/amm')"
)
gateway_lp_parser.add_argument(
    "action",
    nargs="?",
    type=str,
    choices=["add-liquidity", "remove-liquidity", "position-info", "collect-fees"],
    help="LP action to perform"
)
gateway_lp_parser.set_defaults(func=self.gateway_lp)
```

## Add Liquidity Implementation

### Detailed Flow and Pseudo-code

```python
async def _add_liquidity(
    self,  # type: HummingbotApplication
    connector: str
):
    """
    Interactive flow for adding liquidity to a pool.
    Supports both AMM and CLMM protocols.
    """
    try:
        # 1. Validate connector and get chain/network info
        if "/" not in connector:
            self.notify(f"Error: Invalid connector format '{connector}'. Use format like 'uniswap/amm'")
            return

        chain, network, error = await GatewayCommandUtils.get_connector_chain_network(
            self._get_gateway_instance(), connector
        )
        if error:
            self.notify(f"Error: {error}")
            return

        # 2. Get wallet address
        wallet_address, error = await GatewayCommandUtils.get_default_wallet(
            self._get_gateway_instance(), chain
        )
        if error:
            self.notify(f"Error: {error}")
            return

        # 3. Determine connector type
        connector_type = get_connector_type(connector)
        is_clmm = connector_type == ConnectorType.CLMM

        self.notify(f"\n=== Add Liquidity to {connector} ===")
        self.notify(f"Chain: {chain}")
        self.notify(f"Network: {network}")
        self.notify(f"Wallet: {GatewayCommandUtils.format_address_display(wallet_address)}")
        self.notify(f"Type: {'Concentrated Liquidity' if is_clmm else 'Standard AMM'}")

        # 4. Enter interactive mode
        self.placeholder_mode = True
        self.app.hide_input = True

        try:
            # 5. Get trading pair
            pair = await self.app.prompt(
                prompt="Enter trading pair (e.g., ETH-USDC): "
            )
            if self.app.to_stop_config or not pair:
                self.notify("Add liquidity cancelled")
                return

            base_token, quote_token = GatewayCommandUtils.parse_trading_pair(pair)
            if not base_token or not quote_token:
                self.notify("Error: Invalid trading pair format")
                return

            trading_pair = f"{base_token}-{quote_token}"

            # 6. Create LP connector instance and start network
            lp_connector = GatewayLp(
                client_config_map=self.client_config_map,
                connector_name=connector,
                chain=chain,
                network=network,
                address=wallet_address,
                trading_pairs=[trading_pair]
            )
            await lp_connector.start_network()

            # 7. Get and display pool info
            self.notify(f"\nFetching pool information for {trading_pair}...")
            pool_info = await lp_connector.get_pool_info(trading_pair)

            if not pool_info:
                self.notify(f"Error: Could not find pool for {trading_pair}")
                await lp_connector.stop_network()
                return

            # Display pool information
            self._display_pool_info(pool_info, is_clmm)

            # 8. Get position parameters based on type
            position_params = {}

            if is_clmm:
                # For CLMM, get price range
                current_price = pool_info.price

                # Ask for price range method
                range_method = await self.app.prompt(
                    prompt="\nSelect price range method:\n"
                           "1. Percentage from current price (recommended)\n"
                           "2. Custom price range\n"
                           "Enter choice (1 or 2): "
                )

                if range_method == "1":
                    spread_pct = await self.app.prompt(
                        prompt="Enter range width percentage (e.g., 10 for ±10%): "
                    )
                    try:
                        spread_pct = float(spread_pct)
                        position_params['spread_pct'] = spread_pct

                        # Calculate and show price range
                        lower_price = current_price * (1 - spread_pct/100)
                        upper_price = current_price * (1 + spread_pct/100)

                        self.notify(f"\nPrice range:")
                        self.notify(f"  Lower: {lower_price:.6f}")
                        self.notify(f"  Current: {current_price:.6f}")
                        self.notify(f"  Upper: {upper_price:.6f}")

                    except ValueError:
                        self.notify("Error: Invalid percentage")
                        return
                else:
                    # Custom price range
                    lower_price = await self.app.prompt(
                        prompt=f"Enter lower price (current: {current_price:.6f}): "
                    )
                    upper_price = await self.app.prompt(
                        prompt=f"Enter upper price (current: {current_price:.6f}): "
                    )

                    try:
                        lower_price = float(lower_price)
                        upper_price = float(upper_price)

                        if lower_price >= upper_price:
                            self.notify("Error: Lower price must be less than upper price")
                            return

                        if lower_price > current_price or upper_price < current_price:
                            self.notify("Warning: Current price is outside your range!")

                        # Calculate spread percentage for the connector
                        mid_price = (lower_price + upper_price) / 2
                        spread_pct = ((upper_price - lower_price) / (2 * mid_price)) * 100
                        position_params['spread_pct'] = spread_pct

                    except ValueError:
                        self.notify("Error: Invalid price values")
                        return

            # 9. Get token amounts
            self.notify(f"\nEnter token amounts to add (press Enter to skip):")

            base_amount_str = await self.app.prompt(
                prompt=f"Amount of {base_token} (optional): "
            )
            quote_amount_str = await self.app.prompt(
                prompt=f"Amount of {quote_token} (optional): "
            )

            # Parse amounts
            base_amount = None
            quote_amount = None

            if base_amount_str:
                try:
                    base_amount = float(base_amount_str)
                except ValueError:
                    self.notify("Error: Invalid base token amount")
                    return

            if quote_amount_str:
                try:
                    quote_amount = float(quote_amount_str)
                except ValueError:
                    self.notify("Error: Invalid quote token amount")
                    return

            # Validate at least one amount provided
            if base_amount is None and quote_amount is None:
                self.notify("Error: Must provide at least one token amount")
                return

            # 10. Calculate optimal amounts if only one provided
            if is_clmm:
                # For CLMM, calculate based on price range
                if base_amount and not quote_amount:
                    # Calculate quote amount based on range and liquidity distribution
                    quote_amount = self._calculate_clmm_pair_amount(
                        base_amount, pool_info, lower_price, upper_price, True
                    )
                elif quote_amount and not base_amount:
                    base_amount = self._calculate_clmm_pair_amount(
                        quote_amount, pool_info, lower_price, upper_price, False
                    )
            else:
                # For AMM, maintain pool ratio
                pool_ratio = pool_info.base_token_amount / pool_info.quote_token_amount

                if base_amount and not quote_amount:
                    quote_amount = base_amount / pool_ratio
                elif quote_amount and not base_amount:
                    base_amount = quote_amount * pool_ratio

            # Display calculated amounts
            self.notify(f"\nToken amounts to add:")
            self.notify(f"  {base_token}: {base_amount:.6f}")
            self.notify(f"  {quote_token}: {quote_amount:.6f}")

            # 11. Check balances and calculate impact
            tokens_to_check = [base_token, quote_token]
            native_token = lp_connector.native_currency or chain.upper()

            current_balances = await GatewayCommandUtils.get_wallet_balances(
                gateway_client=self._get_gateway_instance(),
                chain=chain,
                network=network,
                wallet_address=wallet_address,
                tokens_to_check=tokens_to_check,
                native_token=native_token
            )

            # 12. Estimate transaction fee
            self.notify(f"\nEstimating transaction fees...")
            fee_info = await GatewayCommandUtils.estimate_transaction_fee(
                self._get_gateway_instance(),
                chain,
                network,
                transaction_type="add_liquidity"
            )

            gas_fee_estimate = fee_info.get("fee_in_native", 0) if fee_info.get("success", False) else 0

            # 13. Calculate balance changes
            balance_changes = {}
            if base_amount:
                balance_changes[base_token] = -base_amount
            if quote_amount:
                balance_changes[quote_token] = -quote_amount

            # 14. Display balance impact
            warnings = []
            GatewayCommandUtils.display_balance_impact_table(
                app=self,
                wallet_address=wallet_address,
                current_balances=current_balances,
                balance_changes=balance_changes,
                native_token=native_token,
                gas_fee=gas_fee_estimate,
                warnings=warnings,
                title="Balance Impact After Adding Liquidity"
            )

            # 15. Display transaction fee details
            GatewayCommandUtils.display_transaction_fee_details(app=self, fee_info=fee_info)

            # 16. Show expected LP tokens or position
            if not is_clmm:
                # For AMM, calculate expected LP tokens
                expected_lp_tokens = self._calculate_expected_lp_tokens(
                    pool_info, base_amount, quote_amount
                )
                self.notify(f"\nExpected LP tokens: ~{expected_lp_tokens:.6f}")
            else:
                # For CLMM, show position details
                self.notify(f"\nPosition will be created with:")
                self.notify(f"  Range: {lower_price:.6f} - {upper_price:.6f}")
                self.notify(f"  Current price: {pool_info.price:.6f}")

            # 17. Display warnings
            if warnings:
                self.notify("\n⚠️  WARNINGS:")
                for warning in warnings:
                    self.notify(f"  • {warning}")

            # 18. Show slippage info
            connector_config = await GatewayCommandUtils.get_connector_config(
                self._get_gateway_instance(), connector
            )
            slippage_pct = connector_config.get("slippagePct", 1.0)
            self.notify(f"\nSlippage tolerance: {slippage_pct}%")

            # 19. Confirmation
            confirm = await self.app.prompt(
                prompt="\nDo you want to add liquidity? (Yes/No) >>> "
            )

            if confirm.lower() not in ["y", "yes"]:
                self.notify("Add liquidity cancelled")
                return

            # 20. Execute transaction
            self.notify("\nAdding liquidity...")

            # Create order ID and execute
            if is_clmm:
                order_id = lp_connector.add_liquidity(
                    trading_pair=trading_pair,
                    price=pool_info.price,
                    spread_pct=position_params['spread_pct'],
                    base_token_amount=base_amount,
                    quote_token_amount=quote_amount,
                    slippage_pct=slippage_pct
                )
            else:
                order_id = lp_connector.add_liquidity(
                    trading_pair=trading_pair,
                    price=pool_info.price,
                    base_token_amount=base_amount,
                    quote_token_amount=quote_amount,
                    slippage_pct=slippage_pct
                )

            self.notify(f"Transaction submitted. Order ID: {order_id}")
            self.notify("Monitoring transaction status...")

            # 21. Monitor transaction
            result = await GatewayCommandUtils.monitor_transaction_with_timeout(
                app=self,
                connector=lp_connector,
                order_id=order_id,
                timeout=120.0,  # 2 minutes for LP transactions
                check_interval=2.0,
                pending_msg_delay=5.0
            )

            if result["completed"] and result["success"]:
                self.notify("\n✓ Liquidity added successfully!")
                self.notify("Use 'gateway lp position-info' to view your position")

            # Stop the connector
            await lp_connector.stop_network()

        finally:
            self.placeholder_mode = False
            self.app.hide_input = False
            self.app.change_prompt(prompt=">>> ")

    except Exception as e:
        self.logger().error(f"Error in add liquidity: {e}", exc_info=True)
        self.notify(f"Error: {str(e)}")
```

### Helper Methods for Add Liquidity

```python
def _display_pool_info(
    self,
    pool_info: Union[AMMPoolInfo, CLMMPoolInfo],
    is_clmm: bool
):
    """Display pool information in a user-friendly format"""
    self.notify("\n=== Pool Information ===")
    self.notify(f"Pool Address: {pool_info.address}")
    self.notify(f"Current Price: {pool_info.price:.6f}")
    self.notify(f"Fee: {pool_info.fee_pct}%")

    if is_clmm and isinstance(pool_info, CLMMPoolInfo):
        self.notify(f"Active Bin ID: {pool_info.active_bin_id}")
        self.notify(f"Bin Step: {pool_info.bin_step}")

    self.notify(f"\nPool Reserves:")
    self.notify(f"  Base: {pool_info.base_token_amount:.6f}")
    self.notify(f"  Quote: {pool_info.quote_token_amount:.6f}")

    # Calculate TVL if prices available
    tvl_estimate = (pool_info.base_token_amount * pool_info.price +
                   pool_info.quote_token_amount)
    self.notify(f"  TVL (in quote): ~{tvl_estimate:.2f}")

def _calculate_clmm_pair_amount(
    self,
    known_amount: float,
    pool_info: CLMMPoolInfo,
    lower_price: float,
    upper_price: float,
    is_base_known: bool
) -> float:
    """
    Calculate the paired token amount for CLMM positions.
    This is a simplified calculation - actual implementation would use
    proper CLMM math based on the protocol.
    """
    current_price = pool_info.price

    if current_price <= lower_price:
        # All quote token
        return known_amount * current_price if is_base_known else 0
    elif current_price >= upper_price:
        # All base token
        return known_amount / current_price if not is_base_known else 0
    else:
        # Calculate based on liquidity distribution in range
        # This is protocol-specific and would need proper implementation
        price_ratio = (current_price - lower_price) / (upper_price - lower_price)

        if is_base_known:
            # Known base, calculate quote
            return known_amount * current_price * (1 - price_ratio)
        else:
            # Known quote, calculate base
            return known_amount / current_price * price_ratio

def _calculate_expected_lp_tokens(
    self,
    pool_info: AMMPoolInfo,
    base_amount: float,
    quote_amount: float
) -> float:
    """
    Estimate expected LP tokens for AMM pools.
    Actual calculation depends on the specific AMM protocol.
    """
    # Simplified calculation - actual would depend on protocol
    pool_value = pool_info.base_token_amount * pool_info.price + pool_info.quote_token_amount
    added_value = base_amount * pool_info.price + quote_amount

    # Assuming proportional LP token distribution
    if pool_value > 0:
        return (added_value / pool_value) * 100  # Placeholder calculation
    else:
        return added_value  # New pool
```

## Remove Liquidity Implementation

### Detailed Flow and Pseudo-code

```python
async def _remove_liquidity(
    self,  # type: HummingbotApplication
    connector: str
):
    """
    Interactive flow for removing liquidity from positions.
    Supports partial removal and complete position closing.
    """
    try:
        # 1. Validate connector and get chain/network info
        if "/" not in connector:
            self.notify(f"Error: Invalid connector format '{connector}'")
            return

        chain, network, error = await GatewayCommandUtils.get_connector_chain_network(
            self._get_gateway_instance(), connector
        )
        if error:
            self.notify(f"Error: {error}")
            return

        # 2. Get wallet address
        wallet_address, error = await GatewayCommandUtils.get_default_wallet(
            self._get_gateway_instance(), chain
        )
        if error:
            self.notify(f"Error: {error}")
            return

        # 3. Determine connector type
        connector_type = get_connector_type(connector)
        is_clmm = connector_type == ConnectorType.CLMM

        self.notify(f"\n=== Remove Liquidity from {connector} ===")
        self.notify(f"Chain: {chain}")
        self.notify(f"Network: {network}")
        self.notify(f"Wallet: {GatewayCommandUtils.format_address_display(wallet_address)}")

        # 4. Create LP connector instance (needed for getting positions)
        # We'll use a dummy trading pair for now, will update later with actual pair
        lp_connector = GatewayLp(
            client_config_map=self.client_config_map,
            connector_name=connector,
            chain=chain,
            network=network,
            address=wallet_address,
            trading_pairs=[]  # Will be populated after we get positions
        )
        await lp_connector.start_network()

        try:
            # 5. Get user's positions using the connector
            self.notify("\nFetching your liquidity positions...")
            positions = await lp_connector.get_user_positions()

        if not positions:
            self.notify("No liquidity positions found for this connector")
            return

        # 5. Display positions
        self._display_positions_table(positions, is_clmm)

        # 6. Enter interactive mode
        self.placeholder_mode = True
        self.app.hide_input = True

        try:
            # 7. Let user select position
            if len(positions) == 1:
                selected_position = positions[0]
                self.notify(f"\nSelected position: {self._format_position_id(selected_position)}")
            else:
                position_num = await self.app.prompt(
                    prompt=f"\nSelect position number (1-{len(positions)}): "
                )

                try:
                    position_idx = int(position_num) - 1
                    if 0 <= position_idx < len(positions):
                        selected_position = positions[position_idx]
                    else:
                        self.notify("Error: Invalid position number")
                        return
                except ValueError:
                    self.notify("Error: Please enter a valid number")
                    return

            # 8. Get removal percentage
            percentage_str = await self.app.prompt(
                prompt="\nPercentage to remove (0-100, default 100): "
            )

            if not percentage_str:
                percentage = 100.0
            else:
                try:
                    percentage = float(percentage_str)
                    if percentage <= 0 or percentage > 100:
                        self.notify("Error: Percentage must be between 0 and 100")
                        return
                except ValueError:
                    self.notify("Error: Invalid percentage")
                    return

            # 9. For 100% removal, ask about closing position
            close_position = False
            if percentage == 100.0 and is_clmm:
                close_prompt = await self.app.prompt(
                    prompt="\nCompletely close this position? (Yes/No): "
                )
                close_position = close_prompt.lower() in ["y", "yes"]

            # 10. Calculate tokens to receive
            base_to_receive, quote_to_receive = self._calculate_removal_amounts(
                selected_position, percentage
            )

            self.notify(f"\nYou will receive:")
            self.notify(f"  {selected_position.base_token}: {base_to_receive:.6f}")
            self.notify(f"  {selected_position.quote_token}: {quote_to_receive:.6f}")

            # Show fees if any
            if hasattr(selected_position, 'base_fee_amount'):
                total_base_fees = selected_position.base_fee_amount
                total_quote_fees = selected_position.quote_fee_amount
                if total_base_fees > 0 or total_quote_fees > 0:
                    self.notify(f"\nUncollected fees:")
                    self.notify(f"  {selected_position.base_token}: {total_base_fees:.6f}")
                    self.notify(f"  {selected_position.quote_token}: {total_quote_fees:.6f}")
                    self.notify("Note: Fees will be automatically collected")

            # 11. Update LP connector with the selected trading pair
            trading_pair = f"{selected_position.base_token}-{selected_position.quote_token}"
            lp_connector._trading_pairs = [trading_pair]
            # Reload token data for the selected pair if needed
            await lp_connector.load_token_data()

            # 12. Check balances and estimate fees
            tokens_to_check = [selected_position.base_token, selected_position.quote_token]
            native_token = lp_connector.native_currency or chain.upper()

            current_balances = await GatewayCommandUtils.get_wallet_balances(
                gateway_client=self._get_gateway_instance(),
                chain=chain,
                network=network,
                wallet_address=wallet_address,
                tokens_to_check=tokens_to_check,
                native_token=native_token
            )

            # 13. Estimate transaction fee
            self.notify(f"\nEstimating transaction fees...")
            tx_type = "close_position" if close_position else "remove_liquidity"
            fee_info = await GatewayCommandUtils.estimate_transaction_fee(
                self._get_gateway_instance(),
                chain,
                network,
                transaction_type=tx_type
            )

            gas_fee_estimate = fee_info.get("fee_in_native", 0) if fee_info.get("success", False) else 0

            # 14. Calculate balance changes (positive for receiving tokens)
            balance_changes = {}
            balance_changes[selected_position.base_token] = base_to_receive
            balance_changes[selected_position.quote_token] = quote_to_receive

            # Add fees to balance changes
            if hasattr(selected_position, 'base_fee_amount'):
                balance_changes[selected_position.base_token] += selected_position.base_fee_amount
                balance_changes[selected_position.quote_token] += selected_position.quote_fee_amount

            # 15. Display balance impact
            warnings = []
            GatewayCommandUtils.display_balance_impact_table(
                app=self,
                wallet_address=wallet_address,
                current_balances=current_balances,
                balance_changes=balance_changes,
                native_token=native_token,
                gas_fee=gas_fee_estimate,
                warnings=warnings,
                title="Balance Impact After Removing Liquidity"
            )

            # 16. Display transaction fee details
            GatewayCommandUtils.display_transaction_fee_details(app=self, fee_info=fee_info)

            # 17. Display warnings
            if warnings:
                self.notify("\n⚠️  WARNINGS:")
                for warning in warnings:
                    self.notify(f"  • {warning}")

            # 18. Confirmation
            action_text = "close position" if close_position else f"remove {percentage}% liquidity"
            confirm = await self.app.prompt(
                prompt=f"\nDo you want to {action_text}? (Yes/No) >>> "
            )

            if confirm.lower() not in ["y", "yes"]:
                self.notify("Remove liquidity cancelled")
                return

            # 20. Execute transaction
            self.notify(f"\n{'Closing position' if close_position else 'Removing liquidity'}...")

            # Create order ID and execute
            position_address = getattr(selected_position, 'address', None) or \
                             getattr(selected_position, 'pool_address', None)

            order_id = lp_connector.remove_liquidity(
                trading_pair=trading_pair,
                position_address=position_address,
                percentage=percentage if not close_position else 100.0
            )

            self.notify(f"Transaction submitted. Order ID: {order_id}")
            self.notify("Monitoring transaction status...")

            # 21. Monitor transaction
            result = await GatewayCommandUtils.monitor_transaction_with_timeout(
                app=self,
                connector=lp_connector,
                order_id=order_id,
                timeout=120.0,
                check_interval=2.0,
                pending_msg_delay=5.0
            )

            if result["completed"] and result["success"]:
                if close_position:
                    self.notify("\n✓ Position closed successfully!")
                else:
                    self.notify(f"\n✓ {percentage}% liquidity removed successfully!")
                    self.notify("Use 'gateway lp position-info' to view remaining position")

        finally:
            self.placeholder_mode = False
            self.app.hide_input = False
            self.app.change_prompt(prompt=">>> ")

            # Always stop the connector
            if lp_connector:
                await lp_connector.stop_network()

    except Exception as e:
        self.logger().error(f"Error in remove liquidity: {e}", exc_info=True)
        self.notify(f"Error: {str(e)}")
```

### Helper Methods for Remove Liquidity

```python
# Note: The get_user_positions method should be added to GatewayLp class:

# In gateway_lp.py, add this method to GatewayLp class:
async def get_user_positions(self) -> List[Union[AMMPositionInfo, CLMMPositionInfo]]:
    """
    Fetch all user positions for this connector and wallet.
    """
    positions = []

    try:
        # Call gateway endpoint to list user positions
        response = await self._get_gateway_instance().get_user_positions(
            connector=self.connector_name,
            network=self.network,
            wallet_address=self.address
        )

        connector_type = get_connector_type(self.connector_name)

        # Parse position data based on connector type
        for pos_data in response.get("positions", []):
            if connector_type == ConnectorType.CLMM:
                position = CLMMPositionInfo(**pos_data)
                # Ensure token symbols are available
                if not hasattr(position, 'base_token_symbol'):
                    # Get token info from addresses if needed
                    base_info = self.get_token_info(position.base_token_address)
                    quote_info = self.get_token_info(position.quote_token_address)
                    position.base_token_symbol = base_info.get('symbol', 'Unknown') if base_info else 'Unknown'
                    position.quote_token_symbol = quote_info.get('symbol', 'Unknown') if quote_info else 'Unknown'
                positions.append(position)
            else:
                position = AMMPositionInfo(**pos_data)
                if not hasattr(position, 'base_token_symbol'):
                    base_info = self.get_token_info(position.base_token_address)
                    quote_info = self.get_token_info(position.quote_token_address)
                    position.base_token_symbol = base_info.get('symbol', 'Unknown') if base_info else 'Unknown'
                    position.quote_token_symbol = quote_info.get('symbol', 'Unknown') if quote_info else 'Unknown'
                positions.append(position)

    except Exception as e:
        self.logger().error(f"Error fetching positions: {e}", exc_info=True)

    return positions

def _display_positions_table(
    self,
    positions: List[Union[AMMPositionInfo, CLMMPositionInfo]],
    is_clmm: bool
):
    """Display user positions in a formatted table"""
    if is_clmm:
        # CLMM positions table
        rows = []
        for i, pos in enumerate(positions):
            rows.append({
                "No": i + 1,
                "ID": self._format_position_id(pos),
                "Pair": f"{pos.base_token_symbol}-{pos.quote_token_symbol}",
                "Range": f"{pos.lower_price:.2f}-{pos.upper_price:.2f}",
                "Value": f"{pos.base_token_amount:.4f} / {pos.quote_token_amount:.4f}",
                "Fees": f"{pos.base_fee_amount:.4f} / {pos.quote_fee_amount:.4f}"
            })

        df = pd.DataFrame(rows)
        self.notify("\nYour Concentrated Liquidity Positions:")
    else:
        # AMM positions table
        rows = []
        for i, pos in enumerate(positions):
            rows.append({
                "No": i + 1,
                "Pool": self._format_position_id(pos),
                "Pair": f"{pos.base_token_symbol}-{pos.quote_token_symbol}",
                "LP Tokens": f"{pos.lp_token_amount:.6f}",
                "Value": f"{pos.base_token_amount:.4f} / {pos.quote_token_amount:.4f}",
                "Price": f"{pos.price:.6f}"
            })

        df = pd.DataFrame(rows)
        self.notify("\nYour Liquidity Positions:")

    lines = ["    " + line for line in df.to_string(index=False).split("\n")]
    self.notify("\n".join(lines))

def _format_position_id(
    self,
    position: Union[AMMPositionInfo, CLMMPositionInfo]
) -> str:
    """Format position identifier for display"""
    if hasattr(position, 'address'):
        # CLMM position with unique address
        return GatewayCommandUtils.format_address_display(position.address)
    else:
        # AMM position identified by pool
        return GatewayCommandUtils.format_address_display(position.pool_address)

def _calculate_removal_amounts(
    self,
    position: Union[AMMPositionInfo, CLMMPositionInfo],
    percentage: float
) -> Tuple[float, float]:
    """Calculate token amounts to receive when removing liquidity"""
    factor = percentage / 100.0

    base_amount = position.base_token_amount * factor
    quote_amount = position.quote_token_amount * factor

    return base_amount, quote_amount
```

## Position Info Implementation

### Detailed Flow and Pseudo-code

```python
async def _position_info(
    self,  # type: HummingbotApplication
    connector: str
):
    """
    Display detailed information about user's liquidity positions.
    Includes summary and detailed views.
    """
    try:
        # 1. Validate connector and get chain/network info
        if "/" not in connector:
            self.notify(f"Error: Invalid connector format '{connector}'")
            return

        chain, network, error = await GatewayCommandUtils.get_connector_chain_network(
            self._get_gateway_instance(), connector
        )
        if error:
            self.notify(f"Error: {error}")
            return

        # 2. Get wallet address
        wallet_address, error = await GatewayCommandUtils.get_default_wallet(
            self._get_gateway_instance(), chain
        )
        if error:
            self.notify(f"Error: {error}")
            return

        # 3. Determine connector type
        connector_type = get_connector_type(connector)
        is_clmm = connector_type == ConnectorType.CLMM

        self.notify(f"\n=== Liquidity Positions on {connector} ===")
        self.notify(f"Chain: {chain}")
        self.notify(f"Network: {network}")
        self.notify(f"Wallet: {GatewayCommandUtils.format_address_display(wallet_address)}")

        # 4. Create LP connector instance to fetch positions
        lp_connector = GatewayLp(
            client_config_map=self.client_config_map,
            connector_name=connector,
            chain=chain,
            network=network,
            address=wallet_address,
            trading_pairs=[]  # Will be populated as needed
        )
        await lp_connector.start_network()

        try:
            # 5. Get user's positions
            self.notify("\nFetching your liquidity positions...")
            positions = await lp_connector.get_user_positions()

        if not positions:
            self.notify("\nNo liquidity positions found for this connector")
            return

        # 5. Display positions summary
        self._display_positions_summary(positions, is_clmm)

        # 6. Enter interactive mode for detailed view
        if len(positions) > 1:
            self.placeholder_mode = True
            self.app.hide_input = True

            try:
                view_details = await self.app.prompt(
                    prompt="\nView detailed position info? (Yes/No): "
                )

                if view_details.lower() in ["y", "yes"]:
                    position_num = await self.app.prompt(
                        prompt=f"Select position number (1-{len(positions)}): "
                    )

                    try:
                        position_idx = int(position_num) - 1
                        if 0 <= position_idx < len(positions):
                            selected_position = positions[position_idx]
                            await self._display_position_details(
                                connector, selected_position, is_clmm
                            )
                        else:
                            self.notify("Error: Invalid position number")
                    except ValueError:
                        self.notify("Error: Please enter a valid number")

            finally:
                self.placeholder_mode = False
                self.app.hide_input = False
                self.app.change_prompt(prompt=">>> ")
        else:
            # Single position - show details directly
            await self._display_position_details(connector, positions[0], is_clmm)

        finally:
            # Always stop the connector
            if lp_connector:
                await lp_connector.stop_network()

    except Exception as e:
        self.logger().error(f"Error in position info: {e}", exc_info=True)
        self.notify(f"Error: {str(e)}")

def _display_positions_summary(
    self,
    positions: List[Union[AMMPositionInfo, CLMMPositionInfo]],
    is_clmm: bool
):
    """Display summary of all positions"""
    total_value_base = 0
    total_value_quote = 0
    total_fees_base = 0
    total_fees_quote = 0

    # Calculate totals
    for pos in positions:
        total_value_base += pos.base_token_amount
        total_value_quote += pos.quote_token_amount

        if hasattr(pos, 'base_fee_amount'):
            total_fees_base += pos.base_fee_amount
            total_fees_quote += pos.quote_fee_amount

    self.notify(f"\nTotal Positions: {len(positions)}")
    self.notify(f"Total Value Locked:")

    # Group by token pair
    positions_by_pair = {}
    for pos in positions:
        pair = f"{pos.base_token_symbol}-{pos.quote_token_symbol}"
        if pair not in positions_by_pair:
            positions_by_pair[pair] = []
        positions_by_pair[pair].append(pos)

    for pair, pair_positions in positions_by_pair.items():
        base_token, quote_token = pair.split("-")
        pair_base_total = sum(p.base_token_amount for p in pair_positions)
        pair_quote_total = sum(p.quote_token_amount for p in pair_positions)

        self.notify(f"  {pair}: {pair_base_total:.6f} {base_token} / "
                   f"{pair_quote_total:.6f} {quote_token}")

    if total_fees_base > 0 or total_fees_quote > 0:
        self.notify(f"\nTotal Uncollected Fees:")
        for pair, pair_positions in positions_by_pair.items():
            if any(hasattr(p, 'base_fee_amount') for p in pair_positions):
                base_token, quote_token = pair.split("-")
                pair_fees_base = sum(getattr(p, 'base_fee_amount', 0) for p in pair_positions)
                pair_fees_quote = sum(getattr(p, 'quote_fee_amount', 0) for p in pair_positions)

                if pair_fees_base > 0 or pair_fees_quote > 0:
                    self.notify(f"  {pair}: {pair_fees_base:.6f} {base_token} / "
                               f"{pair_fees_quote:.6f} {quote_token}")

    # Display positions table
    self._display_positions_table(positions, is_clmm)

async def _display_position_details(
    self,
    connector: str,
    position: Union[AMMPositionInfo, CLMMPositionInfo],
    is_clmm: bool
):
    """Display detailed information for a specific position"""
    self.notify(f"\n=== Position Details ===")

    # Basic info
    self.notify(f"Position ID: {self._format_position_id(position)}")
    self.notify(f"Pool: {position.pool_address}")
    self.notify(f"Pair: {position.base_token_symbol}-{position.quote_token_symbol}")

    # Token amounts
    self.notify(f"\nCurrent Holdings:")
    self.notify(f"  {position.base_token_symbol}: {position.base_token_amount:.6f}")
    self.notify(f"  {position.quote_token_symbol}: {position.quote_token_amount:.6f}")

    # Show token amounts only - no value calculations

    # CLMM specific details
    if is_clmm and isinstance(position, CLMMPositionInfo):
        self.notify(f"\nPrice Range:")
        self.notify(f"  Lower: {position.lower_price:.6f}")
        self.notify(f"  Upper: {position.upper_price:.6f}")
        self.notify(f"  Current: {position.price:.6f}")

        # Check if in range
        if position.lower_price <= position.price <= position.upper_price:
            self.notify(f"  Status: ✓ In Range")
        else:
            if position.price < position.lower_price:
                self.notify(f"  Status: ⚠️  Below Range")
            else:
                self.notify(f"  Status: ⚠️  Above Range")

        # Show fees
        if position.base_fee_amount > 0 or position.quote_fee_amount > 0:
            self.notify(f"\nUncollected Fees:")
            self.notify(f"  {position.base_token_symbol}: {position.base_fee_amount:.6f}")
            self.notify(f"  {position.quote_token_symbol}: {position.quote_fee_amount:.6f}")

    # AMM specific details
    elif isinstance(position, AMMPositionInfo):
        self.notify(f"\nLP Token Balance: {position.lp_token_amount:.6f}")

        # Calculate pool share (would need total supply)
        # This is a placeholder calculation
        self.notify(f"Pool Share: ~{position.lp_token_amount / 1000:.2%}")

    # Current price info
    self.notify(f"\nCurrent Pool Price: {position.price:.6f}")

    # Additional pool info
    try:
        trading_pair = f"{position.base_token_symbol}-{position.quote_token_symbol}"

        # Create temporary connector to fetch pool info
        lp_connector = GatewayLp(
            client_config_map=self.client_config_map,
            connector_name=connector,
            chain=chain,
            network=network,
            address=wallet_address,
            trading_pairs=[trading_pair]
        )
        await lp_connector.start_network()

        pool_info = await lp_connector.get_pool_info(trading_pair)
        if pool_info:
            self.notify(f"\nPool Statistics:")
            self.notify(f"  Total Liquidity: {pool_info.base_token_amount:.2f} / "
                       f"{pool_info.quote_token_amount:.2f}")
            self.notify(f"  Fee Tier: {pool_info.fee_pct}%")

        await lp_connector.stop_network()

    except Exception as e:
        self.logger().debug(f"Could not fetch additional pool info: {e}")
```

## Collect Fees Implementation

### Detailed Flow and Pseudo-code

```python
async def _collect_fees(
    self,  # type: HummingbotApplication
    connector: str
):
    """
    Interactive flow for collecting accumulated fees from positions.
    Only applicable for CLMM positions that track fees separately.
    """
    try:
        # 1. Validate connector and get chain/network info
        if "/" not in connector:
            self.notify(f"Error: Invalid connector format '{connector}'")
            return

        chain, network, error = await GatewayCommandUtils.get_connector_chain_network(
            self._get_gateway_instance(), connector
        )
        if error:
            self.notify(f"Error: {error}")
            return

        # 2. Check if connector supports fee collection
        connector_type = get_connector_type(connector)
        if connector_type != ConnectorType.CLMM:
            self.notify("Fee collection is only available for concentrated liquidity positions")
            return

        # 3. Get wallet address
        wallet_address, error = await GatewayCommandUtils.get_default_wallet(
            self._get_gateway_instance(), chain
        )
        if error:
            self.notify(f"Error: {error}")
            return

        self.notify(f"\n=== Collect Fees from {connector} ===")
        self.notify(f"Chain: {chain}")
        self.notify(f"Network: {network}")
        self.notify(f"Wallet: {GatewayCommandUtils.format_address_display(wallet_address)}")

        # 4. Create LP connector instance to fetch positions
        lp_connector = GatewayLp(
            client_config_map=self.client_config_map,
            connector_name=connector,
            chain=chain,
            network=network,
            address=wallet_address,
            trading_pairs=[]  # Will be populated as needed
        )
        await lp_connector.start_network()

        try:
            # 5. Get positions with fees
            self.notify("\nFetching positions with uncollected fees...")
            all_positions = await lp_connector.get_user_positions()

        # Filter positions with fees > 0
        positions_with_fees = [
            pos for pos in all_positions
            if hasattr(pos, 'base_fee_amount') and
               (pos.base_fee_amount > 0 or pos.quote_fee_amount > 0)
        ]

        if not positions_with_fees:
            self.notify("\nNo uncollected fees found in your positions")
            return

        # 5. Display positions with fees
        self._display_positions_with_fees(positions_with_fees)

        # 6. Calculate total fees
        total_fees = self._calculate_total_fees(positions_with_fees)

        self.notify(f"\nTotal fees to collect:")
        for token, amount in total_fees.items():
            if amount > 0:
                self.notify(f"  {token}: {amount:.6f}")

        # 7. Enter interactive mode
        self.placeholder_mode = True
        self.app.hide_input = True

        try:
            # 8. Ask which positions to collect from
            if len(positions_with_fees) == 1:
                selected_positions = positions_with_fees
                self.notify(f"\nCollecting fees from 1 position")
            else:
                collect_choice = await self.app.prompt(
                    prompt=f"\nCollect fees from:\n"
                           f"1. All positions ({len(positions_with_fees)} positions)\n"
                           f"2. Select specific positions\n"
                           f"Enter choice (1 or 2): "
                )

                if collect_choice == "1":
                    selected_positions = positions_with_fees
                elif collect_choice == "2":
                    # Let user select specific positions
                    position_nums = await self.app.prompt(
                        prompt=f"Enter position numbers to collect from "
                               f"(comma-separated, e.g., 1,3,5): "
                    )

                    try:
                        indices = [int(x.strip()) - 1 for x in position_nums.split(",")]
                        selected_positions = [
                            positions_with_fees[i] for i in indices
                            if 0 <= i < len(positions_with_fees)
                        ]

                        if not selected_positions:
                            self.notify("Error: No valid positions selected")
                            return

                    except (ValueError, IndexError):
                        self.notify("Error: Invalid position selection")
                        return
                else:
                    self.notify("Invalid choice")
                    return

            # 9. Calculate fees to collect from selected positions
            fees_to_collect = self._calculate_total_fees(selected_positions)

            self.notify(f"\nFees to collect from {len(selected_positions)} position(s):")
            for token, amount in fees_to_collect.items():
                if amount > 0:
                    self.notify(f"  {token}: {amount:.6f}")

            # 10. Check gas costs vs fees
            # Get native token for gas estimation
            native_token = lp_connector.native_currency or chain.upper()

            # Update connector with the trading pairs from selected positions
            trading_pairs = list(set(
                f"{pos.base_token_symbol}-{pos.quote_token_symbol}"
                for pos in selected_positions
            ))
            lp_connector._trading_pairs = trading_pairs
            await lp_connector.load_token_data()

            # 11. Estimate transaction fee
            self.notify(f"\nEstimating transaction fees...")
            fee_info = await GatewayCommandUtils.estimate_transaction_fee(
                self._get_gateway_instance(),
                chain,
                network,
                transaction_type="collect_fees"
            )

            gas_fee_estimate = fee_info.get("fee_in_native", 0) if fee_info.get("success", False) else 0

            # 12. Get current balances
            tokens_to_check = list(fees_to_collect.keys())
            if native_token not in tokens_to_check:
                tokens_to_check.append(native_token)

            current_balances = await GatewayCommandUtils.get_wallet_balances(
                gateway_client=self._get_gateway_instance(),
                chain=chain,
                network=network,
                wallet_address=wallet_address,
                tokens_to_check=tokens_to_check,
                native_token=native_token
            )

            # 13. Display balance impact
            warnings = []
            GatewayCommandUtils.display_balance_impact_table(
                app=self,
                wallet_address=wallet_address,
                current_balances=current_balances,
                balance_changes=fees_to_collect,  # Fees are positive (receiving)
                native_token=native_token,
                gas_fee=gas_fee_estimate,
                warnings=warnings,
                title="Balance Impact After Collecting Fees"
            )

            # 14. Display transaction fee details
            GatewayCommandUtils.display_transaction_fee_details(app=self, fee_info=fee_info)

            # 15. Show gas costs
            self.notify(f"\nEstimated gas cost: ~{gas_fee_estimate:.6f} {native_token}")

            # 16. Display warnings
            if warnings:
                self.notify("\n⚠️  WARNINGS:")
                for warning in warnings:
                    self.notify(f"  • {warning}")

            # 17. Confirmation
            confirm = await self.app.prompt(
                prompt="\nDo you want to collect these fees? (Yes/No) >>> "
            )

            if confirm.lower() not in ["y", "yes"]:
                self.notify("Fee collection cancelled")
                return

            # 18. Execute fee collection
            self.notify("\nCollecting fees...")

            # Collect fees for each selected position
            # This would ideally be batched if the protocol supports it
            results = []
            for i, position in enumerate(selected_positions):
                self.notify(f"Collecting from position {i+1}/{len(selected_positions)}...")

                try:
                    # Call gateway to collect fees
                    result = await self._get_gateway_instance().clmm_collect_fees(
                        connector=connector,
                        network=network,
                        wallet_address=wallet_address,
                        position_address=position.address
                    )

                    if result.get("signature"):
                        results.append({
                            'position': position,
                            'tx_hash': result["signature"],
                            'success': True
                        })
                    else:
                        results.append({
                            'position': position,
                            'error': result.get('error', 'Unknown error'),
                            'success': False
                        })

                except Exception as e:
                    results.append({
                        'position': position,
                        'error': str(e),
                        'success': False
                    })

            # 19. Monitor transactions
            successful_txs = [r for r in results if r['success']]

            if successful_txs:
                self.notify(f"\nMonitoring {len(successful_txs)} transaction(s)...")

                # Monitor each transaction
                for result in successful_txs:
                    tx_hash = result['tx_hash']
                    self.notify(f"Transaction: {tx_hash}")

                    # Simple monitoring - in production would track all
                    tx_status = await self._monitor_fee_collection_tx(
                        lp_connector, tx_hash
                    )

                    if tx_status['success']:
                        pos = result['position']
                        self.notify(f"✓ Fees collected from position "
                                   f"{self._format_position_id(pos)}")

            # 20. Summary
            failed_count = len([r for r in results if not r['success']])
            if failed_count > 0:
                self.notify(f"\n⚠️  {failed_count} collection(s) failed")

            if successful_txs:
                self.notify(f"\n✓ Successfully collected fees from "
                           f"{len(successful_txs)} position(s)!")

        finally:
            self.placeholder_mode = False
            self.app.hide_input = False
            self.app.change_prompt(prompt=">>> ")

            # Always stop the connector
            if lp_connector:
                await lp_connector.stop_network()

    except Exception as e:
        self.logger().error(f"Error in collect fees: {e}", exc_info=True)
        self.notify(f"Error: {str(e)}")
```

### Helper Methods for Collect Fees

```python
def _display_positions_with_fees(
    self,
    positions: List[CLMMPositionInfo]
):
    """Display positions that have uncollected fees"""
    rows = []
    for i, pos in enumerate(positions):
        rows.append({
            "No": i + 1,
            "Position": self._format_position_id(pos),
            "Pair": f"{pos.base_token_symbol}-{pos.quote_token_symbol}",
            "Base Fees": f"{pos.base_fee_amount:.6f}",
            "Quote Fees": f"{pos.quote_fee_amount:.6f}"
        })

    df = pd.DataFrame(rows)
    self.notify("\nPositions with Uncollected Fees:")
    lines = ["    " + line for line in df.to_string(index=False).split("\n")]
    self.notify("\n".join(lines))

def _calculate_total_fees(
    self,
    positions: List[CLMMPositionInfo]
) -> Dict[str, float]:
    """Calculate total fees across positions grouped by token"""
    fees_by_token = {}

    for pos in positions:
        base_token = pos.base_token_symbol
        quote_token = pos.quote_token_symbol

        if base_token not in fees_by_token:
            fees_by_token[base_token] = 0
        if quote_token not in fees_by_token:
            fees_by_token[quote_token] = 0

        fees_by_token[base_token] += pos.base_fee_amount
        fees_by_token[quote_token] += pos.quote_fee_amount

    return fees_by_token

async def _monitor_fee_collection_tx(
    self,
    connector: GatewayLp,
    tx_hash: str,
    timeout: float = 60.0
) -> Dict[str, Any]:
    """Monitor a fee collection transaction"""
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            tx_status = await self._get_gateway_instance().get_transaction_status(
                connector.chain,
                connector.network,
                tx_hash
            )

            if tx_status.get("txStatus") == TransactionStatus.CONFIRMED.value:
                return {"success": True, "tx_hash": tx_hash}
            elif tx_status.get("txStatus") == TransactionStatus.FAILED.value:
                return {"success": False, "error": "Transaction failed"}

        except Exception as e:
            self.logger().debug(f"Error checking tx status: {e}")

        await asyncio.sleep(2.0)

    return {"success": False, "error": "Transaction timeout"}
```

## Common Utilities

### Additions to command_utils.py

```python
# In command_utils.py, add these methods to GatewayCommandUtils class:

@staticmethod
def format_pool_info_display(
    pool_info: Union[AMMPoolInfo, CLMMPoolInfo],
    base_symbol: str,
    quote_symbol: str
) -> List[Dict[str, str]]:
    """
    Format pool information for display.

    :param pool_info: Pool information object
    :param base_symbol: Base token symbol
    :param quote_symbol: Quote token symbol
    :return: List of formatted rows
    """
    rows = []

    rows.append({
        "Property": "Pool Address",
        "Value": GatewayCommandUtils.format_address_display(pool_info.address)
    })

    rows.append({
        "Property": "Current Price",
        "Value": f"{pool_info.price:.6f} {quote_symbol}/{base_symbol}"
    })

    rows.append({
        "Property": "Fee Tier",
        "Value": f"{pool_info.fee_pct}%"
    })

    rows.append({
        "Property": "Base Reserves",
        "Value": f"{pool_info.base_token_amount:.6f} {base_symbol}"
    })

    rows.append({
        "Property": "Quote Reserves",
        "Value": f"{pool_info.quote_token_amount:.6f} {quote_symbol}"
    })

    if isinstance(pool_info, CLMMPoolInfo):
        rows.append({
            "Property": "Active Bin",
            "Value": str(pool_info.active_bin_id)
        })
        rows.append({
            "Property": "Bin Step",
            "Value": str(pool_info.bin_step)
        })

    return rows

@staticmethod
def format_position_info_display(
    position: Union[AMMPositionInfo, CLMMPositionInfo]
) -> List[Dict[str, str]]:
    """
    Format position information for display.

    :param position: Position information object
    :return: List of formatted rows
    """
    rows = []

    if hasattr(position, 'address'):
        rows.append({
            "Property": "Position ID",
            "Value": GatewayCommandUtils.format_address_display(position.address)
        })

    rows.append({
        "Property": "Pool",
        "Value": GatewayCommandUtils.format_address_display(position.pool_address)
    })

    rows.append({
        "Property": "Base Amount",
        "Value": f"{position.base_token_amount:.6f}"
    })

    rows.append({
        "Property": "Quote Amount",
        "Value": f"{position.quote_token_amount:.6f}"
    })

    if isinstance(position, CLMMPositionInfo):
        rows.append({
            "Property": "Price Range",
            "Value": f"{position.lower_price:.6f} - {position.upper_price:.6f}"
        })

        if position.base_fee_amount > 0 or position.quote_fee_amount > 0:
            rows.append({
                "Property": "Uncollected Fees",
                "Value": f"{position.base_fee_amount:.6f} / {position.quote_fee_amount:.6f}"
            })

    elif isinstance(position, AMMPositionInfo):
        rows.append({
            "Property": "LP Tokens",
            "Value": f"{position.lp_token_amount:.6f}"
        })

    return rows

@staticmethod
async def estimate_lp_transaction_fee(
    gateway_client: "GatewayHttpClient",
    chain: str,
    network: str,
    transaction_type: str = "add_liquidity"
) -> Dict[str, Any]:
    """
    Estimate transaction fee for LP operations.

    :param gateway_client: Gateway client instance
    :param chain: Chain name
    :param network: Network name
    :param transaction_type: Type of LP transaction
    :return: Fee estimation details
    """
    # LP transactions typically cost more gas than swaps
    gas_multipliers = {
        "add_liquidity": 1.5,      # 50% more than swap
        "remove_liquidity": 1.2,   # 20% more than swap
        "close_position": 1.3,     # 30% more than swap
        "collect_fees": 0.8        # 80% of swap cost
    }

    multiplier = gas_multipliers.get(transaction_type, 1.0)

    # Get base fee estimation
    base_fee_info = await GatewayCommandUtils.estimate_transaction_fee(
        gateway_client, chain, network, "swap"
    )

    if base_fee_info.get("success", False):
        # Adjust units and fee based on transaction type
        base_fee_info["estimated_units"] = int(
            base_fee_info["estimated_units"] * multiplier
        )
        base_fee_info["fee_in_native"] = (
            base_fee_info["fee_in_native"] * multiplier
        )

    return base_fee_info
```

## Error Handling

### Common Error Patterns

```python
class LPCommandError(Exception):
    """Base exception for LP command errors"""
    pass

class InsufficientBalanceError(LPCommandError):
    """Raised when user has insufficient balance for LP operation"""
    pass

class PositionNotFoundError(LPCommandError):
    """Raised when requested position is not found"""
    pass

class PriceOutOfRangeError(LPCommandError):
    """Raised when current price is outside CLMM position range"""
    pass

class InvalidParametersError(LPCommandError):
    """Raised when user provides invalid parameters"""
    pass

# Error handling wrapper
def handle_lp_errors(func):
    """Decorator to handle common LP command errors"""
    async def wrapper(self, *args, **kwargs):
        try:
            return await func(self, *args, **kwargs)
        except InsufficientBalanceError as e:
            self.notify(f"\n❌ Insufficient Balance: {str(e)}")
            self.notify("Please check your token balances and try again.")
        except PositionNotFoundError as e:
            self.notify(f"\n❌ Position Not Found: {str(e)}")
            self.notify("Use 'gateway lp position-info' to see your positions.")
        except PriceOutOfRangeError as e:
            self.notify(f"\n❌ Price Out of Range: {str(e)}")
            self.notify("Consider adjusting your price range or creating a new position.")
        except InvalidParametersError as e:
            self.notify(f"\n❌ Invalid Parameters: {str(e)}")
        except asyncio.CancelledError:
            self.notify("\n⚠️  Operation cancelled")
            raise
        except Exception as e:
            self.logger().error(f"Unexpected error in {func.__name__}: {e}", exc_info=True)
            self.notify(f"\n❌ Unexpected error: {str(e)}")
            self.notify("Please check the logs for more details.")
    return wrapper
```

### Validation Functions

```python
def validate_percentage(percentage: float) -> None:
    """Validate percentage is within valid range"""
    if percentage <= 0 or percentage > 100:
        raise InvalidParametersError(
            f"Percentage must be between 0 and 100, got {percentage}"
        )

def validate_price_range(
    lower_price: float,
    upper_price: float,
    current_price: float
) -> None:
    """Validate CLMM price range parameters"""
    if lower_price >= upper_price:
        raise InvalidParametersError(
            "Lower price must be less than upper price"
        )

    if lower_price <= 0 or upper_price <= 0:
        raise InvalidParametersError(
            "Prices must be positive values"
        )

    # Warning if current price outside range
    if current_price < lower_price or current_price > upper_price:
        # This is allowed but should warn the user
        pass

def validate_token_amounts(
    base_amount: Optional[float],
    quote_amount: Optional[float]
) -> None:
    """Validate token amounts for liquidity provision"""
    if base_amount is None and quote_amount is None:
        raise InvalidParametersError(
            "At least one token amount must be provided"
        )

    if base_amount is not None and base_amount < 0:
        raise InvalidParametersError(
            f"Base token amount must be positive, got {base_amount}"
        )

    if quote_amount is not None and quote_amount < 0:
        raise InvalidParametersError(
            f"Quote token amount must be positive, got {quote_amount}"
        )
```

## Testing Strategy

### Unit Tests

```python
# test_gateway_lp_command.py

import pytest
from decimal import Decimal
from unittest.mock import MagicMock, AsyncMock, patch

from hummingbot.client.command.gateway_lp_command import GatewayLPCommand
from hummingbot.connector.gateway.common_types import ConnectorType
from hummingbot.connector.gateway.gateway_lp import (
    AMMPoolInfo, CLMMPoolInfo, AMMPositionInfo, CLMMPositionInfo
)

class TestGatewayLPCommand:

    @pytest.fixture
    def lp_command(self):
        """Create a GatewayLPCommand instance with mocked dependencies"""
        command = GatewayLPCommand()
        command.notify = MagicMock()
        command.logger = MagicMock()
        command._get_gateway_instance = MagicMock()
        command.client_config_map = MagicMock()
        command.ev_loop = AsyncMock()
        return command

    @pytest.mark.asyncio
    async def test_add_liquidity_amm_success(self, lp_command):
        """Test successful AMM liquidity addition"""
        # Mock gateway responses
        gateway = lp_command._get_gateway_instance.return_value
        gateway.get_connector_chain_network.return_value = {
            "chain": "ethereum",
            "network": "mainnet"
        }

        # Mock pool info
        pool_info = AMMPoolInfo(
            address="0x123...",
            baseTokenAddress="0xabc...",
            quoteTokenAddress="0xdef...",
            price=1500.0,
            feePct=0.3,
            baseTokenAmount=1000.0,
            quoteTokenAmount=1500000.0
        )

        with patch('hummingbot.connector.gateway.gateway_lp.GatewayLp') as MockLP:
            mock_lp = MockLP.return_value
            mock_lp.get_pool_info.return_value = pool_info
            mock_lp.add_liquidity.return_value = "order-123"

            # Test the flow
            await lp_command._add_liquidity("uniswap/amm")

            # Verify correct calls
            assert mock_lp.get_pool_info.called
            assert mock_lp.add_liquidity.called

    @pytest.mark.asyncio
    async def test_remove_liquidity_clmm_partial(self, lp_command):
        """Test partial CLMM liquidity removal"""
        # Mock position
        position = CLMMPositionInfo(
            address="0xpos123...",
            poolAddress="0xpool123...",
            baseTokenAddress="0xabc...",
            quoteTokenAddress="0xdef...",
            baseTokenAmount=10.0,
            quoteTokenAmount=15000.0,
            baseFeeAmount=0.1,
            quoteFeeAmount=150.0,
            lowerBinId=1000,
            upperBinId=2000,
            lowerPrice=1400.0,
            upperPrice=1600.0,
            price=1500.0
        )

        lp_command._get_user_positions = AsyncMock(return_value=[position])

        # Test removal calculation
        base_to_remove, quote_to_remove = lp_command._calculate_removal_amounts(
            position, 50.0  # 50% removal
        )

        assert base_to_remove == 5.0
        assert quote_to_remove == 7500.0

    def test_validate_price_range(self, lp_command):
        """Test price range validation"""
        # Valid range
        lp_command.validate_price_range(1400.0, 1600.0, 1500.0)

        # Invalid range (lower > upper)
        with pytest.raises(InvalidParametersError):
            lp_command.validate_price_range(1600.0, 1400.0, 1500.0)

        # Invalid range (negative price)
        with pytest.raises(InvalidParametersError):
            lp_command.validate_price_range(-100.0, 1600.0, 1500.0)
```

### Integration Tests

```python
# test_gateway_lp_integration.py

@pytest.mark.integration
class TestGatewayLPIntegration:

    @pytest.mark.asyncio
    async def test_full_lp_lifecycle(self, gateway_fixture):
        """Test complete LP lifecycle: add → view → remove"""
        # This would test against a real gateway instance
        # or a comprehensive mock that simulates gateway behavior

        command = GatewayLPCommand()

        # 1. Add liquidity
        order_id = await command._execute_add_liquidity(
            connector="uniswap/amm",
            trading_pair="ETH-USDC",
            base_amount=1.0,
            quote_amount=1500.0
        )

        # 2. Wait for confirmation
        await asyncio.sleep(5)

        # 3. Check position exists
        positions = await command._get_user_positions(
            "uniswap/amm",
            "0xwallet..."
        )
        assert len(positions) > 0

        # 4. Remove liquidity
        await command._execute_remove_liquidity(
            connector="uniswap/amm",
            position=positions[0],
            percentage=100.0
        )
```

### Edge Case Tests

```python
def test_edge_cases():
    """Test various edge cases"""

    # 1. Zero liquidity pool
    # 2. Extreme price ranges
    # 3. Minimum tick spacing
    # 4. Maximum uint256 amounts
    # 5. Slippage protection triggers
    # 6. Gas estimation failures
    # 7. Network disconnections
    # 8. Invalid token addresses
    # 9. Insufficient allowances
    # 10. Position already closed
```

## Implementation Timeline

### Phase 1: Foundation (Week 1)
- [ ] Create gateway_lp_command.py structure
- [ ] Add command routing in gateway_command.py
- [ ] Update parser for LP commands
- [ ] Implement position-info sub-command
- [ ] Add helper methods to command_utils.py

### Phase 2: Add Liquidity (Week 2)
- [ ] Implement add-liquidity for AMM
- [ ] Add balance validation and impact display
- [ ] Implement price range selection for CLMM
- [ ] Add transaction monitoring
- [ ] Create comprehensive error handling

### Phase 3: Remove Liquidity (Week 3)
- [ ] Implement remove-liquidity for both types
- [ ] Add position selection UI
- [ ] Implement partial removal logic
- [ ] Add close-position support
- [ ] Handle fee collection during removal

### Phase 4: Fee Collection (Week 4)
- [ ] Implement collect-fees for CLMM
- [ ] Add batch collection support
- [ ] Implement gas cost analysis
- [ ] Add net profit calculations
- [ ] Complete testing and documentation
