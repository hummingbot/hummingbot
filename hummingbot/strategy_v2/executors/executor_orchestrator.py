import asyncio
import logging
import uuid
from collections import deque
from decimal import Decimal
from typing import TYPE_CHECKING, Dict, List, Optional

from hummingbot.connector.markets_recorder import MarketsRecorder
from hummingbot.core.data_type.common import PositionAction, PositionMode, PriceType, TradeType
from hummingbot.logger import HummingbotLogger
from hummingbot.model.position import Position

if TYPE_CHECKING:
    from hummingbot.strategy.strategy_v2_base import StrategyV2Base

from hummingbot.strategy_v2.executors.arbitrage_executor.arbitrage_executor import ArbitrageExecutor
from hummingbot.strategy_v2.executors.data_types import PositionSummary
from hummingbot.strategy_v2.executors.dca_executor.dca_executor import DCAExecutor
from hummingbot.strategy_v2.executors.grid_executor.grid_executor import GridExecutor
from hummingbot.strategy_v2.executors.lp_executor.lp_executor import LPExecutor
from hummingbot.strategy_v2.executors.order_executor.order_executor import OrderExecutor
from hummingbot.strategy_v2.executors.position_executor.position_executor import PositionExecutor
from hummingbot.strategy_v2.executors.twap_executor.twap_executor import TWAPExecutor
from hummingbot.strategy_v2.executors.xemm_executor.xemm_executor import XEMMExecutor
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executor_actions import (
    CreateExecutorAction,
    ExecutorAction,
    StopExecutorAction,
    StoreExecutorAction,
)
from hummingbot.strategy_v2.models.executors import CloseType
from hummingbot.strategy_v2.models.executors_info import ExecutorInfo, PerformanceReport


