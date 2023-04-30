import logging

import pandas as pd

from hummingbot import data_path
from hummingbot.data_feed.candles_feed.candles_factory import CandlesFactory
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class BacktestMM(ScriptStrategyBase):
    """
    BotCamp Cohort: 4
    Design Template:
    Video:
    Description:
    This bot implments a simpler backtester for a market making strategy using the Binance candles feed
    """

    exchange = "binance"
    trading_pair = "ETH-USDT"
    bid_amount = 0.1
    ask_amount = 0.1
    bid_spread_bps = 10
    ask_spread_bps = 10
    fee_bps = 10
    days = 1

    interval = "1m"
    done = False
    candle = CandlesFactory.get_candle(connector=exchange, trading_pair=trading_pair, interval=interval, max_records=days * 60 * 24)
    candle.start()

    csv_path = data_path() + f"/backtest_{trading_pair}_{bid_spread_bps}_bid_{ask_spread_bps}_ask.csv"
    markets = {f"{exchange}_paper_trade": {trading_pair}}

    def on_tick(self):
        if not self.candle.is_ready:
            self.logger().info(f"Candles not ready yet for {self.trading_pair}! Missing {self.candle._candles.maxlen - len(self.candle._candles)}")
            pass
        else:
            df = self.candle.candles_df
            df['ask_price'] = df["open"] * (1 + self.ask_spread_bps / 10000)
            df['bid_price'] = df["open"] * (1 - self.bid_spread_bps / 10000)
            df['buy_amount'] = df['low'].le(df['bid_price']) * self.bid_amount
            df['sell_amount'] = df['high'].ge(df['ask_price']) * self.ask_amount
            df['fees_paid'] = (df['buy_amount'] * df['bid_price'] + df['sell_amount'] * df['ask_price']) * self.fee_bps / 10000
            df['base_delta'] = df['buy_amount'] - df['sell_amount']
            df['quote_delta'] = df['sell_amount'] * df['ask_price'] - df['buy_amount'] * df['bid_price'] - df['fees_paid']

        if self.candle.is_ready and not self.done:
            df.to_csv(self.csv_path, index=False)
            msg = "Backtesting complete - run 'status' to see results."
            self.log_with_clock(logging.INFO, msg)
            self.notify_hb_app_with_timestamp(msg)
            self.done = True

    def on_stop(self):
        self.candle.stop()

    def generate_results_df(self, df):
        results = {
            'start_time': df.head(1)['timestamp'].values[0],
            'end_time': df.tail(1)['timestamp'].values[0],
            'start_price': df.head(1)['open'].values[0],
            'end_price': df.tail(1)['close'].values[0],
            'total_buy_trades': df['buy_amount'].ne(0).sum(),
            'total_sell_trades': df['sell_amount'].ne(0).sum(),
            'amount_bought': df['buy_amount'].sum(),
            'amount_sold': df['sell_amount'].sum(),
            'fees_paid': df['fees_paid'].sum(),
            'base_asset_change': df['base_delta'].sum(),
            'quote_asset_change': df['quote_delta'].sum(),
        }
        return pd.DataFrame(results, index=[0])

    def get_trades_df(self, df):
        base, quote = self.trading_pair.split("-")
        total_buy_trades = df['buy_amount'].ne(0).sum()
        total_sell_trades = df['sell_amount'].ne(0).sum()
        amount_bought = df['buy_amount'].sum()
        amount_sold = df['sell_amount'].sum()

        trades_columns = ["", "buy", "sell", "total"]
        trades_data = [
            [f"{'Number of trades':<27}", total_buy_trades, total_sell_trades, total_buy_trades + total_sell_trades],
            [f"{f'Total trade volume ({base})':<27}", amount_bought, amount_sold, amount_bought + amount_sold],
            # [f"{'Avg price':<27}",
        ]
        return pd.DataFrame(data=trades_data, columns=trades_columns)

    def format_status(self) -> str:
        if not self.ready_to_trade:
            return "Market connectors are not ready."
        if not self.candle.is_ready:
            return (f"Candles not ready yet for {self.trading_pair}! Missing {self.candle._candles.maxlen - len(self.candle._candles)}")

        df = self.candle.candles_df
        lines = []
        # start_time = datetime.fromtimestamp(int(df.head(1)['timestamp'].values[0]))
        # end_time = datetime.fromtimestamp(int(df.tail(1)['timestamp'].values[0]))
        # lines.extend(
        #     [f"\nStart Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}"]
        #     [f"\nEnd Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}"]
        # )
        lines.extend([f"\n{self.exchange} / {self.trading_pair}"])

        trades_df = self.get_trades_df(df)
        lines.extend(["", "  Trades:"] + ["    " + line for line in trades_df.to_string(index=False).split("\n")])
        return "\n".join(lines)
