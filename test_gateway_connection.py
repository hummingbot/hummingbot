#!/usr/bin/env python
"""Test Gateway connection."""

import asyncio
import sys
from pathlib import Path

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.connector.gateway.core import GatewayHttpClient

sys.path.insert(0, str(Path(__file__).parent))


async def test_gateway_connection():
    """Test Gateway connection."""
    # Test with default URL
    print("Testing Gateway connection to http://localhost:15888...")

    client = GatewayHttpClient.get_instance("http://localhost:15888")

    # Test ping
    print("\n1. Testing ping_gateway()...")
    try:
        result = await client.ping_gateway()
        print(f"   Result: {result}")
    except Exception as e:
        print(f"   Error: {e}")

    # Test direct request
    print("\n2. Testing direct request to root endpoint...")
    try:
        result = await client.request("GET", "")
        print(f"   Result: {result}")
    except Exception as e:
        print(f"   Error: {e}")

    # Test get_gateway_status
    print("\n3. Testing get_gateway_status()...")
    try:
        result = await client.get_gateway_status()
        print(f"   Result: {result}")
    except Exception as e:
        print(f"   Error: {e}")

    # Test with ClientConfigMap
    print("\n4. Testing with ClientConfigMap...")
    config = ClientConfigMap()
    config.gateway.gateway_api_host = "localhost"
    config.gateway.gateway_api_port = 15888

    # Simulate what GatewayStatusMonitor does
    gateway_url = f"http://{config.gateway.gateway_api_host}:{config.gateway.gateway_api_port}"
    print(f"   Gateway URL: {gateway_url}")

    client2 = GatewayHttpClient.get_instance(gateway_url)
    try:
        result = await client2.ping_gateway()
        print(f"   Ping result: {result}")
    except Exception as e:
        print(f"   Error: {e}")

    # Close sessions
    await client.close()


if __name__ == "__main__":
    asyncio.run(test_gateway_connection())
