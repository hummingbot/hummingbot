import numpy as np
import pandas as pd
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
import sklearn
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.model_selection import train_test_split
import lightgbm as lgb
import xgboost as xgb
import joblib
import os
import time
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Tuple, Optional, Union, Any
import random
import optuna
from statsmodels.tsa.statespace.sarimax import SARIMAX
from tensorflow.keras.callbacks import EarlyStopping
from tensorflow.keras.regularizers import l1_l2

# Configure TF to use memory growth
physical_devices = tf.config.list_physical_devices('GPU')
if physical_devices:
    tf.config.experimental.set_memory_growth(physical_devices[0], True)

# Create a logger
logger = logging.getLogger("MLModels")

class FeatureEngineering:
    """Class for feature engineering to prepare data for ML models"""
    
    @staticmethod
    def create_features(df: pd.DataFrame) -> pd.DataFrame:
        """
        Create technical indicators as features
        
        Args:
            df: DataFrame with OHLCV data
            
        Returns:
            DataFrame with added features
        """
        # Make a copy to avoid modifying original data
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
        
        # Drop NaN values created by rolling windows and shifts
        df_feat = df_feat.dropna()
        
        return df_feat

    @staticmethod
    def prepare_ml_data(df_features: pd.DataFrame, 
                       target_col: str = 'target_direction',
                       test_size: float = 0.2,
                       sequence_length: int = 10) -> Tuple:
        """
        Prepare data for ML models including scaling and train/test split
        
        Args:
            df_features: DataFrame with features
            target_col: Target column for prediction
            test_size: Proportion of data for testing
            sequence_length: Length of sequences for LSTM models
            
        Returns:
            Tuple of (X_train, X_test, y_train, y_test, scaler)
        """
        # Select features and target
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
        
        # Adjust target arrays to match sequence data
        y_train_seq = y_train[sequence_length:]
        y_test_seq = y_test[sequence_length:]
        
        return (X_train, X_test, y_train, y_test, 
                X_train_seq, X_test_seq, y_train_seq, y_test_seq, 
                scaler, feature_cols)

class LSTMModel:
    """LSTM model for time series prediction in crypto trading"""
    
    def __init__(self, input_shape, lstm_units=64, dropout_rate=0.2, l1_reg=0.01, l2_reg=0.01):
        """
        Initialize LSTM model
        
        Args:
            input_shape: Shape of input data (sequence_length, n_features)
            lstm_units: Number of LSTM units
            dropout_rate: Dropout rate for regularization
            l1_reg: L1 regularization parameter
            l2_reg: L2 regularization parameter
        """
        self.input_shape = input_shape
        self.lstm_units = lstm_units
        self.dropout_rate = dropout_rate
        self.l1_reg = l1_reg
        self.l2_reg = l2_reg
        self.model = self._build_model()
        
    def _build_model(self):
        """Build and compile the LSTM model"""
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
             batch_size=32, epochs=50, patience=10,
             save_path=None):
        """
        Train the LSTM model
        
        Args:
            X_train: Training data
            y_train: Training labels
            X_val: Validation data (optional)
            y_val: Validation labels (optional)
            batch_size: Batch size for training
            epochs: Maximum number of epochs
            patience: Patience for early stopping
            save_path: Path to save the model (optional)
            
        Returns:
            Training history
        """
        early_stopping = EarlyStopping(
            monitor='val_loss' if X_val is not None else 'loss',
            patience=patience,
            restore_best_weights=True
        )
        
        if X_val is not None and y_val is not None:
            validation_data = (X_val, y_val)
        else:
            validation_data = None
            
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
        """
        Make predictions with the model
        
        Args:
            X: Input data
            
        Returns:
            Predictions
        """
        return self.model.predict(X)
    
    def save(self, path):
        """Save the model to disk"""
        self.model.save(path)
    
    @classmethod
    def load(cls, path):
        """Load a model from disk"""
        model = keras.models.load_model(path)
        instance = cls(input_shape=model.input_shape[1:])
        instance.model = model
        return instance
    
    def tune_hyperparameters(self, X_train, y_train, X_val, y_val, 
                           n_trials=20, timeout=1800):
        """
        Tune hyperparameters using Optuna
        
        Args:
            X_train: Training data
            y_train: Training labels
            X_val: Validation data
            y_val: Validation labels
            n_trials: Number of trials for optimization
            timeout: Timeout in seconds
            
        Returns:
            Best hyperparameters
        """
        def objective(trial):
            # Define hyperparameter search space
            lstm_units = trial.suggest_categorical('lstm_units', [32, 64, 128, 256])
            dropout_rate = trial.suggest_float('dropout_rate', 0.1, 0.5)
            learning_rate = trial.suggest_float('learning_rate', 1e-4, 1e-2, log=True)
            batch_size = trial.suggest_categorical('batch_size', [16, 32, 64, 128])
            l1_reg = trial.suggest_float('l1_reg', 1e-6, 1e-2, log=True)
            l2_reg = trial.suggest_float('l2_reg', 1e-6, 1e-2, log=True)
            
            # Build model with trial hyperparameters
            model = keras.Sequential([
                layers.LSTM(lstm_units, 
                           return_sequences=True, 
                           input_shape=self.input_shape,
                           kernel_regularizer=l1_l2(l1=l1_reg, l2=l2_reg)),
                layers.Dropout(dropout_rate),
                layers.LSTM(lstm_units // 2, 
                           return_sequences=False,
                           kernel_regularizer=l1_l2(l1=l1_reg, l2=l2_reg)),
                layers.Dropout(dropout_rate),
                layers.Dense(32, activation='relu'),
                layers.Dense(1, activation='sigmoid')
            ])
            
            model.compile(
                optimizer=keras.optimizers.Adam(learning_rate=learning_rate),
                loss='binary_crossentropy',
                metrics=['accuracy']
            )
            
            # Train with early stopping
            early_stopping = EarlyStopping(
                monitor='val_loss',
                patience=5,
                restore_best_weights=True
            )
            
            model.fit(
                X_train, y_train,
                batch_size=batch_size,
                epochs=30,
                validation_data=(X_val, y_val),
                callbacks=[early_stopping],
                verbose=0
            )
            
            # Evaluate on validation set
            val_loss, val_accuracy = model.evaluate(X_val, y_val, verbose=0)
            
            return val_accuracy
        
        # Create Optuna study
        study = optuna.create_study(direction='maximize')
        study.optimize(objective, n_trials=n_trials, timeout=timeout)
        
        logger.info(f"Best hyperparameters: {study.best_params}")
        logger.info(f"Best validation accuracy: {study.best_value}")
        
        # Update model with best hyperparameters
        self.lstm_units = study.best_params['lstm_units']
        self.dropout_rate = study.best_params['dropout_rate']
        self.l1_reg = study.best_params['l1_reg']
        self.l2_reg = study.best_params['l2_reg']
        self.model = self._build_model()
        
        return study.best_params
    
