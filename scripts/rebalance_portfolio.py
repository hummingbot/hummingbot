import logging
from decimal import Decimal
from typing import List

from hummingbot.core.data_type.common import OrderType, PriceType, TradeType
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.event.events import OrderFilledEvent
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase

from requests import Request, Session
import json
import time
import webbrowser


class WeightCalculatorBase:
    portfolio: []

    def __init__(self, portfolio: []):
        self.portfolio = portfolio
        pass

    def calculated_weights(self) -> dict:
        pass


class WeightCalculatorMock(WeightCalculatorBase):
    counter = 1

    def calculate(self) -> dict:
        weights = dict()
        for asset in self.portfolio:
            if self.counter % 2 == 0:
                weights[asset] = Decimal(1.0) / Decimal(len(self.portfolio))
            else:
                weights = {"ETH": Decimal(0.1), "BTC": Decimal(0.9), "BUSD": Decimal(0.0), "SOL": Decimal(0.0),
                           "FIL": Decimal(0.0)}
        self.counter += 1
        return weights


class WeightCalculatorMarketCap(WeightCalculatorBase):
    def calculate(self) -> dict:
        market_info = self.get_market_info()
        total: Decimal = 0.0
        for asset, signal in market_info.items():
            total = Decimal(total) + signal
        weights = dict()
        for asset, signal in market_info.items():
            weights[asset] = Decimal(signal / total)
        return weights

    def get_market_info(self) -> dict:  # Function to get the info
        symbols_raw = ""
        for asset in self.portfolio:
            symbols_raw += asset + ","
        symbols = symbols_raw[:-1]

        url = 'https://sandbox-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest'  # Sanbox API url
        parameters = {'symbol': symbols}
        headers = {
            'Accepts': 'application/json',
            'X-CMC_PRO_API_KEY': 'b54bcf4d-1bca-4e8e-9a24-22ff2c3d462c'  # Sandbox API key
        }
        session = Session()
        session.headers.update(headers)
        response = session.get(url, params=parameters)
        info = json.loads(response.text)

        market_info_dict = dict()
        for asset in self.portfolio:
            quote_details = info["data"][asset]["quote"]["USD"]
            volume_24h = Decimal(quote_details["volume_24h"])
            market_cap = Decimal(quote_details["market_cap"])
            market_info_dict[asset] = Decimal(volume_24h * market_cap)
        return market_info_dict


class RebalancePortfolio(ScriptStrategyBase):
    portfolio_rebalance_time = 15
    create_timestamp = 0
    assets = {"ETH", "BTC", "BUSD", "SOL", "FIL"}
    quote = "USDT"
    portfolio_pairs = {"ETH-USDT", "BTC-USDT", "BUSD-USDT", "SOL-USDT", "FIL-USDT"}
    exchange = "binance_paper_trade"
    markets = {exchange: portfolio_pairs}
    weights_calculator_real = True
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
            amounts_diffs = self.calculate_weight_diffs()
            self.rebalance_portfolio(amounts_diffs)
            self.create_timestamp = self.portfolio_rebalance_time + self.current_timestamp

    def calculate_weight_diffs(self) -> dict:
        new_weights = self.weights_calculator.calculate()
        self.log_with_clock(logging.INFO, f"New weights 666: {new_weights}")

        current_balances_prices = self.get_portfolio_balances()
        self.log_with_clock(logging.INFO, f"Current balances and prices: {current_balances_prices}")

        # calculate total portfolio value
        total_portfolio_value: Decimal = 0.0
        for value in current_balances_prices.values():
            total_portfolio_value = Decimal(total_portfolio_value) + Decimal(value[0] * value[1])
        self.log_with_clock(logging.INFO, f"Total portfolio value: {total_portfolio_value}")

        # calculate current weights
        current_weights = dict()
        for asset, value in current_balances_prices.items():
            current_weights[asset] = Decimal(Decimal(value[0] * value[1])) / Decimal(total_portfolio_value)
        self.log_with_clock(logging.INFO, f"Current weights: {current_weights}")

        # amount diff based on new weight and current weight
        amounts_diffs = dict()
        for asset in self.assets:
            amounts_diffs[asset] = ((new_weights[asset] - current_weights[asset]) * total_portfolio_value) / \
                                   current_balances_prices[asset][1]
        self.log_with_clock(logging.INFO, f"Weights diffs: {amounts_diffs}")

        return amounts_diffs

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
            self.log_with_clock(logging.INFO, f"Balance for asset {asset} = {balance}")
            price = self.connectors[self.exchange].get_price_by_type(asset + "-" + self.quote, self.price_source)
            self.log_with_clock(logging.INFO, f"Price for asset {asset} = {price}")
            asset_balance_dict[asset] = (balance, price)  # balance * price
        return asset_balance_dict

    def rebalance_portfolio(self, ammounts_diffs: dict):
        # This is a very basic execution method, which is good enough for proof of concept and small size portfolio
        # Simplifications:
        #      a) No large order execution management
        #      b) Rebalancing uses market orders

        self.log_with_clock(logging.INFO, f"Rebalancing portfolio with ammounts diffs: {ammounts_diffs}")

        # 1st sell differences for assets with diff value < 0. This will obtain quote currency.
        for asset, value in ammounts_diffs.items():
            if value < 0:
                pair = asset + "-" + self.quote
                amount = abs(value)
                sell_order = OrderCandidate(trading_pair=pair, is_maker=False, order_type=OrderType.MARKET,
                                            order_side=TradeType.SELL, amount=Decimal(amount), price=Decimal("NaN"))
                self.log_with_clock(logging.INFO, f"About to place sell order: {sell_order}")
                self.place_order(connector_name=self.exchange, order=sell_order)

        # 2nd buy differences for assets with diff value > 0.
        for asset, value in ammounts_diffs.items():
            if value > 0:
                pair = asset + "-" + self.quote
                amount = abs(value)
                buy_order = OrderCandidate(trading_pair=pair, is_maker=False, order_type=OrderType.MARKET,
                                           order_side=TradeType.BUY, amount=Decimal(amount), price=Decimal("NaN"))
                self.log_with_clock(logging.INFO, f"About to place buy order: {buy_order}")
                self.place_order(connector_name=self.exchange, order=buy_order)

    def place_order(self, connector_name: str, order: OrderCandidate):
        if order.order_side == TradeType.SELL:
            self.sell(connector_name=connector_name, trading_pair=order.trading_pair, amount=order.amount,
                      order_type=order.order_type, price=order.price)
        elif order.order_side == TradeType.BUY:
            self.buy(connector_name=connector_name, trading_pair=order.trading_pair, amount=order.amount,
                     order_type=order.order_type, price=order.price)
