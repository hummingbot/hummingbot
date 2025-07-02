#!/usr/bin/env python
"""Test script to verify Gateway connector can be instantiated."""

import asyncio
import sys
from pathlib import Path

# from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.connector.gateway.core import GatewayConnector

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))


async def test_gateway_connector():
    """Test Gateway connector instantiation."""
    try:
        # Create a minimal client config
        # client_config = ClientConfigMap()

        # Test creating a Gateway connector
        print("Creating Gateway connector for jupiter on mainnet-beta...")
        connector = GatewayConnector(
            connector_name="jupiter",
            network="mainnet-beta",
            wallet_address=None,  # Optional for testing
            trading_required=False
        )

        print("✓ Connector created successfully")
        print(f"  - Connector name: {connector.name}")
        print(f"  - Network: {connector.network}")
        print(f"  - Chain: {connector.chain}")
        print(f"  - Connector name attribute: {connector.connector_name}")

        # Test client initialization
        print("\n✓ Gateway client initialized")
        print(f"  - Base URL: {connector.client.base_url}")

        print("\n✅ All tests passed!")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_gateway_connector())
