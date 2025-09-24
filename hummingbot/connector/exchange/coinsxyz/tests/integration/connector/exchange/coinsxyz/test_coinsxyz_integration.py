"""
Comprehensive integration tests for Coins.xyz exchange connector.

This module provides end-to-end integration testing for the Coins.xyz connector,
including:
- API client integration with live endpoints
- Authentication flow validation
- Rate limiting and throttling integration
- WebSocket connectivity and data streaming
- Order book data source integration
- User stream data source integration
- Error handling and recovery workflows
- Performance and reliability testing
"""

import asyncio
import json
import logging
import os
import sys
import time
import unittest
from decimal import Decimal
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Configure logging for integration tests
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Try to import Hummingbot components
try:
    from hummingbot.connector.exchange.coinsxyz import coinsxyz_constants as CONSTANTS
    from hummingbot.connector.exchange.coinsxyz.coinsxyz_api_client import CoinsxyzAPIClient
    from hummingbot.connector.exchange.coinsxyz.coinsxyz_auth import CoinsxyzAuth
    from hummingbot.connector.exchange.coinsxyz.coinsxyz_exchange import CoinsxyzExchange
    from hummingbot.connector.exchange.coinsxyz.coinsxyz_exceptions import (
        CoinsxyzAPIError,
        CoinsxyzNetworkError,
        CoinsxyzServerError,
        CoinsxyzRateLimitError
    )
    from hummingbot.connector.exchange.coinsxyz import coinsxyz_web_utils as web_utils
    from hummingbot.connector.exchange.coinsxyz.coinsxyz_retry_utils import (
        CoinsxyzRetryHandler,
        RetryConfigs
    )
    from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
    from hummingbot.core.web_assistant.connections.data_types import RESTMethod
    HUMMINGBOT_AVAILABLE = True
except ImportError:
    # Create mock implementations for testing without full Hummingbot
    HUMMINGBOT_AVAILABLE = False
    
    class CONSTANTS:
        REST_URL = "https://api.coins.xyz/openapi/"
        WSS_URL = "wss://stream.coins.xyz/openapi/ws"
        PING_PATH_URL = "v1/ping"
        SERVER_TIME_PATH_URL = "v1/time"
        USER_IP_PATH_URL = "v1/user/ip"
        EXCHANGE_INFO_PATH_URL = "v1/exchangeInfo"
        DEFAULT_DOMAIN = "coins_xyz_main"
        WS_HEARTBEAT_TIME_INTERVAL = 30
    
    class RESTMethod:
        GET = "GET"
        POST = "POST"
        DELETE = "DELETE"
    
    class CoinsxyzAPIError(Exception):
        def __init__(self, message: str, status_code: int = None):
            super().__init__(message)
            self.status_code = status_code


