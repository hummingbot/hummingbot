import logging
import math
from decimal import Decimal
from typing import List, Optional, Union

from hummingbot.core.data_type.common import OrderType, PositionAction, PriceType, TradeType
from hummingbot.core.data_type.order_candidate import OrderCandidate, PerpetualOrderCandidate
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketOrderFailureEvent,
    OrderFilledEvent,
    SellOrderCompletedEvent,
    SellOrderCreatedEvent,
)
from hummingbot.logger import HummingbotLogger
from hummingbot.smart_components.executors.executor_base import ExecutorBase
from hummingbot.smart_components.executors.position_executor.data_types import PositionExecutorConfig
from hummingbot.smart_components.models.base import SmartComponentStatus
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
                 update_interval: float = 1.0, max_retries: int = 5):
        if config.triple_barrier_config.time_limit_order_type != OrderType.MARKET or \
                config.triple_barrier_config.stop_loss_order_type != OrderType.MARKET:
            error = "Only market orders are supported for time_limit and stop_loss"
            self.logger().error(error)
            raise ValueError(error)
        super().__init__(strategy=strategy, config=config, connectors=[config.exchange], update_interval=update_interval)
        self.config: PositionExecutorConfig = config

        # Order tracking
        self._open_order: Optional[TrackedOrder] = None
        self._close_order: Optional[TrackedOrder] = None
        self._take_profit_limit_order: Optional[TrackedOrder] = None
        self._failed_orders: List[TrackedOrder] = []
        self._trailing_stop_trigger_pct: Optional[Decimal] = None

        self._total_executed_amount_backup: Decimal = Decimal("0")
        self._current_retries = 0
        self._max_retries = max_retries

    @property
    def is_perpetual(self):
        return self.is_perpetual_connector(self.config.exchange)

    @property
    def open_filled_amount(self):
        return self._open_order.executed_amount_base if self._open_order else Decimal("0")

    @property
    def open_filled_amount_quote(self):
        return self.open_filled_amount * self.entry_price

    @property
    def close_filled_amount(self):
        return self._close_order.executed_amount_base if self._close_order else Decimal("0")

    @property
    def is_expired(self):
        return self.end_time and self.end_time <= self._strategy.current_timestamp

    @property
    def current_market_price(self):
        """
        This method is responsible for getting the current market price to be used as a reference for control barriers
        """
        price_type = PriceType.BestBid if self.config.side == TradeType.BUY else PriceType.BestAsk
        return self.get_price(self.config.exchange, self.config.trading_pair, price_type=price_type)

    @property
    def entry_price(self):
        if self._open_order and self._open_order.is_done:
            return self._open_order.average_executed_price
        elif self.config.entry_price:
            return self.config.entry_price
        else:
            price_type = PriceType.BestAsk if self.config.side == TradeType.BUY else PriceType.BestBid
            return self.get_price(self.config.exchange, self.config.trading_pair, price_type=price_type)

    @property
    def close_price(self):
        if self._close_order and self._close_order.is_done:
            return self._close_order.average_executed_price
        else:
            return self.current_market_price

    @property
    def trade_pnl_pct(self):
        """
        This method is responsible for calculating the trade pnl (Pure pnl without fees)
        """
        if self.open_filled_amount != Decimal("0"):
            if self.config.side == TradeType.BUY:
                return (self.close_price - self.entry_price) / self.entry_price
            else:
                return (self.entry_price - self.close_price) / self.entry_price
        else:
            return Decimal("0")

    @property
    def trade_pnl_quote(self):
        """
        This method is responsible for calculating the trade pnl in quote asset
        """
        return self.trade_pnl_pct * self.open_filled_amount * self.entry_price

    def get_net_pnl_quote(self):
        """
        This method is responsible for calculating the net pnl in quote asset
        """
        return self.trade_pnl_quote - self.cum_fees_quote

    def get_cum_fees_quote(self):
        """
        This method is responsible for calculating the cumulative fees in quote asset
        """
        orders = [self._open_order, self._close_order]
        return sum([order.cum_fees_quote for order in orders if order])

    def get_net_pnl_pct(self):
        """
        This method is responsible for calculating the net pnl percentage
        """
        return self.net_pnl_quote / self.open_filled_amount_quote if self.open_filled_amount_quote != Decimal("0") else Decimal("0")

    @property
    def end_time(self):
        """
        This method is responsible for calculating the end time of the position based on the time limit
        """
        if not self.config.triple_barrier_config.time_limit:
            return None
        return self.config.timestamp + self.config.triple_barrier_config.time_limit

    @property
    def take_profit_price(self):
        """
        This method is responsible for calculating the take profit price to place the take profit limit order
        """
        take_profit_price = self.entry_price * (1 + self.config.triple_barrier_config.take_profit) \
            if self.config.side == TradeType.BUY else self.entry_price * (1 - self.config.triple_barrier_config.take_profit)
        return take_profit_price

    async def control_task(self):
        if self.status == SmartComponentStatus.RUNNING:
            self.control_open_order()
            self.control_barriers()
        elif self.status == SmartComponentStatus.SHUTTING_DOWN:
            self.control_shutdown_process()
        self.evaluate_max_retries()

    def control_shutdown_process(self):
        if math.isclose(self.open_filled_amount, self.close_filled_amount):
            self.stop()
        else:
            self.logger().info(f"Open amount: {self.open_filled_amount}, Close amount: {self.close_filled_amount}")
            self.place_close_order_and_cancel_open_orders(close_type=self.close_type)
            self._current_retries += 1

    def evaluate_max_retries(self):
        """
        This method is responsible for evaluating the maximum number of retries to place an order and stop the executor
        if the maximum number of retries is reached.
        """
        if self._current_retries > self._max_retries:
            self.close_type = CloseType.FAILED
            self.stop()

    def on_start(self):
        """
        This method is responsible for starting the executor and validating if the position is expired. The base method
        validates if there is enough balance to place the open order.
        """
        super().on_start()
        if self.is_expired:
            self.close_type = CloseType.EXPIRED
            self.stop()

    def control_open_order(self):
        """
        This method is responsible for controlling the open order. It checks if the open order is not placed and if the
        close price is within the activation bounds to place the open order.
        """
        if not self._open_order and self._is_within_activation_bounds(self.close_price):
            self.place_open_order()

    def _is_within_activation_bounds(self, close_price: Decimal) -> bool:
        """
        This method is responsible for checking if the close price is within the activation bounds to place the open
        order. If the activation bounds are not set, it returns True. This makes the executor more capital efficient.
        """
        activation_bounds = self.config.activation_bounds
        order_price = self.config.entry_price
        if activation_bounds:
            if self.config.triple_barrier_config.open_order_type == OrderType.LIMIT:
                if self.config.side == TradeType.BUY:
                    return order_price > close_price * (1 - activation_bounds[0])
                else:
                    return order_price < close_price * (1 + activation_bounds[0])
            else:
                if self.config.side == TradeType.BUY:
                    return order_price < close_price * (1 - activation_bounds[1])
                else:
                    return order_price > close_price * (1 + activation_bounds[1])
        else:
            return True

    def place_open_order(self):
        """
        This method is responsible for placing the open order.
        """
        order_id = self.place_order(
            connector_name=self.config.exchange,
            trading_pair=self.config.trading_pair,
            order_type=self.config.triple_barrier_config.open_order_type,
            amount=self.config.amount,
            price=self.entry_price,
            side=self.config.side,
            position_action=PositionAction.OPEN,
        )
        self._open_order = TrackedOrder(order_id=order_id)
        self.logger().debug("Placing open order")

    def control_barriers(self):
        self.control_stop_loss()
        self.control_trailing_stop()
        self.control_take_profit()
        self.control_time_limit()

    def place_close_order_and_cancel_open_orders(self, close_type: CloseType, price: Decimal = Decimal("NaN")):
        delta_amount_to_close = abs(self.open_filled_amount - self.close_filled_amount)
        if delta_amount_to_close > self.connectors[self.config.exchange].trading_rules[self.config.trading_pair].min_order_size:
            order_id = self.place_order(
                connector_name=self.config.exchange,
                trading_pair=self.config.trading_pair,
                order_type=OrderType.MARKET,
                amount=self.open_filled_amount - self._take_profit_limit_order.executed_amount_base,
                price=price,
                side=TradeType.SELL if self.config.side == TradeType.BUY else TradeType.BUY,
                position_action=PositionAction.CLOSE,
            )
            self._close_order = TrackedOrder(order_id=order_id)
            self.logger().debug(f"Placing close order --> Filled amount: {self.open_filled_amount}")
        self.cancel_open_orders()
        self.close_type = close_type
        self.close_timestamp = self._strategy.current_timestamp
        self._status = SmartComponentStatus.SHUTTING_DOWN

    def cancel_open_orders(self):
        if self._open_order:
            self.cancel_open_order()
        if self._take_profit_limit_order:
            self.cancel_take_profit()

    def control_stop_loss(self):
        if self.config.triple_barrier_config.stop_loss:
            if self.net_pnl_pct <= -self.config.triple_barrier_config.stop_loss:
                self.place_close_order_and_cancel_open_orders(close_type=CloseType.STOP_LOSS)

    def control_take_profit(self):
        if self.open_filled_amount > Decimal("0") and self.config.triple_barrier_config.take_profit:
            if self.config.triple_barrier_config.take_profit_order_type.is_limit_type():
                if not self._take_profit_limit_order:
                    self.place_take_profit_limit_order()
                elif self._take_profit_limit_order.order and not math.isclose(self._take_profit_limit_order.order.amount,
                                                                              self._open_order.executed_amount_base):
                    self.renew_take_profit_order()
            elif self.net_pnl_pct >= self.config.triple_barrier_config.take_profit:
                self.place_close_order_and_cancel_open_orders(close_type=CloseType.TAKE_PROFIT)

    def control_time_limit(self):
        if self.is_expired:
            self.place_close_order_and_cancel_open_orders(close_type=CloseType.TIME_LIMIT)

    def place_take_profit_limit_order(self):
        order_id = self.place_order(
            connector_name=self.config.exchange,
            trading_pair=self.config.trading_pair,
            amount=self.open_filled_amount,
            price=self.take_profit_price,
            order_type=self.config.triple_barrier_config.take_profit_order_type,
            position_action=PositionAction.CLOSE,
            side=TradeType.BUY if self.config.side == TradeType.SELL else TradeType.SELL,
        )
        self._take_profit_limit_order = TrackedOrder(order_id=order_id)
        self.logger().debug("Placing take profit order")

    def renew_take_profit_order(self):
        self.cancel_take_profit()
        self.place_take_profit_limit_order()
        self.logger().debug("Renewing take profit order")

    def cancel_take_profit(self):
        self._strategy.cancel(
            connector_name=self.config.exchange,
            trading_pair=self.config.trading_pair,
            order_id=self._take_profit_limit_order.order_id
        )
        self.logger().debug("Removing take profit")

    def cancel_open_order(self):
        self._strategy.cancel(
            connector_name=self.config.exchange,
            trading_pair=self.config.trading_pair,
            order_id=self._open_order.order_id
        )
        self.logger().debug("Removing open order")

    def early_stop(self):
        """
        This method allows strategy to stop the executor early.
        """
        self.place_close_order_and_cancel_open_orders(close_type=CloseType.EARLY_STOP)

    def update_tracked_orders_with_order_id(self, order_id: str):
        if self._open_order and self._open_order.order_id == order_id:
            self._open_order.order = self.get_in_flight_order(self.config.exchange, order_id)
        elif self._close_order and self._close_order.order_id == order_id:
            self._close_order.order = self.get_in_flight_order(self.config.exchange, order_id)
        elif self._take_profit_limit_order and self._take_profit_limit_order.order_id == order_id:
            self._take_profit_limit_order.order = self.get_in_flight_order(self.config.exchange, order_id)

    def process_order_created_event(self, _, market, event: Union[BuyOrderCreatedEvent, SellOrderCreatedEvent]):
        self.update_tracked_orders_with_order_id(event.order_id)

    def process_order_completed_event(self, _, market, event: Union[BuyOrderCompletedEvent, SellOrderCompletedEvent]):
        if self._close_order and self._close_order.order_id == event.order_id:
            self.close_timestamp = event.timestamp
        elif self._take_profit_limit_order and self._take_profit_limit_order.order_id == event.order_id:
            self.close_type = CloseType.TAKE_PROFIT
            self.close_timestamp = event.timestamp
            self._close_order = self._take_profit_limit_order
            self.cancel_open_orders()
            self._status = SmartComponentStatus.SHUTTING_DOWN

    def process_order_filled_event(self, _, market, event: OrderFilledEvent):
        """
        This method is responsible for processing the order filled event. Here we will update the value of
        _total_executed_amount_backup, that can be used if the InFlightOrder
        is not available.
        """
        self._total_executed_amount_backup += event.amount
        self.update_tracked_orders_with_order_id(event.order_id)

    def process_order_failed_event(self, _, market, event: MarketOrderFailureEvent):
        """
        This method is responsible for processing the order failed event. Here we will add the InFlightOrder to the
        failed orders list.
        """
        self._current_retries += 1
        if self._open_order and event.order_id == self._open_order.order_id:
            self._failed_orders.append(self._open_order)
            self._open_order = None
            self.logger().error(f"Open order failed. Retrying {self._current_retries}/{self._max_retries}")
        elif self._close_order and event.order_id == self._close_order.order_id:
            self._failed_orders.append(self._close_order)
            self._close_order = None
            self.logger().error(f"Close order failed. Retrying {self._current_retries}/{self._max_retries}")
        elif self._take_profit_limit_order and event.order_id == self._take_profit_limit_order.order_id:
            self._failed_orders.append(self._take_profit_limit_order)
            self._take_profit_limit_order = None
            self.logger().error(f"Take profit order failed. Retrying {self._current_retries}/{self._max_retries}")

    def to_json(self):
        return {
            "timestamp": self.config.timestamp,
            "exchange": self.config.exchange,
            "trading_pair": self.config.trading_pair,
            "side": self.config.side.name,
            "amount": self.open_filled_amount,
            "trade_pnl": self.trade_pnl_pct,
            "trade_pnl_quote": self.trade_pnl_quote,
            "cum_fee_quote": self.cum_fees_quote,
            "net_pnl_quote": self.net_pnl_quote,
            "net_pnl_pct": self.net_pnl_pct,
            "close_timestamp": self.close_timestamp,
            "close_type": self.close_type.name if self.close_type else None,
            "entry_price": self.entry_price,
            "close_price": self.close_price,
            "sl": self.config.triple_barrier_config.stop_loss,
            "tp": self.config.triple_barrier_config.take_profit,
            "tl": self.config.triple_barrier_config.time_limit,
            "open_order_type": self.config.triple_barrier_config.open_order_type.name,
            "take_profit_order_type": self.config.triple_barrier_config.take_profit_order_type.name,
            "stop_loss_order_type": self.config.triple_barrier_config.stop_loss_order_type.name,
            "time_limit_order_type": self.config.triple_barrier_config.time_limit_order_type.name,
            "leverage": self.config.leverage,
        }

    def to_format_status(self, scale=1.0):
        lines = []
        current_price = self.get_price(self.config.exchange, self.config.trading_pair)
        amount_in_quote = self.entry_price * (self.open_filled_amount if self.open_filled_amount > Decimal("0") else self.config.amount)
        quote_asset = self.config.trading_pair.split("-")[1]
        if self.is_closed:
            lines.extend([f"""
| Trading Pair: {self.config.trading_pair} | Exchange: {self.config.exchange} | Side: {self.config.side}
| Entry price: {self.entry_price:.6f} | Close price: {self.close_price:.6f} | Amount: {amount_in_quote:.4f} {quote_asset}
| Realized PNL: {self.trade_pnl_quote:.6f} {quote_asset} | Total Fee: {self.cum_fees_quote:.6f} {quote_asset}
| PNL (%): {self.net_pnl_pct * 100:.2f}% | PNL (abs): {self.net_pnl_quote:.6f} {quote_asset} | Close Type: {self.close_type}
"""])
        else:
            lines.extend([f"""
| Trading Pair: {self.config.trading_pair} | Exchange: {self.config.exchange} | Side: {self.config.side} |
| Entry price: {self.entry_price:.6f} | Close price: {self.close_price:.6f} | Amount: {amount_in_quote:.4f} {quote_asset}
| Unrealized PNL: {self.trade_pnl_quote:.6f} {quote_asset} | Total Fee: {self.cum_fees_quote:.6f} {quote_asset}
| PNL (%): {self.net_pnl_pct * 100:.2f}% | PNL (abs): {self.net_pnl_quote:.6f} {quote_asset} | Close Type: {self.close_type}
        """])

        if self.is_trading:
            progress = 0
            if self.config.triple_barrier_config.time_limit:
                time_scale = int(scale * 60)
                seconds_remaining = (self.end_time - self._strategy.current_timestamp)
                time_progress = (self.config.triple_barrier_config.time_limit - seconds_remaining) / self.config.triple_barrier_config.time_limit
                time_bar = "".join(['*' if i < time_scale * time_progress else '-' for i in range(time_scale)])
                lines.extend([f"Time limit: {time_bar}"])

            if self.config.triple_barrier_config.take_profit and self.config.triple_barrier_config.stop_loss:
                price_scale = int(scale * 60)
                stop_loss_price = self.entry_price * (1 - self.config.triple_barrier_config.stop_loss) if self.config.side == TradeType.BUY \
                    else self.entry_price * (1 + self.config.triple_barrier_config.stop_loss)
                take_profit_price = self.entry_price * (1 + self.config.triple_barrier_config.take_profit) if self.config.side == TradeType.BUY \
                    else self.entry_price * (1 - self.config.triple_barrier_config.take_profit)
                if self.config.side == TradeType.BUY:
                    price_range = take_profit_price - stop_loss_price
                    progress = (current_price - stop_loss_price) / price_range
                elif self.config.side == TradeType.SELL:
                    price_range = stop_loss_price - take_profit_price
                    progress = (stop_loss_price - current_price) / price_range
                price_bar = [f'--{current_price:.5f}--' if i == int(price_scale * progress) else '-' for i in range(price_scale)]
                price_bar.insert(0, f"SL:{stop_loss_price:.5f}")
                price_bar.append(f"TP:{take_profit_price:.5f}")
                lines.extend(["".join(price_bar)])
            if self.config.triple_barrier_config.trailing_stop:
                lines.extend([f"Trailing stop pnl trigger: {self._trailing_stop_trigger_pct:.5f}"])
            lines.extend(["-----------------------------------------------------------------------------------------------------------"])
        return lines

    def control_trailing_stop(self):
        if self.config.triple_barrier_config.trailing_stop:
            net_pnl_pct = self.get_net_pnl_pct()
            if not self._trailing_stop_trigger_pct:
                if net_pnl_pct > self.config.triple_barrier_config.trailing_stop.activation_price:
                    self._trailing_stop_trigger_pct = net_pnl_pct - self.config.triple_barrier_config.trailing_stop.trailing_delta
            else:
                if net_pnl_pct < self._trailing_stop_trigger_pct:
                    self.place_close_order_and_cancel_open_orders(close_type=CloseType.TRAILING_STOP)
                if net_pnl_pct - self.config.triple_barrier_config.trailing_stop.trailing_delta > self._trailing_stop_trigger_pct:
                    self._trailing_stop_trigger_pct = net_pnl_pct - self.config.triple_barrier_config.trailing_stop.trailing_delta

    def validate_sufficient_balance(self):
        if self.is_perpetual:
            order_candidate = PerpetualOrderCandidate(
                trading_pair=self.config.trading_pair,
                is_maker=self.config.triple_barrier_config.open_order_type.is_limit_type(),
                order_type=self.config.triple_barrier_config.open_order_type,
                order_side=self.config.side,
                amount=self.config.amount,
                price=self.entry_price,
                leverage=Decimal(self.config.leverage),
            )
        else:
            order_candidate = OrderCandidate(
                trading_pair=self.config.trading_pair,
                is_maker=self.config.triple_barrier_config.open_order_type.is_limit_type(),
                order_type=self.config.triple_barrier_config.open_order_type,
                order_side=self.config.side,
                amount=self.config.amount,
                price=self.entry_price,
            )
        adjusted_order_candidates = self.adjust_order_candidates(self.config.exchange, [order_candidate])
        if adjusted_order_candidates[0].amount == Decimal("0"):
            self.close_type = CloseType.INSUFFICIENT_BALANCE
            self.logger().error("Not enough budget to open position.")
            self.stop()
