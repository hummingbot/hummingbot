"""
ML Models for Crypto Trading
v2.0.0
"""

import numpy as np
import pandas as pd
import os
import time
import logging
import datetime
from typing import Dict, List, Optional, Union, Tuple, Any
from collections import deque
import joblib

# ML imports with error handling
try:
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras import layers
    from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint
    from tensorflow.keras.regularizers import l1_l2
    import sklearn
    from sklearn.preprocessing import StandardScaler, MinMaxScaler, RobustScaler
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.model_selection import train_test_split, GridSearchCV, TimeSeriesSplit
    import lightgbm as lgb
    import optuna
    import xgboost as xgb
    HAS_ML_DEPENDENCIES = True
except ImportError:
    HAS_ML_DEPENDENCIES = False

# Configure TensorFlow if available
if HAS_ML_DEPENDENCIES:
    try:
        physical_devices = tf.config.list_physical_devices('GPU')
        if physical_devices:
            tf.config.experimental.set_memory_growth(physical_devices[0], True)
    except:
        pass

# Logger for ML models
ml_logger = logging.getLogger("MLModels")

class FeatureEngineering:
    """Feature engineering and data preparation for ML models."""
    
    @staticmethod
    def create_features(df: pd.DataFrame) -> pd.DataFrame:
        """Create features from raw OHLCV data."""
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
        for window in [5, 10, 20, 50, 100]:
            df_feat[f'ma_{window}'] = df_feat['close'].rolling(window=window).mean()
            df_feat[f'ma_ratio_{window}'] = df_feat['close'] / df_feat[f'ma_{window}']
            
            # EMA features
            df_feat[f'ema_{window}'] = df_feat['close'].ewm(span=window, adjust=False).mean()
            df_feat[f'ema_ratio_{window}'] = df_feat['close'] / df_feat[f'ema_{window}']
        
        # Momentum features
        for period in [3, 6, 12, 24, 48]:
            df_feat[f'momentum_{period}'] = df_feat['close'] / df_feat['close'].shift(period) - 1
        
        # Volatility features
        for window in [5, 10, 20, 50]:
            df_feat[f'vol_{window}'] = df_feat['returns'].rolling(window=window).std()
            
        # Mean reversion features
        for window in [5, 10, 20, 50]:
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
        
        # RSI calculation
        delta = df_feat['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df_feat['rsi_14'] = 100 - (100 / (1 + rs))
        
        # MACD calculation
        ema12 = df_feat['close'].ewm(span=12, adjust=False).mean()
        ema26 = df_feat['close'].ewm(span=26, adjust=False).mean()
        df_feat['macd'] = ema12 - ema26
        df_feat['macd_signal'] = df_feat['macd'].ewm(span=9, adjust=False).mean()
        df_feat['macd_hist'] = df_feat['macd'] - df_feat['macd_signal']
        
        # Bollinger Bands
        for window in [20, 50]:
            middle_band = df_feat['close'].rolling(window=window).mean()
            std_dev = df_feat['close'].rolling(window=window).std()
            df_feat[f'bb_upper_{window}'] = middle_band + (2 * std_dev)
            df_feat[f'bb_lower_{window}'] = middle_band - (2 * std_dev)
            df_feat[f'bb_width_{window}'] = (df_feat[f'bb_upper_{window}'] - df_feat[f'bb_lower_{window}']) / middle_band
            df_feat[f'bb_pct_{window}'] = (df_feat['close'] - df_feat[f'bb_lower_{window}']) / (df_feat[f'bb_upper_{window}'] - df_feat[f'bb_lower_{window}'])
        
        # Market regime features
        df_feat['regime_volatility'] = np.where(df_feat['volatility'] > df_feat['volatility'].rolling(window=100).mean(), 1, 0)
        df_feat['regime_trend'] = np.where(df_feat['close'] > df_feat['ma_50'], 1, 0)
        
        # Drop NaN values
        df_feat = df_feat.dropna()
        
        return df_feat

    @staticmethod
    def prepare_ml_data(df_features: pd.DataFrame, target_col: str = 'target_direction',
                       test_size: float = 0.2, sequence_length: int = 10) -> Tuple:
        """Prepare data for machine learning models."""
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

    @staticmethod
    def prepare_latest_data(df: pd.DataFrame, scaler: Any, feature_cols: List[str], 
                          sequence_length: int = 10) -> np.ndarray:
        """Prepare the latest data for prediction."""
        df_features = FeatureEngineering.create_features(df)
        latest_data = df_features[feature_cols].iloc[-sequence_length:].values
        scaled_data = scaler.transform(latest_data)
        return np.array([scaled_data])

class LSTMModel:
    """LSTM model for time series prediction."""
    
    def __init__(self, input_shape, lstm_units=64, dropout_rate=0.2, l1_reg=0.01, l2_reg=0.01):
        self.input_shape = input_shape
        self.lstm_units = lstm_units
        self.dropout_rate = dropout_rate
        self.l1_reg = l1_reg
        self.l2_reg = l2_reg
        self.model = self._build_model()
        
    def _build_model(self):
        """Build the LSTM model architecture."""
        if not HAS_ML_DEPENDENCIES:
            raise ImportError("TensorFlow and Keras are required for LSTM model")
            
        model = keras.Sequential([
            layers.LSTM(self.lstm_units, 
                      return_sequences=True, 
                      input_shape=self.input_shape,
                      kernel_regularizer=l1_l2(l1=self.l1_reg, l2=self.l2_reg)),
            layers.BatchNormalization(),
            layers.Dropout(self.dropout_rate),
            layers.LSTM(self.lstm_units // 2, 
                      return_sequences=False,
                      kernel_regularizer=l1_l2(l1=self.l1_reg, l2=self.l2_reg)),
            layers.BatchNormalization(),
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
        """Train the LSTM model."""
        callbacks = [
            EarlyStopping(
                monitor='val_loss' if X_val is not None else 'loss',
                patience=patience,
                restore_best_weights=True
            )
        ]
        
        if save_path:
            callbacks.append(
                ModelCheckpoint(
                    filepath=save_path,
                    save_best_only=True,
                    monitor='val_loss' if X_val is not None else 'loss'
                )
            )
        
        validation_data = (X_val, y_val) if X_val is not None and y_val is not None else None
            
        history = self.model.fit(
            X_train, y_train,
            batch_size=batch_size,
            epochs=epochs,
            validation_data=validation_data,
            callbacks=callbacks,
            verbose=1
        )
        
        if save_path and not any(isinstance(c, ModelCheckpoint) for c in callbacks):
            self.save(save_path)
            
        return history
    
    def predict(self, X):
        """Make predictions using the LSTM model."""
        return self.model.predict(X)
    
    def save(self, path):
        """Save the model to disk."""
        self.model.save(path)
    
    @classmethod
    def load(cls, path):
        """Load a model from disk."""
        model = keras.models.load_model(path)
        instance = cls(input_shape=model.input_shape[1:])
        instance.model = model
        return instance

class GBMModel:
    """Gradient Boosting Machine model."""
    
    def __init__(self, params=None):
        default_params = {
            'n_estimators': 100,
            'learning_rate': 0.1,
            'max_depth': 5,
            'subsample': 0.8,
            'colsample_bytree': 0.8,
            'objective': 'binary:logistic',
            'eval_metric': 'logloss',
            'random_state': 42
        }
        self.params = params or default_params
        self.model = xgb.XGBClassifier(**self.params)
        
    def train(self, X_train, y_train, X_val=None, y_val=None):
        """Train the GBM model."""
        eval_set = [(X_train, y_train)]
        if X_val is not None and y_val is not None:
            eval_set.append((X_val, y_val))
            
        self.model.fit(
            X_train, y_train,
            eval_set=eval_set,
            early_stopping_rounds=10,
            verbose=1
        )
        return self
    
    def predict(self, X):
        """Make probability predictions using the GBM model."""
        return self.model.predict_proba(X)[:, 1]
    
    def save(self, path):
        """Save the model to disk."""
        joblib.dump(self.model, path)
    
    @classmethod
    def load(cls, path):
        """Load a model from disk."""
        instance = cls()
        instance.model = joblib.load(path)
        return instance

class LGBModel:
    """LightGBM model."""
    
    def __init__(self, params=None):
        default_params = {
            'n_estimators': 100,
            'learning_rate': 0.1,
            'max_depth': 5,
            'num_leaves': 31,
            'subsample': 0.8,
            'colsample_bytree': 0.8,
            'objective': 'binary',
            'metric': 'binary_logloss',
            'random_state': 42
        }
        self.params = params or default_params
        self.model = lgb.LGBMClassifier(**self.params)
        
    def train(self, X_train, y_train, X_val=None, y_val=None):
        """Train the LightGBM model."""
        eval_set = [(X_train, y_train)]
        if X_val is not None and y_val is not None:
            eval_set.append((X_val, y_val))
            
        self.model.fit(
            X_train, y_train,
            eval_set=eval_set,
            early_stopping_rounds=10,
            verbose=1
        )
        return self
    
    def predict(self, X):
        """Make probability predictions using the LightGBM model."""
        return self.model.predict_proba(X)[:, 1]
    
    def save(self, path):
        """Save the model to disk."""
        joblib.dump(self.model, path)
    
    @classmethod
    def load(cls, path):
        """Load a model from disk."""
        instance = cls()
        instance.model = joblib.load(path)
        return instance

class EnsembleModel:
    """Ensemble of multiple models for improved prediction accuracy."""
    
    def __init__(self, models=None):
        self.models = models or []
        self.weights = None
        
    def add_model(self, model, weight=1.0):
        """Add a model to the ensemble."""
        self.models.append(model)
        if self.weights is None:
            self.weights = [weight]
        else:
            self.weights.append(weight)
            # Normalize weights
            self.weights = [w/sum(self.weights) for w in self.weights]
            
    def predict(self, X):
        """Make ensemble predictions."""
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
        """Update model weights based on validation performance."""
        if not self.models:
            return
            
        performances = []
        for model in self.models:
            preds = model.predict(X_val)
            # Use accuracy as a simple performance metric
            acc = np.mean((preds > 0.5).astype(int) == y_val)
            performances.append(acc)
            
        # Set weights proportional to performance
        total_perf = sum(performances)
        self.weights = [p/total_perf for p in performances]
        
        return self.weights

class OnlineModelTrainer:
    """Class for training and updating models online with new data."""
    
    def __init__(self, data_buffer_size=5000, update_interval=3600, 
                models_dir='./models', feature_engineering=None):
        self.data_buffer = deque(maxlen=data_buffer_size)
        self.update_interval = update_interval
        self.last_update_time = 0
        self.models_dir = models_dir
        self.feature_engineering = feature_engineering or FeatureEngineering()
        self.models = {
            'lstm': None,
            'gbm': None,
            'lgb': None
        }
        self.ensemble = EnsembleModel()
        self.scaler = None
        self.feature_cols = []
        
        # Create models directory if it doesn't exist
        os.makedirs(models_dir, exist_ok=True)
    
    def add_data_point(self, candle_data):
        """Add a new data point to the buffer."""
        self.data_buffer.append(candle_data)
        
        # Check if it's time to update models
        current_time = time.time()
        if current_time - self.last_update_time > self.update_interval and len(self.data_buffer) > 100:
            self.update_models()
            self.last_update_time = current_time
    
    def update_models(self):
        """Update all models with the latest data."""
        if not HAS_ML_DEPENDENCIES:
            ml_logger.warning("ML dependencies not available, skipping model update")
            return
            
        try:
            # Convert data buffer to DataFrame
            df = pd.DataFrame(self.data_buffer)
            if len(df) < 100:  # Need enough data for training
                return
                
            # Create features
            df_features = self.feature_engineering.create_features(df)
            
            # Prepare data for ML
            (X_train, X_test, y_train, y_test, 
             X_train_seq, X_test_seq, y_train_seq, y_test_seq, 
             self.scaler, self.feature_cols) = self.feature_engineering.prepare_ml_data(
                df_features, sequence_length=10
            )
            
            # Train LSTM model
            if X_train_seq.shape[0] > 0:
                input_shape = X_train_seq.shape[1:]
                self.models['lstm'] = LSTMModel(input_shape)
                self.models['lstm'].train(
                    X_train_seq, y_train_seq, 
                    X_val=X_test_seq, y_val=y_test_seq,
                    save_path=os.path.join(self.models_dir, 'lstm_model.keras')
                )
            
            # Train GBM model
            self.models['gbm'] = GBMModel()
            self.models['gbm'].train(X_train, y_train, X_val=X_test, y_val=y_test)
            self.models['gbm'].save(os.path.join(self.models_dir, 'gbm_model.joblib'))
            
            # Train LightGBM model
            self.models['lgb'] = LGBModel()
            self.models['lgb'].train(X_train, y_train, X_val=X_test, y_val=y_test)
            self.models['lgb'].save(os.path.join(self.models_dir, 'lgb_model.joblib'))
            
            # Create ensemble
            self.ensemble = EnsembleModel()
            
            # Add LSTM to ensemble if available
            if self.models['lstm'] is not None:
                self.ensemble.add_model(
                    lambda x: self.models['lstm'].predict(
                        np.array([x[-10:]])
                    )[0],
                    weight=0.4
                )
            
            # Add other models to ensemble
            self.ensemble.add_model(
                lambda x: self.models['gbm'].predict(x.reshape(1, -1))[0],
                weight=0.3
            )
            self.ensemble.add_model(
                lambda x: self.models['lgb'].predict(x.reshape(1, -1))[0],
                weight=0.3
            )
            
            # Update weights based on performance
            self.ensemble.update_weights(X_test, y_test)
            
            ml_logger.info("Models successfully updated")
            
        except Exception as e:
            ml_logger.error(f"Error updating models: {str(e)}")
    
    def get_prediction(self, latest_data):
        """Get prediction for the latest data."""
        if not HAS_ML_DEPENDENCIES or not self.models['gbm']:
            return 0.5, 0.0  # Neutral prediction with zero confidence
            
        try:
            # Create features and prepare data
            df = pd.DataFrame(latest_data)
            df_features = self.feature_engineering.create_features(df)
            
            # Get the most recent feature set
            X = df_features[self.feature_cols].iloc[-1].values.reshape(1, -1)
            X_scaled = self.scaler.transform(X)
            
            # Get sequential data for LSTM
            X_seq = np.array([[self.scaler.transform(df_features[self.feature_cols].iloc[-10:].values)]])
            
            # Get predictions from individual models
            lstm_pred = 0.5  # Default neutral
            if self.models['lstm'] is not None:
                lstm_pred = float(self.models['lstm'].predict(X_seq)[0][0])
                
            gbm_pred = float(self.models['gbm'].predict(X_scaled)[0])
            lgb_pred = float(self.models['lgb'].predict(X_scaled)[0])
            
            # Combine predictions
            weights = self.ensemble.weights if self.ensemble.weights else [0.4, 0.3, 0.3]
            
            if self.models['lstm'] is not None:
                ensemble_pred = weights[0] * lstm_pred + weights[1] * gbm_pred + weights[2] * lgb_pred
            else:
                # Only use GBM and LGB if LSTM is not available
                ensemble_pred = (weights[1] * gbm_pred + weights[2] * lgb_pred) / (weights[1] + weights[2])
            
            # Calculate confidence as distance from 0.5
            confidence = abs(ensemble_pred - 0.5) * 2  # Scale to 0-1
            
            return ensemble_pred, confidence
            
        except Exception as e:
            ml_logger.error(f"Error making prediction: {str(e)}")
            return 0.5, 0.0  # Neutral prediction with zero confidence

class MarketRegimeDetector:
    """Detect different market regimes (trending, ranging, volatile)."""
    
    def __init__(self, lookback_window=100):
        self.lookback_window = lookback_window
    
    def detect_regime(self, prices):
        """Detect the current market regime."""
        if len(prices) < self.lookback_window:
            return {
                'regime': 'unknown',
                'volatility': 'normal',
                'trend': 'neutral',
                'confidence': 0.0
            }
            
        # Calculate needed metrics
        returns = np.diff(prices) / prices[:-1]
        log_returns = np.log(prices[1:] / prices[:-1])
        
        # Volatility measurement
        current_volatility = np.std(returns[-20:])
        historical_volatility = np.std(returns[-self.lookback_window:-20])
        volatility_ratio = current_volatility / historical_volatility if historical_volatility > 0 else 1.0
        
        # Trend measurement
        ma_short = np.mean(prices[-20:])
        ma_long = np.mean(prices[-self.lookback_window:])
        trend_strength = (ma_short / ma_long) - 1
        
        # Momentum measurement
        momentum = prices[-1] / prices[-20] - 1
        
        # Mean reversion measurement
        z_score = (prices[-1] - ma_long) / (np.std(prices[-self.lookback_window:]) if np.std(prices[-self.lookback_window:]) > 0 else 1)
        
        # Calculate regime scores
        trend_score = 0.7 * trend_strength + 0.3 * momentum
        range_score = -abs(z_score) * 0.5  # Higher when price is near mean (low z-score)
        volatility_score = np.log(volatility_ratio) if volatility_ratio > 0 else 0
        
        # Determine the regime
        scores = {
            'trending': trend_score,
            'ranging': range_score,
            'volatile': volatility_score
        }
        
        regime = max(scores, key=scores.get)
        confidence = abs(scores[regime]) / (sum(abs(v) for v in scores.values()) if sum(abs(v) for v in scores.values()) > 0 else 1)
        
        # Determine volatility state
        if volatility_ratio > 1.5:
            volatility = 'high'
        elif volatility_ratio < 0.75:
            volatility = 'low'
        else:
            volatility = 'normal'
            
        # Determine trend direction
        if trend_strength > 0.01:
            trend = 'bullish'
        elif trend_strength < -0.01:
            trend = 'bearish'
        else:
            trend = 'neutral'
            
        return {
            'regime': regime,
            'volatility': volatility,
            'trend': trend,
            'confidence': float(confidence),
            'regime_scores': {k: float(v) for k, v in scores.items()},
            'volatility_ratio': float(volatility_ratio),
            'trend_strength': float(trend_strength),
            'z_score': float(z_score)
        } 