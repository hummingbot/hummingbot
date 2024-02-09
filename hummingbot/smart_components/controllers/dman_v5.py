import time
import uuid
from decimal import Decimal
from typing import List, Optional

import pandas as pd
import pandas_ta as ta  # noqa: F401

from hummingbot.core.data_type.common import TradeType
from hummingbot.smart_components.executors.dca_executor.data_types import DCAExecutorConfig, DCAMode
from hummingbot.smart_components.executors.position_executor.data_types import TrailingStop
from hummingbot.smart_components.models.executor_actions import (
    CreateExecutorAction,
    ExecutorAction,
    StopExecutorAction,
    StoreExecutorAction,
)
from hummingbot.smart_components.models.executors_info import ExecutorInfo
from hummingbot.smart_components.order_level_distributions.distributions import Distributions
from hummingbot.smart_components.strategy_frameworks.controller_base import ControllerConfigBase
from hummingbot.smart_components.strategy_frameworks.generic_strategy.generic_controller import GenericController


class DManV5Config(ControllerConfigBase):
    """
    Configuration required to run the PairsTrading strategy.
    """
    strategy_name: str = "dman_v5"
    exchange: str = "binance_perpetual"
    trading_pair: str = "DOGE-USDT"
    leverage: int = 20

    # indicator configuration
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9

    # DCA configuration
    dca_refresh_time: int = 60
    max_dca_per_side: int = 3
    min_distance_between_dca: float = 0.02
    order_amount_quote: Decimal = Decimal("10")
    amount_ratio_increase: float = 1.5
    n_levels: int = 5

    top_order_start_spread: float = 0.001
    start_spread: float = 0.02
    spread_ratio_increase: float = 2.0
    time_limit: int = 60 * 60 * 24 * 7
    take_profit: Decimal = Decimal("0.02")
    stop_loss: Decimal = Decimal("0.1")
    trailing_stop: TrailingStop = TrailingStop(activation_price=Decimal("0.01"),
                                               trailing_delta=Decimal("0.005"))
    activation_bounds: Optional[Decimal] = None


