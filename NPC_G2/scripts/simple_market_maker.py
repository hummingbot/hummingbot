#!/usr/bin/env python3

"""
Simple Market Making Strategy for BITS GOA Assignment

This strategy implements a basic market making approach with dynamic spreads
based on basic volatility calculations and inventory management.
"""

import logging
from decimal import Decimal
from typing import Dict, List

from hummingbot.core.data_type.common import OrderType, PriceType, TradeType
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.event.events import OrderFilledEvent
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.connector.connector_base import ConnectorBase


class SimpleMarketMaker(ScriptStrategyBase):
    """
    Simple Market Making Strategy that adjusts spreads based on inventory position
    and implements basic risk management.
    """
    
    # Strategy parameters
    bid_spread = 0.001  # 0.1%
    ask_spread = 0.001  # 0.1%
    order_refresh_time = 15.0  # seconds
    order_amount = 0.01
    max_order_age = 300.0  # seconds
    trading_pair = "ETH-USDT"
    exchange = "binance_paper_trade"
    price_source = PriceType.MidPrice
    
    # Get base/quote from trading pair
    base, quote = trading_pair.split("-")
    
    # Risk management parameters
    target_base_ratio = 0.5  # Target 50% in base asset
    
    # Internal tracking variables
    create_timestamp = 0
    
    # Define markets
    markets = {exchange: {trading_pair}}
    
    def __init__(self, connectors: Dict[str, ConnectorBase]):
        super().__init__(connectors)
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        self.logger.info("Simple Market Making Strategy initialized")
    
    def on_tick(self):
        """
        This function is called frequently and contains the main logic
        """
        if self.create_timestamp <= self.current_timestamp:
            self.cancel_all_orders()
            
            # Get current inventory state
            self.update_inventory_metrics()
            
            # Create and place orders
            proposal = self.create_proposal()
            proposal_adjusted = self.adjust_proposal_to_budget(proposal)
            self.place_orders(proposal_adjusted)
            
            # Set next order refresh time
            self.create_timestamp = self.order_refresh_time + self.current_timestamp
    
    def update_inventory_metrics(self):
        """Update inventory-related metrics"""
        connector = self.connectors[self.exchange]
        
        # Get balances
        base_balance = connector.get_balance(self.base)
        quote_balance = connector.get_balance(self.quote)
        
        # Get current price
        mid_price = connector.get_price_by_type(self.trading_pair, self.price_source)
        if mid_price is None:
            self.logger.warning("Unable to fetch price")
            return
            
        # Calculate base value in quote
        base_value = base_balance * mid_price
        
        # Calculate total portfolio value in quote
        total_value = base_value + quote_balance
        
        if total_value > 0:
            current_base_ratio = float(base_value / total_value)
        else:
            current_base_ratio = 0.5  # Default to balanced
        
        # Calculate inventory skew
        inventory_skew = current_base_ratio - self.target_base_ratio
        
        # Adjust spreads based on inventory skew
        if inventory_skew > 0:  # Too much base, wider bid spread, tighter ask
            adjusted_bid_spread = self.bid_spread * (1 + abs(inventory_skew) * 2)
            adjusted_ask_spread = self.ask_spread * (1 - abs(inventory_skew) * 0.5)
        else:  # Too little base, tighter bid spread, wider ask
            adjusted_bid_spread = self.bid_spread * (1 - abs(inventory_skew) * 0.5)
            adjusted_ask_spread = self.ask_spread * (1 + abs(inventory_skew) * 2)
            
        # Ensure spreads don't go negative or too tight
        min_spread = 0.0005  # 0.05%
        self.bid_spread = max(min_spread, adjusted_bid_spread)
        self.ask_spread = max(min_spread, adjusted_ask_spread)
        
        # Adjust order sizes based on inventory skew
        self.buy_amount = self.order_amount * (1 + max(-0.5, min(0.5, -inventory_skew)))
        self.sell_amount = self.order_amount * (1 + max(-0.5, min(0.5, inventory_skew)))
        
        self.logger.info(f"Base Ratio: {current_base_ratio:.4f}, Target: {self.target_base_ratio:.4f}, Skew: {inventory_skew:.4f}")
        self.logger.info(f"Bid Spread: {self.bid_spread:.4f}, Ask Spread: {self.ask_spread:.4f}")
    
    def create_proposal(self) -> List[OrderCandidate]:
        """Create buy and sell orders"""
        connector = self.connectors[self.exchange]
        
        # Get current price
        mid_price = connector.get_price_by_type(self.trading_pair, self.price_source)
        if mid_price is None:
            self.logger.warning("Unable to fetch price")
            return []
            
        # Calculate order prices
        buy_price = mid_price * (Decimal("1") - Decimal(str(self.bid_spread)))
        sell_price = mid_price * (Decimal("1") + Decimal(str(self.ask_spread)))
        
        # Create order candidates
        buy_order = OrderCandidate(
            trading_pair=self.trading_pair,
            is_maker=True,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=Decimal(str(self.buy_amount)),
            price=buy_price
        )
        
        sell_order = OrderCandidate(
            trading_pair=self.trading_pair,
            is_maker=True,
            order_type=OrderType.LIMIT,
            order_side=TradeType.SELL,
            amount=Decimal(str(self.sell_amount)),
            price=sell_price
        )
        
        return [buy_order, sell_order]
    
    def adjust_proposal_to_budget(self, proposal: List[OrderCandidate]) -> List[OrderCandidate]:
        """Adjust order proposal to available budget"""
        return self.connectors[self.exchange].budget_checker.adjust_candidates(proposal, all_or_none=False)
    
    def place_orders(self, proposal: List[OrderCandidate]) -> None:
        """Place orders"""
        for order in proposal:
            if order.order_side == TradeType.BUY:
                self.buy(
                    connector_name=self.exchange,
                    trading_pair=order.trading_pair,
                    amount=order.amount,
                    order_type=order.order_type,
                    price=order.price
                )
                self.logger.info(f"Placed BUY order for {order.amount} {self.base} at {order.price}")
            else:
                self.sell(
                    connector_name=self.exchange,
                    trading_pair=order.trading_pair,
                    amount=order.amount,
                    order_type=order.order_type,
                    price=order.price
                )
                self.logger.info(f"Placed SELL order for {order.amount} {self.base} at {order.price}")
    
    def cancel_all_orders(self):
        """Cancel all active orders"""
        for order in self.get_active_orders(connector_name=self.exchange):
            self.cancel(self.exchange, order.trading_pair, order.client_order_id)
    
    def did_fill_order(self, event: OrderFilledEvent):
        """Handle order filled event"""
        self.logger.info(f"Order filled: {event.amount} {event.trading_pair} at {event.price}")

    def format_status(self) -> str:
        """Format status for display"""
        if not self.ready_to_trade:
            return "Market connectors are not ready."
            
        lines = []
        
        # Add balances
        balance_df = self.get_balance_df()
        lines.extend(["", "  Balances:"] + ["    " + line for line in balance_df.to_string(index=False).split("\n")])
        
        # Add active orders
        try:
            orders_df = self.active_orders_df()
            lines.extend(["", "  Orders:"] + ["    " + line for line in orders_df.to_string(index=False).split("\n")])
        except ValueError:
            lines.extend(["", "  No active orders."])
        
        # Add strategy parameters
        lines.extend(["", "  Strategy Parameters:"])
        lines.extend([f"    Bid Spread: {self.bid_spread:.4f}"])
        lines.extend([f"    Ask Spread: {self.ask_spread:.4f}"])
        lines.extend([f"    Order Amount: {self.order_amount}"])
        
        return "\n".join(lines)
