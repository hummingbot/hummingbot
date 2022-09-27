import pandas as pd

from decimal import Decimal
from statistics import mean
from typing import Tuple, List, Dict

# from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.event.events import OrderFilledEvent, OrderType, TradeType, OrderBookTradeEvent, OrderBookEvent
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.connector.utils import split_hb_trading_pair
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.event.event_forwarder import SourceInfoEventForwarder


class rsi_strategy_example(ScriptStrategyBase):
    
    """
    This strategy buys ETH (with BTC) if rsi < 30 & ewma(50) > ewma(200)(asset over-sold). 
    This strategy sells ETH (with BTC) if rsi > 70 & ewma(50) < ewma(200) (asset over-bought).
    Otherwise, skip trading with [all_or_none = True] for OrderCandidate : 
        if you have sufficient balance, orders passes, otherwise, order skipped. 
    """
    
    trading_pair = "ETH-BTC"
    base_asset, quote_asset = split_hb_trading_pair(trading_pair) 
    conversion_pair: str = f"{quote_asset}-USD"
    exchange = "binance_paper_trade"
    rsi_window: int = 14 #  look-back window standard n = 14
    ma_long = 200
    ma_short = 50
    rsi_long = 30
    rsi_short = 70
    on_going_task = False 
    event_to_add : OrderBookTradeEvent
    
    markets = {exchange: {trading_pair}}
    
    trade_database: 'list[OrderBookTradeEvent]' = []

    
    def on_tick(self):
        """
        Runs every tick_size seconds, this is the main operation of the strategy.
        - Create proposal (a list of order candidates)
        - Check the account balance and adjust the proposal accordingly (lower order amount if needed)
        - Lastly, execute the proposal on the exchange
        """
        
    
        if len(self.trade_database) > 0:
            df = self.transform_to_OHLCV()
            df = self.calculate_ma(df)
            df = self.calculate_rsi(df)
            if  df['long'] == ((df.RSI < self.rsi_long) & (df.ma_short > df.ma_long))*1 : 
               TradeType.BUY
               self.rsi = df.iloc[-1]['RSI']
               self.logger().info(f"RSI is {self.rsi}")
            elif df['short'] == ((df.RSI > self.rsi_short) & (df.ma_short < df.ma_long))*-1 :
                TradeType.SELL
            else :
                pass
           
    def transform_to_OHLCV(self) -> pd.DataFrame():
        
        """ 
        Transform price event into OHLCV by resampling.
        """
        
        data = pd.DataFrame(self.trade_database)        
        df = data.resample('30s', how={'price': 'ohlc'}) 
        return df 
    
    @staticmethod
    def calculate_rsi(df: pd.DataFrame, rsi_window = 14):
        
        """
        Gives the RSI for a certain dataframe for rsi_window n = 14 period
        """
        
        df['change'] = df['close'].diff()
        df['U'] = [x if x > 0 else 0 for x in df.change]
        df['D'] = [abs(x) if x <0 else 0 for x in df.change]
        
        df['U'] = df.U.ewm(span = rsi_window, min_periods= rsi_window-1).mean()
        df['D'] = df.D.ewm(span = rsi_window, min_periods= rsi_window-1).mean()
        
        df['RS'] = df.U / df.D
        df['RSI'] = 100 - 100 / (1+ df.RS)
        df.drop(['change', 'U', 'D', 'RS'], axis = 1, inplace = True) 
        return df 
    
    
    def calculate_ma(df: pd.DataFrame, ma_long = 200, ma_short = 50):
        '''
        calculates two expontential movings averages, based on arguments passed
        '''
        
        df['ma_long'] = df.close.ewm(span = ma_long, min_periods = ma_long-1).mean()
        df['ma_short'] = df.close.ewm(span = ma_short, min_periods = ma_short-1).mean()
        
        
    def format_status(self) -> str:
        if not self.ready_to_trade:
            return "Market connectors are not ready."
        lines = []
        warning_lines = []
        warning_lines.extend(self.network_warning(self.get_market_trading_pair_tuples()))

        balance_df = self.get_balance_df()
        lines.extend(["", "  Balances:"] + ["    " + line for line in balance_df.to_string(index=False).split("\n")])

        market_status_df = self.market_status_data_frame(self.get_market_trading_pair_tuples())
        lines.extend(["", "  Market Status:"] + ["    " + line for line in market_status_df.to_string(index=False).split("\n")])

        warning_lines.extend(self.balance_warning(self.get_market_trading_pair_tuples()))
        if len(warning_lines) > 0:
            lines.extend(["", "*** WARNINGS ***"] + warning_lines)
        return "\n".join(lines)