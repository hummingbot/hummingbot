from decimal import Decimal
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.strategy_v2.executors.data_types import ExecutorConfigBase
from hummingbot.strategy_v2.executors.position_executor.data_types import TripleBarrierConfig
from hummingbot.strategy_v2.models.executors import TrackedOrder


class GridExecutorConfig(ExecutorConfigBase):
    type: Literal["grid_executor"] = "grid_executor"  # 执行器类型，固定为 grid_executor
    # Boundaries 边界参数
    connector_name: str  # 交易所连接器名称
    trading_pair: str  # 交易对
    start_price: Decimal  # 网格起始价格
    end_price: Decimal  # 网格结束价格
    limit_price: Decimal  # 限价（可用于止损/止盈）
    side: TradeType = TradeType.BUY  # 网格方向，买入或卖出
    # Profiling 配置参数
    total_amount_quote: Decimal  # 总投入资金（计价货币）
    min_spread_between_orders: Decimal = Decimal("0.0005")  # 相邻订单最小价差
    min_order_amount_quote: Decimal = Decimal("5")  # 单笔最小下单金额（计价货币）
    # Execution 执行参数
    max_open_orders: int = 5  # 最大同时挂单数量
    max_orders_per_batch: Optional[int] = None  # 每批最大下单数
    order_frequency: int = 0  # 下单频率（秒）
    activation_bounds: Optional[Decimal] = None  # 激活区间（可选）
    safe_extra_spread: Decimal = Decimal("0.0001")  # 安全额外价差
    # Risk Management 风控参数
    triple_barrier_config: TripleBarrierConfig  # 三重风控配置
    leverage: int = 20  # 杠杆倍数
    level_id: Optional[str] = None  # 网格层级ID（可选）
    deduct_base_fees: bool = False  # 是否用基础币扣除手续费
    keep_position: bool = False  # 是否持仓不平仓
    coerce_tp_to_step: bool = False  # 是否将止盈强制对齐到网格步长


class GridLevelStates(Enum):
    NOT_ACTIVE = "NOT_ACTIVE"  # 未激活
    OPEN_ORDER_PLACED = "OPEN_ORDER_PLACED"  # 已挂开仓单
    OPEN_ORDER_FILLED = "OPEN_ORDER_FILLED"  # 开仓单已成交
    CLOSE_ORDER_PLACED = "CLOSE_ORDER_PLACED"  # 已挂平仓单
    COMPLETE = "COMPLETE"  # 网格已完成


class GridLevel(BaseModel):
    id: str  # 网格层级唯一ID
    price: Decimal  # 网格价格
    amount_quote: Decimal  # 该层级下单金额（计价货币）
    take_profit: Decimal  # 止盈百分比
    side: TradeType  # 买/卖方向
    open_order_type: OrderType  # 开仓订单类型
    take_profit_order_type: OrderType  # 止盈订单类型
    active_open_order: Optional[TrackedOrder] = None  # 当前激活的开仓订单
    active_close_order: Optional[TrackedOrder] = None  # 当前激活的平仓订单
    state: GridLevelStates = GridLevelStates.NOT_ACTIVE  # 当前层级状态
    model_config = ConfigDict(arbitrary_types_allowed=True)  # 允许任意类型

    def update_state(self):
        """
        更新当前网格层级的状态，根据订单的成交情况自动切换状态。
        """
        if self.active_open_order is None:
            self.state = GridLevelStates.NOT_ACTIVE  # 没有开仓订单，未激活
        elif self.active_open_order.is_filled:
            self.state = GridLevelStates.OPEN_ORDER_FILLED  # 开仓单已成交
        else:
            self.state = GridLevelStates.OPEN_ORDER_PLACED  # 已挂开仓单但未成交
        if self.active_close_order is not None:
            if self.active_close_order.is_filled:
                self.state = GridLevelStates.COMPLETE  # 平仓单已成交，网格完成
            else:
                self.state = GridLevelStates.CLOSE_ORDER_PLACED  # 已挂平仓单但未成交

    def reset_open_order(self):
        """
        重置开仓订单状态。
        """
        self.active_open_order = None
        self.state = GridLevelStates.NOT_ACTIVE

    def reset_close_order(self):
        """
        重置平仓订单状态。
        """
        self.active_close_order = None
        self.state = GridLevelStates.OPEN_ORDER_FILLED

    def reset_level(self):
        """
        重置整个网格层级状态，包括开仓和平仓订单。
        """
        self.active_open_order = None
        self.active_close_order = None
        self.state = GridLevelStates.NOT_ACTIVE
