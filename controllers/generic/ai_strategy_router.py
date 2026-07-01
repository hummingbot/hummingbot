from decimal import Decimal
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_core.core_schema import ValidationInfo

from hummingbot.core.data_type.common import MarketDict, OrderType, PositionMode, PriceType, TradeType
from hummingbot.data_feed.candles_feed.data_types import CandlesConfig
from hummingbot.strategy_v2.controllers import ControllerBase, ControllerConfigBase
from hummingbot.strategy_v2.executors.data_types import ConnectorPair
from hummingbot.strategy_v2.executors.grid_executor.data_types import GridExecutorConfig
from hummingbot.strategy_v2.executors.position_executor.data_types import PositionExecutorConfig, TripleBarrierConfig
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, ExecutorAction, StopExecutorAction
from hummingbot.strategy_v2.routers import RouterFeatureEngine, RuleBasedStrategyRouter, default_strategy_registry
from hummingbot.strategy_v2.routers.data_types import MarketFeatures, ReasonCode, RiskLevel, RouterAction, RouterDecision
from hummingbot.strategy_v2.routers.router import RuleBasedRouterThresholds
from hummingbot.strategy_v2.utils.common import parse_enum_value


class AIStrategyRouterConfig(ControllerConfigBase):
    controller_type: str = "generic"
    controller_name: str = "ai_strategy_router"

    connector_name: str = Field(
        default="binance_perpetual",
        json_schema_extra={"prompt": "Enter the connector name: ", "prompt_on_new": True},
    )
    trading_pair: str = Field(
        default="BTC-USDT",
        json_schema_extra={"prompt": "Enter the trading pair: ", "prompt_on_new": True},
    )
    candles_connector: Optional[str] = Field(default=None, json_schema_extra={"prompt_on_new": False})
    candles_trading_pair: Optional[str] = Field(default=None, json_schema_extra={"prompt_on_new": False})
    interval: str = Field(default="3m", json_schema_extra={"is_updatable": True})
    candles_records: int = Field(default=120, ge=60, json_schema_extra={"is_updatable": True})

    enable_trading: bool = Field(default=False, json_schema_extra={"is_updatable": True})
    router_cooldown: int = Field(default=300, ge=0, json_schema_extra={"is_updatable": True})
    max_active_executors: int = Field(default=1, ge=1, json_schema_extra={"is_updatable": True})
    protect_keep_position: bool = Field(default=False, json_schema_extra={"is_updatable": True})
    allow_short: bool = Field(default=False, json_schema_extra={"is_updatable": True})

    leverage: int = Field(default=1, ge=1)
    position_mode: PositionMode = PositionMode.HEDGE

    # Regime thresholds
    low_bb_width_pct: Decimal = Field(default=Decimal("0.01"), json_schema_extra={"is_updatable": True})
    high_bb_width_pct: Decimal = Field(default=Decimal("0.03"), json_schema_extra={"is_updatable": True})
    trend_slope_pct: Decimal = Field(default=Decimal("0.001"), json_schema_extra={"is_updatable": True})
    atr_spike_pct: Decimal = Field(default=Decimal("0.03"), json_schema_extra={"is_updatable": True})
    volume_spike_zscore: Decimal = Field(default=Decimal("3.0"), json_schema_extra={"is_updatable": True})
    range_break_buffer_pct: Decimal = Field(default=Decimal("0.001"), json_schema_extra={"is_updatable": True})
    active_loss_limit_pct: Decimal = Field(default=Decimal("0.03"), json_schema_extra={"is_updatable": True})

    # Grid route parameters
    grid_side: TradeType = Field(default=TradeType.BUY, json_schema_extra={"is_updatable": True})
    grid_range_pct: Decimal = Field(default=Decimal("0.006"), gt=0, json_schema_extra={"is_updatable": True})
    grid_take_profit_pct: Decimal = Field(default=Decimal("0.001"), gt=0, json_schema_extra={"is_updatable": True})
    grid_limit_price_spread: Decimal = Field(default=Decimal("0.003"), gt=0, json_schema_extra={"is_updatable": True})
    grid_min_spread_between_orders: Decimal = Field(default=Decimal("0.0005"), gt=0, json_schema_extra={"is_updatable": True})
    grid_min_order_amount_quote: Decimal = Field(default=Decimal("5"), gt=0, json_schema_extra={"is_updatable": True})
    grid_max_open_orders: int = Field(default=3, ge=1, json_schema_extra={"is_updatable": True})
    grid_order_frequency: int = Field(default=3, ge=0, json_schema_extra={"is_updatable": True})

    # Trend route parameters
    trend_stop_loss_pct: Optional[Decimal] = Field(default=Decimal("0.02"), json_schema_extra={"is_updatable": True})
    trend_take_profit_pct: Optional[Decimal] = Field(default=Decimal("0.03"), json_schema_extra={"is_updatable": True})
    trend_time_limit: Optional[int] = Field(default=60 * 45, json_schema_extra={"is_updatable": True})

    @field_validator("candles_connector", mode="before")
    @classmethod
    def set_candles_connector(cls, v, validation_info: ValidationInfo):
        if v is None or v == "":
            return validation_info.data.get("connector_name")
        return v

    @field_validator("candles_trading_pair", mode="before")
    @classmethod
    def set_candles_trading_pair(cls, v, validation_info: ValidationInfo):
        if v is None or v == "":
            return validation_info.data.get("trading_pair")
        return v

    @field_validator("position_mode", mode="before")
    @classmethod
    def validate_position_mode(cls, v: str) -> PositionMode:
        return parse_enum_value(PositionMode, v, "position_mode")

    @field_validator("grid_side", mode="before")
    @classmethod
    def validate_grid_side(cls, v: str) -> TradeType:
        return parse_enum_value(TradeType, v, "grid_side")

    def update_markets(self, markets: MarketDict) -> MarketDict:
        return markets.add_or_update(self.connector_name, self.trading_pair)

    @staticmethod
    def _paper_trade_base_connector(connector_name: str) -> str:
        return connector_name.replace("_paper_trade", "") if connector_name.endswith("_paper_trade") else connector_name


