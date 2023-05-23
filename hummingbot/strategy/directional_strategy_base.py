import datetime
import os
from decimal import Decimal
from typing import Dict, List, Set

import pandas as pd
import pandas_ta as ta  # noqa: F401

from hummingbot import data_path
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.data_feed.candles_feed.candles_base import CandlesBase
from hummingbot.smart_components.position_executor.data_types import PositionConfig, TrailingStop
from hummingbot.smart_components.position_executor.position_executor import PositionExecutor
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class DirectionalStrategyBase(ScriptStrategyBase):
    """
    Base class to create directional strategies using the PositionExecutor.
    """
    directional_strategy_name: str
    # Define the trading pair and exchange that we want to use and the csv where we are going to store the entries
    trading_pair: str
    exchange: str

    # Maximum position executors at a time
    max_executors: int = 1
    active_executors: List[PositionExecutor] = []
    stored_executors: List[PositionExecutor] = []

    # Configure the parameters for the position
    stop_loss: float = 0.01
    take_profit: float = 0.01
    time_limit: int = 120
    open_order_type = OrderType.MARKET
    open_order_slippage_buffer: int = 0.001
    take_profit_order_type: OrderType = OrderType.MARKET
    stop_loss_order_type: OrderType = OrderType.MARKET
    time_limit_order_type: OrderType = OrderType.MARKET
    trailing_stop_activation_delta = 0.003
    trailing_stop_trailing_delta = 0.001

    # Create the candles that we want to use and the thresholds for the indicators
    candles: List[CandlesBase]

    # Configure the leverage and order amount the bot is going to use
    set_leverage_flag = None
    leverage = 10
    order_amount_usd = Decimal("10")
    markets: Dict[str, Set[str]] = {}

    @property
    def all_candles_ready(self):
        """
        Checks if the candlesticks are full.
        """
        return all([candle.is_ready for candle in self.candles])

    def get_csv_path(self) -> str:
        today = datetime.datetime.today()
        csv_path = data_path() + f"/{self.directional_strategy_name}_position_executors_{self.exchange}_{self.trading_pair}_{today.day:02d}-{today.month:02d}-{today.year}.csv"
        return csv_path

    def __init__(self, connectors: Dict[str, ConnectorBase]):
        # Is necessary to start the Candles Feed.
        super().__init__(connectors)
        for candle in self.candles:
            candle.start()

    def on_stop(self):
        """
        Without this functionality, the network iterator will continue running forever after stopping the strategy
        That's why is necessary to introduce this new feature to make a custom stop with the strategy.
        """
        # we are going to close all the open positions when the bot stops
        self.close_open_positions()
        for candle in self.candles:
            candle.stop()

    def get_active_executors(self):
        return [signal_executor for signal_executor in self.active_executors
                if not signal_executor.is_closed]

    def on_tick(self):
        self.check_and_set_leverage()
        if len(self.get_active_executors()) < self.max_executors and self.all_candles_ready:
            position_config = self.get_position_config()
            if position_config:
                signal_executor = PositionExecutor(
                    strategy=self,
                    position_config=position_config,
                )
                self.active_executors.append(signal_executor)
        self.clean_and_store_executors()

    def get_position_config(self):
        signal = self.get_signal()
        if signal == 0:
            return None
        else:
            price = self.connectors[self.exchange].get_mid_price(self.trading_pair)
            side = TradeType.BUY if signal == 1 else TradeType.SELL
            if self.open_order_type.is_limit_type():
                price = price * (1 - signal * self.open_order_slippage_buffer)
            position_config = PositionConfig(
                timestamp=self.current_timestamp,
                trading_pair=self.trading_pair,
                exchange=self.exchange,
                side=side,
                amount=self.order_amount_usd / price,
                take_profit=self.take_profit,
                stop_loss=self.stop_loss,
                time_limit=self.time_limit,
                entry_price=price,
                open_order_type=self.open_order_type,
                take_profit_order_type=self.take_profit_order_type,
                stop_loss_order_type=self.stop_loss_order_type,
                time_limit_order_type=self.open_order_type,
                trailing_stop=TrailingStop(
                    activation_price_delta=self.trailing_stop_activation_delta,
                    trailing_delta=self.trailing_stop_trailing_delta
                )
            )
            return position_config

    def get_signal(self):
        """Base method to get the signal from the candles."""
        raise NotImplementedError

    def format_status(self) -> str:
        """
        Displays the three candlesticks involved in the script with RSI, BBANDS and EMA.
        """
        if not self.ready_to_trade:
            return "Market connectors are not ready."
        lines = []

        if len(self.stored_executors) > 0:
            lines.extend(["\n################################## Closed Executors ##################################"])
        for executor in self.stored_executors:
            lines.extend([f"|Signal id: {executor.position_config.timestamp}"])
            lines.extend(executor.to_format_status())
            lines.extend([
                "-----------------------------------------------------------------------------------------------------------"])

        if len(self.active_executors) > 0:
            lines.extend(["\n################################## Active Executors ##################################"])

        for executor in self.active_executors:
            lines.extend([f"|Signal id: {executor.position_config.timestamp}"])
            lines.extend(executor.to_format_status())
        if self.all_candles_ready:
            lines.extend([
                "\n############################################ Market Data ############################################\n"])
            lines.extend([f"Value: {self.get_signal()}"])
            lines.extend(self.market_data_extra_info())
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
        csv_path = self.get_csv_path()
        if not os.path.exists(csv_path):
            df_header = pd.DataFrame([("timestamp",
                                       "exchange",
                                       "trading_pair",
                                       "side",
                                       "amount",
                                       "trade_pnl",
                                       "trade_pnl_quote",
                                       "cum_fee_quote",
                                       "net_pnl_quote",
                                       "net_pnl",
                                       "close_timestamp",
                                       "executor_status",
                                       "close_type",
                                       "entry_price",
                                       "close_price",
                                       "sl",
                                       "tp",
                                       "tl",
                                       "open_order_type",
                                       "take_profit_order_type",
                                       "stop_loss_order_type",
                                       "time_limit_order_type",
                                       "leverage"
                                       )])
            df_header.to_csv(csv_path, mode='a', header=False, index=False)
        for executor in executors_to_store:
            self.stored_executors.append(executor)
            df = pd.DataFrame([(executor.position_config.timestamp,
                                executor.exchange,
                                executor.trading_pair,
                                executor.side,
                                executor.amount,
                                executor.trade_pnl,
                                executor.trade_pnl_quote,
                                executor.cum_fee_quote,
                                executor.net_pnl_quote,
                                executor.net_pnl,
                                executor.close_timestamp,
                                executor.executor_status,
                                executor.close_type,
                                executor.entry_price,
                                executor.close_price,
                                executor.position_config.stop_loss,
                                executor.position_config.take_profit,
                                executor.position_config.time_limit,
                                executor.open_order_type,
                                executor.take_profit_order_type,
                                executor.stop_loss_order_type,
                                executor.time_limit_order_type,
                                self.leverage)])
            df.to_csv(self.get_csv_path(), mode='a', header=False, index=False)
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

    def market_data_extra_info(self):
        return ["\n"]
