import logging
from decimal import Decimal
from typing import List, Optional, Union

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
from hummingbot.smart_components.executors.dca_executor.data_types import DCAConfig, DCAMode
from hummingbot.smart_components.executors.executor_base import ExecutorBase
from hummingbot.smart_components.models.base import SmartComponentStatus
from hummingbot.smart_components.models.executors import CloseType, TrackedOrder
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class DCAExecutor(ExecutorBase):
    _logger = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, strategy: ScriptStrategyBase, dca_config: DCAConfig, update_interval: float = 1.0,
                 max_retries: int = 5):
        # validate amounts and prices
        if len(dca_config.amounts_quote) != len(dca_config.prices):
            raise ValueError("Amounts and prices lists must have the same length")
        self._dca_config: DCAConfig = dca_config
        self.n_levels = len(dca_config.amounts_quote)

        # set default bounds if is taker
        if self._dca_config.mode == DCAMode.TAKER and not self._dca_config.activation_bounds:
            self._dca_config.activation_bounds = [Decimal("0.0001"), Decimal("0.005")]  # 0.01% and 0.5%

        # executors tracking
        self._open_orders: List[TrackedOrder] = []
        self._close_orders: List[TrackedOrder] = []  # for now will be just one order but we can have multiple
        self._failed_orders: List[TrackedOrder] = []
        self._trailing_stop_trigger_pct: Optional[Decimal] = None
        self.close_type: Optional[CloseType] = None
        self.close_timestamp: Optional[int] = None

        # used to track the total amount filled that is updated by the event in case that the InFlightOrder is
        # not available
        self._total_executed_amount_backup: Decimal = Decimal("0")

        # add retries
        self._current_retries = 0
        self._max_retries = max_retries
        super().__init__(strategy=strategy, connectors=[dca_config.exchange], update_interval=update_interval)

    @property
    def active_orders(self) -> List[TrackedOrder]:
        return self._open_orders

    @property
    def open_order_type(self) -> OrderType:
        return OrderType.LIMIT if self._dca_config.mode == DCAMode.MAKER else OrderType.MARKET

    @property
    def close_order_type(self) -> OrderType:
        return OrderType.MARKET

    @property
    def filled_amount(self) -> Decimal:
        return sum([order.executed_amount_base for order in self.active_orders])

    @property
    def filled_amount_quote(self) -> Decimal:
        return self.filled_amount * self.current_position_average_price

    @property
    def max_amount_quote(self) -> Decimal:
        return sum(self._dca_config.amounts_quote)

    @property
    def min_price(self) -> Decimal:
        return min(self._dca_config.prices)

    @property
    def max_price(self) -> Decimal:
        return max(self._dca_config.prices)

    @property
    def max_loss_quote(self) -> Decimal:
        return self.max_amount_quote * self._dca_config.stop_loss

    @property
    def current_market_price(self):
        """
        This method is responsible for getting the current market price to be used as a reference for control barriers
        """
        price_type = PriceType.BestBid if self._dca_config.side == TradeType.BUY else PriceType.BestAsk
        return self.get_price(self._dca_config.exchange, self._dca_config.trading_pair, price_type=price_type)

    @property
    def close_price(self):
        """
        This method is responsible for getting the close price, if the executor is active, it will return the current
        market price, otherwise it will return the average price of the closed orders
        """
        if self.status == SmartComponentStatus.TERMINATED:
            return sum([order.average_executed_price * order.executed_amount_base for order in self._close_orders]) / \
                self.filled_amount if self._close_orders and self.filled_amount > Decimal("0") else Decimal("0")
        else:
            return self.current_market_price

    @property
    def current_position_average_price(self) -> Decimal:
        return sum([order.average_executed_price * order.executed_amount_base for order in self._open_orders]) / \
            self.filled_amount if self._open_orders and self.filled_amount > Decimal("0") else Decimal("0")

    @property
    def target_position_average_price(self) -> Decimal:
        return sum([price * amount for price, amount in
                    zip(self._dca_config.prices, self._dca_config.amounts_quote)]) / self.max_amount_quote

    @property
    def trade_pnl_pct(self):
        """
        This method is responsible for calculating the trade pnl (Pure pnl without fees)
        """
        if self.current_position_average_price:
            if self._dca_config.side == TradeType.BUY:
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
        return self.trade_pnl_pct * self.filled_amount * self.current_position_average_price

    @property
    def net_pnl_quote(self) -> Decimal:
        """
        This method is responsible for calculating the net pnl in quote asset
        """
        return self.trade_pnl_quote - self.cum_fee_quote

    @property
    def net_pnl_pct(self) -> Decimal:
        """
        This method is responsible for calculating the net pnl percentage
        """
        return self.net_pnl_quote / self.filled_amount_quote if self.filled_amount_quote else Decimal("0")

    @property
    def cum_fee_quote(self) -> Decimal:
        """
        This method is responsible for calculating the cumulative fees in quote asset
        """
        all_orders = self._open_orders + self._close_orders
        return sum([order.cum_fees_quote for order in all_orders])

    @property
    def all_open_orders_executed(self) -> bool:
        """
        This method is responsible for checking if all orders are completed
        """
        return all([order.is_done for order in self._open_orders]) and len(self._open_orders) == self.n_levels

    def check_budget(self):
        """
        This method is responsible for checking the budget
        """
        order_candidates = []
        for amount_quote, price in zip(self._dca_config.amounts_quote, self._dca_config.prices):
            amount_base = amount_quote / price
            is_maker = self._dca_config.mode == DCAMode.MAKER
            if self.is_perpetual_connector(self._dca_config.exchange):
                order_candidate = PerpetualOrderCandidate(
                    trading_pair=self._dca_config.trading_pair,
                    is_maker=is_maker,
                    order_type=self.open_order_type,
                    order_side=self._dca_config.side,
                    amount=amount_base,
                    price=price,
                    leverage=Decimal(self._dca_config.leverage),
                )
            else:
                order_candidate = OrderCandidate(
                    trading_pair=self._dca_config.trading_pair,
                    is_maker=is_maker,
                    order_type=self.open_order_type,
                    order_side=self._dca_config.side,
                    amount=amount_base,
                    price=price,
                )
            order_candidates.append(order_candidate)
        adjusted_order_candidates = self.adjust_order_candidates(self._dca_config.exchange, order_candidates)
        if any([order_candidate.amount == Decimal("0") for order_candidate in adjusted_order_candidates]):
            self.close_type = CloseType.INSUFFICIENT_BALANCE
            self.stop()
            self.logger().error("Not enough budget to create DCA.")

    async def control_task(self):
        """
        This task is responsible for creating and closing position executors
        """
        if self.status == SmartComponentStatus.RUNNING:
            self.control_open_order_process()
            self.control_barriers()
        elif self.status == SmartComponentStatus.SHUTTING_DOWN:
            self.control_shutdown_process()

    def control_open_order_process(self):
        """
        This method is responsible for controlling the opening process
        """
        next_level = len(self._open_orders)
        if next_level < self.n_levels:
            close_price = self.get_price(connector_name=self._dca_config.exchange,
                                         trading_pair=self._dca_config.trading_pair)
            order_price = self._dca_config.prices[next_level]
            if self._is_within_activation_bounds(order_price, close_price):
                self.create_dca_order(level=next_level)

    def create_dca_order(self, level: int):
        """
        This method is responsible for creating a new DCA order
        """
        price = self._dca_config.prices[level]
        amount = self._dca_config.amounts_quote[level] / price
        order_id = self.place_order(connector_name=self._dca_config.exchange,
                                    trading_pair=self._dca_config.trading_pair, order_type=self.open_order_type,
                                    side=self._dca_config.side, amount=amount, price=price,
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

    def control_stop_loss(self):
        """
        This method is responsible for controlling the stop loss. In order to trigger the stop loss all the orders must
        be completed and the net pnl must be lower than the stop loss. If it's maker mode, the stop loss will be
        triggered if the net pnl is lower than the stop loss and all the orders were executed, otherwise the stop loss
        will be triggered if the net pnl is lower than the stop loss.
        """
        if self._dca_config.stop_loss:
            if self._dca_config.mode == DCAMode.MAKER:
                if self.all_open_orders_executed and self.net_pnl_pct < self._dca_config.stop_loss:
                    self.place_close_order(close_type=CloseType.STOP_LOSS)
            else:
                if self.net_pnl_quote < self.max_loss_quote:
                    self.place_close_order(close_type=CloseType.STOP_LOSS)

    def control_trailing_stop(self):
        """
        This method is responsible for controlling the trailing stop. In order to activated the trailing stop the net
        pnl must be higher than the activation price delta. Once the trailing stop is activated, the trailing stop trigger
        will be the activation price delta minus the trailing delta and the stop loss will be triggered if the net pnl
        is lower than the trailing stop trigger. the value of hte trailing stop trigger will be updated if the net pnl
        minus the trailing delta is higher than the current value of the trailing stop trigger.
        """
        if self._dca_config.trailing_stop:
            if not self._trailing_stop_trigger_pct:
                if self.net_pnl_pct > self._dca_config.trailing_stop.activation_price:
                    self._trailing_stop_trigger_pct = self.net_pnl_pct
            else:
                if self.net_pnl_pct - self._dca_config.trailing_stop.trailing_delta > self._trailing_stop_trigger_pct:
                    self._trailing_stop_trigger_pct = self.net_pnl_pct - self._dca_config.trailing_stop.trailing_delta
                if self.net_pnl_pct < self._trailing_stop_trigger_pct:
                    self.place_close_order(close_type=CloseType.TRAILING_STOP)

    def control_take_profit(self):
        """
        This method is responsible for controlling the take profit. In order to trigger the take profit all the orders must
        be completed and the net pnl must be higher than the take profit
        """
        if self._dca_config.take_profit:
            if self.net_pnl_pct > self._dca_config.take_profit:
                self.place_close_order(close_type=CloseType.TAKE_PROFIT)

    def early_stop(self):
        """
        This method allows strategy to stop the executor early.
        """
        self.place_close_order(close_type=CloseType.EARLY_STOP)

    def place_close_order(self, close_type: CloseType, price: Decimal = Decimal("NaN")):
        """
        This method is responsible for placing the close order
        """
        order_id = self.place_order(
            connector_name=self._dca_config.exchange,
            trading_pair=self._dca_config.trading_pair,
            order_type=OrderType.MARKET,
            amount=self.filled_amount,
            price=price,
            side=TradeType.SELL if self._dca_config.side == TradeType.BUY else TradeType.BUY,
            position_action=PositionAction.CLOSE,
        )
        self.close_type = close_type
        self._status = SmartComponentStatus.SHUTTING_DOWN
        self._close_orders.append(TrackedOrder(order_id=order_id))

    def _is_within_activation_bounds(self, order_price: Decimal, close_price: Decimal) -> bool:
        """
        This method is responsible for checking if the order is within the activation bounds
        """
        activation_bounds = self._dca_config.activation_bounds
        if self._dca_config.mode == DCAMode.MAKER:
            if activation_bounds:
                if self._dca_config.side == TradeType.BUY:
                    return order_price < close_price * (1 + activation_bounds[0])
                else:
                    return order_price > close_price * (1 - activation_bounds[0])
            else:
                return True
        elif self._dca_config.mode == DCAMode.TAKER:
            # Taker mode requires activation bounds for safety. Default to 0.01% and 0.5% if not provided.
            if self._dca_config.side == TradeType.BUY:
                min_price_to_buy = order_price * (1 - activation_bounds[0])
                max_price_to_buy = order_price * (1 + activation_bounds[1])
                return min_price_to_buy < close_price < max_price_to_buy
            else:
                min_price_to_sell = order_price * (1 - activation_bounds[1])
                max_price_to_sell = order_price * (1 + activation_bounds[0])
                return min_price_to_sell < close_price < max_price_to_sell

    def control_shutdown_process(self):
        """
        This method is responsible for shutting down the process, ensuring that all orders are completed.
        """
        active_open_orders = [order for order in self._open_orders if not order.is_done]
        active_close_orders = [order for order in self._close_orders if not order.is_done]
        if not active_open_orders and not active_close_orders:
            self.stop()
        else:
            for active_open_order in active_open_orders:
                self._strategy.cancel(
                    connector_name=self._dca_config.exchange,
                    trading_pair=self._dca_config.trading_pair,
                    order_id=active_open_order.order_id
                )

    def process_order_created_event(self,
                                    event_tag: int,
                                    market: ConnectorBase,
                                    event: Union[BuyOrderCreatedEvent, SellOrderCreatedEvent]):
        """
        This method is responsible for processing the order created event. Here we will add the InFlightOrder to the
        active orders list.
        """
        all_orders = self._open_orders + self._close_orders
        active_order = next((order for order in all_orders if order.order_id == event.order_id), None)
        if active_order:
            in_flight_order = self.get_in_flight_order(self._dca_config.exchange, event.order_id)
            if in_flight_order:
                active_order.in_flight_order = in_flight_order
                self.logger().debug(f"Order {event.order_id} created.")

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
            self.place_close_order(close_type=self.close_type)
        self._current_retries += 1
        if self._current_retries >= self._max_retries:
            self.close_type = CloseType.FAILED
            self.stop()
            self.logger().error("Max retries reached. Stopping DCA executor.")

    def process_order_filled_event(self, event_tag: int, market: ConnectorBase, event: OrderFilledEvent):
        """
        This method is responsible for processing the order filled event. Here we will update the value of
        _total_executed_amount_backup, that can be used if the InFlightOrder
        is not available.
        """
        self._total_executed_amount_backup += event.amount

    def to_json(self):
        """
        Serializes the object to json
        """
        return {
            "timestamp": self._dca_config.timestamp,
            "exchange": self._dca_config.exchange,
            "trading_pair": self._dca_config.trading_pair,
            "status": self.status.name,
            "side": self._dca_config.side.name,
            "leverage": self._dca_config.leverage,
            "close_type": self.close_type.name if self.close_type else None,
            "close_timestamp": self.close_timestamp,
            "filled_amount": self.filled_amount,
            "filled_amount_quote": self.filled_amount_quote,
            "max_amount_quote": self.max_amount_quote,
            "min_price": self.min_price,
            "max_price": self.max_price,
            "current_position_average_price": self.current_position_average_price,
            "target_position_average_price": self.target_position_average_price,
            "stop_loss": self._dca_config.stop_loss,
            "take_profit": self._dca_config.take_profit,
            "trailing_stop_activation_price": self._dca_config.trailing_stop.activation_price,
            "trailing_stop_trailing_delta": self._dca_config.trailing_stop.trailing_delta,
            "trailing_stop_trigger_pct": self._trailing_stop_trigger_pct,
            "net_pnl_quote": self.net_pnl_quote,
            "cum_fee_quote": self.cum_fee_quote,
            "net_pnl_pct": self.net_pnl_pct,
            "max_loss_quote": self.max_loss_quote,
        }
