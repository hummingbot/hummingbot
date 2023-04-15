from decimal import Decimal

from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase

EXCHANGE = "binance_paper_trade"


class OneOverNPortfolio(ScriptStrategyBase):
    """
    This strategy aims to create a 1/N cryptocurrency portfolio, providing perfect diversification without parametrization and giving a reasonable baseline performance.
    """

    base_currency = "USDT"
    quote_currencies = ["BTC", "ETH", "ONE"]
    pairs = {f"{currency}-USDT" for currency in quote_currencies}

    #: Define markets to instruct Hummingbot to create connectors on the exchanges and markets you need
    markets = {EXCHANGE: pairs}

    def on_tick(self):
        connector = self.connectors[EXCHANGE]
        #: check current balance of coins
        balance_df = self.get_balance_df()
        #: Filter by exchange "binance_paper_trade"
        exchange_balance_df = balance_df.loc[balance_df["Exchange"] == EXCHANGE]
        #: Create a dictionary with asset name as key and total and available balance measuered in quote currencies
        quote_balances = {}
        for _, row in exchange_balance_df.iterrows():
            asset_name = row["Asset"]
            if asset_name in self.quote_currencies:
                total_balance = Decimal(row["Total Balance"])
                available_balance = Decimal(row["Available Balance"])
                quote_balances[asset_name] = (total_balance, available_balance)
                self.logger().info(f"Available Balance in pieces: {available_balance} {asset_name}")

        #: Multiply each balance with the current price to get the balances in the base currency
        base_balances = {}
        for asset, balances in quote_balances.items():
            trading_pair = f"{asset}-{self.base_currency}"
            # TODO: should I put the amount to buy sell to get a orderbook conform value?
            current_price = Decimal(connector.get_price(trading_pair, is_buy=False))
            total_balance = balances[0] * current_price
            available_balance = balances[1] * current_price
            base_balances[asset] = (total_balance, available_balance, current_price)
            self.logger().info(
                f"Available Balance {asset} * {current_price} {self.base_currency} = {available_balance} {self.base_currency}")
        #: Sum the available balances
        total_available_balance = sum(balances[1] for balances in base_balances.values())
        self.logger().info(f"TOT ({self.base_currency}): {total_available_balance}")
        self.logger().info(
            f"TOT/{len(self.quote_currencies)} ({self.base_currency}): {total_available_balance / len(self.quote_currencies)}")
        #: Calculate the percentage of each available_balance over total_available_balance
        percentages_dict = {}
        for asset, balances in base_balances.items():
            available_balance = balances[1]
            percentage = (available_balance / total_available_balance)
            percentages_dict[asset] = percentage
            self.logger().info(f"Total share {asset}: {percentage * 100}%")
        number_of_assets = Decimal(len(base_balances))
        #: Calculate the difference between each percentage and 1/number_of_assets
        differences_dict = {}
        for asset, percentage in percentages_dict.items():
            deficit = (Decimal('1') / number_of_assets) - percentage
            differences_dict[asset] = deficit
            self.logger().info(f"Missing from 1/N {asset}: {deficit * 100}%")

        # Calculate the absolute differences in base currency
        differences_in_base_currency = {}
        for asset, deficit in differences_dict.items():
            trading_pair = f"{asset}-{self.base_currency}"
            # TODO: take the bid when selling and ask when buying? get_mid_price seems not available anymore?
            current_price = Decimal(connector.get_price(trading_pair, is_buy=True if deficit < 0 else False))
            difference_in_base_currency = deficit / current_price
            differences_in_base_currency[asset] = difference_in_base_currency
        #: Calculate the difference in pieces of each quote asset
        differences_in_quote_asset = {}
        for asset, deficit in differences_in_base_currency.items():
            differences_in_quote_asset[asset] = deficit * total_available_balance
        for asset, deficit in differences_in_quote_asset.items():
            self.logger().info(f" Need to Trade {asset}: {deficit}")
        HummingbotApplication.main_application().stop()
        return
    # TODO: def format status def format_status(self) -> str:
