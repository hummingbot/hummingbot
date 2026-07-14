from __future__ import annotations

from hummingbot.strategy_v2.routing.config import AISettings, ScoreWeights
from hummingbot.strategy_v2.routing.data_types import (
    AIRoutingSignal,
    FixedScoreComponents,
)


class DeterministicScorer:
    def __init__(self, weights: ScoreWeights, ai: AISettings):
        self.weights = weights
        self.ai = ai

    def score(
        self,
        strategy_id: str,
        components: FixedScoreComponents,
        *,
        now: float,
        ai_signal: AIRoutingSignal | None = None,
    ) -> tuple[float, float, float, bool]:
        fixed_score = (
            self.weights.regime_fit * components.regime_fit
            + self.weights.expected_edge_after_cost
            * components.expected_edge_after_cost
            + self.weights.execution_quality * components.execution_quality
            + self.weights.strategy_health * components.strategy_health
        )
        penalties = (
            components.switch_cost_penalty
            + components.concentration_penalty
            + components.correlation_penalty
        )
        fixed_score = _clamp(fixed_score - penalties, 0.0, 1.0)

        ai_adjustment = 0.0
        ai_applied = False
        if self._usable_ai_signal(ai_signal, now):
            cap = min(self.weights.ai_adjustment, self.ai.max_adjustment)
            ai_adjustment = _clamp(
                float(ai_signal.strategy_adjustments.get(strategy_id, 0.0)),
                -cap,
                cap,
            )
            ai_applied = strategy_id in ai_signal.strategy_adjustments
        final_score = _clamp(fixed_score + ai_adjustment, 0.0, 1.0)
        return fixed_score, ai_adjustment, final_score, ai_applied

    def _usable_ai_signal(self, signal: AIRoutingSignal | None, now: float) -> bool:
        if (
            not self.ai.enabled
            or self.ai.mode == "shadow"
            or signal is None
            or signal.abstain
        ):
            return False
        ttl = min(signal.ttl_seconds, self.ai.response_ttl_seconds)
        return 0 <= now - signal.observed_at <= ttl


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))