class PositionHold:
    def __init__(self, connector_name: str, trading_pair: str, side: TradeType = None):
        self.connector_name = connector_name
        self.trading_pair = trading_pair
        self.side = side
        # Store only client order IDs
        self.order_ids = set()

        # Net position tracking (positive = long, negative = short)
        self.net_amount_base = Decimal("0")
        self.avg_entry_price = Decimal("0")

        # Accumulated metrics
        self.realized_pnl_quote = Decimal("0")
        self.volume_traded_quote = Decimal("0")
        self.cum_fees_quote = Decimal("0")

        # Separate tracking for buys and sells (for logging/diagnostics)
        self.buy_amount_base = Decimal("0")
        self.buy_amount_quote = Decimal("0")
        self.sell_amount_base = Decimal("0")
        self.sell_amount_quote = Decimal("0")

    def _process_order(self, is_buy: bool, amount_base: Decimal, amount_quote: Decimal):
        """
        Process an order incrementally: realize PnL when reducing position,
        update avg_entry_price when adding to position.
        """
        if amount_base == 0:
            return

        order_price = amount_quote / amount_base
        is_reducing = (self.net_amount_base > 0 and not is_buy) or (self.net_amount_base < 0 and is_buy)

        if is_reducing:
            abs_net = abs(self.net_amount_base)
            matched = min(amount_base, abs_net)

            # Realize PnL on matched portion
            if self.net_amount_base > 0:
                self.realized_pnl_quote += (order_price - self.avg_entry_price) * matched
            else:
                self.realized_pnl_quote += (self.avg_entry_price - order_price) * matched

            excess = amount_base - matched
            if excess > 0:
                # Position flipped to opposite side
                self.net_amount_base = excess if is_buy else -excess
                self.avg_entry_price = order_price
            elif matched == abs_net:
                # Position fully closed
                self.net_amount_base = Decimal("0")
                self.avg_entry_price = Decimal("0")
            else:
                # Position partially reduced, avg_entry_price stays the same
                if self.net_amount_base > 0:
                    self.net_amount_base -= matched
                else:
                    self.net_amount_base += matched
        else:
            # Adding to position or first order
            if self.net_amount_base == 0:
                self.net_amount_base = amount_base if is_buy else -amount_base
                self.avg_entry_price = order_price
            else:
                abs_net = abs(self.net_amount_base)
                total_cost = self.avg_entry_price * abs_net + amount_quote
                new_abs = abs_net + amount_base
                self.avg_entry_price = total_cost / new_abs
                self.net_amount_base = new_abs if is_buy else -new_abs

    def add_orders_from_executor(self, executor: ExecutorInfo):
        custom_info = executor.custom_info
        if "held_position_orders" not in custom_info or len(custom_info["held_position_orders"]) == 0:
            logging.getLogger(__name__).warning(
                f"PositionHold.add_orders: executor {executor.id[:8]} has no held_position_orders. "
                f"close_type={executor.close_type} side={executor.config.side} "
                f"level_id={custom_info.get('level_id', 'N/A')}"
            )
            return

        for order in custom_info["held_position_orders"]:
            # Skip if we've already processed this order
            order_id = order.get("client_order_id")
            if order_id in self.order_ids:
                logging.getLogger(__name__).debug(
                    f"PositionHold.add_orders: skipping duplicate order {order_id}"
                )
                continue

            # Add the order ID to our set
            self.order_ids.add(order_id)

            # Update metrics incrementally
            executed_amount_base = Decimal(str(order.get("executed_amount_base", 0)))
            executed_amount_quote = Decimal(str(order.get("executed_amount_quote", 0)))

            is_buy = order.get("trade_type") == "BUY"
            order_type_label = order.get("order_type", "N/A")
            position_action = order.get("position", "N/A")

            # Snapshot before
            prev_net = self.net_amount_base

            # Update volume traded in quote
            self.volume_traded_quote += executed_amount_quote

            # Update buy/sell totals (for logging/diagnostics)
            if is_buy:
                self.buy_amount_base += executed_amount_base
                self.buy_amount_quote += executed_amount_quote
            else:
                self.sell_amount_base += executed_amount_base
                self.sell_amount_quote += executed_amount_quote

            # Update fees (tx fees paid)
            self.cum_fees_quote += Decimal(str(order.get("cumulative_fee_paid_quote", 0)))

            # Process order for incremental PnL calculation
            self._process_order(is_buy, executed_amount_base, executed_amount_quote)

            logging.getLogger(__name__).debug(
                f"PositionHold.add_orders: {self.trading_pair} | "
                f"order={order_id[:12] if order_id else 'N/A'} | "
                f"trade_type={'BUY' if is_buy else 'SELL'} | "
                f"order_type={order_type_label} | position_action={position_action} | "
                f"amount_base={executed_amount_base} amount_quote={executed_amount_quote:.2f} | "
                f"executor_side={executor.config.side} level={custom_info.get('level_id', 'N/A')} | "
                f"net_before={prev_net} -> net_after={self.net_amount_base} | "
                f"avg_entry={self.avg_entry_price:.4f} realized_pnl={self.realized_pnl_quote:.4f} | "
                f"buy_total={self.buy_amount_base} sell_total={self.sell_amount_base}"
            )

    def get_position_summary(self, mid_price: Decimal):
        abs_amount = abs(self.net_amount_base)
        is_net_long = self.net_amount_base >= 0

        # Calculate unrealized PnL for remaining open position
        unrealized_pnl_quote = Decimal("0")
        if abs_amount > 0:
            if is_net_long:
                unrealized_pnl_quote = (mid_price - self.avg_entry_price) * abs_amount
            else:
                unrealized_pnl_quote = (self.avg_entry_price - mid_price) * abs_amount

        summary = PositionSummary(
            connector_name=self.connector_name,
            trading_pair=self.trading_pair,
            volume_traded_quote=self.volume_traded_quote,
            amount=abs_amount,
            side=TradeType.BUY if is_net_long else TradeType.SELL,
            breakeven_price=self.avg_entry_price,
            unrealized_pnl_quote=unrealized_pnl_quote,
            realized_pnl_quote=self.realized_pnl_quote,
            cum_fees_quote=self.cum_fees_quote)

        logging.getLogger(__name__).debug(
            f"PositionHold.summary: {self.trading_pair} | "
            f"net={'LONG' if is_net_long else 'SHORT'} {abs_amount} @ entry={self.avg_entry_price:.4f} | "
            f"unrealized_pnl={unrealized_pnl_quote:.4f} realized_pnl={self.realized_pnl_quote:.4f} | "
            f"mid_price={mid_price:.4f} orders={len(self.order_ids)}"
        )
        return summary


