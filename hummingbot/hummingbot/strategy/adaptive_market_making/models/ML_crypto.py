from decimal import Decimal
try:
    import numpy as np
    import pandas as pd
except ImportError:
    import sys
    import subprocess
    import os
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pandas", "numpy"])
    import numpy as np
    import pandas as pd

import os
import time
import logging
import datetime
from typing import Dict, List, Optional, Union, Tuple, Any
import random
from collections import deque

# TensorFlow and ML imports
try:
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
    HAS_ML_DEPENDENCIES = True
except ImportError:
    try:
        import sys
        import subprocess
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
        HAS_ML_DEPENDENCIES = True
    except Exception as e:
        logging.warning(f"Failed to install ML dependencies: {e}")
        HAS_ML_DEPENDENCIES = False

# Hummingbot imports
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.strategy_py_base import StrategyPyBase
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.event.events import OrderType, TradeType

# Configure TensorFlow if available
if HAS_ML_DEPENDENCIES:
    physical_devices = tf.config.list_physical_devices('GPU')
    if physical_devices:
        try:
            tf.config.experimental.set_memory_growth(physical_devices[0], True)
        except:
            pass

# Logger for ML models
ml_logger = logging.getLogger("MLModels")

# ML Model Implementation
class FeatureEngineering:
    @staticmethod
    def create_features(df: pd.DataFrame) -> pd.DataFrame:
        df_feat = df.copy()
        
        # Price features
        df_feat['returns'] = df_feat['close'].pct_change()
        df_feat['log_returns'] = np.log(df_feat['close'] / df_feat['close'].shift(1))
        df_feat['volatility'] = df_feat['returns'].rolling(window=14).std()
        
        # Volume features
        df_feat['volume_change'] = df_feat['volume'].pct_change()
        df_feat['volume_ma'] = df_feat['volume'].rolling(window=20).mean()
        df_feat['volume_ratio'] = df_feat['volume'] / df_feat['volume_ma']
        
        # Price pattern features
        df_feat['hl_ratio'] = df_feat['high'] / df_feat['low']
        df_feat['co_ratio'] = df_feat['close'] / df_feat['open']
        
        # Trend features
        for window in [5, 10, 20, 50]:
            df_feat[f'ma_{window}'] = df_feat['close'].rolling(window=window).mean()
            df_feat[f'ma_ratio_{window}'] = df_feat['close'] / df_feat[f'ma_{window}']
        
        # Momentum features
        for period in [3, 6, 12, 24]:
            df_feat[f'momentum_{period}'] = df_feat['close'] / df_feat['close'].shift(period) - 1
        
        # Volatility features
        for window in [5, 10, 20]:
            df_feat[f'vol_{window}'] = df_feat['returns'].rolling(window=window).std()
            
        # Mean reversion features
        for window in [5, 10, 20]:
            rolling_mean = df_feat['close'].rolling(window=window).mean()
            rolling_std = df_feat['close'].rolling(window=window).std()
            df_feat[f'zscore_{window}'] = (df_feat['close'] - rolling_mean) / rolling_std
        
        # Lagged features
        for lag in range(1, 6):
            df_feat[f'close_lag_{lag}'] = df_feat['close'].shift(lag)
            df_feat[f'return_lag_{lag}'] = df_feat['returns'].shift(lag)
        
        # Candle patterns
        df_feat['body_size'] = abs(df_feat['close'] - df_feat['open'])
        df_feat['upper_wick'] = df_feat['high'] - df_feat[['open', 'close']].max(axis=1)
        df_feat['lower_wick'] = df_feat[['open', 'close']].min(axis=1) - df_feat['low']
        
        # Target variables for prediction
        df_feat['target_next_return'] = df_feat['returns'].shift(-1)
        df_feat['target_direction'] = np.where(df_feat['target_next_return'] > 0, 1, 0)
        
        # Drop NaN values
        df_feat = df_feat.dropna()
        
        return df_feat

    @staticmethod
    def prepare_ml_data(df_features: pd.DataFrame, target_col: str = 'target_direction',
                       test_size: float = 0.2, sequence_length: int = 10) -> Tuple:
        # Select features
        feature_cols = [col for col in df_features.columns if col not in 
                      ['target_next_return', 'target_direction', 'date', 'timestamp']]
        
        X = df_features[feature_cols].values
        y = df_features[target_col].values
        
        # Scale features
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        # Split into train and test
        X_train, X_test, y_train, y_test = train_test_split(
            X_scaled, y, test_size=test_size, shuffle=False
        )
        
        # Create sequences for LSTM
        X_train_seq = []
        X_test_seq = []
        
        for i in range(len(X_train) - sequence_length):
            X_train_seq.append(X_train[i:i+sequence_length])
            
        for i in range(len(X_test) - sequence_length):
            X_test_seq.append(X_test[i:i+sequence_length])
        
        # Convert to numpy arrays
        X_train_seq = np.array(X_train_seq)
        X_test_seq = np.array(X_test_seq)
        
        # Adjust targets
        y_train_seq = y_train[sequence_length:]
        y_test_seq = y_test[sequence_length:]
        
        return (X_train, X_test, y_train, y_test, 
                X_train_seq, X_test_seq, y_train_seq, y_test_seq, 
                scaler, feature_cols)

class LSTMModel:
    def __init__(self, input_shape, lstm_units=64, dropout_rate=0.2, l1_reg=0.01, l2_reg=0.01):
        self.input_shape = input_shape
        self.lstm_units = lstm_units
        self.dropout_rate = dropout_rate
        self.l1_reg = l1_reg
        self.l2_reg = l2_reg
        self.model = self._build_model()
        
    def _build_model(self):
        if not HAS_ML_DEPENDENCIES:
            raise ImportError("TensorFlow and Keras are required for LSTM model")
            
        model = keras.Sequential([
            layers.LSTM(self.lstm_units, 
                      return_sequences=True, 
                      input_shape=self.input_shape,
                      kernel_regularizer=l1_l2(l1=self.l1_reg, l2=self.l2_reg)),
            layers.Dropout(self.dropout_rate),
            layers.LSTM(self.lstm_units // 2, 
                      return_sequences=False,
                      kernel_regularizer=l1_l2(l1=self.l1_reg, l2=self.l2_reg)),
            layers.Dropout(self.dropout_rate),
            layers.Dense(32, activation='relu'),
            layers.Dense(1, activation='sigmoid')
        ])
        
        model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=0.001),
            loss='binary_crossentropy',
            metrics=['accuracy']
        )
        
        return model
    
    def train(self, X_train, y_train, X_val=None, y_val=None, 
             batch_size=32, epochs=50, patience=10, save_path=None):
        early_stopping = EarlyStopping(
            monitor='val_loss' if X_val is not None else 'loss',
            patience=patience,
            restore_best_weights=True
        )
        
        validation_data = (X_val, y_val) if X_val is not None and y_val is not None else None
            
        history = self.model.fit(
            X_train, y_train,
            batch_size=batch_size,
            epochs=epochs,
            validation_data=validation_data,
            callbacks=[early_stopping],
            verbose=1
        )
        
        if save_path:
            self.save(save_path)
            
        return history
    
    def predict(self, X):
        return self.model.predict(X)
    
    def save(self, path):
        self.model.save(path)
    
    @classmethod
    def load(cls, path):
        model = keras.models.load_model(path)
        instance = cls(input_shape=model.input_shape[1:])
        instance.model = model
        return instance

