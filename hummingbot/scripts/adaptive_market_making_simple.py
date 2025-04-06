from decimal import Decimal
import pandas as pd
import time
from typing import Dict, List, Optional

from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.event.events import OrderType, TradeType
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class AdaptiveMarketMaking(ScriptStrategyBase):
    """
    A simplified version of the adaptive market making strategy for testing.
    """
    
    def __init__(self):
        super().__init__()
        
        # Strategy parameters
        self.connector_name = "binance_paper_trade"
        self.trading_pair = "ETH-USDT"
        self.order_amount = Decimal("0.1")
        self.min_spread = Decimal("0.001")  # 0.1%
        self.max_spread = Decimal("0.01")   # 1%
        self.order_refresh_time = 30.0
        
        # Parse the trading pair
        self.base_asset, self.quote_asset = self.trading_pair.split("-")
        
        # Runtime variables
        self.last_order_refresh_time = 0
        
        # Register markets
        self.markets = {self.connector_name: {self.trading_pair}}
        
    def on_tick(self):
        """
        Called on each clock tick.
        """
        # Check if it's time to refresh orders
        current_time = time.time()
        elapsed_time = current_time - self.last_order_refresh_time
        
        if elapsed_time < self.order_refresh_time:
            # Not time to refresh yet
            return
            
        # Cancel existing orders and place new ones
        self.cancel_all_orders()
        self.place_orders()
        
        self.last_order_refresh_time = current_time
        self.logger().info("Refreshed orders")
    
    def place_orders(self):
        """
        Place bid and ask orders.
        """
        connector = self.connectors[self.connector_name]
        
        # Get current market price
        mid_price = self.get_mid_price()
        
        # Calculate bid and ask prices with default spread
        spread = (self.min_spread + self.max_spread) / Decimal("2")
        bid_price = mid_price * (Decimal("1") - spread)
        ask_price = mid_price * (Decimal("1") + spread)
        
        # Round prices
        bid_price = self.round_price(bid_price)
        ask_price = self.round_price(ask_price)
        
        # Place bid order
        connector.buy(
            trading_pair=self.trading_pair,
            price=bid_price,
            amount=self.order_amount,
            order_type=OrderType.LIMIT,
        )
        self.logger().info(f"Placed bid order: {self.order_amount} {self.base_asset} at {bid_price} {self.quote_asset}")
        
        # Place ask order
        connector.sell(
            trading_pair=self.trading_pair,
            price=ask_price,
            amount=self.order_amount,
            order_type=OrderType.LIMIT,
        )
        self.logger().info(f"Placed ask order: {self.order_amount} {self.base_asset} at {ask_price} {self.quote_asset}")
    
    def cancel_all_orders(self):
        """
        Cancel all active orders.
        """
        connector = self.connectors[self.connector_name]
        connector.cancel_all(self.trading_pair)
    
    def get_mid_price(self) -> Decimal:
        """
        Get the current mid price from the order book.
        """
        connector = self.connectors[self.connector_name]
        order_book: OrderBook = connector.get_order_book(self.trading_pair)
        return order_book.get_price_for_volume(True, 0.5).result_price
    
    def round_price(self, price: Decimal) -> Decimal:
        """
        Round price to appropriate precision.
        """
        connector = self.connectors[self.connector_name]
        price_precision = connector.get_order_price_quantum(self.trading_pair, price)
        return (price // price_precision) * price_precision


# This function is required by Hummingbot
def start(script_name, strategy_file_name):
    """
    This is the main entry point for the script.
    :param script_name: the name of the script
    :param strategy_file_name: the name of the configuration file if any
    :return: the initialized strategy object
    """
    # Create and initialize the strategy instance
    strategy = AdaptiveMarketMaking()
    
    # Important: print some initialization message - this helps with debugging
    print("Initializing Adaptive Market Making strategy...")
    print(f"Trading pair: {strategy.trading_pair}")
    print(f"Order amount: {strategy.order_amount} {strategy.base_asset}")
    print(f"Spread range: {float(strategy.min_spread)*100}% - {float(strategy.max_spread)*100}%")
    
    return strategy 