from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from hummingbot.strategy_v2.routing.config import SwitchPolicy
from hummingbot.strategy_v2.routing.data_types import (
    LifecycleState,
    StrategySleeve,
    TransitionObservation,
    TransitionRecord,
    RoutePlan,
    RouteTarget,
)
from hummingbot.strategy_v2.routing.lifecycle import PersistentLifecycleGate
from hummingbot.strategy_v2.routing.transition import TransitionCoordinator
from hummingbot.strategy_v2.routing.worker import WorkerAction


class TransitionCoordinatorTest(TestCase):
    def setUp(self):
        self.policy = SwitchPolicy(
            minimum_score_delta=0.08,
            confirmation_cycles=3,
            minimum_dwell_seconds=0,
            cooldown_seconds=0,
            drain_timeout_seconds=30,
            canary_seconds=60,
        )
        self.coordinator = TransitionCoordinator(self.policy)
        self.record = TransitionRecord(
            account_id="binance-mm",
            sleeve=StrategySleeve.MARKET_MAKING,
            trading_pair="BTC-USDT",
            active_strategy_id="grid_strike",
            desired_strategy_id="grid_strike",
            state_entered_at=0,
            last_transition_at=0,
        )

    def test_switch_requires_confirmation_drain_start_and_canary(self):
        observation = TransitionObservation(
            desired_strategy_id="pmm_mister",
            score_delta=0.12,
        )
        record = self.coordinator.advance(self.record, observation, now=10)
        self.assertEqual(LifecycleState.CANDIDATE, record.state)
        record = self.coordinator.advance(record, observation, now=20)
        self.assertEqual(LifecycleState.CONFIRMING, record.state)
        record = self.coordinator.advance(record, observation, now=30)
        self.assertEqual(LifecycleState.DRAINING_OLD, record.state)

        record = self.coordinator.advance(
            record,
            TransitionObservation(desired_strategy_id="pmm_mister", old_drained=True),
            now=40,
        )
        self.assertEqual(LifecycleState.STARTING_NEW, record.state)
        self.assertIsNone(record.active_strategy_id)

        record = self.coordinator.advance(
            record,
            TransitionObservation(desired_strategy_id="pmm_mister", new_started=True),
            now=50,
        )
        self.assertEqual(LifecycleState.CANARY, record.state)
        self.assertEqual("pmm_mister", record.active_strategy_id)

        record = self.coordinator.advance(
            record,
            TransitionObservation(desired_strategy_id="pmm_mister"),
            now=111,
        )
        self.assertEqual(LifecycleState.STABLE, record.state)

    def test_switch_requires_consecutive_score_confirmation(self):
        desired = "pmm_mister"
        record = self.coordinator.advance(
            self.record,
            TransitionObservation(desired_strategy_id=desired, score_delta=0.12),
            now=10,
        )
        record = self.coordinator.advance(
            record,
            TransitionObservation(desired_strategy_id=desired, score_delta=0.01),
            now=20,
        )
        self.assertEqual(LifecycleState.CONFIRMING, record.state)
        self.assertEqual(0, record.confirmation_cycles)

        for now in (30, 40):
            record = self.coordinator.advance(
                record,
                TransitionObservation(desired_strategy_id=desired, score_delta=0.12),
                now=now,
            )
            self.assertEqual(LifecycleState.CONFIRMING, record.state)
        record = self.coordinator.advance(
            record,
            TransitionObservation(desired_strategy_id=desired, score_delta=0.12),
            now=50,
        )
        self.assertEqual(LifecycleState.DRAINING_OLD, record.state)

    def test_weak_switch_does_not_enter_candidate_state(self):
        record = self.coordinator.advance(
            self.record,
            TransitionObservation(
                desired_strategy_id="pmm_mister",
                score_delta=0.01,
            ),
            now=10,
        )
        self.assertEqual(LifecycleState.STABLE, record.state)

    def test_drain_timeout_enters_protect(self):
        record = self.record.model_copy(
            update={
                "state": LifecycleState.DRAINING_OLD,
                "desired_strategy_id": "pmm_mister",
                "state_entered_at": 10,
            }
        )

        record = self.coordinator.advance(
            record,
            TransitionObservation(desired_strategy_id="pmm_mister"),
            now=40,
        )

        self.assertEqual(LifecycleState.PROTECT, record.state)
        self.assertEqual("drain_timeout", record.last_error)

    def test_unhealthy_canary_rolls_back(self):
        record = self.record.model_copy(
            update={
                "state": LifecycleState.CANARY,
                "active_strategy_id": "pmm_mister",
                "desired_strategy_id": "pmm_mister",
                "previous_strategy_id": "grid_strike",
                "state_entered_at": 10,
            }
        )
        record = self.coordinator.advance(
            record,
            TransitionObservation(
                desired_strategy_id="pmm_mister", canary_healthy=False
            ),
            now=20,
        )
        self.assertEqual(LifecycleState.ROLLBACK, record.state)

        record = self.coordinator.advance(
            record,
            TransitionObservation(
                desired_strategy_id="grid_strike", rollback_completed=True
            ),
            now=30,
        )
        self.assertEqual(LifecycleState.STABLE, record.state)
        self.assertEqual("grid_strike", record.active_strategy_id)

    def test_risk_trigger_preempts_every_state(self):
        record = self.coordinator.advance(
            self.record,
            TransitionObservation(
                desired_strategy_id="pmm_mister", risk_triggered=True
            ),
            now=10,
        )

        self.assertEqual(LifecycleState.PROTECT, record.state)
        self.assertIsNone(record.desired_strategy_id)

    def test_persistent_gate_counts_unique_decisions_before_start(self):
        target = RouteTarget(
            account_id="binance-mm",
            sleeve="market_making",
            strategy_id="pmm_mister",
            candidate_id="candidate-1",
            config_hash="1" * 64,
            trading_pair="ETH-USDT",
            target_capital_quote=1000,
            score=0.8,
        )
        action = WorkerAction(
            account_id="binance-mm",
            worker_id="hummingbot-pmm-mister-paper",
            action="start",
            strategy_id="pmm_mister",
            candidate_id="candidate-1",
            config_hash="1" * 64,
        )

        def plan(decision_id):
            return RoutePlan(
                decision_id=decision_id,
                generated_at=100,
                effective_at=100,
                expires_at=400,
                environment="paper",
                allocations=[target],
                input_hash=decision_id.ljust(64, "0"),
            )

        with TemporaryDirectory() as directory:
            gate = PersistentLifecycleGate(
                self.policy,
                Path(directory) / "lifecycle.json",
            )
            first = gate.gate([action], plan("route-1"), now=100)[0]
            repeated = gate.gate([action], plan("route-1"), now=110)[0]
            second = gate.gate([action], plan("route-2"), now=120)[0]
            third = gate.gate([action], plan("route-3"), now=130)[0]
        self.assertEqual("blocked", first.action)
        self.assertEqual(first.reason_codes, repeated.reason_codes)
        self.assertIn("confirmation_cycles:2/3", second.reason_codes)
        self.assertEqual("start", third.action)