class ExecutorOrchestrator:
    """
    Orchestrator for various executors.
    """
    _logger = None
    _executor_mapping = {
        "position_executor": PositionExecutor,
        "grid_executor": GridExecutor,
        "dca_executor": DCAExecutor,
        "arbitrage_executor": ArbitrageExecutor,
        "twap_executor": TWAPExecutor,
        "xemm_executor": XEMMExecutor,
        "order_executor": OrderExecutor,
        "lp_executor": LPExecutor,
    }

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self,
                 strategy: "StrategyV2Base",
                 executors_update_interval: float = 1.0,
                 executors_max_retries: int = 10,
                 initial_positions_by_controller: Optional[dict] = None):
        self.strategy = strategy
        self.executors_update_interval = executors_update_interval
        self.executors_max_retries = executors_max_retries
        self.active_executors = {}
        self.recently_terminated_executors: Dict[str, deque] = {}
        self.positions_held = {}
        self.executors_ids_position_held = deque(maxlen=50)
        self.cached_performance = {}
        self.initial_positions_by_controller = initial_positions_by_controller or {}
        self._initial_positions_initialized = False
        self._initialize_cached_performance()

    def _initialize_cached_performance(self):
        """
        Initialize cached performance by querying the database for stored executors and positions.
        If initial positions are provided for a controller, skip loading database positions for that controller.
        """
        for controller_id in self.strategy.controllers.keys():
            if controller_id not in self.cached_performance:
                self.cached_performance[controller_id] = PerformanceReport()
                self.active_executors[controller_id] = []
                self.positions_held[controller_id] = []
        db_executors = MarketsRecorder.get_instance().get_all_executors()
        for executor in db_executors:
            controller_id = executor.controller_id
            if controller_id not in self.strategy.controllers:
                continue
            self._update_cached_performance(controller_id, executor)

        # Load positions from database only for controllers without initial position overrides
        db_positions = MarketsRecorder.get_instance().get_all_positions()
        for position in db_positions:
            controller_id = position.controller_id
            # Skip if this controller has initial position overrides
            if controller_id in self.initial_positions_by_controller or controller_id not in self.strategy.controllers:
                continue
            # Skip if the connector/trading pair is not in the current strategy markets
            if (position.connector_name not in self.strategy.markets or
                    position.trading_pair not in self.strategy.markets.get(position.connector_name, set())):
                self.logger().warning(f"Skipping position for {position.connector_name}.{position.trading_pair} - "
                                      f"not available in current strategy markets")
                continue
            self._load_position_from_db(controller_id, position)

    def _update_cached_performance(self, controller_id: str, executor_info: ExecutorInfo):
        """
        Update the cached performance for a specific controller with an executor's information.
        """
        if controller_id not in self.cached_performance:
            self.cached_performance[controller_id] = PerformanceReport()
        report = self.cached_performance[controller_id]
        # Only add to realized PnL if not a position hold (consistent with generate_performance_report)
        if executor_info.close_type != CloseType.POSITION_HOLD:
            report.realized_pnl_quote += executor_info.net_pnl_quote
            report.volume_traded += executor_info.filled_amount_quote
        if executor_info.close_type:
            report.close_type_counts[executor_info.close_type] = report.close_type_counts.get(executor_info.close_type,
                                                                                              0) + 1

    def _load_position_from_db(self, controller_id: str, db_position: Position):
        """
        Load a position from the database and recreate it as a PositionHold object.
        Since the database only stores net position data, we reconstruct the PositionHold
        with the assumption that it represents the remaining net position.
        """
        # Convert the database position back to a PositionHold object
        side = TradeType.BUY if db_position.side == "BUY" else TradeType.SELL
        position_hold = PositionHold(db_position.connector_name, db_position.trading_pair, side)

        # Set the aggregated values from the database
        position_hold.volume_traded_quote = db_position.volume_traded_quote
        position_hold.cum_fees_quote = db_position.cum_fees_quote

        # Restore net position and avg entry price from database
        if db_position.side == "BUY":
            position_hold.net_amount_base = db_position.amount
            position_hold.buy_amount_base = db_position.amount
            position_hold.buy_amount_quote = db_position.amount * db_position.breakeven_price
        else:
            position_hold.net_amount_base = -db_position.amount
            position_hold.sell_amount_base = db_position.amount
            position_hold.sell_amount_quote = db_position.amount * db_position.breakeven_price
        position_hold.avg_entry_price = db_position.breakeven_price
        # Restore realized PnL if available
        position_hold.realized_pnl_quote = getattr(db_position, 'realized_pnl_quote', Decimal("0"))

        # Add to positions held
        self.positions_held[controller_id].append(position_hold)

    def initialize_initial_positions(self):
        """
        Initialize initial positions from config overrides.
        Must be called after connectors are ready (order books available).
        """
        if self._initial_positions_initialized:
            return
        self._initial_positions_initialized = True
        self._create_initial_positions()

    def _create_initial_positions(self):
        """
        Create initial positions from config overrides.
        Quote amounts are calculated using current mid_price.
        """
        for controller_id, initial_positions in self.initial_positions_by_controller.items():
            if controller_id not in self.cached_performance:
                self.cached_performance[controller_id] = PerformanceReport()
                self.active_executors[controller_id] = []
                self.positions_held[controller_id] = []

            for position_config in initial_positions:
                # Get mid_price for quote amount calculation
                mid_price = self.strategy.market_data_provider.get_price_by_type(
                    position_config.connector_name, position_config.trading_pair, PriceType.MidPrice
                )
                quote_amount = position_config.amount * mid_price

                # Create PositionHold object
                position_hold = PositionHold(
                    position_config.connector_name,
                    position_config.trading_pair,
                    position_config.side
                )

                # Set net position and avg entry price
                if position_config.side == TradeType.BUY:
                    position_hold.net_amount_base = position_config.amount
                    position_hold.buy_amount_base = position_config.amount
                    position_hold.buy_amount_quote = quote_amount
                else:
                    position_hold.net_amount_base = -position_config.amount
                    position_hold.sell_amount_base = position_config.amount
                    position_hold.sell_amount_quote = quote_amount
                position_hold.avg_entry_price = mid_price

                # Add to positions held
                self.positions_held[controller_id].append(position_hold)

                self.logger().info(f"Created initial position for controller {controller_id}: {position_config.amount} "
                                   f"{position_config.side.name} {position_config.trading_pair} on {position_config.connector_name}")

    async def stop(self, max_executors_close_attempts: int = 3):
        """
        Stop the orchestrator task and all active executors.
        """
        # first we stop all active executors
        for controller_id, executors_list in self.active_executors.items():
            for executor in executors_list:
                if not executor.is_closed:
                    executor.early_stop()
        for i in range(max_executors_close_attempts):
            if all([executor.executor_info.is_done for executors_list in self.active_executors.values()
                    for executor in executors_list]):
                break  # All executors are done, exit early
            await asyncio.sleep(2.0)
        # Store all positions and executors
        self.store_all_positions()
        self.store_all_executors()
        # Clear executors and trigger garbage collection
        self.active_executors.clear()

    def store_all_positions(self):
        """
        Store or update all positions in the database.
        """
        markets_recorder = MarketsRecorder.get_instance()
        for controller_id, positions_list in self.positions_held.items():
            if controller_id is None:
                self.logger().warning(f"Skipping {len(positions_list)} position(s) with no controller_id")
                continue
            for position in positions_list:
                # Skip if the connector/trading pair is not in the current strategy markets
                if (position.connector_name not in self.strategy.markets or
                        position.trading_pair not in self.strategy.markets.get(position.connector_name, set())):
                    self.logger().warning(f"Skipping position storage for {position.connector_name}.{position.trading_pair} - "
                                          f"not available in current strategy markets")
                    continue
                mid_price = self.strategy.market_data_provider.get_price_by_type(
                    position.connector_name, position.trading_pair, PriceType.MidPrice)
                position_summary = position.get_position_summary(mid_price if not mid_price.is_nan() else Decimal("0"))

                # Create a Position record (id will only be used for new positions)
                position_record = Position(
                    id=str(uuid.uuid4()),
                    controller_id=controller_id,
                    connector_name=position_summary.connector_name,
                    trading_pair=position_summary.trading_pair,
                    side=position_summary.side.name,
                    timestamp=int(self.strategy.current_timestamp * 1e3),
                    volume_traded_quote=position_summary.volume_traded_quote,
                    amount=position_summary.amount,
                    breakeven_price=position_summary.breakeven_price,
                    unrealized_pnl_quote=position_summary.unrealized_pnl_quote,
                    realized_pnl_quote=position_summary.realized_pnl_quote,
                    cum_fees_quote=position_summary.cum_fees_quote,
                )
                # Store or update the position in the database
                markets_recorder.update_or_store_position(position_record)

        # Clear all positions after storing (avoid modifying list while iterating)
        self.positions_held.clear()

    def store_all_executors(self):
        for controller_id, executors_list in self.active_executors.items():
            for executor in executors_list:
                # Store the executor in the database
                MarketsRecorder.get_instance().store_or_update_executor(executor)
                self._update_cached_performance(controller_id, executor.executor_info)
        # Remove the executors from the list
        self.active_executors = {}

    def execute_action(self, action: ExecutorAction):
        """
        Execute the action and handle executors based on action type.
        """
        controller_id = action.controller_id
        if controller_id is None:
            self.logger().error(f"Received action with controller_id=None: {action}. "
                                "Check that the controller config has a valid 'id' field.")
            return
        if controller_id not in self.cached_performance:
            self.active_executors[controller_id] = []
            self.positions_held[controller_id] = []
            self.cached_performance[controller_id] = PerformanceReport()

        if isinstance(action, CreateExecutorAction):
            self.create_executor(action)
        elif isinstance(action, StopExecutorAction):
            self.stop_executor(action)
        elif isinstance(action, StoreExecutorAction):
            self.store_executor(action)

    def execute_actions(self, actions: List[ExecutorAction]):
        """
        Execute a list of actions.
        """
        for action in actions:
            self.execute_action(action)

    def create_executor(self, action: CreateExecutorAction):
        """
        Create an executor based on the configuration in the action.
        """
        controller_id = action.controller_id
        executor_config = action.executor_config

        # For now, we replace the controller ID in the executor config with the actual controller object to mantain
        # compa
        executor_config.controller_id = controller_id

        executor_class = self._executor_mapping.get(executor_config.type)
        if executor_class is not None:
            executor = executor_class(
                strategy=self.strategy,
                config=executor_config,
                update_interval=self.executors_update_interval,
                max_retries=self.executors_max_retries,
            )
        else:
            raise ValueError("Unsupported executor config type")

        executor.start()
        self.active_executors[controller_id].append(executor)
        # MarketsRecorder.get_instance().store_or_update_executor(executor)
        self.logger().debug(f"Created {type(executor).__name__} for controller {controller_id}")

    def stop_executor(self, action: StopExecutorAction):
        """
        Stop an executor based on the action details.
        """
        controller_id = action.controller_id
        executor_id = action.executor_id

        executor = next(
            (executor for executor in self.active_executors[controller_id] if executor.config.id == executor_id),
            None)
        if not executor:
            self.logger().error(f"Executor ID {executor_id} not found for controller {controller_id}.")
            return
        executor.early_stop(action.keep_position)

    def _auto_store_terminated_executors(self):
        """
        Automatically store terminated executors to the database and move them to a bounded deque
        so strategies can still inspect recently terminated executors for cooldown or pricing logic.
        """
        for controller_id, executors_list in list(self.active_executors.items()):
            stored = []
            for executor in executors_list:
                if executor.status != RunnableStatus.TERMINATED:
                    continue
                try:
                    MarketsRecorder.get_instance().store_or_update_executor(executor)
                    self._update_cached_performance(controller_id, executor.executor_info)
                    stored.append(executor)
                except Exception as e:
                    self.logger().error(f"Error auto-storing terminated executor {executor.config.id}: {str(e)}")
            if controller_id not in self.recently_terminated_executors:
                self.recently_terminated_executors[controller_id] = deque(maxlen=50)
            for executor in stored:
                executors_list.remove(executor)
                self.recently_terminated_executors[controller_id].append(executor)

    def _update_positions_from_done_executors(self):
        """
        Update positions from executors that are done but haven't been processed yet.
        This is called before generating reports to ensure position state is current.
        """
        for controller_id, executors_list in self.active_executors.items():
            # Filter executors that need position updates
            executors_to_process = [
                executor for executor in executors_list
                if (executor.executor_info.is_done and
                    executor.executor_info.close_type == CloseType.POSITION_HOLD and
                    executor.executor_info.config.id not in self.executors_ids_position_held)
            ]

            # Skip if no executors to process
            if not executors_to_process:
                continue

            positions = self.positions_held.get(controller_id, [])

            for executor in executors_to_process:
                executor_info = executor.executor_info
                self.executors_ids_position_held.append(executor_info.config.id)

                # Determine position side (handling perpetual markets)
                position_side = self._determine_position_side(executor_info)

                held_orders = executor_info.custom_info.get("held_position_orders", [])
                held_summary = [
                    f"{o.get('trade_type')}:{o.get('executed_amount_base')}@{o.get('position', 'N/A')}"
                    for o in held_orders
                ]

                self.logger().debug(
                    f"Processing POSITION_HOLD executor: {executor_info.id[:8]} | "
                    f"controller={controller_id} | side={executor_info.config.side} | "
                    f"level={executor_info.custom_info.get('level_id', 'N/A')} | "
                    f"position_side_resolved={position_side} | "
                    f"held_orders({len(held_orders)}): {held_summary} | "
                    f"existing_positions={len(positions)}"
                )

                # Find or create position
                existing_position = self._find_existing_position(positions, executor_info, position_side)

                if existing_position:
                    existing_position.add_orders_from_executor(executor_info)
                    self.logger().debug(
                        f"Merged executor {executor_info.id[:8]} into existing position: "
                        f"net={existing_position.net_amount_base} avg_entry={existing_position.avg_entry_price:.4f}"
                    )
                else:
                    # Create new position (handles both spot/perp and LP)
                    assigned_side = position_side
                    self.logger().debug(
                        f"Creating new PositionHold for executor {executor_info.id[:8]} with side={assigned_side}"
                    )
                    position = PositionHold(
                        executor_info.connector_name,
                        executor_info.trading_pair,
                        assigned_side
                    )
                    position.add_orders_from_executor(executor_info)
                    positions.append(position)

    def _determine_position_side(self, executor_info: ExecutorInfo) -> Optional[TradeType]:
        """
        Determine the position side used to bucket a position hold.

        Only perpetual markets in HEDGE mode can hold a long and a short position
        simultaneously, so only in that case do we return a specific side (allowing
        a separate long and short position hold per trading pair). For spot markets
        and perpetual markets in ONEWAY mode there can only be a single net position
        per trading pair, so we return None and let all activity merge into one
        PositionHold (whose net direction is derived from its buy/sell amounts).
        """
        is_perpetual = "_perpetual" in executor_info.connector_name
        if not is_perpetual:
            return None

        market = self.strategy.connectors.get(executor_info.connector_name)
        if not market or not hasattr(market, 'position_mode'):
            return None

        position_mode = market.position_mode
        if hasattr(executor_info.config, "position_action") and position_mode == PositionMode.HEDGE:
            opposite_side = TradeType.BUY if executor_info.config.side == TradeType.SELL else TradeType.SELL
            return opposite_side if executor_info.config.position_action == PositionAction.CLOSE else executor_info.config.side

        # Spot or perpetual ONEWAY: a single net position per trading pair (one side at a time).
        return None

    def _find_existing_position(self, positions: List[PositionHold],
                                executor_info: ExecutorInfo,
                                position_side: Optional[TradeType]) -> Optional[PositionHold]:
        """
        Find an existing position that matches the executor's trading pair and side.
        """
        for position in positions:
            if (position.trading_pair == executor_info.trading_pair and
                    position.connector_name == executor_info.connector_name):

                # If we have a specific position side, match it
                if position_side is not None:
                    if position.side == position_side:
                        return position
                else:
                    # No specific side requirement, return first match
                    return position

        return None

    def store_executor(self, action: StoreExecutorAction):
        """
        Store executor data based on the action details and update cached performance.
        """
        controller_id = action.controller_id
        executor_id = action.executor_id

        executor = next(
            (executor for executor in self.active_executors[controller_id] if executor.config.id == executor_id),
            None)
        if not executor:
            self.logger().error(f"Executor ID {executor_id} not found for controller {controller_id}.")
            return
        if executor.is_active:
            self.logger().error(f"Executor ID {executor_id} is still active.")
            return
        try:
            MarketsRecorder.get_instance().store_or_update_executor(executor)
            self._update_cached_performance(controller_id, executor.executor_info)
        except Exception as e:
            self.logger().error(f"Error storing executor id {executor_id}: {str(e)}.")
            self.logger().error(f"Executor info: {executor.executor_info} | Config: {executor.config}")

        self.active_executors[controller_id].remove(executor)
        del executor
        # Trigger garbage collection after executor cleanup

    def get_executors_report(self) -> Dict[str, List[ExecutorInfo]]:
        """
        Generate a report of all executors, including recently terminated ones from the deque.
        """
        report = {}
        for controller_id, executors_list in self.active_executors.items():
            active = [executor.executor_info for executor in executors_list if executor]
            recent = [executor.executor_info for executor in
                      self.recently_terminated_executors.get(controller_id, [])]
            report[controller_id] = active + recent
        return report

    def get_positions_report(self) -> Dict[str, List[PositionSummary]]:
        """
        Generate a report of all positions held.
        """
        report = {}
        for controller_id, positions_list in self.positions_held.items():
            positions_summary = []
            for position in positions_list:
                mid_price = self.strategy.market_data_provider.get_price_by_type(
                    position.connector_name, position.trading_pair, PriceType.MidPrice)
                positions_summary.append(position.get_position_summary(mid_price if not mid_price.is_nan() else Decimal("0")))
            report[controller_id] = positions_summary
        return report

    def get_all_reports(self) -> Dict[str, Dict]:
        """
        Generate a unified report containing executors, positions, and performance for all controllers.
        Returns a dictionary with controller_id as key and a dict containing all reports as value.
        """
        # Update any pending position holds from done executors
        self._update_positions_from_done_executors()

        # Auto-store terminated executors to the database
        self._auto_store_terminated_executors()

        # Generate all reports
        executors_report = self.get_executors_report()
        positions_report = self.get_positions_report()

        # Get all controller IDs
        all_controller_ids = set(list(self.active_executors.keys()) +
                                 list(self.recently_terminated_executors.keys()) +
                                 list(self.positions_held.keys()) +
                                 list(self.cached_performance.keys()))

        # Use dict comprehension to compile reports for each controller
        return {
            controller_id: {
                "executors": executors_report.get(controller_id, []),
                "positions": positions_report.get(controller_id, []),
                "performance": self.generate_performance_report(controller_id)
            }
            for controller_id in all_controller_ids
        }

    def generate_performance_report(self, controller_id: str) -> PerformanceReport:
        # Create a new report starting from cached base values
        report = PerformanceReport()
        cached_report = self.cached_performance.get(controller_id, PerformanceReport())

        # Start with cached values (from DB)
        report.realized_pnl_quote = cached_report.realized_pnl_quote
        report.volume_traded = cached_report.volume_traded
        report.close_type_counts = cached_report.close_type_counts.copy() if cached_report.close_type_counts else {}

        # Add data from active executors
        active_executors = self.active_executors.get(controller_id, [])
        positions = self.positions_held.get(controller_id, [])

        for executor in active_executors:
            executor_info = executor.executor_info
            if not executor_info.is_done:
                report.unrealized_pnl_quote += executor_info.net_pnl_quote
                report.volume_traded += executor_info.filled_amount_quote
            else:
                # For done executors, only add to realized PnL if they're not already in position holds
                # Position holds will be counted separately to avoid double counting
                if executor_info.close_type != CloseType.POSITION_HOLD:
                    report.realized_pnl_quote += executor_info.net_pnl_quote
                    report.volume_traded += executor_info.filled_amount_quote
                if executor_info.close_type:
                    report.close_type_counts[executor_info.close_type] = report.close_type_counts.get(executor_info.close_type, 0) + 1

        # Add data from positions held and collect position summaries
        positions_summary = []
        for position in positions:
            # Skip if the connector/trading pair is not in the current strategy markets
            if (position.connector_name not in self.strategy.markets or
                    position.trading_pair not in self.strategy.markets.get(position.connector_name, set())):
                self.logger().warning(f"Skipping position in performance report for {position.connector_name}.{position.trading_pair} - "
                                      f"not available in current strategy markets")
                continue
            mid_price = self.strategy.market_data_provider.get_price_by_type(
                position.connector_name, position.trading_pair, PriceType.MidPrice)
            position_summary = position.get_position_summary(mid_price if not mid_price.is_nan() else Decimal("0"))

            # Update report with position data
            # Position summary realized_pnl_quote is already net of fees (calculated correctly in position logic)
            report.realized_pnl_quote += position_summary.realized_pnl_quote
            report.volume_traded += position_summary.volume_traded_quote
            report.unrealized_pnl_quote += position_summary.unrealized_pnl_quote
            positions_summary.append(position_summary)

        # Set the positions summary (don't use dynamic attribute)
        report.positions_summary = positions_summary

        # Calculate global PNL values
        report.global_pnl_quote = report.unrealized_pnl_quote + report.realized_pnl_quote
        report.global_pnl_pct = (report.global_pnl_quote / report.volume_traded) * 100 if report.volume_traded != 0 else Decimal(0)

        # Calculate individual PNL percentages
        report.unrealized_pnl_pct = (report.unrealized_pnl_quote / report.volume_traded) * 100 if report.volume_traded != 0 else Decimal(0)
        report.realized_pnl_pct = (report.realized_pnl_quote / report.volume_traded) * 100 if report.volume_traded != 0 else Decimal(0)

        return report
