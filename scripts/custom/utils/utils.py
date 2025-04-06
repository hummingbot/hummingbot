"""
Utility Module

This module contains utility functions used by the Adaptive Market Making Strategy.
"""

import time
import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple, Union
from decimal import Decimal


def convert_to_decimal(value: Union[float, int, str]) -> Decimal:
    """
    Convert value to Decimal
    
    Args:
        value: Value to convert
        
    Returns:
        Decimal value
    """
    return Decimal(str(value))


def format_price(price: Decimal, tick_size: Decimal) -> Decimal:
    """
    Format price according to tick size
    
    Args:
        price: Price to format
        tick_size: Minimum price increment
        
    Returns:
        Formatted price
    """
    return Decimal(int(price / tick_size)) * tick_size


def format_amount(amount: Decimal, step_size: Decimal) -> Decimal:
    """
    Format amount according to step size
    
    Args:
        amount: Amount to format
        step_size: Minimum amount increment
        
    Returns:
        Formatted amount
    """
    return Decimal(int(amount / step_size)) * step_size


def calculate_inventory_ratio(
    base_balance: Decimal,
    quote_balance: Decimal,
    price: Decimal
) -> float:
    """
    Calculate the ratio of base asset value to total portfolio value
    
    Args:
        base_balance: Balance of base asset
        quote_balance: Balance of quote asset
        price: Current price of base asset in quote asset
        
    Returns:
        Inventory ratio (0.0 to 1.0)
    """
    base_value = float(base_balance) * float(price)
    total_value = base_value + float(quote_balance)
    
    if total_value == 0:
        return 0.5  # Default to balanced if no assets
    
    return base_value / total_value


def calculate_market_mid_price(
    order_book: Dict[str, List[List[float]]]
) -> Decimal:
    """
    Calculate mid price from order book
    
    Args:
        order_book: Order book data with 'bids' and 'asks'
        
    Returns:
        Mid price
    """
    if not order_book or 'bids' not in order_book or 'asks' not in order_book:
        return Decimal('0')
    
    if not order_book['bids'] or not order_book['asks']:
        return Decimal('0')
    
    bid = Decimal(str(order_book['bids'][0][0]))
    ask = Decimal(str(order_book['asks'][0][0]))
    
    return (bid + ask) / Decimal('2')


def calculate_spread_percentage(
    bid_price: Decimal,
    ask_price: Decimal
) -> Decimal:
    """
    Calculate spread percentage
    
    Args:
        bid_price: Bid price
        ask_price: Ask price
        
    Returns:
        Spread percentage
    """
    mid_price = (bid_price + ask_price) / Decimal('2')
    
    if mid_price == Decimal('0'):
        return Decimal('0')
    
    return (ask_price - bid_price) / mid_price


def detect_price_jump(
    prices: List[float],
    threshold: float = 0.03,
    window: int = 5
) -> bool:
    """
    Detect if there was a significant price jump
    
    Args:
        prices: List of recent prices
        threshold: Threshold for price jump detection (percentage)
        window: Window size for detection
        
    Returns:
        True if price jump detected, False otherwise
    """
    if len(prices) < window + 1:
        return False
    
    # Calculate returns
    returns = [prices[i] / prices[i-1] - 1 for i in range(1, len(prices))]
    
    # Check for price jump
    for i in range(len(returns) - window + 1):
        window_returns = returns[i:i+window]
        if abs(sum(window_returns)) > threshold:
            return True
    
    return False


def calculate_volatility(
    prices: List[float],
    window: int = 20
) -> float:
    """
    Calculate price volatility (standard deviation of returns)
    
    Args:
        prices: List of prices
        window: Window size for volatility calculation
        
    Returns:
        Volatility
    """
    if len(prices) < window + 1:
        return 0.0
    
    # Calculate returns
    returns = [prices[i] / prices[i-1] - 1 for i in range(1, len(prices))]
    
    # Calculate standard deviation of returns
    if len(returns) < window:
        return np.std(returns) * np.sqrt(252)  # Annualized
    
    return np.std(returns[-window:]) * np.sqrt(252)  # Annualized


def convert_ohlcv_to_dataframe(
    ohlcv_data: List[List[float]]
) -> pd.DataFrame:
    """
    Convert OHLCV data to pandas DataFrame
    
    Args:
        ohlcv_data: List of OHLCV data [timestamp, open, high, low, close, volume]
        
    Returns:
        DataFrame with OHLCV data
    """
    df = pd.DataFrame(
        ohlcv_data,
        columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
    )
    
    # Convert timestamp to datetime
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    
    return df


def get_position_side(
    base_balance: Decimal,
    inventory_target_base_pct: float,
    price: Decimal,
    quote_balance: Decimal
) -> str:
    """
    Determine position side (long/short) based on inventory
    
    Args:
        base_balance: Balance of base asset
        inventory_target_base_pct: Target percentage of base asset
        price: Current price of base asset in quote asset
        quote_balance: Balance of quote asset
        
    Returns:
        Position side ('long', 'short', or 'neutral')
    """
    # Calculate current inventory ratio
    current_ratio = calculate_inventory_ratio(base_balance, quote_balance, price)
    
    # Determine position side based on difference from target
    diff = current_ratio - inventory_target_base_pct
    
    if abs(diff) < 0.05:  # 5% tolerance
        return 'neutral'
    elif diff < 0:
        return 'long'  # Need to buy more base asset
    else:
        return 'short'  # Need to sell base asset


def estimate_position_value(
    base_balance: Decimal,
    price: Decimal
) -> Decimal:
    """
    Estimate position value in quote asset
    
    Args:
        base_balance: Balance of base asset
        price: Current price of base asset in quote asset
        
    Returns:
        Position value in quote asset
    """
    return base_balance * price


def calculate_realized_pnl(
    trades: List[Dict[str, Any]]
) -> Decimal:
    """
    Calculate realized PnL from trades
    
    Args:
        trades: List of trade data
        
    Returns:
        Realized PnL
    """
    buy_volume = Decimal('0')
    buy_value = Decimal('0')
    sell_volume = Decimal('0')
    sell_value = Decimal('0')
    
    for trade in trades:
        if trade['side'] == 'buy':
            buy_volume += Decimal(str(trade['amount']))
            buy_value += Decimal(str(trade['amount'])) * Decimal(str(trade['price']))
        else:  # sell
            sell_volume += Decimal(str(trade['amount']))
            sell_value += Decimal(str(trade['amount'])) * Decimal(str(trade['price']))
    
    # Calculate average prices
    avg_buy_price = buy_value / buy_volume if buy_volume > 0 else Decimal('0')
    avg_sell_price = sell_value / sell_volume if sell_volume > 0 else Decimal('0')
    
    # Calculate realized PnL
    common_volume = min(buy_volume, sell_volume)
    if common_volume == 0:
        return Decimal('0')
    
    realized_pnl = (avg_sell_price - avg_buy_price) * common_volume
    return realized_pnl 