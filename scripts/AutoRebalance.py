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
    connector_name = "binance_paper_trade"

    # Initialize timestamp and order time
    last_ordered_ts = 0.
    order_interval = 60.

    # Set hold asset configuration
    ut_hold_asset_config = {"BUSD": Decimal('20.00')}
    dt_hold_asset_config = {"BUSD": Decimal('50.00')}
    hold_asset_config = ut_hold_asset_config  # Initialize hold_asset_config

    # Set a list of coins configurations
    ut_coin_config = {
        "BTC": Decimal('25.00'),
        "ETH": Decimal('20.00'),
        "BNB": Decimal('15.00'),
        "RNDR": Decimal('10.00'),
        "DOGE": Decimal('10.00')
    }
    dt_coin_config = {
        "BTC": Decimal('20.00'),
        "ETH": Decimal('10.00'),
        "BNB": Decimal('10.00'),
        "RNDR": Decimal('5.00'),
        "DOGE": Decimal('5.00')
    }
    coin_config = ut_coin_config  # Initialize coin_config

    # Set rebalance threshold
    ut_threshold = Decimal('1.00')
    dt_threshold = Decimal('0.50')
    threshold = dt_threshold  # Initialize threshold

    # Abstract coin name and Make coin list
    hold_asset = abstract_keys(hold_asset_config)[0]
    coins = abstract_keys(coin_config)
    pairs = make_pairs(coins, hold_asset)

    # Put connector and pairs into markets
    markets = {connector_name: pairs}

    # Set status
    status = "rebalancing"

    # Set active order or not
    mm_mode = True

    # Set klines configuration
    last_data_ts = 0.
    data_interval = 60  # Should be equal to interval
    interval = "1m"
    limit = 34  # Should be more than l_atrR_period

    # Set long and short atr configuration
    s_atr_period = 13
    l_atr_period = 34
    s_atr_list = []  # Placeholder
    l_atr_list = []  # Placeholder
    s_atr_mean = 0.  # Placeholder
    l_atr_mean = 0.  # Placeholder
    is_volatile = True  # Initialize is_volatile

    # Set SuperTrend configuration
    trend_atr_period = 13
    atr_mult = 3.
    upperband = 0.  # Placeholder
    lowerband = 0.  # Placeholder
    preclose = 0.  # Placeholder
    supertrend_atr = 0.  # Placeholder
    is_uptrend = True  # Initialize is_uptrend
    _supertrend = pd.DataFrame()  # initialize _supertrend df

    # Set market making threshold
    mm_threshold = Decimal('0.00')

    @property
    def connector(self):
        """
        The only connector in this strategy, define it here for easy access
        """
        return self.connectors[self.connector_name]

    def on_tick(self):
        exchange = self.connector

        if self.last_data_ts < (self.current_timestamp - self.data_interval):
            self.logger().info("Time to get new data !!!")
            df_all = pd.DataFrame()

            for coin in self.coins:
                pair = coin + "-" + self.hold_asset
                all_df = get_klines(pair, self.interval, self.limit)

                # ATR indicator
                # Calculate long and short ATR
                all_df['s_atr'] = atr(all_df, self.s_atr_period)
                s_atr = all_df.iloc[-1]['s_atr']
                self.s_atr_list.append(s_atr)
                all_df['l_atr'] = atr(all_df, self.l_atr_period)
                l_atr = all_df.iloc[-1]['l_atr']
                self.l_atr_list.append(l_atr)

                # Prepare df for supertrend
                s_df = all_df.select_dtypes(exclude=["datetime"])
                df_all = df_all.add(s_df, fill_value=0)
                all_df[s_df.columns] = s_df.add(df_all)
                self._supertrend = supertrend(all_df, self.trend_atr_period, self.atr_mult)

            s_atr_sum = sum(self.s_atr_list)
            self.s_atr_mean = s_atr_sum / len(self.s_atr_list)
            l_atr_sum = sum(self.l_atr_list)
            self.l_atr_mean = l_atr_sum / len(self.l_atr_list)
            self.is_volatile = bool(self.s_atr_mean > self.l_atr_mean)

            # SuperTrend indicator
            self.upperband = self._supertrend.iloc[-1]['upperband']
            self.lowerband = self._supertrend.iloc[-1]['lowerband']
            self.preclose = self._supertrend.iloc[-1]['previous_close']
            self.supertrend_atr = self._supertrend.iloc[-1]['atr']
            self.is_uptrend = bool(self._supertrend.iloc[-1]['in_uptrend'])

            # Set threshold according to volatility
            if self.is_volatile is False:
                self.threshold = self.dt_threshold
                self.logger().info(f"Market is volatile? {self.is_volatile}")
                self.logger().info(f"Set threshold: {self.threshold}")
            else:
                self.threshold = self.ut_threshold
                self.logger().info(f"Market is volatile? {self.is_volatile}")
                self.logger().info(f"Set threshold: {self.threshold}")

            # Set coins ratio according to the trend
            if self.is_uptrend is True:
                self.hold_asset_config = self.ut_hold_asset_config
                self.coin_config = self.ut_coin_config
                self.logger().info(f"Market is UpTrend? {self.is_uptrend}")
                self.logger().info(f"Set coin config: {self.hold_asset_config} and {self.coin_config}")

            else:
                self.hold_asset_config = self.dt_hold_asset_config
                self.coin_config = self.dt_coin_config
                self.logger().info(f"Market is UpTrend? {self.is_uptrend}")
                self.logger().info(f"Set coin config: {self.hold_asset_config} and {self.coin_config}")

            # Update data timestamp
            self.last_data_ts = self.current_timestamp

        # Check if it is time to rebalance
        if self.last_ordered_ts < (self.current_timestamp - self.order_interval):

            # Calculate all coins weight
            current_weight = self.get_current_weight(self.coins)
            # Cancel all orders
            self.cancel_all_orders()

            # Run over all coins
            for coin in self.coins:
                pair = coin + "-" + self.hold_asset
                if current_weight[coin] >= \
                        (Decimal((self.coin_config[coin] / 100)) * (Decimal('1.00') + (self.threshold / 100))):
                    self.status = "rebalancing"
                    self.sell(self.connector_name, pair, self.order_amount(coin, self.coins), OrderType.LIMIT,
                              Decimal(exchange.get_price(pair, True) * Decimal('1.0001')).quantize(Decimal('1.0000')))
                elif current_weight[coin] <= \
                        ((Decimal(self.coin_config[coin] / 100)) * (Decimal('1.00') - (self.threshold / 100))):
                    self.status = "rebalancing"
                    self.buy(self.connector_name, pair, self.order_amount(coin, self.coins), OrderType.LIMIT,
                             Decimal(exchange.get_price(pair, False) * Decimal('0.9999')).quantize(Decimal('1.0000')))

            if self.mm_mode is True:
                self.mm_threshold = self.threshold
                if self.status == "rebalancing":
                    try:
                        self.active_orders_df()
                    except ValueError:
                        self.status = "market making"

                # If not run rebalancing then do market making
                if self.status == "market making":
                    for coin in self.coins:
                        sell_order_amount, buy_order_amount = self.m_order_amount(coin)
                        pair = coin + "-" + self.hold_asset
                        self.sell(self.connector_name, pair, sell_order_amount, OrderType.LIMIT,
                                  Decimal(exchange.get_price(pair, True) * (1 + (self.mm_threshold / 100)))
                                  .quantize(Decimal('1.0000')))
                        self.buy(self.connector_name, pair, buy_order_amount, OrderType.LIMIT,
                                 Decimal(exchange.get_price(pair, False) * (1 - (self.mm_threshold / 100)))
                                 .quantize(Decimal('1.0000')))
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

    def m_order_amount(self, coin):
        """
        Calculate order amount
        """
        exchange = self.connector
        sell_order_amount = Decimal(exchange.get_balance(coin) *
                                    (1 + (self.mm_threshold / 100))) - Decimal(exchange.get_balance(coin))
        buy_order_amount = Decimal(exchange.get_balance(coin)) - Decimal(exchange.get_balance(coin) *
                                                                         (1 - (self.mm_threshold / 100)))
        return sell_order_amount, buy_order_amount

    def order_amount(self, coin, coins):
        """
        Calculate order amount
        """
        exchange = self.connector
        pair = coin + "-" + self.hold_asset
        order_amount = Decimal((self.get_current_value(coins)[coin] -
                                (self.get_total_value(coins) * (self.coin_config[coin] / 100))) /
                               exchange.get_mid_price(pair)).quantize(Decimal('1.000'))
        order_amount = abs(order_amount)
        return order_amount

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
        for coin in self.coin_config.values():
            target_weight.append(coin)
        target_weight.append(self.hold_asset_config[self.hold_asset])

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
                      f"  Status: {self.status}" +
                      f"  MM mode: {self.mm_mode}"])
        lines.extend(["", "  Balances:\n"] +
                     ["  " + line for line in account_data.to_string(index=False).split("\n")])
        lines.extend(["", f"  | Passive order threshold: {self.threshold}%" +
                      f" | Active order threshold: {self.mm_threshold}% |"])
        lines.extend(["", "  Active Orders:\n"])
        try:
            active_order = self.active_orders_df().drop('Exchange', axis=1)
            lines.extend(["  " + line for line in active_order.to_string(index=False).split("\n")])
        except ValueError:
            lines.extend(["", "  No active maker orders."])

        lines.extend(["", "  Trend Info:\n"])
        lines.extend([f" | ATR Short period: {np.round(self.s_atr_period, 4)}     |" +
                      f" ATR Long period: {np.round(self.l_atr_period, 4)}     |"])
        lines.extend([f" | Short period ATR: {np.round(self.s_atr_mean, 4)} |" +
                      f" Long period ATR: {np.round(self.l_atr_mean, 4)} |" + f" Is volatile: {self.is_volatile} |\n"] +
                     [f" | SuperTrend ATR period: {self.trend_atr_period} |" +
                      f" SuperTrend ATR multiplier: {self.atr_mult} |"] +
                     [f" | SuperTrend is Uptrend ? {self.is_uptrend}     |"] +
                     [f" | SuperTrend upperband: {np.round(self.upperband, 4)} |" +
                      f" SuperTrend lowerband: {np.round(self.lowerband, 4)} |"] +
                     [f" | SuperTrend ATR: {np.round(self.supertrend_atr, 4)}          |" +
                      f" SuperTrend preclose: {np.round(self.preclose, 4)}  |"])

        warning_lines.extend(self.balance_warning(self.get_market_trading_pair_tuples()))
        if len(warning_lines) > 0:
            lines.extend(["", "*** WARNINGS ***"] + warning_lines)
        return "\n".join(lines)
