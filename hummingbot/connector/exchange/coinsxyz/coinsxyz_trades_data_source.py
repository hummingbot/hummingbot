"""
Recent Trades Data Source for Coins.xyz Exchange.

This module provides REST API integration for fetching recent trade data
from Coins.xyz exchange with comprehensive trade data parsing.
"""

import asyncio
import logging
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

from hummingbot.connector.exchange.coinsxyz import coinsxyz_constants as CONSTANTS
from hummingbot.connector.exchange.coinsxyz import coinsxyz_web_utils as web_utils
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.logger import HummingbotLogger


class CoinsxyzTradesDataSource:
    """
    Data source for fetching recent trades from Coins.xyz exchange.
    
    Provides comprehensive trade data parsing and conversion to Hummingbot format.
    
    Features:
    - REST API integration for recent trades
    - Trade data parsing and validation
    - Conversion to Hummingbot OrderBookMessage format
    - Batch trade fetching with pagination
    - Trade filtering and sorting capabilities
    """
    
    def __init__(self, 
                 api_factory: WebAssistantsFactory,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN):
        """
        Initialize trades data source.
        
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
    
    async def get_recent_trades(self, 
                              trading_pair: str,
                              limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get recent trades for a trading pair.
        
        Args:
            trading_pair: Trading pair in Hummingbot format (e.g., "BTC-USDT")
            limit: Number of trades to fetch (max 1000)
            
        Returns:
            List of trade dictionaries in Coins.xyz format
        """
        try:
            # Convert trading pair to exchange symbol format
            symbol = web_utils.convert_to_exchange_trading_pair(trading_pair)
            
            # Validate limit
            limit = min(max(1, limit), 1000)  # Clamp between 1 and 1000
            
            # Prepare REST API request
            url = web_utils.public_rest_url(path_url=CONSTANTS.RECENT_TRADES_PATH_URL, domain=self._domain)
            params = {
                "symbol": symbol,
                "limit": limit
            }
            
            # Create REST assistant and make request
            rest_assistant = await self._api_factory.get_rest_assistant()
            response = await rest_assistant.execute_request(
                url=url,
                params=params,
                method=RESTMethod.GET,
                throttler_limit_id=CONSTANTS.RECENT_TRADES_PATH_URL
            )
            
            # Parse response - Coins.xyz returns array directly
            trades_data = response if isinstance(response, list) else response.get("data", [])
            
            self.logger().info(f"Fetched {len(trades_data)} recent trades for {trading_pair}")
            
            return trades_data
            
        except Exception as e:
            self.logger().error(f"Error fetching recent trades for {trading_pair}: {e}")
            return []
    
    async def get_recent_trades_messages(self,
                                       trading_pair: str,
                                       limit: int = 100) -> List[OrderBookMessage]:
        """
        Get recent trades as Hummingbot OrderBookMessage objects.
        
        Args:
            trading_pair: Trading pair in Hummingbot format
            limit: Number of trades to fetch
            
        Returns:
            List of OrderBookMessage objects with trade data
        """
        try:
            # Fetch raw trade data
            trades_data = await self.get_recent_trades(trading_pair, limit)
            
            # Convert to OrderBookMessage format
            trade_messages = []
            for trade_data in trades_data:
                try:
                    trade_msg = self.parse_trade_message(trade_data, trading_pair)
                    if trade_msg:
                        trade_messages.append(trade_msg)
                except Exception as e:
                    self.logger().warning(f"Error parsing trade message: {e}")
                    continue
            
            self.logger().info(f"Converted {len(trade_messages)} trades to OrderBookMessage format")
            
            return trade_messages
            
        except Exception as e:
            self.logger().error(f"Error getting trade messages for {trading_pair}: {e}")
            return []
    
    def parse_trade_message(self, 
                          trade_data: Dict[str, Any], 
                          trading_pair: str) -> Optional[OrderBookMessage]:
        """
        Parse Coins.xyz trade data into Hummingbot OrderBookMessage.
        
        Coins.xyz trade format:
        {
            "price": "110297.380000000000000000",
            "id": 2030645095099490817,
            "qty": "0.000443700000000000",
            "quoteQty": "48.938947506",
            "time": 1756807759116,
            "isBuyerMaker": false,
            "isBestMatch": true
        }
        
        Args:
            trade_data: Raw trade data from Coins.xyz API
            trading_pair: Trading pair in Hummingbot format
            
        Returns:
            OrderBookMessage with trade data or None if parsing fails
        """
        try:
            # Extract trade data
            trade_id = str(trade_data.get("id", ""))
            price = Decimal(str(trade_data.get("price", "0")))
            quantity = Decimal(str(trade_data.get("qty", "0")))
            quote_quantity = Decimal(str(trade_data.get("quoteQty", "0")))
            timestamp = int(trade_data.get("time", 0))
            is_buyer_maker = trade_data.get("isBuyerMaker", False)
            is_best_match = trade_data.get("isBestMatch", True)
            
            # Determine trade type (from taker perspective)
            # If buyer is maker, then taker is seller (sell trade)
            # If buyer is taker, then it's a buy trade
            trade_type = float(TradeType.SELL.value) if is_buyer_maker else float(TradeType.BUY.value)
            
            # Validate required fields
            if not trade_id or price <= 0 or quantity <= 0:
                self.logger().warning(f"Invalid trade data: {trade_data}")
                return None
            
            # Create trade message content
            content = {
                "trading_pair": trading_pair,
                "trade_type": trade_type,
                "price": price,
                "amount": quantity,
                "trade_id": trade_id,
                "trade_time": timestamp,
                "quote_amount": quote_quantity,
                "is_buyer_maker": is_buyer_maker,
                "is_best_match": is_best_match
            }
            
            # Create OrderBookMessage
            trade_message = OrderBookMessage(
                OrderBookMessageType.TRADE,
                content,
                float(timestamp)
            )
            
            return trade_message
            
        except Exception as e:
            self.logger().error(f"Error parsing trade message: {e}")
            return None
    
    async def get_trades_in_time_range(self,
                                     trading_pair: str,
                                     start_time: int,
                                     end_time: int,
                                     limit: int = 1000) -> List[Dict[str, Any]]:
        """
        Get trades within a specific time range.
        
        Note: Coins.xyz API doesn't support time range filtering directly,
        so we fetch recent trades and filter by time.
        
        Args:
            trading_pair: Trading pair in Hummingbot format
            start_time: Start timestamp in milliseconds
            end_time: End timestamp in milliseconds
            limit: Maximum number of trades to fetch
            
        Returns:
            List of trade dictionaries within the time range
        """
        try:
            # Fetch recent trades
            all_trades = await self.get_recent_trades(trading_pair, limit)
            
            # Filter by time range
            filtered_trades = []
            for trade in all_trades:
                trade_time = trade.get("time", 0)
                if start_time <= trade_time <= end_time:
                    filtered_trades.append(trade)
            
            self.logger().info(f"Filtered {len(filtered_trades)} trades from {len(all_trades)} "
                             f"for time range {start_time}-{end_time}")
            
            return filtered_trades
            
        except Exception as e:
            self.logger().error(f"Error getting trades in time range: {e}")
            return []
    
    async def get_trade_statistics(self, 
                                 trading_pair: str,
                                 limit: int = 100) -> Dict[str, Any]:
        """
        Calculate trade statistics from recent trades.
        
        Args:
            trading_pair: Trading pair in Hummingbot format
            limit: Number of recent trades to analyze
            
        Returns:
            Dictionary with trade statistics
        """
        try:
            trades_data = await self.get_recent_trades(trading_pair, limit)
            
            if not trades_data:
                return {}
            
            # Calculate statistics
            prices = [Decimal(str(trade.get("price", "0"))) for trade in trades_data]
            quantities = [Decimal(str(trade.get("qty", "0"))) for trade in trades_data]
            quote_quantities = [Decimal(str(trade.get("quoteQty", "0"))) for trade in trades_data]
            
            buy_trades = [trade for trade in trades_data if not trade.get("isBuyerMaker", False)]
            sell_trades = [trade for trade in trades_data if trade.get("isBuyerMaker", False)]
            
            statistics = {
                "trading_pair": trading_pair,
                "total_trades": len(trades_data),
                "buy_trades": len(buy_trades),
                "sell_trades": len(sell_trades),
                "buy_sell_ratio": len(buy_trades) / len(sell_trades) if sell_trades else float('inf'),
                "min_price": min(prices) if prices else Decimal("0"),
                "max_price": max(prices) if prices else Decimal("0"),
                "avg_price": sum(prices) / len(prices) if prices else Decimal("0"),
                "total_volume": sum(quantities) if quantities else Decimal("0"),
                "total_quote_volume": sum(quote_quantities) if quote_quantities else Decimal("0"),
                "avg_trade_size": sum(quantities) / len(quantities) if quantities else Decimal("0"),
                "price_range": max(prices) - min(prices) if prices else Decimal("0"),
                "timestamp": time.time() * 1000
            }
            
            self.logger().info(f"Calculated trade statistics for {trading_pair}: "
                             f"{statistics['total_trades']} trades, "
                             f"avg price: ${statistics['avg_price']}")
            
            return statistics
            
        except Exception as e:
            self.logger().error(f"Error calculating trade statistics: {e}")
            return {}
    
    def validate_trade_data(self, trade_data: Dict[str, Any]) -> bool:
        """
        Validate trade data format and values.
        
        Args:
            trade_data: Trade data dictionary to validate
            
        Returns:
            True if valid, False otherwise
        """
        try:
            required_fields = ["id", "price", "qty", "time"]
            
            # Check required fields
            for field in required_fields:
                if field not in trade_data:
                    return False
            
            # Validate data types and ranges
            price = Decimal(str(trade_data.get("price", "0")))
            quantity = Decimal(str(trade_data.get("qty", "0")))
            trade_time = int(trade_data.get("time", 0))
            
            if price <= 0 or quantity <= 0 or trade_time <= 0:
                return False
            
            return True
            
        except (ValueError, TypeError, KeyError):
            return False


