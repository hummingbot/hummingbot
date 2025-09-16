"""
Utility functions for Hummingbot connectors.
Minimal implementation to support connector development.
"""

import asyncio
import time
from decimal import Decimal
from typing import Dict, List, Optional, Any, Union
from urllib.parse import urljoin


def combine_to_hb_trading_pair(base: str, quote: str) -> str:
    """
    Combine base and quote assets to create a Hummingbot trading pair.
    
    Args:
        base: Base asset symbol
        quote: Quote asset symbol
        
    Returns:
        Trading pair in Hummingbot format (BASE-QUOTE)
    """
    return f"{base.upper()}-{quote.upper()}"


def split_hb_trading_pair(trading_pair: str) -> tuple:
    """
    Split a Hummingbot trading pair into base and quote assets.
    
    Args:
        trading_pair: Trading pair in Hummingbot format (BASE-QUOTE)
        
    Returns:
        Tuple of (base, quote) asset symbols
    """
    parts = trading_pair.split("-")
    if len(parts) != 2:
        raise ValueError(f"Invalid trading pair format: {trading_pair}")
    return parts[0], parts[1]


def convert_to_exchange_trading_pair(hb_trading_pair: str, 
                                   delimiter: str = "",
                                   base_quote_mapping: Optional[Dict[str, str]] = None) -> str:
    """
    Convert Hummingbot trading pair to exchange format.
    
    Args:
        hb_trading_pair: Trading pair in Hummingbot format
        delimiter: Delimiter used by the exchange
        base_quote_mapping: Optional mapping for asset symbols
        
    Returns:
        Trading pair in exchange format
    """
    base, quote = split_hb_trading_pair(hb_trading_pair)
    
    if base_quote_mapping:
        base = base_quote_mapping.get(base, base)
        quote = base_quote_mapping.get(quote, quote)
    
    return f"{base}{delimiter}{quote}"


def convert_from_exchange_trading_pair(exchange_trading_pair: str,
                                     delimiter: str = "",
                                     base_quote_mapping: Optional[Dict[str, str]] = None) -> str:
    """
    Convert exchange trading pair to Hummingbot format.
    
    Args:
        exchange_trading_pair: Trading pair in exchange format
        delimiter: Delimiter used by the exchange
        base_quote_mapping: Optional reverse mapping for asset symbols
        
    Returns:
        Trading pair in Hummingbot format
    """
    if delimiter:
        parts = exchange_trading_pair.split(delimiter)
    else:
        # For exchanges without delimiters, this is more complex
        # This is a simplified implementation
        parts = [exchange_trading_pair[:3], exchange_trading_pair[3:]]
    
    if len(parts) != 2:
        raise ValueError(f"Cannot parse exchange trading pair: {exchange_trading_pair}")
    
    base, quote = parts[0], parts[1]
    
    if base_quote_mapping:
        base = base_quote_mapping.get(base, base)
        quote = base_quote_mapping.get(quote, quote)
    
    return combine_to_hb_trading_pair(base, quote)


def get_new_client_order_id(is_buy: bool, trading_pair: str, 
                           hbot_order_id_prefix: str = "HB") -> str:
    """
    Generate a new client order ID.
    
    Args:
        is_buy: Whether this is a buy order
        trading_pair: Trading pair for the order
        hbot_order_id_prefix: Prefix for the order ID
        
    Returns:
        New client order ID
    """
    side = "B" if is_buy else "S"
    timestamp = int(time.time() * 1000)
    base, quote = split_hb_trading_pair(trading_pair)
    
    return f"{hbot_order_id_prefix}{side}{base[:2]}{quote[:2]}{timestamp}"


def retry_sleep_time(try_count: int, max_sleep_time: float = 60.0) -> float:
    """
    Calculate exponential backoff sleep time for retries.
    
    Args:
        try_count: Current retry attempt count
        max_sleep_time: Maximum sleep time
        
    Returns:
        Sleep time in seconds
    """
    sleep_time = min(max_sleep_time, (2 ** try_count))
    return sleep_time


async def aiohttp_response_with_errors(response) -> Dict[str, Any]:
    """
    Process aiohttp response and handle errors.
    
    Args:
        response: aiohttp response object
        
    Returns:
        Response data as dictionary
        
    Raises:
        Exception: If response indicates an error
    """
    try:
        response_data = await response.json()
        
        if response.status >= 400:
            error_msg = f"HTTP {response.status}: {response_data}"
            raise Exception(error_msg)
        
        return response_data
    except Exception as e:
        raise Exception(f"Error processing response: {str(e)}")


def build_api_factory() -> Any:
    """
    Build API factory for creating API clients.
    This is a placeholder implementation.
    
    Returns:
        API factory instance
    """
    # Placeholder implementation
    return None


def get_tracking_nonce() -> int:
    """
    Get a tracking nonce for order tracking.
    
    Returns:
        Tracking nonce as integer
    """
    return int(time.time() * 1000000)
