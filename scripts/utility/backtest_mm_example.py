import logging
from datetime import datetime

import numpy as np
import pandas as pd

from hummingbot import data_path
from hummingbot.data_feed.candles_feed.candles_factory import CandlesFactory
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class BacktestMM(ScriptStrategyBase):
    """
    BotCamp Cohort: 4
    Design Template: https://www.notion.so/hummingbot-foundation/Backtestable-Market-Making-Stategy-95c0d17e4042485bb90b7b2914af7f68?pvs=4
    Video: https://www.loom.com/share/e18380429e9443ceb1ef86eb131c14a2
    Description: This bot implements a simpler backtester for a market making strategy using the Binance candles feed.
    After processing the user-defined backtesting parameters through historical OHLCV candles, it calculates a summary
    table displayed in 'status' and saves the data to a CSV file.

    You may need to run 'balance paper [asset] [amount]' beforehand to set the initial balances used for backtesting.
    """

    # User-defined parameters
    exchange = "binance"
    trading_pair = "ETH-USDT"
    order_amount = 0.1
    bid_spread_bps = 10
    ask_spread_bps = 10
    fee_bps = 10
    days = 7
    paper_trade_enabled = True

    # System parameters
    precision = 2
    base, quote = trading_pair.split("-")
    execution_exchange = f"{exchange}_paper_trade" if paper_trade_enabled else exchange
    interval = "1m"
    results_df = None
    candle = CandlesFactory.get_candle(CandlesConfig(connector=exchange, trading_pair=trading_pair, interval=interval, max_records=days * 60 * 24))
    candle.start()

    csv_path = data_path() + f"/backtest_{trading_pair}_{bid_spread_bps}_bid_{ask_spread_bps}_ask.csv"
    markets = {f"{execution_exchange}": {trading_pair}}

    def on_tick(self):
        if not self.candle.ready:
            self.logger().info(f"Candles not ready yet for {self.trading_pair}! Missing {self.candle._candles.maxlen - len(self.candle._candles)}")
            pass
        else:
            df = self.candle.candles_df
            df['ask_price'] = df["open"] * (1 + self.ask_spread_bps / 10000)
            df['bid_price'] = df["open"] * (1 - self.bid_spread_bps / 10000)
            df['buy_amount'] = df['low'].le(df['bid_price']) * self.order_amount
            df['sell_amount'] = df['high'].ge(df['ask_price']) * self.order_amount
            df['fees_paid'] = (df['buy_amount'] * df['bid_price'] + df['sell_amount'] * df['ask_price']) * self.fee_bps / 10000
            df['base_delta'] = df['buy_amount'] - df['sell_amount']
            df['quote_delta'] = df['sell_amount'] * df['ask_price'] - df['buy_amount'] * df['bid_price'] - df['fees_paid']

        if self.candle.ready and self.results_df is None:
            df.to_csv(self.csv_path, index=False)
            self.results_df = df
            msg = "Backtesting complete - run 'status' to see results."
            self.log_with_clock(logging.INFO, msg)
            self.notify_hb_app_with_timestamp(msg)

    async def on_stop(self):
        self.candle.stop()

    def get_trades_df(self, df):
        total_buy_trades = df['buy_amount'].ne(0).sum()
        total_sell_trades = df['sell_amount'].ne(0).sum()
        amount_bought = df['buy_amount'].sum()
        amount_sold = df['sell_amount'].sum()
        end_price = df.tail(1)['close'].values[0]
        amount_bought_quote = amount_bought * end_price
        amount_sold_quote = amount_sold * end_price
        avg_buy_price = np.dot(df['bid_price'], df['buy_amount']) / amount_bought
        avg_sell_price = np.dot(df['ask_price'], df['sell_amount']) / amount_sold
        avg_total_price = (avg_buy_price * amount_bought + avg_sell_price * amount_sold) / (amount_bought + amount_sold)

        trades_columns = ["", "buy", "sell", "total"]
        trades_data = [
            [f"{'Number of trades':<27}", total_buy_trades, total_sell_trades, total_buy_trades + total_sell_trades],
            [f"{f'Total trade volume ({self.base})':<27}",
             round(amount_bought, self.precision),
             round(amount_sold, self.precision),
             round(amount_bought + amount_sold, self.precision)],
            [f"{f'Total trade volume ({self.quote})':<27}",
             round(amount_bought_quote, self.precision),
             round(amount_sold_quote, self.precision),
             round(amount_bought_quote + amount_sold_quote, self.precision)],
            [f"{'Avg price':<27}",
             round(avg_buy_price, self.precision),
             round(avg_sell_price, self.precision),
             round(avg_total_price, self.precision)],
        ]
        return pd.DataFrame(data=trades_data, columns=trades_columns)

    def get_assets_df(self, df):
        for connector_name, connector in self.connectors.items():
            base_bal_start = float(connector.get_balance(self.base))
            quote_bal_start = float(connector.get_balance(self.quote))
        base_bal_change = df['base_delta'].sum()
        quote_bal_change = df['quote_delta'].sum()
        base_bal_end = base_bal_start + base_bal_change
        quote_bal_end = quote_bal_start + quote_bal_change
        start_price = df.head(1)['open'].values[0]
        end_price = df.tail(1)['close'].values[0]
        base_bal_start_pct = base_bal_start / (base_bal_start + quote_bal_start / start_price)
        base_bal_end_pct = base_bal_end / (base_bal_end + quote_bal_end / end_price)

        assets_columns = ["", "start", "end", "change"]
        assets_data = [
            [f"{f'{self.base}':<27}", f"{base_bal_start:2}", round(base_bal_end, self.precision), round(base_bal_change, self.precision)],
            [f"{f'{self.quote}':<27}", f"{quote_bal_start:2}", round(quote_bal_end, self.precision), round(quote_bal_change, self.precision)],
            [f"{f'{self.base}-{self.quote} price':<27}", start_price, end_price, end_price - start_price],
            [f"{'Base asset %':<27}", f"{base_bal_start_pct:.2%}",
                                      f"{base_bal_end_pct:.2%}",
                                      f"{base_bal_end_pct - base_bal_start_pct:.2%}"],
        ]
        return pd.DataFrame(data=assets_data, columns=assets_columns)

    def get_performance_df(self, df):
        for connector_name, connector in self.connectors.items():
            base_bal_start = float(connector.get_balance(self.base))
            quote_bal_start = float(connector.get_balance(self.quote))
        base_bal_change = df['base_delta'].sum()
        quote_bal_change = df['quote_delta'].sum()
        start_price = df.head(1)['open'].values[0]
        end_price = df.tail(1)['close'].values[0]
        base_bal_end = base_bal_start + base_bal_change
        quote_bal_end = quote_bal_start + quote_bal_change
        hold_value = base_bal_end * start_price + quote_bal_end
        current_value = base_bal_end * end_price + quote_bal_end
        total_pnl = current_value - hold_value
        fees_paid = df['fees_paid'].sum()
        return_pct = total_pnl / hold_value
        perf_data = [
            ["Hold portfolio value    ", f"{round(hold_value, self.precision)} {self.quote}"],
            ["Current portfolio value ", f"{round(current_value, self.precision)} {self.quote}"],
            ["Trade P&L               ", f"{round(total_pnl + fees_paid, self.precision)} {self.quote}"],
            ["Fees paid               ", f"{round(fees_paid, self.precision)} {self.quote}"],
            ["Total P&L               ", f"{round(total_pnl, self.precision)} {self.quote}"],
            ["Return %                ", f"{return_pct:2%} {self.quote}"],
        ]
        return pd.DataFrame(data=perf_data)

    def format_status(self) -> str:
        if not self.ready_to_trade:
            return "Market connectors are not ready."
        if not self.candle.ready:
            return (f"Candles not ready yet for {self.trading_pair}! Missing {self.candle._candles.maxlen - len(self.candle._candles)}")

        df = self.results_df
        base, quote = self.trading_pair.split("-")
        lines = []
        start_time = datetime.fromtimestamp(int(df.head(1)['timestamp'].values[0] / 1000))
        end_time = datetime.fromtimestamp(int(df.tail(1)['timestamp'].values[0] / 1000))

        lines.extend(
            [f"\n  Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}"] +
            [f"  End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}"] +
            [f"  Duration: {pd.Timedelta(seconds=(end_time - start_time).seconds)}"]
        )
        lines.extend(
            [f"\n  Market: {self.exchange} / {self.trading_pair}"] +
            [f"  Spread(bps): {self.bid_spread_bps} bid / {self.ask_spread_bps} ask"] +
            [f"  Order Amount: {self.order_amount} {base}"]
        )

        trades_df = self.get_trades_df(df)
        lines.extend(["", "  Trades:"] + ["    " + line for line in trades_df.to_string(index=False).split("\n")])

        assets_df = self.get_assets_df(df)
        lines.extend(["", "  Assets:"] + ["    " + line for line in assets_df.to_string(index=False).split("\n")])

        performance_df = self.get_performance_df(df)
        lines.extend(["", "  Performance:"] + ["    " + line for line in performance_df.to_string(index=False, header=False).split("\n")])

        return "\n".join(lines)
