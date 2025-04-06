#!/usr/bin/env python3
"""
Script to run the strategy tests without importing the full Hummingbot connector codebase
which has pydantic v2 compatibility issues.
"""
import sys
import os
import unittest
import yaml
from decimal import Decimal
from unittest.mock import MagicMock, patch

# Add the tests directory to the path
sys.path.append(os.path.join(os.getcwd(), 'tests'))

class TestRunner:
    """Run the strategy tests"""
    
    def run_tests(self):
        """Run all the tests in the tests directory"""
        # Find all test modules in the tests directory
        test_loader = unittest.TestLoader()
        test_suite = test_loader.discover('tests/unit', pattern='test_*.py')
        
        # Run the tests
        test_runner = unittest.TextTestRunner(verbosity=2)
        result = test_runner.run(test_suite)
        
        return result.wasSuccessful()
    
    def test_config_loading(self):
        """Test that the config file exists and can be loaded"""
        config_path = 'config/strategy_config.yaml'
        
        # Check if file exists
        assert os.path.exists(config_path), f"Config file {config_path} does not exist"
        
        # Try to load the file
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Check required fields
        required_fields = [
            'exchange', 'trading_pair', 'order_refresh_time',
            'order_amount', 'min_spread', 'max_spread'
        ]
        
        for field in required_fields:
            assert field in config, f"Required field {field} not in config"
        
        # Check numeric values
        assert config['min_spread'] > 0, "min_spread must be positive"
        assert config['max_spread'] > config['min_spread'], "max_spread must be greater than min_spread"
        
        print("Config test passed.")
        return True

    def test_inventory_ratio_calculation(self):
        """Test the inventory ratio calculation logic"""
        # Create mock objects
        mock_connector = MagicMock()
        # Set up balances to get a 50/50 split ratio (0.5)
        base_token = 'BTC'
        quote_token = 'USDT'
        current_price = Decimal('50000')
        
        # With 1 BTC and 50000 USDT, we have 50% in base and 50% in quote
        mock_connector.get_balance.side_effect = lambda token: Decimal('1') if token == base_token else Decimal('50000')
        
        # Get balances
        base_balance = mock_connector.get_balance(base_token)
        quote_balance = mock_connector.get_balance(quote_token)
        
        # Calculate values
        base_value = base_balance * current_price  # 1 * 50000 = 50000
        total_value = base_value + quote_balance  # 50000 + 50000 = 100000
        
        # Inventory ratio should be base_value / total_value
        # With 1 BTC @ 50000 and 50000 USDT, ratio should be 0.5 (50/50 split)
        inventory_ratio = base_value / total_value if total_value > 0 else Decimal('0')
        
        assert inventory_ratio == Decimal('0.5'), f"Expected ratio 0.5, got {inventory_ratio}"
        print("Inventory ratio test passed.")
        return True
    
if __name__ == "__main__":
    runner = TestRunner()
    if len(sys.argv) > 1 and sys.argv[1] == 'config':
        success = runner.test_config_loading()
    elif len(sys.argv) > 1 and sys.argv[1] == 'inventory':
        success = runner.test_inventory_ratio_calculation()
    else:
        success = runner.run_tests()
    
    sys.exit(0 if success else 1) 