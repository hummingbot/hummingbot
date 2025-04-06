import os
import time
import logging
from decimal import Decimal
from typing import Dict, List, Set, Optional, Tuple, Any
import datetime
import random
import numpy as np
import pandas as pd
from collections import deque

from pydantic import Field

from hummingbot.client.config.config_data_types import BaseClientModel, ClientFieldData
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.strategy.strategy_py_base import (
    BuyOrderCompletedEvent,
    SellOrderCompletedEvent,
    OrderFilledEvent,
    BuyOrderCreatedEvent,
    SellOrderCreatedEvent,
)

# ML dependency handling
try:
    import numpy as np
    import pandas as pd
    HAS_PANDAS_NUMPY = True
except ImportError:
    HAS_PANDAS_NUMPY = False
    
# TensorFlow and ML imports
try:
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras import layers
    from tensorflow.keras.callbacks import EarlyStopping
    from tensorflow.keras.regularizers import l1_l2
    import sklearn
    from sklearn.preprocessing import StandardScaler, MinMaxScaler
    from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
    from sklearn.model_selection import train_test_split
    import lightgbm as lgb
    import joblib
    import optuna
    HAS_ML_DEPENDENCIES = True
    
    # Configure TensorFlow if available
    physical_devices = tf.config.list_physical_devices('GPU')
    if physical_devices:
        try:
            tf.config.experimental.set_memory_growth(physical_devices[0], True)
        except:
            pass
except ImportError:
    HAS_ML_DEPENDENCIES = False

# Logger for ML models
ml_logger = logging.getLogger("MLModels")

# Install dependencies if not available
def install_dependencies():
    """Install required dependencies if they are not already installed"""
    global HAS_PANDAS_NUMPY, HAS_ML_DEPENDENCIES
    
    try:
        if not HAS_PANDAS_NUMPY:
            import sys
            import subprocess
            ml_logger.info("Installing pandas and numpy...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pandas", "numpy"])
            import numpy as np
            import pandas as pd
            HAS_PANDAS_NUMPY = True
            
        if not HAS_ML_DEPENDENCIES:
            import sys
            import subprocess
            ml_logger.info("Installing ML dependencies...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", 
                                  "tensorflow", "scikit-learn", "lightgbm", 
                                  "joblib", "optuna"])
            import tensorflow as tf
            from tensorflow import keras
            from tensorflow.keras import layers
            from tensorflow.keras.callbacks import EarlyStopping
            from tensorflow.keras.regularizers import l1_l2
            import sklearn
            from sklearn.preprocessing import StandardScaler, MinMaxScaler
            from sklearn.ensemble import RandomForestClassifier
            from sklearn.model_selection import train_test_split
            import lightgbm as lgb
            import joblib
            import optuna
            
            # Configure TensorFlow
            physical_devices = tf.config.list_physical_devices('GPU')
            if physical_devices:
                try:
                    tf.config.experimental.set_memory_growth(physical_devices[0], True)
                except:
                    pass
                    
            HAS_ML_DEPENDENCIES = True
            ml_logger.info("Successfully installed ML dependencies")
            return True
    except Exception as e:
        ml_logger.error(f"Failed to install dependencies: {e}")
        return False
    
    return True 

# Configuration class for the strategy
class AdaptiveMMConfig(BaseClientModel):
    """
    Configuration parameters for the Adaptive Market Making strategy.
    This strategy combines technical indicators with ML predictions to dynamically
    adjust spreads and position sizes.
    """
    script_file_name: str = Field(default_factory=lambda: os.path.basename(__file__))
    
    # Exchange and market parameters
    connector_name: str = Field("binance_paper_trade", client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Exchange where the bot will place orders"))
    trading_pair: str = Field("ETH-USDT", client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Trading pair where the bot will place orders"))
    
    # Basic market making parameters
    order_amount: Decimal = Field(Decimal("0.01"), client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Order amount (denominated in base asset)"))
    min_spread: Decimal = Field(Decimal("0.001"), client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Minimum spread (in decimal, e.g. 0.001 for 0.1%)"))
    max_spread: Decimal = Field(Decimal("0.01"), client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Maximum spread (in decimal, e.g. 0.01 for 1%)"))
    order_refresh_time: float = Field(10.0, client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Order refresh time (in seconds)"))
    max_order_age: float = Field(300.0, client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Maximum order age (in seconds)"))
    
    # Technical indicator parameters
    rsi_length: int = Field(14, client_data=ClientFieldData(
        prompt_on_new=False, prompt=lambda mi: "RSI length"))
    rsi_overbought: float = Field(70.0, client_data=ClientFieldData(
        prompt_on_new=False, prompt=lambda mi: "RSI overbought threshold"))
    rsi_oversold: float = Field(30.0, client_data=ClientFieldData(
        prompt_on_new=False, prompt=lambda mi: "RSI oversold threshold"))
    ema_short: int = Field(12, client_data=ClientFieldData(
        prompt_on_new=False, prompt=lambda mi: "EMA short period"))
    ema_long: int = Field(26, client_data=ClientFieldData(
        prompt_on_new=False, prompt=lambda mi: "EMA long period"))
    
    # Bollinger Bands parameters
    bb_length1: int = Field(120, client_data=ClientFieldData(
        prompt_on_new=False, prompt=lambda mi: "BB primary length"))
    bb_length2: int = Field(12, client_data=ClientFieldData(
        prompt_on_new=False, prompt=lambda mi: "BB secondary length"))
    bb_std: float = Field(2.0, client_data=ClientFieldData(
        prompt_on_new=False, prompt=lambda mi: "BB standard deviation multiplier"))
    bb_use_kalman: bool = Field(True, client_data=ClientFieldData(
        prompt_on_new=False, prompt=lambda mi: "Use Kalman filter on BB calculation"))
    
    # Risk management parameters
    max_inventory_ratio: float = Field(0.5, client_data=ClientFieldData(
        prompt_on_new=False, prompt=lambda mi: "Maximum inventory ratio"))
    min_inventory_ratio: float = Field(0.3, client_data=ClientFieldData(
        prompt_on_new=False, prompt=lambda mi: "Minimum inventory ratio"))
    volatility_adjustment: float = Field(1.0, client_data=ClientFieldData(
        prompt_on_new=False, prompt=lambda mi: "Volatility adjustment factor"))
    trailing_stop_pct: Decimal = Field(Decimal("0.02"), client_data=ClientFieldData(
        prompt_on_new=False, prompt=lambda mi: "Trailing stop percentage"))
    
    # ML parameters
    use_ml: bool = Field(True, client_data=ClientFieldData(
        prompt_on_new=True, prompt=lambda mi: "Use ML predictions to enhance strategy"))
    ml_data_buffer_size: int = Field(5000, client_data=ClientFieldData(
        prompt_on_new=False, prompt=lambda mi: "ML data buffer size"))
    ml_update_interval: int = Field(3600, client_data=ClientFieldData(
        prompt_on_new=False, prompt=lambda mi: "ML model update interval (in seconds)"))
    ml_confidence_threshold: float = Field(0.65, client_data=ClientFieldData(
        prompt_on_new=False, prompt=lambda mi: "ML confidence threshold"))
    ml_signal_weight: float = Field(0.35, client_data=ClientFieldData(
        prompt_on_new=False, prompt=lambda mi: "ML signal weight"))
    ml_model_dir: str = Field("./models", client_data=ClientFieldData(
        prompt_on_new=False, prompt=lambda mi: "Directory for ML models")) 