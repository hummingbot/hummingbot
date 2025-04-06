"""
Technical Indicators for Crypto Trading
v2.0.0
"""

import numpy as np
import pandas as pd
from typing import Tuple, List, Dict, Any, Union

class TechnicalIndicators:
    """Collection of technical indicators for market analysis."""
    
    @staticmethod
    def sma(data: np.ndarray, period: int) -> np.ndarray:
        """Simple Moving Average."""
        return np.convolve(data, np.ones(period)/period, mode='valid')
    
    @staticmethod
    def ema(data: np.ndarray, period: int) -> np.ndarray:
        """Exponential Moving Average."""
        alpha = 2 / (period + 1)
        ema = np.zeros_like(data)
        ema[0] = data[0]
        
        for i in range(1, len(data)):
            ema[i] = alpha * data[i] + (1 - alpha) * ema[i-1]
            
        return ema
    
    @staticmethod
    def rsi(data: np.ndarray, period: int = 14) -> np.ndarray:
        """Relative Strength Index."""
        delta = np.diff(data)
        gains = np.where(delta > 0, delta, 0)
        losses = np.where(delta < 0, -delta, 0)
        
        avg_gain = np.zeros_like(data)
        avg_loss = np.zeros_like(data)
        
        # First average
        avg_gain[period] = np.mean(gains[:period])
        avg_loss[period] = np.mean(losses[:period])
        
        # Rest of the averages
        for i in range(period + 1, len(data)):
            avg_gain[i] = (avg_gain[i-1] * (period - 1) + gains[i-1]) / period
            avg_loss[i] = (avg_loss[i-1] * (period - 1) + losses[i-1]) / period
        
        rs = avg_gain / (avg_loss + 1e-10)  # Add small constant to avoid division by zero
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    @staticmethod
    def macd(data: np.ndarray, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Moving Average Convergence Divergence."""
        ema_fast = TechnicalIndicators.ema(data, fast_period)
        ema_slow = TechnicalIndicators.ema(data, slow_period)
        
        macd_line = ema_fast - ema_slow
        signal_line = TechnicalIndicators.ema(macd_line, signal_period)
        histogram = macd_line - signal_line
        
        return macd_line, signal_line, histogram
    
    @staticmethod
    def bollinger_bands(data: np.ndarray, period: int = 20, num_std: float = 2.0) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Bollinger Bands."""
        # Calculate middle band (SMA)
        middle_band = np.zeros_like(data)
        for i in range(period - 1, len(data)):
            middle_band[i] = np.mean(data[i - period + 1:i + 1])
        
        # Calculate standard deviation
        std_dev = np.zeros_like(data)
        for i in range(period - 1, len(data)):
            std_dev[i] = np.std(data[i - period + 1:i + 1])
        
        # Calculate upper and lower bands
        upper_band = middle_band + (std_dev * num_std)
        lower_band = middle_band - (std_dev * num_std)
        
        return upper_band, middle_band, lower_band
    
    @staticmethod
    def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
        """Average True Range."""
        tr = np.zeros(len(high))
        
        # First true range is just high - low
        tr[0] = high[0] - low[0]
        
        # Calculate true range for the rest
        for i in range(1, len(high)):
            tr[i] = max(
                high[i] - low[i],              # Current high - low
                abs(high[i] - close[i-1]),     # Current high - previous close
                abs(low[i] - close[i-1])       # Current low - previous close
            )
        
        # Calculate ATR using EMA
        atr = TechnicalIndicators.ema(tr, period)
        
        return atr
    
    @staticmethod
    def vwap(high: np.ndarray, low: np.ndarray, close: np.ndarray, volume: np.ndarray, period: int = 14) -> np.ndarray:
        """Volume Weighted Average Price."""
        typical_price = (high + low + close) / 3
        tp_volume = typical_price * volume
        
        vwap = np.zeros_like(close)
        
        for i in range(period - 1, len(close)):
            vwap[i] = np.sum(tp_volume[i - period + 1:i + 1]) / np.sum(volume[i - period + 1:i + 1])
        
        return vwap
    
    @staticmethod
    def stochastic_oscillator(high: np.ndarray, low: np.ndarray, close: np.ndarray, k_period: int = 14, d_period: int = 3) -> Tuple[np.ndarray, np.ndarray]:
        """Stochastic Oscillator."""
        # Initialize arrays
        k = np.zeros_like(close)
        d = np.zeros_like(close)
        
        # Calculate %K
        for i in range(k_period - 1, len(close)):
            highest_high = np.max(high[i - k_period + 1:i + 1])
            lowest_low = np.min(low[i - k_period + 1:i + 1])
            
            if highest_high == lowest_low:
                k[i] = 50.0  # Middle value if range is zero
            else:
                k[i] = 100 * (close[i] - lowest_low) / (highest_high - lowest_low)
        
        # Calculate %D using SMA of %K
        for i in range(k_period + d_period - 2, len(close)):
            d[i] = np.mean(k[i - d_period + 1:i + 1])
        
        return k, d
    
    @staticmethod
    def calculate_all_indicators(ohlcv_df: pd.DataFrame) -> pd.DataFrame:
        """Calculate all indicators for a DataFrame with OHLCV data."""
        # Create a copy of the dataframe
        df = ohlcv_df.copy()
        
        # Extract arrays
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        volume = df['volume'].values if 'volume' in df.columns else np.ones_like(close)
        
        # Calculate indicators
        # SMA
        for period in [5, 10, 20, 50, 200]:
            sma = TechnicalIndicators.sma(close, period)
            # Pad the beginning with NaN
            sma_padded = np.full_like(close, np.nan)
            sma_padded[period-1:] = sma
            df[f'sma_{period}'] = sma_padded
        
        # EMA
        for period in [5, 10, 20, 50, 200]:
            df[f'ema_{period}'] = TechnicalIndicators.ema(close, period)
        
        # RSI
        df['rsi_14'] = TechnicalIndicators.rsi(close)
        
        # MACD
        macd, signal, hist = TechnicalIndicators.macd(close)
        df['macd'] = macd
        df['macd_signal'] = signal
        df['macd_hist'] = hist
        
        # Bollinger Bands
        upper, middle, lower = TechnicalIndicators.bollinger_bands(close)
        df['bb_upper'] = upper
        df['bb_middle'] = middle
        df['bb_lower'] = lower
        df['bb_width'] = (upper - lower) / middle
        
        # ATR
        df['atr_14'] = TechnicalIndicators.atr(high, low, close)
        
        # VWAP
        df['vwap_14'] = TechnicalIndicators.vwap(high, low, close, volume)
        
        # Stochastic Oscillator
        k, d = TechnicalIndicators.stochastic_oscillator(high, low, close)
        df['stoch_k'] = k
        df['stoch_d'] = d
        
        return df

def calculate_support_resistance(prices: np.ndarray, window_size: int = 10, threshold: float = 0.02) -> Dict[str, List[float]]:
    """
    Calculate support and resistance levels using a windowed approach.
    
    Args:
        prices: Array of price values
        window_size: Size of the window to consider for local extrema
        threshold: Minimum percentage difference to consider as distinct level
        
    Returns:
        Dictionary containing support and resistance levels
    """
    supports = []
    resistances = []
    
    # Find local minima (supports) and maxima (resistances)
    for i in range(window_size, len(prices) - window_size):
        # Check if it's a local minimum
        if all(prices[i] <= prices[i-j] for j in range(1, window_size+1)) and \
           all(prices[i] <= prices[i+j] for j in range(1, window_size+1)):
            supports.append(prices[i])
            
        # Check if it's a local maximum
        if all(prices[i] >= prices[i-j] for j in range(1, window_size+1)) and \
           all(prices[i] >= prices[i+j] for j in range(1, window_size+1)):
            resistances.append(prices[i])
    
    # Cluster close levels together
    supports = cluster_levels(supports, threshold)
    resistances = cluster_levels(resistances, threshold)
    
    return {
        'supports': supports,
        'resistances': resistances
    }

def cluster_levels(levels: List[float], threshold: float) -> List[float]:
    """
    Cluster price levels that are within threshold percentage of each other.
    
    Args:
        levels: List of price levels
        threshold: Maximum percentage difference to consider as same level
        
    Returns:
        List of clustered price levels
    """
    if not levels:
        return []
        
    # Sort levels
    sorted_levels = sorted(levels)
    clustered = []
    current_cluster = [sorted_levels[0]]
    
    for i in range(1, len(sorted_levels)):
        # If current level is within threshold of the average of current cluster
        cluster_avg = sum(current_cluster) / len(current_cluster)
        if abs(sorted_levels[i] - cluster_avg) / cluster_avg <= threshold:
            current_cluster.append(sorted_levels[i])
        else:
            # Add average of current cluster to results
            clustered.append(sum(current_cluster) / len(current_cluster))
            # Start new cluster
            current_cluster = [sorted_levels[i]]
    
    # Add the last cluster
    if current_cluster:
        clustered.append(sum(current_cluster) / len(current_cluster))
    
    return clustered 