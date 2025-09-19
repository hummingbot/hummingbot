"""
Integration test configuration for Coins.xyz connector.

This module provides configuration management for integration tests,
including environment variable handling, test settings, and mock data.
"""

import os
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class IntegrationTestConfig:
    """Configuration class for integration tests."""
    
    # API Configuration
    api_key: str = "test_api_key"
    secret_key: str = "test_secret_key"
    use_live_api: bool = False
    timeout: float = 30.0
    
    # Test Configuration
    max_retries: int = 3
    retry_delay: float = 1.0
    concurrent_requests: int = 5
    performance_test_requests: int = 10
    
    # WebSocket Configuration
    ws_timeout: float = 10.0
    ws_heartbeat_interval: float = 30.0
    
    # Rate Limiting Configuration
    rate_limit_test_requests: int = 5
    rate_limit_window: float = 60.0
    
    # Performance Thresholds
    max_response_time: float = 5.0
    min_throughput: float = 1.0
    max_error_rate: float = 10.0  # 10%


class IntegrationTestConfigManager:
    """Manager for integration test configuration."""
    
    def __init__(self):
        self.config = self._load_config()
    
    def _load_config(self) -> IntegrationTestConfig:
        """Load configuration from environment variables and defaults."""
        return IntegrationTestConfig(
            # API Configuration from environment
            api_key=os.getenv("COINSXYZ_API_KEY", "test_api_key"),
            secret_key=os.getenv("COINSXYZ_SECRET_KEY", "test_secret_key"),
            use_live_api=os.getenv("COINSXYZ_USE_LIVE_API", "false").lower() == "true",
            timeout=float(os.getenv("COINSXYZ_TIMEOUT", "30.0")),
            
            # Test Configuration from environment
            max_retries=int(os.getenv("COINSXYZ_MAX_RETRIES", "3")),
            retry_delay=float(os.getenv("COINSXYZ_RETRY_DELAY", "1.0")),
            concurrent_requests=int(os.getenv("COINSXYZ_CONCURRENT_REQUESTS", "5")),
            performance_test_requests=int(os.getenv("COINSXYZ_PERFORMANCE_REQUESTS", "10")),
            
            # WebSocket Configuration from environment
            ws_timeout=float(os.getenv("COINSXYZ_WS_TIMEOUT", "10.0")),
            ws_heartbeat_interval=float(os.getenv("COINSXYZ_WS_HEARTBEAT", "30.0")),
            
            # Rate Limiting Configuration from environment
            rate_limit_test_requests=int(os.getenv("COINSXYZ_RATE_LIMIT_REQUESTS", "5")),
            rate_limit_window=float(os.getenv("COINSXYZ_RATE_LIMIT_WINDOW", "60.0")),
            
            # Performance Thresholds from environment
            max_response_time=float(os.getenv("COINSXYZ_MAX_RESPONSE_TIME", "5.0")),
            min_throughput=float(os.getenv("COINSXYZ_MIN_THROUGHPUT", "1.0")),
            max_error_rate=float(os.getenv("COINSXYZ_MAX_ERROR_RATE", "10.0"))
        )
    
    def get_config(self) -> IntegrationTestConfig:
        """Get the current configuration."""
        return self.config
    
    def update_config(self, **kwargs) -> None:
        """Update configuration with new values."""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
    
    def validate_config(self) -> bool:
        """Validate the current configuration."""
        try:
            # Validate API configuration
            if not self.config.api_key or len(self.config.api_key) < 8:
                raise ValueError("Invalid API key")
            
            if not self.config.secret_key or len(self.config.secret_key) < 8:
                raise ValueError("Invalid secret key")
            
            if self.config.timeout <= 0:
                raise ValueError("Timeout must be positive")
            
            # Validate test configuration
            if self.config.max_retries < 0:
                raise ValueError("Max retries must be non-negative")
            
            if self.config.retry_delay < 0:
                raise ValueError("Retry delay must be non-negative")
            
            if self.config.concurrent_requests <= 0:
                raise ValueError("Concurrent requests must be positive")
            
            # Validate performance thresholds
            if self.config.max_response_time <= 0:
                raise ValueError("Max response time must be positive")
            
            if self.config.min_throughput <= 0:
                raise ValueError("Min throughput must be positive")
            
            if not (0 <= self.config.max_error_rate <= 100):
                raise ValueError("Max error rate must be between 0 and 100")
            
            return True
            
        except ValueError as e:
            print(f"Configuration validation error: {e}")
            return False
    
    def get_mock_data(self) -> Dict[str, Any]:
        """Get mock data for testing."""
        return {
            "ping_response": {},
            "server_time_response": {
                "serverTime": 1640995200123
            },
            "user_ip_response": {
                "ip": "192.168.1.1"
            },
            "exchange_info_response": {
                "timezone": "UTC",
                "serverTime": 1640995200123,
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
                        "filters": [
                            {
                                "filterType": "PRICE_FILTER",
                                "minPrice": "0.01000000",
                                "maxPrice": "1000000.00000000",
                                "tickSize": "0.01000000"
                            },
                            {
                                "filterType": "LOT_SIZE",
                                "minQty": "0.00001000",
                                "maxQty": "9000.00000000",
                                "stepSize": "0.00001000"
                            }
                        ]
                    },
                    {
                        "symbol": "ETHUSDT",
                        "status": "TRADING",
                        "baseAsset": "ETH",
                        "quoteAsset": "USDT",
                        "baseAssetPrecision": 8,
                        "quotePrecision": 8,
                        "orderTypes": ["LIMIT", "MARKET"],
                        "icebergAllowed": True,
                        "ocoAllowed": True,
                        "isSpotTradingAllowed": True,
                        "isMarginTradingAllowed": False,
                        "filters": [
                            {
                                "filterType": "PRICE_FILTER",
                                "minPrice": "0.01000000",
                                "maxPrice": "100000.00000000",
                                "tickSize": "0.01000000"
                            },
                            {
                                "filterType": "LOT_SIZE",
                                "minQty": "0.00010000",
                                "maxQty": "10000.00000000",
                                "stepSize": "0.00010000"
                            }
                        ]
                    }
                ]
            },
            "websocket_messages": {
                "subscription": {
                    "method": "SUBSCRIBE",
                    "params": ["btcusdt@depth"],
                    "id": 1
                },
                "depth_update": {
                    "stream": "btcusdt@depth",
                    "data": {
                        "lastUpdateId": 12345,
                        "bids": [
                            ["50000.00", "0.001"],
                            ["49999.00", "0.002"],
                            ["49998.00", "0.003"]
                        ],
                        "asks": [
                            ["50001.00", "0.002"],
                            ["50002.00", "0.003"],
                            ["50003.00", "0.001"]
                        ]
                    }
                },
                "trade_update": {
                    "stream": "btcusdt@trade",
                    "data": {
                        "id": 12345,
                        "price": "50000.00",
                        "qty": "0.001",
                        "time": 1640995200123,
                        "isBuyerMaker": True
                    }
                }
            },
            "error_responses": {
                "network_error": {
                    "error": "Network connection failed",
                    "status_code": 0
                },
                "rate_limit_error": {
                    "error": "Rate limit exceeded",
                    "status_code": 429,
                    "retry_after": 60
                },
                "server_error": {
                    "error": "Internal server error",
                    "status_code": 500
                },
                "authentication_error": {
                    "error": "Invalid API key",
                    "status_code": 401
                },
                "client_error": {
                    "error": "Invalid parameter",
                    "status_code": 400
                }
            }
        }
    
    def get_test_credentials(self) -> Dict[str, str]:
        """Get test credentials (masked for security)."""
        return {
            "api_key_masked": f"***{self.config.api_key[-4:]}" if len(self.config.api_key) > 4 else "***",
            "secret_key_masked": f"***{self.config.secret_key[-4:]}" if len(self.config.secret_key) > 4 else "***",
            "use_live_api": str(self.config.use_live_api)
        }
    
    def print_config_summary(self) -> None:
        """Print a summary of the current configuration."""
        print("🔧 Integration Test Configuration Summary")
        print("=" * 50)
        
        credentials = self.get_test_credentials()
        print(f"API Key: {credentials['api_key_masked']}")
        print(f"Secret Key: {credentials['secret_key_masked']}")
        print(f"Use Live API: {credentials['use_live_api']}")
        print(f"Timeout: {self.config.timeout}s")
        
        print(f"\nTest Settings:")
        print(f"Max Retries: {self.config.max_retries}")
        print(f"Retry Delay: {self.config.retry_delay}s")
        print(f"Concurrent Requests: {self.config.concurrent_requests}")
        print(f"Performance Test Requests: {self.config.performance_test_requests}")
        
        print(f"\nWebSocket Settings:")
        print(f"WS Timeout: {self.config.ws_timeout}s")
        print(f"WS Heartbeat Interval: {self.config.ws_heartbeat_interval}s")
        
        print(f"\nPerformance Thresholds:")
        print(f"Max Response Time: {self.config.max_response_time}s")
        print(f"Min Throughput: {self.config.min_throughput} req/s")
        print(f"Max Error Rate: {self.config.max_error_rate}%")


# Global configuration manager instance
config_manager = IntegrationTestConfigManager()

# Convenience functions
def get_config() -> IntegrationTestConfig:
    """Get the global integration test configuration."""
    return config_manager.get_config()

def get_mock_data() -> Dict[str, Any]:
    """Get mock data for testing."""
    return config_manager.get_mock_data()

def validate_config() -> bool:
    """Validate the global configuration."""
    return config_manager.validate_config()

def print_config_summary() -> None:
    """Print configuration summary."""
    config_manager.print_config_summary()
