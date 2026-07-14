from __future__ import annotations

from hummingbot.strategy_v2.routing.config import SwitchPolicy
from hummingbot.strategy_v2.routing.data_types import (
    LifecycleState,
    TransitionObservation,
    TransitionRecord,
)


class TransitionCoordinator:
    """Pure state machine for safe strategy replacement.

    It emits state only. Account workers remain responsible for side effects and
    must report ``old_drained``, ``new_started``, and canary health back to the
    coordinator.
    """

    def __init__(self, policy: SwitchPolicy):
        self.policy = policy

    def advance(
        self,
        record: TransitionRecord,
        observation: TransitionObservation,
        *,
        now: float,
    ) -> TransitionRecord:
        if observation.risk_triggered:
            return record.model_copy(
                update={
                    "state": LifecycleState.PROTECT,
                    "desired_strategy_id": None,
                    "confirmation_cycles": 0,
                    "state_entered_at": now,
                    "last_transition_at": now,
                    "last_error": "risk_triggered",
                }
            )

        state = record.state
        if state == LifecycleState.PROTECT:
            if not observation.risk_cleared:
                return record
            return record.model_copy(
                update={
                    "state": LifecycleState.STABLE,
                    "active_strategy_id": None,
                    "desired_strategy_id": observation.desired_strategy_id,
                    "previous_strategy_id": record.active_strategy_id,
                    "confirmation_cycles": 0,
                    "state_entered_at": now,
                    "last_transition_at": now,
                    "last_error": None,
                }
            )

        if state == LifecycleState.STABLE:
            return self._from_stable(record, observation, now)
        if state in {LifecycleState.CANDIDATE, LifecycleState.CONFIRMING}:
            return self._confirm(record, observation, now)
        if state == LifecycleState.DRAINING_OLD:
            return self._drain(record, observation, now)
        if state == LifecycleState.STARTING_NEW:
            return self._start(record, observation, now)
        if state == LifecycleState.CANARY:
            return self._canary(record, observation, now)
        if state == LifecycleState.ROLLBACK:
            return self._rollback(record, observation, now)
        return record

    def _from_stable(
        self,
        record: TransitionRecord,
        observation: TransitionObservation,
        now: float,
    ) -> TransitionRecord:
        desired = observation.desired_strategy_id
        if desired == record.active_strategy_id:
            return record.model_copy(update={"desired_strategy_id": desired})
        if desired is None and record.active_strategy_id is None:
            return record
        if now - record.last_transition_at < self.policy.cooldown_seconds:
            return record
        if (
            record.active_strategy_id
            and now - record.last_transition_at < self.policy.minimum_dwell_seconds
        ):
            return record
        if (
            record.active_strategy_id
            and desired is not None
            and observation.score_delta < self.policy.minimum_score_delta
        ):
            return record.model_copy(update={"desired_strategy_id": desired})
        return record.model_copy(
            update={
                "state": LifecycleState.CANDIDATE,
                "desired_strategy_id": desired,
                "confirmation_cycles": 1,
                "state_entered_at": now,
                "last_error": None,
            }
        )

    def _confirm(
        self,
        record: TransitionRecord,
        observation: TransitionObservation,
        now: float,
    ) -> TransitionRecord:
        desired = observation.desired_strategy_id
        if desired == record.active_strategy_id:
            return record.model_copy(
                update={
                    "state": LifecycleState.STABLE,
                    "desired_strategy_id": desired,
                    "confirmation_cycles": 0,
                    "state_entered_at": now,
                }
            )
        if desired != record.desired_strategy_id:
            return record.model_copy(
                update={
                    "state": LifecycleState.CANDIDATE,
                    "desired_strategy_id": desired,
                    "confirmation_cycles": 1,
                    "state_entered_at": now,
                }
            )
        confirmations = record.confirmation_cycles + 1
        if observation.score_delta < self.policy.minimum_score_delta:
            return record.model_copy(
                update={
                    "state": LifecycleState.CONFIRMING,
                    "confirmation_cycles": 0,
                }
            )
        if confirmations < self.policy.confirmation_cycles:
            return record.model_copy(
                update={
                    "state": LifecycleState.CONFIRMING,
                    "confirmation_cycles": confirmations,
                }
            )
        next_state = (
            LifecycleState.DRAINING_OLD
            if record.active_strategy_id
            else LifecycleState.STARTING_NEW
        )
        return record.model_copy(
            update={
                "state": next_state,
                "previous_strategy_id": record.active_strategy_id,
                "state_entered_at": now,
                "last_transition_at": now,
            }
        )

    def _drain(
        self,
        record: TransitionRecord,
        observation: TransitionObservation,
        now: float,
    ) -> TransitionRecord:
        if observation.old_drained:
            return record.model_copy(
                update={
                    "state": LifecycleState.STARTING_NEW,
                    "active_strategy_id": None,
                    "state_entered_at": now,
                    "last_transition_at": now,
                }
            )
        if now - record.state_entered_at >= self.policy.drain_timeout_seconds:
            return record.model_copy(
                update={
                    "state": LifecycleState.PROTECT,
                    "desired_strategy_id": None,
                    "state_entered_at": now,
                    "last_transition_at": now,
                    "last_error": "drain_timeout",
                }
            )
        return record

    def _start(
        self,
        record: TransitionRecord,
        observation: TransitionObservation,
        now: float,
    ) -> TransitionRecord:
        if observation.start_failed:
            return record.model_copy(
                update={
                    "state": LifecycleState.ROLLBACK,
                    "state_entered_at": now,
                    "last_transition_at": now,
                    "last_error": "start_failed",
                }
            )
        if observation.new_started:
            return record.model_copy(
                update={
                    "state": LifecycleState.CANARY,
                    "active_strategy_id": record.desired_strategy_id,
                    "state_entered_at": now,
                    "last_transition_at": now,
                }
            )
        if now - record.state_entered_at >= self.policy.drain_timeout_seconds:
            return record.model_copy(
                update={
                    "state": LifecycleState.ROLLBACK,
                    "state_entered_at": now,
                    "last_transition_at": now,
                    "last_error": "start_timeout",
                }
            )
        return record

    def _canary(
        self,
        record: TransitionRecord,
        observation: TransitionObservation,
        now: float,
    ) -> TransitionRecord:
        if not observation.canary_healthy:
            return record.model_copy(
                update={
                    "state": LifecycleState.ROLLBACK,
                    "state_entered_at": now,
                    "last_transition_at": now,
                    "last_error": "canary_unhealthy",
                }
            )
        if now - record.state_entered_at < self.policy.canary_seconds:
            return record
        return record.model_copy(
            update={
                "state": LifecycleState.STABLE,
                "previous_strategy_id": None,
                "confirmation_cycles": 0,
                "state_entered_at": now,
                "last_transition_at": now,
                "last_error": None,
            }
        )

    @staticmethod
    def _rollback(
        record: TransitionRecord,
        observation: TransitionObservation,
        now: float,
    ) -> TransitionRecord:
        if not observation.rollback_completed:
            return record
        return record.model_copy(
            update={
                "state": LifecycleState.STABLE,
                "active_strategy_id": record.previous_strategy_id,
                "desired_strategy_id": record.previous_strategy_id,
                "previous_strategy_id": None,
                "confirmation_cycles": 0,
                "state_entered_at": now,
                "last_transition_at": now,
                "last_error": None,
            }
        )