class EnsembleModel:
    def __init__(self, models=None):
        self.models = models or []
        self.weights = None
        
    def add_model(self, model, weight=1.0):
        self.models.append(model)
        if self.weights is None:
            self.weights = [weight]
        else:
            self.weights.append(weight)
            # Normalize weights
            self.weights = [w/sum(self.weights) for w in self.weights]
            
    def predict(self, X):
        if not self.models:
            raise ValueError("No models in ensemble")
            
        # Get predictions from all models
        predictions = [model.predict(X) for model in self.models]
        
        # Weight predictions
        if self.weights is None:
            # Equal weights if not specified
            self.weights = [1.0/len(self.models)] * len(self.models)
            
        # Compute weighted average
        weighted_preds = np.zeros_like(predictions[0])
        for pred, weight in zip(predictions, self.weights):
            weighted_preds += pred * weight
            
        return weighted_preds
    
    def update_weights(self, X_val, y_val):
        if not self.models:
            return
            
        # Evaluate each model
        accuracies = []
        for model in self.models:
            preds = model.predict(X_val)
            preds_binary = (preds > 0.5).astype(int)
            accuracy = np.mean(preds_binary.flatten() == y_val)
            accuracies.append(accuracy)
            
        # Normalize accuracies to get weights
        total_accuracy = sum(accuracies)
        if total_accuracy > 0:
            self.weights = [acc/total_accuracy for acc in accuracies]
        else:
            # Equal weights if all models perform poorly
            self.weights = [1.0/len(self.models)] * len(self.models)
            
        ml_logger.info(f"Updated ensemble weights: {self.weights}")

class OnlineModelTrainer:
    def __init__(self, data_buffer_size=5000, update_interval=3600, 
                models_dir='./models', feature_engineering=None):
        self.data_buffer = []
        self.data_buffer_size = data_buffer_size
        self.update_interval = update_interval
        self.models_dir = models_dir
        self.feature_engineering = feature_engineering or FeatureEngineering()
        self.last_update_time = time.time()
        self.models = {}
        self.ensemble = EnsembleModel()
        
        # Create models directory if it doesn't exist
        os.makedirs(models_dir, exist_ok=True)
        
    def add_data_point(self, candle_data):
        self.data_buffer.append(candle_data)
        
        # Keep buffer size under limit
        if len(self.data_buffer) > self.data_buffer_size:
            self.data_buffer = self.data_buffer[-self.data_buffer_size:]
            
        # Check if it's time to update models
        current_time = time.time()
        if current_time - self.last_update_time > self.update_interval:
            self.update_models()
            self.last_update_time = current_time
            
    def update_models(self):
        if not HAS_ML_DEPENDENCIES:
            ml_logger.warning("ML dependencies not available, skipping model update")
            return
            
        if len(self.data_buffer) < 100:  # Minimum data needed
            ml_logger.info("Not enough data for model update")
            return
            
        try:
            # Convert buffer to DataFrame
            df = pd.DataFrame(self.data_buffer)
            
            # Create features
            df_features = self.feature_engineering.create_features(df)
            
            # Prepare data for ML
            (X_train, X_test, y_train, y_test, 
             X_train_seq, X_test_seq, y_train_seq, y_test_seq, 
             scaler, feature_cols) = self.feature_engineering.prepare_ml_data(
                df_features, sequence_length=10)
            
            # Update or create LSTM model
            if 'lstm' not in self.models:
                input_shape = (X_train_seq.shape[1], X_train_seq.shape[2])
                self.models['lstm'] = LSTMModel(input_shape=input_shape)
            
            # Train LSTM model
            self.models['lstm'].train(
                X_train_seq, y_train_seq,
                X_val=X_test_seq, y_val=y_test_seq,
                save_path=os.path.join(self.models_dir, 'lstm_model.h5')
            )
            
            # Update or create Random Forest model
            if 'rf' not in self.models:
                self.models['rf'] = RandomForestClassifier(
                    n_estimators=100, 
                    max_depth=10,
                    random_state=42
                )
                
            self.models['rf'].fit(X_train, y_train)
            joblib.dump(self.models['rf'], 
                       os.path.join(self.models_dir, 'rf_model.joblib'))
            
            # Update or create LightGBM model
            if 'lgbm' not in self.models:
                self.models['lgbm'] = lgb.LGBMClassifier(
                    n_estimators=100,
                    learning_rate=0.05,
                    random_state=42
                )
                
            self.models['lgbm'].fit(X_train, y_train)
            joblib.dump(self.models['lgbm'], 
                       os.path.join(self.models_dir, 'lgbm_model.joblib'))
            
            # Update ensemble
            self.ensemble = EnsembleModel()
            self.ensemble.add_model(self.models['lstm'])
            self.ensemble.add_model(self.models['rf'])
            self.ensemble.add_model(self.models['lgbm'])
            self.ensemble.update_weights(X_test_seq, y_test_seq)
            
            # Save feature scaler
            joblib.dump(scaler, os.path.join(self.models_dir, 'scaler.joblib'))
            
            # Save feature columns
            with open(os.path.join(self.models_dir, 'feature_cols.txt'), 'w') as f:
                f.write('\n'.join(feature_cols))
                
            ml_logger.info("Models updated successfully")
            
            # Calculate feature importance
            if hasattr(self.models['rf'], 'feature_importances_'):
                importances = self.models['rf'].feature_importances_
                feature_importance = dict(zip(feature_cols, importances))
                sorted_importance = {k: v for k, v in sorted(
                    feature_importance.items(), key=lambda item: item[1], reverse=True)}
                
                # Log top 10 most important features
                top_features = list(sorted_importance.items())[:10]
                ml_logger.info(f"Top 10 important features: {top_features}")
                
        except Exception as e:
            ml_logger.error(f"Error updating models: {str(e)}")
            
    def get_prediction(self, latest_data):
        if not HAS_ML_DEPENDENCIES:
            return {"signal": 0, "confidence": 0.5}
            
        if not self.models:
            return {"signal": 0, "confidence": 0.5}
            
        try:
            # Convert to DataFrame
            df = pd.DataFrame([latest_data])
            
            # Add historical data for feature calculation
            combined_data = self.data_buffer[-100:] + [latest_data]
            df_hist = pd.DataFrame(combined_data)
            
            # Create features
            df_features = self.feature_engineering.create_features(df_hist)
            
            # Get the last row with features
            features_row = df_features.iloc[-1:]
            
            # Load scaler
            scaler_path = os.path.join(self.models_dir, 'scaler.joblib')
            if not os.path.exists(scaler_path):
                ml_logger.warning("Scaler not found, cannot make prediction")
                return {"signal": 0, "confidence": 0.5}
                
            scaler = joblib.load(scaler_path)
            
            # Load feature columns
            with open(os.path.join(self.models_dir, 'feature_cols.txt'), 'r') as f:
                feature_cols = f.read().splitlines()
                
            # Select and scale features
            X = features_row[feature_cols].values
            X_scaled = scaler.transform(X)
            
            # Prepare sequence data for LSTM
            sequence_length = 10
            if len(self.data_buffer) >= sequence_length:
                # Get last sequence_length data points
                sequence_data = df_features.iloc[-sequence_length:][feature_cols].values
                sequence_data_scaled = scaler.transform(sequence_data)
                X_seq = np.array([sequence_data_scaled])
                
                # Get ensemble prediction
                if 'lstm' in self.models and hasattr(self.ensemble, 'predict'):
                    pred = self.ensemble.predict(X_seq)[0][0]
                    
                    # Convert to signal and confidence
                    signal = 1 if pred > 0.5 else -1 if pred < 0.5 else 0
                    confidence = max(pred, 1-pred)
                    
                    return {
                        "signal": signal,
                        "confidence": float(confidence),
                        "raw_prediction": float(pred)
                    }
            
            # Fallback to Random Forest if LSTM prediction fails
            if 'rf' in self.models:
                pred = self.models['rf'].predict_proba(X_scaled)[0][1]
                signal = 1 if pred > 0.6 else -1 if pred < 0.4 else 0
                confidence = max(pred, 1-pred)
                
                return {
                    "signal": signal,
                    "confidence": float(confidence),
                    "raw_prediction": float(pred)
                }
                
        except Exception as e:
            ml_logger.error(f"Error making prediction: {str(e)}")
            
        return {"signal": 0, "confidence": 0.5}

