from decimal import Decimal
from typing import Dict, List, Optional

from pydantic import Field

from hummingbot.core.data_type.common import MarketDict, OrderType, PositionMode, PriceType, TradeType
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy_v2.controllers import ControllerBase, ControllerConfigBase
from hummingbot.strategy_v2.executors.data_types import ConnectorPair
from hummingbot.strategy_v2.executors.grid_executor.data_types import GridExecutorConfig
from hummingbot.strategy_v2.executors.position_executor.data_types import TripleBarrierConfig
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, ExecutorAction, StopExecutorAction
from hummingbot.strategy_v2.models.executors_info import ExecutorInfo
from hummingbot.strategy_v2.models.base import RunnableStatus


class GridStrikeConfig(ControllerConfigBase):
    """
    双向网格策略配置类，支持在两个账户同时执行相反方向的网格交易。
    """
    controller_type: str = "generic"  # 控制器类型
    controller_name: str = "grid_strike"  # 控制器名称
    candles_config: List[CandlesConfig] = []  # 蜡烛图配置

    # 账户配置
    leverage: int = 20  # 杠杆倍数
    position_mode: PositionMode = PositionMode.HEDGE  # 持仓模式，对冲模式

    # 边界参数
    connector_name: str = "binance_perpetual"  # 第一个连接器名称
    trading_pair: str = "WLD-USDT"  # 交易对
    side: TradeType = TradeType.BUY  # 第一个网格的交易方向
    start_price: Decimal = Field(default=Decimal("0.58"), json_schema_extra={"is_updatable": True})  # 网格起始价格
    end_price: Decimal = Field(default=Decimal("0.95"), json_schema_extra={"is_updatable": True})  # 网格结束价格
    limit_price: Decimal = Field(default=Decimal("0.55"), json_schema_extra={"is_updatable": True})  # 限价

    # 第二个连接器配置（用于反向网格）
    second_connector_name: str = "binance_perpetual_2"  # 第二个连接器名称
    use_second_connector: bool = Field(default=False, json_schema_extra={"is_updatable": True})  # 是否使用第二个连接器

    # 资金配置
    total_amount_quote: Decimal = Field(default=Decimal("1000"), json_schema_extra={"is_updatable": True})  # 每个网格的总投入资金
    min_spread_between_orders: Optional[Decimal] = Field(default=Decimal("0.001"), json_schema_extra={"is_updatable": True})  # 订单之间的最小价差
    min_order_amount_quote: Optional[Decimal] = Field(default=Decimal("5"), json_schema_extra={"is_updatable": True})  # 最小订单金额

    # 执行参数
    max_open_orders: int = Field(default=2, json_schema_extra={"is_updatable": True})  # 最大挂单数量
    max_orders_per_batch: Optional[int] = Field(default=1, json_schema_extra={"is_updatable": True})  # 每批最大订单数
    order_frequency: int = Field(default=3, json_schema_extra={"is_updatable": True})  # 下单频率（秒）
    activation_bounds: Optional[Decimal] = Field(default=None, json_schema_extra={"is_updatable": True})  # 激活边界
    keep_position: bool = Field(default=False, json_schema_extra={"is_updatable": True})  # 是否保持持仓

    # 风险管理
    triple_barrier_config: TripleBarrierConfig = TripleBarrierConfig(
        take_profit=Decimal("0.001"),  # 止盈比例
        open_order_type=OrderType.LIMIT_MAKER,  # 开仓订单类型
        take_profit_order_type=OrderType.LIMIT_MAKER,  # 止盈订单类型
    )

    def update_markets(self, markets: MarketDict) -> MarketDict:
        """
        更新市场信息，添加两个连接器的交易对
        """
        markets = markets.add_or_update(self.connector_name, self.trading_pair)
        if self.use_second_connector:
            markets = markets.add_or_update(self.second_connector_name, self.trading_pair)
        return markets


