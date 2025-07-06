#!/usr/bin/env python
"""Test Gateway monitor functionality."""

import asyncio
import sys
from pathlib import Path

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.connector.gateway.core import GatewayMonitor

sys.path.insert(0, str(Path(__file__).parent))


async def test_gateway_monitor():
    """Test Gateway monitor."""
    print("Testing Gateway Monitor...")

    # Create a mock app with client config
    class MockApp:
        def __init__(self):
            self.client_config_map = ClientConfigMap()
            self.client_config_map.gateway.gateway_api_host = "localhost"
            self.client_config_map.gateway.gateway_api_port = 15888

    app = MockApp()

    # Create and start monitor
    monitor = GatewayMonitor(app, check_interval=2.0)  # Fast interval for testing

    print(f"Initial status: {monitor.gateway_status}")
    print(f"Initial is_available: {monitor.is_available}")

    # Start monitoring
    await monitor.start()

    # Wait a bit for the first check
    print("\nWaiting for first check...")
    await asyncio.sleep(3)

    print(f"Status after check: {monitor.gateway_status}")
    print(f"Is available: {monitor.is_available}")
    print(f"Ready event set: {monitor.ready_event.is_set()}")
    print(f"Config keys: {len(monitor.gateway_config_keys)} keys")

    # Test direct check
    print("\nTesting direct check_once()...")
    result = await monitor.check_once()
    print(f"Direct check result: {result}")

    # Stop monitor
    await monitor.stop()

    # Close client session
    if monitor.client:
        await monitor.client.close()


if __name__ == "__main__":
    asyncio.run(test_gateway_monitor())
