#!/usr/bin/env python3

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hummingbot.client.config.client_config_map import ClientConfigMap  # noqa: E402
from hummingbot.client.config.config_helpers import ClientConfigAdapter  # noqa: E402
from hummingbot.connector.gateway.core.gateway_http_client import GatewayHttpClient  # noqa: E402


async def test_gateway_connection():
    """Test the gateway connection."""
    try:
        # Create a minimal config
        config_map = ClientConfigMap()
        client_config = ClientConfigAdapter(config_map)

        # Get gateway instance
        gateway = GatewayHttpClient.get_instance(client_config)
        print(f"Gateway URL: {gateway.base_url}")

        # Test ping
        print("\nTesting ping_gateway()...")
        is_online = await gateway.ping_gateway()
        print(f"Gateway is {'ONLINE' if is_online else 'OFFLINE'}")

        # Test direct API request
        print("\nTesting direct API request to /...")
        try:
            response = await gateway.api_request("GET", "")
            print(f"Response: {response}")
        except Exception as e:
            print(f"Error: {e}")

    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_gateway_connection())
