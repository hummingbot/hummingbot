import time
import uuid
from decimal import Decimal
from typing import List, Set

from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.smart_components.executors.position_executor.data_types import PositionExecutorConfig
from hummingbot.smart_components.strategy_frameworks.controller_base import ControllerConfigBase
from hummingbot.smart_components.strategy_frameworks.data_types import (
    BotAction,
    CreatePositionExecutorAction,
    ExecutorHandlerReport,
    StopExecutorAction,
)
from hummingbot.smart_components.strategy_frameworks.generic_strategy.generic_controller import GenericController


class PairsTradingConfig(ControllerConfigBase):
    """
    Configuration required to run the PairsTrading strategy.
    """
    exchange: str = "binance_perpetual"
    trading_pair: str = "BTC-USDT"
    trading_pair_2: str = "ETH-USDT"
    strategy_name: str = "pairs_trading"
    leverage: int = 100
    amount: float = 20
    max_inventory_asset_1: float = 100
    max_inventory_asset_2: float = 100
    min_inventory_asset_1: float = -100
    min_inventory_asset_2: float = -100
    min_delta: float = -50
    max_delta: float = 50
    order_refresh_time: int = 60 * 15
    bbands_length: int = 20
    bbands_std_dev: float = 2.0
    spread_factor: float = 1.0
    global_take_profit: float = 0.01
    global_stop_loss: float = 0.01


