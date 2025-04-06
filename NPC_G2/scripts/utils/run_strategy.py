#!/usr/bin/env python3
"""
Run Strategy Script

This script loads and runs the Adaptive Market Making Strategy with the specified configuration.
"""

import os
import sys
import argparse
import logging
import importlib.util
import yaml
from typing import Dict, Any

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import strategy components
try:
    from scripts.strategies.config import AdaptiveMMConfig
except ImportError:
    print("Error importing strategy modules. Make sure you're running from the hummingbot directory.")
    sys.exit(1)


def load_config_from_yaml(file_path: str) -> Dict[str, Any]:
    """
    Load configuration from YAML file
    
    Args:
        file_path: Path to YAML configuration file
        
    Returns:
        Configuration dictionary
    """
    try:
        with open(file_path, 'r') as file:
            config = yaml.safe_load(file)
        return config
    except Exception as e:
        print(f"Error loading configuration: {str(e)}")
        return {}


def run_strategy(config_path: str) -> None:
    """
    Run the strategy with the specified configuration
    
    Args:
        config_path: Path to configuration file
    """
    # Load configuration
    config_dict = load_config_from_yaml(config_path)
    
    # Create configuration object
    config = AdaptiveMMConfig(**config_dict)
    
    # Import and run the strategy
    try:
        from scripts.strategies.adaptive_market_making import AdaptiveMarketMakingStrategy
        
        # Initialize and run strategy
        strategy = AdaptiveMarketMakingStrategy(config)
        strategy.run()
    except Exception as e:
        print(f"Error running strategy: {str(e)}")
        import traceback
        print(traceback.format_exc())


def setup_logging() -> None:
    """Set up logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(os.path.join('logs', 'strategy.log'))
        ]
    )


def main() -> None:
    """Main function"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Run Adaptive Market Making Strategy')
    parser.add_argument('--config', type=str, default='conf/adaptive_market_making_config.yml',
                        help='Path to configuration file')
    args = parser.parse_args()
    
    # Set up logging
    setup_logging()
    
    # Run strategy
    run_strategy(args.config)


if __name__ == '__main__':
    main() 