class AIStrategyRouter(ControllerBase):
    def __init__(self, config: AIStrategyRouterConfig, *args, **kwargs):
        super().__init__(config, *args, **kwargs)
        self.config = config
        self.registry = default_strategy_registry()
        self._last_action_timestamp = 0
        self._last_decision_key = None
        self._last_trade_gate_log_timestamp = 0
        self.market_data_provider.initialize_rate_sources([
            ConnectorPair(connector_name=self._market_data_connector_name(), trading_pair=self.config.trading_pair)
        ])

    async def update_processed_data(self):
        timestamp = self.market_data_provider.time()
        active_executors = self._active_executors()
        candles = self.market_data_provider.get_candles_df(
            connector_name=self._market_data_connector_name(),
            trading_pair=self.config.candles_trading_pair,
            interval=self.config.interval,
            max_records=self.config.candles_records,
        )
        mid_price = self._mid_price()
        features = RouterFeatureEngine.build_features(
            candles=candles,
            active_executors=active_executors,
            timestamp=timestamp,
            mid_price=mid_price,
        )
        router = self._router()
        decision = self._apply_config_constraints(router.decide(features))
        candidate_scores = router.rank_candidates(features, decision)
        self.processed_data = {
            "features": features,
            "decision": decision,
            "candidate_scores": candidate_scores,
            "registry": self.registry,
        }
        self._log_decision_change(decision)

    def determine_executor_actions(self) -> List[ExecutorAction]:
        decision = self.processed_data.get("decision")
        features = self.processed_data.get("features")
        if not isinstance(decision, RouterDecision) or not isinstance(features, MarketFeatures):
            return []
        if not self.config.enable_trading:
            return []
        if self._mid_price() is None:
            self._log_trade_gate("mid price is not ready; skipping executor action.")
            return []

        if self._in_cooldown():
            self._log_trade_gate("router cooldown active; skipping executor action.")
            return []

        active_executors = self._active_executors()
        actions: List[ExecutorAction] = []

        if decision.action in [RouterAction.PROTECT, RouterAction.STOP]:
            actions.extend(self._stop_actions(active_executors, keep_position=self.config.protect_keep_position))
        elif decision.action == RouterAction.SWITCH:
            if active_executors:
                actions.extend(self._stop_actions(active_executors, keep_position=False))
            elif len(active_executors) < self.config.max_active_executors:
                create_action = self._create_action_for_decision(decision, features)
                if create_action:
                    actions.append(create_action)
                else:
                    self.logger().info(
                        "AI Router trade gate: no create action generated for "
                        f"recommended={decision.recommended_strategy}, mid={features.mid_price:.4f}, "
                        f"scale={decision.position_scale:.2f}."
                    )

        if actions:
            self._last_action_timestamp = self.market_data_provider.time()
            self.logger().info(f"AI Router sending {len(actions)} executor action(s): {actions}")
        return actions

    def _create_action_for_decision(self, decision: RouterDecision, features: MarketFeatures) -> Optional[CreateExecutorAction]:
        if decision.recommended_strategy in ["grid_strike", "bollingrid"]:
            return self._create_grid_action(features, decision)
        if decision.recommended_strategy in ["trend_long", "trend_short"]:
            return self._create_trend_action(features, decision)
        return None

    def _apply_config_constraints(self, decision: RouterDecision) -> RouterDecision:
        if decision.recommended_strategy == "trend_short" and not self.config.allow_short:
            action = RouterAction.PROTECT if decision.active_strategy else RouterAction.OBSERVE
            return decision.model_copy(update={
                "action": action,
                "risk_level": RiskLevel.HIGH,
                "recommended_strategy": "protect_mode",
                "position_scale": 0,
                "reason_codes": decision.reason_codes + [ReasonCode.SHORT_DISABLED],
                "message": "Short route blocked by allow_short=False; protecting or observing instead.",
            })
        return decision

    def _create_grid_action(self, features: MarketFeatures, decision: RouterDecision) -> Optional[CreateExecutorAction]:
        if features.mid_price <= 0 or decision.position_scale <= 0:
            return None
        mid_price = Decimal(str(features.mid_price))
        range_pct = self.config.grid_range_pct
        start_price = mid_price * (Decimal("1") - range_pct)
        end_price = mid_price * (Decimal("1") + range_pct)
        limit_price = (
            start_price * (Decimal("1") - self.config.grid_limit_price_spread)
            if self.config.grid_side == TradeType.BUY
            else end_price * (Decimal("1") + self.config.grid_limit_price_spread)
        )
        amount_quote = self.config.total_amount_quote * Decimal(str(decision.position_scale))
        grid_order_type = OrderType.LIMIT if self._is_paper_trade_connector() else OrderType.LIMIT_MAKER
        return CreateExecutorAction(
            controller_id=self.config.id,
            executor_config=GridExecutorConfig(
                timestamp=self.market_data_provider.time(),
                connector_name=self.config.connector_name,
                trading_pair=self.config.trading_pair,
                start_price=start_price,
                end_price=end_price,
                limit_price=limit_price,
                side=self.config.grid_side,
                total_amount_quote=amount_quote,
                min_spread_between_orders=self.config.grid_min_spread_between_orders,
                min_order_amount_quote=self.config.grid_min_order_amount_quote,
                max_open_orders=self.config.grid_max_open_orders,
                max_orders_per_batch=1,
                order_frequency=self.config.grid_order_frequency,
                triple_barrier_config=TripleBarrierConfig(
                    take_profit=self.config.grid_take_profit_pct,
                    open_order_type=grid_order_type,
                    take_profit_order_type=grid_order_type,
                    stop_loss_order_type=OrderType.MARKET,
                    time_limit_order_type=OrderType.MARKET,
                ),
                leverage=self.config.leverage,
                coerce_tp_to_step=True,
            ),
        )

    def _create_trend_action(self, features: MarketFeatures, decision: RouterDecision) -> Optional[CreateExecutorAction]:
        if features.mid_price <= 0 or decision.position_scale <= 0:
            return None
        if decision.recommended_strategy == "trend_short" and not self.config.allow_short:
            return None
        side = TradeType.BUY if decision.recommended_strategy == "trend_long" else TradeType.SELL
        entry_price = Decimal(str(features.mid_price))
        amount_quote = self.config.total_amount_quote * Decimal(str(decision.position_scale))
        amount = amount_quote / entry_price
        return CreateExecutorAction(
            controller_id=self.config.id,
            executor_config=PositionExecutorConfig(
                timestamp=self.market_data_provider.time(),
                connector_name=self.config.connector_name,
                trading_pair=self.config.trading_pair,
                side=side,
                entry_price=entry_price,
                amount=amount,
                triple_barrier_config=TripleBarrierConfig(
                    stop_loss=self.config.trend_stop_loss_pct,
                    take_profit=self.config.trend_take_profit_pct,
                    time_limit=self.config.trend_time_limit,
                    open_order_type=OrderType.MARKET,
                    take_profit_order_type=OrderType.MARKET,
                    stop_loss_order_type=OrderType.MARKET,
                    time_limit_order_type=OrderType.MARKET,
                ),
                leverage=self.config.leverage,
            ),
        )

    def _stop_actions(self, active_executors, keep_position: bool) -> List[StopExecutorAction]:
        return [
            StopExecutorAction(
                controller_id=self.config.id,
                executor_id=executor.id,
                keep_position=keep_position,
            )
            for executor in active_executors
        ]

    def _router(self) -> RuleBasedStrategyRouter:
        thresholds = RuleBasedRouterThresholds(
            low_bb_width_pct=float(self.config.low_bb_width_pct),
            high_bb_width_pct=float(self.config.high_bb_width_pct),
            trend_slope_pct=float(self.config.trend_slope_pct),
            atr_spike_pct=float(self.config.atr_spike_pct),
            volume_spike_zscore=float(self.config.volume_spike_zscore),
            range_break_buffer_pct=float(self.config.range_break_buffer_pct),
            active_loss_limit_pct=float(self.config.active_loss_limit_pct),
        )
        return RuleBasedStrategyRouter(registry=self.registry, thresholds=thresholds)

    def _log_decision_change(self, decision: RouterDecision):
        decision_key = (
            decision.regime,
            decision.action,
            decision.recommended_strategy,
            tuple(decision.reason_codes),
        )
        if decision_key == self._last_decision_key:
            return
        self._last_decision_key = decision_key
        self.logger().info(
            "AI Router decision: "
            f"regime={decision.regime.value}, action={decision.action.value}, "
            f"active={decision.active_strategy or 'none'}, recommended={decision.recommended_strategy or 'none'}, "
            f"confidence={decision.confidence:.2f}, scale={decision.position_scale:.2f}, "
            f"reasons={[reason.value for reason in decision.reason_codes]}"
        )

    def _log_trade_gate(self, message: str):
        timestamp = self.market_data_provider.time()
        if timestamp - self._last_trade_gate_log_timestamp < 30:
            return
        self._last_trade_gate_log_timestamp = timestamp
        self.logger().info(f"AI Router trade gate: {message}")

    def _active_executors(self):
        return self.filter_executors(
            executors=self.executors_info,
            filter_func=lambda executor: executor.is_active,
        )

    def _mid_price(self) -> Optional[float]:
        try:
            price = self.market_data_provider.get_price_by_type(
                self.config.connector_name,
                self.config.trading_pair,
                PriceType.MidPrice,
            )
            return float(price)
        except Exception as exc:
            self.logger().debug(f"Mid price is not ready for {self.config.trading_pair}: {exc}")
            return None

    def _market_data_connector_name(self) -> str:
        connector_name = self.config.candles_connector or self.config.connector_name
        return self.config._paper_trade_base_connector(connector_name)

    def _is_paper_trade_connector(self) -> bool:
        return self.config.connector_name.endswith("_paper_trade")

    def _in_cooldown(self) -> bool:
        return self.market_data_provider.time() - self._last_action_timestamp < self.config.router_cooldown

    def get_candles_config(self) -> List[CandlesConfig]:
        return [
            CandlesConfig(
                connector=self._market_data_connector_name(),
                trading_pair=self.config.candles_trading_pair,
                interval=self.config.interval,
                max_records=self.config.candles_records,
            )
        ]

    def get_custom_info(self) -> dict:
        decision = self.processed_data.get("decision")
        features = self.processed_data.get("features")
        candidate_scores = self.processed_data.get("candidate_scores", [])
        return {
            "decision": decision.model_dump(mode="json") if isinstance(decision, RouterDecision) else {},
            "features": features.model_dump(mode="json") if isinstance(features, MarketFeatures) else {},
            "candidate_scores": [score.model_dump(mode="json") for score in candidate_scores[:8]],
            "enable_trading": self.config.enable_trading,
        }

    def to_format_status(self) -> List[str]:
        decision = self.processed_data.get("decision")
        features = self.processed_data.get("features")
        if not isinstance(decision, RouterDecision) or not isinstance(features, MarketFeatures):
            return ["AI Router: waiting for data."]

        lines = [
            "AI Strategy Router",
            f"Trading Enabled: {self.config.enable_trading}",
            f"Regime: {decision.regime.value} | Action: {decision.action.value} | Risk: {decision.risk_level.value}",
            f"Active: {decision.active_strategy or 'none'} | Recommended: {decision.recommended_strategy or 'none'}",
            f"Confidence: {decision.confidence:.2f} | Position Scale: {decision.position_scale:.2f}",
            f"Reasons: {', '.join(reason.value for reason in decision.reason_codes) or 'none'}",
            (
                f"Features: mid={features.mid_price:.4f}, atr={features.atr_pct:.4%}, "
                f"bb_width={features.bb_width_pct:.4%}, ema_slope={features.ema_slope_pct:.4%}, "
                f"vol_z={features.volume_zscore:.2f}"
            ),
        ]
        candidate_scores = self.processed_data.get("candidate_scores", [])
        if candidate_scores:
            formatted_scores = [
                f"{score.name}:{score.score:.2f}{'' if score.enabled else '*'}"
                for score in candidate_scores[:5]
            ]
            lines.append(f"Top Candidates: {', '.join(formatted_scores)} (* shadow)")
        return lines
