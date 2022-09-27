from typing import List
from decimal import Decimal

from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.rate_oracle.rate_oracle import RateOracle


class AutoPMM(ScriptStrategyBase):
    position_size = 1000
    trading_pair = "AAVE-USDT"
    exchange = "binance_paper_trade"
    proposal: List[OrderCandidate] = []
    proposal_adjusted: List[OrderCandidate] = []

    markets = {exchange: {trading_pair}}

    def on_tick(self):
        try:
            self.cancel_all_orders()
            self.proposal= self.create_proposal()
            self.proposal_adjusted = self.adjust_proposal_to_budget(self.proposal)
            self.place_orders(self.proposal_adjusted)
            
        except Exception as e:
            print(e)
        # HummingbotApplication.main_application().stop()

    def get_order_amount(self):
        
        conversion_rate = RateOracle.get_instance().rate(self.trading_pair)
        amount = self.position_size / conversion_rate 
        order_amount = self.connectors[self.exchange].quantize_order_amount(self.trading_pair, amount)
        
        self.logger().info(f"order_amount: {order_amount}") 
        
        return order_amount 

            
    def calculate_spread(self):
        
        mid_price = self.connectors[self.exchange].get_mid_price(self.trading_pair)
        bid_price = self.connectors[self.exchange].get_price(self.trading_pair, False)
        ask_price = self.connectors[self.exchange].get_price(self.trading_pair, True)

        bid_ask_spread = (bid_price - ask_price )* mid_price / 100
        self.logger().info(f"bid_ask_spread: {bid_ask_spread}")

        return bid_ask_spread
        

    def create_proposal(self) -> List[OrderCandidate]:
        mid_price = self.connectors[self.exchange].get_mid_price(self.trading_pair)
        spread = self.calculate_spread()
        order_amount = self.get_order_amount()
        
        buy_price = mid_price * Decimal(1 - spread)
        buy_order = OrderCandidate(trading_pair=self.trading_pair, order_type=OrderType.LIMIT,
                                order_side=TradeType.BUY, is_maker = True, amount=Decimal(order_amount), price=buy_price)
            
        sell_price = mid_price * Decimal(1 + spread)
        sell_order = OrderCandidate(trading_pair=self.trading_pair, order_type=OrderType.LIMIT,
                                    order_side=TradeType.SELL, is_maker = True, amount=Decimal(order_amount), price=sell_price)

        return [buy_order, sell_order]

    def adjust_proposal_to_budget(self, proposal: List[OrderCandidate]) -> List[OrderCandidate]:
        proposal_adjusted = self.connectors[self.exchange].budget_checker.adjust_candidates(proposal, all_or_none=True)
        return proposal_adjusted

    def place_orders(self, proposal: List[OrderCandidate]) -> None:
        for order in proposal:
            self.place_order(connector_name=self.exchange, order=order)

    def place_order(self,connector_name: str, order: OrderCandidate):
        if order.order_side == TradeType.SELL:
            self.sell(connector_name = connector_name, trading_pair=order.trading_pair, amount=order.amount,
                      order_type=order.order_type, price=order.price)
        elif order.order_side == TradeType.BUY:
            self.buy(connector_name= connector_name, trading_pair=order.trading_pair, amount=order.amount,
                     order_type=order.order_type, price=order.price)

    def cancel_all_orders(self):
        for exchange in self.connectors.values():
            safe_ensure_future(exchange.cancel_all(timeout_seconds=6))
    
    
    def format_status(self) -> str:
        if not self.ready_to_trade:
            return "Market connectors are not ready."
        lines = []
        warning_lines = []
        warning_lines.extend(self.network_warning(self.get_market_trading_pair_tuples()))

        balance_df = self.get_balance_df()
        lines.extend(["", "  Balances:"] + ["    " + line for line in balance_df.to_string(index=False).split("\n")])

        market_status_df = self.market_status_data_frame(self.get_market_trading_pair_tuples())
        lines.extend(["", "  Market Status:"] + ["    " + line for line in market_status_df.to_string(index=False).split("\n")])
        
        # Strategy status
        lines.extend(["", "  bid_ask_spread:"] + ["    " + f"{self.bid_ask_spread:.0f}"])

        warning_lines.extend(self.balance_warning(self.get_market_trading_pair_tuples()))
        if len(warning_lines) > 0:
            lines.extend(["", "*** WARNINGS ***"] + warning_lines)
        return "\n".join(lines)