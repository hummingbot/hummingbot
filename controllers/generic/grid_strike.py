from decimal import Decimal
from typing import Dict, List, Optional, Set

from pydantic import BaseModel, Field

from hummingbot.client.config.config_data_types import ClientFieldData
from hummingbot.core.data_type.common import OrderType, PositionMode, PriceType, TradeType
from hummingbot.core.data_type.trade_fee import TokenAmount
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy_v2.controllers import ControllerBase, ControllerConfigBase
from hummingbot.strategy_v2.executors.position_executor.data_types import PositionExecutorConfig, TripleBarrierConfig
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, ExecutorAction, StopExecutorAction
from hummingbot.strategy_v2.models.executors_info import ExecutorInfo
from hummingbot.strategy_v2.utils.distributions import Distributions


class GridRange(BaseModel):
    id: str
    start_price: Decimal
    end_price: Decimal
    total_amount_pct: Decimal
    side: TradeType = TradeType.BUY
    open_order_type: OrderType = OrderType.LIMIT_MAKER
    take_profit_order_type: OrderType = OrderType.LIMIT
    active: bool = True


class GridStrikeConfig(ControllerConfigBase):
    """
    Configuration required to run the GridStrike strategy for one connector and trading pair.
    """
    controller_name: str = "grid_strike"
    candles_config: List[CandlesConfig] = []
    controller_type = "generic"
    connector_name: str = "binance"
    trading_pair: str = "BTC-USDT"
    total_amount_quote: Decimal = Field(default=Decimal("1000"), client_data=ClientFieldData(is_updatable=True))
    grid_ranges: List[GridRange] = Field(default=[GridRange(id="R0", start_price=Decimal("40000"),
                                                            end_price=Decimal("60000"),
                                                            total_amount_pct=Decimal("0.1"))],
                                         client_data=ClientFieldData(is_updatable=True))
    position_mode: PositionMode = PositionMode.HEDGE
    leverage: int = 1
    time_limit: Optional[int] = Field(default=60 * 60 * 24 * 2, client_data=ClientFieldData(is_updatable=True))
    activation_bounds: Decimal = Field(default=Decimal("0.01"), client_data=ClientFieldData(is_updatable=True))
    min_spread_between_orders: Optional[Decimal] = Field(default=None,
                                                         client_data=ClientFieldData(is_updatable=True))
    min_order_amount: Optional[Decimal] = Field(default=Decimal("1"),
                                                client_data=ClientFieldData(is_updatable=True))
    max_open_orders: int = Field(default=5, client_data=ClientFieldData(is_updatable=True))
    grid_range_update_interval: int = Field(default=60, client_data=ClientFieldData(is_updatable=True))
    extra_balance_base_usd: Decimal = Decimal("10")

    def update_markets(self, markets: Dict[str, Set[str]]) -> Dict[str, Set[str]]:
        if self.connector_name not in markets:
            markets[self.connector_name] = set()
        markets[self.connector_name].add(self.trading_pair)
        return markets


class GridLevel(BaseModel):
    id: str
    price: Decimal
    amount: Decimal
    step: Decimal
    side: TradeType
    open_order_type: OrderType
    take_profit_order_type: OrderType