class MarketRegimeDetector:
    def __init__(self, lookback_window=100):
        self.lookback_window = lookback_window
        
    def detect_regime(self, prices):
        if len(prices) < self.lookback_window:
            return {"regime": "unknown", "confidence": 0.0}
            
        # Use recent price data
        recent_prices = prices[-self.lookback_window:]
        
        # Calculate returns
        returns = np.diff(recent_prices) / recent_prices[:-1]
        
        # Calculate volatility (annualized)
        volatility = np.std(returns) * np.sqrt(365)
        
        # Calculate trend strength
        price_start = recent_prices[0]
        price_end = recent_prices[-1]
        trend = (price_end - price_start) / price_start
        
        # Calculate efficiency ratio (trend strength / volatility)
        path_length = np.sum(np.abs(returns))
        if path_length > 0:
            efficiency = abs(trend) / path_length
        else:
            efficiency = 0
            
        # Detect regime
        if volatility > 0.03:  # High volatility threshold
            if efficiency > 0.6:
                regime = "trending_volatile"
            else:
                regime = "volatile"
        else:  # Lower volatility
            if efficiency > 0.7:
                regime = "trending"
            else:
                regime = "ranging"
                
        # Calculate confidence
        if regime == "trending_volatile":
            confidence = min(1.0, volatility * 10 * efficiency)
        elif regime == "volatile":
            confidence = min(1.0, volatility * 20)
        elif regime == "trending":
            confidence = min(1.0, efficiency * 1.2)
        else:  # ranging
            confidence = min(1.0, (1 - efficiency) * 1.1)
            
        return {
            "regime": regime,
            "trend_direction": 1 if trend > 0 else -1,
            "volatility": float(volatility),
            "efficiency": float(efficiency),
            "confidence": float(confidence)
        }

