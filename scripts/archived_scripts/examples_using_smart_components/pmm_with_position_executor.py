import datetime
import os
import time
from decimal import Decimal
from typing import Dict, List

import pandas as pd

from hummingbot import data_path
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, PriceType, TradeType
from hummingbot.data_feed.candles_feed.candles_factory import CandlesConfig, CandlesFactory
from hummingbot.smart_components.executors.position_executor.data_types import (
    PositionExecutorConfig,
    PositionExecutorStatus,
    TrailingStop,
)
from hummingbot.smart_components.executors.position_executor.position_executor import PositionExecutor
from hummingbot.smart_components.models.executors import CloseType
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class PMMWithPositionExecutor(ScriptStrategyBase):
    """
    BotCamp Cohort: Sept 2022
    Design Template: https://hummingbot-foundation.notion.site/Simple-PMM-63cc765486dd42228d3da0b32537fc92
    Video: -
    Description:
    The bot will place two orders around the price_source (mid price or last traded price) in a trading_pair on
    exchange, with a distance defined by the ask_spread and bid_spread. Every order_refresh_time in seconds,
    the bot will cancel and replace the orders.
    """
    market_making_strategy_name = "pmm_with_position_executor"
    trading_pair = "FRONT-BUSD"
    exchange = "binance"

    # Configure order levels and spreads
    order_levels = {
        1: {"spread_factor": 1.7, "order_amount_usd": Decimal("13")},
        2: {"spread_factor": 3.4, "order_amount_usd": Decimal("21")},
    }
    position_mode: PositionMode = PositionMode.HEDGE
    active_executors: List[PositionExecutor] = []
    stored_executors: List[PositionExecutor] = []

    # Configure the parameters for the position
    stop_loss: float = 0.03
    take_profit: float = 0.015
    time_limit: int = 3600 * 24
    executor_refresh_time: int = 30
    open_order_type = OrderType.LIMIT
    take_profit_order_type: OrderType = OrderType.MARKET
    stop_loss_order_type: OrderType = OrderType.MARKET
    time_limit_order_type: OrderType = OrderType.MARKET
    trailing_stop_activation_delta = 0.003
    trailing_stop_trailing_delta = 0.001
    # Here you can use for example the LastTrade price to use in your strategy
    price_source = PriceType.MidPrice
    candles = [CandlesFactory.get_candle(CandlesConfig(connector=exchange, trading_pair=trading_pair, interval="3m", max_records=1000))
               ]

    # Configure the leverage and order amount the bot is going to use
    set_leverage_flag = None
    leverage = 1
    inventory_balance_pct = Decimal("0.4")
    inventory_balance_tol = Decimal("0.05")
    _inventory_balanced = False
    spreads = None
    reference_price = None

    markets = {exchange: {trading_pair}}

    @property
    def is_perpetual(self):
        """
        Checks if the exchange is a perpetual market.
        """
        return "perpetual" in self.exchange

    def get_csv_path(self) -> str:
        today = datetime.datetime.today()
        csv_path = data_path() + f"/{self.market_making_strategy_name}_position_executors_{self.exchange}_{self.trading_pair}_{today.day:02d}-{today.month:02d}-{today.year}.csv"
        return csv_path

    @property
    def all_candles_ready(self):
        """
        Checks if the candlesticks are full.
        """
        return all([candle.is_ready for candle in self.candles])

    def get_active_executors(self):
        return [signal_executor for signal_executor in self.active_executors
                if not signal_executor.is_closed]

    def __init__(self, connectors: Dict[str, ConnectorBase]):
        # Is necessary to start the Candles Feed.
        super().__init__(connectors)
        for candle in self.candles:
            candle.start()
        self._active_bids = {level: None for level in self.order_levels.keys()}
        self._active_asks = {level: None for level in self.order_levels.keys()}

    def on_stop(self):
        """
        Without this functionality, the network iterator will continue running forever after stopping the strategy
        That's why is necessary to introduce this new feature to make a custom stop with the strategy.
        """
        if self.is_perpetual:
            # we are going to close all the open positions when the bot stops
            self.close_open_positions()
        else:
            self.check_and_rebalance_inventory()
        for candle in self.candles:
            candle.stop()

    def on_tick(self):
        if self.is_perpetual:
            self.check_and_set_leverage()
        elif not self._inventory_balanced:
            self.check_and_rebalance_inventory()
        if self.all_candles_ready:
            self.update_parameters()
            self.check_and_create_executors()
        self.clean_and_store_executors()

    def update_parameters(self):
        candles_df = self.get_candles_with_features()
        natr = candles_df["NATR_21"].iloc[-1]
        bbp = candles_df["BBP_200_2.0"].iloc[-1]
        price_multiplier = ((0.5 - bbp) / 0.5) * natr * 0.3
        price = self.connectors[self.exchange].get_price_by_type(self.trading_pair, self.price_source)
        self.spreads = natr
        self.reference_price = price * Decimal(str(1 + price_multiplier))

    def get_candles_with_features(self):
        candles_df = self.candles[0].candles_df
        candles_df.ta.bbands(length=200, append=True)
        candles_df.ta.natr(length=21, scalar=2, append=True)
        return candles_df

    def create_executor(self, side: TradeType, price: Decimal, amount_usd: Decimal):
        position_config = PositionExecutorConfig(
            timestamp=self.current_timestamp,
            trading_pair=self.trading_pair,
            exchange=self.exchange,
            side=side,
            amount=amount_usd / price,
            take_profit=self.take_profit,
            stop_loss=self.stop_loss,
            time_limit=self.time_limit,
            entry_price=price,
            open_order_type=self.open_order_type,
            take_profit_order_type=self.take_profit_order_type,
            stop_loss_order_type=self.stop_loss_order_type,
            time_limit_order_type=self.time_limit_order_type,
            trailing_stop=TrailingStop(
                activation_price=self.trailing_stop_activation_delta,
                trailing_delta=self.trailing_stop_trailing_delta
            ),
            leverage=self.leverage,
        )
        executor = PositionExecutor(
            strategy=self,
            config=position_config,
        )
        return executor

    def check_and_set_leverage(self):
        if not self.set_leverage_flag:
            for connector in self.connectors.values():
                for trading_pair in connector.trading_pairs:
                    connector.set_position_mode(self.position_mode)
                    connector.set_leverage(trading_pair=trading_pair, leverage=self.leverage)
            self.set_leverage_flag = True

    def clean_and_store_executors(self):
        executors_to_store = []
        for level, executor in self._active_bids.items():
            if executor:
                age = time.time() - executor.position_config.timestamp
                if age > self.executor_refresh_time and executor.executor_status == PositionExecutorStatus.NOT_STARTED:
                    executor.early_stop()
                if executor.is_closed:
                    executors_to_store.append(executor)
                    self._active_bids[level] = None
        for level, executor in self._active_asks.items():
            if executor:
                age = time.time() - executor.position_config.timestamp
                if age > self.executor_refresh_time and executor.executor_status == PositionExecutorStatus.NOT_STARTED:
                    executor.early_stop()
                if executor.is_closed:
                    executors_to_store.append(executor)
                    self._active_asks[level] = None

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
                                executor.cum_fees_quote,
                                executor.net_pnl_quote,
                                executor.net_pnl_pct,
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

    def format_status(self) -> str:
        """
        Displays the three candlesticks involved in the script with RSI, BBANDS and EMA.
        """
        if not self.ready_to_trade:
            return "Market connectors are not ready."
        lines = []

        if len(self.stored_executors) > 0:
            lines.extend(["\n################################## Closed Executors ##################################"])
        for executor in [executor for executor in self.stored_executors if executor.close_type not in [CloseType.EXPIRED, CloseType.INSUFFICIENT_BALANCE]]:
            lines.extend([f"|Signal id: {executor.position_config.timestamp}"])
            lines.extend(executor.to_format_status())
            lines.extend([
                "-----------------------------------------------------------------------------------------------------------"])

        lines.extend(["\n################################## Active Bids ##################################"])
        for level, executor in self._active_bids.items():
            if executor:
                lines.extend([f"|Signal id: {executor.position_config.timestamp}"])
                lines.extend(executor.to_format_status())
                lines.extend([
                    "-----------------------------------------------------------------------------------------------------------"])
        lines.extend(["\n################################## Active Asks ##################################"])
        for level, executor in self._active_asks.items():
            if executor:
                lines.extend([f"|Signal id: {executor.position_config.timestamp}"])
                lines.extend(executor.to_format_status())
                lines.extend([
                    "-----------------------------------------------------------------------------------------------------------"])
        if self.all_candles_ready:
            lines.extend(["\n################################## Market Data ##################################\n"])
            lines.extend(self.market_data_extra_info())
        else:
            lines.extend(["", "  No data collected."])

        return "\n".join(lines)

    def check_and_rebalance_inventory(self):
        base_balance = self.connectors[self.exchange].get_available_balance(self.trading_pair.split("-")[0])
        quote_balance = self.connectors[self.exchange].get_available_balance(self.trading_pair.split("-")[1])
        price = self.connectors[self.exchange].get_price_by_type(self.trading_pair, self.price_source)
        total_balance = base_balance + quote_balance / price
        balance_ratio = base_balance / total_balance
        if abs(balance_ratio - self.inventory_balance_pct) < self.inventory_balance_tol:
            self._inventory_balanced = True
            return
        base_target_balance = total_balance * Decimal(self.inventory_balance_pct)
        base_delta = base_target_balance - base_balance
        if base_delta > 0:
            self.buy(self.exchange, self.trading_pair, base_delta, OrderType.MARKET, price)
        elif base_delta < 0:
            self.sell(self.exchange, self.trading_pair, base_delta, OrderType.MARKET, price)
        self._inventory_balanced = True

    def check_and_create_executors(self):
        for level, executor in self._active_asks.items():
            if executor is None:
                level_config = self.order_levels[level]
                price = self.reference_price * Decimal(1 + self.spreads * level_config["spread_factor"])
                executor = self.create_executor(side=TradeType.SELL, price=price, amount_usd=level_config["order_amount_usd"])
                self._active_asks[level] = executor

        for level, executor in self._active_bids.items():
            if executor is None:
                level_config = self.order_levels[level]
                price = self.reference_price * Decimal(1 - self.spreads * level_config["spread_factor"])
                executor = self.create_executor(side=TradeType.BUY, price=price, amount_usd=level_config["order_amount_usd"])
                self._active_bids[level] = executor
