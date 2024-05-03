import asyncio
import logging
import math
from decimal import Decimal
from typing import Dict, List, Optional, Union

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import OrderType, PositionAction, PriceType, TradeType
from hummingbot.core.data_type.order_candidate import OrderCandidate, PerpetualOrderCandidate
from hummingbot.core.event.events import (
    BuyOrderCreatedEvent,
    MarketOrderFailureEvent,
    OrderFilledEvent,
    SellOrderCreatedEvent,
)
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.strategy_v2.executors.dca_executor.data_types import DCAExecutorConfig, DCAMode
from hummingbot.strategy_v2.executors.executor_base import ExecutorBase
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executors import CloseType, TrackedOrder


class DCAExecutor(ExecutorBase):
    _logger = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, strategy: ScriptStrategyBase, config: DCAExecutorConfig, update_interval: float = 1.0,
                 max_retries: int = 15):
        # validate amounts and prices
        if len(config.amounts_quote) != len(config.prices):
            raise ValueError("Amounts and prices lists must have the same length")

        # Initialize super class
        super().__init__(strategy=strategy, connectors=[config.connector_name], config=config, update_interval=update_interval)
        self.config: DCAExecutorConfig = config

        # validate amounts with exchange trading rules
        if self.is_any_amount_lower_than_min_order_size():
            self.close_execution_by(CloseType.FAILED)
            trading_rules = self.get_trading_rules(connector_name=config.connector_name, trading_pair=config.trading_pair)
            self.logger().error("Please increase the amount of the order:"
                                f"- Current amounts quote: {config.amounts_quote} | Min notional size: {trading_rules.min_notional_size}"
                                f"- Current amounts base: {[amount / price for amount, price in zip(config.amounts_quote, config.prices)]} | Min order size: {trading_rules.min_order_size}")
        # set default bounds
        self.n_levels = len(config.amounts_quote)
        if self.config.mode == DCAMode.TAKER and not self.config.activation_bounds:
            self.config.activation_bounds = [Decimal("0.0001"), Decimal("0.005")]  # 0.01% and 0.5%

        # executors tracking
        self._open_orders: List[TrackedOrder] = []
        self._close_orders: List[TrackedOrder] = []  # for now will be just one order but we can have multiple
        self._failed_orders: List[TrackedOrder] = []
        self._trailing_stop_trigger_pct: Optional[Decimal] = None

        # used to track the total amount filled that is updated by the event in case that the InFlightOrder is
        # not available
        self._total_executed_amount_backup: Decimal = Decimal("0")

        # add retries
        self._current_retries = 0
        self._max_retries = max_retries

    @property
    def active_open_orders(self) -> List[TrackedOrder]:
        return self._open_orders

    @property
    def active_close_orders(self) -> List[TrackedOrder]:
        return self._close_orders

    @property
    def open_order_type(self) -> OrderType:
        return OrderType.LIMIT if self.config.mode == DCAMode.MAKER else OrderType.MARKET

    @property
    def close_order_type(self) -> OrderType:
        return OrderType.MARKET

    @property
    def open_filled_amount(self) -> Decimal:
        return sum([order.executed_amount_base for order in self.active_open_orders])

    @property
    def open_filled_amount_quote(self) -> Decimal:
        return self.open_filled_amount * self.current_position_average_price

    @property
    def close_filled_amount(self) -> Decimal:
        return sum([order.executed_amount_base for order in self.active_close_orders])

    @property
    def close_filled_amount_quote(self) -> Decimal:
        return self.close_filled_amount * self.close_price

    @property
    def filled_amount(self) -> Decimal:
        return self.open_filled_amount + self.close_filled_amount

    @property
    def filled_amount_quote(self) -> Decimal:
        return self.open_filled_amount_quote + self.close_filled_amount_quote

    @property
    def max_amount_quote(self) -> Decimal:
        return sum(self.config.amounts_quote)

    @property
    def unrealized_pnl_when_last_order_filled(self) -> Decimal:
        last_order_price = self.max_price if self.config.side == TradeType.SELL else self.min_price
        distance_from_last_order_to_break_even = abs(last_order_price - self.target_position_average_price) / \
            self.target_position_average_price
        return self.max_amount_quote * distance_from_last_order_to_break_even

    @property
    def end_time(self):
        if not self.config.time_limit:
            return None
        return self.config.timestamp + self.config.time_limit

    @property
    def is_expired(self):
        return self.end_time and self.end_time <= self._strategy.current_timestamp

    @property
    def min_price(self) -> Decimal:
        return min(self.config.prices)

    @property
    def max_price(self) -> Decimal:
        return max(self.config.prices)

    @property
    def max_loss_quote(self) -> Decimal:
        # TODO: refactor the ExecutorBase class to handle max loss in pct and quote asset since some strategies like
        #  arbitrage and XEMM will need a more complex calculation
        sl = self.config.stop_loss if self.config.stop_loss else Decimal("0")
        return self.max_amount_quote * sl

    @property
    def current_market_price(self):
        """
        This method is responsible for getting the current market price to be used as a reference for control barriers
        """
        price_type = PriceType.BestBid if self.config.side == TradeType.BUY else PriceType.BestAsk
        return self.get_price(self.config.connector_name, self.config.trading_pair, price_type=price_type)

    @property
    def close_price(self):
        """
        This method is responsible for getting the close price, if the executor is active, it will return the current
        market price, otherwise it will return the average price of the closed orders
        """
        if self.status == RunnableStatus.TERMINATED and len(self._close_orders) > 0:
            # for now we will consider just one close order, in the future we can have multiple close orders
            return self._close_orders[0].average_executed_price
        else:
            return self.current_market_price

    @property
    def current_position_average_price(self) -> Decimal:
        return sum([order.average_executed_price * order.executed_amount_base for order in self._open_orders]) / \
            self.open_filled_amount if self._open_orders and self.open_filled_amount > Decimal("0") else Decimal("0")

    @property
    def target_position_average_price(self) -> Decimal:
        return sum([price * amount for price, amount in
                    zip(self.config.prices, self.config.amounts_quote)]) / self.max_amount_quote

    @property
    def trade_pnl_pct(self):
        """
        This method is responsible for calculating the trade pnl (Pure pnl without fees)
        """
        if self.current_position_average_price != Decimal("0"):
            if self.config.side == TradeType.BUY:
                return (self.close_price - self.current_position_average_price) / self.current_position_average_price
            else:
                return (self.current_position_average_price - self.close_price) / self.current_position_average_price
        else:
            return Decimal("0")

    @property
    def trade_pnl_quote(self) -> Decimal:
        """
        This method is responsible for calculating the trade pnl in quote asset
        """
        return self.trade_pnl_pct * self.open_filled_amount_quote

    def is_any_amount_lower_than_min_order_size(self):
        """
        This method is responsible for checking if any amount is lower than the minimum order size
        """
        notional_size_check = any([amount < self.connectors[self.config.connector_name].trading_rules[self.config.trading_pair].min_notional_size for amount in self.config.amounts_quote])
        base_amount_size_check = any([amount / price < self.connectors[self.config.connector_name].trading_rules[self.config.trading_pair].min_order_size for amount, price in zip(self.config.amounts_quote, self.config.prices)])
        return notional_size_check or base_amount_size_check

    def get_net_pnl_quote(self) -> Decimal:
        """
        This method is responsible for calculating the net pnl in quote asset
        """
        return self.trade_pnl_quote - self.cum_fees_quote

    def get_net_pnl_pct(self) -> Decimal:
        """
        This method is responsible for calculating the net pnl percentage
        """
        return self.net_pnl_quote / self.open_filled_amount_quote if self.open_filled_amount_quote > Decimal("0") else Decimal("0")

    def get_cum_fees_quote(self) -> Decimal:
        """
        This method is responsible for calculating the cumulative fees in quote asset
        """
        all_orders = self._open_orders + self._close_orders
        return sum([order.cum_fees_quote for order in all_orders])

    def on_start(self):
        super().on_start()
        if self.is_expired:
            self.close_execution_by(CloseType.EXPIRED)

    @property
    def all_open_orders_executed(self) -> bool:
        """
        This method is responsible for checking if all orders are completed
        """
        return all([order.is_done for order in self._open_orders]) and len(self._open_orders) == self.n_levels

    def validate_sufficient_balance(self):
        """
        This method is responsible for checking the budget
        """
        order_candidates = []
        for amount_quote, price in zip(self.config.amounts_quote, self.config.prices):
            amount_base = amount_quote / price
            is_maker = self.config.mode == DCAMode.MAKER
            if self.is_perpetual_connector(self.config.connector_name):
                order_candidate = PerpetualOrderCandidate(
                    trading_pair=self.config.trading_pair,
                    is_maker=is_maker,
                    order_type=self.open_order_type,
                    order_side=self.config.side,
                    amount=amount_base,
                    price=price,
                    leverage=Decimal(self.config.leverage),
                )
            else:
                order_candidate = OrderCandidate(
                    trading_pair=self.config.trading_pair,
                    is_maker=is_maker,
                    order_type=self.open_order_type,
                    order_side=self.config.side,
                    amount=amount_base,
                    price=price,
                )
            order_candidates.append(order_candidate)
        adjusted_order_candidates = self.adjust_order_candidates(self.config.connector_name, order_candidates)
        if any([order_candidate.amount == Decimal("0") for order_candidate in adjusted_order_candidates]):
            self.close_execution_by(CloseType.INSUFFICIENT_BALANCE)
            self.logger().error("Not enough budget to create DCA.")

    async def control_task(self):
        """
        This task is responsible for creating and closing position executors
        """
        if self.status == RunnableStatus.RUNNING:
            self.control_open_order_process()
            self.control_barriers()
        elif self.status == RunnableStatus.SHUTTING_DOWN:
            await self.control_shutdown_process()
        self.evaluate_max_retries()

    def control_open_order_process(self):
        """
        This method is responsible for controlling the opening process
        """
        next_level = len(self._open_orders)
        if next_level < self.n_levels:
            close_price = self.get_price(connector_name=self.config.connector_name,
                                         trading_pair=self.config.trading_pair)
            order_price = self.config.prices[next_level]
            if self._is_within_activation_bounds(order_price, close_price) and not self.is_expired:
                self.create_dca_order(level=next_level)

    def create_dca_order(self, level: int):
        """
        This method is responsible for creating a new DCA order
        """
        price = self.config.prices[level]
        amount = self.config.amounts_quote[level] / price
        order_id = self.place_order(connector_name=self.config.connector_name,
                                    trading_pair=self.config.trading_pair, order_type=self.open_order_type,
                                    side=self.config.side, amount=amount, price=price,
                                    position_action=PositionAction.OPEN)
        if order_id:
            self._open_orders.append(TrackedOrder(order_id=order_id))

    def control_barriers(self):
        """
        This method is responsible for controlling the active executors
        """
        self.control_stop_loss()
        self.control_trailing_stop()
        self.control_take_profit()
        self.control_time_limit()

    def control_time_limit(self):
        if self.is_expired:
            self.close_type = CloseType.TIME_LIMIT
            self.place_close_order_and_cancel_open_orders()

    def control_stop_loss(self):
        """
        This method is responsible for controlling the stop loss. In order to trigger the stop loss all the orders must
        be completed and the net pnl must be lower than the stop loss. If it's maker mode, the stop loss will be
        triggered if the net pnl is lower than the stop loss and all the orders were executed, otherwise the stop loss
        will be triggered if the net pnl is lower than the stop loss.
        """
        if self.config.stop_loss:
            if self.config.mode == DCAMode.MAKER:
                if self.all_open_orders_executed and self.net_pnl_pct <= -self.config.stop_loss:
                    self.close_type = CloseType.STOP_LOSS
                    self.place_close_order_and_cancel_open_orders()
            else:
                if self.net_pnl_quote <= -self.max_loss_quote:
                    self.close_type = CloseType.STOP_LOSS
                    self.place_close_order_and_cancel_open_orders()

    def control_trailing_stop(self):
        """
        This method is responsible for controlling the trailing stop. In order to activated the trailing stop the net
        pnl must be higher than the activation price delta. Once the trailing stop is activated, the trailing stop trigger
        will be the activation price delta minus the trailing delta and the stop loss will be triggered if the net pnl
        is lower than the trailing stop trigger. the value of hte trailing stop trigger will be updated if the net pnl
        minus the trailing delta is higher than the current value of the trailing stop trigger.
        """
        if self.config.trailing_stop:
            net_pnl_pct = self.get_net_pnl_pct()
            if not self._trailing_stop_trigger_pct:
                if net_pnl_pct > self.config.trailing_stop.activation_price:
                    self._trailing_stop_trigger_pct = net_pnl_pct - self.config.trailing_stop.trailing_delta
            else:
                if net_pnl_pct < self._trailing_stop_trigger_pct:
                    self.close_type = CloseType.TRAILING_STOP
                    self.place_close_order_and_cancel_open_orders()
                if net_pnl_pct - self.config.trailing_stop.trailing_delta > self._trailing_stop_trigger_pct:
                    self._trailing_stop_trigger_pct = net_pnl_pct - self.config.trailing_stop.trailing_delta

    def control_take_profit(self):
        """
        This method is responsible for controlling the take profit. In order to trigger the take profit all the orders must
        be completed and the net pnl must be higher than the take profit. Take profit order is limit type only, if you
        want to use market order, you can use trailing stop instead.
        """
        if self.config.take_profit:
            if self.net_pnl_pct > self.config.take_profit:
                self.close_type = CloseType.TAKE_PROFIT
                self.place_close_order_and_cancel_open_orders()

    def early_stop(self):
        """
        This method allows strategy to stop the executor early.
        """
        self.close_type = CloseType.EARLY_STOP
        self.place_close_order_and_cancel_open_orders()

    def place_close_order_and_cancel_open_orders(self, price: Decimal = Decimal("NaN")):
        """
        This method is responsible for placing the close order
        """
        self.cancel_open_orders()
        self.place_close_order(price)
        self._status = RunnableStatus.SHUTTING_DOWN
        self.close_timestamp = self._strategy.current_timestamp

    def close_execution_by(self, close_type):
        self.close_type = close_type
        self.close_timestamp = self._strategy.current_timestamp
        self.stop()

    def place_close_order(self, price):
        delta_amount_to_close = self.open_filled_amount - self.close_filled_amount
        min_order_size = self.connectors[self.config.connector_name].trading_rules[self.config.trading_pair].min_order_size
        if delta_amount_to_close >= min_order_size:
            order_id = self.place_order(
                connector_name=self.config.connector_name,
                trading_pair=self.config.trading_pair,
                order_type=OrderType.MARKET,
                amount=delta_amount_to_close,
                price=price,
                side=TradeType.SELL if self.config.side == TradeType.BUY else TradeType.BUY,
                position_action=PositionAction.CLOSE,
            )
            self._close_orders.append(TrackedOrder(order_id=order_id))

    def cancel_open_orders(self):
        for tracked_order in self._open_orders:
            if tracked_order.order and tracked_order.order.is_open:
                self._strategy.cancel(connector_name=self.config.connector_name, trading_pair=self.config.trading_pair,
                                      order_id=tracked_order.order_id)

    def _is_within_activation_bounds(self, order_price: Decimal, close_price: Decimal) -> bool:
        """
        This method is responsible for checking if the order is within the activation bounds
        """
        activation_bounds = self.config.activation_bounds
        if self.config.mode == DCAMode.MAKER:
            if activation_bounds:
                if self.config.side == TradeType.BUY:
                    return order_price > close_price * (1 - activation_bounds[0])
                else:
                    return order_price < close_price * (1 + activation_bounds[0])
            else:
                return True
        elif self.config.mode == DCAMode.TAKER:
            # Taker mode requires activation bounds for safety. Default to 0.01% and 0.5% if not provided.
            if self.config.side == TradeType.BUY:
                min_price_to_buy = order_price * (1 - activation_bounds[0])
                max_price_to_buy = order_price * (1 + activation_bounds[1])
                return min_price_to_buy < close_price < max_price_to_buy
            else:
                min_price_to_sell = order_price * (1 - activation_bounds[1])
                max_price_to_sell = order_price * (1 + activation_bounds[0])
                return min_price_to_sell < close_price < max_price_to_sell

    async def control_shutdown_process(self):
        """
        This method is responsible for shutting down the process, ensuring that all orders are completed.
        """
        if math.isclose(self.open_filled_amount, self.close_filled_amount):
            self.close_execution_by(self.close_type)
        elif len(self.active_close_orders) > 0:
            connector = self.connectors[self.config.connector_name]
            await connector._update_orders_with_error_handler(
                orders=[order.order for order in self.active_close_orders if order.order],
                error_handler=connector._handle_update_error_for_active_order
            )
            for order in self.active_close_orders:
                self.update_tracked_orders_with_order_id(order.order_id)
                if order.order and order.order.is_done and order.executed_amount_base == Decimal("0"):
                    self.logger().error(
                        f"Close order {order.order_id} is done, might be an error with this update. Cancelling the order and placing it again.")
                    self._strategy.cancel(connector_name=self.config.connector_name, trading_pair=self.config.trading_pair,
                                          order_id=order.order_id)
                    self._close_orders.remove(order)
                    self._failed_orders.append(order)
        else:
            self.logger().info(
                f"Open amount: {self.open_filled_amount}, Close amount: {self.close_filled_amount}, Back up filled amount {self._total_executed_amount_backup}")
            self.place_close_order_and_cancel_open_orders()
            self._current_retries += 1
        await asyncio.sleep(5.0)

    def update_tracked_orders_with_order_id(self, order_id: str):
        all_orders = self._open_orders + self._close_orders
        active_order = next((order for order in all_orders if order.order_id == order_id), None)
        if active_order:
            in_flight_order = self.get_in_flight_order(self.config.connector_name, order_id)
            if in_flight_order:
                active_order.order = in_flight_order

    def process_order_created_event(self,
                                    event_tag: int,
                                    market: ConnectorBase,
                                    event: Union[BuyOrderCreatedEvent, SellOrderCreatedEvent]):
        """
        This method is responsible for processing the order created event. Here we will add the InFlightOrder to the
        active orders list.
        """
        self.update_tracked_orders_with_order_id(event.order_id)

    def process_order_failed_event(self,
                                   event_tag: int,
                                   market: ConnectorBase,
                                   event: MarketOrderFailureEvent):
        """
        This method is responsible for processing the order failed event. Here we will add the InFlightOrder to the
        failed orders list.
        """
        open_order = next((order for order in self._open_orders if order.order_id == event.order_id), None)
        if open_order:
            self._failed_orders.append(open_order)
            self._open_orders.remove(open_order)
            self.logger().error(f"Order {event.order_id} failed.")
        close_order = next((order for order in self._close_orders if order.order_id == event.order_id), None)
        if close_order:
            self._failed_orders.append(close_order)
            self._close_orders.remove(close_order)
            self.logger().error(f"Order {event.order_id} failed.")
            self._current_retries += 1

    def evaluate_max_retries(self):
        """
        This method is responsible for evaluating the max retries. If the max retries is reached, the executor will be
        stopped.
        """
        if self._current_retries >= self._max_retries:
            self.close_execution_by(CloseType.FAILED)
            self.logger().error("Max retries reached. Stopping DCA executor.")

    def process_order_filled_event(self, event_tag: int, market: ConnectorBase, event: OrderFilledEvent):
        """
        This method is responsible for processing the order filled event. Here we will update the value of
        _total_executed_amount_backup, that can be used if the InFlightOrder
        is not available.
        """
        if event.order_id in [order.order_id for order in self._open_orders]:
            self._total_executed_amount_backup += event.amount
        self.update_tracked_orders_with_order_id(event.order_id)

    def get_custom_info(self) -> Dict:
        return {
            "side": self.config.side,
            "current_position_average_price": self.current_position_average_price,
            "target_position_average_price": self.target_position_average_price,
            "filled_amount": self.filled_amount,
            "filled_amount_quote": self.filled_amount_quote,
            "max_amount_quote": self.max_amount_quote,
            "min_price": self.min_price,
            "max_price": self.max_price,
            "max_loss_quote": self.max_loss_quote,
            "current_market_price": self.current_market_price,
            "close_price": self.close_price,
            "close_type": self.close_type,
            "close_timestamp": self.close_timestamp,
            "n_levels": self.n_levels,
            "trailing_stop_trigger_pct": self._trailing_stop_trigger_pct,
            "total_executed_amount_backup": self._total_executed_amount_backup,
            "current_retries": self._current_retries,
            "max_retries": self._max_retries,
            "level_id": self.config.level_id,
            "order_ids": [order.order_id for order in self._open_orders + self._close_orders],
        }
