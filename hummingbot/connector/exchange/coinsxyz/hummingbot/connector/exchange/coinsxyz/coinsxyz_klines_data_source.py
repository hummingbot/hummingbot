"""
Klines/Candlestick Data Source for Coins.xyz Exchange.

This module provides REST API integration for fetching klines/candlestick data
from Coins.xyz exchange with comprehensive data parsing and validation.
"""

import asyncio
import logging
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

from hummingbot.connector.exchange.coinsxyz import coinsxyz_constants as CONSTANTS
from hummingbot.connector.exchange.coinsxyz import coinsxyz_utils as utils
from hummingbot.connector.exchange.coinsxyz import coinsxyz_web_utils as web_utils
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.logger import HummingbotLogger


class CoinsxyzKlinesDataSource:
    """
    Data source for fetching klines/candlestick data from Coins.xyz exchange.
    
    Provides comprehensive klines data parsing and conversion to standard format.
    
    Features:
    - REST API integration for klines data
    - Multiple timeframe support
    - Data validation and parsing
    - Historical data fetching with pagination
    - Real-time klines data support
    """
    
    # Supported intervals mapping (Hummingbot -> Coins.xyz)
    INTERVALS = {
        "1m": "1m",
        "3m": "3m", 
        "5m": "5m",
        "15m": "15m",
        "30m": "30m",
        "1h": "1h",
        "2h": "2h",
        "4h": "4h",
        "6h": "6h",
        "8h": "8h",
        "12h": "12h",
        "1d": "1d",
        "3d": "3d",
        "1w": "1w",
        "1M": "1M"
    }
    
    def __init__(self, 
                 api_factory: WebAssistantsFactory,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN):
        """
        Initialize klines data source.
        
        Args:
            api_factory: Web assistants factory for API requests
            domain: API domain (default or testnet)
        """
        self._api_factory = api_factory
        self._domain = domain
        self._logger = None
    
    def logger(self) -> HummingbotLogger:
        """Get logger instance."""
        if self._logger is None:
            self._logger = logging.getLogger(__name__)
        return self._logger
    
    async def get_klines(self, 
                        trading_pair: str,
                        interval: str = "1h",
                        limit: int = 500,
                        start_time: Optional[int] = None,
                        end_time: Optional[int] = None) -> List[List[Union[int, str]]]:
        """
        Get klines/candlestick data for a trading pair.
        
        Args:
            trading_pair: Trading pair in Hummingbot format (e.g., "BTC-USDT")
            interval: Kline interval (1m, 5m, 1h, 1d, etc.)
            limit: Number of klines to fetch (max 1000)
            start_time: Start time in milliseconds (optional)
            end_time: End time in milliseconds (optional)
            
        Returns:
            List of klines data in format:
            [
                [
                    open_time,      # 0: Open time (timestamp)
                    open_price,     # 1: Open price
                    high_price,     # 2: High price
                    low_price,      # 3: Low price
                    close_price,    # 4: Close price
                    volume,         # 5: Volume
                    close_time,     # 6: Close time (timestamp)
                    quote_volume,   # 7: Quote asset volume
                    trade_count,    # 8: Number of trades
                    taker_buy_base_volume,  # 9: Taker buy base asset volume
                    taker_buy_quote_volume, # 10: Taker buy quote asset volume
                    ignore          # 11: Unused field
                ]
            ]
        """
        try:
            # Convert trading pair to exchange symbol format
            symbol = utils.convert_to_exchange_trading_pair(trading_pair)
            
            # Validate interval
            if interval not in self.INTERVALS:
                raise ValueError(f"Unsupported interval: {interval}. Supported: {list(self.INTERVALS.keys())}")
            
            exchange_interval = self.INTERVALS[interval]
            
            # Validate limit
            limit = min(max(1, limit), 1000)  # Clamp between 1 and 1000
            
            # Prepare REST API request
            url = web_utils.public_rest_url(path_url=CONSTANTS.KLINES_PATH_URL, domain=self._domain)
            params = {
                "symbol": symbol,
                "interval": exchange_interval,
                "limit": limit
            }
            
            # Add time range if specified
            if start_time is not None:
                params["startTime"] = int(start_time)
            if end_time is not None:
                params["endTime"] = int(end_time)
            
            # Create REST assistant and make request
            rest_assistant = await self._api_factory.get_rest_assistant()
            response = await rest_assistant.execute_request(
                url=url,
                params=params,
                method=RESTMethod.GET,
                throttler_limit_id=CONSTANTS.KLINES_PATH_URL
            )
            
            # Parse response - Coins.xyz returns array directly
            klines_data = response if isinstance(response, list) else response.get("data", [])
            
            # Validate and convert data
            validated_klines = []
            for kline in klines_data:
                try:
                    validated_kline = self._validate_and_convert_kline(kline)
                    if validated_kline:
                        validated_klines.append(validated_kline)
                except Exception as e:
                    self.logger().warning(f"Error validating kline data: {e}")
                    continue
            
            self.logger().info(f"Fetched {len(validated_klines)} klines for {trading_pair} ({interval})")
            
            return validated_klines
            
        except Exception as e:
            self.logger().error(f"Error fetching klines for {trading_pair}: {e}")
            return []
    
    def _validate_and_convert_kline(self, kline_data: List[Any]) -> Optional[List[Union[int, str]]]:
        """
        Validate and convert kline data to standard format.
        
        Args:
            kline_data: Raw kline data from exchange
            
        Returns:
            Validated kline data or None if invalid
        """
        try:
            if not isinstance(kline_data, list) or len(kline_data) < 6:
                return None
            
            # Validate timestamp first
            timestamp = int(kline_data[0])
            if timestamp <= 0:
                return None

            # Convert to standard format
            # Coins.xyz format: [timestamp, open, high, low, close, volume, ...]
            validated_kline = [
                timestamp,               # 0: Open time
                str(kline_data[1]),      # 1: Open price
                str(kline_data[2]),      # 2: High price
                str(kline_data[3]),      # 3: Low price
                str(kline_data[4]),      # 4: Close price
                str(kline_data[5]),      # 5: Volume
                timestamp + self._get_interval_ms("1h"),  # 6: Close time (estimated)
                str(kline_data[6]) if len(kline_data) > 6 else "0",  # 7: Quote volume
                int(kline_data[7]) if len(kline_data) > 7 else 0,    # 8: Trade count
                str(kline_data[8]) if len(kline_data) > 8 else "0",  # 9: Taker buy base volume
                str(kline_data[9]) if len(kline_data) > 9 else "0",  # 10: Taker buy quote volume
                "0"  # 11: Unused field
            ]

            # Validate prices are positive
            for i in [1, 2, 3, 4]:  # open, high, low, close
                if float(validated_kline[i]) <= 0:
                    return None

            # Validate volume is non-negative
            if float(validated_kline[5]) < 0:
                return None
            
            return validated_kline
            
        except (ValueError, IndexError, TypeError) as e:
            self.logger().warning(f"Error validating kline data: {e}")
            return None
    
    def _get_interval_ms(self, interval: str) -> int:
        """Get interval duration in milliseconds."""
        interval_ms = {
            "1m": 60 * 1000,
            "3m": 3 * 60 * 1000,
            "5m": 5 * 60 * 1000,
            "15m": 15 * 60 * 1000,
            "30m": 30 * 60 * 1000,
            "1h": 60 * 60 * 1000,
            "2h": 2 * 60 * 60 * 1000,
            "4h": 4 * 60 * 60 * 1000,
            "6h": 6 * 60 * 60 * 1000,
            "8h": 8 * 60 * 60 * 1000,
            "12h": 12 * 60 * 60 * 1000,
            "1d": 24 * 60 * 60 * 1000,
            "3d": 3 * 24 * 60 * 60 * 1000,
            "1w": 7 * 24 * 60 * 60 * 1000,
            "1M": 30 * 24 * 60 * 60 * 1000  # Approximate
        }
        return interval_ms.get(interval, 60 * 60 * 1000)  # Default to 1h
    
    async def get_latest_kline(self, 
                              trading_pair: str,
                              interval: str = "1h") -> Optional[List[Union[int, str]]]:
        """
        Get the latest kline for a trading pair.
        
        Args:
            trading_pair: Trading pair in Hummingbot format
            interval: Kline interval
            
        Returns:
            Latest kline data or None if not available
        """
        try:
            klines = await self.get_klines(trading_pair, interval, limit=1)
            return klines[0] if klines else None
        except Exception as e:
            self.logger().error(f"Error fetching latest kline for {trading_pair}: {e}")
            return None
    
    async def get_historical_klines(self,
                                   trading_pair: str,
                                   interval: str,
                                   start_time: int,
                                   end_time: Optional[int] = None,
                                   limit: int = 1000) -> List[List[Union[int, str]]]:
        """
        Get historical klines data with time range.
        
        Args:
            trading_pair: Trading pair in Hummingbot format
            interval: Kline interval
            start_time: Start time in milliseconds
            end_time: End time in milliseconds (optional, defaults to now)
            limit: Maximum number of klines to fetch
            
        Returns:
            List of historical klines data
        """
        if end_time is None:
            end_time = int(time.time() * 1000)
        
        return await self.get_klines(
            trading_pair=trading_pair,
            interval=interval,
            limit=limit,
            start_time=start_time,
            end_time=end_time
        )
    
    def get_supported_intervals(self) -> List[str]:
        """Get list of supported kline intervals."""
        return list(self.INTERVALS.keys())
    
    def is_interval_supported(self, interval: str) -> bool:
        """Check if interval is supported."""
        return interval in self.INTERVALS
