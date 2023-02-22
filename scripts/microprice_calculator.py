import datetime
import os
from decimal import Decimal
from operator import itemgetter

import numpy as np
import pandas as pd
from scipy.linalg import block_diag

from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class MicropricePMM(ScriptStrategyBase):
    # ! Configuration
    trading_pair = "ETH-USDT"
    exchange = "kucoin_paper_trade"
    range_of_imbalance = 1  # ? Compute imbalance from [best bid/ask, +/- ticksize*range_of_imbalance)

    # ! Microprice configuration
    dt = 1
    n_imb = 6  # ? Needs to be large enough to capture shape of imbalance adjustmnts without being too large to capture noise

    # ! Advanced configuration variables
    show_data = False  # ? Controls whether current df is shown in status
    path_to_data = './data'  # ? Default file format './data/microprice_{trading_pair}_{exchange}_{date}.csv'
    interval_to_write = 60
    price_line_width = 60
    precision = 4  # ? should be the length of the ticksize
    data_size_min = 10000  # ? Seems to be the ideal value to get microprice adjustment values for other spreads
    day_offset = 1  # ? How many days back to start looking for csv files to load data from

    # ! Script variabes
    columns = ['date', 'time', 'bid', 'bs', 'ask', 'as']
    current_dataframe = pd.DataFrame(columns=columns)
    time_to_write = 0
    markets = {exchange: {trading_pair}}
    g_star = None
    recording_data = True
    ticksize = None
    n_spread = None

    # ! System methods
    def on_tick(self):
        # Record data, dump data, update write timestamp
        self.record_data()
        if self.time_to_write < self.current_timestamp:
            self.time_to_write = self.interval_to_write + self.current_timestamp
            self.dump_data()

    def format_status(self) -> str:
        bid, ask = itemgetter('bid', 'ask')(self.get_bid_ask())
        bar = '=' * self.price_line_width + '\n'
        header = f'Trading pair: {self.trading_pair}\nExchange: {self.exchange}\n'
        price_line = f'Adjusted Midprice: {self.compute_adjusted_midprice()}\n         Midprice: {round((bid + ask) / 2, 8)}\n                 = {round(self.compute_adjusted_midprice() - ((bid + ask) / 2), 20)}\n\n{self.get_price_line()}\n'
        imbalance_line = f'Imbalance: {self.compute_imbalance()}\n{self.get_imbalance_line()}\n'
        data = f'Data path: {self.get_csv_path()}\n'
        g_star = f'g_star:\n{self.g_star}' if self.g_star is not None else ''

        return f"\n\n\n{bar}\n\n{header}\n{price_line}\n\n{imbalance_line}\nn_spread: {self.n_spread} {'tick' if self.n_spread == 1 else 'ticks'}\n\n\n{g_star}\n\n{data}\n\n{bar}\n\n\n"

    # ! Data recording methods
    # Records a new row to the dataframe every tick
    # Every 'time_to_write' ticks, writes the dataframe to a csv file
    def record_data(self):
        # Fetch bid and ask data
        bid, ask, bid_volume, ask_volume = itemgetter('bid', 'ask', 'bs', 'as')(self.get_bid_ask())
        # Fetch date and time in seconds
        date = datetime.datetime.now().strftime("%Y-%m-%d")
        time = self.current_timestamp

        data = [[date, time, bid, bid_volume, ask, ask_volume]]
        self.current_dataframe = self.current_dataframe.append(pd.DataFrame(data, columns=self.columns), ignore_index=True)
        return

    def dump_data(self):
        if len(self.current_dataframe) < 2 * self.range_of_imbalance:
            return
        # Dump data to csv file
        csv_path = f'{self.path_to_data}/microprice_{self.trading_pair}_{self.exchange}_{datetime.datetime.now().strftime("%Y-%m-%d")}.csv'
        try:
            data = pd.read_csv(csv_path, index_col=[0])
        except Exception as e:
            self.logger().info(e)
            self.logger().info(f'Creating new csv file at {csv_path}')
            data = pd.DataFrame(columns=self.columns)

        data = data.append(self.current_dataframe.iloc[:-self.range_of_imbalance], ignore_index=True)
        data.to_csv(csv_path)
        self.current_dataframe = self.current_dataframe.iloc[-self.range_of_imbalance:]
        return

