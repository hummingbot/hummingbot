import decimal
import logging
import math
from decimal import Decimal
from typing import Dict

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import OrderType
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.strategy.strategy_py_base import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderExpiredEvent,
    OrderFilledEvent,
    SellOrderCompletedEvent,
    SellOrderCreatedEvent,
)


def create_differences_bar_chart(differences_dict):
    diff_str = "Differences to 1/N:\n"
    bar_length = 20
    for asset, deficit in differences_dict.items():
        deficit_percentage = deficit * 100
        filled_length = math.ceil(abs(deficit) * bar_length)

        if deficit > 0:
            bar = f"{asset:6}: {' ' * bar_length}|{'#' * filled_length:<{bar_length}} +{deficit_percentage:.4f}%"
        else:
            bar = f"{asset:6}: {'#' * filled_length:>{bar_length}}|{' ' * bar_length} -{-deficit_percentage:.4f}%"
        diff_str += bar + "\n"
    return diff_str


class OneOverNPortfolio(ScriptStrategyBase):
    """
    This strategy aims to create a 1/N cryptocurrency portfolio, providing perfect diversification without
    parametrization and giving a reasonable baseline performance.
    https://www.notion.so/1-N-Index-Portfolio-26752a174c5a4648885b8c344f3f1013
    Future improvements:
    - add quote_currency balance as funding so that it can be traded, and it is not stuck when some trades are lost by
        the exchange
    - create a state machine so that all sells are executed before buy orders are submitted. Thus guaranteeing the
        funding
    """

    exchange_name = "binance_paper_trade"
    quote_currency = "USDT"
    # top 10 coins by market cap, excluding stablecoins
    base_currencies = ["BTC", "ETH", "MATIC", "XRP", "BNB", "ADA", "DOT", "LTC", "DOGE", "SOL"]
    pairs = {f"{currency}-USDT" for currency in base_currencies}

    #: Define markets to instruct Hummingbot to create connectors on the exchanges and markets you need
    markets = {exchange_name: pairs}
    activeOrders = 0

    def __init__(self, connectors: Dict[str, ConnectorBase]):
        super().__init__(connectors)
        self.total_available_balance = None
        self.differences_dict = None
        self.quote_balances = None
        self.base_balances = None

    def on_tick(self):
        #: check current balance of coins
        balance_df = self.get_balance_df()
        #: Filter by exchange "binance_paper_trade"
        exchange_balance_df = balance_df.loc[balance_df["Exchange"] == self.exchange_name]
        self.base_balances = self.calculate_base_balances(exchange_balance_df)
        self.quote_balances = self.calculate_quote_balances(self.base_balances)

        #: Sum the available balances
        self.total_available_balance = sum(balances[1] for balances in self.quote_balances.values())
        self.logger().info(f"TOT ({self.quote_currency}): {self.total_available_balance}")
        self.logger().info(
            f"TOT/{len(self.base_currencies)} ({self.quote_currency}): {self.total_available_balance / len(self.base_currencies)}")
        #: Calculate the percentage of each available_balance over total_available_balance
        total_available_balance = self.total_available_balance
        percentages_dict = {}
        for asset, balances in self.quote_balances.items():
            available_balance = balances[1]
            percentage = (available_balance / total_available_balance)
            percentages_dict[asset] = percentage
            self.logger().info(f"Total share {asset}: {percentage * 100}%")
        number_of_assets = Decimal(len(self.quote_balances))
        #: Calculate the difference between each percentage and 1/number_of_assets
        differences_dict = self.calculate_deficit_percentages(number_of_assets, percentages_dict)
        self.differences_dict = differences_dict

        # Calculate the absolute differences in quote currency
        deficit_over_current_price = {}
        for asset, deficit in differences_dict.items():
            current_price = self.quote_balances[asset][2]
            deficit_over_current_price[asset] = deficit / current_price
        #: Calculate the difference in pieces of each base asset
        differences_in_base_asset = {}
        for asset, deficit in deficit_over_current_price.items():
            differences_in_base_asset[asset] = deficit * total_available_balance
        #: Create an ordered list of asset-deficit pairs starting from the smallest negative deficit ending with the
        #  biggest positive deficit
        ordered_trades = sorted(differences_in_base_asset.items(), key=lambda x: x[1])
        #: log the planned ordered trades with sequence number
        for i, (asset, deficit) in enumerate(ordered_trades):
            trade_number = i + 1
            trade_type = "sell" if deficit < Decimal('0') else "buy"
            self.logger().info(f"Trade {trade_number}: {trade_type} {asset}: {deficit}")

        if 0 < self.activeOrders:
            self.logger().info(f"Wait to trade until all active orders have completed: {self.activeOrders}")
            return
        for i, (asset, deficit) in enumerate(ordered_trades):
            quote_price = self.quote_balances[asset][2]
            # We don't trade under 1 quote value, e.g. dollar. We can save trading fees by increasing this amount
            if abs(deficit * quote_price) < 1:
                self.logger().info(f"{abs(deficit * quote_price)} < 1 too small to trade")
                continue
            trade_is_buy = True if deficit > Decimal('0') else False
            try:
                if trade_is_buy:
                    self.buy(connector_name=self.exchange_name, trading_pair=f"{asset}-{self.quote_currency}",
                             amount=abs(deficit), order_type=OrderType.MARKET, price=quote_price)
                else:
                    self.sell(connector_name=self.exchange_name, trading_pair=f"{asset}-{self.quote_currency}",
                              amount=abs(deficit), order_type=OrderType.MARKET, price=quote_price)
            except decimal.InvalidOperation as e:
                # Handle the error by logging it or taking other appropriate actions
                print(f"Caught an error: {e}")
                self.activeOrders -= 1

        return

    def calculate_deficit_percentages(self, number_of_assets, percentages_dict):
        differences_dict = {}
        for asset, percentage in percentages_dict.items():
            deficit = (Decimal('1') / number_of_assets) - percentage
            differences_dict[asset] = deficit
            self.logger().info(f"Missing from 1/N {asset}: {deficit * 100}%")
        return differences_dict

    def calculate_quote_balances(self, base_balances):
        #: Multiply each balance with the current price to get the balances in the quote currency
        quote_balances = {}
        connector = self.connectors[self.exchange_name]
        for asset, balances in base_balances.items():
            trading_pair = f"{asset}-{self.quote_currency}"
            # noinspection PyUnresolvedReferences
            current_price = Decimal(connector.get_mid_price(trading_pair))
            total_balance = balances[0] * current_price
            available_balance = balances[1] * current_price
            quote_balances[asset] = (total_balance, available_balance, current_price)
            self.logger().info(
                f"{asset} * {current_price} {self.quote_currency} = {available_balance} {self.quote_currency}")
        return quote_balances

    def calculate_base_balances(self, exchange_balance_df):
        base_balances = {}
        for _, row in exchange_balance_df.iterrows():
            asset_name = row["Asset"]
            if asset_name in self.base_currencies:
                total_balance = Decimal(row["Total Balance"])
                available_balance = Decimal(row["Available Balance"])
                base_balances[asset_name] = (total_balance, available_balance)
                logging.info(f"{available_balance:015,.5f} {asset_name} \n")
        return base_balances

    def format_status(self) -> str:
        # checking if last member variable in on_tick is set, so we can start
        if self.differences_dict is None:
            return "SYSTEM NOT READY... booting"
        # create a table of base_balances and quote_balances and the summed up total of the quote_balances
        table_of_balances = "base balances         quote balances           price\n"
        for asset_name, base_balances in self.base_balances.items():
            quote_balance = self.quote_balances[asset_name][1]
            price = self.quote_balances[asset_name][2]
            table_of_balances += f"{base_balances[1]:15,.5f} {asset_name:5} {quote_balance:15,.5f} {price:15,.5f} {self.quote_currency}\n"
        table_of_balances += f"TOT    ({self.quote_currency}): {self.total_available_balance:15,.2f}\n"
        table_of_balances += f"TOT/{len(self.base_currencies)} ({self.quote_currency}): {self.total_available_balance / len(self.base_currencies):15,.2f}\n"
        return f"active orders: {self.activeOrders}\n" + \
            table_of_balances + "\n" + \
            create_differences_bar_chart(self.differences_dict)

    def did_create_buy_order(self, event: BuyOrderCreatedEvent):
        self.activeOrders += 1
        logging.info(f"Created Buy - Active Orders ++: {self.activeOrders}")

    def did_create_sell_order(self, event: SellOrderCreatedEvent):
        self.activeOrders += 1
        logging.info(f"Created Sell - Active Orders ++: {self.activeOrders}")

    def did_complete_buy_order(self, event: BuyOrderCompletedEvent):
        self.activeOrders -= 1
        logging.info(f"Completed Buy - Active Orders --: {self.activeOrders}")

    def did_complete_sell_order(self, event: SellOrderCompletedEvent):
        self.activeOrders -= 1
        logging.info(f"Completed Sell - Active Orders --: {self.activeOrders}")

    def did_cancel_order(self, event: OrderCancelledEvent):
        self.activeOrders -= 1
        logging.info(f"Canceled Order - Active Order --: {self.activeOrders}")

    def did_expire_order(self, event: OrderExpiredEvent):
        self.activeOrders -= 1
        logging.info(f"Expired Order - Active Order --: {self.activeOrders}")

    def did_fail_order(self, event: MarketOrderFailureEvent):
        self.activeOrders -= 1
        logging.info(f"Failed Order - Active Order --: {self.activeOrders}")

    def did_fill_order(self, event: OrderFilledEvent):
        logging.info(f"Filled Order - Active Order ??: {self.activeOrders}")
