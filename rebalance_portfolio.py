import logging
from decimal import Decimal
from typing import List

from hummingbot.core.data_type.common import OrderType, PriceType, TradeType
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.event.events import OrderFilledEvent
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class WeightCalculatorBase:
    portfolio: []

    def __init__(self, portfolio: []):
        self.portfolio = portfolio
        pass

    # @abstractmethod
    def calculated_weights(self) -> []:
        pass


class WeightCalculatorMock(WeightCalculatorBase):
    def calculate(self) -> []:
        return []


class WeightCalculatorMarketCap(WeightCalculatorBase):
    def calculate(self) -> []:
        return []


class RebalancePortfolio(ScriptStrategyBase):
    portfolio_rebalance_time = 15
    create_timestamp = 0
    base_currencies = {"ETH", "BTC", "BUSD", "SOL", "FIL"}
    quote = "USDT"
    portfolio_pairs = {"ETH-USDT", "BTC-USDT", "BUSD-USDT", "SOL-USDT", "FIL-USDT"}
    exchange = "binance_paper_trade"
    markets = {exchange: portfolio_pairs}
    weights_calculator_real = False
    weights_calculator: WeightCalculatorBase = None

    def on_tick(self):
        self.log_with_clock(logging.INFO, f"1")
        if self.create_timestamp <= self.current_timestamp:
            self.log_with_clock(logging.INFO, f"2")
            self.cancel_all_orders()
            self.log_with_clock(logging.INFO, f"3")
            self.create_weights_calculator()
            self.log_with_clock(logging.INFO, f"4")
            deltas = self.calculate_balances_deltas()
            self.log_with_clock(logging.INFO, f"5")
            self.rebalance_portfolio(deltas)
            self.log_with_clock(logging.INFO, f"6")
            self.create_timestamp = self.portfolio_rebalance_time + self.current_timestamp

    def calculate_balances_deltas(self):
        self.create_weights_calculator()
        weights = self.weights_calculator.calculate()
        current_balances = self.get_portfolio_balances()
        # map weights with balances
        return []

    def create_weights_calculator(self):
        if self.weights_calculator is None:
            if self.weights_calculator_real:
                self.log_with_clock(logging.INFO, f"Creating weights calculator for portfolio {self.portfolio_pairs}")
                self.weights_calculator = WeightCalculatorMarketCap(self.portfolio_pairs)
            else:
                self.log_with_clock(logging.INFO, f"Creating mock weights calculator for portfolio {self.portfolio_pairs}")
                self.weights_calculator = WeightCalculatorMock(self.portfolio_pairs)

    def cancel_all_orders(self):
        for order in self.get_active_orders(connector_name=self.exchange):
            self.cancel(self.exchange, order.trading_pair, order.client_order_id)

    def get_portfolio_balances(self):
        return []
        # for portfolio in base_currencies:
        #    self.markets.

    def rebalance_portfolio(self, deltas: []):
        self.log_with_clock(logging.INFO, f"Rebalancing portfolio with deltas: {deltas}")