class DManV5(GenericController):
    def __init__(self, config: DManV5Config):
        super().__init__(config)
        self.config = config
        self.amounts_quote = Distributions.geometric(n_levels=self.config.n_levels, start=float(self.config.order_amount_quote),
                                                     ratio=self.config.amount_ratio_increase)
        self.spreads = [Decimal(self.config.top_order_start_spread)] + Distributions.geometric(
            n_levels=self.config.n_levels - 1, start=self.config.start_spread,
            ratio=self.config.spread_ratio_increase)
        self.stored_dcas = set()

    async def determine_actions(self) -> [List[ExecutorAction]]:
        """
        Determine actions based on the provided executor handler report.
        """
        proposal = []
        if self.all_candles_ready:
            proposal.extend(self.create_actions_proposal())
            proposal.extend(self.stop_actions_proposal())
            proposal.extend(self.store_actions_proposal())
        return proposal

    def create_actions_proposal(self) -> List[CreateExecutorAction]:
        """
        Create a list of actions to create new DCA executors. Will evaluate if the conditions of max DCA per side and
        minimum distance between DCA are met to create a new executor. If there is no active DCA executor, it will create
        a new one immediately.
        """
        proposal = []

        # access the active DCA executors and close price
        active_dca_executors = self._executor_handler_info.active_dca_executors
        close_price = self.get_close_price(self.config.trading_pair)
        signal = self.get_signal()

        # compute number of DCAs per side
        long_dcas = [executor for executor in active_dca_executors if executor.config.side == TradeType.BUY]
        short_dcas = [executor for executor in active_dca_executors if executor.config.side == TradeType.SELL]
        n_long_dcas = len(long_dcas)
        n_short_dcas = len(short_dcas)

        # evaluate long dca conditions
        if signal == 1:
            if n_long_dcas == 0:
                proposal.append(self.create_dca_action(TradeType.BUY, close_price))
            elif n_long_dcas < self.config.max_dca_per_side:
                # evaluate if all the DCAs are active to create a new one
                all_dca_trading_condition = all([executor.is_trading for executor in long_dcas])
                # compute the min price of all the DCA open prices to see if we should create another DCA
                min_long_dca_average_price = min([executor.custom_info["max_price"] for executor in long_dcas])
                min_price_distance_condition = float(close_price) < float(min_long_dca_average_price) * (1 - self.config.min_distance_between_dca)

                if all_dca_trading_condition and min_price_distance_condition:
                    proposal.append(self.create_dca_action(TradeType.BUY, close_price))

        # evaluate short dca conditions
        elif signal == -1:
            if n_short_dcas == 0:
                proposal.append(self.create_dca_action(TradeType.SELL, close_price))
            elif n_short_dcas < self.config.max_dca_per_side:
                # evaluate if all the DCAs are active to create a new one
                all_dca_trading_condition = all([executor.is_trading for executor in long_dcas])
                # compute the max price of all the DCA open prices to see if we should create another DCAa
                max_short_dca_open_price = max([executor.custom_info["min_price"] for executor in short_dcas])
                max_price_distance_condition = float(close_price) > float(max_short_dca_open_price) * (1 + self.config.min_distance_between_dca)
                if all_dca_trading_condition and max_price_distance_condition:
                    proposal.append(self.create_dca_action(TradeType.SELL, close_price))
        return proposal

    def stop_actions_proposal(self) -> List[StopExecutorAction]:
        """
        Create a list of actions to stop the DCA executors that have reached their time limit.
        """
        proposal = []
        for executor in self._executor_handler_info.active_dca_executors:
            if executor.timestamp + self.config.dca_refresh_time < time.time() and not executor.is_trading:
                proposal.append(StopExecutorAction(executor_id=executor.id, controller_id=self.config.id))
        return proposal

    def create_dca_action(self, trade_type: TradeType, close_price: Decimal):
        dca_id = str(uuid.uuid4())
        prices = [close_price * (1 - spread) if trade_type == TradeType.BUY else close_price * (1 + spread) for spread
                  in self.spreads]
        return CreateExecutorAction(
            controller_id=self.config.id,
            executor_config=DCAExecutorConfig(
                id=dca_id,
                timestamp=time.time(),
                exchange=self.config.exchange,
                trading_pair=self.config.trading_pair,
                side=trade_type,
                amounts_quote=self.amounts_quote,
                prices=prices,
                stop_loss=self.config.stop_loss,
                take_profit=self.config.take_profit,
                trailing_stop=self.config.trailing_stop,
                time_limit=self.config.time_limit,
                leverage=self.config.leverage,
                mode=DCAMode.MAKER,
                activation_bounds=self.config.activation_bounds,
            ))

    def get_signal(self):
        candles_df = self.candles[0].candles_df
        macd_output = ta.macd(candles_df["close"], fast=self.config.macd_fast, slow=self.config.macd_slow,
                              signal=self.config.macd_signal)
        macd = macd_output[f"MACD_{self.config.macd_fast}_{self.config.macd_slow}_{self.config.macd_signal}"].apply(
            lambda x: -1 if x > 0 else 1)
        macdh = macd_output[f"MACDh_{self.config.macd_fast}_{self.config.macd_slow}_{self.config.macd_signal}"].apply(
            lambda x: 1 if x > 0 else -1)

        signal = macd + macdh
        signal = signal.apply(lambda x: 1 if x == 2 else (-1 if x == -2 else 0))
        return signal.iat[-1]

    def store_actions_proposal(self) -> List[StoreExecutorAction]:
        """
        Create a list of actions to store the DCA executors that have been terminated. For reporting purposes,
        we are going to wait 60 seconds before storing the executor.
        """
        proposal = []
        for executor in self._executor_handler_info.closed_dca_executors:
            if executor.id not in self.stored_dcas and executor.close_timestamp + 60 < time.time():
                proposal.append(StoreExecutorAction(executor_id=executor.id, controller_id=self.config.id))
                self.stored_dcas.add(executor.id)
        return proposal

    @staticmethod
    def executors_info_to_df(executors_info: List[ExecutorInfo]) -> pd.DataFrame:
        """
        Convert a list of executor handler info to a dataframe.
        """
        df = pd.DataFrame([ei.dict() for ei in executors_info])
        # Normalize the desired data
        keys_to_expand = ['current_position_average_price', 'filled_amount_quote', "side"]
        expanded_data = df['custom_info'].apply(pd.Series)[keys_to_expand]

        # Concatenate with the original DataFrame
        df_expanded = pd.concat([df, expanded_data], axis=1).drop('custom_info', axis=1)

        # Rename the columns
        columns_to_show = ['id', 'timestamp', 'side', 'status', 'net_pnl_pct', 'net_pnl_quote', 'cum_fees_quote',
                           'close_type', 'current_position_average_price', 'filled_amount_quote']
        return df_expanded[columns_to_show]
