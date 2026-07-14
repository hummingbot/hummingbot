from __future__ import annotations

import json
from pathlib import Path

from hummingbot.strategy_v2.routing.config import SwitchPolicy
from hummingbot.strategy_v2.routing.data_types import (
    LifecycleState,
    RoutePlan,
    TransitionObservation,
    TransitionRecord,
)
from hummingbot.strategy_v2.routing.transition import TransitionCoordinator
from hummingbot.strategy_v2.routing.worker import WorkerAction


class PersistentLifecycleGate:
    """Connect RoutePlan decisions to the persistent transition state machine."""

    def __init__(self, policy: SwitchPolicy, state_path: Path):
        self.policy = policy
        self.state_path = state_path
        self.coordinator = TransitionCoordinator(policy)

    def gate(
        self,
        actions: list[WorkerAction],
        plan: RoutePlan,
        *,
        now: float,
    ) -> list[WorkerAction]:
        state = self._state()
        entries = state.setdefault("entries", {})
        targets = {row.account_id: row for row in plan.allocations}
        gated = []
        for action in actions:
            if action.action in {"blocked", "stop"}:
                gated.append(action)
                continue
            target = targets.get(action.account_id)
            if target is None:
                gated.append(action)
                continue
            key = f"{action.account_id}:{target.sleeve.value}:{target.trading_pair}"
            entry = entries.get(key) or {}
            record = self._record(entry, action, target.sleeve, target.trading_pair)
            same_decision = entry.get("last_decision_id") == plan.decision_id
            if action.action == "continue":
                record = self._advance_continue(record, target.strategy_id, now)
                gated.append(action)
            elif action.action == "start":
                if record.state == LifecycleState.DRAINING_OLD:
                    record = self.coordinator.advance(
                        record,
                        TransitionObservation(
                            desired_strategy_id=target.strategy_id,
                            old_drained=True,
                            score_delta=target.score,
                        ),
                        now=now,
                    )
                elif not same_decision:
                    record = self.coordinator.advance(
                        record,
                        TransitionObservation(
                            desired_strategy_id=target.strategy_id,
                            score_delta=target.score,
                        ),
                        now=now,
                    )
                gated.append(
                    action
                    if record.state == LifecycleState.STARTING_NEW
                    else self._confirmation_block(action, record)
                )
            elif action.action == "drain":
                if record.active_strategy_id is None:
                    record = record.model_copy(
                        update={
                            "active_strategy_id": "existing_runtime",
                            "desired_strategy_id": "existing_runtime",
                        }
                    )
                if not same_decision:
                    record = self.coordinator.advance(
                        record,
                        TransitionObservation(
                            desired_strategy_id=target.strategy_id,
                            score_delta=target.score,
                        ),
                        now=now,
                    )
                gated.append(
                    action
                    if record.state == LifecycleState.DRAINING_OLD
                    else self._confirmation_block(action, record)
                )
            else:
                gated.append(action)
            entries[key] = {
                "record": record.model_dump(mode="json"),
                "last_decision_id": plan.decision_id,
            }
        self._save_state(state)
        return gated

    def _record(self, entry, action, sleeve, trading_pair) -> TransitionRecord:
        payload = entry.get("record")
        if payload:
            return TransitionRecord.model_validate(payload)
        return TransitionRecord(
            account_id=action.account_id,
            sleeve=sleeve,
            trading_pair=trading_pair,
            state_entered_at=0,
            last_transition_at=0,
        )

    def _advance_continue(
        self,
        record: TransitionRecord,
        strategy_id: str,
        now: float,
    ) -> TransitionRecord:
        if record.state == LifecycleState.STARTING_NEW:
            return self.coordinator.advance(
                record,
                TransitionObservation(
                    desired_strategy_id=strategy_id,
                    new_started=True,
                ),
                now=now,
            )
        if record.state == LifecycleState.CANARY:
            return self.coordinator.advance(
                record,
                TransitionObservation(
                    desired_strategy_id=strategy_id,
                    canary_healthy=True,
                ),
                now=now,
            )
        return record

    def _confirmation_block(
        self,
        action: WorkerAction,
        record: TransitionRecord,
    ) -> WorkerAction:
        return action.model_copy(
            update={
                "action": "blocked",
                "reason_codes": [
                    f"transition_{record.state.value}",
                    (
                        f"confirmation_cycles:{record.confirmation_cycles}/"
                        f"{self.policy.confirmation_cycles}"
                    ),
                ],
            }
        )

    def _state(self) -> dict:
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"version": 1, "entries": {}}
        return payload if isinstance(payload, dict) else {"version": 1, "entries": {}}

    def _save_state(self, payload: dict) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(f"{self.state_path.suffix}.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.state_path)
