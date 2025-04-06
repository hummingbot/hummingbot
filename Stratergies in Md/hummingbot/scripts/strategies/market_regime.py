"""
Market Regime Detection Module

This module contains the implementation of market regime detection algorithms
used by the Adaptive Market Making Strategy.
"""

import numpy as np
from typing import List, Dict, Any, Optional
from scipy import stats


class MarketRegimeDetector:
    """
    Detects market regimes (trending, ranging, volatile) from price data
    """
    
    def __init__(self, lookback_window: int = 100):
        """
        Initialize the MarketRegimeDetector
        
        Args:
            lookback_window: Number of data points to consider for regime detection
        """
        self.lookback_window = lookback_window
        
    def detect_regime(
        self, 
        prices: List[float], 
        volumes: Optional[List[float]] = None
    ) -> Dict[str, Any]:
        """
        Detect market regime from price history
        
        Args:
            prices: Array of historical prices
            volumes: Optional array of volume data
            
        Returns:
            Dict with regime info
        """
        if len(prices) < self.lookback_window:
            return {
                "regime": "unknown", 
                "confidence": 0.0, 
                "trend_direction": 0,
                "volatility": 0.0
            }
            
        # Get relevant price window
        price_window = prices[-self.lookback_window:]
        
        # Calculate returns and volatility
        returns = np.diff(price_window) / price_window[:-1]
        volatility = np.std(returns) * np.sqrt(252)  # Annualized
        
        # Check for trend using linear regression
        x = np.arange(len(price_window))
        slope, _, r_value, _, _ = stats.linregress(x, price_window)
        
        # Use volume if available
        vol_signal = 0
        if volumes is not None and len(volumes) >= self.lookback_window:
            vol_window = volumes[-self.lookback_window:]
            vol_ma = np.mean(vol_window)
            recent_vol = np.mean(vol_window[-5:])
            vol_signal = 1 if recent_vol > vol_ma * 1.5 else 0
            
        # Determine regime
        if volatility > 0.05:  # High volatility
            if abs(r_value) > 0.7:  # Strong trend
                regime = "trending_volatile"
                confidence = abs(r_value) * 0.8 + volatility * 4
                trend_direction = 1 if slope > 0 else -1
            else:
                regime = "volatile"
                confidence = volatility * 10
                trend_direction = 0
        else:  # Lower volatility
            if abs(r_value) > 0.7:  # Strong trend
                regime = "trending"
                confidence = abs(r_value)
                trend_direction = 1 if slope > 0 else -1
            else:
                regime = "ranging"
                confidence = 1 - abs(r_value)
                trend_direction = 0
                
        # Adjust confidence based on volume signal
        if vol_signal and trend_direction != 0:
            confidence *= 1.2
                
        return {
            "regime": regime,
            "confidence": min(1.0, confidence),
            "trend_direction": trend_direction,
            "volatility": volatility
        }
    
    def calculate_regime_features(
        self, 
        prices: List[float], 
        volumes: Optional[List[float]] = None
    ) -> Dict[str, float]:
        """
        Calculate features that describe the current market regime
        
        Args:
            prices: Array of historical prices
            volumes: Optional array of volume data
            
        Returns:
            Dictionary of features describing the market regime
        """
        if len(prices) < self.lookback_window:
            return {
                "trend_strength": 0.0,
                "volatility": 0.0,
                "volume_intensity": 0.0,
                "range_width": 0.0
            }
        
        # Get relevant price window
        price_window = prices[-self.lookback_window:]
        
        # Calculate returns
        returns = np.diff(price_window) / price_window[:-1]
        
        # Calculate trend strength using linear regression
        x = np.arange(len(price_window))
        _, _, r_value, _, _ = stats.linregress(x, price_window)
        trend_strength = abs(r_value)
        
        # Calculate volatility
        volatility = np.std(returns) * np.sqrt(252)  # Annualized
        
        # Calculate range width
        price_range = max(price_window) - min(price_window)
        range_width = price_range / np.mean(price_window)
        
        # Calculate volume intensity if volume data is available
        volume_intensity = 0.0
        if volumes is not None and len(volumes) >= self.lookback_window:
            vol_window = volumes[-self.lookback_window:]
            vol_ma = np.mean(vol_window)
            recent_vol = np.mean(vol_window[-5:])
            volume_intensity = recent_vol / vol_ma
        
        return {
            "trend_strength": trend_strength,
            "volatility": volatility,
            "volume_intensity": volume_intensity,
            "range_width": range_width
        } 