# Utility functions for trade data processing
def sort_trades_by_time(trades: List[Dict[str, Any]], ascending: bool = True) -> List[Dict[str, Any]]:
    """
    Sort trades by timestamp.
    
    Args:
        trades: List of trade dictionaries
        ascending: Sort in ascending order if True, descending if False
        
    Returns:
        Sorted list of trades
    """
    return sorted(trades, key=lambda x: x.get("time", 0), reverse=not ascending)


def filter_trades_by_type(trades: List[Dict[str, Any]], trade_type: str) -> List[Dict[str, Any]]:
    """
    Filter trades by type (buy/sell).
    
    Args:
        trades: List of trade dictionaries
        trade_type: "buy" or "sell"
        
    Returns:
        Filtered list of trades
    """
    if trade_type.lower() == "buy":
        return [trade for trade in trades if not trade.get("isBuyerMaker", False)]
    elif trade_type.lower() == "sell":
        return [trade for trade in trades if trade.get("isBuyerMaker", False)]
    else:
        return trades


def calculate_vwap(trades: List[Dict[str, Any]]) -> Decimal:
    """
    Calculate Volume Weighted Average Price (VWAP) from trades.
    
    Args:
        trades: List of trade dictionaries
        
    Returns:
        VWAP as Decimal
    """
    try:
        total_volume = Decimal("0")
        total_value = Decimal("0")
        
        for trade in trades:
            price = Decimal(str(trade.get("price", "0")))
            quantity = Decimal(str(trade.get("qty", "0")))
            
            total_volume += quantity
            total_value += price * quantity
        
        return total_value / total_volume if total_volume > 0 else Decimal("0")
        
    except Exception:
        return Decimal("0")
