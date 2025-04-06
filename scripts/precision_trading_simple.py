#!/usr/bin/env python3
"""
Simplified Precision Trading Strategy for Testing
"""

import pandas as pd
import time
import os
import yaml
import logging
from decimal import Decimal
from typing import Dict, List, Optional

# Hummingbot imports
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import OrderType
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase

class PrecisionTradingSimple(ScriptStrategyBase):
    """Simplified version for testing"""
    
    def __init__(self, config_file_path="conf_simple_precision_trading.yml"):
        """Initialize the strategy"""
        super().__init__()
        
        # Default parameters
        self.exchange = "binance_paper_trade"
        self.trading_pair = "BTC-USDT"
        self.order_amount = Decimal("0.01")
        self.min_spread = Decimal("0.002")  # 0.2%
        self.max_spread = Decimal("0.02")   # 2%
        self.order_refresh_time = 30  # seconds
        
        # Set up logging to file
        self.logger().info("Initializing Simple Precision Trading Strategy")
        
        # Try to load config
        try:
            # Check multiple possible locations for the config file
            script_dir = os.path.dirname(os.path.realpath(__file__))
            hummingbot_root = os.path.dirname(script_dir)
            
            # List of possible config file locations (in order of preference)
            config_paths = [
                os.path.join(hummingbot_root, "conf", "strategies", config_file_path),  # Standard location
                os.path.join(script_dir, config_file_path),  # Script directory
            ]
            
            config_loaded = False
            config = None
            
            # Try each possible location
            for config_path in config_paths:
                self.logger().info(f"Looking for config file at: {config_path}")
                print(f"Looking for config file at: {config_path}")
                
                if os.path.exists(config_path):
                    with open(config_path, "r") as file:
                        config = yaml.safe_load(file)
                    
                    self.logger().info(f"Config file found and loaded successfully from {config_path}")
                    print(f"Config file found and loaded from {config_path}")
                    config_loaded = True
                    break
            
            if not config_loaded:
                self.logger().warning("Config file not found in any location, using default settings")
                print("Config file not found in any location, using default settings")
                
                # Update parameters from config
                self.exchange = config.get("exchange", self.exchange)
                self.trading_pair = config.get("trading_pair", self.trading_pair)
                self.order_amount = Decimal(str(config.get("order_amount", self.order_amount)))
                self.min_spread = Decimal(str(config.get("min_spread", self.min_spread)))
                self.max_spread = Decimal(str(config.get("max_spread", self.max_spread)))
                self.order_refresh_time = int(config.get("order_refresh_time", self.order_refresh_time))
            # Config file handling is done above
        except Exception as e:
            self.logger().error(f"Error loading config file: {e}", exc_info=True)
            print(f"Error loading config file: {e}")
            print("Using default settings")
        
        # Internal variables
        self._last_trade_time = 0
        self._active_orders = {}
        
        # Log and print initialization parameters
        log_msg = f"Strategy initialized with: {self.exchange}, {self.trading_pair}"
        self.logger().info(log_msg)
        print(log_msg)
        
        log_msg = f"Order amount: {self.order_amount}, Min spread: {self.min_spread}, Max spread: {self.max_spread}"
        self.logger().info(log_msg)
        print(log_msg)
        
        log_msg = f"Order refresh time: {self.order_refresh_time} seconds"
        self.logger().info(log_msg)
        print(log_msg)
        
    def on_tick(self):
        """Main strategy logic executed on each tick"""
        if not self.ready_to_trade:
            return
            
        current_tick = time.time()
        
        # Only create orders every X seconds based on config
        if current_tick - self._last_trade_time < self.order_refresh_time:
            return
            
        self._last_trade_time = current_tick
        
        # Simple market making logic
        try:
            self.logger().debug("Creating new orders")
            # Cancel existing orders
            self._cancel_active_orders()
            
            # Get connector
            connector = self.connectors[self.exchange]
            
            # Get mid price
            mid_price = self._get_mid_price(connector, self.trading_pair)
            if mid_price is None:
                error_msg = "Unable to get mid price, skipping order creation"
                self.logger().warning(error_msg)
                print(error_msg)
                return
                
            # Calculate basic spreads (no fancy adaptive logic for testing)
            bid_spread = self.min_spread
            ask_spread = self.min_spread
            
            # Calculate prices
            bid_price = mid_price * (Decimal("1") - bid_spread)
            ask_price = mid_price * (Decimal("1") + ask_spread)
            
            # Round prices to ticker price precision
            bid_price = connector.quantize_order_price(self.trading_pair, bid_price)
            ask_price = connector.quantize_order_price(self.trading_pair, ask_price)
            
            # Quantize order sizes
            bid_size = connector.quantize_order_amount(self.trading_pair, self.order_amount)
            ask_size = connector.quantize_order_amount(self.trading_pair, self.order_amount)
            
            # Create orders
            if bid_size > Decimal("0") and ask_size > Decimal("0"):
                log_msg = f"Creating orders at - BUY: {bid_size} @ {bid_price}, SELL: {ask_size} @ {ask_price}"
                self.logger().info(log_msg)
                print(log_msg)
                
                # Create buy order
                buy_order_id = self.buy(
                    connector_name=self.exchange,
                    trading_pair=self.trading_pair,
                    amount=bid_size,
                    order_type=OrderType.LIMIT,
                    price=bid_price
                )
                
                # Create sell order
                sell_order_id = self.sell(
                    connector_name=self.exchange,
                    trading_pair=self.trading_pair,
                    amount=ask_size,
                    order_type=OrderType.LIMIT,
                    price=ask_price
                )
                
                # Track orders
                if buy_order_id:
                    self._active_orders[buy_order_id] = {"type": "buy", "created_at": time.time()}
                if sell_order_id:
                    self._active_orders[sell_order_id] = {"type": "sell", "created_at": time.time()}
        
        except Exception as e:
            self.logger().error(f"Error creating orders: {e}", exc_info=True)
    
    def _cancel_active_orders(self):
        """Cancel all active orders"""
        try:
            for connector_name, trading_pairs in self.markets.items():
                for trading_pair in trading_pairs:
                    orders = self.get_active_orders(connector_name=connector_name, trading_pair=trading_pair)
                    for order in orders:
                        self.cancel(connector_name, trading_pair, order.client_order_id)
            
            # Clear tracking dictionary
            self._active_orders = {}
        except Exception as e:
            self.logger().error(f"Error cancelling orders: {e}", exc_info=True)
    
    def _get_mid_price(self, connector: ConnectorBase, trading_pair: str) -> Optional[Decimal]:
        """Get mid price from orderbook"""
        try:
            orderbook = connector.get_order_book(trading_pair)
            bid_price = orderbook.get_price_for_volume(True, 0.1).result_price
            ask_price = orderbook.get_price_for_volume(False, 0.1).result_price
            if bid_price is None or ask_price is None:
                return None
            return (bid_price + ask_price) / Decimal("2")
        except Exception as e:
            self.logger().error(f"Error getting mid price: {e}", exc_info=True)
            return None
    
    def format_status(self) -> str:
        """Format status for display in Hummingbot"""
        if not self.ready_to_trade:
            return "Strategy not ready to trade."
            
        lines = []
        lines.append("Simplified Precision Trading Strategy")
        
        # Add market info
        connector = self.connectors[self.exchange]
        mid_price = self._get_mid_price(connector, self.trading_pair)
        lines.append(f"\nTrading Pair: {self.trading_pair} @ {self.exchange}")
        lines.append(f"Current price: {mid_price:.8g}")
        
        # Show active orders
        lines.append("\nActive Orders:")
        active_orders = self.get_active_orders(connector_name=self.exchange)
        if not active_orders:
            lines.append("  No active orders")
        else:
            for order in active_orders:
                lines.append(f"  {order.order_side.name}: {order.amount} @ {order.price:.8g}")
        
        return "\n".join(lines)

# Initialize the strategy
def start():
    print("Starting Simplified Precision Trading Strategy")
    strategy = PrecisionTradingSimple()
    return strategy
