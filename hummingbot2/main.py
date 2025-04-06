#!/usr/bin/env python3
"""
Hummingbot V2 - Main Entry Point
v2.0.0
"""

import os
import sys
import logging
import argparse
import asyncio
import yaml
from typing import Dict, Any

# Import strategy modules
from strategies.adaptive_ml_strategy import AdaptiveMLMarketMakingStrategy

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("hummingbot_v2.log")
    ]
)
logger = logging.getLogger("hummingbot_v2")

def load_config(config_path: str) -> Dict[str, Any]:
    """Load configuration from YAML file."""
    try:
        with open(config_path, 'r') as file:
            config = yaml.safe_load(file)
            logger.info(f"Loaded configuration from {config_path}")
            return config
    except Exception as e:
        logger.error(f"Error loading config from {config_path}: {str(e)}")
        sys.exit(1)

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Hummingbot V2")
    parser.add_argument(
        "-c", "--config", 
        type=str, 
        default="config/adaptive_ml_config.yml",
        help="Path to configuration file"
    )
    parser.add_argument(
        "-d", "--debug", 
        action="store_true", 
        help="Enable debug logging"
    )
    parser.add_argument(
        "-s", "--strategy", 
        type=str, 
        default=None,
        help="Override strategy in config file"
    )
    return parser.parse_args()

async def main():
    """Main entry point."""
    # Parse command line arguments
    args = parse_args()
    
    # Set log level based on args
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")
    
    # Load configuration
    config_path = args.config
    if not os.path.isabs(config_path):
        # Convert relative path to absolute
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), config_path)
    
    config = load_config(config_path)
    
    # Override strategy if specified in command line
    if args.strategy:
        config["strategy"] = args.strategy
        logger.info(f"Overriding strategy with {args.strategy}")
    
    # Initialize and start the appropriate strategy
    strategy_name = config.get("strategy")
    logger.info(f"Starting strategy: {strategy_name}")
    
    if strategy_name == "adaptive_ml_market_making":
        # Extract required parameters for the strategy
        strategy = AdaptiveMLMarketMakingStrategy(
            exchange=config.get("exchange", "binance_paper_trade"),
            market=config.get("market", "ETH-USDT"),
            order_amount=config.get("order_amount", 0.1),
            min_spread=config.get("min_spread", 0.002),
            max_spread=config.get("max_spread", 0.02),
            order_refresh_time=config.get("order_refresh_time", 30.0),
            max_order_age=config.get("max_order_age", 300.0),
            
            # Technical indicator parameters
            rsi_length=config.get("rsi_length", 14),
            rsi_overbought=config.get("rsi_overbought", 70),
            rsi_oversold=config.get("rsi_oversold", 30),
            ema_short=config.get("ema_short", 12),
            ema_long=config.get("ema_long", 26),
            bb_length1=config.get("bb_length1", 120),
            bb_length2=config.get("bb_length2", 12),
            bb_std=config.get("bb_std", 2.0),
            
            # Risk management parameters
            max_inventory_ratio=config.get("max_inventory_ratio", 0.5),
            min_inventory_ratio=config.get("min_inventory_ratio", 0.3),
            volatility_adjustment=config.get("volatility_adjustment", 1.0),
            trailing_stop_pct=config.get("trailing_stop_pct", 0.02),
            
            # ML parameters
            use_ml=config.get("use_ml", True),
            ml_data_buffer_size=config.get("ml_data_buffer_size", 5000),
            ml_update_interval=config.get("ml_update_interval", 3600),
            ml_confidence_threshold=config.get("ml_confidence_threshold", 0.65),
            ml_signal_weight=config.get("ml_signal_weight", 0.35),
            ml_model_dir=config.get("ml_model_dir", "./models")
        )
        
        await strategy.start()
    else:
        logger.error(f"Unknown strategy: {strategy_name}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        # Run the main function
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt detected. Exiting...")
    except Exception as e:
        logger.exception(f"Unexpected error: {str(e)}")
        sys.exit(1) 