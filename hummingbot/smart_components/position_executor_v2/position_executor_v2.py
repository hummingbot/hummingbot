from decimal import Decimal
from typing import Union

from hummingbot.core.data_type.common import OrderType, PositionAction, TradeType
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderFilledEvent,
    SellOrderCompletedEvent,
    SellOrderCreatedEvent,
)
from hummingbot.smart_components.position_executor.data_types import (
    CloseType,
    PositionConfig,
    PositionExecutorStatus,
    TrackedOrder,
)
from hummingbot.smart_components.smart_component_base import SmartComponentBase
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class PositionExecutorV2(SmartComponentBase):
    def __init__(self, strategy: ScriptStrategyBase, position_config: PositionConfig):
        super().__init__(strategy, [position_config.exchange])
        if not (position_config.take_profit or position_config.stop_loss or position_config.time_limit):
            error = "At least one of take_profit, stop_loss or time_limit must be set"
            self.logger().error(error)
            raise ValueError(error)
        self._position_config: PositionConfig = position_config
        self._close_type = None
        self._close_timestamp = None
        self._executor_status: PositionExecutorStatus = PositionExecutorStatus.NOT_STARTED

        # Order tracking
        self._open_order: TrackedOrder = TrackedOrder()
        self._close_order: TrackedOrder = TrackedOrder()
        self._take_profit_order: TrackedOrder = TrackedOrder()

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
    def position_config(self):
        return self._position_config

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
            return self.get_price(self.exchange, self.trading_pair)

    @property
    def close_price(self):
        if self.close_order.order:
            return self.close_order.average_executed_price

    @property
    def pnl(self):
        close_price = self.close_price if self.close_price else self.get_price(self.exchange, self.trading_pair)
        entry_price = self.entry_price if self.entry_price else self.get_price(self.exchange, self.trading_pair)
        if self.side == TradeType.BUY:
            return (close_price - entry_price) / entry_price
        else:
            return (entry_price - close_price) / entry_price

    @property
    def pnl_usd(self):
        return self.pnl * self.filled_amount * self.entry_price

    @property
    def cum_fees(self):
        return self.open_order.cum_fees + self.close_order.cum_fees

    @property
    def end_time(self):
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
        stop_loss_price = self.entry_price * (1 - self._position_config.stop_loss) if self.side == TradeType.BUY else \
            self.entry_price * (1 + self._position_config.stop_loss)
        return stop_loss_price

    @property
    def take_profit_price(self):
        take_profit_price = self.entry_price * (1 + self._position_config.take_profit) if self.side == TradeType.BUY else \
            self.entry_price * (1 - self._position_config.take_profit)
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
            return self.get_price(self.exchange, self.trading_pair) >= self.take_profit_price
        else:
            return self.get_price(self.exchange, self.trading_pair) <= self.take_profit_price

    def stop_loss_condition(self):
        if self.side == TradeType.BUY:
            return self.get_price(self.exchange, self.trading_pair) <= self.stop_loss_price
        else:
            return self.get_price(self.exchange, self.trading_pair) >= self.stop_loss_price

    def time_limit_condition(self):
        return self._strategy.current_timestamp >= self.end_time

    def on_stop(self):
        if self.take_profit_order.order and self.take_profit_order.order.is_open:
            self.logger().info(f"Take profit order status: {self.take_profit_order.order.current_state}")
            self.remove_take_profit()

    def control_task(self):
        if self.executor_status == PositionExecutorStatus.NOT_STARTED:
            self.control_open_order()
        elif self.executor_status == PositionExecutorStatus.ACTIVE_POSITION:
            self.control_barriers()

    def control_open_order(self):
        if self.end_time >= self._strategy.current_timestamp:
            if not self.open_order.order_id:
                self.place_open_order()
            else:
                self.control_open_order_expiration()
        else:
            self.executor_status = PositionExecutorStatus.COMPLETED
            self.terminate_control_loop()

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
        if self.end_time <= self._strategy.current_timestamp:
            self._strategy.cancel(
                connector_name=self.exchange,
                trading_pair=self.trading_pair,
                order_id=self._open_order.order_id
            )
            self.logger().info("Removing open order by time limit")

    def control_barriers(self):
        if not self.close_order.order_id:
            self.control_stop_loss()
            self.control_take_profit()
            self.control_time_limit()
        else:
            self.control_close_order()

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
        self._close_type = close_type
        self._close_order.order_id = order_id
        self.logger().info("Placing close order")

    def control_stop_loss(self):
        if self.stop_loss_condition():
            self.place_close_order(close_type=CloseType.STOP_LOSS)

    def control_take_profit(self):
        if self.take_profit_order_type.is_limit_type():
            if not self.take_profit_order.order_id:
                self.place_take_profit_limit_order()
            elif self.take_profit_order.executed_amount_base != self.open_order.executed_amount_base:
                self.renew_take_profit_order()
        elif self.take_profit_order_type == OrderType.MARKET and self.take_profit_condition():
            self.place_close_order(close_type=CloseType.TAKE_PROFIT)

    def control_time_limit(self):
        if self.time_limit_condition():
            self.place_close_order(close_type=CloseType.TIME_LIMIT)

    def place_take_profit_limit_order(self):
        price = self.get_price(self.exchange, self.trading_pair) if self.take_profit_order_type == OrderType.MARKET else self.take_profit_price
        order_id = self.place_order(
            connector_name=self._position_config.exchange,
            trading_pair=self._position_config.trading_pair,
            amount=self.open_order.executed_amount_base,
            price=price,
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
            self.logger().info(f"Closed by {self._close_type}")
            self.executor_status = PositionExecutorStatus.COMPLETED
        elif self.take_profit_order.order_id == event.order_id:
            self._close_type = CloseType.TAKE_PROFIT
            self.close_timestamp = event.timestamp
            self.logger().info(f"Closed by {self._close_type}")

    def process_order_canceled_event(self, _, market, event: OrderCancelledEvent):
        if self.open_order.order_id == event.order_id:
            self.executor_status = PositionExecutorStatus.COMPLETED
            self._close_type = CloseType.EXPIRED
            self.close_timestamp = event.timestamp

    def process_order_filled_event(self, _, market, event: OrderFilledEvent):
        if self.open_order.order_id == event.order_id:
            if self.executor_status == PositionExecutorStatus.ACTIVE_POSITION:
                self.logger().info("Position incremented, updating take profit next tick.")
            else:
                self.executor_status = PositionExecutorStatus.ACTIVE_POSITION

    def process_order_failed_event(self, _, market, event: MarketOrderFailureEvent):
        if self.open_order.order_id == event.order_id:
            self.place_open_order()
        elif self.close_order.order_id == event.order_id:
            self.place_close_order(self._close_type)
        elif self.take_profit_order.order_id == event.order_id:
            self.place_take_profit_limit_order()

    def control_close_order(self):
        # TODO: Implement functionality for closing order (ie. limit order type for sl and tl)
        pass

    def to_format_status(self):
        lines = []
        current_price = self.get_price(self.exchange, self.trading_pair)
        amount_in_quote = self.amount * self.entry_price
        base_asset = self.trading_pair.split("-")[0]
        quote_asset = self.trading_pair.split("-")[1]
        if self.is_closed:
            lines.extend([f"""
| Trading Pair: {self.trading_pair} | Exchange: {self.exchange} | Side: {self.side} | Amount: {amount_in_quote:.4f} {quote_asset} - {self.amount:.4f} {base_asset}
| Entry price: {self.entry_price:.4f}  | Close price: {self.close_price:.4f} --> PNL: {self.pnl * 100:.2f}%
| Realized PNL: {self.pnl_usd:.4f} {quote_asset} | Total Fee: {self.cum_fees:.4f} {quote_asset} --> Net return: {(self.pnl_usd - self.cum_fees):.4f} {quote_asset}
| Status: {self.status}
"""])
        else:
            lines.extend([f"""
| Trading Pair: {self.trading_pair} | Exchange: {self.exchange} | Side: {self.side} | Amount: {amount_in_quote:.4f} {quote_asset} - {self.amount:.4f} {base_asset}
| Entry price: {self.entry_price:.4f}  | Current price: {current_price:.4f} --> PNL: {self.pnl * 100:.2f}%
| Unrealized PNL: {self.pnl_usd:.4f} {quote_asset} | Total Fee: {self.cum_fees:.4f} {quote_asset} --> Net return: {(self.pnl_usd - self.cum_fees):.4f} {quote_asset}
        """])
        time_scale = 67
        price_scale = 47

        progress = 0
        if self.executor_status == PositionExecutorStatus.ACTIVE_POSITION:
            seconds_remaining = (self.end_time - self._strategy.current_timestamp)
            time_progress = (self.position_config.time_limit - seconds_remaining) / self.position_config.time_limit
            time_bar = "".join(['*' if i < time_scale * time_progress else '-' for i in range(time_scale)])
            lines.extend([f"Time limit: {time_bar}"])
            stop_loss_price = self.stop_loss_price
            take_profit_price = self.take_profit_price
            if self.side == TradeType.BUY:
                price_range = take_profit_price - stop_loss_price
                progress = (current_price - stop_loss_price) / price_range
            elif self.side == TradeType.SELL:
                price_range = stop_loss_price - take_profit_price
                progress = (stop_loss_price - current_price) / price_range
            price_bar = [f'--{current_price:.4f}--' if i == int(price_scale * progress) else '-' for i in
                         range(price_scale)]
            price_bar.insert(0, f"SL:{stop_loss_price:.4f}")
            price_bar.append(f"TP:{take_profit_price:.4f}")
            lines.extend(["".join(price_bar), "\n"])
            lines.extend(["-----------------------------------------------------------------------------------------------------------"])
        return lines