# Main Strategy Class
class AdaptiveMLMarketMakingStrategy(StrategyPyBase):
    # Strategy parameters
    market_info: MarketTradingPairTuple
    min_spread: Decimal
    max_spread: Decimal
    order_amount: Decimal
    order_refresh_time: float
    max_order_age: float
    
    # Technical indicator parameters
    rsi_length: int = 14
    rsi_overbought: float = 70
    rsi_oversold: float = 30
    ema_short: int = 12
    ema_long: int = 26
    # Bollinger Bands parameters
    bb_length1: int = 120
    bb_length2: int = 12
    bb_ma_type: str = "EMA"
    bb_source: str = "hl2"
    bb_std: float = 2.0
    # VWAP parameters
    vwap_length: int = 1
    vwap_source: str = "close"
    vwap_offset: int = 0
    # Additional BB parameters
    bb_price_data: str = "hl2"
    bb_lookback: int = 24
    bb_show_cross: bool = True
    bb_gain: float = 10000
    bb_use_kalman: bool = True
    
    # Risk management parameters
    max_inventory_ratio: float = 0.5
    min_inventory_ratio: float = 0.3
    volatility_adjustment: float = 1.0
    max_position_value: Decimal = Decimal("inf")
    trailing_stop_pct: Decimal = Decimal("0.02")
    
    # ML Model parameters
    use_ml: bool = True
    ml_data_buffer_size: int = 5000
    ml_update_interval: int = 3600
    ml_confidence_threshold: float = 0.65
    ml_signal_weight: float = 0.35
    ml_model_dir: str = "./models"
    
    def __init__(self,
                 market_info: MarketTradingPairTuple,
                 min_spread: Decimal,
                 max_spread: Decimal,
                 order_amount: Decimal,
                 order_refresh_time: float = 10.0,
                 max_order_age: float = 300.0,
                 rsi_length: int = 14,
                 ema_short: int = 12,
                 ema_long: int = 26,
                 bb_length1: int = 120,
                 bb_length2: int = 12,
                 bb_ma_type: str = "EMA",
                 bb_source: str = "hl2",
                 bb_std: float = 2.0,
                 vwap_length: int = 1,
                 vwap_source: str = "close",
                 vwap_offset: int = 0,
                 bb_price_data: str = "hl2",
                 bb_lookback: int = 24,
                 bb_show_cross: bool = True,
                 bb_gain: float = 10000,
                 bb_use_kalman: bool = True,
                 max_inventory_ratio: float = 0.5,
                 min_inventory_ratio: float = 0.3,
                 volatility_adjustment: float = 1.0,
                 max_position_value: Decimal = Decimal("inf"),
                 trailing_stop_pct: Decimal = Decimal("0.02"),
                 use_ml: bool = True,
                 ml_data_buffer_size: int = 5000,
                 ml_update_interval: int = 3600,
                 ml_confidence_threshold: float = 0.65,
                 ml_signal_weight: float = 0.35,
                 ml_model_dir: str = "./models"):
        
        super().__init__()
        self.market_info = market_info
        self.min_spread = min_spread
        self.max_spread = max_spread
        self.order_amount = order_amount
        self.order_refresh_time = order_refresh_time
        self.max_order_age = max_order_age
        
        # Technical indicator parameters
        self.rsi_length = rsi_length
        self.rsi_overbought = rsi_overbought
        self.rsi_oversold = rsi_oversold
        self.ema_short = ema_short
        self.ema_long = ema_long
        self.bb_length1 = bb_length1
        self.bb_length2 = bb_length2
        self.bb_ma_type = bb_ma_type
        self.bb_source = bb_source
        self.bb_std = bb_std
        self.vwap_length = vwap_length
        self.vwap_source = vwap_source
        self.vwap_offset = vwap_offset
        self.bb_price_data = bb_price_data
        self.bb_lookback = bb_lookback
        self.bb_show_cross = bb_show_cross
        self.bb_gain = bb_gain
        self.bb_use_kalman = bb_use_kalman
        
        # Risk management parameters
        self.max_inventory_ratio = max_inventory_ratio
        self.min_inventory_ratio = min_inventory_ratio
        self.volatility_adjustment = volatility_adjustment
        self.max_position_value = max_position_value
        self.trailing_stop_pct = trailing_stop_pct
        
        # ML Model parameters
        self.use_ml = use_ml and HAS_ML_DEPENDENCIES
        self.ml_data_buffer_size = ml_data_buffer_size
        self.ml_update_interval = ml_update_interval
        self.ml_confidence_threshold = ml_confidence_threshold
        self.ml_signal_weight = ml_signal_weight
        self.ml_model_dir = ml_model_dir
        
        # Internal state variables
        self._last_timestamp = 0
        self._current_orders = {}
        self._last_spread_adjustment = time.time()
        self._indicator_scores = {"rsi": 0, "macd": 0, "ema": 0, "bbands": 0, "volume": 0}
        self._historical_prices = []
        self._historical_volumes = []
        self._trailing_stop_price = None
        
        # Performance tracking
        self._start_base_balance = None
        self._start_quote_balance = None
        self._start_price = None
        self._start_time = time.time()
        self._trade_profit = Decimal("0")
        self._total_fees = Decimal("0")
        self._total_trades = 0
        self._win_trades = 0
        self._loss_trades = 0
        self._trade_values = []
        self._ml_confidence_sum = 0
        
        # ML Model components
        if self.use_ml:
            # Initialize ML components
            self._feature_engineering = FeatureEngineering()
            self._online_trainer = OnlineModelTrainer(
                data_buffer_size=self.ml_data_buffer_size,
                update_interval=self.ml_update_interval,
                models_dir=self.ml_model_dir,
                feature_engineering=self._feature_engineering
            )
            self._market_regime_detector = MarketRegimeDetector(lookback_window=100)
            self._ml_prediction = {"signal": 0, "confidence": 0.5, "raw_prediction": 0.5}
            self._market_regime = {"regime": "unknown", "confidence": 0.0, "trend_direction": 0}
        
        # Register event listeners
        self.add_markets([market_info.market])
        
        self.logger().info("Adaptive ML Market Making strategy initialized.")
        if self.use_ml:
            self.logger().info(f"ML components initialized with model directory: {self.ml_model_dir}")
            os.makedirs(self.ml_model_dir, exist_ok=True)
        elif use_ml:
            self.logger().warning("ML dependencies not available - running without ML features")

    async def calculate_indicators(self):
        # Get historical data
        candles = await self.market_info.market.get_candles(
            trading_pair=self.market_info.trading_pair,
            interval="1h",
            limit=max(150, self.bb_length1 + self.bb_lookback + 10)
        )
        
        if len(candles) < self.bb_length1 + 10:
            return
        
        # Extract price and volume data
        close_prices = np.array([float(candle.close) for candle in candles])
        high_prices = np.array([float(candle.high) for candle in candles])
        low_prices = np.array([float(candle.low) for candle in candles])
        volumes = np.array([float(candle.volume) for candle in candles])
        open_prices = np.array([float(candle.open) for candle in candles])
        timestamps = np.array([candle.timestamp for candle in candles])
        
        # Calculate price data based on source
        if self.bb_source == "hl2":
            price_data = (high_prices + low_prices) / 2
        elif self.bb_source == "hlc3":
            price_data = (high_prices + low_prices + close_prices) / 3
        elif self.bb_source == "ohlc4":
            price_data = (open_prices + high_prices + low_prices + close_prices) / 4
        else:  # Default to close
            price_data = close_prices
        
        # Store historical data
        self._historical_prices = close_prices
        self._historical_volumes = volumes
        
        # Calculate RSI
        rsi = self.calculate_rsi(close_prices, self.rsi_length)
        
        # Calculate MACD
        macd, signal, hist = self.calculate_macd(close_prices, self.ema_short, self.ema_long)
        
        # Calculate EMA
        ema50 = self.calculate_ema(close_prices, 50)
        
        # Calculate Bollinger Bands
        upper, middle, lower, crossover, crossunder = self.calculate_bollinger_bands_enhanced(
            price_data, high_prices, low_prices, close_prices, volumes
        )
        
        # Check volume spike
        avg_volume = np.mean(volumes[-20:])
        latest_volume = volumes[-1]
        volume_spike = latest_volume > (2 * avg_volume)
        
        # Calculate indicator scores
        if rsi[-1] < self.rsi_oversold:
            self._indicator_scores["rsi"] = 20  # Oversold condition, bullish
        elif rsi[-1] > self.rsi_overbought:
            self._indicator_scores["rsi"] = -20  # Overbought condition, bearish
        else:
            self._indicator_scores["rsi"] = 0
        
        if macd[-1] > signal[-1] and macd[-2] <= signal[-2]:
            self._indicator_scores["macd"] = 25  # Bullish crossover
        elif macd[-1] < signal[-1] and macd[-2] >= signal[-2]:
            self._indicator_scores["macd"] = -25  # Bearish crossover
        else:
            self._indicator_scores["macd"] = 0
        
        if close_prices[-1] > ema50[-1] and close_prices[-2] <= ema50[-2]:
            self._indicator_scores["ema"] = 15  # Bullish EMA break
        elif close_prices[-1] < ema50[-1] and close_prices[-2] >= ema50[-2]:
            self._indicator_scores["ema"] = -15  # Bearish EMA break
        else:
            self._indicator_scores["ema"] = 0
        
        # Check for Bollinger Band squeeze and breakout
        bb_width = (upper[-1] - lower[-1]) / middle[-1]
        bb_width_prev = (upper[-10] - lower[-10]) / middle[-10]
        
        if bb_width < 0.1 and bb_width_prev > 0.2:
            self._indicator_scores["bbands"] = 15  # Squeeze identified, potential breakout
        elif close_prices[-1] > upper[-1]:
            self._indicator_scores["bbands"] = -15  # Upper band rejection, bearish
        elif close_prices[-1] < lower[-1]:
            self._indicator_scores["bbands"] = 15  # Lower band support, bullish
        else:
            self._indicator_scores["bbands"] = 0
            
        # Add scoring for BB crossovers
        if self.bb_show_cross:
            # Find the most recent crossover/crossunder in the last 5 bars
            recent_crossover = np.any(crossover[-5:])
            recent_crossunder = np.any(crossunder[-5:])
            
            if recent_crossover:
                self._indicator_scores["bbands"] -= 20  # Price crossing above upper band is bearish
            elif recent_crossunder:
                self._indicator_scores["bbands"] += 20  # Price crossing below lower band is bullish
                
        # Track BB states for strategy decisions
        self._bb_state = {
            "upper": upper[-1],
            "middle": middle[-1],
            "lower": lower[-1],
            "width": bb_width,
            "crossover": np.any(crossover[-3:]),
            "crossunder": np.any(crossunder[-3:])
        }
        
        if volume_spike:
            self._indicator_scores["volume"] = 20 if close_prices[-1] > close_prices[-2] else -20
        else:
            self._indicator_scores["volume"] = 0
            
        # ML Model integration
        if self.use_ml and len(candles) > 0:
            # Prepare data for ML model
            latest_candle = candles[-1]
            
            # Create a dictionary with OHLCV data
            candle_data = {
                "timestamp": latest_candle.timestamp,
                "open": float(latest_candle.open),
                "high": float(latest_candle.high),
                "low": float(latest_candle.low),
                "close": float(latest_candle.close),
                "volume": float(latest_candle.volume),
                "date": datetime.datetime.fromtimestamp(latest_candle.timestamp / 1000.0)
            }
            
            # Add data to ML model buffer
            self._online_trainer.add_data_point(candle_data)
            
            # Detect market regime
            self._market_regime = self._market_regime_detector.detect_regime(close_prices)
            
            # Get ML prediction
            if len(self._online_trainer.data_buffer) >= 100:
                self._ml_prediction = self._online_trainer.get_prediction(candle_data)
                
                # Log ML prediction
                self.logger().info(f"ML Prediction: Signal={self._ml_prediction['signal']}, "
                                   f"Confidence={self._ml_prediction['confidence']:.4f}, "
                                   f"Market Regime={self._market_regime['regime']}, "
                                   f"Regime Confidence={self._market_regime['confidence']:.4f}")
                
                # Adjust indicator scores based on ML prediction
                if self._ml_prediction["confidence"] >= self.ml_confidence_threshold:
                    ml_impact = int(30 * self._ml_prediction["confidence"] * self._ml_prediction["signal"])
                    self._indicator_scores["ml"] = ml_impact
                else:
                    self._indicator_scores["ml"] = 0
    
    def calculate_rsi(self, prices, length):
        deltas = np.diff(prices)
        seed = deltas[:length+1]
        up = seed[seed >= 0]
        down = -seed[seed < 0]
        up_sum = np.sum(up)
        down_sum = np.sum(down)
        rs = up_sum / down_sum if down_sum > 0 else 0
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def calculate_macd(self, prices, short_period, long_period):
        short_ema = self.calculate_ema(prices, short_period)
        long_ema = self.calculate_ema(prices, long_period)
        macd = short_ema - long_ema
        signal = self.calculate_ema(macd, 9)
        hist = macd - signal
        return macd, signal, hist

    def calculate_ema(self, prices, period):
        ema = np.zeros_like(prices)
        alpha = 2 / (period + 1)
        ema[period-1] = np.mean(prices[:period])
        for t in range(period, len(prices)):
            ema[t] = prices[t] * alpha + ema[t-1] * (1 - alpha)
        return ema

    def calculate_bollinger_bands_enhanced(self, prices, high, low, close, volumes):
        typical_price = (high + low + close) / 3
        sma = self.calculate_ema(typical_price, 20)
        std = np.std(typical_price - sma)
        upper = sma + 2 * std
        middle = sma
        lower = sma - 2 * std
        return upper, middle, lower, np.where(typical_price > upper, 1, 0), np.where(typical_price < lower, 1, 0)
    def calculate_rsi(self, prices, length):
        deltas = np.diff(prices)
        seed = deltas[:length+1]
        up = seed[seed >= 0].sum()/length
        down = -seed[seed < 0].sum()/length
        rs = up/down if down != 0 else 0
        rsi = np.zeros_like(prices)
        rsi[:length] = 100. - 100./(1. + rs)
        
        for i in range(length, len(prices)):
            delta = deltas[i-1]
            if delta > 0:
                upval = delta
                downval = 0
            else:
                upval = 0
                downval = -delta
                
            up = (up * (length - 1) + upval) / length
            down = (down * (length - 1) + downval) / length
            rs = up/down if down != 0 else 0
            rsi[i] = 100. - 100./(1. + rs)
        return rsi
    
    def calculate_macd(self, prices, fast_length, slow_length, signal_length=9):
        # Calculate EMAs
        fast_ema = self.calculate_ema(prices, fast_length)
        slow_ema = self.calculate_ema(prices, slow_length)
        
        # Calculate MACD line
        macd_line = fast_ema - slow_ema
        
        # Calculate signal line
        signal_line = self.calculate_ema(macd_line, signal_length)
        
        # Calculate histogram
        histogram = macd_line - signal_line
        
        return macd_line, signal_line, histogram
    
    def calculate_ema(self, prices, length):
        ema = np.zeros_like(prices)
        ema[0] = prices[0]
        
        multiplier = 2 / (length + 1)
        
        for i in range(1, len(prices)):
            ema[i] = prices[i] * multiplier + ema[i-1] * (1 - multiplier)
            
        return ema
    
    def calculate_atr(self, prices, length=14):
        if len(prices) < length + 1:
            return 0
            
        high_prices = np.array(prices)
        low_prices = np.array(prices)
        close_prices = np.array(prices)
        
        # True range
        tr1 = np.abs(high_prices[1:] - low_prices[1:])
        tr2 = np.abs(high_prices[1:] - close_prices[:-1])
        tr3 = np.abs(low_prices[1:] - close_prices[:-1])
        
        true_range = np.maximum(np.maximum(tr1, tr2), tr3)
        
        # Average true range
        atr = np.zeros(len(prices))
        atr[:length] = np.NaN
        atr[length] = np.mean(true_range[:length])
        
        for i in range(length+1, len(prices)):
            atr[i] = (atr[i-1] * (length-1) + true_range[i-1]) / length
            
        return atr
    
    def calculate_bollinger_bands_enhanced(self, price_data, high_prices, low_prices, close_prices, volumes):
        # Calculate standard Bollinger Bands
        length = self.bb_length1
        ma = np.zeros_like(price_data)
        stddev = np.zeros_like(price_data)
        
        for i in range(length-1, len(price_data)):
            ma[i] = np.mean(price_data[i-length+1:i+1])
            stddev[i] = np.std(price_data[i-length+1:i+1])
            
        upper_band = ma + self.bb_std * stddev
        lower_band = ma - self.bb_std * stddev
        
        # Calculate crossovers
        crossover = np.zeros_like(price_data, dtype=bool)
        crossunder = np.zeros_like(price_data, dtype=bool)
        
        for i in range(1, len(price_data)):
            if close_prices[i] > upper_band[i] and close_prices[i-1] <= upper_band[i-1]:
                crossover[i] = True
            if close_prices[i] < lower_band[i] and close_prices[i-1] >= lower_band[i-1]:
                crossunder[i] = True
                
        return upper_band, ma, lower_band, crossover, crossunder
    
    def calculate_inventory_ratio(self):
        """Calculate current inventory ratio"""
        base_balance = self.market_info.base_balance
        quote_balance = self.market_info.quote_balance
        mid_price = self.market_info.get_mid_price()
        
        total_in_quote = base_balance * mid_price + quote_balance
        base_in_quote = base_balance * mid_price
        
        inventory_ratio = base_in_quote / total_in_quote if total_in_quote > 0 else 0
        return float(inventory_ratio)
    
    def calculate_adaptive_spread(self):
        # Calculate total score
        total_score = sum(self._indicator_scores.values())
        
        # Base spread (within min/max bounds)
        base_spread = (self.max_spread + self.min_spread) / 2
        
        # Get volatility adjustment
        atr = self.calculate_atr(self._historical_prices, 14)
        current_price = self._historical_prices[-1] if len(self._historical_prices) > 0 else Decimal("0")
        normalized_atr = atr / current_price if current_price > 0 else 0
        
        # Increase spread in volatile markets
        volatility_component = normalized_atr * self.volatility_adjustment * 50
        
        # Inventory adjustment
        inventory_ratio = self.calculate_inventory_ratio()
        inventory_factor = 0
        
        if inventory_ratio > self.max_inventory_ratio:
            # Too much base asset, prioritize selling
            inventory_factor = (inventory_ratio - self.max_inventory_ratio) * 3
        elif inventory_ratio < self.min_inventory_ratio:
            # Too little base asset, prioritize buying
            inventory_factor = (self.min_inventory_ratio - inventory_ratio) * -3
            
        # ML model adjustments
        ml_adjustment = 0
        if self.use_ml and "ml" in self._indicator_scores:
            # Get ML signal impact
            ml_adjustment = self._indicator_scores["ml"] / 200
            
            # Factor in market regime detection
            if self._market_regime["regime"] == "trending" and self._market_regime["confidence"] > 0.6:
                # In trending markets, tighten spread to follow trend
                trend_direction = self._market_regime["trend_direction"]
                if trend_direction > 0:  # Uptrend
                    # Decrease buy spread, increase sell spread for uptrends
                    ml_adjustment -= 0.05 * self._market_regime["confidence"]
                else:  # Downtrend
                    # Increase buy spread, decrease sell spread for downtrends
                    ml_adjustment += 0.05 * self._market_regime["confidence"]
            
            elif self._market_regime["regime"] == "volatile" and self._market_regime["confidence"] > 0.6:
                # In volatile markets, widen spread to reduce risk
                ml_adjustment += 0.1 * self._market_regime["confidence"]
            
            elif self._market_regime["regime"] == "ranging" and self._market_regime["confidence"] > 0.6:
                # In ranging markets, tighten spread to capture small movements
                ml_adjustment -= 0.03 * self._market_regime["confidence"]
                
        # Combine all factors with weights (total score has highest weight)
        total_adjustment = (
            (total_score / 250) * 0.5 +  # Technical indicators (50%)
            volatility_component * 0.2 +  # Volatility (20%)
            inventory_factor * 0.15 +     # Inventory management (15%)
            ml_adjustment * self.ml_signal_weight  # ML predictions (set by ml_signal_weight parameter)
        )
        
        # Adjust base spread
        adjusted_spread = base_spread * (1 + total_adjustment)
        
        # Ensure within min/max bounds
        adjusted_spread = max(self.min_spread, min(self.max_spread, adjusted_spread))
        
        return Decimal(str(adjusted_spread))
    
    def calculate_order_amount(self):
        """Calculate order amounts for buy and sell orders with dynamic position sizing based on indicators and ML predictions"""
        
        # Get base amount (default)
        base_amount = self.order_amount
        
        # Get indicator score
        total_score = sum(self._indicator_scores.values())
        
        # Get inventory ratio
        inventory_ratio = self.calculate_inventory_ratio()
        target_ratio = (self.max_inventory_ratio + self.min_inventory_ratio) / 2
        
        # Adjust buy and sell amounts based on inventory
        buy_adjustment = 1.0
        sell_adjustment = 1.0
        
        # If we have too much inventory, reduce buy orders
        if inventory_ratio > self.max_inventory_ratio:
            buy_adjustment = max(0.2, 1 - (inventory_ratio - self.max_inventory_ratio) * 3)
            sell_adjustment = min(2.0, 1 + (inventory_ratio - target_ratio) * 2)
        # If we have too little inventory, reduce sell orders
        elif inventory_ratio < self.min_inventory_ratio:
            sell_adjustment = max(0.2, 1 - (self.min_inventory_ratio - inventory_ratio) * 3)
            buy_adjustment = min(2.0, 1 + (target_ratio - inventory_ratio) * 2)
            
        # Calculate position size based on market conditions
        if total_score > 50:  # Strong bullish
            condition_adjustment_buy = 1.25
            condition_adjustment_sell = 0.80
        elif total_score < -50:  # Strong bearish
            condition_adjustment_buy = 0.80
            condition_adjustment_sell = 1.25
        else:
            condition_adjustment_buy = 1.0 + (total_score / 200)
            condition_adjustment_sell = 1.0 - (total_score / 200)
            
        # ML model adjustments for order sizing
        ml_buy_adjustment = 1.0
        ml_sell_adjustment = 1.0
        
        if self.use_ml and hasattr(self, "_ml_prediction"):
            # Only apply ML adjustments if confidence is high enough
            if self._ml_prediction["confidence"] >= self.ml_confidence_threshold:
                # Adjust based on ML signal and confidence
                if self._ml_prediction["signal"] > 0:  # Bullish
                    ml_factor = self._ml_prediction["confidence"] * self.ml_signal_weight * 2
                    ml_buy_adjustment = 1.0 + ml_factor
                    ml_sell_adjustment = 1.0 - (ml_factor / 2)
                elif self._ml_prediction["signal"] < 0:  # Bearish
                    ml_factor = self._ml_prediction["confidence"] * self.ml_signal_weight * 2
                    ml_buy_adjustment = 1.0 - (ml_factor / 2)
                    ml_sell_adjustment = 1.0 + ml_factor
                    
            # Additional adjustment based on market regime
            if hasattr(self, "_market_regime") and self._market_regime["confidence"] > 0.5:
                regime = self._market_regime["regime"]
                
                if regime == "volatile":
                    # In volatile markets, reduce position sizes
                    vol_factor = self._market_regime["confidence"] * 0.4
                    ml_buy_adjustment *= (1.0 - vol_factor)
                    ml_sell_adjustment *= (1.0 - vol_factor)
                elif regime == "trending" and self._market_regime["trend_direction"] != 0:
                    # In trending markets, increase size in trend direction
                    trend_factor = self._market_regime["confidence"] * 0.3
                    if self._market_regime["trend_direction"] > 0:  # Uptrend
                        ml_buy_adjustment *= (1.0 + trend_factor)
                    else:  # Downtrend
                        ml_sell_adjustment *= (1.0 + trend_factor)
                        
        # Combine all adjustments
        final_buy_adjustment = buy_adjustment * condition_adjustment_buy * ml_buy_adjustment
        final_sell_adjustment = sell_adjustment * condition_adjustment_sell * ml_sell_adjustment
        
        # Ensure adjustments are within reasonable limits (20% to 200% of base)
        final_buy_adjustment = max(0.2, min(2.0, final_buy_adjustment))
        final_sell_adjustment = max(0.2, min(2.0, final_sell_adjustment))
        
        # Apply adjustments to base amount
        buy_amount = base_amount * Decimal(str(final_buy_adjustment))
        sell_amount = base_amount * Decimal(str(final_sell_adjustment))
        
        # Log adjustments if they're significant
        if abs(final_buy_adjustment - 1.0) > 0.1 or abs(final_sell_adjustment - 1.0) > 0.1:
            self.logger().info(f"Order size adjustments: buy={final_buy_adjustment:.2f}, sell={final_sell_adjustment:.2f}")
            if self.use_ml and hasattr(self, "_ml_prediction") and self._ml_prediction["confidence"] >= self.ml_confidence_threshold:
                self.logger().info(f"ML impact: signal={self._ml_prediction['signal']}, confidence={self._ml_prediction['confidence']:.2f}")
        
        return buy_amount, sell_amount
    
    def check_and_update_trailing_stop(self):
        """Check and update trailing stop price for risk management"""
        if not self._historical_prices or len(self._historical_prices) < 2:
            return False
            
        current_price = self._historical_prices[-1]
        
        # Initialize trailing stop price if not set
        if self._trailing_stop_price is None:
            self._trailing_stop_price = current_price * (1 - self.trailing_stop_pct)
            return False
            
        # Check if price hit the trailing stop
        if current_price <= self._trailing_stop_price:
            self.logger().warning(f"Trailing stop triggered at price {current_price} (stop price: {self._trailing_stop_price})")
            return True
            
        # Update trailing stop price if price moves up
        if current_price > self._trailing_stop_price / (1 - self.trailing_stop_pct):
            self._trailing_stop_price = current_price * (1 - self.trailing_stop_pct)
            
        return False
    
    def update_strategy_params_based_on_market_conditions(self):
        # Calculate total indicator score
        total_score = sum(self._indicator_scores.values())
        
        # Use market regime detection from ML model if available
        market_regime = None
        regime_confidence = 0.0
        
        if self.use_ml and hasattr(self, "_market_regime"):
            market_regime = self._market_regime.get("regime")
            regime_confidence = self._market_regime.get("confidence", 0.0)
            trend_direction = self._market_regime.get("trend_direction", 0)
            
            if regime_confidence > 0.6:
                self.logger().info(f"Adjusting strategy based on ML market regime: {market_regime} "
                                 f"(confidence: {regime_confidence:.4f}, trend: {trend_direction})")
                
                # Adjust parameters based on market regime
                if market_regime == "trending":
                    # In trending markets, use tighter spreads to capture trend movement
                    self.min_spread = Decimal("0.0015")  # 0.15%
                    self.max_spread = Decimal("0.008")   # 0.8%
                    
                    # Update inventory targets based on trend direction
                    if trend_direction > 0:  # Uptrend
                        # Hold more base asset in uptrends
                        self.max_inventory_ratio = 0.7
                        self.min_inventory_ratio = 0.4
                    else:  # Downtrend
                        # Hold less base asset in downtrends
                        self.max_inventory_ratio = 0.4
                        self.min_inventory_ratio = 0.15
                        
                elif market_regime == "ranging":
                    # In ranging markets, use wider spreads to profit from oscillations
                    self.min_spread = Decimal("0.002")   # 0.2%
                    self.max_spread = Decimal("0.012")   # 1.2%
                    
                    # Balanced inventory for range markets
                    self.max_inventory_ratio = 0.6
                    self.min_inventory_ratio = 0.3
                    
                elif market_regime == "volatile" or market_regime == "trending_volatile":
                    # In volatile markets, use wider spreads to account for risk
                    self.min_spread = Decimal("0.004")   # 0.4%
                    self.max_spread = Decimal("0.025")   # 2.5%
                    
                    # Tighter inventory bands to reduce exposure
                    self.max_inventory_ratio = 0.5
                    self.min_inventory_ratio = 0.25
                    
                    # Increase trailing stop percentage in volatile markets
                    self.trailing_stop_pct = Decimal("0.03")  # 3%
                    
                    # If both ML and traditional indicators agree on direction in volatile markets
                    if hasattr(self, "_ml_prediction") and self._ml_prediction["confidence"] > 0.7:
                        ml_signal = self._ml_prediction["signal"]
                        
                        if ml_signal > 0 and total_score > 30:  # Both bullish
                            # More aggressive with strong bullish consensus
                            self.max_inventory_ratio = 0.65
                        elif ml_signal < 0 and total_score < -30:  # Both bearish
                            # More conservative with strong bearish consensus
                            self.max_inventory_ratio = 0.3
                
                # Log parameter adjustments
                self.logger().info(f"Adjusted parameters for {market_regime} regime: "
                                 f"spread=[{self.min_spread}-{self.max_spread}], "
                                 f"inventory=[{self.min_inventory_ratio}-{self.max_inventory_ratio}]")
        else:
            # Fallback to traditional indicator-based adjustments if no ML model
            if hasattr(self, "_bb_state"):
                bb = self._bb_state
                
                # Calculate volatility from band width
                volatility = bb['width']
                
                # Detect trends using crossovers
                if bb['crossover']:
                    bb_signal = -2  # Strong bearish
                elif bb['crossunder']:
                    bb_signal = 2   # Strong bullish
                else:
                    bb_signal = 0
                    
                # Check price position relative to bands
                current_price = self._historical_prices[-1]
                band_position = (current_price - bb['lower']) / (bb['upper'] - bb['lower'])
                
                if band_position > 0.8:  # Near upper band
                    bb_signal -= 1
                elif band_position < 0.2:  # Near lower band
                    bb_signal += 1
                    
                # Adjust parameters based on volatility
                if volatility > 0.04:  # High volatility
                    self.max_spread = Decimal("0.01")  # Wider spreads to account for volatility
                elif volatility < 0.01:  # Low volatility
                    self.max_spread = Decimal("0.003")  # Tighter spreads for better execution
                else:  # Medium volatility
                    self.max_spread = Decimal("0.005")
    
    def calculate_performance_metrics(self):
        """Calculate performance metrics including ML model contribution"""
        # Check if we have enough data
        if not self._start_base_balance or not self._start_quote_balance or not self._start_price:
            return None
            
        # Get current balances and price
        current_base_balance = self.market_info.base_balance
        current_quote_balance = self.market_info.quote_balance
        current_price = self.market_info.get_mid_price()
        
        # Calculate current portfolio value
        current_base_value_in_quote = current_base_balance * current_price
        current_total_value = current_base_value_in_quote + current_quote_balance
        
        # Calculate initial portfolio value
        initial_base_value_in_quote = self._start_base_balance * self._start_price
        initial_total_value = initial_base_value_in_quote + self._start_quote_balance
        
        # Calculate profit/loss
        total_profit = current_total_value - initial_total_value
        profit_percent = (total_profit / initial_total_value) * 100 if initial_total_value > 0 else 0
        
        # Calculate HODL comparison
        hodl_base_value = self._start_base_balance * current_price
        hodl_total_value = hodl_base_value + self._start_quote_balance
        hodl_profit = hodl_total_value - initial_total_value
        hodl_profit_percent = (hodl_profit / initial_total_value) * 100 if initial_total_value > 0 else 0
        
        # Calculate alpha (excess return over HODL)
        alpha = profit_percent - hodl_profit_percent
        
        # Calculate win rate
        win_rate = (self._win_trades / self._total_trades) * 100 if self._total_trades > 0 else 0
        
        # Calculate average profit per trade
        avg_profit_per_trade = self._trade_profit / self._total_trades if self._total_trades > 0 else 0
        
        # Calculate running time
        running_time = time.time() - self._start_time
        hours, remainder = divmod(int(running_time), 3600)
        minutes, seconds = divmod(remainder, 60)
        running_time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
        # Calculate Sharpe ratio approximation (if enough trades)
        sharpe_ratio = 0
        if len(self._trade_values) > 10:
            returns = np.diff(self._trade_values) / self._trade_values[:-1]
            sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(365) if np.std(returns) > 0 else 0
            
        # ML model contribution metrics
        ml_contribution = None
        if self.use_ml and hasattr(self, "_ml_prediction") and self._total_trades > 0:
            total_ml_influence_trades = sum(1 for trade_id, order in self._current_orders.items() 
                                         if hasattr(order, "metadata") and 
                                         order.metadata.get("ml_influence", False))
            
            ml_contribution = {
                "ml_trades": total_ml_influence_trades,
                "ml_trade_percent": (total_ml_influence_trades / self._total_trades) * 100,
                "ml_confidence_avg": getattr(self, "_ml_confidence_sum", 0) / total_ml_influence_trades
                                     if total_ml_influence_trades > 0 else 0
            }
        
        return {
            "total_profit": total_profit,
            "profit_percent": profit_percent,
            "hodl_profit": hodl_profit,
            "hodl_profit_percent": hodl_profit_percent,
            "alpha": alpha,
            "win_rate": win_rate,
            "avg_profit_per_trade": avg_profit_per_trade,
            "total_trades": self._total_trades,
            "win_trades": self._win_trades,
            "loss_trades": self._loss_trades,
            "total_fees": self._total_fees,
            "running_time": running_time_str,
            "sharpe_ratio": sharpe_ratio,
            "ml_contribution": ml_contribution
        }
    
    async def format_status(self) -> str:
        """Format status message with enhanced info including ML model metrics"""
        if not self._ready_to_trade:
            return "Market connectors are not ready."
            
        lines = []
        mid_price = self.market_info.get_mid_price()
        spread = self.calculate_adaptive_spread()
        
        # Assets and balance info
        base_asset = self.market_info.base_asset
        quote_asset = self.market_info.quote_asset
        base_balance = self.market_info.base_balance
        quote_balance = self.market_info.quote_balance
            
        # Format status message
        lines.extend([
            f"Exchange: {self.market_info.market.display_name}",
            f"Market: {base_asset}-{quote_asset}",
            f"Mid price: {mid_price:.8f}",
            f"Spread: {spread:.6f} | Min: {self.min_spread:.6f} | Max: {self.max_spread:.6f}",
            f"Inventory ratio: {self.calculate_inventory_ratio():.4f}",
            f"Base balance: {base_balance:.6f} {base_asset}",
            f"Quote balance: {quote_balance:.6f} {quote_asset}",
        ])
        
        # Technical indicator scores
        indicator_lines = [
            "\nTechnical Indicators:",
            f"RSI: {self._indicator_scores['rsi']} | MACD: {self._indicator_scores['macd']}",
            f"EMA: {self._indicator_scores['ema']} | BBands: {self._indicator_scores['bbands']}",
            f"Volume: {self._indicator_scores['volume']} | Total: {sum(self._indicator_scores.values())}"
        ]
        lines.extend(indicator_lines)
        
        # ML model information
        if self.use_ml:
            ml_lines = [
                "\nML Model Metrics:",
                f"Model Dir: {self.ml_model_dir}",
                f"Data Points: {len(self._online_trainer.data_buffer) if hasattr(self, '_online_trainer') else 0}",
                f"Signal: {self._ml_prediction['signal'] if hasattr(self, '_ml_prediction') else 'N/A'}",
                f"Confidence: {self._ml_prediction['confidence']:.4f if hasattr(self, '_ml_prediction') else 'N/A'}",
                f"Market Regime: {self._market_regime['regime'] if hasattr(self, '_market_regime') else 'unknown'}",
                f"Regime Confidence: {self._market_regime['confidence']:.4f if hasattr(self, '_market_regime') else 'N/A'}"
            ]
            lines.extend(ml_lines)
        
        # Active orders
        active_orders = len(self._current_orders)
        if active_orders > 0:
            lines.append("\nActive Orders:")
            for order_id, order in self._current_orders.items():
                order_type = "Buy" if order.is_buy else "Sell"
                age = int(time.time() - order.timestamp / 1000)
                lines.append(f"{order_type} {order.quantity} @ {order.price:.8f} | Age: {age}s")
                
        # Performance metrics
        performance_metrics = self.calculate_performance_metrics()
        if performance_metrics:
            lines.extend([
                "\nPerformance Metrics:",
                f"Total profit: {performance_metrics['total_profit']:.6f} {quote_asset}",
                f"Profit %: {performance_metrics['profit_percent']:.2f}%",
                f"Win rate: {performance_metrics['win_rate']:.2f}%",
                f"Total trades: {performance_metrics['total_trades']}",
                f"Total fees: {performance_metrics['total_fees']:.6f} {quote_asset}",
                f"Running time: {performance_metrics['running_time']}"
            ])
            
        return "\n".join(lines)
    
    async def create_orders(self):
        # Calculate current market parameters
        mid_price = self.market_info.get_mid_price()
        spread = self.calculate_adaptive_spread()
        buy_amount, sell_amount = self.calculate_order_amount()
        
        # Calculate order prices
        buy_price = mid_price * (Decimal("1") - spread)
        sell_price = mid_price * (Decimal("1") + spread)
        
        # Check trailing stop
        stop_triggered = self.check_and_update_trailing_stop()
        
        # Adjust orders based on Bollinger Bands
        if hasattr(self, "_bb_state"):
            bb = self._bb_state
            current_price = Decimal(str(self._historical_prices[-1]))
            bb_upper = Decimal(str(bb['upper']))
            bb_lower = Decimal(str(bb['lower']))
            bb_middle = Decimal(str(bb['middle']))
            
            # Adjust buy price based on lower band
            if current_price < bb_lower * Decimal("1.01"):  # Price near or below lower band
                # More aggressive buy close to lower band
                buy_price = max(current_price * Decimal("0.995"), bb_lower * Decimal("0.99"))
                # Increase buy amount on strong signals
                if bb['crossunder']:
                    buy_amount = buy_amount * Decimal("1.5")
                    self.logger().info(f"Increasing buy amount due to BB lower band crossunder")
            
            # Adjust sell price based on upper band
            if current_price > bb_upper * Decimal("0.99"):  # Price near or above upper band
                # More aggressive sell close to upper band
                sell_price = min(current_price * Decimal("1.005"), bb_upper * Decimal("1.01"))
                # Increase sell amount on strong signals
                if bb['crossover']:
                    sell_amount = sell_amount * Decimal("1.5")
                    self.logger().info(f"Increasing sell amount due to BB upper band crossover")
        
        # Further adjustments based on ML model predictions
        ml_influence = False
        if self.use_ml and hasattr(self, "_ml_prediction") and self._ml_prediction["confidence"] >= self.ml_confidence_threshold:
            ml_signal = self._ml_prediction["signal"]
            ml_confidence = self._ml_prediction["confidence"]
            
            self.logger().info(f"Applying ML adjustments: Signal={ml_signal}, Confidence={ml_confidence:.4f}")
            
            # Mark that ML influenced this order
            ml_influence = True
            
            # Adjust order prices based on ML predictions
            if ml_signal > 0:  # Bullish prediction
                # Make buy more aggressive, sell less aggressive
                buy_price = buy_price * Decimal(str(1 + 0.05 * ml_confidence))  # Increase buy price to improve fill likelihood
                buy_amount = buy_amount * Decimal(str(1 + 0.2 * ml_confidence))  # Increase buy size
                
                # For sell orders, either increase price or do nothing depending on confidence
                if ml_confidence > 0.8:  # Very high confidence
                    sell_price = sell_price * Decimal(str(1 + 0.03 * ml_confidence))  # Still place sells but at higher prices
                
            elif ml_signal < 0:  # Bearish prediction
                # Make sell more aggressive, buy less aggressive
                sell_price = sell_price * Decimal(str(1 - 0.05 * ml_confidence))  # Decrease sell price to improve fill likelihood
                sell_amount = sell_amount * Decimal(str(1 + 0.2 * ml_confidence))  # Increase sell size
                
                # For buy orders, either decrease price or do nothing depending on confidence
                if ml_confidence > 0.8:  # Very high confidence
                    buy_price = buy_price * Decimal(str(1 - 0.03 * ml_confidence))  # Still place buys but at lower prices
            
            # Additional adjustments based on market regime
            if hasattr(self, "_market_regime") and self._market_regime["confidence"] > 0.6:
                regime = self._market_regime["regime"]
                
                if regime == "trending_volatile":
                    # In trending volatile markets, be more aggressive in the trend direction
                    trend_direction = self._market_regime["trend_direction"]
                    if trend_direction > 0 and ml_signal > 0:  # Strong uptrend signal
                        buy_amount = buy_amount * Decimal("1.2")
                        buy_price = buy_price * Decimal("1.01")  # More aggressive on buy side
                    elif trend_direction < 0 and ml_signal < 0:  # Strong downtrend signal
                        sell_amount = sell_amount * Decimal("1.2")
                        sell_price = sell_price * Decimal("0.99")  # More aggressive on sell side
                
                elif regime == "ranging" and self._market_regime["confidence"] > 0.7:
                    # In ranging markets, place orders closer to the bands
                    if hasattr(self, "_bb_state"):
                        bb_width = self._bb_state["width"]
                        if bb_width < 0.03:  # Narrow bands indicating tight range
                            buy_price = max(buy_price, Decimal(str(self._bb_state["lower"] * 1.01)))
                            sell_price = min(sell_price, Decimal(str(self._bb_state["upper"] * 0.99)))
        
        # Apply trailing stop if triggered
        if stop_triggered:
            self.logger().info("Trailing stop triggered - skipping buy orders")
            buy_amount = Decimal("0")
        
        # Clear existing orders before placing new ones
        await self.cancel_all_orders()
        
        # Place orders with metadata
        metadata = {"ml_influence": ml_influence}
        
        # Place buy order if amount is positive
        if buy_amount > Decimal("0"):
            await self.place_order(TradeType.BUY, buy_price, buy_amount, metadata)
            
        # Place sell order if amount is positive
        if sell_amount > Decimal("0"):
            await self.place_order(TradeType.SELL, sell_price, sell_amount, metadata)
    
    async def place_order(self, trade_type, price, amount, metadata=None):
        order_id = self.market_info.market.buy(
            self.market_info.trading_pair,
            amount,
            OrderType.LIMIT,
            price
        ) if trade_type is TradeType.BUY else self.market_info.market.sell(
            self.market_info.trading_pair,
            amount,
            OrderType.LIMIT,
            price
        )
        
        self._current_orders[order_id] = {
            "trade_type": trade_type,
            "price": price,
            "amount": amount,
            "timestamp": time.time(),
            "metadata": metadata
        }
        
        self.logger().info(f"Placed {'buy' if trade_type is TradeType.BUY else 'sell'} order {order_id} "
                         f"for {amount} {self.market_info.base_asset} at {price} {self.market_info.quote_asset}")
    
    async def cancel_all_orders(self):
        for order_id in list(self._current_orders.keys()):
            try:
                await self.market_info.market.cancel(self.market_info.trading_pair, order_id)
                self.logger().info(f"Canceled order {order_id}")
            except Exception as e:
                self.logger().error(f"Failed to cancel order {order_id}: {str(e)}")
            
            self._current_orders.pop(order_id, None)
    
    async def tick(self):
        """Tick function called on each clock tick"""
        if not self._ready_to_trade:
            self._ready_to_trade = all(market.ready for market in self._sb_markets)
            if not self._ready_to_trade:
                return
                
            # Initialize performance tracking on first ready tick
            if self._start_base_balance is None:
                self._start_base_balance = self.market_info.base_balance
                self._start_quote_balance = self.market_info.quote_balance
                self._start_price = self.market_info.get_mid_price()
        
        current_tick = time.time()
        
        # Check if it's time to refresh orders
        need_to_refresh = False
        if len(self._current_orders) == 0:
            need_to_refresh = True
        elif current_tick - self._last_timestamp > self.order_refresh_time:
            need_to_refresh = True
            
        # Check for old orders that need to be canceled
        for order_id, order_data in list(self._current_orders.items()):
            if current_tick - order_data["timestamp"] > self.max_order_age:
                self.logger().info(f"Order {order_id} has exceeded max age, refreshing")
                need_to_refresh = True
                break
                
        if need_to_refresh:
            # Calculate indicators
            await self.calculate_indicators()
            
            # Update strategy parameters based on market conditions
            self.update_strategy_params_based_on_market_conditions()
            
            # Create new orders
            await self.create_orders()
            
            # Update timestamp
            self._last_timestamp = current_tick
    
    async def stop(self):
        # Cancel all active orders
        await self.cancel_all_orders()
        
        # Log final performance metrics
        metrics = self.calculate_performance_metrics()
        if metrics:
            self.logger().info("Final performance metrics:")
            for key, value in metrics.items():
                if isinstance(value, dict):
                    self.logger().info(f"{key}:")
                    for subkey, subvalue in value.items():
                        self.logger().info(f"  {subkey}: {subvalue}")
                else:
                    self.logger().info(f"{key}: {value}")