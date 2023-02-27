import math
import datetime
import os
from decimal import Decimal
from typing import Dict, List

import pandas as pd
import pandas_ta as ta  # noqa: F401

from hummingbot import data_path
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide
from hummingbot.smart_components.position_executor.data_types import PositionConfig
from hummingbot.smart_components.position_executor.position_executor import PositionExecutor
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class GeometricTrailingGrid(ScriptStrategyBase):
    """
    A living grid strategy that follows the price anywhere.
    When strategy starts, it will map price in the steps according to steps interval for maximum steps calculated from
    the stop loss defined.
    When price go down, it will execute buys according to steps mapping, until it hits stop_loss for each step
    When price go up, it will recreate the steps mapping.
    @TODO: #1 Deleting uppermost step not by price, but by the sell event when the stop loss triggered
    @TODO: #2 Enable the script to execute on multiple pairs

    """

    # Define the trading pair and exchange
    base = "ETH"
    quote = "USDT"
    exchange = "binance_perpetual_testnet"

    # Maximum position executors at a time
    active_steps: List[PositionExecutor] = []
    stored_steps: List[PositionExecutor] = []
    step_candidates = []

    # Configure the parameters for the position
    stop_loss = 0.25
    take_profit = 0.02
    time_limit = 60 * 60
    step_interval = 0.002

    # Calculate maximum number of steps
    max_steps = math.ceil(math.log(1 + stop_loss) / math.log(1 + step_interval) + 1)

    # Configure the leverage and order amount the bot is going to use
    set_leverage_flag = None
    leverage = 1
    order_amount_usd = Decimal("12")

    today = datetime.datetime.today()
    trading_pair = f"{base}-{quote}"

    # Define where to store data
    csv_path = data_path() + f"/{exchange}_{trading_pair}_{today.day:02d}-{today.month:02d}-{today.year}.csv"
    markets = {exchange: {trading_pair}}

    def init_step_candidates(self):
        # Initiate list to map what price the next steps below current price should trigger
        current_price = self.connectors[self.exchange].get_mid_price(self.trading_pair)
        step_candidates = []
        for n in range(self.max_steps):
            price_n = current_price * Decimal(math.pow(1 - self.step_interval, n))
            stop_loss_n = price_n * Decimal(1 - self.stop_loss)
            step_candidates.append({'step_price_n': price_n, 'stop_loss_n': stop_loss_n})
        self.step_candidates = step_candidates

    def __init__(self, connectors: Dict[str, ConnectorBase]):
        super().__init__(connectors)

    def get_active_steps(self):
        return [step_executor for step_executor in self.active_steps
                if not step_executor.is_closed]

    def get_closed_steps(self):
        return self.stored_steps

    def on_tick(self):
        """
        Create step_candidates when not found
        If price went down exceed step_interval, then execute buy based on step_candidates
        If price going up exceed step_interval, then put the new price & SL on uppermost step_candidates
        If price wet down exceed stop_loss on uppermost step (then order will be closed), then delete the uppermost step
        """
        self.check_and_set_leverage()
        self.clean_and_store_steps()
        price = self.connectors[self.exchange].get_mid_price(self.trading_pair)
        if not self.step_candidates:
            self.init_step_candidates()
            self.execute_step()
        if price < self.step_candidates[1]['step_price_n']:
            self.execute_step()
            del self.step_candidates[0]
        elif price > self.step_candidates[0]['step_price_n'] * Decimal(1 + self.step_interval):
            self.execute_step()
            self.step_candidates.insert(0, {'step_price_n': price, 'stop_loss_n': (price * Decimal(1 - self.stop_loss))})
            self.step_candidates.pop()
        if price < self.step_candidates[0]['stop_loss_n']:
            del self.step_candidates[0]

    def execute_step(self):
        price = self.connectors[self.exchange].get_mid_price(self.trading_pair)
        step_executor = PositionExecutor(
            position_config=PositionConfig(
                timestamp=self.current_timestamp,
                trading_pair=self.trading_pair,
                exchange=self.exchange,
                order_type=OrderType.MARKET,
                side=PositionSide.LONG,
                entry_price=price,
                amount=self.order_amount_usd / price,
                stop_loss=self.stop_loss,
                take_profit=self.take_profit,
                time_limit=self.time_limit),
            strategy=self,
        )
        self.active_steps.append(step_executor)
        self.logger().info(f"Bought {self.order_amount_usd} on {price}")

    def on_stop(self):
        """
        Without this functionality, the network iterator will continue running forever after stopping the strategy
        That's why is necessary to introduce this new feature to make a custom stop with the strategy.
        """
        # we are going to close all the open positions when the bot stops
        self.close_open_positions()

    def format_status(self) -> str:
        if not self.ready_to_trade:
            return "Market connectors are not ready."
        lines = []

        if len(self.stored_steps) > 0:
            lines.extend([
                "\n########################################## Closed Steps ##########################################"])

        for step_executor in self.stored_steps:
            lines.extend([f"|Step id: {step_executor.timestamp}"])
            lines.extend(step_executor.to_format_status())
            lines.extend([
                "---------------------------------------------------------------------------------------------------"])

        if len(self.active_steps) > 0:
            lines.extend([
                "\n########################################## Active Steps ##########################################"])

        for step_executor in self.active_steps:
            lines.extend([f"|Step id: {step_executor.timestamp}"])
            lines.extend(step_executor.to_format_status())
            lines.extend([f"Total active steps {len(self.active_steps)}"])

        return "\n".join(lines)

    def check_and_set_leverage(self):
        if not self.set_leverage_flag:
            for connector in self.connectors.values():
                for trading_pair in connector.trading_pairs:
                    connector.set_position_mode(PositionMode.HEDGE)
                    connector.set_leverage(trading_pair=trading_pair, leverage=self.leverage)
            self.set_leverage_flag = True

    def clean_and_store_steps(self):
        steps_to_store = [step_executor for step_executor in self.active_steps if step_executor.is_closed]
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
        for step_executor in steps_to_store:
            self.stored_steps.append(step_executor)
            df = pd.DataFrame([(step_executor.timestamp,
                                step_executor.exchange,
                                step_executor.trading_pair,
                                step_executor.side,
                                step_executor.amount,
                                step_executor.pnl,
                                step_executor.close_timestamp,
                                step_executor.entry_price,
                                step_executor.close_price,
                                step_executor.status,
                                step_executor.position_config.stop_loss,
                                step_executor.position_config.take_profit,
                                step_executor.position_config.time_limit,
                                step_executor.open_order_type,
                                self.leverage)])
            df.to_csv(self.csv_path, mode='a', header=False, index=False)
        self.active_steps = [step_executor for step_executor in self.active_steps if not step_executor.is_closed]

    def close_open_positions(self):
        # we are going to close all the open positions when the bot stops
        for connector_name, connector in self.connectors.items():
            for trading_pair, position in connector.account_positions.items():
                self.sell(
                    connector_name=connector_name,
                    trading_pair=position.trading_pair,
                    amount=abs(position.amount),
                    order_type=OrderType.MARKET,
                    price=connector.get_mid_price(position.trading_pair),
                    position_action=PositionAction.CLOSE
                )
                self.logger().info(f"connector_name= {connector_name} connector= {connector}")

    def is_margin_enough(self):
        quote_balance = self.connectors[self.exchange].get_available_balance(self.trading_pair.split("-")[-1])
        if self.bot_profile_order_amount_usd < quote_balance * self.bot_profile_leverage:
            return True
        else:
            self.logger().info("No enough margin to place orders.")
            return False
