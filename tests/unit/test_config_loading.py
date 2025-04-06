#!/usr/bin/env python3
"""
Unit tests for YAML configuration loading
"""
import os
import unittest
import yaml
from decimal import Decimal

class TestConfigLoading(unittest.TestCase):
    """Test cases for strategy_config.yaml loading and parsing"""
    
    def setUp(self):
        """Set up the test case"""
        self.config_path = "config/strategy_config.yaml"
        
    def test_config_file_exists(self):
        """Test that the config file exists"""
        self.assertTrue(os.path.exists(self.config_path), 
                        f"Config file does not exist at {self.config_path}")
    
    def test_config_file_loads(self):
        """Test that the config file can be loaded with yaml"""
        try:
            with open(self.config_path, 'r') as file:
                config = yaml.safe_load(file)
            self.assertIsNotNone(config, "Config should not be None")
        except Exception as e:
            self.fail(f"Loading config file raised exception: {e}")
    
    def test_required_fields_exist(self):
        """Test that required fields exist in the config"""
        with open(self.config_path, 'r') as file:
            config = yaml.safe_load(file)
        
        # Check required fields
        required_fields = [
            "exchange", "trading_pair", "order_refresh_time",
            "order_amount", "min_spread", "max_spread",
            "short_window", "long_window", "rsi_length", 
            "target_inventory_ratio", "candle_intervals"
        ]
        
        for field in required_fields:
            self.assertIn(field, config, f"Required field '{field}' missing in config")
    
    def test_numeric_values_valid(self):
        """Test that numeric values are valid"""
        with open(self.config_path, 'r') as file:
            config = yaml.safe_load(file)
        
        # Check numeric values
        self.assertGreater(float(config.get("order_refresh_time", 0)), 0, 
                          "order_refresh_time should be positive")
        self.assertGreater(float(config.get("order_amount", 0)), 0, 
                          "order_amount should be positive")
        self.assertGreater(float(config.get("min_spread", 0)), 0, 
                          "min_spread should be positive")
        self.assertGreater(float(config.get("max_spread", 0)), 0, 
                          "max_spread should be positive")
        self.assertGreaterEqual(float(config.get("max_spread", 0)), 
                               float(config.get("min_spread", 0)),
                               "max_spread should be >= min_spread")

if __name__ == "__main__":
    unittest.main() 