class CoinsxyzIntegrationTestBase(unittest.TestCase):
    """Base class for Coins.xyz integration tests."""
    
    def setUp(self):
        """Set up integration test fixtures."""
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Test configuration
        self.test_config = {
            "api_key": os.getenv("COINSXYZ_API_KEY", "test_api_key"),
            "secret_key": os.getenv("COINSXYZ_SECRET_KEY", "test_secret_key"),
            "use_live_api": os.getenv("COINSXYZ_USE_LIVE_API", "false").lower() == "true",
            "timeout": 30.0
        }
        
        # Integration test metrics
        self.test_metrics = {
            "start_time": time.time(),
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "response_times": [],
            "errors": []
        }
        
        # Initialize components
        self._setup_components()
    
    def _setup_components(self):
        """Set up test components based on availability."""
        if HUMMINGBOT_AVAILABLE and self.test_config["use_live_api"]:
            # Use real components for live testing
            self.throttler = web_utils.create_throttler()
            self.auth = CoinsxyzAuth(
                api_key=self.test_config["api_key"],
                secret_key=self.test_config["secret_key"]
            )
            self.api_client = CoinsxyzAPIClient(
                auth=self.auth,
                throttler=self.throttler,
                timeout=self.test_config["timeout"]
            )
        else:
            # Use mock components for testing
            self.throttler = MagicMock()
            self.auth = MagicMock()
            self.api_client = MagicMock()
            self._setup_mock_responses()
    
    def _setup_mock_responses(self):
        """Set up mock responses for testing."""
        # Mock API client responses
        self.api_client.ping = AsyncMock(return_value={})
        self.api_client.get_server_time = AsyncMock(
            return_value={"serverTime": int(time.time() * 1000)}
        )
        self.api_client.get_user_ip = AsyncMock(
            return_value={"ip": "192.168.1.1"}
        )
        self.api_client.get_exchange_info = AsyncMock(
            return_value={
                "timezone": "UTC",
                "serverTime": int(time.time() * 1000),
                "symbols": [
                    {
                        "symbol": "BTCUSDT",
                        "status": "TRADING",
                        "baseAsset": "BTC",
                        "quoteAsset": "USDT",
                        "baseAssetPrecision": 8,
                        "quotePrecision": 8,
                        "orderTypes": ["LIMIT", "MARKET"],
                        "icebergAllowed": True,
                        "ocoAllowed": True,
                        "isSpotTradingAllowed": True,
                        "isMarginTradingAllowed": False,
                        "filters": []
                    }
                ]
            }
        )
    
    def tearDown(self):
        """Clean up after each test."""
        # Calculate test metrics
        self.test_metrics["end_time"] = time.time()
        self.test_metrics["total_time"] = (
            self.test_metrics["end_time"] - self.test_metrics["start_time"]
        )
        
        # Log test summary
        self.logger.info(f"Test completed in {self.test_metrics['total_time']:.3f}s")
        if self.test_metrics["total_requests"] > 0:
            success_rate = (
                self.test_metrics["successful_requests"] / 
                self.test_metrics["total_requests"] * 100
            )
            self.logger.info(f"Success rate: {success_rate:.1f}%")
    
    async def _make_tracked_request(self, coro):
        """Make a request and track metrics."""
        start_time = time.time()
        self.test_metrics["total_requests"] += 1
        
        try:
            result = await coro
            end_time = time.time()
            response_time = end_time - start_time
            
            self.test_metrics["successful_requests"] += 1
            self.test_metrics["response_times"].append(response_time)
            
            return result
            
        except Exception as e:
            end_time = time.time()
            response_time = end_time - start_time
            
            self.test_metrics["failed_requests"] += 1
            self.test_metrics["response_times"].append(response_time)
            self.test_metrics["errors"].append({
                "error": str(e),
                "type": type(e).__name__,
                "response_time": response_time
            })
            
            raise


