import logging
import math
from decimal import Decimal
from typing import Union

from hummingbot.core.data_type.common import OrderType, PositionAction, PriceType, TradeType
from hummingbot.core.data_type.order_candidate import OrderCandidate, PerpetualOrderCandidate
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderFilledEvent,
    SellOrderCompletedEvent,
    SellOrderCreatedEvent,
)
from hummingbot.logger import HummingbotLogger
from hummingbot.smart_components.executors.executor_base import ExecutorBase
from hummingbot.smart_components.executors.position_executor.data_types import (
    PositionExecutorConfig,
    PositionExecutorStatus,
)
from hummingbot.smart_components.models.executors import CloseType, TrackedOrder
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class PositionExecutor(ExecutorBase):
    _logger = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, strategy: ScriptStrategyBase, config: PositionExecutorConfig,
                 update_interval: float = 1.0, max_retries: int = 3):
        if not (config.take_profit or config.stop_loss or config.time_limit):
            error = "At least one of take_profit, stop_loss or time_limit must be set"
            self.logger().error(error)
            raise ValueError(error)
        if config.time_limit_order_type != OrderType.MARKET or config.stop_loss_order_type != OrderType.MARKET:
            error = "Only market orders are supported for time_limit and stop_loss"
            self.logger().error(error)
            raise ValueError(error)
        super().__init__(strategy=strategy, config=config, connectors=[config.exchange], update_interval=update_interval)
        self.config: PositionExecutorConfig = config
        self._executor_status: PositionExecutorStatus = PositionExecutorStatus.NOT_STARTED

        # Order tracking
        self._open_order: TrackedOrder = TrackedOrder()
        self._close_order: TrackedOrder = TrackedOrder()
        self._take_profit_order: TrackedOrder = TrackedOrder()
        self._trailing_stop_price = Decimal("0")
        self._trailing_stop_activated = False
        self._max_retries = max_retries
        self._current_retries = 0

    @property
    def executor_status(self):
        return self._executor_status

    @executor_status.setter
    def executor_status(self, status: PositionExecutorStatus):
        self._executor_status = status

    @property
    def is_closed(self):
        return self.executor_status == PositionExecutorStatus.COMPLETED

    @property
    def is_perpetual(self):
        return self.is_perpetual_connector(self.exchange)

    @property
    def position_config(self):
        return self.config

    @property
    def exchange(self):
        return self.position_config.exchange

    @property
    def trading_pair(self):
        return self.position_config.trading_pair

    @property
    def amount(self):
        return self.position_config.amount

    @property
    def filled_amount(self):
        return self.open_order.executed_amount_base

    @property
    def entry_price(self):
        if self.open_order.average_executed_price:
            return self.open_order.average_executed_price
        elif self.position_config.entry_price:
            return self.position_config.entry_price
        else:
            price_type = PriceType.BestAsk if self.side == TradeType.BUY else PriceType.BestBid
            return self.get_price(self.exchange, self.trading_pair, price_type=price_type)

    @property
    def trailing_stop_config(self):
        return self.position_config.trailing_stop

    @property
    def close_price(self):
        # TODO: Evaluate if there is a close order instead of checking the state
        if self.executor_status == PositionExecutorStatus.COMPLETED and self.close_type not in [CloseType.EXPIRED,
                                                                                                CloseType.INSUFFICIENT_BALANCE]:
            return self.close_order.average_executed_price
        elif self.executor_status == PositionExecutorStatus.ACTIVE_POSITION:
            price_type = PriceType.BestBid if self.side == TradeType.BUY else PriceType.BestAsk
            return self.get_price(self.exchange, self.trading_pair, price_type=price_type)
        else:
            return self.entry_price

    @property
    def trade_pnl(self):
        if self.side == TradeType.BUY:
            return (self.close_price - self.entry_price) / self.entry_price
        else:
            return (self.entry_price - self.close_price) / self.entry_price

    @property
    def trade_pnl_quote(self):
        return self.trade_pnl * self.filled_amount * self.entry_price

    def get_net_pnl_quote(self):
        return self.trade_pnl_quote - self.cum_fees_quote

    def get_cum_fees_quote(self):
        return self.open_order.cum_fees_quote + self.close_order.cum_fees_quote

    def get_net_pnl_pct(self):
        if self.filled_amount == Decimal("0"):
            return Decimal("0")
        else:
            return self.net_pnl_quote / (self.filled_amount * self.entry_price)

    @property
    def end_time(self):
        if not self.position_config.time_limit:
            return None
        return self.position_config.timestamp + self.position_config.time_limit

    @property
    def side(self):
        return self.position_config.side

    @property
    def open_order_type(self):
        return self.position_config.open_order_type

    @property
    def take_profit_order_type(self):
        return self.position_config.take_profit_order_type

    @property
    def stop_loss_order_type(self):
        return self.position_config.stop_loss_order_type

    @property
    def time_limit_order_type(self):
        return self.position_config.time_limit_order_type

    @property
    def stop_loss_price(self):
        stop_loss_price = self.entry_price * (1 - self.config.stop_loss) if self.side == TradeType.BUY else \
            self.entry_price * (1 + self.config.stop_loss)
        return stop_loss_price

    @property
    def take_profit_price(self):
        take_profit_price = self.entry_price * (1 + self.config.take_profit) if self.side == TradeType.BUY else \
            self.entry_price * (1 - self.config.take_profit)
        return take_profit_price

    @property
    def open_order(self):
        return self._open_order

    @property
    def close_order(self):
        return self._close_order

    @property
    def take_profit_order(self):
        return self._take_profit_order

    def take_profit_condition(self):
        if self.side == TradeType.BUY:
            return self.close_price >= self.take_profit_price
        else:
            return self.close_price <= self.take_profit_price

    def stop_loss_condition(self):
        if self.side == TradeType.BUY:
            return self.close_price <= self.stop_loss_price
        else:
            return self.close_price >= self.stop_loss_price

    def time_limit_condition(self):
        return self._strategy.current_timestamp >= self.end_time

    def on_stop(self):
        if self.take_profit_order.order and self.take_profit_order.order.is_open:
            self.logger().info(f"Take profit order status: {self.take_profit_order.order.current_state}")
            self.remove_take_profit()

    async def control_task(self):
        if self.executor_status == PositionExecutorStatus.NOT_STARTED:
            self.control_open_order()
        elif self.executor_status == PositionExecutorStatus.ACTIVE_POSITION:
            self.control_barriers()

    def control_open_order(self):
        if not self.open_order.order_id:
            if not self.end_time or self.end_time >= self._strategy.current_timestamp:
                self.place_open_order()
            else:
                self.executor_status = PositionExecutorStatus.COMPLETED
                self.close_type = CloseType.EXPIRED
                self.stop()
        else:
            self.control_open_order_expiration()

    def place_open_order(self):
        order_id = self.place_order(
            connector_name=self.exchange,
            trading_pair=self.trading_pair,
            order_type=self.open_order_type,
            amount=self.amount,
            price=self.entry_price,
            side=self.side,
            position_action=PositionAction.OPEN,
        )
        self._open_order.order_id = order_id
        self.logger().info("Placing open order")

    def control_open_order_expiration(self):
        if self.end_time and self.end_time <= self._strategy.current_timestamp:
            self._strategy.cancel(
                connector_name=self.exchange,
                trading_pair=self.trading_pair,
                order_id=self._open_order.order_id
            )
            self.logger().info("Removing open order by time limit")

    def control_barriers(self):
        if not self.close_order.order_id:
            if self.position_config.stop_loss:
                self.control_stop_loss()
            if self.position_config.take_profit:
                self.control_take_profit()
            if self.position_config.time_limit:
                self.control_time_limit()

    def place_close_order(self, close_type: CloseType, price: Decimal = Decimal("NaN")):
        tp_partial_execution = self.take_profit_order.executed_amount_base if self.take_profit_order.executed_amount_base else Decimal("0")
        order_id = self.place_order(
            connector_name=self.exchange,
            trading_pair=self.trading_pair,
            order_type=OrderType.MARKET,
            amount=self.filled_amount - tp_partial_execution,
            price=price,
            side=TradeType.SELL if self.side == TradeType.BUY else TradeType.BUY,
            position_action=PositionAction.CLOSE,
        )
        self.close_type = close_type
        self._close_order.order_id = order_id
        self.logger().info(f"Placing close order --> Filled amount: {self.filled_amount} | TP Partial execution: {tp_partial_execution}")

    def control_stop_loss(self):
        if self.stop_loss_condition():
            self.place_close_order(close_type=CloseType.STOP_LOSS)
        elif self.trailing_stop_condition():
            self.place_close_order(close_type=CloseType.TRAILING_STOP)

    def control_take_profit(self):
        if self.take_profit_order_type.is_limit_type():
            if not self.take_profit_order.order_id:
                self.place_take_profit_limit_order()
            elif not math.isclose(self.take_profit_order.order.amount, self.open_order.executed_amount_base):
                self.renew_take_profit_order()
        elif self.take_profit_condition():
            self.place_close_order(close_type=CloseType.TAKE_PROFIT)

    def control_time_limit(self):
        if self.time_limit_condition():
            self.place_close_order(close_type=CloseType.TIME_LIMIT)

    def place_take_profit_limit_order(self):
        order_id = self.place_order(
            connector_name=self.config.exchange,
            trading_pair=self.config.trading_pair,
            amount=self.filled_amount,
            price=self.take_profit_price,
            order_type=self.take_profit_order_type,
            position_action=PositionAction.CLOSE,
            side=TradeType.BUY if self.side == TradeType.SELL else TradeType.SELL,
        )
        self.take_profit_order.order_id = order_id
        self.logger().info("Placing take profit order")

    def renew_take_profit_order(self):
        self.remove_take_profit()
        self.place_take_profit_limit_order()
        self.logger().info("Renewing take profit order")

    def remove_take_profit(self):
        self._strategy.cancel(
            connector_name=self.exchange,
            trading_pair=self.trading_pair,
            order_id=self._take_profit_order.order_id
        )
        self.logger().info("Removing take profit")

    def early_stop(self):
        if self.executor_status == PositionExecutorStatus.ACTIVE_POSITION:
            self.place_close_order(close_type=CloseType.EARLY_STOP)
        elif self.executor_status == PositionExecutorStatus.NOT_STARTED and self._open_order.order_id:
            self._strategy.cancel(
                connector_name=self.exchange,
                trading_pair=self.trading_pair,
                order_id=self._open_order.order_id
            )

    def process_order_created_event(self, _, market, event: Union[BuyOrderCreatedEvent, SellOrderCreatedEvent]):
        if self.open_order.order_id == event.order_id:
            self.open_order.order = self.get_in_flight_order(self.exchange, event.order_id)
            self.logger().info("Open Order Created")
        elif self.close_order.order_id == event.order_id:
            self.logger().info("Close Order Created")
            self.close_order.order = self.get_in_flight_order(self.exchange, event.order_id)
        elif self.take_profit_order.order_id == event.order_id:
            self.take_profit_order.order = self.get_in_flight_order(self.exchange, event.order_id)
            self.logger().info("Take profit Created")

    def process_order_completed_event(self, _, market, event: Union[BuyOrderCompletedEvent, SellOrderCompletedEvent]):
        if self.open_order.order_id == event.order_id:
            self.logger().info("Open Order Completed")
            self.executor_status = PositionExecutorStatus.ACTIVE_POSITION
        elif self.close_order.order_id == event.order_id:
            self.close_timestamp = event.timestamp
            self.executor_status = PositionExecutorStatus.COMPLETED
            self.logger().info(f"Closed by {self.close_type}")
            self.stop()
        elif self.take_profit_order.order_id == event.order_id:
            self.close_type = CloseType.TAKE_PROFIT
            self.executor_status = PositionExecutorStatus.COMPLETED
            self.close_timestamp = event.timestamp
            self.close_order.order_id = event.order_id
            self.close_order.order = self.take_profit_order.order
            self.logger().info(f"Closed by {self.close_type}")
            self.stop()

    def process_order_canceled_event(self, _, market, event: OrderCancelledEvent):
        if self.open_order.order_id == event.order_id:
            self.executor_status = PositionExecutorStatus.COMPLETED
            self.close_type = CloseType.EXPIRED
            self.close_timestamp = event.timestamp

    def process_order_filled_event(self, _, market, event: OrderFilledEvent):
        if self.open_order.order_id == event.order_id:
            if self.executor_status == PositionExecutorStatus.ACTIVE_POSITION:
                self.logger().info("Position incremented, updating take profit next tick.")
            else:
                self.executor_status = PositionExecutorStatus.ACTIVE_POSITION

    def process_order_failed_event(self, _, market, event: MarketOrderFailureEvent):
        self._current_retries += 1
        if self._current_retries <= self._max_retries:
            self.logger().info(f"Retrying order, attempt {self._current_retries}")
            if self.open_order.order_id == event.order_id:
                self.place_open_order()
            elif self.close_order.order_id == event.order_id:
                self.place_close_order(self.close_type)
            elif self.take_profit_order.order_id == event.order_id:
                self.take_profit_order.order_id = None
        else:
            self.logger().info("Max retries reached, terminating position executor")
            self.close_type = CloseType.FAILED
            self.stop()

    def to_json(self):
        return {
            "timestamp": self.position_config.timestamp,
            "exchange": self.exchange,
            "trading_pair": self.trading_pair,
            "side": self.side.name,
            "amount": self.filled_amount,
            "trade_pnl": self.trade_pnl,
            "trade_pnl_quote": self.trade_pnl_quote,
            "cum_fee_quote": self.cum_fees_quote,
            "net_pnl_quote": self.net_pnl_quote,
            "net_pnl": self.net_pnl_pct,
            "close_timestamp": self.close_timestamp,
            "executor_status": self.executor_status.name,
            "close_type": self.close_type.name if self.close_type else None,
            "entry_price": self.entry_price,
            "close_price": self.close_price,
            "sl": self.position_config.stop_loss,
            "tp": self.position_config.take_profit,
            "tl": self.position_config.time_limit,
            "open_order_type": self.open_order_type.name,
            "take_profit_order_type": self.take_profit_order_type.name,
            "stop_loss_order_type": self.stop_loss_order_type.name,
            "time_limit_order_type": self.time_limit_order_type.name,
            "leverage": self.position_config.leverage,
        }

    def to_format_status(self, scale=1.0):
        lines = []
        current_price = self.get_price(self.exchange, self.trading_pair)
        amount_in_quote = self.entry_price * (self.filled_amount if self.filled_amount > Decimal("0") else self.amount)
        quote_asset = self.trading_pair.split("-")[1]
        if self.is_closed:
            lines.extend([f"""
| Trading Pair: {self.trading_pair} | Exchange: {self.exchange} | Side: {self.side}
| Entry price: {self.entry_price:.6f} | Close price: {self.close_price:.6f} | Amount: {amount_in_quote:.4f} {quote_asset}
| Realized PNL: {self.trade_pnl_quote:.6f} {quote_asset} | Total Fee: {self.cum_fees_quote:.6f} {quote_asset}
| PNL (%): {self.net_pnl_pct * 100:.2f}% | PNL (abs): {self.net_pnl_quote:.6f} {quote_asset} | Close Type: {self.close_type}
"""])
        else:
            lines.extend([f"""
| Trading Pair: {self.trading_pair} | Exchange: {self.exchange} | Side: {self.side} |
| Entry price: {self.entry_price:.6f} | Close price: {self.close_price:.6f} | Amount: {amount_in_quote:.4f} {quote_asset}
| Unrealized PNL: {self.trade_pnl_quote:.6f} {quote_asset} | Total Fee: {self.cum_fees_quote:.6f} {quote_asset}
| PNL (%): {self.net_pnl_pct * 100:.2f}% | PNL (abs): {self.net_pnl_quote:.6f} {quote_asset} | Close Type: {self.close_type}
        """])

        if self.executor_status == PositionExecutorStatus.ACTIVE_POSITION:
            progress = 0
            if self.position_config.time_limit:
                time_scale = int(scale * 60)
                seconds_remaining = (self.end_time - self._strategy.current_timestamp)
                time_progress = (self.position_config.time_limit - seconds_remaining) / self.position_config.time_limit
                time_bar = "".join(['*' if i < time_scale * time_progress else '-' for i in range(time_scale)])
                lines.extend([f"Time limit: {time_bar}"])

            if self.position_config.take_profit and self.position_config.stop_loss:
                price_scale = int(scale * 60)
                stop_loss_price = self.stop_loss_price
                take_profit_price = self.take_profit_price
                if self.side == TradeType.BUY:
                    price_range = take_profit_price - stop_loss_price
                    progress = (current_price - stop_loss_price) / price_range
                elif self.side == TradeType.SELL:
                    price_range = stop_loss_price - take_profit_price
                    progress = (stop_loss_price - current_price) / price_range
                price_bar = [f'--{current_price:.5f}--' if i == int(price_scale * progress) else '-' for i in range(price_scale)]
                price_bar.insert(0, f"SL:{stop_loss_price:.5f}")
                price_bar.append(f"TP:{take_profit_price:.5f}")
                lines.extend(["".join(price_bar)])
            if self.trailing_stop_config:
                lines.extend([f"Trailing stop status: {self._trailing_stop_activated} | Trailing stop price: {self._trailing_stop_price:.5f}"])
            lines.extend(["-----------------------------------------------------------------------------------------------------------"])
        return lines

    def trailing_stop_condition(self):
        if self.trailing_stop_config:
            price = self.close_price
            if not self._trailing_stop_activated and self.activation_price_condition(price):
                self._trailing_stop_activated = True
                self._trailing_stop_price = price
                self.logger().info(f"Trailing stop activated at {price}")
            if self._trailing_stop_activated:
                self.update_trailing_stop_price(price)
                if self.side == TradeType.BUY:
                    return price < self._trailing_stop_price
                else:
                    return price > self._trailing_stop_price
            else:
                return False

    def activation_price_condition(self, price):
        side = 1 if self.side == TradeType.BUY else -1
        activation_price = self.entry_price * (1 + side * self.trailing_stop_config.activation_price)
        return price >= activation_price if self.side == TradeType.BUY \
            else price <= activation_price

    def update_trailing_stop_price(self, price):
        if self.side == TradeType.BUY:
            trailing_stop_price = price * (1 - self.trailing_stop_config.trailing_delta)
            if trailing_stop_price > self._trailing_stop_price:
                self._trailing_stop_price = trailing_stop_price
        else:
            trailing_stop_price = price * (1 + self.trailing_stop_config.trailing_delta)
            if trailing_stop_price < self._trailing_stop_price:
                self._trailing_stop_price = trailing_stop_price

    def validate_sufficient_balance(self):
        if self.is_perpetual:
            order_candidate = PerpetualOrderCandidate(
                trading_pair=self.trading_pair,
                is_maker=self.open_order_type.is_limit_type(),
                order_type=self.open_order_type,
                order_side=self.side,
                amount=self.amount,
                price=self.entry_price,
                leverage=Decimal(self.position_config.leverage),
            )
        else:
            order_candidate = OrderCandidate(
                trading_pair=self.trading_pair,
                is_maker=self.open_order_type.is_limit_type(),
                order_type=self.open_order_type,
                order_side=self.side,
                amount=self.amount,
                price=self.entry_price,
            )
        adjusted_order_candidates = self.adjust_order_candidates(self.config.exchange, [order_candidate])
        if adjusted_order_candidates[0].amount == Decimal("0"):
            self.close_type = CloseType.INSUFFICIENT_BALANCE
            self.executor_status = PositionExecutorStatus.COMPLETED
            self.logger().error("Not enough budget to open position.")
            self.stop()