class PairsTrading(GenericController):

    def __init__(self, config: PairsTradingConfig):
        super().__init__(config)
        self.config = config

    def update_strategy_markets_dict(self, markets_dict: dict[str, Set] = {}):
        if self.config.exchange not in markets_dict:
            markets_dict[self.config.exchange] = {self.config.trading_pair, self.config.trading_pair_2}
        else:
            markets_dict[self.config.exchange].add(self.config.trading_pair)
            markets_dict[self.config.exchange].add(self.config.trading_pair_2)
        return markets_dict

    def determine_actions(self, executor_handler_report: ExecutorHandlerReport) -> [List[BotAction]]:
        """
        Determine actions based on the provided executor handler report.
        """
        if self.all_candles_ready:
            actions_proposal: List[BotAction] = self.create_actions_proposal()
            filtered_actions_proposal: List[BotAction] = self.filter_actions_proposal(
                actions_proposal, executor_handler_report)
            return filtered_actions_proposal
        else:
            return []

    def compute_signal_and_spread_multiplier(self) -> (int, float):
        """
        Compute the signal and spread multiplier.
        """
        return 1, 0.01

    def create_actions_proposal(self) -> List[CreatePositionExecutorAction]:
        """
        Create a list of actions based on the provided signal and spread multiplier.
        Side = 1 means buy asset 1 and sell asset 2
        Side = -1 means sell asset 1 and buy asset 2
        """
        signal, spread_multiplier = self.compute_signal_and_spread_multiplier()
        proposal: List[CreatePositionExecutorAction] = []
        trading_pair_1_close_price = self.get_close_price(self.config.trading_pair)
        trading_pair_2_close_price = self.get_close_price(self.config.trading_pair_2)
        if signal == 1:
            tp_1_entry_price = trading_pair_1_close_price * Decimal(1 - self.config.spread_factor * spread_multiplier)
            tp_2_entry_price = trading_pair_2_close_price * Decimal(1 + self.config.spread_factor * spread_multiplier)
            proposal.append(CreatePositionExecutorAction(
                position_config=PositionExecutorConfig(
                    timestamp=time.time(),
                    trading_pair=self.config.trading_pair,
                    exchange=self.config.exchange,
                    amount=Decimal(self.config.amount) / tp_1_entry_price,
                    time_limit=60 * 60 * 24 * 7,
                    open_order_type=OrderType.LIMIT,
                    leverage=self.config.leverage,
                    side=TradeType.BUY,
                    entry_price=tp_1_entry_price,
                ),
                level_id=uuid.uuid4().hex))
            proposal.append(CreatePositionExecutorAction(
                position_config=PositionExecutorConfig(
                    timestamp=time.time(),
                    trading_pair=self.config.trading_pair_2,
                    exchange=self.config.exchange,
                    amount=Decimal(self.config.amount) / tp_2_entry_price,
                    time_limit=60 * 60 * 24 * 7,
                    open_order_type=OrderType.LIMIT,
                    leverage=self.config.leverage,
                    side=TradeType.SELL,
                    entry_price=tp_2_entry_price,
                ),
                level_id=uuid.uuid4().hex))
        elif signal == -1:
            tp_1_entry_price = trading_pair_1_close_price * Decimal(1 + self.config.spread_factor * spread_multiplier)
            tp_2_entry_price = trading_pair_2_close_price * Decimal(1 - self.config.spread_factor * spread_multiplier)
            proposal.append(CreatePositionExecutorAction(
                position_config=PositionExecutorConfig(
                    timestamp=time.time(),
                    trading_pair=self.config.trading_pair,
                    exchange=self.config.exchange,
                    amount=Decimal(self.config.amount) / tp_1_entry_price,
                    time_limit=60 * 60 * 24 * 7,
                    open_order_type=OrderType.LIMIT,
                    leverage=self.config.leverage,
                    side=TradeType.SELL,
                    entry_price=tp_1_entry_price,
                ),
                level_id=uuid.uuid4().hex))
            proposal.append(CreatePositionExecutorAction(
                position_config=PositionExecutorConfig(
                    timestamp=time.time(),
                    trading_pair=self.config.trading_pair_2,
                    exchange=self.config.exchange,
                    amount=Decimal(self.config.amount) / tp_2_entry_price,
                    time_limit=60 * 60 * 24 * 7,
                    open_order_type=OrderType.LIMIT,
                    leverage=self.config.leverage,
                    side=TradeType.BUY,
                    entry_price=tp_2_entry_price,
                ),
                level_id=uuid.uuid4().hex))
        return proposal

    def filter_actions_proposal(self, actions_proposal: List[CreatePositionExecutorAction],
                                executor_handler_report: ExecutorHandlerReport) -> List[BotAction]:
        """
        Filter the actions proposal based on the provided executor handler report.
        """
        if executor_handler_report.active_position_executors.empty:
            return actions_proposal
        else:
            executors_df = executor_handler_report.active_position_executors

            # Adjust the amount based on side
            executors_df['adjusted_amount'] = executors_df.apply(
                lambda row: row['amount'] if row['side'] == 'BUY' else -row['amount'], axis=1)

            # Current net position for each trading pair
            current_net_positions = executors_df.groupby('trading_pair')['adjusted_amount'].sum()

            # Current delta
            current_delta = (current_net_positions.get(self.config.trading_pair, 0) -
                             current_net_positions.get(self.config.trading_pair_2, 0))

            # Identify open orders (not started) by trading pair and side
            not_started_executors = executors_df[executors_df["executor_status"] == "NOT_STARTED"]
            open_orders = set((row['trading_pair'], row['side']) for _, row in not_started_executors.iterrows())

            filtered_proposals = []
            for action in actions_proposal:
                trading_pair = action.position_config.trading_pair
                side = action.position_config.side
                amount = action.position_config.amount

                # Potential new net position after action
                potential_net_position = current_net_positions.get(trading_pair, 0) + (
                    amount if side == TradeType.BUY else -amount)
                action_key = (action.position_config.trading_pair, "BUY" if action.position_config.side == TradeType.BUY else "SELL")

                # Skip if there's a matching open order (not started) for this trading pair and side
                if action_key in open_orders:
                    continue

                # Check inventory constraints
                if trading_pair == self.config.trading_pair:
                    if not self.config.min_inventory_asset_1 <= potential_net_position <= self.config.max_inventory_asset_1:
                        continue
                    # Delta management for trading pair 1
                    if current_delta < self.config.min_delta and side == TradeType.SELL:
                        continue
                    if current_delta > self.config.max_delta and side == TradeType.BUY:
                        continue
                elif trading_pair == self.config.trading_pair_2:
                    if not self.config.min_inventory_asset_2 <= potential_net_position <= self.config.max_inventory_asset_2:
                        continue
                    # Delta management for trading pair 2
                    if current_delta < self.config.min_delta and side == TradeType.BUY:
                        continue
                    if current_delta > self.config.max_delta and side == TradeType.SELL:
                        continue

                # If the action passes all constraints, add to filtered proposals
                filtered_proposals.append(action)
            # Get the executors that have not been started for more than order_refresh_time
            executors_to_stop = executors_df.loc[(executors_df["executor_status"] == "NOT_STARTED") & (executors_df["timestamp"] < time.time() - self.config.order_refresh_time), "level_id"].values
            for executor_id in executors_to_stop:
                filtered_proposals.append(StopExecutorAction(executor_id=executor_id))
            return filtered_proposals