class EnsembleModel:
    """Ensemble model combining multiple ML models for more robust predictions"""
    
    def __init__(self, models=None):
        """
        Initialize ensemble model
        
        Args:
            models: List of models to include in the ensemble
        """
        self.models = models or []
        self.weights = None
        
    def add_model(self, model, weight=1.0):
        """
        Add a model to the ensemble
        
        Args:
            model: Model to add
            weight: Weight of the model in the ensemble
        """
        self.models.append(model)
        if self.weights is None:
            self.weights = [weight]
        else:
            self.weights.append(weight)
            # Normalize weights
            self.weights = [w/sum(self.weights) for w in self.weights]
            
    def predict(self, X):
        """
        Make predictions with the ensemble
        
        Args:
            X: Input data
            
        Returns:
            Weighted average of predictions
        """
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
        """
        Update model weights based on validation performance
        
        Args:
            X_val: Validation data
            y_val: Validation labels
        """
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
            
        logger.info(f"Updated ensemble weights: {self.weights}")

class OnlineModelTrainer:
    """
    Handler for continuous online training of ML models during trading
    """
    
    def __init__(self, data_buffer_size=5000, update_interval=3600, 
                models_dir='./models', feature_engineering=None):
        """
        Initialize online trainer
        
        Args:
            data_buffer_size: Maximum size of data buffer
            update_interval: Interval between model updates (seconds)
            models_dir: Directory to save models
            feature_engineering: Feature engineering instance
        """
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
        """
        Add a new data point to the buffer
        
        Args:
            candle_data: Dictionary with OHLCV data
        """
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
        """Update all models with latest data"""
        if len(self.data_buffer) < 100:  # Minimum data needed
            logger.info("Not enough data for model update")
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
                # Initial hyperparameter tuning
                if len(X_train_seq) > 500:  # Only tune with sufficient data
                    self.models['lstm'].tune_hyperparameters(
                        X_train_seq, y_train_seq, 
                        X_test_seq, y_test_seq,
                        n_trials=10, timeout=1200)
            
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
                
            logger.info("Models updated successfully")
            
            # Calculate feature importance from Random Forest
            if hasattr(self.models['rf'], 'feature_importances_'):
                importances = self.models['rf'].feature_importances_
                feature_importance = dict(zip(feature_cols, importances))
                sorted_importance = {k: v for k, v in sorted(
                    feature_importance.items(), key=lambda item: item[1], reverse=True)}
                
                # Log top 10 most important features
                top_features = list(sorted_importance.items())[:10]
                logger.info(f"Top 10 important features: {top_features}")
                
        except Exception as e:
            logger.error(f"Error updating models: {str(e)}")
            
    def get_prediction(self, latest_data):
        """
        Get prediction for latest market data
        
        Args:
            latest_data: Dictionary with latest OHLCV data
            
        Returns:
            Dictionary with prediction results
        """
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
                logger.warning("Scaler not found, cannot make prediction")
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
            logger.error(f"Error making prediction: {str(e)}")
            
        return {"signal": 0, "confidence": 0.5}
    
class MarketRegimeDetector:
    """Detector for market regimes (trending, ranging, volatile)"""
    
    def __init__(self, lookback_window=100):
        """
        Initialize market regime detector
        
        Args:
            lookback_window: Window size for regime detection
        """
        self.lookback_window = lookback_window
        
    def detect_regime(self, prices):
        """
        Detect current market regime
        
        Args:
            prices: Array of price data
            
        Returns:
            Dictionary with regime information
        """
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