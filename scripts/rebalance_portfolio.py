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
    def calculated_weights(self) -> dict:
        pass


class WeightCalculatorMock(WeightCalculatorBase):
    def calculate(self) -> dict:
        weights = dict()
        for asset in self.portfolio:
            weights[asset] = Decimal(1.0) / Decimal(len(self.portfolio))
        return weights


class WeightCalculatorMarketCap(WeightCalculatorBase):
    def calculate(self) -> dict:
        return dict()


class RebalancePortfolio(ScriptStrategyBase):
    portfolio_rebalance_time = 15
    create_timestamp = 0
    assets = {"ETH", "BTC", "BUSD", "SOL", "FIL"}
    quote = "USDT"
    portfolio_pairs = {"ETH-USDT", "BTC-USDT", "BUSD-USDT", "SOL-USDT", "FIL-USDT"}
    exchange = "binance_paper_trade"
    markets = {exchange: portfolio_pairs}
    weights_calculator_real = False
    weights_calculator: WeightCalculatorBase = None
    ran_once = False
    price_source = PriceType.MidPrice

    def on_tick(self):
        if self.create_timestamp <= self.current_timestamp:
            if not self.ran_once:
                self.log_with_clock(logging.INFO, f"Initializing ...")
                self.create_weights_calculator()
                self.ran_once = True
            self.cancel_all_orders()
            diffs = self.calculate_weight_diffs()
            self.rebalance_portfolio(diffs)
            self.create_timestamp = self.portfolio_rebalance_time + self.current_timestamp

    def calculate_weight_diffs(self) -> dict:
        self.create_weights_calculator()
        new_weights = self.weights_calculator.calculate()
        self.log_with_clock(logging.INFO, f"New weights: {new_weights}")
        current_balances = self.get_portfolio_balances()
        self.log_with_clock(logging.INFO, f"Current balances: {current_balances}")

        # calculate total portfolio value
        total_portfolio_value: Decimal = 0.0
        for value in current_balances.values():
            total_portfolio_value = Decimal(total_portfolio_value) + Decimal(value)
        self.log_with_clock(logging.INFO, f"Total portfolio value: {total_portfolio_value}")

        # calculate current weights
        current_weights = dict()
        for asset, value in current_balances.items():
            current_weights[asset] = Decimal(value) / Decimal(total_portfolio_value)
        self.log_with_clock(logging.INFO, f"Current weights: {current_weights}")

        # diff between new weight and current weight
        weight_diffs = dict()
        for asset in self.assets:
            weight_diffs[asset] = new_weights[asset] - current_weights[asset]
        self.log_with_clock(logging.INFO, f"Weights diffs: {weight_diffs}")

        return weight_diffs

    def create_weights_calculator(self):
        if self.weights_calculator is None:
            if self.weights_calculator_real:
                self.log_with_clock(logging.INFO, f"Creating weights calculator for portfolio {self.assets}")
                self.weights_calculator = WeightCalculatorMarketCap(self.assets)
            else:
                self.log_with_clock(logging.INFO,
                                    f"Creating mock weights calculator for portfolio {self.assets}")
                self.weights_calculator = WeightCalculatorMock(self.assets)

    def cancel_all_orders(self):
        for order in self.get_active_orders(connector_name=self.exchange):
            self.cancel(self.exchange, order.trading_pair, order.client_order_id)

    def get_portfolio_balances(self):
        asset_balance_dict = dict()
        for asset in self.assets:
            balance = self.connectors[self.exchange].get_balance(asset)
            self.log_with_clock(logging.INFO, f"Balance for portfolio {asset} = {balance}")
            price = self.connectors[self.exchange].get_price_by_type(asset + "-" + self.quote, self.price_source)
            self.log_with_clock(logging.INFO, f"Price for asset {asset} = {price}")
            asset_balance_dict[asset] = balance * price
        return asset_balance_dict

    def rebalance_portfolio(self, diffs: dict):
        self.log_with_clock(logging.INFO, f"Rebalancing portfolio with deltas: {diffs}")
