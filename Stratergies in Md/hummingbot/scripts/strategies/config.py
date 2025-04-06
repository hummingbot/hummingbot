"""
Configuration Module for Adaptive Market Making Strategy

This module defines the configuration parameters for the Adaptive Market Making Strategy.
"""

import os
from decimal import Decimal
from typing import Dict, Any, List

from pydantic import Field, BaseModel


class AdaptiveMMConfig(BaseModel):
    """
    Configuration parameters for the Adaptive Market Making strategy.
    This strategy combines technical indicators with ML predictions to dynamically
    adjust spreads and position sizes.
    """
    script_file_name: str = Field(default="adaptive_market_making.py")
    
    # Exchange and market parameters
    connector_name: str = Field("binance_paper_trade")
    trading_pair: str = Field("ETH-USDT")
    
    # Basic market making parameters
    order_amount: Decimal = Field(Decimal("0.01"))
    min_spread: Decimal = Field(Decimal("0.001"))
    max_spread: Decimal = Field(Decimal("0.01"))
    order_refresh_time: float = Field(10.0)
    max_order_age: float = Field(300.0)
    
    # Technical indicator parameters
    rsi_length: int = Field(14)
    rsi_overbought: float = Field(70.0)
    rsi_oversold: float = Field(30.0)
    ema_short: int = Field(12)
    ema_long: int = Field(26)
    
    # Bollinger Bands parameters
    bb_length: int = Field(20)
    bb_std: float = Field(2.0)
    bb_use_kalman: bool = Field(True)
    
    # Risk management parameters
    max_inventory_ratio: float = Field(0.5)
    min_inventory_ratio: float = Field(0.3)
    volatility_adjustment: float = Field(1.0)
    trailing_stop_pct: Decimal = Field(Decimal("0.02"))
    
    # ML parameters
    use_ml: bool = Field(False)
    ml_data_buffer_size: int = Field(5000)
    ml_update_interval: int = Field(3600)
    ml_confidence_threshold: float = Field(0.65)
    
    # Multi-timeframe parameters
    primary_timeframe: str = Field("1h")
    secondary_timeframe: str = Field("15m")
    tertiary_timeframe: str = Field("1d")
    
    # Score threshold for signal strength
    signal_threshold: float = Field(30.0)
    
    # Additional strategy parameters
    inventory_target_base_pct: float = Field(0.5)
    min_order_amount: Decimal = Field(Decimal("0.001"))


class TradingParam:
    """Helper class for strategy parameter tuning"""
    def __init__(self, 
                 default_value: Any, 
                 min_value: Any = None, 
                 max_value: Any = None,
                 step: Any = None):
        self.default = default_value
        self.min = min_value
        self.max = max_value
        self.step = step
        self.value = default_value

    def set_value(self, value: Any) -> None:
        """Set parameter value"""
        if self.min is not None and value < self.min:
            self.value = self.min
        elif self.max is not None and value > self.max:
            self.value = self.max
        else:
            self.value = value

    def get_value(self) -> Any:
        """Get parameter value"""
        return self.value


class StrategyParameters:
    """
    Mutable strategy parameters that can be adjusted dynamically
    """
    
    def __init__(self, config: AdaptiveMMConfig = None):
        """Initialize with default values or from configuration"""
        # Initialize with config if provided, otherwise use default values
        if config is None:
            config = AdaptiveMMConfig()
        
        # Initialize trading parameters
        self.min_spread = TradingParam(
            default_value=float(config.min_spread),
            min_value=0.0001,
            max_value=0.05,
            step=0.0001
        )
        
        self.max_spread = TradingParam(
            default_value=float(config.max_spread),
            min_value=0.001,
            max_value=0.1,
            step=0.001
        )
        
        self.order_amount = TradingParam(
            default_value=float(config.order_amount),
            min_value=0.001
        )
        
        self.inventory_target_base_pct = TradingParam(
            default_value=config.inventory_target_base_pct,
            min_value=0.0,
            max_value=1.0,
            step=0.01
        )
        
        self.volatility_adjustment = TradingParam(
            default_value=config.volatility_adjustment,
            min_value=0.1,
            max_value=5.0,
            step=0.1
        )
        
        self.signal_threshold = TradingParam(
            default_value=config.signal_threshold,
            min_value=0.0,
            max_value=100.0,
            step=1.0
        )
    
    def update_parameters(self, market_state: Dict[str, Any]) -> None:
        """
        Update parameters based on market state
        
        Args:
            market_state: Dictionary containing market data and indicators
        """
        # Example of parameter adaptation based on market conditions
        
        # Adjust spread based on volatility
        if market_state.get('volatility', 0.0) > 0.05:
            # Higher volatility -> wider spread
            volatility_factor = market_state.get('volatility', 0.0) * 10
            new_min_spread = self.min_spread.default * (1 + volatility_factor)
            self.min_spread.set_value(min(new_min_spread, self.max_spread.value))
        else:
            # Lower volatility -> tighter spread
            self.min_spread.set_value(self.min_spread.default)
        
        # Adjust position size based on trend strength
        trend_strength = market_state.get('trend_strength', 0.0)
        if trend_strength > 0.7:
            # Strong trend -> larger position size
            self.order_amount.set_value(self.order_amount.default * 1.2)
        else:
            # Weak or no trend -> normal position size
            self.order_amount.set_value(self.order_amount.default)
        
        # Adjust inventory target based on market regime
        regime = market_state.get('regime', 'unknown')
        if regime == 'trending':
            # In trending market, adjust inventory target based on trend direction
            trend_direction = market_state.get('trend_direction', 0)
            if trend_direction > 0:
                # Bullish trend -> increase base asset target
                self.inventory_target_base_pct.set_value(0.6)
            elif trend_direction < 0:
                # Bearish trend -> decrease base asset target
                self.inventory_target_base_pct.set_value(0.4)
        else:
            # In other regimes, use balanced inventory
            self.inventory_target_base_pct.set_value(0.5)


def load_strategy_config_from_yaml(file_path: str) -> AdaptiveMMConfig:
    """
    Load strategy configuration from YAML file
    
    Args:
        file_path: Path to YAML configuration file
        
    Returns:
        AdaptiveMMConfig object
    """
    # Note: In a real implementation, this would parse a YAML config file
    # For this example, we'll just return the default config
    return AdaptiveMMConfig()


def save_strategy_config_to_yaml(config: AdaptiveMMConfig, file_path: str) -> None:
    """
    Save strategy configuration to YAML file
    
    Args:
        config: AdaptiveMMConfig object
        file_path: Path to save YAML configuration file
    """
    # Note: In a real implementation, this would serialize to YAML
    pass 