import os
import time
from decimal import Decimal
from typing import Dict, List, Optional, Set

from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.clock import Clock
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.remote_iface.mqtt import ETopicPublisher
from hummingbot.strategy.strategy_v2_base import StrategyV2Base, StrategyV2ConfigBase
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, StopExecutorAction


class GenericV2StrategyWithCashOutConfig(StrategyV2ConfigBase):
    script_file_name: str = os.path.basename(__file__)
    candles_config: List[CandlesConfig] = []
    markets: Dict[str, Set[str]] = {}
    time_to_cash_out: Optional[int] = None
    max_global_drawdown: Optional[float] = None
    max_controller_drawdown: Optional[float] = None
    rebalance_interval: Optional[int] = None
    extra_inventory: Optional[float] = 0.02
    min_amount_to_rebalance_usd: Decimal = Decimal("8")
    asset_to_rebalance: str = "USDT"


class GenericV2StrategyWithCashOut(StrategyV2Base):
    """
    This script runs a generic strategy with cash out feature. Will also check if the controllers configs have been
    updated and apply the new settings.
    The cash out of the script can be set by the time_to_cash_out parameter in the config file. If set, the script will
    stop the controllers after the specified time has passed, and wait until the active executors finalize their
    execution.
    The controllers will also have a parameter to manually cash out. In that scenario, the main strategy will stop the
    specific controller and wait until the active executors finalize their execution. The rest of the executors will
    wait until the main strategy stops them.
    """
    performance_report_interval: int = 1

    def __init__(self, connectors: Dict[str, ConnectorBase], config: GenericV2StrategyWithCashOutConfig):
        super().__init__(connectors, config)
        self.config = config
        self.cashing_out = False
        self.max_pnl_by_controller = {}
        self.performance_reports = {}
        self.max_global_pnl = Decimal("0")
        self.drawdown_exited_controllers = []
        self.closed_executors_buffer: int = 30
        self.rebalance_interval: int = self.config.rebalance_interval
        self._last_performance_report_timestamp = 0
        self._last_rebalance_check_timestamp = 0
        hb_app = HummingbotApplication.main_application()
        self.mqtt_enabled = hb_app._mqtt is not None
        self._pub: Optional[ETopicPublisher] = None
        if self.config.time_to_cash_out:
            self.cash_out_time = self.config.time_to_cash_out + time.time()
        else:
            self.cash_out_time = None

    def start(self, clock: Clock, timestamp: float) -> None:
        """
        Start the strategy.
        :param clock: Clock to use.
        :param timestamp: Current time.
        """
        self._last_timestamp = timestamp
        self.apply_initial_setting()
        if self.mqtt_enabled:
            self._pub = ETopicPublisher("performance", use_bot_prefix=True)

    async def on_stop(self):
        await super().on_stop()
        if self.mqtt_enabled:
            self._pub({controller_id: {} for controller_id in self.controllers.keys()})
            self._pub = None

    def on_tick(self):
        super().on_tick()
        self.performance_reports = {controller_id: self.executor_orchestrator.generate_performance_report(controller_id=controller_id).dict() for controller_id in self.controllers.keys()}
        self.control_rebalance()
        self.control_cash_out()
        self.control_max_drawdown()
        self.send_performance_report()

    def control_rebalance(self):
        if self.rebalance_interval and self._last_rebalance_check_timestamp + self.rebalance_interval <= self.current_timestamp:
            balance_required = {}
            for controller_id, controller in self.controllers.items():
                connector_name = controller.config.model_dump().get("connector_name")
                if connector_name and "perpetual" in connector_name:
                    continue
                if connector_name not in balance_required:
                    balance_required[connector_name] = {}
                tokens_required = controller.get_balance_requirements()
                for token, amount in tokens_required:
                    if token not in balance_required[connector_name]:
                        balance_required[connector_name][token] = amount
                    else:
                        balance_required[connector_name][token] += amount
            for connector_name, balance_requirements in balance_required.items():
                connector = self.connectors[connector_name]
                for token, amount in balance_requirements.items():
                    if token == self.config.asset_to_rebalance:
                        continue
                    balance = connector.get_balance(token)
                    trading_pair = f"{token}-{self.config.asset_to_rebalance}"
                    mid_price = connector.get_mid_price(trading_pair)
                    trading_rule = connector.trading_rules[trading_pair]
                    amount_with_safe_margin = amount * (1 + Decimal(self.config.extra_inventory))
                    active_executors_for_pair = self.filter_executors(
                        executors=self.get_all_executors(),
                        filter_func=lambda x: x.is_active and x.trading_pair == trading_pair and x.connector_name == connector_name
                    )
                    unmatched_amount = sum([executor.filled_amount_quote for executor in active_executors_for_pair if executor.side == TradeType.SELL]) - sum([executor.filled_amount_quote for executor in active_executors_for_pair if executor.side == TradeType.BUY])
                    balance += unmatched_amount / mid_price
                    base_balance_diff = balance - amount_with_safe_margin
                    abs_balance_diff = abs(base_balance_diff)
                    trading_rules_condition = abs_balance_diff > trading_rule.min_order_size and abs_balance_diff * mid_price > trading_rule.min_notional_size and abs_balance_diff * mid_price > self.config.min_amount_to_rebalance_usd
                    order_type = OrderType.MARKET
                    if base_balance_diff > 0:
                        if trading_rules_condition:
                            self.logger().info(f"Rebalance: Selling {amount_with_safe_margin} {token} to {self.config.asset_to_rebalance}. Balance: {balance} | Executors unmatched balance {unmatched_amount / mid_price}")
                            connector.sell(
                                trading_pair=trading_pair,
                                amount=abs_balance_diff,
                                order_type=order_type,
                                price=mid_price)
                        else:
                            self.logger().info("Skipping rebalance due a low amount to sell that may cause future imbalance")
                    else:
                        if not trading_rules_condition:
                            amount = max([self.config.min_amount_to_rebalance_usd / mid_price, trading_rule.min_order_size, trading_rule.min_notional_size / mid_price])
                            self.logger().info(f"Rebalance: Buying for a higher value to avoid future imbalance {amount} {token} to {self.config.asset_to_rebalance}. Balance: {balance} | Executors unmatched balance {unmatched_amount}")
                        else:
                            amount = abs_balance_diff
                            self.logger().info(f"Rebalance: Buying {amount} {token} to {self.config.asset_to_rebalance}. Balance: {balance} | Executors unmatched balance {unmatched_amount}")
                        connector.buy(
                            trading_pair=trading_pair,
                            amount=amount,
                            order_type=order_type,
                            price=mid_price)
            self._last_rebalance_check_timestamp = self.current_timestamp

    def control_max_drawdown(self):
        if self.config.max_controller_drawdown:
            self.check_max_controller_drawdown()
        if self.config.max_global_drawdown:
            self.check_max_global_drawdown()

    def check_max_controller_drawdown(self):
        for controller_id, controller in self.controllers.items():
            if controller.status != RunnableStatus.RUNNING:
                continue
            controller_pnl = self.performance_reports[controller_id]["global_pnl_quote"]
            last_max_pnl = self.max_pnl_by_controller[controller_id]
            if controller_pnl > last_max_pnl:
                self.max_pnl_by_controller[controller_id] = controller_pnl
            else:
                current_drawdown = last_max_pnl - controller_pnl
                if current_drawdown > self.config.max_controller_drawdown:
                    self.logger().info(f"Controller {controller_id} reached max drawdown. Stopping the controller.")
                    controller.stop()
                    executors_order_placed = self.filter_executors(
                        executors=self.executors_info[controller_id],
                        filter_func=lambda x: x.is_active and not x.is_trading,
                    )
                    self.executor_orchestrator.execute_actions(
                        actions=[StopExecutorAction(controller_id=controller_id, executor_id=executor.id) for executor in executors_order_placed]
                    )
                    self.drawdown_exited_controllers.append(controller_id)

    def check_max_global_drawdown(self):
        current_global_pnl = sum([report["global_pnl_quote"] for report in self.performance_reports.values()])
        if current_global_pnl > self.max_global_pnl:
            self.max_global_pnl = current_global_pnl
        else:
            current_global_drawdown = self.max_global_pnl - current_global_pnl
            if current_global_drawdown > self.config.max_global_drawdown:
                self.drawdown_exited_controllers.extend(list(self.controllers.keys()))
                self.logger().info("Global drawdown reached. Stopping the strategy.")
                HummingbotApplication.main_application().stop()

    def send_performance_report(self):
        if self.current_timestamp - self._last_performance_report_timestamp >= self.performance_report_interval and self.mqtt_enabled:
            self._pub(self.performance_reports)
            self._last_performance_report_timestamp = self.current_timestamp

    def control_cash_out(self):
        self.evaluate_cash_out_time()
        if self.cashing_out:
            self.check_executors_status()
        else:
            self.check_manual_cash_out()

    def evaluate_cash_out_time(self):
        if self.cash_out_time and self.current_timestamp >= self.cash_out_time and not self.cashing_out:
            self.logger().info("Cash out time reached. Stopping the controllers.")
            for controller_id, controller in self.controllers.items():
                if controller.status == RunnableStatus.RUNNING:
                    self.logger().info(f"Cash out for controller {controller_id}.")
                    controller.stop()
            self.cashing_out = True

    def check_manual_cash_out(self):
        for controller_id, controller in self.controllers.items():
            if controller.config.manual_kill_switch and controller.status == RunnableStatus.RUNNING:
                self.logger().info(f"Manual cash out for controller {controller_id}.")
                controller.stop()
                executors_to_stop = self.get_executors_by_controller(controller_id)
                self.executor_orchestrator.execute_actions(
                    [StopExecutorAction(executor_id=executor.id,
                                        controller_id=executor.controller_id) for executor in executors_to_stop])
            if not controller.config.manual_kill_switch and controller.status == RunnableStatus.TERMINATED:
                if controller_id in self.drawdown_exited_controllers:
                    continue
                self.logger().info(f"Restarting controller {controller_id}.")
                controller.start()

    def check_executors_status(self):
        active_executors = self.filter_executors(
            executors=self.get_all_executors(),
            filter_func=lambda executor: executor.status == RunnableStatus.RUNNING
        )
        if not active_executors:
            self.logger().info("All executors have finalized their execution. Stopping the strategy.")
            HummingbotApplication.main_application().stop()
        else:
            non_trading_executors = self.filter_executors(
                executors=active_executors,
                filter_func=lambda executor: not executor.is_trading
            )
            self.executor_orchestrator.execute_actions(
                [StopExecutorAction(executor_id=executor.id,
                                    controller_id=executor.controller_id) for executor in non_trading_executors])

    def create_actions_proposal(self) -> List[CreateExecutorAction]:
        return []

    def stop_actions_proposal(self) -> List[StopExecutorAction]:
        return []

    def apply_initial_setting(self):
        connectors_position_mode = {}
        for controller_id, controller in self.controllers.items():
            self.max_pnl_by_controller[controller_id] = Decimal("0")
            config_dict = controller.config.model_dump()
            if "connector_name" in config_dict:
                if self.is_perpetual(config_dict["connector_name"]):
                    if "position_mode" in config_dict:
                        connectors_position_mode[config_dict["connector_name"]] = config_dict["position_mode"]
                    if "leverage" in config_dict:
                        self.connectors[config_dict["connector_name"]].set_leverage(leverage=config_dict["leverage"],
                                                                                    trading_pair=config_dict["trading_pair"])
        for connector_name, position_mode in connectors_position_mode.items():
            self.connectors[connector_name].set_position_mode(position_mode)