# ! Data methods
    def get_csv_path(self):
        # Get all files in self.path_to_data directory
        files = os.listdir(self.path_to_data)
        for i in files:
            if i.startswith(f'microprice_{self.trading_pair}_{self.exchange}'):
                len_data = len(pd.read_csv(f'{self.path_to_data}/{i}', index_col=[0]))
                if len_data > self.data_size_min:
                    return f'{self.path_to_data}/{i}'

        # Otherwise just return today's file
        return f'{self.path_to_data}/microprice_{self.trading_pair}_{self.exchange}_{datetime.datetime.now().strftime("%Y-%m-%d")}.csv'

    def get_bid_ask(self):
        bids, asks = self.connectors[self.exchange].get_order_book(self.trading_pair).snapshot
        # if size > 0, return average of range
        best_ask = asks.iloc[0].price
        ask_volume = asks.iloc[0].amount
        best_bid = bids.iloc[0].price
        bid_volume = bids.iloc[0].amount
        return {'bid': best_bid, 'ask': best_ask, 'bs': bid_volume, 'as': ask_volume}

    # ! Microprice methods
    def compute_adjusted_midprice(self):
        data = self.get_df()
        if len(data) < self.data_size_min or self.current_dataframe.empty:
            self.recording_data = True
            return -1
        if self.n_spread is None:
            self.n_spread = self.compute_n_spread()
        if self.g_star is None:
            ticksize, g_star = self.compute_G_star(data)
            self.g_star = g_star
            self.ticksize = ticksize
        # Compute adjusted midprice from G_star and mid
        bid, ask = itemgetter('bid', 'ask')(self.get_bid_ask())
        mid = (bid + ask) / 2
        G_star = self.g_star
        ticksize = self.ticksize
        n_spread = self.n_spread

        # ? Compute adjusted midprice
        last_row = self.current_dataframe.iloc[-1]
        imb = last_row['bs'].astype(float) / (last_row['bs'].astype(float) + last_row['as'].astype(float))
        # Compute bucket of imbalance
        imb_bucket = [abs(x - imb) for x in G_star.columns].index(min([abs(x - imb) for x in G_star.columns]))
        # Compute and round spread index to nearest ticksize
        spreads = G_star[G_star.columns[imb_bucket]].values
        spread = last_row['ask'].astype(float) - last_row['bid'].astype(float)
        # ? Generally we expect this value to be < self._n_spread so we log when it's > self._n_spread
        spread_bucket = round(spread / ticksize) * ticksize // ticksize - 1
        if spread_bucket >= n_spread:
            spread_bucket = n_spread - 1
        spread_bucket = int(spread_bucket)
        # Compute adjusted midprice
        adj_midprice = mid + spreads[spread_bucket]
        return round(adj_midprice, self.precision * 2)

    def compute_G_star(self, data):
        n_spread = self.n_spread
        T, ticksize = self.prep_data_sym(data, self.n_imb, self.dt, n_spread)
        imb = np.linspace(0, 1, self.n_imb)
        G1, B = self.estimate(T, n_spread, self.n_imb)
        # Calculate G1 then B^6*G1
        G2 = np.dot(B, G1) + G1
        G3 = G2 + np.dot(np.dot(B, B), G1)
        G4 = G3 + np.dot(np.dot(np.dot(B, B), B), G1)
        G5 = G4 + np.dot(np.dot(np.dot(np.dot(B, B), B), B), G1)
        G6 = G5 + np.dot(np.dot(np.dot(np.dot(np.dot(B, B), B), B), B), G1)
        # Reorganize G6 into buckets
        index = [str(i + 1) for i in range(0, n_spread)]
        G_star = pd.DataFrame(G6.reshape(n_spread, self.n_imb), index=index, columns=imb)
        return ticksize, G_star

    def G_star_invalid(self, G_star, ticksize):
        # Check if any values of G_star > ticksize/2
        if np.any(G_star > ticksize / 2):
            return True
        # Check if any values of G_star < -ticksize/2
        if np.any(G_star < -ticksize / 2):
            return True
        # Round middle values of G_star to self.precision and check if any values are 0
        if np.any(np.round(G_star.iloc[int(self.n_imb / 2)], self.precision) == 0):
            return True
        return False

    def estimate(self, T, n_spread, n_imb):
        no_move = T[T['dM'] == 0]
        no_move_counts = no_move.pivot_table(index=['next_imb_bucket'],
                                             columns=['spread', 'imb_bucket'],
                                             values='time',
                                             fill_value=0,
                                             aggfunc='count').unstack()
        Q_counts = np.resize(np.array(no_move_counts[0:(n_imb * n_imb)]), (n_imb, n_imb))
        # loop over all spreads and add block matrices
        for i in range(1, n_spread):
            Qi = np.resize(np.array(no_move_counts[(i * n_imb * n_imb):(i + 1) * (n_imb * n_imb)]), (n_imb, n_imb))
            Q_counts = block_diag(Q_counts, Qi)
        move_counts = T[(T['dM'] != 0)].pivot_table(index=['dM'],
                                                    columns=['spread', 'imb_bucket'],
                                                    values='time',
                                                    fill_value=0,
                                                    aggfunc='count').unstack()

        R_counts = np.resize(np.array(move_counts), (n_imb * n_spread, 4))
        T1 = np.concatenate((Q_counts, R_counts), axis=1).astype(float)
        for i in range(0, n_imb * n_spread):
            T1[i] = T1[i] / T1[i].sum()
        Q = T1[:, 0:(n_imb * n_spread)]
        R1 = T1[:, (n_imb * n_spread):]

        K = np.array([-0.01, -0.005, 0.005, 0.01])
        move_counts = T[(T['dM'] != 0)].pivot_table(index=['spread', 'imb_bucket'],
                                                    columns=['next_spread', 'next_imb_bucket'],
                                                    values='time',
                                                    fill_value=0,
                                                    aggfunc='count')

        R2_counts = np.resize(np.array(move_counts), (n_imb * n_spread, n_imb * n_spread))
        T2 = np.concatenate((Q_counts, R2_counts), axis=1).astype(float)

        for i in range(0, n_imb * n_spread):
            T2[i] = T2[i] / T2[i].sum()
        R2 = T2[:, (n_imb * n_spread):]
        G1 = np.dot(np.dot(np.linalg.inv(np.eye(n_imb * n_spread) - Q), R1), K)
        B = np.dot(np.linalg.inv(np.eye(n_imb * n_spread) - Q), R2)
        return G1, B

    def compute_n_spread(self, T=None):
        if not T:
            T = self.get_df()
        spread = T.ask - T.bid
        spread_counts = spread.value_counts()
        return len(spread_counts[spread_counts > self.data_size_min])

    def prep_data_sym(self, T, n_imb, dt, n_spread):
        spread = T.ask - T.bid
        ticksize = np.round(min(spread.loc[spread > 0]) * 100) / 100
        # T.spread=T.ask-T.bid
        # adds the spread and mid prices
        T['spread'] = np.round((T['ask'] - T['bid']) / ticksize) * ticksize
        T['mid'] = (T['bid'] + T['ask']) / 2
        # filter out spreads >= n_spread
        T = T.loc[(T.spread <= n_spread * ticksize) & (T.spread > 0)]
        T['imb'] = T['bs'] / (T['bs'] + T['as'])
        # discretize imbalance into percentiles
        T['imb_bucket'] = pd.qcut(T['imb'], n_imb, labels=False, duplicates='drop')
        T['next_mid'] = T['mid'].shift(-dt)
        # step ahead state variables
        T['next_spread'] = T['spread'].shift(-dt)
        T['next_time'] = T['time'].shift(-dt)
        T['next_imb_bucket'] = T['imb_bucket'].shift(-dt)
        # step ahead change in price
        T['dM'] = np.round((T['next_mid'] - T['mid']) / ticksize * 2) * ticksize / 2
        T = T.loc[(T.dM <= ticksize * 1.1) & (T.dM >= -ticksize * 1.1)]
        # symetrize data
        T2 = T.copy(deep=True)
        T2['imb_bucket'] = n_imb - 1 - T2['imb_bucket']
        T2['next_imb_bucket'] = n_imb - 1 - T2['next_imb_bucket']
        T2['dM'] = -T2['dM']
        T2['mid'] = -T2['mid']
        T3 = pd.concat([T, T2])
        T3.index = pd.RangeIndex(len(T3.index))
        return T3, ticksize

    def get_df(self):
        csv_path = self.get_csv_path()
        try:
            df = pd.read_csv(csv_path, index_col=[0])
            df = df.append(self.current_dataframe)
        except Exception as e:
            self.logger().info(e)
            df = self.current_dataframe

        df['time'] = df['time'].astype(float)
        df['bid'] = df['bid'].astype(float)
        df['ask'] = df['ask'].astype(float)
        df['bs'] = df['bs'].astype(float)
        df['as'] = df['as'].astype(float)
        df['mid'] = (df['bid'] + df['ask']) / float(2)
        df['imb'] = df['bs'] / (df['bs'] + df['as'])
        return df

    def compute_imbalance(self) -> Decimal:
        if self.get_df().empty or self.current_dataframe.empty:
            self.logger().info('No data to compute imbalance, recording data')
            self.recording_data = True
            return Decimal(-1)
        bid_size = self.current_dataframe['bs'].sum()
        ask_size = self.current_dataframe['as'].sum()
        return round(Decimal(bid_size) / Decimal(bid_size + ask_size), self.precision * 2)

    # ! Format status methods
    def get_price_line(self) -> str:
        # Get best bid and ask
        bid, ask = itemgetter('bid', 'ask')(self.get_bid_ask())
        # Mid price is center of line
        price_line = int(self.price_line_width / 2) * '-' + '|' + int(self.price_line_width / 2) * '-'
        # Add bid, adjusted midprice,
        bid_offset = int(self.price_line_width / 2 - len(str(bid)) - (len(str(self.compute_adjusted_midprice())) / 2))
        ask_offset = int(self.price_line_width / 2 - len(str(ask)) - (len(str(self.compute_adjusted_midprice())) / 2))
        labels = str(bid) + bid_offset * ' ' + str(self.compute_adjusted_midprice()) + ask_offset * ' ' + str(ask) + '\n'
        # Create microprice of size 'price_line_width' with ends best bid and ask
        mid = (bid + ask) / 2
        spread = ask - bid
        microprice_adjustment = self.compute_adjusted_midprice() - mid + (spread / 2)
        adjusted_midprice_i = int(microprice_adjustment / spread * self.price_line_width) + 1
        price_line = price_line[:adjusted_midprice_i] + 'm' + price_line[adjusted_midprice_i:]
        return labels + price_line

    def get_imbalance_line(self) -> str:
        imb_line = int(self.price_line_width / 2) * '-' + '|' + int(self.price_line_width / 2) * '-'
        imb_line = imb_line[:int(self.compute_imbalance() * self.price_line_width)] + 'i' + imb_line[int(self.compute_imbalance() * self.price_line_width):]
        return imb_line