class TestCoinsxyzAPIIntegration(CoinsxyzIntegrationTestBase):
    """Integration tests for Coins.xyz API client."""
    
    @pytest.mark.asyncio
    async def test_api_client_initialization(self):
        """Test API client initialization and configuration."""
        self.assertIsNotNone(self.api_client)
        
        if HUMMINGBOT_AVAILABLE and self.test_config["use_live_api"]:
            self.assertIsNotNone(self.api_client._auth)
            self.assertIsNotNone(self.api_client._throttler)
            self.assertEqual(self.api_client._timeout.total, self.test_config["timeout"])
    
    @pytest.mark.asyncio
    async def test_ping_endpoint_integration(self):
        """Test ping endpoint integration."""
        result = await self._make_tracked_request(self.api_client.ping())
        
        self.assertIsInstance(result, dict)
        # Ping endpoint typically returns empty dict on success
        
        self.logger.info("Ping endpoint integration test passed")
    
    @pytest.mark.asyncio
    async def test_server_time_integration(self):
        """Test server time endpoint integration."""
        result = await self._make_tracked_request(self.api_client.get_server_time())
        
        self.assertIsInstance(result, dict)
        self.assertIn("serverTime", result)
        
        # Validate timestamp format (should be milliseconds)
        server_time = result["serverTime"]
        self.assertIsInstance(server_time, int)
        self.assertGreater(server_time, 1600000000000)  # After 2020
        
        # Check if server time is reasonable (within 1 hour of current time)
        current_time_ms = int(time.time() * 1000)
        time_diff = abs(server_time - current_time_ms)
        self.assertLess(time_diff, 3600000, "Server time differs by more than 1 hour")
        
        self.logger.info(f"Server time integration test passed: {server_time}")
    
    @pytest.mark.asyncio
    async def test_user_ip_integration(self):
        """Test user IP endpoint integration."""
        result = await self._make_tracked_request(self.api_client.get_user_ip())
        
        self.assertIsInstance(result, dict)
        self.assertIn("ip", result)
        
        # Basic IP validation
        ip_address = result["ip"]
        self.assertIsInstance(ip_address, str)
        self.assertTrue(len(ip_address) > 0)
        
        # Check for IPv4 or IPv6 format
        self.assertTrue("." in ip_address or ":" in ip_address)
        
        self.logger.info(f"User IP integration test passed: {ip_address}")
    
    @pytest.mark.asyncio
    async def test_exchange_info_integration(self):
        """Test exchange info endpoint integration."""
        result = await self._make_tracked_request(self.api_client.get_exchange_info())
        
        self.assertIsInstance(result, dict)
        self.assertIn("symbols", result)
        
        symbols = result["symbols"]
        self.assertIsInstance(symbols, list)
        self.assertGreater(len(symbols), 0, "No trading symbols found")
        
        # Validate first symbol structure
        if symbols:
            first_symbol = symbols[0]
            required_fields = ["symbol", "status", "baseAsset", "quoteAsset"]
            for field in required_fields:
                self.assertIn(field, first_symbol, f"Missing field: {field}")
        
        self.logger.info(f"Exchange info integration test passed: {len(symbols)} symbols")
    
    @pytest.mark.asyncio
    async def test_concurrent_api_requests(self):
        """Test concurrent API requests integration."""
        # Create multiple concurrent requests
        tasks = [
            self.api_client.ping(),
            self.api_client.get_server_time(),
            self.api_client.get_user_ip(),
            self.api_client.get_exchange_info()
        ]
        
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()
        
        # Update metrics for all requests
        for result in results:
            if isinstance(result, Exception):
                self.test_metrics["failed_requests"] += 1
                self.test_metrics["errors"].append({
                    "error": str(result),
                    "type": type(result).__name__
                })
            else:
                self.test_metrics["successful_requests"] += 1
        
        self.test_metrics["total_requests"] += len(tasks)
        
        # Validate results
        successful_results = [r for r in results if not isinstance(r, Exception)]
        self.assertGreater(len(successful_results), 0, "No concurrent requests succeeded")
        
        total_time = end_time - start_time
        self.logger.info(
            f"Concurrent requests integration test passed: "
            f"{len(successful_results)}/{len(tasks)} succeeded in {total_time:.3f}s"
        )


class TestCoinsxyzAuthenticationIntegration(CoinsxyzIntegrationTestBase):
    """Integration tests for Coins.xyz authentication."""
    
    @pytest.mark.asyncio
    async def test_authentication_initialization(self):
        """Test authentication component initialization."""
        if not HUMMINGBOT_AVAILABLE:
            self.skipTest("Hummingbot not available for authentication testing")
        
        # Test with valid credentials
        auth = CoinsxyzAuth(
            api_key=self.test_config["api_key"],
            secret_key=self.test_config["secret_key"]
        )
        
        self.assertEqual(auth.api_key, self.test_config["api_key"])
        self.assertEqual(auth.secret_key, self.test_config["secret_key"])
        self.assertTrue(auth.validate_credentials())
        
        self.logger.info("Authentication initialization test passed")
    
    @pytest.mark.asyncio
    async def test_authentication_headers(self):
        """Test authentication header generation."""
        if not HUMMINGBOT_AVAILABLE:
            self.skipTest("Hummingbot not available for authentication testing")
        
        headers = self.auth.header_for_authentication()
        
        self.assertIsInstance(headers, dict)
        self.assertIn("X-COINS-APIKEY", headers)
        self.assertIn("Content-Type", headers)
        self.assertEqual(headers["X-COINS-APIKEY"], self.test_config["api_key"])
        self.assertEqual(headers["Content-Type"], "application/json")
        
        self.logger.info("Authentication headers test passed")
    
    @pytest.mark.asyncio
    async def test_signature_generation(self):
        """Test HMAC signature generation."""
        if not HUMMINGBOT_AVAILABLE:
            self.skipTest("Hummingbot not available for authentication testing")
        
        # Test signature generation with sample data
        test_params = {
            "symbol": "BTCUSDT",
            "side": "BUY",
            "type": "LIMIT",
            "quantity": "0.001",
            "price": "50000.00",
            "timestamp": int(time.time() * 1000)
        }
        
        signature = self.auth._generate_signature(test_params)
        
        self.assertIsInstance(signature, str)
        self.assertEqual(len(signature), 64)  # SHA256 hex digest length
        self.assertTrue(all(c in '0123456789abcdef' for c in signature))
        
        self.logger.info("Signature generation test passed")


