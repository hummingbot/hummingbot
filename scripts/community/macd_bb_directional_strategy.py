import datetime
import os
from collections import deque
from decimal import Decimal
from typing import Deque, Dict, List

import pandas as pd
import pandas_ta as ta  # noqa: F401

from hummingbot import data_path
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.data_feed.candles_feed.candles_factory import CandlesFactory
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.strategy_v2.executors.position_executor.data_types import PositionExecutorConfig, TripleBarrierConfig
from hummingbot.strategy_v2.executors.position_executor.position_executor import PositionExecutor


class MACDBBDirectionalStrategy(ScriptStrategyBase):
    """
    A simple trading strategy that uses RSI in one timeframe to determine whether to go long or short.
    IMPORTANT: Binance perpetual has to be in Single Asset Mode, soon we are going to support Multi Asset Mode.
    """
    # Define the trading pair and exchange that we want to use and the csv where we are going to store the entries
    trading_pair = "APE-BUSD"
    exchange = "binance_perpetual"

    # Maximum position executors at a time
    max_executors = 1
    active_executors: List[PositionExecutor] = []
    stored_executors: Deque[PositionExecutor] = deque(maxlen=10)  # Store only the last 10 executors for reporting

    # Configure the parameters for the position
    stop_loss_multiplier = 0.75
    take_profit_multiplier = 1.5
    time_limit = 60 * 55

    # Create the candles that we want to use and the thresholds for the indicators
    # IMPORTANT: The connector name of the candles can be binance or binance_perpetual, and can be different from the
    # connector that you define to trade
    candles = CandlesFactory.get_candle(CandlesConfig(connector=exchange, trading_pair=trading_pair, interval="3m", max_records=1000))

    # Configure the leverage and order amount the bot is going to use
    set_leverage_flag = None
    leverage = 20
    order_amount_usd = Decimal("15")

    today = datetime.datetime.today()
    csv_path = data_path() + f"/{exchange}_{trading_pair}_{today.day:02d}-{today.month:02d}-{today.year}.csv"
    markets = {exchange: {trading_pair}}

    def __init__(self, connectors: Dict[str, ConnectorBase]):
        # Is necessary to start the Candles Feed.
        super().__init__(connectors)
        self.candles.start()

    def get_active_executors(self):
        return [signal_executor for signal_executor in self.active_executors
                if not signal_executor.is_closed]

    def get_closed_executors(self):
        return self.stored_executors

    def on_tick(self):
        self.check_and_set_leverage()
        if len(self.get_active_executors()) < self.max_executors and self.candles.ready:
            signal_value, take_profit, stop_loss, indicators = self.get_signal_tp_and_sl()
            if self.is_margin_enough() and signal_value != 0:
                price = self.connectors[self.exchange].get_mid_price(self.trading_pair)
                self.notify_hb_app_with_timestamp(f"""
                Creating new position!
                Price: {price}
                BB%: {indicators[0]}
                MACDh: {indicators[1]}
                MACD: {indicators[2]}
                """)
                signal_executor = PositionExecutor(
                    config=PositionExecutorConfig(
                        timestamp=self.current_timestamp, trading_pair=self.trading_pair,
                        connector_name=self.exchange,
                        side=TradeType.SELL if signal_value < 0 else TradeType.BUY,
                        entry_price=price,
                        amount=self.order_amount_usd / price,
                        triple_barrier_config=TripleBarrierConfig(stop_loss=stop_loss, take_profit=take_profit,
                                                                  time_limit=self.time_limit)),
                    strategy=self,
                )
                self.active_executors.append(signal_executor)
        self.clean_and_store_executors()

    def get_signal_tp_and_sl(self):
        candles_df = self.candles.candles_df
        # Let's add some technical indicators
        candles_df.ta.bbands(length=100, append=True)
        candles_df.ta.macd(fast=21, slow=42, signal=9, append=True)
        candles_df["std"] = candles_df["close"].rolling(100).std()
        candles_df["std_close"] = candles_df["std"] / candles_df["close"]
        last_candle = candles_df.iloc[-1]
        bbp = last_candle["BBP_100_2.0"]
        macdh = last_candle["MACDh_21_42_9"]
        macd = last_candle["MACD_21_42_9"]
        std_pct = last_candle["std_close"]
        if bbp < 0.2 and macdh > 0 and macd < 0:
            signal_value = 1
        elif bbp > 0.8 and macdh < 0 and macd > 0:
            signal_value = -1
        else:
            signal_value = 0
        take_profit = std_pct * self.take_profit_multiplier
        stop_loss = std_pct * self.stop_loss_multiplier
        indicators = [bbp, macdh, macd]
        return signal_value, take_profit, stop_loss, indicators

    async def on_stop(self):
        """
        Without this functionality, the network iterator will continue running forever after stopping the strategy
        That's why is necessary to introduce this new feature to make a custom stop with the strategy.
        """
        # we are going to close all the open positions when the bot stops
        self.close_open_positions()
        self.candles.stop()

    def format_status(self) -> str:
        """
        Displays the three candlesticks involved in the script with RSI, BBANDS and EMA.
        """
        if not self.ready_to_trade:
            return "Market connectors are not ready."
        lines = []

        if len(self.stored_executors) > 0:
            lines.extend([
                "\n########################################## Closed Executors ##########################################"])

        for executor in self.stored_executors:
            lines.extend([f"|Signal id: {executor.timestamp}"])
            lines.extend(executor.to_format_status())
            lines.extend([
                "-----------------------------------------------------------------------------------------------------------"])

        if len(self.active_executors) > 0:
            lines.extend([
                "\n########################################## Active Executors ##########################################"])

        for executor in self.active_executors:
            lines.extend([f"|Signal id: {executor.timestamp}"])
            lines.extend(executor.to_format_status())
        if self.candles.ready:
            lines.extend([
                "\n############################################ Market Data ############################################\n"])
            signal, take_profit, stop_loss, indicators = self.get_signal_tp_and_sl()
            lines.extend([f"Signal: {signal} | Take Profit: {take_profit} | Stop Loss: {stop_loss}"])
            lines.extend([f"BB%: {indicators[0]} | MACDh: {indicators[1]} | MACD: {indicators[2]}"])
            lines.extend(["\n-----------------------------------------------------------------------------------------------------------\n"])
        else:
            lines.extend(["", "  No data collected."])

        return "\n".join(lines)

    def check_and_set_leverage(self):
        if not self.set_leverage_flag:
            for connector in self.connectors.values():
                for trading_pair in connector.trading_pairs:
                    connector.set_position_mode(PositionMode.HEDGE)
                    connector.set_leverage(trading_pair=trading_pair, leverage=self.leverage)
            self.set_leverage_flag = True

    def clean_and_store_executors(self):
        executors_to_store = [executor for executor in self.active_executors if executor.is_closed]
        if not os.path.exists(self.csv_path):
            df_header = pd.DataFrame([("timestamp",
                                       "exchange",
                                       "trading_pair",
                                       "side",
                                       "amount",
                                       "pnl",
                                       "close_timestamp",
                                       "entry_price",
                                       "close_price",
                                       "last_status",
                                       "sl",
                                       "tp",
                                       "tl",
                                       "order_type",
                                       "leverage")])
            df_header.to_csv(self.csv_path, mode='a', header=False, index=False)
        for executor in executors_to_store:
            self.stored_executors.append(executor)
            df = pd.DataFrame([(executor.config.timestamp,
                                executor.config.connector_name,
                                executor.config.trading_pair,
                                executor.config.side,
                                executor.config.amount,
                                executor.trade_pnl_pct,
                                executor.close_timestamp,
                                executor.entry_price,
                                executor.close_price,
                                executor.status,
                                executor.config.triple_barrier_config.stop_loss,
                                executor.config.triple_barrier_config.take_profit,
                                executor.config.triple_barrier_config.time_limit,
                                executor.config.triple_barrier_config.open_order_type,
                                self.leverage)])
            df.to_csv(self.csv_path, mode='a', header=False, index=False)
        self.active_executors = [executor for executor in self.active_executors if not executor.is_closed]

    def close_open_positions(self):
        # we are going to close all the open positions when the bot stops
        for connector_name, connector in self.connectors.items():
            for trading_pair, position in connector.account_positions.items():
                if position.position_side == PositionSide.LONG:
                    self.sell(connector_name=connector_name,
                              trading_pair=position.trading_pair,
                              amount=abs(position.amount),
                              order_type=OrderType.MARKET,
                              price=connector.get_mid_price(position.trading_pair),
                              position_action=PositionAction.CLOSE)
                elif position.position_side == PositionSide.SHORT:
                    self.buy(connector_name=connector_name,
                             trading_pair=position.trading_pair,
                             amount=abs(position.amount),
                             order_type=OrderType.MARKET,
                             price=connector.get_mid_price(position.trading_pair),
                             position_action=PositionAction.CLOSE)

    def is_margin_enough(self):
        quote_balance = self.connectors[self.exchange].get_available_balance(self.trading_pair.split("-")[-1])
        if self.order_amount_usd < quote_balance * self.leverage:
            return True
        else:
            self.logger().info("No enough margin to place orders.")
            return False
