import json
import os
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import PriceType
from hummingbot.core.event.events import MarketOrderFailureEvent
from hummingbot.strategy.strategy_v2_base import StrategyV2Base, StrategyV2ConfigBase
from hummingbot.strategy_v2.models.base import RunnableStatus
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, StopExecutorAction


class V2WithControllersConfig(StrategyV2ConfigBase):
    script_file_name: str = os.path.basename(__file__)
    max_global_drawdown_quote: Optional[float] = None
    max_controller_drawdown_quote: Optional[float] = None
    runtime_snapshot_file: str = "trading_runtime.json"
    runtime_snapshot_interval: int = 5
    market_data_stale_after: int = 20
    pause_on_stale_market_data: bool = True
    evolution_candidate_id: Optional[str] = None
    evolution_deployment_id: Optional[str] = None
    evolution_config_hash: Optional[str] = None


class V2WithControllers(StrategyV2Base):
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

    def __init__(self, connectors: Dict[str, ConnectorBase], config: V2WithControllersConfig):
        super().__init__(connectors, config)
        self.config = config
        self.max_pnl_by_controller = {}
        self.max_global_pnl = Decimal("0")
        self.drawdown_exited_controllers = []
        self.closed_executors_buffer: int = 30
        self._last_performance_report_timestamp = 0
        self._last_runtime_snapshot_timestamp = 0
        self._market_data_observations: Dict[Tuple[str, str], Dict[str, float | int]] = {}
        self._market_data_health: List[dict] = []
        self._market_data_paused_controllers: Set[str] = set()

    def on_tick(self):
        market_data_health = self.collect_market_data_health()
        self.apply_market_data_guard(market_data_health)
        super().on_tick()
        self.write_runtime_snapshot()
        if not self._is_stop_triggered:
            self.check_manual_kill_switch()
            self.control_max_drawdown()
            self.send_performance_report()

    @staticmethod
    def _decimal_text(value) -> str:
        return format(Decimal(str(value)), "f")

    def collect_market_data_health(self) -> List[dict]:
        """Track order-book updates separately from the age of the runtime snapshot."""
        now = float(self.current_timestamp)
        seen_markets = set()
        health = []
        for controller in self.controllers.values():
            connector_name = getattr(controller.config, "connector_name", None)
            trading_pair = getattr(controller.config, "trading_pair", None)
            if not connector_name or not trading_pair or (connector_name, trading_pair) in seen_markets:
                continue
            seen_markets.add((connector_name, trading_pair))
            connector = self.connectors.get(connector_name)
            order_book = getattr(connector, "order_books", {}).get(trading_pair) if connector else None
            try:
                update_id = max(
                    int(getattr(order_book, "last_diff_uid", 0) or 0),
                    int(getattr(order_book, "snapshot_uid", 0) or 0),
                )
            except (TypeError, ValueError):
                update_id = 0
            key = (connector_name, trading_pair)
            observation = self._market_data_observations.get(key)
            if observation is None or observation["update_id"] != update_id:
                observation = {"update_id": update_id, "updated_at": now}
                self._market_data_observations[key] = observation
            age_seconds = max(0.0, now - float(observation["updated_at"]))
            stale = age_seconds > max(1, self.config.market_data_stale_after)
            health.append({
                "connector": connector_name,
                "symbol": trading_pair,
                "update_id": update_id,
                "last_update": datetime.fromtimestamp(float(observation["updated_at"]), timezone.utc).isoformat(),
                "age_seconds": round(age_seconds, 1),
                "stale": stale,
            })
        self._market_data_health = health
        return health

    def apply_market_data_guard(self, market_data_health: List[dict]):
        """Suspend paper quoting when the order book stops advancing; resume only after it recovers."""
        if not self.config.pause_on_stale_market_data:
            return
        stale_markets = [item for item in market_data_health if item["stale"]]
        if stale_markets:
            if self._market_data_paused_controllers:
                return
            labels = ", ".join(f"{item['connector']}:{item['symbol']}" for item in stale_markets)
            self.logger().warning(f"Market data is stale for {labels}. Pausing controllers and cancelling paper quotes.")
            actions = []
            for controller_id, controller in self.controllers.items():
                if controller.status != RunnableStatus.RUNNING:
                    continue
                controller.stop()
                self._market_data_paused_controllers.add(controller_id)
                actions.extend(
                    StopExecutorAction(controller_id=executor.controller_id, executor_id=executor.id)
                    for executor in self.get_executors_by_controller(controller_id)
                    if executor.is_active
                )
            if actions:
                self.executor_orchestrator.execute_actions(actions=actions)
            return

        if not self._market_data_paused_controllers:
            return
        resumed = []
        for controller_id in list(self._market_data_paused_controllers):
            controller = self.controllers.get(controller_id)
            if controller is None or controller.config.manual_kill_switch or controller_id in self.drawdown_exited_controllers:
                continue
            controller.start()
            resumed.append(controller_id)
        self._market_data_paused_controllers.difference_update(resumed)
        if resumed:
            self.logger().info(f"Market data recovered. Resuming controllers: {', '.join(resumed)}.")

    def write_runtime_snapshot(self):
        """Persist the read-only account view consumed by the local operations console.

        Balances and open orders are otherwise only available inside the running
        connector. Historical orders and fills remain in Hummingbot's SQLite
        recorder. Keeping this snapshot separate makes the console useful for
        both paper and future approved live connectors without exposing secrets
        or adding a trading control surface.
        """
        interval = max(1, self.config.runtime_snapshot_interval)
        if self.current_timestamp - self._last_runtime_snapshot_timestamp < interval:
            return
        self._last_runtime_snapshot_timestamp = self.current_timestamp

        try:
            balances = []
            open_orders = []
            seen_order_ids = set()

            def append_open_order(order, connector_name: str):
                if order.is_done or order.is_failure or order.is_cancelled or order.client_order_id in seen_order_ids:
                    return
                seen_order_ids.add(order.client_order_id)
                open_orders.append({
                    "id": order.client_order_id,
                    "connector": connector_name,
                    "exchange": connector_name.removesuffix("_paper_trade"),
                    "paper": connector_name.endswith("_paper_trade"),
                    "symbol": order.trading_pair,
                    "side": order.trade_type.name,
                    "order_type": order.order_type.name,
                    "price": self._decimal_text(order.price),
                    "amount": self._decimal_text(order.amount),
                    "filled": self._decimal_text(order.executed_amount_base),
                    "status": order.current_state.name,
                    "created_at": int(order.creation_timestamp * 1000),
                    "updated_at": int(order.last_update_timestamp * 1000),
                })

            def append_paper_limit_order(order, connector_name: str):
                """PaperTrade.limit_orders is the source of truth for funds actually held."""
                order_id = order.client_order_id
                if order_id in seen_order_ids:
                    return
                seen_order_ids.add(order_id)
                created_at = int(order.creation_timestamp / 1000)
                open_orders.append({
                    "id": order_id,
                    "connector": connector_name,
                    "exchange": connector_name.removesuffix("_paper_trade"),
                    "paper": True,
                    "symbol": order.trading_pair,
                    "side": "BUY" if order.is_buy else "SELL",
                    "order_type": "LIMIT",
                    "price": self._decimal_text(order.price),
                    "amount": self._decimal_text(order.quantity),
                    "filled": "0",
                    "status": "OPEN",
                    "created_at": created_at,
                    "updated_at": created_at,
                })

            paper_connectors = set()
            for connector_name, connector in self.connectors.items():
                exchange = connector_name.removesuffix("_paper_trade")
                is_paper = connector_name.endswith("_paper_trade")
                for asset, total in sorted(connector.get_all_balances().items()):
                    balances.append({
                        "connector": connector_name,
                        "exchange": exchange,
                        "paper": is_paper,
                        "asset": asset,
                        "total": self._decimal_text(total),
                        "available": self._decimal_text(connector.get_available_balance(asset)),
                    })
                if is_paper and hasattr(connector, "limit_orders"):
                    paper_connectors.add(connector_name)
                    for order in connector.limit_orders:
                        append_paper_limit_order(order, connector_name)
                    continue
                try:
                    for order in connector.in_flight_orders.values():
                        append_open_order(order, connector_name)
                except NotImplementedError:
                    # PaperTrade orders are held by their V2 executors, not the connector.
                    pass

            for executors in self.executor_orchestrator.active_executors.values():
                for executor in executors:
                    connector_name = getattr(executor.config, "connector_name", "")
                    if connector_name in paper_connectors:
                        continue
                    for order in getattr(executor, "_paper_in_flight_orders", {}).values():
                        append_open_order(order, connector_name)

            positions = []
            for controller_id, controller_positions in self.executor_orchestrator.get_positions_report().items():
                for position in controller_positions:
                    positions.append({
                        "id": f"{controller_id}:{position.connector_name}:{position.trading_pair}:{position.side.name}",
                        "controller_id": controller_id,
                        "connector": position.connector_name,
                        "exchange": position.connector_name.removesuffix("_paper_trade"),
                        "paper": position.connector_name.endswith("_paper_trade"),
                        "symbol": position.trading_pair,
                        "side": position.side.name,
                        "amount": self._decimal_text(position.amount),
                        "entry_price": self._decimal_text(position.breakeven_price),
                        "notional": self._decimal_text(position.amount_quote),
                        "unrealized_pnl": self._decimal_text(position.unrealized_pnl_quote),
                        "realized_pnl": self._decimal_text(position.realized_pnl_quote),
                        "fees": self._decimal_text(position.cum_fees_quote),
                        "pnl": self._decimal_text(position.global_pnl_quote),
                    })

            mark_prices = []
            market_health = {(item["connector"], item["symbol"]): item for item in self._market_data_health}
            seen_markets = set()
            for controller in self.controllers.values():
                connector_name = getattr(controller.config, "connector_name", None)
                trading_pair = getattr(controller.config, "trading_pair", None)
                if not connector_name or not trading_pair or (connector_name, trading_pair) in seen_markets:
                    continue
                seen_markets.add((connector_name, trading_pair))
                mark_price = self.market_data_provider.get_price_by_type(
                    connector_name, trading_pair, PriceType.MidPrice)
                health = market_health.get((connector_name, trading_pair), {})
                mark_prices.append({
                    "connector": connector_name,
                    "symbol": trading_pair,
                    "price": self._decimal_text(mark_price) if mark_price is not None and not mark_price.is_nan() else None,
                    "last_update": health.get("last_update"),
                    "age_seconds": health.get("age_seconds"),
                    "stale": health.get("stale", True),
                })

            snapshot = {
                "version": 1,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "strategy": self.config.script_file_name,
                "evolution_candidate_id": self.config.evolution_candidate_id,
                "evolution_deployment_id": self.config.evolution_deployment_id,
                "evolution_config_hash": self.config.evolution_config_hash,
                "balances": balances,
                "open_orders": open_orders,
                "positions": positions,
                "mark_prices": mark_prices,
                "market_data": self._market_data_health,
            }
            snapshot_file = Path(self.config.runtime_snapshot_file).name
            snapshot_path = Path("data") / snapshot_file
            temporary_path = snapshot_path.with_suffix(f"{snapshot_path.suffix}.tmp")
            temporary_path.write_text(json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            temporary_path.replace(snapshot_path)
        except Exception:
            self.logger().exception("Failed to write the read-only trading runtime snapshot.")

    def control_max_drawdown(self):
        if self.config.max_controller_drawdown_quote:
            self.check_max_controller_drawdown()
        if self.config.max_global_drawdown_quote:
            self.check_max_global_drawdown()

    def check_max_controller_drawdown(self):
        for controller_id, controller in self.controllers.items():
            if controller.status != RunnableStatus.RUNNING:
                continue
            controller_pnl = self.get_performance_report(controller_id).global_pnl_quote
            last_max_pnl = self.max_pnl_by_controller[controller_id]
            if controller_pnl > last_max_pnl:
                self.max_pnl_by_controller[controller_id] = controller_pnl
            else:
                current_drawdown = last_max_pnl - controller_pnl
                if current_drawdown > self.config.max_controller_drawdown_quote:
                    self.logger().info(f"Controller {controller_id} reached max drawdown. Stopping the controller.")
                    controller.stop()
                    executors_order_placed = self.filter_executors(
                        executors=self.get_executors_by_controller(controller_id),
                        filter_func=lambda x: x.is_active and not x.is_trading,
                    )
                    self.executor_orchestrator.execute_actions(
                        actions=[StopExecutorAction(controller_id=controller_id, executor_id=executor.id) for executor in executors_order_placed]
                    )
                    self.drawdown_exited_controllers.append(controller_id)

    def check_max_global_drawdown(self):
        current_global_pnl = sum([self.get_performance_report(controller_id).global_pnl_quote for controller_id in self.controllers.keys()])
        if current_global_pnl > self.max_global_pnl:
            self.max_global_pnl = current_global_pnl
        else:
            current_global_drawdown = self.max_global_pnl - current_global_pnl
            if current_global_drawdown > self.config.max_global_drawdown_quote:
                self.drawdown_exited_controllers.extend(list(self.controllers.keys()))
                self.logger().info("Global drawdown reached. Stopping the strategy.")
                self._is_stop_triggered = True
                HummingbotApplication.main_application().stop()

    def get_controller_report(self, controller_id: str) -> dict:
        """
        Get the full report for a controller including performance and custom info.
        """
        performance_report = self.controller_reports.get(controller_id, {}).get("performance")
        return {
            "performance": performance_report.dict() if performance_report else {},
            "custom_info": self.controllers[controller_id].get_custom_info()
        }

    def send_performance_report(self):
        if self.current_timestamp - self._last_performance_report_timestamp >= self.performance_report_interval and self._pub:
            controller_reports = {controller_id: self.get_controller_report(controller_id) for controller_id in self.controllers.keys()}
            self._pub(controller_reports)
            self._last_performance_report_timestamp = self.current_timestamp

    def check_manual_kill_switch(self):
        for controller_id, controller in self.controllers.items():
            if controller.config.manual_kill_switch and controller.status == RunnableStatus.RUNNING:
                self.logger().info(f"Manual cash out for controller {controller_id}.")
                controller.stop()
                executors_to_stop = self.get_executors_by_controller(controller_id)
                self.executor_orchestrator.execute_actions(
                    [StopExecutorAction(executor_id=executor.id,
                                        controller_id=executor.controller_id) for executor in executors_to_stop])
            if (not controller.config.manual_kill_switch
                    and controller_id not in self._market_data_paused_controllers
                    and controller.status == RunnableStatus.TERMINATED):
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
                    if "leverage" in config_dict and "trading_pair" in config_dict:
                        self.connectors[config_dict["connector_name"]].set_leverage(
                            leverage=config_dict["leverage"],
                            trading_pair=config_dict["trading_pair"])
        for connector_name, position_mode in connectors_position_mode.items():
            self.connectors[connector_name].set_position_mode(position_mode)

    def did_fail_order(self, order_failed_event: MarketOrderFailureEvent):
        """
        Handle order failure events by logging the error and stopping the strategy if necessary.
        """
        if order_failed_event.error_message and "position side" in order_failed_event.error_message.lower():
            connectors_position_mode = {}
            for controller_id, controller in self.controllers.items():
                config_dict = controller.config.model_dump()
                if "connector_name" in config_dict:
                    if self.is_perpetual(config_dict["connector_name"]):
                        if "position_mode" in config_dict:
                            connectors_position_mode[config_dict["connector_name"]] = config_dict["position_mode"]
            for connector_name, position_mode in connectors_position_mode.items():
                self.connectors[connector_name].set_position_mode(position_mode)
