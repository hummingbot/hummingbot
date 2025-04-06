"""
Feature Engineering Module

This module contains the FeatureEngineering class for preparing data for machine learning models.
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple


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
        
        # Target variables for prediction
        df_feat['target_next_return'] = df_feat['returns'].shift(-1)
        df_feat['target_direction'] = np.where(df_feat['target_next_return'] > 0, 1, 0)
        
        # Drop NaN values
        df_feat = df_feat.dropna()
        
        return df_feat
    
    @staticmethod
    def create_multi_timeframe_features(
        dfs: Dict[str, pd.DataFrame],
        timeframe_weights: Dict[str, float]
    ) -> pd.DataFrame:
        """
        Create features from multiple timeframes
        
        Args:
            dfs: Dictionary of DataFrames with OHLCV data for different timeframes
            timeframe_weights: Dictionary of weights for each timeframe
            
        Returns:
            DataFrame with features from multiple timeframes
        """
        # Process each timeframe DataFrame
        processed_dfs = {}
        for tf, df in dfs.items():
            # Create features for this timeframe
            processed_df = FeatureEngineering.create_features(df)
            # Add timeframe as prefix to column names
            processed_df.columns = [f"{tf}_{col}" for col in processed_df.columns]
            processed_dfs[tf] = processed_df
        
        # Combine DataFrames into one
        # Note: This requires aligning timestamps across timeframes, which would
        # need to be implemented according to the specific data structure
        
        # For now, we'll just return the primary timeframe features
        if processed_dfs:
            return list(processed_dfs.values())[0]
        else:
            return pd.DataFrame()
    
    @staticmethod
    def normalize_features(df: pd.DataFrame) -> pd.DataFrame:
        """
        Normalize features to have zero mean and unit variance
        
        Args:
            df: DataFrame with features
            
        Returns:
            DataFrame with normalized features
        """
        # Make a copy to avoid modifying original data
        df_norm = df.copy()
        
        # Separate target variables if present
        target_cols = [col for col in df_norm.columns if 'target' in col]
        feature_cols = [col for col in df_norm.columns if 'target' not in col]
        
        # Normalize feature columns
        for col in feature_cols:
            mean = df_norm[col].mean()
            std = df_norm[col].std()
            if std > 0:
                df_norm[col] = (df_norm[col] - mean) / std
            else:
                df_norm[col] = 0.0
        
        return df_norm
    
    @staticmethod
    def prepare_ml_data(
        df: pd.DataFrame, 
        target_col: str = 'target_direction'
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Prepare data for machine learning
        
        Args:
            df: DataFrame with features and target
            target_col: Name of target column
            
        Returns:
            Tuple of (features array, target array)
        """
        # Check if target column exists
        if target_col not in df.columns:
            raise ValueError(f"Target column '{target_col}' not found in DataFrame")
        
        # Separate features and target
        feature_cols = [col for col in df.columns if col != target_col]
        X = df[feature_cols].values
        y = df[target_col].values
        
        return X, y
    
    @staticmethod
    def create_sequences(
        data: np.ndarray,
        sequence_length: int = 10
    ) -> np.ndarray:
        """
        Create sequences for time series models (e.g., LSTM)
        
        Args:
            data: Input data (features)
            sequence_length: Length of sequences
            
        Returns:
            Array of sequences
        """
        if len(data) < sequence_length:
            raise ValueError(f"Data length ({len(data)}) is less than sequence length ({sequence_length})")
        
        sequences = []
        for i in range(len(data) - sequence_length + 1):
            sequences.append(data[i:i+sequence_length])
        
        return np.array(sequences) 