import asyncio
import logging
from decimal import Decimal
from typing import Dict, List, Optional, Union

from hummingbot.connector.connector_base import ConnectorBase
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
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.strategy_v2.executors.executor_base import ExecutorBase
from hummingbot.strategy_v2.executors.position_executor.data_types import PositionExecutorConfig
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executors import CloseType, TrackedOrder


class PositionExecutor(ExecutorBase):
    _logger = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, strategy: ScriptStrategyBase, config: PositionExecutorConfig,
                 update_interval: float = 1.0, max_retries: int = 10):
        """
        Initialize the PositionExecutor instance.

        :param strategy: The strategy to be used by the PositionExecutor.
        :param config: The configuration for the PositionExecutor, subclass of PositionExecutoConfig.
        :param update_interval: The interval at which the PositionExecutor should be updated, defaults to 1.0.
        :param max_retries: The maximum number of retries for the PositionExecutor, defaults to 5.
        """
        if config.triple_barrier_config.time_limit_order_type != OrderType.MARKET or \
                config.triple_barrier_config.stop_loss_order_type != OrderType.MARKET:
            error = "Only market orders are supported for time_limit and stop_loss"
            self.logger().error(error)
            raise ValueError(error)
        super().__init__(strategy=strategy, config=config, connectors=[config.connector_name],
                         update_interval=update_interval)
        if not config.entry_price:
            open_order_price_type = PriceType.BestBid if config.side == TradeType.BUY else PriceType.BestAsk
            config.entry_price = self.get_price(config.connector_name, config.trading_pair,
                                                price_type=open_order_price_type)
        self.config: PositionExecutorConfig = config
        self.trading_rules = self.get_trading_rules(self.config.connector_name, self.config.trading_pair)

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
    def is_perpetual(self) -> bool:
        """
        Check if the exchange connector is perpetual.

        :return: True if the exchange connector is perpetual, False otherwise.
        """
        return self.is_perpetual_connector(self.config.connector_name)

    @property
    def is_trading(self):
        """
        Check if the position is trading.

        :return: True if the position is trading, False otherwise.
        """
        return self.status == RunnableStatus.RUNNING and self.open_filled_amount > Decimal("0")

    @property
    def open_filled_amount(self) -> Decimal:
        """
        Get the filled amount of the open order.

        :return: The filled amount of the open order if it exists, otherwise 0.
        """
        if self._open_order:
            if self._open_order.fee_asset == self.config.trading_pair.split("-")[0]:
                open_filled_amount = self._open_order.executed_amount_base - self._open_order.cum_fees_base
            else:
                open_filled_amount = self._open_order.executed_amount_base
            return self.connectors[self.config.connector_name].quantize_order_amount(
                trading_pair=self.config.trading_pair,
                amount=open_filled_amount)
        else:
            return Decimal("0")

    @property
    def amount_to_close(self) -> Decimal:
        """
        Get the amount to close the position.

        :return: The amount to close the position.
        """
        return self.open_filled_amount - self.close_filled_amount

    @property
    def open_filled_amount_quote(self) -> Decimal:
        """
        Get the filled amount of the open order in quote currency.

        :return: The filled amount of the open order in quote currency.
        """
        return self.open_filled_amount * self.entry_price

    @property
    def close_filled_amount(self) -> Decimal:
        """
        Get the filled amount of the close order.

        :return: The filled amount of the close order if it exists, otherwise 0.
        """
        return self._close_order.executed_amount_base if self._close_order else Decimal("0")

    @property
    def close_filled_amount_quote(self) -> Decimal:
        """
        Get the filled amount of the close order in quote currency.

        :return: The filled amount of the close order in quote currency.
        """
        return self.close_filled_amount * self.close_price

    @property
    def filled_amount(self) -> Decimal:
        """
        Get the filled amount of the position.
        """
        return self.open_filled_amount + self.close_filled_amount

    @property
    def filled_amount_quote(self) -> Decimal:
        """
        Get the filled amount of the position in quote currency.
        """
        return self.open_filled_amount_quote + self.close_filled_amount_quote if self.close_type != CloseType.POSITION_HOLD else Decimal("0")

    @property
    def is_expired(self) -> bool:
        """
        Check if the position is expired.

        :return: True if the position is expired, False otherwise.
        """
        return self.end_time and self.end_time <= self._strategy.current_timestamp

    @property
    def current_market_price(self) -> Decimal:
        """
        This method is responsible for getting the current market price to be used as a reference for control barriers.

        :return: The current market price.
        """
        price_type = PriceType.BestBid if self.config.side == TradeType.BUY else PriceType.BestAsk
        return self.get_price(self.config.connector_name, self.config.trading_pair, price_type=price_type)

    @property
    def entry_price(self) -> Decimal:
        """
        This method is responsible for getting the entry price. If the open order is done, it returns the average executed price.
        If the entry price is set in the configuration, it returns the entry price from the configuration.
        Otherwise, it returns the best ask price for buy orders and the best bid price for sell orders.

        :return: The entry price.
        """
        if self._open_order and self._open_order.is_done:
            return self._open_order.average_executed_price
        elif self.config.triple_barrier_config.open_order_type == OrderType.LIMIT_MAKER:
            if self.config.side == TradeType.BUY:
                best_bid = self.get_price(self.config.connector_name, self.config.trading_pair, PriceType.BestBid)
                return min(self.config.entry_price, best_bid)
            else:
                best_ask = self.get_price(self.config.connector_name, self.config.trading_pair, PriceType.BestAsk)
                return max(self.config.entry_price, best_ask)
        else:
            return self.config.entry_price

    @property
    def close_price(self) -> Decimal:
        """
        This method is responsible for getting the close price. If the close order is done, it returns the average executed price.
        Otherwise, it returns the current market price.

        :return: The close price.
        """
        if self._close_order and self._close_order.is_done:
            return self._close_order.average_executed_price
        else:
            return self.current_market_price

    @property
    def close_order_side(self):
        return TradeType.BUY if self.config.side == TradeType.SELL else TradeType.SELL

    @property
    def trade_pnl_pct(self) -> Decimal:
        """
        Calculate the trade pnl (Pure pnl without fees)

        :return: The trade pnl percentage.
        """
        if self.open_filled_amount != Decimal("0") and self.close_type not in [CloseType.FAILED, CloseType.POSITION_HOLD]:
            if self.config.side == TradeType.BUY:
                return (self.close_price - self.entry_price) / self.entry_price
            else:
                return (self.entry_price - self.close_price) / self.entry_price
        else:
            return Decimal("0")

    @property
    def trade_pnl_quote(self) -> Decimal:
        """
        Calculate the trade pnl in quote asset

        :return: The trade pnl in quote asset.
        """
        return self.trade_pnl_pct * self.open_filled_amount * self.entry_price

    def get_net_pnl_quote(self) -> Decimal:
        """
        Calculate the net pnl in quote asset

        :return: The net pnl in quote asset.
        """
        return self.trade_pnl_quote - self.cum_fees_quote

    def get_cum_fees_quote(self) -> Decimal:
        """
        Calculate the cumulative fees in quote asset

        :return: The cumulative fees in quote asset.
        """
        orders = [self._open_order, self._close_order]
        return sum([order.cum_fees_quote for order in orders if order])

    def get_net_pnl_pct(self) -> Decimal:
        """
        Calculate the net pnl percentage

        :return: The net pnl percentage.
        """
        return self.net_pnl_quote / self.open_filled_amount_quote if self.open_filled_amount_quote != Decimal("0") else Decimal("0")

    @property
    def end_time(self) -> Optional[float]:
        """
        Calculate the end time of the position based on the time limit

        :return: The end time of the position.
        """
        if not self.config.triple_barrier_config.time_limit:
            return None
        return self.config.timestamp + self.config.triple_barrier_config.time_limit

    @property
    def take_profit_price(self):
        """
        This method is responsible for calculating the take profit price to place the take profit limit order.

        :return: The take profit price.
        """
        if self.config.side == TradeType.BUY:
            take_profit_price = self.entry_price * (1 + self.config.triple_barrier_config.take_profit)
            if self.config.triple_barrier_config.take_profit_order_type == OrderType.LIMIT_MAKER:
                take_profit_price = max(take_profit_price,
                                        self.get_price(self.config.connector_name, self.config.trading_pair,
                                                       PriceType.BestAsk))
        else:
            take_profit_price = self.entry_price * (1 - self.config.triple_barrier_config.take_profit)
            if self.config.triple_barrier_config.take_profit_order_type == OrderType.LIMIT_MAKER:
                take_profit_price = min(take_profit_price,
                                        self.get_price(self.config.connector_name, self.config.trading_pair,
                                                       PriceType.BestBid))
        return take_profit_price

    async def control_task(self):
        """
        This method is responsible for controlling the task based on the status of the executor.

        :return: None
        """
        if self.status == RunnableStatus.RUNNING:
            self.control_open_order()
            self.control_barriers()
        elif self.status == RunnableStatus.SHUTTING_DOWN:
            await self.control_shutdown_process()
        self.evaluate_max_retries()

    def all_orders_completed(self):
        """
        This method is responsible for checking if the open orders are completed.

        :return: True if the open orders are completed, False otherwise.
        """
        open_order_condition = not self._open_order or self._open_order.is_done
        take_profit_condition = not self._take_profit_limit_order or self._take_profit_limit_order.is_done
        close_order_condition = not self._close_order or self._close_order.is_done
        return open_order_condition and take_profit_condition and close_order_condition

    async def control_shutdown_process(self):
        """
        This method is responsible for controlling the shutdown process of the executor.

        :return: None
        """
        self.close_timestamp = self._strategy.current_timestamp
        if self.all_orders_completed():
            if self.close_type == CloseType.POSITION_HOLD:
                if self._open_order and self._open_order.is_filled:
                    self._held_position_orders.append(self._open_order.order.to_json())
                if self._close_order and self._close_order.is_filled:
                    self._held_position_orders.append(self._close_order.order.to_json())
                if len(self._held_position_orders) == 0:
                    self.close_type = CloseType.EARLY_STOP
                self.stop()
            elif self.open_and_close_volume_match():
                self.stop()
            else:
                await self.control_close_order()
                self._current_retries += 1
        else:
            self.cancel_open_orders()
        await self._sleep(5.0)

    def open_and_close_volume_match(self):
        if self.open_filled_amount == Decimal("0"):
            return True
        else:
            return self._close_order and self._close_order.is_filled

    async def control_close_order(self):
        """
        This method is responsible for controlling the close order. If the close order is filled and the open orders are
        completed, it stops the executor. If the close order is not placed, it places the close order. If the close order
        is not filled, it waits for the close order to be filled and requests the order information to the connector.
        """
        if self._close_order:
            in_flight_order = self.get_in_flight_order(self.config.connector_name,
                                                       self._close_order.order_id) if not self._close_order.order else self._close_order.order
            if in_flight_order:
                self._close_order.order = in_flight_order
                connector = self.connectors[self.config.connector_name]
                await connector._update_orders_with_error_handler(
                    orders=[in_flight_order],
                    error_handler=connector._handle_update_error_for_lost_order)
                self.logger().info("Waiting for close order to be filled")
            else:
                self._failed_orders.append(self._close_order)
                self._close_order = None
        else:
            self.place_close_order_and_cancel_open_orders(close_type=self.close_type)

    def evaluate_max_retries(self):
        """
        This method is responsible for evaluating the maximum number of retries to place an order and stop the executor
        if the maximum number of retries is reached.

        :return: None
        """
        if self._current_retries > self._max_retries:
            self.close_type = CloseType.FAILED
            self.stop()

    async def on_start(self):
        """
        This method is responsible for starting the executor and validating if the position is expired. The base method
        validates if there is enough balance to place the open order.

        :return: None
        """
        await super().on_start()
        if self.is_expired:
            self.close_type = CloseType.EXPIRED
            self.stop()

    def control_open_order(self):
        """
        This method is responsible for controlling the open order. It checks if the open order is not placed and if the
        close price is within the activation bounds to place the open order.

        :return: None
        """
        if not self._open_order:
            if self._is_within_activation_bounds(self.config.entry_price, self.config.side,
                                                 self.config.triple_barrier_config.open_order_type):
                self.place_open_order()
        else:
            if self._open_order.order and not self._open_order.is_filled and \
                    not self._is_within_activation_bounds(self.config.entry_price, self.config.side,
                                                          self.config.triple_barrier_config.open_order_type):
                self.cancel_open_order()

    def _is_within_activation_bounds(self, order_price: Decimal, side: TradeType, order_type: OrderType) -> bool:
        """
        This method is responsible for checking if the close price is within the activation bounds to place the open
        order. If the activation bounds are not set, it returns True. This makes the executor more capital efficient.

        :param close_price: The close price to be checked.
        :return: True if the close price is within the activation bounds, False otherwise.
        """
        activation_bounds = self.config.activation_bounds
        mid_price = self.get_price(self.config.connector_name, self.config.trading_pair, PriceType.MidPrice)
        if activation_bounds:
            if order_type.is_limit_type():
                if side == TradeType.BUY:
                    return order_price >= mid_price * (1 - activation_bounds[0])
                else:
                    return order_price <= mid_price * (1 + activation_bounds[0])
            else:
                if side == TradeType.BUY:
                    min_price_to_buy = order_price * (1 - activation_bounds[0])
                    max_price_to_buy = order_price * (1 + activation_bounds[1])
                    return min_price_to_buy <= mid_price <= max_price_to_buy
                else:
                    min_price_to_sell = order_price * (1 - activation_bounds[1])
                    max_price_to_sell = order_price * (1 + activation_bounds[0])
                    return min_price_to_sell <= mid_price <= max_price_to_sell
        else:
            return True

    def place_open_order(self):
        """
        This method is responsible for placing the open order.

        :return: None
        """
        order_id = self.place_order(
            connector_name=self.config.connector_name,
            trading_pair=self.config.trading_pair,
            order_type=self.config.triple_barrier_config.open_order_type,
            amount=self.config.amount,
            price=self.entry_price,
            side=self.config.side,
            position_action=PositionAction.OPEN,
        )
        self._open_order = TrackedOrder(order_id=order_id)
        self.logger().debug(f"Executor ID: {self.config.id} - Placing open order {order_id}")

    def control_barriers(self):
        """
        This method is responsible for controlling the barriers. It controls the stop loss, take profit, time limit and
        trailing stop.

        :return: None
        """
        if self._open_order and self._open_order.is_filled and self.open_filled_amount >= self.trading_rules.min_order_size \
                and self.open_filled_amount_quote >= self.trading_rules.min_notional_size:
            self.control_stop_loss()
            self.control_trailing_stop()
            self.control_take_profit()
        self.control_time_limit()

    def place_close_order_and_cancel_open_orders(self, close_type: CloseType, price: Decimal = Decimal("NaN")):
        """
        This method is responsible for placing the close order and canceling the open orders. If the difference between
        the open filled amount and the close filled amount is greater than the minimum order size, it places the close
        order. It also cancels the open orders.

        :param close_type: The type of the close order.
        :param price: The price to be used in the close order.
        :return: None
        """
        self.cancel_open_orders()
        if self.amount_to_close >= self.trading_rules.min_order_size and close_type != CloseType.POSITION_HOLD:
            order_id = self.place_order(
                connector_name=self.config.connector_name,
                trading_pair=self.config.trading_pair,
                order_type=OrderType.MARKET,
                amount=self.amount_to_close,
                price=price,
                side=self.close_order_side,
                position_action=PositionAction.CLOSE,
            )
            self._close_order = TrackedOrder(order_id=order_id)
            self.logger().debug(f"Executor ID: {self.config.id} - Placing close order {order_id} --> Filled amount: {self.open_filled_amount}")
        self.close_type = close_type
        self.close_timestamp = self._strategy.current_timestamp
        self._status = RunnableStatus.SHUTTING_DOWN

    def cancel_open_orders(self):
        """
        This method is responsible for canceling the open orders.

        :return: None
        """
        if self._open_order and self._open_order.order and self._open_order.order.is_open:
            self.cancel_open_order()
        if self._take_profit_limit_order and self._take_profit_limit_order.order and self._take_profit_limit_order.order.is_open:
            self.cancel_take_profit()

    def control_stop_loss(self):
        """
        This method is responsible for controlling the stop loss. If the net pnl percentage is less than the stop loss
        percentage, it places the close order and cancels the open orders.

        :return: None
        """
        if self.config.triple_barrier_config.stop_loss:
            if self.net_pnl_pct <= -self.config.triple_barrier_config.stop_loss:
                self.place_close_order_and_cancel_open_orders(close_type=CloseType.STOP_LOSS)

    def control_take_profit(self):
        """
        This method is responsible for controlling the take profit. If the net pnl percentage is greater than the take
        profit percentage, it places the close order and cancels the open orders. If the take profit order type is limit,
        it places the take profit limit order. If the amount of the take profit order is different than the total amount
        executed in the open order, it renews the take profit order (can happen with partial fills).

        :return: None
        """
        if self.config.triple_barrier_config.take_profit:
            if self.config.triple_barrier_config.take_profit_order_type.is_limit_type():
                is_within_activation_bounds = self._is_within_activation_bounds(
                    self.take_profit_price, self.close_order_side,
                    self.config.triple_barrier_config.take_profit_order_type)
                if not self._take_profit_limit_order:
                    if is_within_activation_bounds:
                        self.place_take_profit_limit_order()
                else:
                    if self._take_profit_limit_order.is_open and not self._take_profit_limit_order.is_filled and \
                            not is_within_activation_bounds:
                        self.cancel_take_profit()
            elif self.net_pnl_pct >= self.config.triple_barrier_config.take_profit:
                self.place_close_order_and_cancel_open_orders(close_type=CloseType.TAKE_PROFIT)

    def control_time_limit(self):
        """
        This method is responsible for controlling the time limit. If the position is expired, it places the close order
        and cancels the open orders.

        :return: None
        """
        if self.is_expired:
            self.place_close_order_and_cancel_open_orders(close_type=CloseType.TIME_LIMIT)

    def place_take_profit_limit_order(self):
        """
        This method is responsible for placing the take profit limit order.

        :return: None
        """
        order_id = self.place_order(
            connector_name=self.config.connector_name,
            trading_pair=self.config.trading_pair,
            amount=self.amount_to_close,
            price=self.take_profit_price,
            order_type=self.config.triple_barrier_config.take_profit_order_type,
            position_action=PositionAction.CLOSE,
            side=self.close_order_side,
        )
        self._take_profit_limit_order = TrackedOrder(order_id=order_id)
        self.logger().debug(f"Executor ID: {self.config.id} - Placing take profit order {order_id}")

    def renew_take_profit_order(self):
        """
        This method is responsible for renewing the take profit order.

        :return: None
        """
        self.cancel_take_profit()
        self.place_take_profit_limit_order()
        self.logger().debug("Renewing take profit order")

    def cancel_take_profit(self):
        """
        This method is responsible for canceling the take profit order.

        :return: None
        """
        self._strategy.cancel(
            connector_name=self.config.connector_name,
            trading_pair=self.config.trading_pair,
            order_id=self._take_profit_limit_order.order_id
        )
        self.logger().debug("Removing take profit")

    def cancel_open_order(self):
        """
        This method is responsible for canceling the open order.

        :return: None
        """
        self._strategy.cancel(
            connector_name=self.config.connector_name,
            trading_pair=self.config.trading_pair,
            order_id=self._open_order.order_id
        )
        self.logger().debug("Removing open order")

    def early_stop(self, keep_position: bool = False):
        """
        This method allows strategy to stop the executor early.

        :return: None
        """
        self.close_type = CloseType.POSITION_HOLD if keep_position else CloseType.EARLY_STOP
        self._status = RunnableStatus.SHUTTING_DOWN

    def update_tracked_orders_with_order_id(self, order_id: str):
        """
        This method is responsible for updating the tracked orders with the information from the InFlightOrder, using
        the order_id as a reference.

        :param order_id: The order_id to be used as a reference.
        :return: None
        """
        in_flight_order = self.get_in_flight_order(self.config.connector_name, order_id)
        if self._open_order and self._open_order.order_id == order_id:
            self._open_order.order = in_flight_order
        elif self._close_order and self._close_order.order_id == order_id:
            self._close_order.order = in_flight_order
        elif self._take_profit_limit_order and self._take_profit_limit_order.order_id == order_id:
            self._take_profit_limit_order.order = in_flight_order

    def process_order_created_event(self, _, market, event: Union[BuyOrderCreatedEvent, SellOrderCreatedEvent]):
        """
        This method is responsible for processing the order created event. Here we will update the TrackedOrder with the
        order_id.
        """
        self.update_tracked_orders_with_order_id(event.order_id)

    def process_order_filled_event(self, _, market, event: OrderFilledEvent):
        """
        This method is responsible for processing the order filled event. Here we will update the value of
        _total_executed_amount_backup, that can be used if the InFlightOrder
        is not available.
        """
        self.update_tracked_orders_with_order_id(event.order_id)

    def process_order_completed_event(self, _, market, event: Union[BuyOrderCompletedEvent, SellOrderCompletedEvent]):
        """
        This method is responsible for processing the order completed event. Here we will check if the id is one of the
        tracked orders and update the state
        """
        self._total_executed_amount_backup += event.base_asset_amount
        self.update_tracked_orders_with_order_id(event.order_id)

        if self._take_profit_limit_order and self._take_profit_limit_order.order_id == event.order_id:
            self.close_type = CloseType.TAKE_PROFIT
            self._close_order = self._take_profit_limit_order
            self._status = RunnableStatus.SHUTTING_DOWN

    def process_order_canceled_event(self, _, market: ConnectorBase, event: OrderCancelledEvent):
        """
        This method is responsible for processing the order canceled event
        """
        if self._close_order and event.order_id == self._close_order.order_id:
            self._failed_orders.append(self._close_order)
            self._close_order = None
        if self._open_order and event.order_id == self._open_order.order_id:
            self._failed_orders.append(self._open_order)
            self._open_order = None
        if self._take_profit_limit_order and event.order_id == self._take_profit_limit_order.order_id:
            self._failed_orders.append(self._take_profit_limit_order)
            self._take_profit_limit_order = None

    def process_order_failed_event(self, _, market, event: MarketOrderFailureEvent):
        """
        This method is responsible for processing the order failed event. Here we will add the InFlightOrder to the
        failed orders list.
        """
        if self._open_order and event.order_id == self._open_order.order_id:
            self._failed_orders.append(self._open_order)
            self._open_order = None
            self.logger().error(f"Open order failed {event.order_id}. Retrying {self._current_retries}/{self._max_retries}")
            self._current_retries += 1
        elif self._close_order and event.order_id == self._close_order.order_id:
            self._failed_orders.append(self._close_order)
            self._close_order = None
            self.logger().error(f"Close order failed {event.order_id}. Retrying {self._current_retries}/{self._max_retries}")
            self._current_retries += 1
        elif self._take_profit_limit_order and event.order_id == self._take_profit_limit_order.order_id:
            self._failed_orders.append(self._take_profit_limit_order)
            self._take_profit_limit_order = None
            self.logger().error(f"Take profit order failed {event.order_id}. Retrying {self._current_retries}/{self._max_retries}")

    def get_custom_info(self) -> Dict:
        return {
            "level_id": self.config.level_id,
            "current_position_average_price": self.entry_price,
            "side": self.config.side,
            "current_retries": self._current_retries,
            "max_retries": self._max_retries,
            "close_price": self.close_price,
            "open_order_last_update": self._open_order.last_update_timestamp if self._open_order else None,
            "order_ids": [order.order_id for order in [self._open_order, self._close_order, self._take_profit_limit_order] if order],
            "held_position_orders": self._held_position_orders,
        }

    def to_format_status(self, scale=1.0):
        lines = []
        current_price = self.get_price(self.config.connector_name, self.config.trading_pair)
        amount_in_quote = self.entry_price * (self.open_filled_amount if self.open_filled_amount > Decimal("0") else self.config.amount)
        quote_asset = self.config.trading_pair.split("-")[1]
        if self.is_closed:
            lines.extend([f"""
| Trading Pair: {self.config.trading_pair} | Exchange: {self.config.connector_name} | Side: {self.config.side}
| Entry price: {self.entry_price:.6f} | Close price: {self.close_price:.6f} | Amount: {amount_in_quote:.4f} {quote_asset}
| Realized PNL: {self.trade_pnl_quote:.6f} {quote_asset} | Total Fee: {self.cum_fees_quote:.6f} {quote_asset}
| PNL (%): {self.net_pnl_pct * 100:.2f}% | PNL (abs): {self.net_pnl_quote:.6f} {quote_asset} | Close Type: {self.close_type}
"""])
        else:
            lines.extend([f"""
| Trading Pair: {self.config.trading_pair} | Exchange: {self.config.connector_name} | Side: {self.config.side} |
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

    async def validate_sufficient_balance(self):
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
        adjusted_order_candidates = self.adjust_order_candidates(self.config.connector_name, [order_candidate])
        if adjusted_order_candidates[0].amount == Decimal("0"):
            self.close_type = CloseType.INSUFFICIENT_BALANCE
            self.logger().error("Not enough budget to open position.")
            self.stop()

    async def _sleep(self, delay: float):
        """
        This method is responsible for sleeping the executor for a specific time.

        :param delay: The time to sleep.
        :return: None
        """
        await asyncio.sleep(delay)
