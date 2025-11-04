# SPDX-License-Identifier: Apache-2.0
"""
EVEDEX Perpetual Futures Connector for Hummingbot.

This connector enables trading perpetual futures contracts on EVEDEX,
a decentralized perpetual futures exchange with off-chain order book
and on-chain settlement.

Key Features:
- Real-time order book updates via WebSocket
- Support for limit and market orders
- Position management with configurable leverage
- Funding rate tracking
- SIWE (Sign-In with Ethereum) authentication

For more information, visit: https://evedex.com
Documentation: https://docs.evedex.com
"""
from .evedex_perpetual_exchange import EvedexPerpetualExchange

__all__ = [
    "EvedexPerpetualExchange",
]

__version__ = "1.0.0"