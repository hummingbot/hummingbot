#!/usr/bin/env python3
"""
Run script for Adaptive Market Making strategies
"""

import argparse
import os
import sys

def parse_args():
    parser = argparse.ArgumentParser(description='Run Adaptive Market Making strategies')
    parser.add_argument('--strategy', type=str, choices=['adaptive', 'ml'], default='adaptive',
                        help='Strategy to run: adaptive or ml-based')
    parser.add_argument('--mode', type=str, choices=['backtest', 'paper', 'live'], default='backtest',
                        help='Run mode: backtest, paper trading, or live trading')
    parser.add_argument('--config', type=str, help='Path to config file')
    
    return parser.parse_args()

def main():
    args = parse_args()
    
    # Determine which script to run
    if args.strategy == 'adaptive':
        script_path = 'src/main.py'
    else:  # ml
        script_path = 'src/main2.py'
    
    # Determine which config to use if not specified
    if not args.config:
        if args.mode == 'backtest':
            config_path = 'config/backtest_config.yml'
        elif args.mode == 'paper':
            config_path = 'config/paper_trade_config.yml'
        else:  # live
            config_path = 'config/adaptive_market_making_config.yml'
    else:
        config_path = args.config

    # Ensure config file exists
    if not os.path.exists(config_path):
        print(f"Config file not found: {config_path}")
        sys.exit(1)
    
    # Build and execute the command
    cmd = f"python {script_path} --config {config_path} --mode {args.mode}"
    print(f"Running: {cmd}")
    os.system(cmd)

if __name__ == "__main__":
    main() 