class GridStrike(ControllerBase):
    """
    双向网格策略控制器，可同时控制两个相反方向的网格执行器
    """
    def __init__(self, config: GridStrikeConfig, *args, **kwargs):
        """
        初始化双向网格控制器
        """
        super().__init__(config, *args, **kwargs)
        self.config = config
        self._last_grid_levels_update = 0
        self.trading_rules = None
        self.grid_levels = []
        self.initialize_rate_sources()
        
        # 存储执行器ID的字典，用于跟踪主网格和反向网格
        self._executor_ids = {
            "main_grid": None,
            "reverse_grid": None
        }
        
        # 执行器状态变化的标志
        self._executor_status_changed = False
        
        # 上一次检查的执行器状态
        self._last_executor_statuses = {}

    def initialize_rate_sources(self):
        """
        初始化价格数据源
        """
        # 添加第一个连接器的价格源
        self.market_data_provider.initialize_rate_sources([ConnectorPair(connector_name=self.config.connector_name,
                                                                         trading_pair=self.config.trading_pair)])
        # 如果启用第二个连接器，也添加其价格源
        if self.config.use_second_connector:
            self.market_data_provider.initialize_rate_sources([ConnectorPair(connector_name=self.config.second_connector_name,
                                                                             trading_pair=self.config.trading_pair)])

    def active_executors(self) -> List[ExecutorInfo]:
        """
        获取所有活跃的执行器信息
        """
        return [
            executor for executor in self.executors_info
            if executor.is_active
        ]
        
    def get_executor_by_id(self, executor_id: str) -> Optional[ExecutorInfo]:
        """
        根据执行器ID获取执行器信息
        
        :param executor_id: 执行器ID
        :return: 执行器信息，如果不存在则返回None
        """
        for executor in self.executors_info:
            if executor.id == executor_id:
                return executor
        return None
        
    def get_executor_by_level_id(self, level_id: str) -> Optional[ExecutorInfo]:
        """
        根据level_id获取执行器信息
        
        :param level_id: 网格级别ID
        :return: 执行器信息，如果不存在则返回None
        """
        for executor in self.executors_info:
            if hasattr(executor, 'config') and hasattr(executor.config, 'level_id') and executor.config.level_id == level_id:
                return executor
        return None

    def is_inside_bounds(self, price: Decimal) -> bool:
        """
        判断价格是否在网格边界内
        """
        return self.config.start_price <= price <= self.config.end_price

    def determine_executor_actions(self) -> List[ExecutorAction]:
        """
        确定执行器动作，创建主网格和反向网格
        """
        actions = []
        mid_price = self.market_data_provider.get_price_by_type(
            self.config.connector_name, self.config.trading_pair, PriceType.MidPrice)
        
        # 检查是否有活跃的执行器
        active_executors = self.active_executors()
        
        # 如果没有活跃的执行器且价格在边界内，创建新的执行器
        if len(active_executors) == 0 and self.is_inside_bounds(mid_price):
            # 创建第一个网格执行器（主网格）
            main_grid_action = CreateExecutorAction(
                controller_id=self.config.id,
                executor_config=GridExecutorConfig(
                    timestamp=self.market_data_provider.time(),
                    connector_name=self.config.connector_name,
                    trading_pair=self.config.trading_pair,
                    start_price=self.config.start_price,
                    end_price=self.config.end_price,
                    leverage=self.config.leverage,
                    limit_price=self.config.limit_price,
                    side=self.config.side,
                    total_amount_quote=self.config.total_amount_quote,
                    min_spread_between_orders=self.config.min_spread_between_orders,
                    min_order_amount_quote=self.config.min_order_amount_quote,
                    max_open_orders=self.config.max_open_orders,
                    max_orders_per_batch=self.config.max_orders_per_batch,
                    order_frequency=self.config.order_frequency,
                    activation_bounds=self.config.activation_bounds,
                    triple_barrier_config=self.config.triple_barrier_config,
                    level_id="main_grid",
                    keep_position=self.config.keep_position,
                )
            )
            actions.append(main_grid_action)
            
            # 如果启用第二个连接器，创建反向网格执行器
            if self.config.use_second_connector:
                # 反向网格使用相反的交易方向
                reverse_side = TradeType.SELL if self.config.side == TradeType.BUY else TradeType.BUY
                
                reverse_grid_action = CreateExecutorAction(
                    controller_id=self.config.id,
                    executor_config=GridExecutorConfig(
                        timestamp=self.market_data_provider.time(),
                        connector_name=self.config.second_connector_name,
                        trading_pair=self.config.trading_pair,
                        # 反向网格的起始价格和结束价格需要保持一致的价格区间
                        start_price=self.config.start_price,
                        end_price=self.config.end_price,
                        leverage=self.config.leverage,
                        # 反向网格的限价也需要适当调整
                        limit_price=self.config.limit_price,
                        side=reverse_side,  # 使用相反的交易方向
                        total_amount_quote=self.config.total_amount_quote,  # 使用相同的资金量
                        min_spread_between_orders=self.config.min_spread_between_orders,
                        min_order_amount_quote=self.config.min_order_amount_quote,
                        max_open_orders=self.config.max_open_orders,
                        max_orders_per_batch=self.config.max_orders_per_batch,
                        order_frequency=self.config.order_frequency,
                        activation_bounds=self.config.activation_bounds,
                        triple_barrier_config=self.config.triple_barrier_config,
                        level_id="reverse_grid",
                        keep_position=self.config.keep_position,
                    )
                )
                actions.append(reverse_grid_action)
        
        # 处理执行器同步停止逻辑
        stop_actions = self.check_and_sync_executors_status()
        if stop_actions:
            actions.extend(stop_actions)
                
        return actions
    
    def check_and_sync_executors_status(self) -> List[ExecutorAction]:
        """
        检查执行器状态并同步停止
        
        当一个执行器停止或关闭时，确保另一个执行器也停止
        
        :return: 执行器操作列表
        """
        actions = []
        active_executors = self.active_executors()
        
        # 更新执行器ID字典
        for executor in active_executors:
            if hasattr(executor, 'config') and hasattr(executor.config, 'level_id'):
                if executor.config.level_id == "main_grid":
                    self._executor_ids["main_grid"] = executor.id
                elif executor.config.level_id == "reverse_grid":
                    self._executor_ids["reverse_grid"] = executor.id
        
        # 如果没有启用双向网格，不需要同步
        if not self.config.use_second_connector:
            return actions
            
        # 检查执行器状态变化
        current_statuses = {}
        for executor in active_executors:
            current_statuses[executor.id] = executor.status
        
        # 检查是否有执行器状态变化
        for executor_id, status in current_statuses.items():
            if executor_id in self._last_executor_statuses:
                if status != self._last_executor_statuses[executor_id]:
                    self._executor_status_changed = True
                    break
        
        # 如果状态发生变化，检查是否需要同步停止
        if self._executor_status_changed:
            # 检查是否有一个执行器已经停止或正在关闭
            stopping_executor = None
            for executor in active_executors:
                if executor.status in [RunnableStatus.STOPPED, RunnableStatus.SHUTTING_DOWN]:
                    stopping_executor = executor
                    break
            
            # 如果有一个执行器正在停止，确保另一个执行器也停止
            if stopping_executor:
                for executor in active_executors:
                    if executor.id != stopping_executor.id and executor.status not in [RunnableStatus.STOPPED, RunnableStatus.SHUTTING_DOWN]:
                        # 创建停止另一个执行器的操作
                        actions.append(StopExecutorAction(executor_id=executor.id))
                        self.logger().info(f"同步停止执行器: {executor.id}，因为执行器 {stopping_executor.id} 已停止")
        
        # 更新上一次的状态
        self._last_executor_statuses = current_statuses
        self._executor_status_changed = False
        
        return actions

    async def update_processed_data(self):
        """
        更新处理后的数据
        """
        pass

    def to_format_status(self) -> List[str]:
        """
        格式化状态输出，显示双向网格的状态信息
        """
        status = []
        mid_price = self.market_data_provider.get_price_by_type(
            self.config.connector_name, self.config.trading_pair, PriceType.MidPrice)
        
        # 定义标准盒子宽度以保持一致性
        box_width = 114
        
        # 顶部网格配置框，使用简单边框
        status.append("┌" + "─" * box_width + "┐")
        
        # 第一行：网格配置和中间价格
        left_section = "双向网格配置:"
        padding = box_width - len(left_section) - 4  # -4 用于边框字符和间距
        config_line1 = f"│ {left_section}{' ' * padding}"
        padding2 = box_width - len(config_line1) + 1  # +1 用于正确的右边框对齐
        config_line1 += " " * padding2 + "│"
        status.append(config_line1)
        
        # 第二行：配置参数
        config_line2 = f"│ 起始价: {self.config.start_price:.4f} │ 结束价: {self.config.end_price:.4f} │ 主方向: {self.config.side} │ 限价: {self.config.limit_price:.4f} │ 当前价: {mid_price:.4f} │"
        padding = box_width - len(config_line2) + 1  # +1 用于正确的右边框对齐
        config_line2 += " " * padding + "│"
        status.append(config_line2)
        
        # 第三行：最大订单数和是否在边界内
        config_line3 = f"│ 最大订单数: {self.config.max_open_orders}   │ 价格在边界内: {1 if self.is_inside_bounds(mid_price) else 0} │ 双向网格: {'启用' if self.config.use_second_connector else '禁用'}"
        padding = box_width - len(config_line3) + 1  # +1 用于正确的右边框对齐
        config_line3 += " " * padding + "│"
        status.append(config_line3)
        status.append("└" + "─" * box_width + "┘")
        
        # 显示每个活跃执行器的状态
        for level in self.active_executors():
            # 定义列宽度以实现完美对齐
            col_width = box_width // 3  # 将总宽度除以3以获得相等的列
            total_width = box_width
            
            # 网格状态标题 - 使用长线和运行状态
            grid_type = "主网格" if hasattr(level, 'config') and hasattr(level.config, 'level_id') and level.config.level_id == "main_grid" else "反向网格"
            status_header = f"网格状态: {level.id} ({grid_type}) ({level.status})"
            status_line = f"┌ {status_header}" + "─" * (total_width - len(status_header) - 2) + "┐"
            status.append(status_line)
            
            # 计算精确的列宽度以实现完美对齐
            col1_end = col_width
            
            # 列标题
            header_line = "│ 网格层级分布" + " " * (col1_end - 20) + "│"
            header_line += " 订单统计" + " " * (col_width - 18) + "│"
            header_line += " 性能指标" + " " * (col_width - 21) + "│"
            status.append(header_line)
            
            # 三列的数据
            level_dist_data = [
                f"未激活: {len(level.custom_info['levels_by_state'].get('NOT_ACTIVE', []))}",
                f"挂单中: {len(level.custom_info['levels_by_state'].get('OPEN_ORDER_PLACED', []))}",
                f"已成交: {len(level.custom_info['levels_by_state'].get('OPEN_ORDER_FILLED', []))}",
                f"平仓中: {len(level.custom_info['levels_by_state'].get('CLOSE_ORDER_PLACED', []))}",
                f"已完成: {len(level.custom_info['levels_by_state'].get('COMPLETE', []))}"
            ]
            order_stats_data = [
                f"总数: {sum(len(level.custom_info[k]) for k in ['filled_orders', 'failed_orders', 'canceled_orders'])}",
                f"已成交: {len(level.custom_info['filled_orders'])}",
                f"失败: {len(level.custom_info['failed_orders'])}",
                f"已取消: {len(level.custom_info['canceled_orders'])}"
            ]
            perf_metrics_data = [
                f"买入量: {level.custom_info['realized_buy_size_quote']:.4f}",
                f"卖出量: {level.custom_info['realized_sell_size_quote']:.4f}",
                f"已实现盈亏: {level.custom_info['realized_pnl_quote']:.4f}",
                f"已实现手续费: {level.custom_info['realized_fees_quote']:.4f}",
                f"未实现盈亏: {level.custom_info['position_pnl_quote']:.4f}",
                f"持仓量: {level.custom_info['position_size_quote']:.4f}"
            ]
            
            # 构建具有完美对齐的行
            max_rows = max(len(level_dist_data), len(order_stats_data), len(perf_metrics_data))
            for i in range(max_rows):
                col1 = level_dist_data[i] if i < len(level_dist_data) else ""
                col2 = order_stats_data[i] if i < len(order_stats_data) else ""
                col3 = perf_metrics_data[i] if i < len(perf_metrics_data) else ""
                row = "│ " + col1
                row += " " * (col1_end - len(col1) - 2)  # -2 用于开头的"│ "
                row += "│ " + col2
                row += " " * (col_width - len(col2) - 2)  # -2 用于列2前的"│ "
                row += "│ " + col3
                row += " " * (col_width - len(col3) - 2)  # -2 用于列3前的"│ "
                row += "│"
                status.append(row)
            
            # 流动性行，完美对齐
            status.append("├" + "─" * total_width + "┤")
            liquidity_line = f"│ 开仓流动性: {level.custom_info['open_liquidity_placed']:.4f} │ 平仓流动性: {level.custom_info['close_liquidity_placed']:.4f} │"
            liquidity_line += " " * (total_width - len(liquidity_line) + 1)  # +1 用于正确的右边框对齐
            liquidity_line += "│"
            status.append(liquidity_line)
            status.append("└" + "─" * total_width + "┘")
        
        return status
