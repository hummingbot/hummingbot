import asyncio
import logging
from decimal import Decimal
from typing import List, Tuple, Union

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionSide
from hummingbot.core.event.event_forwarder import SourceInfoEventForwarder
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketEvent,
    MarketOrderFailureEvent,
    OrderCancelledEvent,
    OrderFilledEvent,
    SellOrderCompletedEvent,
    SellOrderCreatedEvent,
)
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.logger import HummingbotLogger
from hummingbot.smart_components.position_executor.data_types import (
    PositionConfig,
    PositionExecutorStatus,
    TrackedOrder,
)
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class PositionExecutor:
    _logger = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self,
                 position_config: PositionConfig,
                 strategy: ScriptStrategyBase):
        self._position_config: PositionConfig = position_config
        self._strategy: ScriptStrategyBase = strategy
        self._status: PositionExecutorStatus = PositionExecutorStatus.NOT_STARTED
        self._open_order: TrackedOrder = TrackedOrder()
        self._take_profit_order: TrackedOrder = TrackedOrder()
        self._time_limit_order: TrackedOrder = TrackedOrder()
        self._stop_loss_order: TrackedOrder = TrackedOrder()
        self._close_timestamp = None

        self._cancel_order_forwarder = SourceInfoEventForwarder(self.process_order_canceled_event)
        self._create_buy_order_forwarder = SourceInfoEventForwarder(self.process_order_created_event)
        self._create_sell_order_forwarder = SourceInfoEventForwarder(self.process_order_created_event)

        self._fill_order_forwarder = SourceInfoEventForwarder(self.process_order_filled_event)

        self._complete_buy_order_forwarder = SourceInfoEventForwarder(self.process_order_completed_event)
        self._complete_sell_order_forwarder = SourceInfoEventForwarder(self.process_order_completed_event)

        self._failed_order_forwarder = SourceInfoEventForwarder(self.process_order_failed_event)

        self._event_pairs: List[Tuple[MarketEvent, SourceInfoEventForwarder]] = [
            (MarketEvent.OrderCancelled, self._cancel_order_forwarder),
            (MarketEvent.BuyOrderCreated, self._create_buy_order_forwarder),
            (MarketEvent.SellOrderCreated, self._create_sell_order_forwarder),
            (MarketEvent.OrderFilled, self._fill_order_forwarder),
            (MarketEvent.BuyOrderCompleted, self._complete_buy_order_forwarder),
            (MarketEvent.SellOrderCompleted, self._complete_sell_order_forwarder),
            (MarketEvent.OrderFailure, self._failed_order_forwarder),
        ]
        self.register_events()
        self.terminated = asyncio.Event()
        safe_ensure_future(self.control_loop())

    @property
    def position_config(self):
        return self._position_config

    @property
    def status(self):
        return self._status

    @property
    def is_closed(self):
        return self.status in [PositionExecutorStatus.CLOSED_BY_TIME_LIMIT,
                               PositionExecutorStatus.CLOSED_BY_STOP_LOSS,
                               PositionExecutorStatus.CLOSED_BY_TAKE_PROFIT,
                               PositionExecutorStatus.CANCELED_BY_TIME_LIMIT]

    @status.setter
    def status(self, status: PositionExecutorStatus):
        self._status = status

    @property
    def connector(self) -> ConnectorBase:
        return self._strategy.connectors[self._position_config.exchange]

    @property
    def exchange(self):
        return self.position_config.exchange

    @property
    def trading_pair(self):
        return self.position_config.trading_pair

    @property
    def amount(self):
        if self.open_order.executed_amount_base == Decimal("0"):
            return self.position_config.amount
        else:
            return self.open_order.executed_amount_base

    @property
    def entry_price(self):
        if not self.open_order.average_executed_price:
            entry_price = self.position_config.entry_price
            price = entry_price if entry_price else self.connector.get_mid_price(self.trading_pair)
        else:
            price = self.open_order.average_executed_price
        return price

    @property
    def close_price(self):
        if self.status == PositionExecutorStatus.CLOSED_BY_STOP_LOSS and self.stop_loss_order.order:
            return self.stop_loss_order.average_executed_price
        elif self.status == PositionExecutorStatus.CLOSED_BY_TAKE_PROFIT and self.take_profit_order.order:
            return self.take_profit_order.average_executed_price
        elif self.status == PositionExecutorStatus.CLOSED_BY_TIME_LIMIT and self.take_profit_order.order:
            return self.time_limit_order.average_executed_price
        else:
            return None

    @property
    def pnl(self):
        if self.status in [PositionExecutorStatus.CLOSED_BY_TIME_LIMIT,
                           PositionExecutorStatus.CLOSED_BY_STOP_LOSS,
                           PositionExecutorStatus.CLOSED_BY_TAKE_PROFIT]:
            if self.side == PositionSide.LONG:
                return (self.close_price - self.entry_price) / self.entry_price
            else:
                return (self.entry_price - self.close_price) / self.entry_price
        elif self.status == PositionExecutorStatus.ACTIVE_POSITION:
            current_price = self.connector.get_mid_price(self.trading_pair)
            if self.side == PositionSide.LONG:
                return (current_price - self.entry_price) / self.entry_price
            else:
                return (self.entry_price - current_price) / self.entry_price
        else:
            return Decimal("0")

    @property
    def pnl_usd(self):
        return self.pnl * self.amount * self.entry_price

    @property
    def cum_fees(self):
        return self.open_order.cum_fees + self.take_profit_order.cum_fees + self.stop_loss_order.cum_fees + self.time_limit_order.cum_fees

    @property
    def timestamp(self):
        return self.position_config.timestamp

    @property
    def time_limit(self):
        return self.position_config.time_limit

    @property
    def end_time(self):
        return self.timestamp + self.time_limit

    @property
    def side(self):
        return self.position_config.side

    @property
    def open_order_type(self):
        return self.position_config.order_type

    @property
    def stop_loss_price(self):
        stop_loss_price = self.entry_price * (
            1 - self._position_config.stop_loss) if self.side == PositionSide.LONG else self.entry_price * (
            1 + self._position_config.stop_loss)
        return stop_loss_price

    @property
    def take_profit_price(self):
        take_profit_price = self.entry_price * (
            1 + self._position_config.take_profit) if self.side == PositionSide.LONG else self.entry_price * (
            1 - self._position_config.take_profit)
        return take_profit_price

    def get_order(self, order_id: str):
        order = self.connector._order_tracker.fetch_order(client_order_id=order_id)
        return order

    @property
    def open_order(self):
        return self._open_order

    @property
    def close_order(self):
        if self.status == PositionExecutorStatus.CLOSED_BY_TAKE_PROFIT:
            return self.take_profit_order
        elif self.status == PositionExecutorStatus.CLOSED_BY_STOP_LOSS:
            return self.stop_loss_order
        elif self.status == PositionExecutorStatus.CLOSED_BY_TIME_LIMIT:
            return self.time_limit_order
        else:
            return None

    @property
    def take_profit_order(self):
        return self._take_profit_order

    @property
    def stop_loss_order(self):
        return self._stop_loss_order

    @property
    def time_limit_order(self):
        return self._time_limit_order

    async def control_loop(self):
        while not self.terminated.is_set():
            self.control_position()
            await asyncio.sleep(1)

    def control_position(self):
        if self.status == PositionExecutorStatus.NOT_STARTED:
            self.control_open_order()
        elif self.status == PositionExecutorStatus.ORDER_PLACED:
            self.control_cancel_order_by_time_limit()
        elif self.status == PositionExecutorStatus.ACTIVE_POSITION:
            self.control_take_profit()
            self.control_stop_loss()
            self.control_time_limit()
        elif self.status == PositionExecutorStatus.CLOSE_PLACED:
            self.control_close_order()
        elif self.is_closed:
            self.clean_executor()

    def control_close_order(self):
        if self.stop_loss_order.order_id and self.stop_loss_order.order \
                and self.stop_loss_order.order.is_failure:
            self.place_stop_loss_order()
        elif self.time_limit_order.order_id and self.time_limit_order.order \
                and self.time_limit_order.order.is_failure:
            self.place_time_limit_order()

    def clean_executor(self):
        if self.take_profit_order.order and self.take_profit_order.order.is_open:
            self.logger().info(f"Take profit order status: {self.take_profit_order.order.current_state}")
            self.remove_take_profit()
        else:
            self.terminated.set()

    def control_open_order(self):
        if self.end_time >= self._strategy.current_timestamp:
            if not self.open_order.order_id:
                self.place_open_order()
        else:
            self.status = PositionExecutorStatus.CANCELED_BY_TIME_LIMIT

    def control_cancel_order_by_time_limit(self):
        if self.end_time <= self._strategy.current_timestamp:
            self._strategy.cancel(
                connector_name=self.exchange,
                trading_pair=self.trading_pair,
                order_id=self._open_order.order_id
            )
            self.logger().info("Removing open order by time limit")

    def control_take_profit(self):
        if not self.take_profit_order.order_id and self.open_order.order:
            self.place_take_profit_order()
        elif self.take_profit_order.order and self.open_order.executed_amount_base != self.take_profit_order.order.amount:
            self.logger().info(f"""
            Updating take profit since:
            Open order amount base == {self.open_order.executed_amount_base}
            Take profit amount base == {self.take_profit_order.order.amount}""")
            self.remove_take_profit()
            self.place_take_profit_order()

    def control_stop_loss(self):
        current_price = self.connector.get_mid_price(self.trading_pair)
        trigger_stop_loss = False
        if self.side == PositionSide.LONG and current_price <= self.stop_loss_price:
            trigger_stop_loss = True
        elif self.side == PositionSide.SHORT and current_price >= self.stop_loss_price:
            trigger_stop_loss = True

        if trigger_stop_loss:
            if not self.stop_loss_order.order_id and self.open_order.order:
                self.place_stop_loss_order()
                self.status = PositionExecutorStatus.CLOSE_PLACED

    def control_time_limit(self):
        position_expired = self.end_time < self._strategy.current_timestamp
        if position_expired:
            if not self._time_limit_order.order_id and self.open_order.order:
                self.place_time_limit_order()
                self.status = PositionExecutorStatus.CLOSE_PLACED

    def process_order_completed_event(self,
                                      event_tag: int,
                                      market: ConnectorBase,
                                      event: Union[BuyOrderCompletedEvent, SellOrderCompletedEvent]):
        if self.open_order.order_id == event.order_id:
            self.status = PositionExecutorStatus.ACTIVE_POSITION
        elif self.stop_loss_order.order_id == event.order_id:
            self.status = PositionExecutorStatus.CLOSED_BY_STOP_LOSS
            self.close_timestamp = event.timestamp
            self.logger().info("Closed by Stop loss")
        elif self.time_limit_order.order_id == event.order_id:
            self.status = PositionExecutorStatus.CLOSED_BY_TIME_LIMIT
            self.close_timestamp = event.timestamp
            self.logger().info("Closed by Time Limit")
        elif self.take_profit_order.order_id == event.order_id:
            self.status = PositionExecutorStatus.CLOSED_BY_TAKE_PROFIT
            self.close_timestamp = event.timestamp
            self.logger().info("Closed by Take Profit")

    def process_order_created_event(self,
                                    event_tag: int,
                                    market: ConnectorBase,
                                    event: Union[BuyOrderCreatedEvent, SellOrderCreatedEvent]):
        if self.open_order.order_id == event.order_id:
            self.open_order.order = self.get_order(event.order_id)
            self.status = PositionExecutorStatus.ORDER_PLACED
        elif self.take_profit_order.order_id == event.order_id:
            self.take_profit_order.order = self.get_order(event.order_id)
            self.logger().info("Take profit Created")
        elif self.stop_loss_order.order_id == event.order_id:
            self.logger().info("Stop loss Created")
            self.stop_loss_order.order = self.get_order(event.order_id)
        elif self.time_limit_order.order_id == event.order_id:
            self.logger().info("Time Limit Created")
            self.time_limit_order.order = self.get_order(event.order_id)

    def process_order_canceled_event(self,
                                     event_tag: int,
                                     market: ConnectorBase,
                                     event: OrderCancelledEvent):
        if self.open_order.order_id == event.order_id:
            self.status = PositionExecutorStatus.CANCELED_BY_TIME_LIMIT
            self.close_timestamp = event.timestamp

    def process_order_filled_event(self,
                                   event_tag: int,
                                   market: ConnectorBase,
                                   event: OrderFilledEvent):
        if self.open_order.order_id == event.order_id:
            if self.status == PositionExecutorStatus.ACTIVE_POSITION:
                self.logger().info("Position incremented, updating take profit next tick.")
            else:
                self.status = PositionExecutorStatus.ACTIVE_POSITION

    def process_order_failed_event(self,
                                   event_tag: int,
                                   market: ConnectorBase,
                                   event: MarketOrderFailureEvent):
        if self.open_order.order_id == event.order_id:
            self.place_open_order()
            self.status = PositionExecutorStatus.NOT_STARTED
        elif self.stop_loss_order.order_id == event.order_id:
            self.place_stop_loss_order()
        elif self.time_limit_order.order_id == event.order_id:
            self.place_time_limit_order()
        elif self.take_profit_order.order_id == event.order_id:
            self.place_take_profit_order()

    def place_take_profit_order(self):
        order_id = self.place_order(
            connector_name=self._position_config.exchange,
            trading_pair=self._position_config.trading_pair,
            amount=self.open_order.executed_amount_base,
            price=self.take_profit_price,
            order_type=OrderType.LIMIT,
            position_action=PositionAction.CLOSE,
            position_side=PositionSide.LONG if self.side == PositionSide.SHORT else PositionSide.SHORT
        )
        self.take_profit_order.order_id = order_id
        self.logger().info("Placing take profit order")

    def place_stop_loss_order(self):
        current_price = self.connector.get_mid_price(self.trading_pair)
        order_id = self.place_order(
            connector_name=self.exchange,
            trading_pair=self.trading_pair,
            amount=self.open_order.executed_amount_base,
            price=current_price,
            order_type=OrderType.MARKET,
            position_action=PositionAction.CLOSE,
            position_side=PositionSide.LONG if self.side == PositionSide.SHORT else PositionSide.SHORT
        )
        self.stop_loss_order.order_id = order_id
        self.logger().info("Placing stop loss order")

    def place_time_limit_order(self):
        current_price = self.connector.get_mid_price(self.trading_pair)
        tp_partial_execution = self.take_profit_order.executed_amount_base if self.take_profit_order.executed_amount_base else Decimal("0")
        order_id = self.place_order(
            connector_name=self.exchange,
            trading_pair=self.trading_pair,
            amount=self.open_order.executed_amount_base - tp_partial_execution,
            price=current_price,
            order_type=OrderType.MARKET,
            position_action=PositionAction.CLOSE,
            position_side=PositionSide.LONG if self.side == PositionSide.SHORT else PositionSide.SHORT
        )
        self.time_limit_order.order_id = order_id
        self.logger().info("Placing time limit order")

    def place_open_order(self):
        order_id = self.place_order(
            connector_name=self.exchange,
            trading_pair=self.trading_pair,
            amount=self.amount,
            price=self.entry_price,
            order_type=self.open_order_type,
            position_action=PositionAction.OPEN,
            position_side=self.side
        )
        self._open_order.order_id = order_id
        self.logger().info("Placing open order")

    def remove_take_profit(self):
        self._strategy.cancel(
            connector_name=self.exchange,
            trading_pair=self.trading_pair,
            order_id=self._take_profit_order.order_id
        )
        self.logger().info("Removing take profit")

    def register_events(self):
        """Start listening to events from the given market."""
        for event_pair in self._event_pairs:
            self.connector.add_listener(event_pair[0], event_pair[1])

    def unregister_events(self):
        """Stop listening to events from the given market."""
        for event_pair in self._event_pairs:
            self.connector.remove_listener(event_pair[0], event_pair[1])

    def place_order(self,
                    connector_name: str,
                    trading_pair: str,
                    position_side: PositionSide,
                    amount: Decimal,
                    order_type: OrderType,
                    position_action: PositionAction,
                    price=Decimal("NaN"),
                    ):
        if position_side == PositionSide.LONG:
            return self._strategy.buy(connector_name, trading_pair, amount, order_type, price, position_action)
        else:
            return self._strategy.sell(connector_name, trading_pair, amount, order_type, price, position_action)

    def to_format_status(self):
        lines = []
        current_price = self.connector.get_mid_price(self.trading_pair)
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
        if self.status == PositionExecutorStatus.ACTIVE_POSITION:
            seconds_remaining = (self.end_time - self._strategy.current_timestamp)
            time_progress = (self.time_limit - seconds_remaining) / self.time_limit
            time_bar = "".join(['*' if i < time_scale * time_progress else '-' for i in range(time_scale)])
            lines.extend([f"Time limit: {time_bar}"])
            stop_loss_price = self.stop_loss_price
            take_profit_price = self.take_profit_price
            if self.side == PositionSide.LONG:
                price_range = take_profit_price - stop_loss_price
                progress = (current_price - stop_loss_price) / price_range
            elif self.side == PositionSide.SHORT:
                price_range = stop_loss_price - take_profit_price
                progress = (stop_loss_price - current_price) / price_range
            price_bar = [f'--{current_price:.4f}--' if i == int(price_scale * progress) else '-' for i in
                         range(price_scale)]
            price_bar.insert(0, f"SL:{stop_loss_price:.4f}")
            price_bar.append(f"TP:{take_profit_price:.4f}")
            lines.extend(["".join(price_bar), "\n"])
            lines.extend(["-----------------------------------------------------------------------------------------------------------"])
        return lines
