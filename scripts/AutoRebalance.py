import logging
from decimal import Decimal

import numpy as np
import pandas as pd
import requests

from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderFilledEvent,
    OrderType,
    SellOrderCompletedEvent,
    SellOrderCreatedEvent,
)
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase

# ------------------------------------------------------------------------------------------- #


def abstract_keys(coins_dict):
    # Abstract coin name
    coins = []
    for coin in coins_dict.keys():
        coins.append(coin)
    return coins


def make_pairs(coins, hold_asset):
    # Make coin list
    pairs = []
    for coin in coins:
        pair = coin + "-" + hold_asset
        pairs.append(pair)
    return pairs


def get_klines(pair, interval, limit):
    url = "https://data.binance.com/api/v3/klines"
    params = {"symbol": pair.replace("-", ""),
              "interval": interval, 'limit': limit}
    klines = requests.get(url=url, params=params).json()
    df = pd.DataFrame(klines)
    df = df.drop(columns={6, 7, 8, 9, 10, 11})
    df = df.rename(columns={0: 'timestamps', 1: 'open', 2: 'high', 3: 'low', 4: 'close', 5: 'volume', })
    df = df.fillna(0)
    df[["open", "high", "low", "close", "volume"]] = df[["open", "high", "low", "close", "volume"]].astype(float)
    df['timestamps'] = pd.to_datetime(df['timestamps'], unit='ms')

    return df


def tr(data):
    data['previous_close'] = data['close'].shift(1)
    data['high-low'] = abs(data['high'] - data['low'])
    data['high-pc'] = abs(data['high'] - data['previous_close'])
    data['low-pc'] = abs(data['low'] - data['previous_close'])

    _tr = data[['high-low', 'high-pc', 'low-pc']].max(axis=1)

    return _tr


def atr(data, period):
    data['tr'] = tr(data)
    _atr = data['tr'].rolling(period).mean()

    return _atr


def supertrend(data, period=13, atr_multiplier=3.):
    hl2 = (data['high'] + data['low']) / 2
    data['atr'] = atr(data, period)
    data['upperband'] = hl2 + (atr_multiplier * data['atr'])
    data['lowerband'] = hl2 - (atr_multiplier * data['atr'])
    data['in_uptrend'] = True

    for current in range(1, len(data.index)):
        previous = current - 1

        if data['close'][current] > data['upperband'][previous]:
            data.loc[current, 'in_uptrend'] = True
        elif data['close'][current] < data['lowerband'][previous]:
            data.loc[current, 'in_uptrend'] = False
        else:
            data.loc[current, 'in_uptrend'] = data['in_uptrend'][previous]

            if data['in_uptrend'][current] and data['lowerband'][current] < data['lowerband'][previous]:
                data.loc[current, 'lowerband'] = data['lowerband'][previous]

            if not data['in_uptrend'][current] and data['upperband'][current] > data['upperband'][previous]:
                data.loc[current, 'upperband'] = data['upperband'][previous]

    return data


# ------------------------------------------------------------------------------------------- #