class GridStrike(ControllerBase):
    def __init__(self, config: GridStrikeConfig, *args, **kwargs):
        super().__init__(config, *args, **kwargs)
        self.config = config
        self._last_grid_levels_update = 0
        self.trading_rules = None
        self.grid_levels = []

    def _calculate_grid_config(self):
        self.trading_rules = self.market_data_provider.get_trading_rules(self.config.connector_name,
                                                                         self.config.trading_pair)
        grid_levels = []
        if self.config.min_spread_between_orders:
            spread_between_orders = self.config.min_spread_between_orders * self.get_mid_price()
            step_proposed = max(self.trading_rules.min_price_increment, spread_between_orders)
        else:
            step_proposed = self.trading_rules.min_price_increment
        amount_proposed = max(self.trading_rules.min_notional_size, self.config.min_order_amount) if \
            self.config.min_order_amount else self.trading_rules.min_order_size
        for grid_range in self.config.grid_ranges:
            if grid_range.active:
                total_amount = grid_range.total_amount_pct * self.config.total_amount_quote
                theoretical_orders_by_step = (grid_range.end_price - grid_range.start_price) / step_proposed
                theoretical_orders_by_amount = total_amount / amount_proposed
                orders = int(min(theoretical_orders_by_step, theoretical_orders_by_amount))
                prices = Distributions.linear(orders, float(grid_range.start_price), float(grid_range.end_price))
                step = (grid_range.end_price - grid_range.start_price) / grid_range.end_price / orders
                if orders == 0:
                    self.logger().warning(f"Grid range {grid_range.id} has no orders, change the parameters "
                                          f"(min order amount, amount pct, min spread between orders or total amount)")
                amount_quote = total_amount / orders
                for i, price in enumerate(prices):
                    price_quantized = self.market_data_provider.quantize_order_price(
                        self.config.connector_name,
                        self.config.trading_pair, price)
                    amount_quantized = self.market_data_provider.quantize_order_amount(
                        self.config.connector_name,
                        self.config.trading_pair, amount_quote / self.get_mid_price())
                    # amount_quantized = amount_quote / self.get_mid_price()
                    grid_levels.append(GridLevel(id=f"{grid_range.id}_P{i}",
                                                 price=price_quantized,
                                                 amount=amount_quantized,
                                                 step=step, side=grid_range.side,
                                                 open_order_type=grid_range.open_order_type,
                                                 take_profit_order_type=grid_range.take_profit_order_type,
                                                 ))
        return grid_levels

    def get_balance_requirements(self) -> List[TokenAmount]:
        if "perpetual" in self.config.connector_name:
            return []
        base_currency = self.config.trading_pair.split("-")[0]
        return [TokenAmount(base_currency, self.config.extra_balance_base_usd / self.get_mid_price())]

    def get_mid_price(self) -> Decimal:
        return self.market_data_provider.get_price_by_type(
            self.config.connector_name,
            self.config.trading_pair,
            PriceType.MidPrice
        )

    def active_executors(self, is_trading: bool) -> List[ExecutorInfo]:
        return [
            executor for executor in self.executors_info
            if executor.is_active and executor.is_trading == is_trading
        ]

    def determine_executor_actions(self) -> List[ExecutorAction]:
        if self.market_data_provider.time() - self._last_grid_levels_update > 60:
            self._last_grid_levels_update = self.market_data_provider.time()
            self.grid_levels = self._calculate_grid_config()
        return self.determine_create_executor_actions() + self.determine_stop_executor_actions()

    async def update_processed_data(self):
        mid_price = self.get_mid_price()
        self.processed_data.update({
            "mid_price": mid_price,
            "active_executors_order_placed": self.active_executors(is_trading=False),
            "active_executors_order_trading": self.active_executors(is_trading=True),
            "long_activation_bounds": mid_price * (1 - self.config.activation_bounds),
            "short_activation_bounds": mid_price * (1 + self.config.activation_bounds),
        })

    def determine_create_executor_actions(self) -> List[ExecutorAction]:
        mid_price = self.processed_data["mid_price"]
        long_activation_bounds = self.processed_data["long_activation_bounds"]
        short_activation_bounds = self.processed_data["short_activation_bounds"]
        levels_allowed = []
        for level in self.grid_levels:
            if (level.side == TradeType.BUY and level.price >= long_activation_bounds) or \
                    (level.side == TradeType.SELL and level.price <= short_activation_bounds):
                levels_allowed.append(level)
        active_executors = self.processed_data["active_executors_order_placed"] + \
            self.processed_data["active_executors_order_trading"]
        active_executors_level_id = [executor.custom_info["level_id"] for executor in active_executors]
        levels_allowed = sorted([level for level in levels_allowed if level.id not in active_executors_level_id],
                                key=lambda level: abs(level.price - mid_price))
        levels_allowed = levels_allowed[:self.config.max_open_orders]
        create_actions = []
        for level in levels_allowed:
            if level.side == TradeType.BUY and level.price > mid_price:
                entry_price = mid_price
                take_profit = max(level.step * 2, ((level.price - mid_price) / mid_price) + level.step)
                trailing_stop = None
                # trailing_stop_ap = max(level.step * 2, ((mid_price - level.price) / mid_price) + level.step)
                # trailing_stop = TrailingStop(activation_price=trailing_stop_ap, trailing_delta=level.step / 2)
            elif level.side == TradeType.SELL and level.price < mid_price:
                entry_price = mid_price
                take_profit = max(level.step * 2, ((mid_price - level.price) / mid_price) + level.step)
                # trailing_stop_ap = max(level.step * 2, ((mid_price - level.price) / mid_price) + level.step)
                # trailing_stop = TrailingStop(activation_price=trailing_stop_ap, trailing_delta=level.step / 2)
                trailing_stop = None
            else:
                entry_price = level.price
                take_profit = level.step
                trailing_stop = None
            create_actions.append(CreateExecutorAction(controller_id=self.config.id,
                                                       executor_config=PositionExecutorConfig(
                                                           timestamp=self.market_data_provider.time(),
                                                           connector_name=self.config.connector_name,
                                                           trading_pair=self.config.trading_pair,
                                                           entry_price=entry_price,
                                                           amount=level.amount,
                                                           leverage=self.config.leverage,
                                                           side=level.side,
                                                           level_id=level.id,
                                                           activation_bounds=[self.config.activation_bounds,
                                                                              self.config.activation_bounds],
                                                           triple_barrier_config=TripleBarrierConfig(
                                                               take_profit=take_profit,
                                                               time_limit=self.config.time_limit,
                                                               open_order_type=OrderType.LIMIT_MAKER,
                                                               take_profit_order_type=level.take_profit_order_type,
                                                               trailing_stop=trailing_stop,
                                                           ))))
        return create_actions

    def determine_stop_executor_actions(self) -> List[ExecutorAction]:
        long_activation_bounds = self.processed_data["long_activation_bounds"]
        short_activation_bounds = self.processed_data["short_activation_bounds"]
        active_executors_order_placed = self.processed_data["active_executors_order_placed"]
        non_active_ranges = [grid_range.id for grid_range in self.config.grid_ranges if not grid_range.active]
        active_executor_of_non_active_ranges = [executor.id for executor in self.executors_info if
                                                executor.is_active and
                                                executor.custom_info["level_id"].split("_")[0] in non_active_ranges]
        long_executors_to_stop = [executor.id for executor in active_executors_order_placed if
                                  executor.side == TradeType.BUY and
                                  executor.config.entry_price <= long_activation_bounds]
        short_executors_to_stop = [executor.id for executor in active_executors_order_placed if
                                   executor.side == TradeType.SELL and
                                   executor.config.entry_price >= short_activation_bounds]
        executors_id_to_stop = set(
            active_executor_of_non_active_ranges + long_executors_to_stop + short_executors_to_stop)
        return [StopExecutorAction(controller_id=self.config.id, executor_id=executor) for executor in
                list(executors_id_to_stop)]
