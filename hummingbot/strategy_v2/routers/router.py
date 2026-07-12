from dataclasses import dataclass
from typing import Dict, List, Optional

from hummingbot.strategy_v2.routers.data_types import (
    MarketFeatures,
    MarketRegime,
    ReasonCode,
    RiskLevel,
    RouterAction,
    RouterDecision,
    StrategyCandidate,
    StrategyScore,
)


@dataclass
class RuleBasedRouterThresholds:
    low_bb_width_pct: float = 0.01
    high_bb_width_pct: float = 0.03
    trend_slope_pct: float = 0.001
    atr_spike_pct: float = 0.03
    volume_spike_zscore: float = 3.0
    range_break_buffer_pct: float = 0.001
    active_loss_limit_pct: float = 0.03


class RuleBasedStrategyRouter:
    def __init__(self, registry: Dict[str, StrategyCandidate], thresholds: RuleBasedRouterThresholds):
        self.registry = registry
        self.thresholds = thresholds

    def decide(self, features: MarketFeatures) -> RouterDecision:
        if not features.enough_data:
            return RouterDecision(
                timestamp=features.timestamp,
                regime=MarketRegime.UNKNOWN,
                action=RouterAction.OBSERVE,
                risk_level=RiskLevel.MEDIUM,
                active_strategy=features.active_strategy,
                recommended_strategy="protect_mode",
                confidence=0,
                position_scale=0,
                reason_codes=[ReasonCode.NOT_ENOUGH_DATA],
                message="等待足够的 K 线数据。",
            )

        risk_reasons = self._risk_reasons(features)
        if risk_reasons:
            return RouterDecision(
                timestamp=features.timestamp,
                regime=MarketRegime.EXTREME,
                action=RouterAction.PROTECT,
                risk_level=RiskLevel.EXTREME,
                active_strategy=features.active_strategy,
                recommended_strategy="protect_mode",
                confidence=0.9,
                position_scale=0,
                reason_codes=risk_reasons,
                message="风险门禁已触发；在路由新增风险前先保护资金。",
            )

        regime, regime_reasons, confidence = self._detect_regime(features)
        recommended_strategy = self._select_strategy(regime)
        action = self._select_action(features.active_strategy, recommended_strategy)
        risk_level = self._risk_level(regime)
        position_scale = self._position_scale(regime, confidence)
        reason_codes = regime_reasons
        if action == RouterAction.SWITCH:
            reason_codes = reason_codes + [ReasonCode.STRATEGY_MISMATCH if features.active_strategy else ReasonCode.NO_ACTIVE_STRATEGY]

        return RouterDecision(
            timestamp=features.timestamp,
            regime=regime,
            action=action,
            risk_level=risk_level,
            active_strategy=features.active_strategy,
            recommended_strategy=recommended_strategy,
            confidence=confidence,
            position_scale=position_scale,
            reason_codes=reason_codes,
            message=f"行情状态为 {regime.value}，策略从 {features.active_strategy or '无'} 路由到 {recommended_strategy}。",
        )

    def _risk_reasons(self, features: MarketFeatures) -> List[ReasonCode]:
        reasons = []
        if features.active_net_pnl_pct <= -self.thresholds.active_loss_limit_pct:
            reasons.append(ReasonCode.ACTIVE_LOSS_LIMIT)
        if features.atr_pct >= self.thresholds.atr_spike_pct:
            reasons.append(ReasonCode.ATR_SPIKE)
        if features.volume_zscore >= self.thresholds.volume_spike_zscore:
            reasons.append(ReasonCode.VOLUME_SPIKE)
        return reasons

    def _detect_regime(self, features: MarketFeatures) -> tuple[MarketRegime, List[ReasonCode], float]:
        upper_break = features.close_price > features.range_high * (1 + self.thresholds.range_break_buffer_pct)
        lower_break = features.close_price < features.range_low * (1 - self.thresholds.range_break_buffer_pct)
        if upper_break:
            return MarketRegime.BREAKOUT_UP, [ReasonCode.RANGE_BREAK_UP], 0.8
        if lower_break:
            return MarketRegime.BREAKOUT_DOWN, [ReasonCode.RANGE_BREAK_DOWN], 0.8

        if features.ema_fast > features.ema_slow and features.ema_slope_pct > self.thresholds.trend_slope_pct:
            return MarketRegime.TREND_UP, [ReasonCode.TREND_UP], min(0.85, 0.55 + abs(features.ema_slope_pct) * 100)
        if features.ema_fast < features.ema_slow and features.ema_slope_pct < -self.thresholds.trend_slope_pct:
            return MarketRegime.TREND_DOWN, [ReasonCode.TREND_DOWN], min(0.85, 0.55 + abs(features.ema_slope_pct) * 100)

        if features.bb_width_pct <= self.thresholds.low_bb_width_pct:
            return MarketRegime.RANGE_LOW_VOL, [ReasonCode.LOW_VOL_RANGE], 0.7
        if features.bb_width_pct <= self.thresholds.high_bb_width_pct:
            return MarketRegime.RANGE_HIGH_VOL, [ReasonCode.HIGH_VOL_RANGE], 0.65
        return MarketRegime.RANGE_HIGH_VOL, [ReasonCode.HIGH_VOL_RANGE], 0.55

    def _select_strategy(self, regime: MarketRegime) -> Optional[str]:
        enabled_candidates = [
            candidate for candidate in self.registry.values()
            if candidate.enabled and regime in candidate.supported_regimes
        ]
        if not enabled_candidates:
            return "protect_mode"
        return sorted(enabled_candidates, key=lambda candidate: candidate.priority)[0].name

    @staticmethod
    def _select_action(active_strategy: Optional[str], recommended_strategy: Optional[str]) -> RouterAction:
        if recommended_strategy in [None, "protect_mode"]:
            return RouterAction.PROTECT
        if active_strategy == recommended_strategy:
            return RouterAction.CONTINUE
        return RouterAction.SWITCH

    @staticmethod
    def _risk_level(regime: MarketRegime) -> RiskLevel:
        if regime in [MarketRegime.EXTREME, MarketRegime.BREAKOUT_UP, MarketRegime.BREAKOUT_DOWN]:
            return RiskLevel.HIGH
        if regime in [MarketRegime.TREND_UP, MarketRegime.TREND_DOWN, MarketRegime.RANGE_HIGH_VOL]:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    @staticmethod
    def _position_scale(regime: MarketRegime, confidence: float) -> float:
        if regime in [MarketRegime.EXTREME, MarketRegime.UNKNOWN]:
            return 0
        if regime in [MarketRegime.BREAKOUT_UP, MarketRegime.BREAKOUT_DOWN]:
            return min(0.5, confidence)
        return min(1.0, max(0.25, confidence))

    def rank_candidates(self, features: MarketFeatures, decision: Optional[RouterDecision] = None) -> List[StrategyScore]:
        decision = decision or self.decide(features)
        scores = []
        for candidate in self.registry.values():
            supported = decision.regime in candidate.supported_regimes
            reasons = []
            score = 0.0
            if candidate.name == "protect_mode":
                if decision.action == RouterAction.PROTECT:
                    score = 1.0
                    reasons.append("risk_gate")
                elif decision.regime == MarketRegime.UNKNOWN:
                    score = 0.5
                    reasons.append("fallback")
            elif supported:
                score = decision.confidence
                reasons.append(f"supports_{decision.regime.value}")
                score += max(0.0, (100 - candidate.priority) / 1000)
                if candidate.enabled:
                    reasons.append("enabled")
                else:
                    score *= 0.35
                    reasons.append("shadow_disabled")
            elif candidate.family.value == "observe":
                score = 0.05
                reasons.append("observe_only")

            scores.append(StrategyScore(
                name=candidate.name,
                family=candidate.family,
                enabled=candidate.enabled,
                supported=supported,
                score=round(min(1.0, score), 4),
                reasons=reasons,
            ))

        return sorted(scores, key=lambda candidate_score: candidate_score.score, reverse=True)