class AutoRebalance(ScriptStrategyBase):
    # Set connector name
    connector_name = str("binance_paper_trade")

    # Set long and short atr configuration
    s_atr_period = int(13)
    l_atr_period = int(34)

    # Set SuperTrend configuration
    trend_atr_period = int(13)
    atr_mult = float(2.618)

    # Not binance only accept intervals >> 1m, 3m, 5m ,15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w
    interval = str("15m")
    if str("m") in interval:
        data_interval = interval.replace(str("m"), str(""))
        data_interval = int(data_interval)
        data_interval = int(data_interval * 60)
    elif "h" in interval:
        data_interval = interval.replace(str("h"), str(""))
        data_interval = int(data_interval)
        data_interval = int(data_interval * 60 * 60)
    elif "d" in interval:
        data_interval = interval.replace(str("d"), str(""))
        data_interval = int(data_interval)
        data_interval = int(data_interval * 60 * 60 * 24)
    elif "w" in interval:
        data_interval = interval.replace(str("w"), str(""))
        data_interval = int(data_interval)
        data_interval = int(data_interval * 60 * 60 * 24 * 7)

    limit = int(60)  # Should be more than l_atr_period

    # Set hold asset configuration
    hold_asset_weight = {"BUSD": Decimal('0.00')}  # Initialize hold_asset_weight

    # Set a list of coins configurations
    ut_coin_weight = {
        "BTC": Decimal('20.00'),
        "ETH": Decimal('15.00'),
        "BNB": Decimal('15.00'),
        "AVAX": Decimal('15.00'),
        "MATIC": Decimal('15.00')
    }
    dt_coin_weight = {
        "BTC": Decimal('10.00'),
        "ETH": Decimal('10.00'),
        "BNB": Decimal('10.00'),
        "AVAX": Decimal('10.00'),
        "MATIC": Decimal('10.00')
    }
    coin_weight = dt_coin_weight  # Initialize coin_weight

    # Set rebalance threshold
    ut_threshold = {
        "BTC": Decimal('2.00'),
        "ETH": Decimal('2.00'),
        "BNB": Decimal('2.00'),
        "AVAX": Decimal('2.00'),
        "MATIC": Decimal('2.00')
    }
    dt_threshold = {
        "BTC": Decimal('1.00'),
        "ETH": Decimal('1.00'),
        "BNB": Decimal('1.00'),
        "AVAX": Decimal('1.00'),
        "MATIC": Decimal('1.00')
    }
    threshold = dt_threshold  # Initialize threshold

    # Initialize timestamp and order time
    last_ordered_ts = int(0)
    order_interval = int(60)

    # Abstract coin name and Make coin list
    hold_asset = abstract_keys(hold_asset_weight)[0]
    coins = abstract_keys(coin_weight)
    pairs = make_pairs(coins, hold_asset)

    # Put connector and pairs into markets
    markets = {connector_name: pairs}

    # Create trend dict
    coin_trend = {}
    for coin in coins:
        coin_trend[coin] = False

    # Create volatile dict
    coin_volatile = {}
    for coin in coins:
        coin_volatile[coin] = False

    # Set status
    status = "rebalancing"

    # Set initial data trigger
    have_data = False

    # ------------------------------------------------------------------------------------------- #

    @property
    def connector(self):
        """
        The only connector in this strategy, define it here for easy access
        """
        return self.connectors[self.connector_name]

    # ------------------------------------------------------------------------------------------- #

    def on_tick(self):
        # Get initial data
        if self.have_data is False:
            self.logger().info("Time to get new data !!!")
            self.threshold = {}
            self.coin_weight = {}

            for coin in self.coins:
                market = coin + "-" + self.hold_asset
                kline_df = get_klines(market, self.interval, self.limit)

                kline_df['s_atr'] = atr(kline_df, self.s_atr_period)
                kline_df.drop(columns=['previous_close', 'high-low', 'high-pc', 'low-pc', 'tr'], axis=1,
                              inplace=True)
                s_atr = kline_df.iloc[-1]['s_atr']
                kline_df['l_atr'] = atr(kline_df, self.l_atr_period)
                kline_df.drop(columns=['previous_close', 'high-low', 'high-pc', 'low-pc', 'tr'], axis=1,
                              inplace=True)
                l_atr = kline_df.iloc[-1]['l_atr']
                self.coin_volatile[coin] = bool(s_atr > l_atr)

                # Set threshold according to volatility and Log threshold settings
                if self.coin_volatile[coin] is True:
                    self.threshold[coin] = self.ut_threshold[coin]
                    self.logger().info(coin + f" Market is volatile? {self.coin_volatile[coin]}")
                    self.logger().info(f"Set {coin} threshold: {self.threshold[coin]}")
                elif self.coin_volatile[coin] is False:
                    self.threshold[coin] = self.dt_threshold[coin]
                    self.logger().info(coin + f" Market is volatile? {self.coin_volatile[coin]}")
                    self.logger().info(f"Set {coin} threshold: {self.threshold[coin]}")

                # Calculate supertrend
                _supertrend = supertrend(kline_df, self.trend_atr_period, self.atr_mult)
                _supertrend.drop(columns=['high-low', 'high-pc', 'low-pc', 'tr'], axis=1, inplace=True)
                self.coin_trend[coin] = bool(_supertrend.iloc[-1]['in_uptrend'])

                # Set target weight according to trend
                if self.coin_trend[coin] is True:
                    self.coin_weight[coin] = self.ut_coin_weight[coin]
                    self.logger().info(coin + f" Market is UpTrend? {self.coin_trend[coin]}")
                    self.logger().info(f"Set {coin} weight: {self.coin_weight[coin]}")
                elif self.coin_trend[coin] is False:
                    self.coin_weight[coin] = self.dt_coin_weight[coin]
                    self.logger().info(coin + f" Market is UpTrend? {self.coin_trend[coin]}")
                    self.logger().info(f"Set {coin} weight: {self.coin_weight[coin]}")

            total_value = sum(self.coin_weight.values())
            new_value = Decimal('100.00') - total_value
            self.hold_asset_weight["BUSD"] = new_value
            self.logger().info(f"Set {self.hold_asset} weight: {self.hold_asset_weight['BUSD']}")

            self.have_data = True

        # Check if it is time to get new data
        elif self.current_timestamp == ((self.current_timestamp // self.data_interval) *
                                        self.data_interval) and self.have_data is True:
            self.logger().info("Time to get new data !!!")
            self.threshold = {}
            self.coin_weight = {}

            for coin in self.coins:
                market = coin + "-" + self.hold_asset
                kline_df = get_klines(market, self.interval, self.limit)

                kline_df['s_atr'] = atr(kline_df, self.s_atr_period)
                kline_df.drop(columns=['previous_close', 'high-low', 'high-pc', 'low-pc', 'tr'], axis=1,
                              inplace=True)
                s_atr = kline_df.iloc[-1]['s_atr']
                kline_df['l_atr'] = atr(kline_df, self.l_atr_period)
                kline_df.drop(columns=['previous_close', 'high-low', 'high-pc', 'low-pc', 'tr'], axis=1,
                              inplace=True)
                l_atr = kline_df.iloc[-1]['l_atr']
                self.coin_volatile[coin] = bool(s_atr > l_atr)

                # Set threshold according to volatility and Log threshold settings
                if self.coin_volatile[coin] is True:
                    self.threshold[coin] = self.ut_threshold[coin]
                    self.logger().info(coin + f" Market is volatile? {self.coin_volatile[coin]}")
                    self.logger().info(f"Set {coin} threshold: {self.threshold[coin]}")
                elif self.coin_volatile[coin] is False:
                    self.threshold[coin] = self.dt_threshold[coin]
                    self.logger().info(coin + f" Market is volatile? {self.coin_volatile[coin]}")
                    self.logger().info(f"Set {coin} threshold: {self.threshold[coin]}")

                # Calculate supertrend
                _supertrend = supertrend(kline_df, self.trend_atr_period, self.atr_mult)
                _supertrend.drop(columns=['high-low', 'high-pc', 'low-pc', 'tr'], axis=1, inplace=True)
                self.coin_trend[coin] = bool(_supertrend.iloc[-1]['in_uptrend'])

                # Set target weight according to trend
                if self.coin_trend[coin] is True:
                    self.coin_weight[coin] = self.ut_coin_weight[coin]
                    self.logger().info(coin + f" Market is UpTrend? {self.coin_trend[coin]}")
                    self.logger().info(f"Set {coin} weight: {self.coin_weight[coin]}")
                elif self.coin_trend[coin] is False:
                    self.coin_weight[coin] = self.dt_coin_weight[coin]
                    self.logger().info(coin + f" Market is UpTrend? {self.coin_trend[coin]}")
                    self.logger().info(f"Set {coin} weight: {self.coin_weight[coin]}")

            total_value = sum(self.coin_weight.values())
            new_value = Decimal('100.00') - total_value
            self.hold_asset_weight["BUSD"] = new_value
            self.logger().info(f"Set {self.hold_asset} weight: {self.hold_asset_weight['BUSD']}")

        # Check if it is time to rebalance
        if self.last_ordered_ts < (self.current_timestamp - self.order_interval):
            self.logger().info("Check if rebalance is needed !!!")
            # Calculate all coins weight
            current_weight = self.get_current_weight(self.coins)
            # Cancel all orders
            self.cancel_all_orders()

            # Run over all coins
            for coin in self.coins:
                pair = coin + "-" + self.hold_asset
                if current_weight[coin] >= \
                        (Decimal((self.coin_weight[coin] / 100)) * (Decimal('1.00') + (self.threshold[coin] / 100))) \
                        and self.order_amount(coin, self.coins) * self.sell_order_price(pair) > Decimal('10.00'):
                    self.sell(self.connector_name, pair, self.order_amount(coin, self.coins), OrderType.LIMIT,
                              self.sell_order_price(pair))
                elif current_weight[coin] <= \
                        ((Decimal(self.coin_weight[coin] / 100)) * (Decimal('1.00') - (self.threshold[coin] / 100))) \
                        and self.order_amount(coin, self.coins) * self.buy_order_price(pair) > Decimal('10.00'):
                    self.buy(self.connector_name, pair, self.order_amount(coin, self.coins), OrderType.LIMIT,
                             self.buy_order_price(pair))

            if len(self.get_active_orders(self.connector_name)) != 0:
                self.logger().info("Rebalancing.....")
                self.status = str("rebalancing")
            else:
                self.logger().info("Waiting.....")
                self.status = str("waiting")

            # Set timestamp
            self.last_ordered_ts = self.current_timestamp

    def get_current_value(self, coins):
        """
        Get current value of each coin and make it a dictionary
        """
        exchange = self.connector
        current_value = {}
        for coin in coins:
            pair = coin + "-" + self.hold_asset
            current_value[coin] = Decimal((exchange.get_balance(coin) *
                                           exchange.get_mid_price(pair))).quantize(Decimal('1.0000'))
        return current_value

    def get_total_value(self, coins):
        """
        Get Sum of all value
        """
        exchange = self.connector
        total_value = exchange.get_balance(self.hold_asset)
        current_value = self.get_current_value(coins)
        for coin in current_value:
            total_value = total_value + current_value[coin]
        return total_value

    def get_current_weight(self, coins):
        """
        Get current weight of each coin
        """
        total_value = self.get_total_value(coins)
        current_value_dict = self.get_current_value(coins)
        current_weight = {}
        for coin in coins:
            current_value = current_value_dict[coin]
            current_weight[coin] = Decimal((current_value / total_value)).quantize(Decimal('1.0000'))
        return current_weight

    def order_amount(self, coin, coins):
        """
        Calculate order amount
        """
        exchange = self.connector
        pair = coin + "-" + self.hold_asset
        order_amount = Decimal((self.get_current_value(coins)[coin] -
                                (self.get_total_value(coins) * (self.coin_weight[coin] / 100))) /
                               exchange.get_mid_price(pair)).quantize(Decimal('1.000'))
        order_amount = abs(order_amount)
        return order_amount

    def sell_order_price(self, pair):
        exchange = self.connector
        sell_order_price = Decimal(exchange.get_price(pair, True) * Decimal('1.0001')).quantize(Decimal('1.0000'))
        return sell_order_price

    def buy_order_price(self, pair):
        exchange = self.connector
        buy_order_price = Decimal(exchange.get_price(pair, False) * Decimal('0.9999')).quantize(Decimal('1.0000'))
        return buy_order_price

    def cancel_all_orders(self):
        """
        Cancel all orders from the bot
        """
        for order in self.get_active_orders(connector_name=self.connector_name):
            self.cancel(self.connector_name, order.trading_pair, order.client_order_id)

    # ------------------------------------------------------------------------------------------- #

    def did_create_buy_order(self, event: BuyOrderCreatedEvent):
        """
        Method called when the connector notifies a buy order has been created
        """
        self.logger().info(logging.INFO, f"The buy order {event.order_id} has been created")

    def did_create_sell_order(self, event: SellOrderCreatedEvent):
        """
        Method called when the connector notifies a sell order has been created
        """
        self.logger().info(logging.INFO, f"The sell order {event.order_id} has been created")

    def did_fill_order(self, event: OrderFilledEvent):
        """
        Method called when the connector notifies that an order has been partially or totally filled (a trade happened)
        """
        self.logger().info(logging.INFO, f"The order {event.order_id} has been filled")

    def did_fail_order(self, event: MarketOrderFailureEvent):
        """
        Method called when the connector notifies an order has failed
        """
        self.logger().info(logging.INFO, f"The order {event.order_id} failed")

    def did_cancel_order(self, event: OrderCancelledEvent):
        """
        Method called when the connector notifies an order has been cancelled
        """
        self.logger().info(f"The order {event.order_id} has been cancelled")

    def did_complete_buy_order(self, event: BuyOrderCompletedEvent):
        """
        Method called when the connector notifies a buy order has been completed (fully filled)
        """
        self.logger().info(f"The buy order {event.order_id} has been completed")

    def did_complete_sell_order(self, event: SellOrderCompletedEvent):
        """
        Method called when the connector notifies a sell order has been completed (fully filled)
        """
        self.logger().info(f"The sell order {event.order_id} has been completed")

    def format_status(self) -> str:
        """
        Returns status of the current strategy on user balances and current active orders. This function is called
        when status command is issued. Override this function to create custom status display output.
        """
        if not self.ready_to_trade:
            return "Market connectors are not ready."
        lines = []
        warning_lines = []
        warning_lines.extend(self.network_warning(self.get_market_trading_pair_tuples()))

        balance_df = self.get_balance_df().drop('Exchange', axis=1)

        asset = self.coins + [self.hold_asset]

        current_value = []
        for coin in self.get_current_value(self.coins):
            current_value.append(self.get_current_value(self.coins)[coin])
        current_value.append(Decimal((self.connector.get_balance(self.hold_asset))).quantize(Decimal('1.00')))

        current_weight = []
        current_weight_total = Decimal('0.0000')
        for coin in self.get_current_weight(self.coins):
            current_weight_total = current_weight_total + self.get_current_weight(self.coins)[coin]
            current_weight.append(self.get_current_weight(self.coins)[coin])
        hold_asset_current_weight = Decimal('1.0000') - current_weight_total
        current_weight.append(hold_asset_current_weight)

        target_weight = []
        for coin in self.coin_weight.values():
            target_weight.append(coin)
        target_weight.append(self.hold_asset_weight[self.hold_asset])

        weight_df = pd.DataFrame({
            "Asset": asset,
            "Current Value": current_value,
            "Current Weight": current_weight,
            "Target Weight": target_weight
        })
        weight_df["Current Weight"] = weight_df["Current Weight"].apply(lambda x: '%.2f%%' % (x * 100))
        weight_df["Target Weight"] = weight_df["Target Weight"].apply(lambda x: '%.2f%%' % x)
        account_data = pd.merge(left=balance_df, right=weight_df, how='left', on='Asset')

        lines.extend(["", f"  Exchange: {self.connector_name}" +
                      f"  Status: {self.status}"])
        lines.extend(["", "  Balances:\n"] +
                     ["  " + line for line in account_data.to_string(index=False).split("\n")])

        lines.extend(["", "  ------------------------------------------------------------------------------------"])

        lines.extend(["", "  Active Orders:\n"])
        try:
            active_order = self.active_orders_df().drop('Exchange', axis=1)
            lines.extend(["  " + line for line in active_order.to_string(index=False).split("\n")])
        except ValueError:
            lines.extend(["", "  No active maker orders."])

        lines.extend(["", "  ------------------------------------------------------------------------------------"])

        lines.extend(["", "  Trend Info:\n"])
        lines.extend([f" | ATR Short period: {np.round(self.s_atr_period, 4)}      |" +
                      f" ATR Long period: {np.round(self.l_atr_period, 4)}            |"])
        lines.extend([f" | SuperTrend ATR period: {self.trend_atr_period} |" +
                      f" SuperTrend ATR multiplier: {self.atr_mult} |\n"])

        df = pd.DataFrame(index=list(self.coins), columns=["Uptrend", "Volatile"])
        for coin in self.coins:
            df.at[coin, 'Uptrend'] = self.coin_trend[coin]
            df.at[coin, 'Threshold'] = self.threshold[coin]
            df.at[coin, 'Volatile'] = self.coin_volatile[coin]

        df = df.reset_index()
        df.rename(columns={'index': 'Asset'}, inplace=True)
        new_df = pd.merge(df, account_data, on='Asset')
        new_df['Target Weight'] = new_df['Target Weight'].apply(lambda x: float(x.strip('%')) / 100)
        new_df['Current Weight'] = new_df['Current Weight'].apply(lambda x: float(x.strip('%')) / 100)
        new_df['Weight Diff'] = new_df['Current Weight'] - new_df['Target Weight']
        new_df['Weight Diff'] = new_df['Weight Diff'].apply(lambda x: '%.2f%%' % (x * 100))
        df['Weight Diff'] = new_df.loc[df.index, 'Weight Diff']
        df['Threshold'] = df['Threshold'].apply(lambda x: '%.2f%%' % x)
        columns = ['Asset', 'Uptrend', 'Weight Diff', 'Volatile', 'Threshold']
        df = df[columns]
        df.sort_values(by='Asset', ascending=True, inplace=True)
        lines.extend(["  " + line for line in df.to_string(index=False).split("\n")])

        lines.extend(["", "  ------------------------------------------------------------------------------------"])

        warning_lines.extend(self.balance_warning(self.get_market_trading_pair_tuples()))
        if len(warning_lines) > 0:
            lines.extend(["", "*** WARNINGS ***"] + warning_lines)
        return "\n".join(lines)
