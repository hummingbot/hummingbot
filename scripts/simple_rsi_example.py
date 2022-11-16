import math
import os
from decimal import Decimal
from typing import Optional

import pandas as pd

from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.event.event_forwarder import SourceInfoEventForwarder
from hummingbot.core.event.events import OrderBookEvent, OrderBookTradeEvent, OrderFilledEvent
from hummingbot.core.rate_oracle.rate_oracle import RateOracle
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class SimpleRSIScript(ScriptStrategyBase):
    """
    The strategy is to buy on overbought signal and sell on oversold.
    """
    connector_name = os.getenv("CONNECTOR_NAME", "binance_paper_trade")
    base = os.getenv("BASE", "BTC")
    quote = os.getenv("QUOTE", "USDT")
    timeframe = os.getenv("TIMEFRAME", "1s")

    position_amount_usd = Decimal(os.getenv("POSITION_AMOUNT_USD", "50"))

    rsi_length = int(os.getenv("RSI_LENGTH", "14"))

    # If true - uses Exponential Moving Average, if false - Simple Moving Average.
    rsi_is_ema = os.getenv("RSI_IS_EMA", 'True').lower() in ('true', '1', 't')

    buy_rsi = int(os.getenv("BUY_RSI", "30"))
    sell_rsi = int(os.getenv("SELL_RSI", "70"))

    # It depends on a timeframe. Make sure you have enough trades to calculate rsi_length number of candlesticks.
    trade_count_limit = int(os.getenv("TRADE_COUNT_LIMIT", "100000"))

    trading_pair = combine_to_hb_trading_pair(base, quote)
    markets = {connector_name: {trading_pair}}

    subscribed_to_order_book_trade_event: bool = False
    position: Optional[OrderFilledEvent] = None

    _trades: 'list[OrderBookTradeEvent]' = []
    _cumulative_price_change_pct = Decimal(0)
    _filling_position: bool = False

    def on_tick(self):
        """
        On every tick calculate OHLCV candlesticks, calculate RSI, react on overbought or oversold signal with creating,
        adjusting and sending an order.
        """
        if not self.subscribed_to_order_book_trade_event:
            # Set pandas resample rule for a timeframe
            self._set_resample_rule(self.timeframe)
            self.subscribe_to_order_book_trade_event()
        elif len(self._trades) > 0:
            df = self.calculate_candlesticks()
            df = self.calculate_rsi(df, self.rsi_length, self.rsi_is_ema)
            should_open_position = self.should_open_position(df)
            should_close_position = self.should_close_position(df)
            if should_open_position or should_close_position:
                order_side = TradeType.BUY if should_open_position else TradeType.SELL
                order_candidate = self.create_order_candidate(order_side)
                # Adjust OrderCandidate
                order_adjusted = self.connectors[self.connector_name].budget_checker.adjust_candidate(order_candidate, all_or_none=False)
                if math.isclose(order_adjusted.amount, Decimal("0"), rel_tol=1E-5):
                    self.logger().info(f"Order adjusted: {order_adjusted.amount}, too low to place an order")
                else:
                    self.send_order(order_adjusted)
            else:
                self._rsi = df.iloc[-1]['rsi']
                self.logger().info(f"RSI is {self._rsi:.0f}")

    def _set_resample_rule(self, timeframe):
        """
        Convert timeframe to pandas resample rule value.
        https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.resample.html
        """
        timeframe_to_rule = {
            "1s": "1S",
            "10s": "10S",
            "30s": "30S",
            "1m": "1T",
            "15m": "15T"
        }
        if timeframe not in timeframe_to_rule.keys():
            self.logger().error(f"{timeframe} timeframe is not mapped to resample rule.")
            HummingbotApplication.main_application().stop()
        self._resample_rule = timeframe_to_rule[timeframe]

    def should_open_position(self, df: pd.DataFrame) -> bool:
        """
        If overbought and not in the position.
        """
        rsi: float = df.iloc[-1]['rsi']
        rsi_is_calculated = pd.notna(rsi)
        time_to_buy = rsi_is_calculated and rsi <= self.buy_rsi
        can_buy = self.position is None and not self._filling_position
        return can_buy and time_to_buy

    def should_close_position(self, df: pd.DataFrame) -> bool:
        """
        If oversold and in the position.
        """
        rsi: float = df.iloc[-1]['rsi']
        rsi_is_calculated = pd.notna(rsi)
        time_to_sell = rsi_is_calculated and rsi >= self.sell_rsi
        can_sell = self.position is not None and not self._filling_position
        return can_sell and time_to_sell

    def create_order_candidate(self, order_side: bool) -> OrderCandidate:
        """
        Create and quantize order candidate.
        """
        connector: ConnectorBase = self.connectors[self.connector_name]
        is_buy = order_side == TradeType.BUY
        price = connector.get_price(self.trading_pair, is_buy)
        if is_buy:
            conversion_rate = RateOracle.get_instance().get_pair_rate(self.trading_pair)
            amount = self.position_amount_usd / conversion_rate
        else:
            amount = self.position.amount

        amount = connector.quantize_order_amount(self.trading_pair, amount)
        price = connector.quantize_order_price(self.trading_pair, price)
        return OrderCandidate(
            trading_pair=self.trading_pair,
            is_maker = False,
            order_type = OrderType.LIMIT,
            order_side = order_side,
            amount = amount,
            price = price)

    def send_order(self, order: OrderCandidate):
        """
        Send order to the exchange, indicate that position is filling, and send log message with a trade.
        """
        is_buy = order.order_side == TradeType.BUY
        place_order = self.buy if is_buy else self.sell
        place_order(
            connector_name=self.connector_name,
            trading_pair=self.trading_pair,
            amount=order.amount,
            order_type=order.order_type,
            price=order.price
        )
        self._filling_position = True
        if is_buy:
            msg = f"RSI is below {self.buy_rsi:.2f}, buying {order.amount:.5f} {self.base} with limit order at {order.price:.2f} ."
        else:
            msg = (f"RSI is above {self.sell_rsi:.2f}, selling {self.position.amount:.5f} {self.base}"
                   f" with limit order at ~ {order.price:.2f}, entry price was {self.position.price:.2f}.")
        self.notify_hb_app_with_timestamp(msg)
        self.logger().info(msg)

    def calculate_candlesticks(self) -> pd.DataFrame:
        """
        Convert raw trades to OHLCV dataframe.
        """
        df = pd.DataFrame(self._trades)
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df.drop(columns=[df.columns[0]], axis=1, inplace=True)
        df = df.set_index('timestamp')
        df = df.resample(self._resample_rule).agg({
            'price': ['first', 'max', 'min', 'last'],
            'amount': 'sum',
        })
        df.columns = df.columns.to_flat_index().map(lambda x: x[1])
        df.rename(columns={'first': 'open', 'max': 'high', 'min': 'low', 'last': 'close', 'sum': 'volume'}, inplace=True)
        return df

    def did_fill_order(self, event: OrderFilledEvent):
        """
        Indicate that position is filled, save position properties on enter, calculate cumulative price change on exit.
        """
        if event.trade_type == TradeType.BUY:
            self.position = event
            self._filling_position = False
        elif event.trade_type == TradeType.SELL:
            delta_price = (event.price - self.position.price) / self.position.price
            self._cumulative_price_change_pct += delta_price
            self.position = None
            self._filling_position = False
        else:
            self.logger().warn(f"Unsupported order type filled: {event.trade_type}")

    @staticmethod
    def calculate_rsi(df: pd.DataFrame, length: int = 14, is_ema: bool = True):
        """
        Calculate relative strength index and add it to the dataframe.
        """
        close_delta = df['close'].diff()
        up = close_delta.clip(lower=0)
        down = close_delta.clip(upper=0).abs()

        if is_ema:
            # Exponential Moving Average
            ma_up = up.ewm(com = length - 1, adjust=True, min_periods = length).mean()
            ma_down = down.ewm(com = length - 1, adjust=True, min_periods = length).mean()
        else:
            # Simple Moving Average
            ma_up = up.rolling(window = length, adjust=False).mean()
            ma_down = down.rolling(window = length, adjust=False).mean()

        rs = ma_up / ma_down
        df["rsi"] = 100 - (100 / (1 + rs))
        return df

    def subscribe_to_order_book_trade_event(self):
        """
        Subscribe to raw trade event.
        """
        self.order_book_trade_event = SourceInfoEventForwarder(self._process_public_trade)
        for market in self.connectors.values():
            for order_book in market.order_books.values():
                order_book.add_listener(OrderBookEvent.TradeEvent, self.order_book_trade_event)
        self.subscribed_to_order_book_trade_event = True

    def _process_public_trade(self, event_tag: int, market: ConnectorBase, event: OrderBookTradeEvent):
        """
        Add new trade to list, remove old trade event, if count greater than trade_count_limit.
        """
        if len(self._trades) >= self.trade_count_limit:
            self._trades.pop(0)
        self._trades.append(event)

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

        balance_df = self.get_balance_df()
        lines.extend(["", "  Balances:"] + ["    " + line for line in balance_df.to_string(index=False).split("\n")])

        try:
            df = self.active_orders_df()
            lines.extend(["", "  Orders:"] + ["    " + line for line in df.to_string(index=False).split("\n")])
        except ValueError:
            lines.extend(["", "  No active maker orders."])

        # Strategy specific info
        lines.extend(["", "  Current RSI:"] + ["    " + f"{self._rsi:.0f}"])
        lines.extend(["", "  Simple RSI strategy total price change with all trades:"] + ["    " + f"{self._cumulative_price_change_pct:.5f}" + " %"])

        warning_lines.extend(self.balance_warning(self.get_market_trading_pair_tuples()))
        if len(warning_lines) > 0:
            lines.extend(["", "*** WARNINGS ***"] + warning_lines)
        return "\n".join(lines)
