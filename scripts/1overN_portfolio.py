import decimal
import logging
from decimal import Decimal

from hummingbot.core.data_type.common import OrderType
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class OneOverNPortfolio(ScriptStrategyBase):
    """
    This strategy aims to create a 1/N cryptocurrency portfolio, providing perfect diversification without
    parametrization and giving a reasonable baseline performance.
    """

    exchange = "binance_paper_trade"
    quote_currency = "USDT"
    base_currencies = ["BTC", "ETH", "ONE"]
    pairs = {f"{currency}-USDT" for currency in base_currencies}

    #: Define markets to instruct Hummingbot to create connectors on the exchanges and markets you need
    markets = {exchange: pairs}
    activeOrders = 0

    def on_tick(self):
        # TODO: checking for active orders works ONLY with LIMIT orders. Ask why. Find a better solution to the problem
        #       of atomic transactions on exchanges.
        if 0 < self.activeOrders:
            self.logger().info(f"Wait until all active orders have completed: {self.activeOrders}")
            return

        connector = self.connectors[self.exchange]
        #: check current balance of coins
        balance_df = self.get_balance_df()
        #: Filter by exchange "binance_paper_trade"
        exchange_balance_df = balance_df.loc[balance_df["Exchange"] == self.exchange]
        #: Create a dictionary with asset name as key and total and available balance measured in base currencies
        base_balances = {}
        for _, row in exchange_balance_df.iterrows():
            asset_name = row["Asset"]
            if asset_name in self.base_currencies:
                total_balance = Decimal(row["Total Balance"])
                available_balance = Decimal(row["Available Balance"])
                base_balances[asset_name] = (total_balance, available_balance)
                self.logger().info(f"Available Balance in pieces: {available_balance} {asset_name}")

        #: Multiply each balance with the current price to get the balances in the quote currency
        quote_balances = {}
        for asset, balances in base_balances.items():
            trading_pair = f"{asset}-{self.quote_currency}"
            # TODO: should I put the amount to buy sell to get a orderbook conform value?
            # noinspection PyUnresolvedReferences
            current_price = Decimal(connector.get_mid_price(trading_pair))
            total_balance = balances[0] * current_price
            available_balance = balances[1] * current_price
            quote_balances[asset] = (total_balance, available_balance, current_price)
            self.logger().info(
                f"Available Balance {asset} * {current_price} {self.quote_currency} = {available_balance} {self.quote_currency}")
        #: Sum the available balances
        # TODO: add quote_currency balance correctly so that the full amount can be traded and it is not stuck when trades are canceled etc.
        total_available_balance = sum(balances[1] for balances in quote_balances.values())
        self.logger().info(f"TOT ({self.quote_currency}): {total_available_balance}")
        self.logger().info(
            f"TOT/{len(self.base_currencies)} ({self.quote_currency}): {total_available_balance / len(self.base_currencies)}")
        #: Calculate the percentage of each available_balance over total_available_balance
        percentages_dict = {}
        for asset, balances in quote_balances.items():
            available_balance = balances[1]
            percentage = (available_balance / total_available_balance)
            percentages_dict[asset] = percentage
            self.logger().info(f"Total share {asset}: {percentage * 100}%")
        number_of_assets = Decimal(len(quote_balances))
        #: Calculate the difference between each percentage and 1/number_of_assets
        differences_dict = {}
        for asset, percentage in percentages_dict.items():
            deficit = (Decimal('1') / number_of_assets) - percentage
            differences_dict[asset] = deficit
            self.logger().info(f"Missing from 1/N {asset}: {deficit * 100}%")

        # Calculate the absolute differences in quote currency
        # TODO: if we have any assets in quote currency left in the bank we need to trade it too. This can easily happen
        #       when orders get canceled. By doing so we can also fund the fonds with new cash in that way.
        differences_in_quote_currency = {}
        for asset, deficit in differences_dict.items():
            # TODO: take the bid when selling and ask when buying? generally take the price from the rate oracle
            #  instead from the exchange? this would imply (potentially) more price stability across exchanges if the
            #  source is adjusted
            current_price = quote_balances[asset][2]
            difference_in_quote_currency = deficit / current_price  # TODO: rename it to  deficit_over_price
            differences_in_quote_currency[asset] = difference_in_quote_currency
        #: Calculate the difference in pieces of each base asset
        differences_in_base_asset = {}
        for asset, deficit in differences_in_quote_currency.items():
            differences_in_base_asset[asset] = deficit * total_available_balance
        #: Create an ordered list of asset-deficit pairs starting from the smallest negative deficit ending with the
        #  biggest positive deficit
        ordered_trades = sorted(differences_in_base_asset.items(), key=lambda x: x[1])
        #: log the planned ordered trades with sequence number
        for i, (asset, deficit) in enumerate(ordered_trades):
            trade_number = i + 1
            trade_type = "sell" if deficit < Decimal('0') else "buy"
            self.logger().info(f"Trade {trade_number}: {trade_type} {asset}: {deficit}")
        for i, (asset, deficit) in enumerate(ordered_trades):
            # TODO: this is a quick fix to the trade engine error. We don't trade under 1 quote value, e.g. dollar.
            #  This is even a feature parameter that we can use to save trading fees.
            quote_price = quote_balances[asset][2]
            if abs(deficit * quote_price) < 1:
                self.logger().info(f"{abs(deficit * quote_price)} < 1 too small to trade")
                continue
            trade_is_buy = True if deficit > Decimal('0') else False
            try:
                if trade_is_buy:
                    self.buy(connector_name=self.exchange, trading_pair=f"{asset}-{self.quote_currency}",
                             amount=abs(deficit), order_type=OrderType.MARKET, price=quote_price)
                else:
                    self.sell(connector_name=self.exchange, trading_pair=f"{asset}-{self.quote_currency}",
                              amount=abs(deficit), order_type=OrderType.MARKET, price=quote_price)
            except decimal.InvalidOperation as e:
                # Handle the error by logging it or taking other appropriate actions
                print(f"Caught an error: {e}")
                self.activeOrders -= 1
        return

    # TODO: def format status def format_status(self) -> str:

    def did_create_buy_order(self, *args, **kwargs):
        self.activeOrders += 1
        logging.info(f"Created Buy - Active Orders ++: {self.activeOrders}")

    def did_create_sell_order(self, *args, **kwargs):
        self.activeOrders += 1
        logging.info(f"Created Sell - Active Orders ++: {self.activeOrders}")

    def did_complete_buy_order(self, *args, **kwargs):
        self.activeOrders -= 1
        logging.info(f"Completed Buy - Active Orders --: {self.activeOrders}")

    def did_complete_sell_order(self, *args, **kwargs):
        self.activeOrders -= 1
        logging.info(f"Completed Sell - Active Orders --: {self.activeOrders}")

    def did_cancel_order(self, *args, **kwargs):
        self.activeOrders -= 1
        logging.info(f"Canceled Order - Active Order --: {self.activeOrders}")

    def did_expire_order(self, *args, **kwargs):
        self.activeOrders -= 1
        logging.info(f"Expired Order - Active Order --: {self.activeOrders}")

    def did_fail_order(self, *args, **kwargs):
        self.activeOrders -= 1
        logging.info(f"Failed Order - Active Order --: {self.activeOrders}")

    def did_fill_order(self, *args, **kwargs):
        logging.info(f"Filled Order - Active Order ??: {self.activeOrders}")