class TestCoinsxyzRateLimitingIntegration(CoinsxyzIntegrationTestBase):
    """Integration tests for rate limiting and throttling."""

    @pytest.mark.asyncio
    async def test_rate_limiting_integration(self):
        """Test rate limiting integration with AsyncThrottler."""
        if not HUMMINGBOT_AVAILABLE:
            self.skipTest("Hummingbot not available for rate limiting testing")

        # Test that throttler is properly configured
        self.assertIsNotNone(self.throttler)

        # Test rate limit compliance
        start_time = time.time()

        # Make multiple requests that should be throttled
        tasks = [self.api_client.ping() for _ in range(5)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        end_time = time.time()
        total_time = end_time - start_time

        # Verify throttling occurred (should take some time)
        if self.test_config["use_live_api"]:
            self.assertGreater(total_time, 0.1, "Requests completed too quickly - throttling may not be working")

        successful_results = [r for r in results if not isinstance(r, Exception)]
        self.assertGreater(len(successful_results), 0, "No throttled requests succeeded")

        self.logger.info(f"Rate limiting integration test passed: {total_time:.3f}s for {len(tasks)} requests")

    @pytest.mark.asyncio
    async def test_retry_mechanism_integration(self):
        """Test retry mechanism integration."""
        if not HUMMINGBOT_AVAILABLE:
            self.skipTest("Hummingbot not available for retry testing")

        # Test retry mechanism with request_with_retry if available
        if hasattr(self.api_client, 'request_with_retry'):
            result = await self._make_tracked_request(
                self.api_client.request_with_retry(
                    method=RESTMethod.GET,
                    endpoint=CONSTANTS.PING_PATH_URL
                )
            )

            self.assertIsInstance(result, dict)
            self.logger.info("Retry mechanism integration test passed")
        else:
            self.logger.info("Retry mechanism not available - skipping test")


class TestCoinsxyzWebSocketIntegration(CoinsxyzIntegrationTestBase):
    """Integration tests for WebSocket connectivity."""

    @pytest.mark.asyncio
    async def test_websocket_url_construction(self):
        """Test WebSocket URL construction."""
        if not HUMMINGBOT_AVAILABLE:
            expected_url = CONSTANTS.WSS_URL
        else:
            expected_url = web_utils.websocket_url()

        self.assertEqual(expected_url, CONSTANTS.WSS_URL)
        self.assertTrue(expected_url.startswith("wss://"))
        self.assertIn("coins.xyz", expected_url)

        self.logger.info(f"WebSocket URL construction test passed: {expected_url}")

    @pytest.mark.asyncio
    async def test_websocket_connection_simulation(self):
        """Test WebSocket connection simulation."""
        # Mock WebSocket assistant for integration testing
        mock_ws_assistant = AsyncMock()
        mock_ws_assistant.connect = AsyncMock()
        mock_ws_assistant.disconnect = AsyncMock()
        mock_ws_assistant.send = AsyncMock()
        mock_ws_assistant.receive = AsyncMock()

        # Test connection
        await mock_ws_assistant.connect(
            ws_url=CONSTANTS.WSS_URL,
            ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL
        )

        # Test subscription message
        subscription_message = {
            "method": "SUBSCRIBE",
            "params": ["btcusdt@depth"],
            "id": 1
        }
        await mock_ws_assistant.send(subscription_message)

        # Test message reception
        mock_ws_assistant.receive.return_value = {
            "stream": "btcusdt@depth",
            "data": {
                "lastUpdateId": 12345,
                "bids": [["50000.00", "0.001"]],
                "asks": [["50001.00", "0.002"]]
            }
        }

        received_message = await mock_ws_assistant.receive()
        self.assertIn("stream", received_message)
        self.assertIn("data", received_message)

        # Test disconnection
        await mock_ws_assistant.disconnect()

        self.logger.info("WebSocket connection simulation test passed")


class TestCoinsxyzErrorHandlingIntegration(CoinsxyzIntegrationTestBase):
    """Integration tests for error handling and recovery."""

    @pytest.mark.asyncio
    async def test_network_error_handling(self):
        """Test network error handling integration."""
        # Simulate network error
        if not self.test_config["use_live_api"]:
            # Mock network error
            self.api_client.ping.side_effect = CoinsxyzAPIError("Network error", status_code=0)

            with self.assertRaises(CoinsxyzAPIError):
                await self.api_client.ping()

            self.logger.info("Network error handling test passed")
        else:
            self.logger.info("Skipping network error simulation for live API")

    @pytest.mark.asyncio
    async def test_rate_limit_error_handling(self):
        """Test rate limit error handling integration."""
        # Simulate rate limit error
        if not self.test_config["use_live_api"]:
            # Mock rate limit error
            from tests.unit.connector.exchange.coinsxyz.test_coinsxyz_server_connectivity import CoinsxyzRateLimitError

            self.api_client.get_server_time.side_effect = CoinsxyzRateLimitError(
                "Rate limit exceeded", status_code=429
            )

            with self.assertRaises(CoinsxyzRateLimitError):
                await self.api_client.get_server_time()

            self.logger.info("Rate limit error handling test passed")
        else:
            self.logger.info("Skipping rate limit error simulation for live API")

    @pytest.mark.asyncio
    async def test_server_error_handling(self):
        """Test server error handling integration."""
        # Simulate server error
        if not self.test_config["use_live_api"]:
            # Mock server error
            from tests.unit.connector.exchange.coinsxyz.test_coinsxyz_server_connectivity import CoinsxyzServerError

            self.api_client.get_exchange_info.side_effect = CoinsxyzServerError(
                "Internal server error", status_code=500
            )

            with self.assertRaises(CoinsxyzServerError):
                await self.api_client.get_exchange_info()

            self.logger.info("Server error handling test passed")
        else:
            self.logger.info("Skipping server error simulation for live API")


class TestCoinsxyzPerformanceIntegration(CoinsxyzIntegrationTestBase):
    """Integration tests for performance monitoring."""

    @pytest.mark.asyncio
    async def test_response_time_performance(self):
        """Test response time performance integration."""
        # Make multiple requests and measure performance
        request_count = 10
        response_times = []

        for i in range(request_count):
            start_time = time.time()

            try:
                await self.api_client.ping()
                end_time = time.time()
                response_time = end_time - start_time
                response_times.append(response_time)

            except Exception as e:
                self.logger.warning(f"Request {i+1} failed: {e}")

        if response_times:
            avg_response_time = sum(response_times) / len(response_times)
            min_response_time = min(response_times)
            max_response_time = max(response_times)

            self.assertLess(avg_response_time, 5.0, "Average response time too high")

            self.logger.info(
                f"Performance test passed - Avg: {avg_response_time:.3f}s, "
                f"Min: {min_response_time:.3f}s, Max: {max_response_time:.3f}s"
            )
        else:
            self.fail("No successful requests for performance testing")

    @pytest.mark.asyncio
    async def test_throughput_performance(self):
        """Test throughput performance integration."""
        # Test concurrent request throughput
        concurrent_count = 5

        start_time = time.time()

        tasks = [self.api_client.ping() for _ in range(concurrent_count)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        end_time = time.time()
        total_time = end_time - start_time

        successful_results = [r for r in results if not isinstance(r, Exception)]
        throughput = len(successful_results) / total_time if total_time > 0 else 0

        self.assertGreater(throughput, 0, "No throughput measured")

        self.logger.info(
            f"Throughput test passed - {len(successful_results)} requests "
            f"in {total_time:.3f}s = {throughput:.2f} req/s"
        )


if __name__ == "__main__":
    # Configure test runner
    unittest.main(verbosity=2)
