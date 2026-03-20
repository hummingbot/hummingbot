import os
from decimal import Decimal
from typing import Dict, List, Optional

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.strategy.strategy_v2_base import StrategyV2Base, StrategyV2ConfigBase
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, StopExecutorAction


class HyperliquidStrategyConfig(StrategyV2ConfigBase):
    script_file_name: str = os.path.basename(__file__)
    max_global_drawdown_quote: Optional[float] = None
    max_controller_drawdown_quote: Optional[float] = None
    controllers_config: list[str] = []


class HyperliquidStrategy(StrategyV2Base):
    def __init__(self, connectors: Dict[str, ConnectorBase], config: HyperliquidStrategyConfig):
        super().__init__(connectors, config)
        self.config = config

    def on_tick(self):
        super().on_tick()
        if not self._is_stop_triggered:
            if self.config.max_controller_drawdown_quote:
                self._check_max_controller_drawdown()
            if self.config.max_global_drawdown_quote:
                self._check_max_global_drawdown()

    def _check_max_controller_drawdown(self):
        for controller_id, controller in self.controllers.items():
            report = self.get_performance_report(controller_id)
            if report.global_pnl_quote < -Decimal(str(self.config.max_controller_drawdown_quote)):
                self.logger().warning(
                    f"Controller {controller_id} hit max drawdown ({report.global_pnl_quote}). Stopping."
                )
                controller.stop()
                active = self.filter_executors(
                    executors=self.get_executors_by_controller(controller_id),
                    filter_func=lambda x: x.is_active and not x.is_trading,
                )
                self.executor_orchestrator.execute_actions(
                    [StopExecutorAction(controller_id=controller_id, executor_id=e.id)
                     for e in active]
                )

    def _check_max_global_drawdown(self):
        total_pnl = sum(
            self.get_performance_report(cid).global_pnl_quote
            for cid in self.controllers
        )
        if total_pnl < -Decimal(str(self.config.max_global_drawdown_quote)):
            self.logger().warning(f"Global drawdown hit ({total_pnl}). Stopping all.")
            for controller in self.controllers.values():
                controller.stop()

    def create_actions_proposal(self) -> List[CreateExecutorAction]:
        return []

    def stop_actions_proposal(self) -> List[StopExecutorAction]:
        return []

    def format_status(self) -> str:
        lines = ["Hyperliquid Strategy\n"]
        for controller_id, controller in self.controllers.items():
            report = self.get_performance_report(controller_id)
            lines.append(f"  Controller: {controller_id}")
            lines.append(f"  PnL: {report.global_pnl_quote:.4f} USDC")
            lines.append(f"  Volume: {report.volume_traded:.2f}")
            lines.extend(controller.to_format_status())
            lines.append("")
        return "\n".join(lines)
