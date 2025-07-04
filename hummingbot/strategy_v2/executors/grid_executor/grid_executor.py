import asyncio
import logging
import math
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
from hummingbot.strategy_v2.executors.grid_executor.data_types import GridExecutorConfig, GridLevel, GridLevelStates
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executors import CloseType, TrackedOrder
from hummingbot.strategy_v2.utils.distributions import Distributions



# 网格执行器，继承自基础执行器
class GridExecutor(ExecutorBase):
    _logger = None  # 日志记录器

    @classmethod
    def logger(cls) -> HummingbotLogger:
        # 获取日志记录器
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, strategy: ScriptStrategyBase, config: GridExecutorConfig,
                 update_interval: float = 1.0, max_retries: int = 10):
        """
        初始化网格执行器实例。

        :param strategy: 策略对象。
        :param config: 网格执行器配置。
        :param update_interval: 执行器更新间隔，默认1.0秒。
        :param max_retries: 最大重试次数，默认10。
        """
        self.config: GridExecutorConfig = config  # 网格配置
        # 检查三重风控配置，止损和限时单仅支持市价单
        if config.triple_barrier_config.time_limit_order_type != OrderType.MARKET or \
                config.triple_barrier_config.stop_loss_order_type != OrderType.MARKET:
            error = "Only market orders are supported for time_limit and stop_loss"
            self.logger().error(error)
            raise ValueError(error)
        super().__init__(strategy=strategy, config=config, connectors=[config.connector_name],
                         update_interval=update_interval)
        self.open_order_price_type = PriceType.BestBid if config.side == TradeType.BUY else PriceType.BestAsk  # 开仓挂单类型
        self.close_order_price_type = PriceType.BestAsk if config.side == TradeType.BUY else PriceType.BestBid  # 平仓挂单类型
        self.close_order_side = TradeType.BUY if config.side == TradeType.SELL else TradeType.SELL  # 平仓方向
        self.trading_rules = self.get_trading_rules(self.config.connector_name, self.config.trading_pair)  # 交易规则
        # 网格层级
        self.grid_levels = self._generate_grid_levels()
        self.levels_by_state = {state: [] for state in GridLevelStates}  # 各状态下的网格层级
        self._close_order: Optional[TrackedOrder] = None  # 当前平仓订单
        self._filled_orders = []  # 已成交订单
        self._failed_orders = []  # 失败订单
        self._canceled_orders = []  # 已取消订单

        # 相关指标初始化
        self.step = Decimal("0")  # 网格步长
        self.position_break_even_price = Decimal("0")  # 持仓盈亏平衡价
        self.position_size_base = Decimal("0")  # 持仓基础币数量
        self.position_size_quote = Decimal("0")  # 持仓计价币数量
        self.position_fees_quote = Decimal("0")  # 持仓手续费
        self.position_pnl_quote = Decimal("0")  # 持仓未实现盈亏
        self.position_pnl_pct = Decimal("0")  # 持仓未实现盈亏百分比
        self.open_liquidity_placed = Decimal("0")  # 已挂开仓单资金
        self.close_liquidity_placed = Decimal("0")  # 已挂平仓单资金
        self.realized_buy_size_quote = Decimal("0")  # 已实现买入金额
        self.realized_sell_size_quote = Decimal("0")  # 已实现卖出金额
        self.realized_imbalance_quote = Decimal("0")  # 已实现买卖差额
        self.realized_fees_quote = Decimal("0")  # 已实现手续费
        self.realized_pnl_quote = Decimal("0")  # 已实现盈亏
        self.realized_pnl_pct = Decimal("0")  # 已实现盈亏百分比
        self.max_open_creation_timestamp = 0  # 最近开仓单创建时间戳
        self.max_close_creation_timestamp = 0  # 最近平仓单创建时间戳
        self._open_fee_in_base = False  # 是否基础币扣费

        self._trailing_stop_trigger_pct: Optional[Decimal] = None  # 跟踪止损触发百分比
        self._current_retries = 0  # 当前重试次数
        self._max_retries = max_retries  # 最大重试次数

    @property
    def is_perpetual(self) -> bool:
        """
        判断当前连接器是否为永续合约。

        :return: 如果是永续合约返回True，否则返回False。
        """
        return self.is_perpetual_connector(self.config.connector_name)

    async def validate_sufficient_balance(self):
        """
        校验账户余额是否足够开仓。
        """
        mid_price = self.get_price(self.config.connector_name, self.config.trading_pair, PriceType.MidPrice)
        total_amount_base = self.config.total_amount_quote / mid_price
        if self.is_perpetual:
            order_candidate = PerpetualOrderCandidate(
                trading_pair=self.config.trading_pair,
                is_maker=self.config.triple_barrier_config.open_order_type.is_limit_type(),
                order_type=self.config.triple_barrier_config.open_order_type,
                order_side=self.config.side,
                amount=total_amount_base,
                price=mid_price,
                leverage=Decimal(self.config.leverage),
            )
        else:
            order_candidate = OrderCandidate(
                trading_pair=self.config.trading_pair,
                is_maker=self.config.triple_barrier_config.open_order_type.is_limit_type(),
                order_type=self.config.triple_barrier_config.open_order_type,
                order_side=self.config.side,
                amount=total_amount_base,
                price=mid_price,
            )
        adjusted_order_candidates = self.adjust_order_candidates(self.config.connector_name, [order_candidate])
        if adjusted_order_candidates[0].amount == Decimal("0"):
            self.close_type = CloseType.INSUFFICIENT_BALANCE
            self.logger().error("Not enough budget to open position.")
            self.stop()

    def _generate_grid_levels(self):
        """
        生成网格层级列表，根据配置和交易规则自动分配每层价格和下单金额。
        """
        grid_levels = []
        price = self.get_price(self.config.connector_name, self.config.trading_pair, PriceType.MidPrice)
        # 获取最小名义金额和最小基础币下单增量
        min_notional = max(
            self.config.min_order_amount_quote,
            self.trading_rules.min_notional_size
        )
        min_base_increment = self.trading_rules.min_base_amount_increment
        # 给最小名义金额加安全边际，防止价格波动和量化误差
        min_notional_with_margin = min_notional * Decimal("1.05")  # 20% margin for safety
        # 计算同时满足最小名义金额和最小下单增量的基础币数量
        min_base_amount = max(
            min_notional_with_margin / price,  # Minimum from notional requirement
            min_base_increment * Decimal(str(math.ceil(float(min_notional) / float(min_base_increment * price))))
        )
        # 对最小基础币数量进行量化
        min_base_amount = Decimal(
            str(math.ceil(float(min_base_amount) / float(min_base_increment)))) * min_base_increment
        # 校验量化后金额是否满足最小名义金额
        min_quote_amount = min_base_amount * price
        # 计算网格区间和最小步长
        grid_range = (self.config.end_price - self.config.start_price) / self.config.start_price
        min_step_size = max(
            self.config.min_spread_between_orders,
            self.trading_rules.min_price_increment / price
        )
        # 根据总资金计算最大可用网格层数
        max_possible_levels = int(self.config.total_amount_quote / min_quote_amount)
        if max_possible_levels == 0:
            # If we can't even create one level, create a single level with minimum amount
            n_levels = 1
            quote_amount_per_level = min_quote_amount
        else:
            # Calculate optimal number of levels
            max_levels_by_step = int(grid_range / min_step_size)
            n_levels = min(max_possible_levels, max_levels_by_step)
            # Calculate quote amount per level ensuring it meets minimum after quantization
            base_amount_per_level = max(
                min_base_amount,
                Decimal(str(math.floor(float(self.config.total_amount_quote / (price * n_levels)) /
                                       float(min_base_increment)))) * min_base_increment
            )
            quote_amount_per_level = base_amount_per_level * price
            # Adjust number of levels if total amount would be exceeded
            n_levels = min(n_levels, int(float(self.config.total_amount_quote) / float(quote_amount_per_level)))
        # 至少保证有一层网格
        n_levels = max(1, n_levels)
        # 均匀分布生成每层价格
        if n_levels > 1:
            prices = Distributions.linear(n_levels, float(self.config.start_price), float(self.config.end_price))
            self.step = grid_range / (n_levels - 1)
        else:
            # For single level, use mid-point of range
            mid_price = (self.config.start_price + self.config.end_price) / 2
            prices = [mid_price]
            self.step = grid_range
        take_profit = max(self.step, self.config.triple_barrier_config.take_profit) if self.config.coerce_tp_to_step else self.config.triple_barrier_config.take_profit
        # 创建每一层网格对象
        for i, price in enumerate(prices):
            grid_levels.append(
                GridLevel(
                    id=f"L{i}",
                    price=price,
                    amount_quote=quote_amount_per_level,
                    take_profit=take_profit,
                    side=self.config.side,
                    open_order_type=self.config.triple_barrier_config.open_order_type,
                    take_profit_order_type=self.config.triple_barrier_config.take_profit_order_type,
                )
            )
        # 日志记录网格创建详情
        self.logger().info(
            f"Created {len(grid_levels)} grid levels with "
            f"amount per level: {quote_amount_per_level:.4f} {self.config.trading_pair.split('-')[1]} "
            f"(base amount: {(quote_amount_per_level / price):.8f} {self.config.trading_pair.split('-')[0]})"
        )
        return grid_levels

    @property
    def end_time(self) -> Optional[float]:
        """
        根据三重风控的限时参数计算本次网格的结束时间。

        :return: 网格结束时间戳。
        """
        if not self.config.triple_barrier_config.time_limit:
            return None
        return self.config.timestamp + self.config.triple_barrier_config.time_limit

    @property
    def is_expired(self) -> bool:
        """
        判断网格是否已到期。

        :return: 到期返回True，否则False。
        """
        return self.end_time and self.end_time <= self._strategy.current_timestamp

    @property
    def is_trading(self):
        """
        判断当前是否处于交易状态。

        :return: 处于交易状态返回True，否则False。
        """
        return self.status == RunnableStatus.RUNNING and self.position_size_quote > Decimal("0")

    @property
    def is_active(self):
        """
        返回执行器是否处于打开或交易状态。
        """
        return self._status in [RunnableStatus.RUNNING, RunnableStatus.NOT_STARTED, RunnableStatus.SHUTTING_DOWN]

    async def control_task(self):
        """
        此方法根据执行器的状态控制任务。

        :return: None
        """
        self.update_grid_levels()
        self.update_metrics()
        if self.status == RunnableStatus.RUNNING:
            if self.control_triple_barrier():
                self.cancel_open_orders()
                self._status = RunnableStatus.SHUTTING_DOWN
                return
            open_orders_to_create = self.get_open_orders_to_create()
            close_orders_to_create = self.get_close_orders_to_create()
            open_order_ids_to_cancel = self.get_open_order_ids_to_cancel()
            close_order_ids_to_cancel = self.get_close_order_ids_to_cancel()
            for level in open_orders_to_create:
                self.adjust_and_place_open_order(level)
            for level in close_orders_to_create:
                self.adjust_and_place_close_order(level)
            for orders_id_to_cancel in open_order_ids_to_cancel + close_order_ids_to_cancel:
                # TODO: Implement batch order cancel
                self._strategy.cancel(
                    connector_name=self.config.connector_name,
                    trading_pair=self.config.trading_pair,
                    order_id=orders_id_to_cancel
                )
        elif self.status == RunnableStatus.SHUTTING_DOWN:
            await self.control_shutdown_process()
        self.evaluate_max_retries()

    def early_stop(self, keep_position: bool = False):
        """
        此方法允许策略提前停止执行器。

        :return: None
        """
        self.cancel_open_orders()
        self._status = RunnableStatus.SHUTTING_DOWN
        self.close_type = CloseType.POSITION_HOLD if keep_position else CloseType.EARLY_STOP

    def update_grid_levels(self):
        """
        更新网格层级的状态。
        """
        self.levels_by_state = {state: [] for state in GridLevelStates}
        for level in self.grid_levels:
            level.update_state()
            self.levels_by_state[level.state].append(level)
        completed = self.levels_by_state[GridLevelStates.COMPLETE]
        # Get completed orders and store them in the filled orders list
        for level in completed:
            if level.active_open_order.order.completely_filled_event.is_set() and level.active_close_order.order.completely_filled_event.is_set():
                open_order = level.active_open_order.order.to_json()
                close_order = level.active_close_order.order.to_json()
                self._filled_orders.append(open_order)
                self._filled_orders.append(close_order)
                self.levels_by_state[GridLevelStates.COMPLETE].remove(level)
                level.reset_level()
                self.levels_by_state[GridLevelStates.NOT_ACTIVE].append(level)

    async def control_shutdown_process(self):
        """
        控制执行器的关闭过程，单独处理持仓。
        """
        self.close_timestamp = self._strategy.current_timestamp
        open_orders_completed = self.open_liquidity_placed == Decimal("0")
        close_orders_completed = self.close_liquidity_placed == Decimal("0")

        if open_orders_completed and close_orders_completed:
            if self.close_type == CloseType.POSITION_HOLD:
                # Move filled orders to held positions instead of regular filled orders
                for level in self.levels_by_state[GridLevelStates.OPEN_ORDER_FILLED]:
                    if level.active_open_order and level.active_open_order.order:
                        self._held_position_orders.append(level.active_open_order.order.to_json())
                    level.reset_level()
                for level in self.levels_by_state[GridLevelStates.CLOSE_ORDER_PLACED]:
                    if level.active_close_order and level.active_close_order.order:
                        self._held_position_orders.append(level.active_close_order.order.to_json())
                    level.reset_level()
                if len(self._held_position_orders) == 0:
                    self.close_type = CloseType.EARLY_STOP
                self.levels_by_state = {}
                self.stop()
            else:
                # Regular shutdown process for non-held positions
                order_execution_completed = self.position_size_base == Decimal("0")
                if order_execution_completed:
                    for level in self.levels_by_state[GridLevelStates.OPEN_ORDER_FILLED]:
                        if level.active_open_order and level.active_open_order.order:
                            self._filled_orders.append(level.active_open_order.order.to_json())
                        level.reset_level()
                    for level in self.levels_by_state[GridLevelStates.CLOSE_ORDER_PLACED]:
                        if level.active_close_order and level.active_close_order.order:
                            self._filled_orders.append(level.active_close_order.order.to_json())
                        level.reset_level()
                    if self._close_order and self._close_order.order:
                        self._filled_orders.append(self._close_order.order.to_json())
                        self._close_order = None
                    self.update_realized_pnl_metrics()
                    self.levels_by_state = {}
                    self.stop()
                else:
                    await self.control_close_order()
                    self._current_retries += 1
        else:
            self.cancel_open_orders()
        await self._sleep(5.0)

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
                self.logger().info("Waiting for close order to be filled")
            else:
                self._failed_orders.append(self._close_order.order_id)
                self._close_order = None
        elif not self.config.keep_position or self.close_type == CloseType.TAKE_PROFIT:
            self.place_close_order_and_cancel_open_orders(close_type=self.close_type)

    def adjust_and_place_open_order(self, level: GridLevel):
        """
        This method is responsible for adjusting the open order and placing it.

        :param level: The level to adjust and place the open order.
        :return: None
        """
        order_candidate = self._get_open_order_candidate(level)
        self.adjust_order_candidates(self.config.connector_name, [order_candidate])
        if order_candidate.amount > 0:
            order_id = self.place_order(
                connector_name=self.config.connector_name,
                trading_pair=self.config.trading_pair,
                order_type=self.config.triple_barrier_config.open_order_type,
                amount=order_candidate.amount,
                price=order_candidate.price,
                side=order_candidate.order_side,
                position_action=PositionAction.OPEN,
            )
            level.active_open_order = TrackedOrder(order_id=order_id)
            self.max_open_creation_timestamp = self._strategy.current_timestamp
            self.logger().debug(f"Executor ID: {self.config.id} - Placing open order {order_id}")

    def adjust_and_place_close_order(self, level: GridLevel):
        order_candidate = self._get_close_order_candidate(level)
        self.adjust_order_candidates(self.config.connector_name, [order_candidate])
        if order_candidate.amount > 0:
            order_id = self.place_order(
                connector_name=self.config.connector_name,
                trading_pair=self.config.trading_pair,
                order_type=self.config.triple_barrier_config.take_profit_order_type,
                amount=order_candidate.amount,
                price=order_candidate.price,
                side=order_candidate.order_side,
                position_action=PositionAction.CLOSE,
            )
            level.active_close_order = TrackedOrder(order_id=order_id)
            self.logger().debug(f"Executor ID: {self.config.id} - Placing close order {order_id}")

    def get_take_profit_price(self, level: GridLevel):
        return level.price * (1 + level.take_profit) if self.config.side == TradeType.BUY else level.price * (1 - level.take_profit)

    def _get_open_order_candidate(self, level: GridLevel):
        if ((level.side == TradeType.BUY and level.price >= self.current_open_quote) or
                (level.side == TradeType.SELL and level.price <= self.current_open_quote)):
            entry_price = self.current_open_quote * (1 - self.config.safe_extra_spread) if level.side == TradeType.BUY else self.current_open_quote * (1 + self.config.safe_extra_spread)
        else:
            entry_price = level.price
        if self.is_perpetual:
            return PerpetualOrderCandidate(
                trading_pair=self.config.trading_pair,
                is_maker=self.config.triple_barrier_config.open_order_type.is_limit_type(),
                order_type=self.config.triple_barrier_config.open_order_type,
                order_side=self.config.side,
                amount=level.amount_quote / self.mid_price,
                price=entry_price,
                leverage=Decimal(self.config.leverage)
            )
        return OrderCandidate(
            trading_pair=self.config.trading_pair,
            is_maker=self.config.triple_barrier_config.open_order_type.is_limit_type(),
            order_type=self.config.triple_barrier_config.open_order_type,
            order_side=self.config.side,
            amount=level.amount_quote / self.mid_price,
            price=entry_price
        )

    def _get_close_order_candidate(self, level: GridLevel):
        take_profit_price = self.get_take_profit_price(level)
        if ((level.side == TradeType.BUY and take_profit_price <= self.current_close_quote) or
                (level.side == TradeType.SELL and take_profit_price >= self.current_close_quote)):
            take_profit_price = self.current_close_quote * (
                1 + self.config.safe_extra_spread) if level.side == TradeType.BUY else self.current_close_quote * (
                1 - self.config.safe_extra_spread)
        if level.active_open_order.fee_asset == self.config.trading_pair.split("-")[0] and self.config.deduct_base_fees:
            amount = level.active_open_order.executed_amount_base - level.active_open_order.cum_fees_base
            self._open_fee_in_base = True
        else:
            amount = level.active_open_order.executed_amount_base
        if self.is_perpetual:
            return PerpetualOrderCandidate(
                trading_pair=self.config.trading_pair,
                is_maker=self.config.triple_barrier_config.take_profit_order_type.is_limit_type(),
                order_type=self.config.triple_barrier_config.take_profit_order_type,
                order_side=self.close_order_side,
                amount=amount,
                price=take_profit_price,
                leverage=Decimal(self.config.leverage)
            )
        return OrderCandidate(
            trading_pair=self.config.trading_pair,
            is_maker=self.config.triple_barrier_config.take_profit_order_type.is_limit_type(),
            order_type=self.config.triple_barrier_config.take_profit_order_type,
            order_side=self.close_order_side,
            amount=amount,
            price=take_profit_price
        )

    def update_metrics(self):
        self.mid_price = self.get_price(self.config.connector_name, self.config.trading_pair, PriceType.MidPrice)
        self.current_open_quote = self.get_price(self.config.connector_name, self.config.trading_pair,
                                                 price_type=self.open_order_price_type)
        self.current_close_quote = self.get_price(self.config.connector_name, self.config.trading_pair,
                                                  price_type=self.close_order_price_type)
        self.update_position_metrics()
        self.update_realized_pnl_metrics()

    def get_open_orders_to_create(self):
        """
        This method is responsible for controlling the open orders. Will check for each grid level if the order if there
        is an open order. If not, it will place a new orders from the proposed grid levels based on the current price,
        max open orders, max orders per batch, activation bounds and order frequency.
        """
        n_open_orders = len(
            [level.active_open_order for level in self.levels_by_state[GridLevelStates.OPEN_ORDER_PLACED]])
        if (self.max_open_creation_timestamp > self._strategy.current_timestamp - self.config.order_frequency or
                n_open_orders >= self.config.max_open_orders):
            return []
        levels_allowed = self._filter_levels_by_activation_bounds()
        sorted_levels_by_proximity = self._sort_levels_by_proximity(levels_allowed)
        return sorted_levels_by_proximity[:self.config.max_orders_per_batch]

    def get_close_orders_to_create(self):
        """
        This method is responsible for controlling the take profit. It will check if the net pnl percentage is greater
        than the take profit percentage and place the close order.

        :return: None
        """
        close_orders_proposal = []
        open_orders_filled = self.levels_by_state[GridLevelStates.OPEN_ORDER_FILLED]
        for level in open_orders_filled:
            if self.config.activation_bounds:
                tp_to_mid = abs(self.get_take_profit_price(level) - self.mid_price) / self.mid_price
                if tp_to_mid < self.config.activation_bounds:
                    close_orders_proposal.append(level)
            else:
                close_orders_proposal.append(level)
        return close_orders_proposal

    def get_open_order_ids_to_cancel(self):
        if self.config.activation_bounds:
            open_orders_to_cancel = []
            open_orders_placed = [level.active_open_order for level in
                                  self.levels_by_state[GridLevelStates.OPEN_ORDER_PLACED]]
            for order in open_orders_placed:
                price = order.price
                if price:
                    distance_pct = abs(price - self.mid_price) / self.mid_price
                    if distance_pct > self.config.activation_bounds:
                        open_orders_to_cancel.append(order.order_id)
                        self.logger().debug(f"Executor ID: {self.config.id} - Canceling open order {order.order_id}")
            return open_orders_to_cancel
        return []

    def get_close_order_ids_to_cancel(self):
        """
        此方法负责控制平仓订单。它将检查止盈价格是否高于当前价格，
        并取消平仓订单。

        :return: None
        """
        if self.config.activation_bounds:
            close_orders_to_cancel = []
            close_orders_placed = [level.active_close_order for level in
                                   self.levels_by_state[GridLevelStates.CLOSE_ORDER_PLACED]]
            for order in close_orders_placed:
                price = order.price
                if price:
                    distance_to_mid = abs(price - self.mid_price) / self.mid_price
                    if distance_to_mid > self.config.activation_bounds:
                        close_orders_to_cancel.append(order.order_id)
            return close_orders_to_cancel
        return []

    def _filter_levels_by_activation_bounds(self):
        """
        根据激活边界筛选未激活的网格层级。
        :return: 在激活边界内的未激活层级列表。
        """
        not_active_levels = self.levels_by_state[GridLevelStates.NOT_ACTIVE]
        if self.config.activation_bounds:
            if self.config.side == TradeType.BUY:
                activation_bounds_price = self.mid_price * (1 - self.config.activation_bounds)
                return [level for level in not_active_levels if level.price >= activation_bounds_price]
            else:
                activation_bounds_price = self.mid_price * (1 + self.config.activation_bounds)
                return [level for level in not_active_levels if level.price <= activation_bounds_price]
        return not_active_levels

    def _sort_levels_by_proximity(self, levels: List[GridLevel]):
        """
        按与中间价的接近程度对层级进行排序。
        :param levels: 要排序的层级列表。
        :return: 按接近程度排序后的层级列表。
        """
        return sorted(levels, key=lambda level: abs(level.price - self.mid_price))

    def control_triple_barrier(self):
        """
        此方法负责控制各种交易屏障，包括止损、止盈、时间限制和跟踪止损。

        :return: 如果触发了任何屏障，返回True，否则返回False。
        """
        if self.stop_loss_condition():
            self.close_type = CloseType.STOP_LOSS
            return True
        elif self.limit_price_condition():
            self.close_type = CloseType.POSITION_HOLD if self.config.keep_position else CloseType.STOP_LOSS
            return True
        elif self.is_expired:
            self.close_type = CloseType.TIME_LIMIT
            return True
        elif self.trailing_stop_condition():
            self.close_type = CloseType.TRAILING_STOP
            return True
        elif self.take_profit_condition():
            self.close_type = CloseType.TAKE_PROFIT
            return True
        return False

    def take_profit_condition(self):
        """
        当中间价高于网格的结束价（买入侧）或低于起始价（卖出侧），
        且没有活动的执行器时，触发止盈。
        """
        if self.mid_price > self.config.end_price if self.config.side == TradeType.BUY else self.mid_price < self.config.start_price:
            return True
        return False

    def stop_loss_condition(self):
        """
        此方法负责控制止损。如果净盈亏百分比小于止损百分比，
        则下达平仓订单并取消所有开仓订单。

        :return: 如果达到止损条件，返回True，否则返回False。
        """
        if self.config.triple_barrier_config.stop_loss:
            return self.position_pnl_pct <= -self.config.triple_barrier_config.stop_loss
        return False

    def limit_price_condition(self):
        """
        此方法负责控制限价。如果当前价格超过限价，
        则下达平仓订单并取消所有开仓订单。

        :return: 如果达到限价条件，返回True，否则返回False。
        """
        if self.config.limit_price:
            if self.config.side == TradeType.BUY:
                return self.mid_price <= self.config.limit_price
            else:
                return self.mid_price >= self.config.limit_price
        return False

    def trailing_stop_condition(self):
        """
        控制跟踪止损的逻辑。
        :return: 如果触发跟踪止损，返回True。
        """
        if self.config.triple_barrier_config.trailing_stop:
            net_pnl_pct = self.position_pnl_pct
            if not self._trailing_stop_trigger_pct:
                if net_pnl_pct > self.config.triple_barrier_config.trailing_stop.activation_price:
                    self._trailing_stop_trigger_pct = net_pnl_pct - self.config.triple_barrier_config.trailing_stop.trailing_delta
            else:
                if net_pnl_pct < self._trailing_stop_trigger_pct:
                    return True
                if net_pnl_pct - self.config.triple_barrier_config.trailing_stop.trailing_delta > self._trailing_stop_trigger_pct:
                    self._trailing_stop_trigger_pct = net_pnl_pct - self.config.triple_barrier_config.trailing_stop.trailing_delta
        return False

    def place_close_order_and_cancel_open_orders(self, close_type: CloseType, price: Decimal = Decimal("NaN")):
        """
        此方法负责下达平仓订单并取消所有开仓订单。如果开仓已成交金额
        与平仓已成交金额之差大于最小订单大小，则下达平仓订单。
        同时它也会取消所有开仓订单。

        :param close_type: 平仓订单的类型。
        :param price: 用于平仓订单的价格。
        :return: None
        """
        self.cancel_open_orders()
        if self.position_size_base >= self.trading_rules.min_order_size:
            order_id = self.place_order(
                connector_name=self.config.connector_name,
                trading_pair=self.config.trading_pair,
                order_type=OrderType.MARKET,
                amount=self.position_size_base,
                price=price,
                side=self.close_order_side,
                position_action=PositionAction.CLOSE,
            )
            self._close_order = TrackedOrder(order_id=order_id)
            self.logger().debug(f"Executor ID: {self.config.id} - Placing close order {order_id}")
        self.close_type = close_type
        self._status = RunnableStatus.SHUTTING_DOWN

    def cancel_open_orders(self):
        """
        此方法负责取消所有开仓订单。

        :return: None
        """
        open_order_placed = [level.active_open_order for level in
                             self.levels_by_state[GridLevelStates.OPEN_ORDER_PLACED]]
        close_order_placed = [level.active_close_order for level in
                              self.levels_by_state[GridLevelStates.CLOSE_ORDER_PLACED]]
        for order in open_order_placed + close_order_placed:
            # TODO: Implement cancel batch orders
            if order:
                self._strategy.cancel(
                    connector_name=self.config.connector_name,
                    trading_pair=self.config.trading_pair,
                    order_id=order.order_id
                )
                self.logger().debug("Removing open order")
                self.logger().debug(f"Executor ID: {self.config.id} - Canceling open order {order.order_id}")

    def get_custom_info(self) -> Dict:
        """
        获取自定义信息字典，用于UI展示或API输出。
        :return: 包含执行器状态的字典。
        """
        held_position_value = sum([
            Decimal(order["executed_amount_quote"])
            for order in self._held_position_orders
        ])

        return {
            "levels_by_state": {key.name: value for key, value in self.levels_by_state.items()},
            "filled_orders": self._filled_orders,
            "held_position_orders": self._held_position_orders,
            "held_position_value": held_position_value,
            "failed_orders": self._failed_orders,
            "canceled_orders": self._canceled_orders,
            "realized_buy_size_quote": self.realized_buy_size_quote,
            "realized_sell_size_quote": self.realized_sell_size_quote,
            "realized_imbalance_quote": self.realized_imbalance_quote,
            "realized_fees_quote": self.realized_fees_quote,
            "realized_pnl_quote": self.realized_pnl_quote,
            "realized_pnl_pct": self.realized_pnl_pct,
            "position_size_quote": self.position_size_quote,
            "position_fees_quote": self.position_fees_quote,
            "break_even_price": self.position_break_even_price,
            "position_pnl_quote": self.position_pnl_quote,
            "open_liquidity_placed": self.open_liquidity_placed,
            "close_liquidity_placed": self.close_liquidity_placed,
        }

    async def on_start(self):
        """
        此方法负责启动执行器并验证持仓是否已过期。基类方法会
        验证是否有足够余额来下达开仓订单。

        :return: None
        """
        await super().on_start()
        self.update_metrics()
        if self.control_triple_barrier():
            self.logger().error(f"Grid is already expired by {self.close_type}.")

            self._status = RunnableStatus.SHUTTING_DOWN

    def evaluate_max_retries(self):
        """
        此方法负责评估下单的最大重试次数，并在达到最大次数时停止执行器。

        :return: None
        """
        if self._current_retries > self._max_retries:
            self.close_type = CloseType.FAILED
            self.stop()

    def update_tracked_orders_with_order_id(self, order_id: str):
        """
        此方法负责使用 order_id 作为参考，通过 InFlightOrder 的信息更新被跟踪的订单。

        :param order_id: 用作参考的 order_id。
        :return: None
        """
        self.update_grid_levels()
        in_flight_order = self.get_in_flight_order(self.config.connector_name, order_id)
        if in_flight_order:
            for level in self.grid_levels:
                if level.active_open_order and level.active_open_order.order_id == order_id:
                    level.active_open_order.order = in_flight_order
                if level.active_close_order and level.active_close_order.order_id == order_id:
                    level.active_close_order.order = in_flight_order
            if self._close_order and self._close_order.order_id == order_id:
                self._close_order.order = in_flight_order

    def process_order_created_event(self, _, market, event: Union[BuyOrderCreatedEvent, SellOrderCreatedEvent]):
        """
        此方法负责处理订单创建事件。在这里，我们将使用 order_id 更新 TrackedOrder。
        """
        self.update_tracked_orders_with_order_id(event.order_id)

    def process_order_filled_event(self, _, market, event: OrderFilledEvent):
        """
        此方法负责处理订单成交事件。在这里，我们将更新
        _total_executed_amount_backup 的值，以便在 InFlightOrder
        不可用时使用。
        """
        self.update_tracked_orders_with_order_id(event.order_id)

    def process_order_completed_event(self, _, market, event: Union[BuyOrderCompletedEvent, SellOrderCompletedEvent]):
        """
        此方法负责处理订单完成事件。在这里，我们将检查 ID 是否为
        被跟踪的订单之一，并更新其状态。
        """
        self.update_tracked_orders_with_order_id(event.order_id)

    def process_order_canceled_event(self, _, market: ConnectorBase, event: OrderCancelledEvent):
        """
        此方法负责处理订单取消事件。
        """
        self.update_grid_levels()
        levels_open_order_placed = [level for level in self.levels_by_state[GridLevelStates.OPEN_ORDER_PLACED]]
        levels_close_order_placed = [level for level in self.levels_by_state[GridLevelStates.CLOSE_ORDER_PLACED]]
        for level in levels_open_order_placed:
            if event.order_id == level.active_open_order.order_id:
                self._canceled_orders.append(level.active_open_order.order_id)
                self.max_open_creation_timestamp = 0
                level.reset_open_order()
        for level in levels_close_order_placed:
            if event.order_id == level.active_close_order.order_id:
                self._canceled_orders.append(level.active_close_order.order_id)
                self.max_close_creation_timestamp = 0
                level.reset_close_order()
        if self._close_order and event.order_id == self._close_order.order_id:
            self._canceled_orders.append(self._close_order.order_id)
            self._close_order = None

    def process_order_failed_event(self, _, market, event: MarketOrderFailureEvent):
        """
        此方法负责处理订单失败事件。在这里，我们将把 InFlightOrder 添加到失败订单列表中。
        """
        self.update_grid_levels()
        levels_open_order_placed = [level for level in self.levels_by_state[GridLevelStates.OPEN_ORDER_PLACED]]
        levels_close_order_placed = [level for level in self.levels_by_state[GridLevelStates.CLOSE_ORDER_PLACED]]
        for level in levels_open_order_placed:
            if event.order_id == level.active_open_order.order_id:
                self._failed_orders.append(level.active_open_order.order_id)
                self.max_open_creation_timestamp = 0
                level.reset_open_order()
        for level in levels_close_order_placed:
            if event.order_id == level.active_close_order.order_id:
                self._failed_orders.append(level.active_close_order.order_id)
                self.max_close_creation_timestamp = 0
                level.reset_close_order()
        if self._close_order and event.order_id == self._close_order.order_id:
            self._failed_orders.append(self._close_order.order_id)
            self._close_order = None

    def update_position_metrics(self):
        """
        计算未实现盈亏（以计价资产为单位）

        :return: 未实现盈亏（以计价资产为单位）。
        """
        open_filled_levels = self.levels_by_state[GridLevelStates.OPEN_ORDER_FILLED] + self.levels_by_state[
            GridLevelStates.CLOSE_ORDER_PLACED]
        side_multiplier = 1 if self.config.side == TradeType.BUY else -1
        executed_amount_base = Decimal(sum([level.active_open_order.order.amount for level in open_filled_levels]))
        if executed_amount_base == Decimal("0"):
            self.position_size_base = Decimal("0")
            self.position_size_quote = Decimal("0")
            self.position_fees_quote = Decimal("0")
            self.position_pnl_quote = Decimal("0")
            self.position_pnl_pct = Decimal("0")
            self.close_liquidity_placed = Decimal("0")
        else:
            self.position_break_even_price = sum(
                [level.active_open_order.order.price * level.active_open_order.order.amount
                 for level in open_filled_levels]) / executed_amount_base
            if self._open_fee_in_base:
                executed_amount_base -= sum([level.active_open_order.cum_fees_base for level in open_filled_levels])
            close_order_size_base = self._close_order.executed_amount_base if self._close_order and self._close_order.is_done else Decimal(
                "0")
            self.position_size_base = executed_amount_base - close_order_size_base
            self.position_size_quote = self.position_size_base * self.position_break_even_price
            self.position_fees_quote = Decimal(sum([level.active_open_order.cum_fees_quote for level in open_filled_levels]))
            self.position_pnl_quote = side_multiplier * ((self.mid_price - self.position_break_even_price) / self.position_break_even_price) * self.position_size_quote - self.position_fees_quote
            self.position_pnl_pct = self.position_pnl_quote / self.position_size_quote if self.position_size_quote > 0 else Decimal(
                "0")
            self.close_liquidity_placed = sum([level.amount_quote for level in self.levels_by_state[GridLevelStates.CLOSE_ORDER_PLACED] if level.active_close_order and level.active_close_order.executed_amount_base == Decimal("0")])
        if len(self.levels_by_state[GridLevelStates.OPEN_ORDER_PLACED]) > 0:
            self.open_liquidity_placed = sum([level.amount_quote for level in self.levels_by_state[GridLevelStates.OPEN_ORDER_PLACED] if level.active_open_order and level.active_open_order.executed_amount_base == Decimal("0")])
        else:
            self.open_liquidity_placed = Decimal("0")

    def update_realized_pnl_metrics(self):
        """
        计算已实现盈亏（以计价资产为单位，不包括持仓）
        """
        if len(self._filled_orders) == 0:
            self._reset_metrics()
            return
        # 仅计算已完全平仓的交易的指标（不包括持仓）
        regular_filled_orders = [order for order in self._filled_orders
                                 if order not in self._held_position_orders]
        if len(regular_filled_orders) == 0:
            self._reset_metrics()
            return
        if self._open_fee_in_base:
            self.realized_buy_size_quote = sum([
                Decimal(order["executed_amount_quote"]) - Decimal(order["cumulative_fee_paid_quote"])
                for order in regular_filled_orders if order["trade_type"] == TradeType.BUY.name
            ])
        else:
            self.realized_buy_size_quote = sum([
                Decimal(order["executed_amount_quote"])
                for order in regular_filled_orders if order["trade_type"] == TradeType.BUY.name
            ])
        self.realized_sell_size_quote = sum([
            Decimal(order["executed_amount_quote"])
            for order in regular_filled_orders if order["trade_type"] == TradeType.SELL.name
        ])
        self.realized_imbalance_quote = self.realized_buy_size_quote - self.realized_sell_size_quote
        self.realized_fees_quote = sum([
            Decimal(order["cumulative_fee_paid_quote"])
            for order in regular_filled_orders
        ])
        self.realized_pnl_quote = (
            self.realized_sell_size_quote -
            self.realized_buy_size_quote -
            self.realized_fees_quote
        )
        self.realized_pnl_pct = (
            self.realized_pnl_quote / self.realized_buy_size_quote
            if self.realized_buy_size_quote > 0 else Decimal("0")
        )

    def _reset_metrics(self):
        """辅助方法，用于重置所有盈亏指标"""
        self.realized_buy_size_quote = Decimal("0")
        self.realized_sell_size_quote = Decimal("0")
        self.realized_imbalance_quote = Decimal("0")
        self.realized_fees_quote = Decimal("0")
        self.realized_pnl_quote = Decimal("0")
        self.realized_pnl_pct = Decimal("0")

    def get_net_pnl_quote(self) -> Decimal:
        """
        计算净盈亏（以计价资产为单位）

        :return: 净盈亏（以计价资产为单位）。
        """
        return self.position_pnl_quote + self.realized_pnl_quote if self.close_type != CloseType.POSITION_HOLD else self.realized_pnl_quote

    def get_cum_fees_quote(self) -> Decimal:
        """
        计算累计手续费（以计价资产为单位）

        :return: 累计手续费（以计价资产为单位）。
        """
        return self.position_fees_quote + self.realized_fees_quote if self.close_type != CloseType.POSITION_HOLD else self.realized_fees_quote

    @property
    def filled_amount_quote(self) -> Decimal:
        """
        计算总金额（以计价资产为单位）

        :return: 总金额（以计价资产为单位）。
        """
        matched_volume = self.realized_buy_size_quote + self.realized_sell_size_quote
        return self.position_size_quote + matched_volume if self.close_type != CloseType.POSITION_HOLD else matched_volume

    def get_net_pnl_pct(self) -> Decimal:
        """
        计算净盈亏百分比

        :return: 净盈亏百分比。
        """
        return self.get_net_pnl_quote() / self.filled_amount_quote if self.filled_amount_quote > 0 else Decimal("0")

    async def _sleep(self, delay: float):
        """
        此方法负责让执行器休眠一段时间。

        :param delay: 休眠时间。
        :return: None
        """
        await asyncio.sleep(delay)
