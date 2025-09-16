"""
Ticker Data Source for Coins.xyz Exchange.

This module provides REST API integration for fetching 24hr ticker statistics
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


class CoinsxyzTickerDataSource:
    """
    Data source for fetching 24hr ticker statistics from Coins.xyz exchange.
    
    Provides comprehensive ticker data parsing and validation.
    
    Features:
    - REST API integration for 24hr ticker statistics
    - Single symbol and all symbols support
    - Price change calculations
    - Volume and trade count statistics
    - Best bid/ask price information
    """
    
    def __init__(self, 
                 api_factory: WebAssistantsFactory,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN):
        """
        Initialize ticker data source.
        
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
    
    async def get_24hr_ticker(self, trading_pair: Optional[str] = None) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Get 24hr ticker statistics.
        
        Args:
            trading_pair: Trading pair in Hummingbot format (e.g., "BTC-USDT")
                         If None, returns all symbols
            
        Returns:
            Single ticker dict if trading_pair specified, list of tickers if None
            
        Ticker format:
        {
            "symbol": "BTCUSDT",
            "priceChange": "-94.99999800",
            "priceChangePercent": "-95.960",
            "weightedAvgPrice": "0.29628482",
            "prevClosePrice": "0.10002000",
            "lastPrice": "4.00000200",
            "lastQty": "200.00000000",
            "bidPrice": "4.00000000",
            "bidQty": "100.00000000",
            "askPrice": "4.00000200",
            "askQty": "100.00000000",
            "openPrice": "99.00000000",
            "highPrice": "100.00000000",
            "lowPrice": "0.10000000",
            "volume": "8913.30000000",
            "quoteVolume": "15.30000000",
            "openTime": 1499783499040,
            "closeTime": 1499869899040,
            "firstId": 28385,
            "lastId": 28460,
            "count": 76
        }
        """
        try:
            # Prepare REST API request
            url = web_utils.public_rest_url(path_url=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL, domain=self._domain)
            params = {}
            
            # Add symbol if specified
            if trading_pair:
                symbol = utils.convert_to_exchange_trading_pair(trading_pair)
                params["symbol"] = symbol
            
            # Create REST assistant and make request
            rest_assistant = await self._api_factory.get_rest_assistant()
            response = await rest_assistant.execute_request(
                url=url,
                params=params,
                method=RESTMethod.GET,
                throttler_limit_id=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL
            )
            
            # Parse response
            if trading_pair:
                # Single symbol response
                ticker_data = response if isinstance(response, dict) else response.get("data", {})
                validated_ticker = self._validate_and_convert_ticker(ticker_data, trading_pair)
                self.logger().info(f"Fetched 24hr ticker for {trading_pair}")
                return validated_ticker or {}
            else:
                # All symbols response
                tickers_data = response if isinstance(response, list) else response.get("data", [])
                validated_tickers = []
                
                for ticker in tickers_data:
                    try:
                        # Convert symbol back to trading pair format
                        symbol = ticker.get("symbol", "")
                        if symbol:
                            # This is a simplified conversion - in practice you'd need proper mapping
                            trading_pair_name = utils.convert_from_exchange_trading_pair(
                                symbol, 
                                symbol[:-4] if len(symbol) > 4 else symbol[:3],  # Base asset
                                symbol[-4:] if len(symbol) > 4 else symbol[3:]   # Quote asset
                            )
                            validated_ticker = self._validate_and_convert_ticker(ticker, trading_pair_name)
                            if validated_ticker:
                                validated_tickers.append(validated_ticker)
                    except Exception as e:
                        self.logger().warning(f"Error processing ticker for symbol {ticker.get('symbol', 'unknown')}: {e}")
                        continue
                
                self.logger().info(f"Fetched 24hr tickers for {len(validated_tickers)} symbols")
                return validated_tickers
            
        except Exception as e:
            self.logger().error(f"Error fetching 24hr ticker: {e}")
            return {} if trading_pair else []
    
    def _validate_and_convert_ticker(self, ticker_data: Dict[str, Any], trading_pair: str) -> Optional[Dict[str, Any]]:
        """
        Validate and convert ticker data to standard format.
        
        Args:
            ticker_data: Raw ticker data from exchange
            trading_pair: Trading pair in Hummingbot format
            
        Returns:
            Validated ticker data or None if invalid
        """
        try:
            if not isinstance(ticker_data, dict):
                return None
            
            # Extract and validate required fields
            symbol = ticker_data.get("symbol", "")
            last_price = ticker_data.get("lastPrice", "0")
            
            if not symbol or float(last_price) <= 0:
                return None
            
            # Convert to standard format
            validated_ticker = {
                "symbol": symbol,
                "trading_pair": trading_pair,
                "last_price": str(last_price),
                "price_change": str(ticker_data.get("priceChange", "0")),
                "price_change_percent": str(ticker_data.get("priceChangePercent", "0")),
                "weighted_avg_price": str(ticker_data.get("weightedAvgPrice", "0")),
                "prev_close_price": str(ticker_data.get("prevClosePrice", "0")),
                "last_qty": str(ticker_data.get("lastQty", "0")),
                "bid_price": str(ticker_data.get("bidPrice", "0")),
                "bid_qty": str(ticker_data.get("bidQty", "0")),
                "ask_price": str(ticker_data.get("askPrice", "0")),
                "ask_qty": str(ticker_data.get("askQty", "0")),
                "open_price": str(ticker_data.get("openPrice", "0")),
                "high_price": str(ticker_data.get("highPrice", "0")),
                "low_price": str(ticker_data.get("lowPrice", "0")),
                "volume": str(ticker_data.get("volume", "0")),
                "quote_volume": str(ticker_data.get("quoteVolume", "0")),
                "open_time": int(ticker_data.get("openTime", 0)),
                "close_time": int(ticker_data.get("closeTime", 0)),
                "first_id": int(ticker_data.get("firstId", 0)),
                "last_id": int(ticker_data.get("lastId", 0)),
                "count": int(ticker_data.get("count", 0))
            }
            
            return validated_ticker
            
        except (ValueError, TypeError) as e:
            self.logger().warning(f"Error validating ticker data: {e}")
            return None
    
    async def get_best_bid_ask(self, trading_pair: str) -> Optional[Dict[str, Any]]:
        """
        Get best bid and ask prices for a trading pair.
        
        Args:
            trading_pair: Trading pair in Hummingbot format
            
        Returns:
            Dict with best bid/ask data or None if not available
            
        Format:
        {
            "symbol": "BTCUSDT",
            "bidPrice": "4.00000000",
            "bidQty": "431.00000000",
            "askPrice": "4.00000200",
            "askQty": "9.00000000"
        }
        """
        try:
            # Convert trading pair to exchange symbol format
            symbol = utils.convert_to_exchange_trading_pair(trading_pair)
            
            # Prepare REST API request
            url = web_utils.public_rest_url(path_url=CONSTANTS.TICKER_BOOK_PATH_URL, domain=self._domain)
            params = {"symbol": symbol}
            
            # Create REST assistant and make request
            rest_assistant = await self._api_factory.get_rest_assistant()
            response = await rest_assistant.execute_request(
                url=url,
                params=params,
                method=RESTMethod.GET,
                throttler_limit_id=CONSTANTS.TICKER_BOOK_PATH_URL
            )
            
            # Parse response
            book_ticker = response if isinstance(response, dict) else response.get("data", {})
            
            if not book_ticker:
                return None
            
            # Validate and convert
            validated_book_ticker = {
                "symbol": book_ticker.get("symbol", symbol),
                "trading_pair": trading_pair,
                "bid_price": str(book_ticker.get("bidPrice", "0")),
                "bid_qty": str(book_ticker.get("bidQty", "0")),
                "ask_price": str(book_ticker.get("askPrice", "0")),
                "ask_qty": str(book_ticker.get("askQty", "0")),
                "timestamp": int(time.time() * 1000)
            }
            
            self.logger().info(f"Fetched best bid/ask for {trading_pair}")
            return validated_book_ticker
            
        except Exception as e:
            self.logger().error(f"Error fetching best bid/ask for {trading_pair}: {e}")
            return None
    
    async def get_price_ticker(self, trading_pair: Optional[str] = None) -> Union[Dict[str, str], List[Dict[str, str]]]:
        """
        Get latest price for symbol(s).
        
        Args:
            trading_pair: Trading pair in Hummingbot format (optional)
            
        Returns:
            Price ticker data
            
        Format:
        {
            "symbol": "LTCBTC",
            "price": "4.00000200"
        }
        """
        try:
            # Prepare REST API request
            url = web_utils.public_rest_url(path_url=CONSTANTS.PRICES_PATH_URL, domain=self._domain)
            params = {}
            
            # Add symbol if specified
            if trading_pair:
                symbol = utils.convert_to_exchange_trading_pair(trading_pair)
                params["symbol"] = symbol
            
            # Create REST assistant and make request
            rest_assistant = await self._api_factory.get_rest_assistant()
            response = await rest_assistant.execute_request(
                url=url,
                params=params,
                method=RESTMethod.GET,
                throttler_limit_id=CONSTANTS.PRICES_PATH_URL
            )
            
            # Parse response
            if trading_pair:
                # Single symbol response
                price_data = response if isinstance(response, dict) else response.get("data", {})
                return {
                    "symbol": price_data.get("symbol", ""),
                    "trading_pair": trading_pair,
                    "price": str(price_data.get("price", "0"))
                }
            else:
                # All symbols response
                prices_data = response if isinstance(response, list) else response.get("data", [])
                return [
                    {
                        "symbol": price.get("symbol", ""),
                        "price": str(price.get("price", "0"))
                    }
                    for price in prices_data
                    if isinstance(price, dict) and price.get("symbol")
                ]
            
        except Exception as e:
            self.logger().error(f"Error fetching price ticker: {e}")
            return {} if trading_pair else []
    
    async def get_ticker_statistics(self, trading_pair: str) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive ticker statistics for a trading pair.
        
        Args:
            trading_pair: Trading pair in Hummingbot format
            
        Returns:
            Comprehensive ticker statistics
        """
        try:
            # Get 24hr ticker and best bid/ask
            ticker_24hr = await self.get_24hr_ticker(trading_pair)
            best_bid_ask = await self.get_best_bid_ask(trading_pair)
            
            if not ticker_24hr:
                return None
            
            # Combine data
            statistics = {
                **ticker_24hr,
                "spread": "0",
                "spread_percent": "0"
            }
            
            # Calculate spread if bid/ask available
            if best_bid_ask:
                try:
                    bid_price = Decimal(best_bid_ask["bid_price"])
                    ask_price = Decimal(best_bid_ask["ask_price"])
                    
                    if bid_price > 0 and ask_price > 0:
                        spread = ask_price - bid_price
                        spread_percent = (spread / ask_price) * 100
                        
                        statistics["spread"] = str(spread)
                        statistics["spread_percent"] = str(spread_percent)
                        
                        # Update bid/ask from book ticker (more recent)
                        statistics["bid_price"] = best_bid_ask["bid_price"]
                        statistics["bid_qty"] = best_bid_ask["bid_qty"]
                        statistics["ask_price"] = best_bid_ask["ask_price"]
                        statistics["ask_qty"] = best_bid_ask["ask_qty"]
                        
                except Exception as e:
                    self.logger().warning(f"Error calculating spread: {e}")
            
            return statistics
            
        except Exception as e:
            self.logger().error(f"Error fetching ticker statistics for {trading_pair}: {e}")
            return None
