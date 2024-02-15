from decimal import Decimal

from hummingbot.core.data_type.common import OrderType, PositionMode, TradeType
from hummingbot.smart_components.executors.position_executor.data_types import (
    PositionExecutorConfig,
    TripleBarrierConfig,
)
from hummingbot.smart_components.executors.position_executor.position_executor import PositionExecutor
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class TestPositionExecutorScript(ScriptStrategyBase):
    exchange = "binance_perpetual"
    trading_pair = "BTC-USDT"
    order_amount_usd = 150
    spread = Decimal("0.0004")
    active_long_position_executors = []
    active_short_position_executors = []
    stopped_position_executors = []
    position_mode = PositionMode.HEDGE
    leverage = 100
    account_config_set = False

    triple_barrier_config = TripleBarrierConfig(
        stop_loss=Decimal("0.005"),
        take_profit=Decimal("0.0007"),
        time_limit=600,
        open_order_type=OrderType.LIMIT,
        take_profit_order_type=OrderType.LIMIT,
    )
    markets = {exchange: {trading_pair}}

    def on_stop(self):
        all_executors = self.active_long_position_executors + self.active_short_position_executors
        for position_executor in all_executors:
            position_executor.early_stop()

    def store_position_executors(self):
        for position_executor in self.active_long_position_executors:
            if position_executor.is_closed:
                self.stopped_position_executors.append(position_executor)
                self.active_long_position_executors.remove(position_executor)
        for position_executor in self.active_short_position_executors:
            if position_executor.is_closed:
                self.stopped_position_executors.append(position_executor)
                self.active_short_position_executors.remove(position_executor)

    def create_position_executor(self, side: TradeType, amount: Decimal, price: Decimal):
        position_executor = PositionExecutor(
            strategy=self,
            config=PositionExecutorConfig(
                timestamp=self.current_timestamp,
                trading_pair=self.trading_pair,
                exchange=self.exchange,
                side=side,
                amount=amount,
                entry_price=price,
                triple_barrier_config=self.triple_barrier_config,
                leverage=self.leverage,
            )
        )
        position_executor.start()
        return position_executor

    def on_tick(self):
        if not self.account_config_set:
            self.connectors["binance_perpetual"].set_position_mode(self.position_mode)
            self.connectors["binance_perpetual"].set_leverage("BTC-USDT", self.leverage)
            self.account_config_set = True
        price = self.connectors["binance_perpetual"].get_price("BTC-USDT", True)
        if len(self.active_long_position_executors) == 0:
            order_price = price * (1 - self.spread)
            amount = self.order_amount_usd / order_price
            position_executor = self.create_position_executor(TradeType.BUY, amount, order_price)
            self.active_long_position_executors.append(position_executor)
        if len(self.active_short_position_executors) == 0:
            order_price = price * (1 + self.spread)
            amount = self.order_amount_usd / order_price
            position_executor = self.create_position_executor(TradeType.SELL, amount, order_price)
            self.active_short_position_executors.append(position_executor)
        self.store_position_executors()

    def format_status(self) -> str:
        original_info = super().format_status()
        all_executors = self.active_long_position_executors + self.active_short_position_executors
        active_pe_info = [pe.to_format_status()[0] for pe in all_executors]
        if len(active_pe_info) > 0:
            position_executor_str = "\n".join(active_pe_info)
            pe_active_report = "Position Executors:\n" + position_executor_str
        else:
            pe_active_report = "No active position executors"
        stored_executors_close_types = [pe.close_type for pe in self.stopped_position_executors]
        grouped_close_types = {close_type: stored_executors_close_types.count(close_type) for close_type in set(stored_executors_close_types)}
        pe_stopped_report = "\n".join([f"{k}: {v}" for k, v in grouped_close_types.items()])
        return f"{original_info}\n{pe_active_report}\n{pe_stopped_report}"
