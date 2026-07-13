import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from hummingbot.strategy_v2.evolution.automation import (
    IntelligentStrategySelector,
    SafeExperimentExecutor,
)
from hummingbot.strategy_v2.evolution.config import (
    EvolutionConfig,
    load_evolution_config,
)
from hummingbot.strategy_v2.evolution.engine import StrategyEvolutionEngine
from hummingbot.strategy_v2.evolution.models import (
    AutoActionSpec,
    CycleStatus,
    EvidenceSnapshot,
    EvolutionPolicy,
    EvolutionStage,
    ExperimentPlan,
    StrategySpec,
    StrategyState,
)
from hummingbot.strategy_v2.evolution.playbooks import CandidatePlaybook


NOW = datetime(2026, 7, 13, tzinfo=timezone.utc)


def spec(**overrides) -> StrategySpec:
    values = {
        "strategy_id": "alpha",
        "name": "Alpha",
        "family": "test",
        "thesis": "test thesis",
        "target": "test.target",
        "evidence_file": "reports/evidence.json",
        "walk_forward_file": "reports/walk.json",
        "minimum_paper_hours": 24,
        "minimum_paper_fills": 20,
    }
    values.update(overrides)
    return StrategySpec(**values)


def evidence(**overrides) -> EvidenceSnapshot:
    values = {
        "collected_at": NOW.isoformat(),
        "adapter_tests_passed": True,
        "stop_path_verified": True,
        "backtest_passed": True,
        "walk_forward_passed": True,
        "costs_included": True,
        "walk_forward_exists": True,
        "walk_forward_age_hours": 1,
        "paper_hours": 0,
        "paper_fills": 0,
        "paper_pnl_quote": 0,
    }
    values.update(overrides)
    return EvidenceSnapshot(**values)


class EvolutionEngineTest(TestCase):
    def setUp(self):
        self.policy = EvolutionPolicy()
        self.engine = StrategyEvolutionEngine(self.policy)

    def test_backtest_stage_advances_but_live_remains_manual(self):
        state, result = self.engine.advance(
            spec(),
            evidence(),
            StrategyState(strategy_id="alpha"),
            now=NOW,
        )

        self.assertEqual(EvolutionStage.BACKTEST_PASSED, state.stage)
        self.assertEqual(CycleStatus.ADVANCED, result.status)
        self.assertFalse(result.evidence.canary_approved)
        self.assertFalse(result.experiment.auto_executable)

    def test_paper_scorecard_stops_at_human_canary_review(self):
        previous = StrategyState(
            strategy_id="alpha", stage=EvolutionStage.BACKTEST_PASSED
        )
        state, result = self.engine.advance(
            spec(runtime_file="data/runtime.json", database_file="data/paper.sqlite"),
            evidence(
                runtime_exists=True,
                runtime_fresh=True,
                paper_only=True,
                paper_hours=30,
                paper_fills=25,
                paper_scorecard_passed=True,
                paper_scorecard_candidate_id="candidate-a",
                accepted_candidate_id="candidate-a",
                runtime_candidate_id="candidate-a",
                candidate_binding_valid=True,
            ),
            previous,
            now=NOW,
        )

        self.assertEqual(EvolutionStage.PAPER_PASSED, state.stage)
        self.assertEqual(CycleStatus.ADVANCED, result.status)
        self.assertEqual("request_manual_canary_review", result.experiment.action)
        self.assertEqual(0, result.experiment.change_budget)

    def test_collecting_sample_does_not_open_operational_circuit(self):
        runtime_spec = spec(
            runtime_file="data/runtime.json", database_file="data/paper.sqlite"
        )
        collecting = evidence(
            runtime_exists=True,
            runtime_fresh=True,
            paper_only=True,
            accepted_candidate_id="candidate-a",
            runtime_candidate_id="candidate-a",
            candidate_binding_valid=True,
        )
        current = StrategyState(
            strategy_id="alpha", stage=EvolutionStage.BACKTEST_PASSED
        )
        for _ in range(5):
            current, result = self.engine.advance(
                runtime_spec, collecting, current, now=NOW
            )

        self.assertEqual("healthy", current.diagnostic_signature)
        self.assertFalse(current.circuit_open)
        self.assertEqual(CycleStatus.OBSERVING, result.status)

    def test_unsafe_runtime_opens_circuit_immediately(self):
        runtime_spec = spec(
            runtime_file="data/runtime.json", database_file="data/paper.sqlite"
        )
        unsafe = evidence(runtime_exists=True, runtime_fresh=True, paper_only=False)
        current = StrategyState(
            strategy_id="alpha", stage=EvolutionStage.BACKTEST_PASSED
        )
        current, result = self.engine.advance(runtime_spec, unsafe, current, now=NOW)

        self.assertEqual(CycleStatus.CIRCUIT_OPEN, result.status)
        self.assertTrue(current.circuit_open)

    def test_paper_scorecard_cannot_bypass_stop_and_walk_forward_gates(self):
        unsafe_evidence = evidence(
            stop_path_verified=False,
            backtest_passed=False,
            walk_forward_passed=False,
            costs_included=False,
            paper_hours=30,
            paper_fills=25,
            paper_scorecard_passed=True,
        )

        state, result = self.engine.advance(
            spec(), unsafe_evidence, StrategyState(strategy_id="alpha"), now=NOW
        )

        self.assertEqual(EvolutionStage.SHADOW, state.stage)
        self.assertEqual(CycleStatus.BLOCKED, result.status)

    def test_circuit_is_sticky_until_verified_healthy_cycles(self):
        current = StrategyState(strategy_id="alpha", circuit_open=True)
        current, first = self.engine.advance(spec(), evidence(), current, now=NOW)
        current, second = self.engine.advance(
            spec(), evidence(recovery_verified=True), current, now=NOW
        )
        current, third = self.engine.advance(
            spec(), evidence(recovery_verified=True), current, now=NOW
        )

        self.assertEqual(CycleStatus.CIRCUIT_OPEN, first.status)
        self.assertEqual(CycleStatus.CIRCUIT_OPEN, second.status)
        self.assertFalse(current.circuit_open)
        self.assertNotEqual(CycleStatus.CIRCUIT_OPEN, third.status)

    def test_missing_test_dependency_is_not_a_strategy_failure(self):
        current, result = self.engine.advance(
            spec(checks=(("python3", "-m", "pytest"),)),
            evidence(
                checks_executed=True,
                check_results=[
                    {
                        "ok": False,
                        "classification": "environment_missing",
                        "error": "No module named tabulate",
                    }
                ],
            ),
            StrategyState(strategy_id="alpha", stage=EvolutionStage.BACKTEST_PASSED),
            now=NOW,
        )

        check_gate = next(
            gate for gate in result.gates if gate.key == "configured_checks"
        )
        self.assertEqual("missing", check_gate.status.value)
        self.assertEqual("healthy", current.diagnostic_signature)


class EvolutionConfigTest(TestCase):
    def test_live_actions_cannot_be_enabled(self):
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = root / "conf" / "strategy_evolution.json"
            config_path.parent.mkdir(parents=True)
            config_path.write_text(
                json.dumps(
                    {
                        "policy": {"allow_live_actions": True},
                        "strategies": [
                            {
                                "id": "alpha",
                                "evidence_file": "e.json",
                                "walk_forward_file": "w.json",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "does not permit live actions"):
                load_evolution_config(config_path, root=root)


class IntelligentAutomationTest(TestCase):
    def test_rate_limit_failure_gets_cooldown_instead_of_strategy_rejection(self):
        classification, retry_after = (
            SafeExperimentExecutor._classify_execution_failure(
                "urllib.error.HTTPError: HTTP Error 429: Too Many Requests"
            )
        )

        self.assertEqual("external_rate_limited", classification)
        self.assertEqual(900, retry_after)

    def test_selector_skips_observation_and_selects_one_safe_experiment(self):
        action = AutoActionSpec(
            action="run_cost_walk_forward",
            command=(
                "python3",
                "scripts/walk_forward_funding_arb.py",
                "--json-output",
                "{artifact_json}",
            ),
            artifact_json="data/strategy-evolution/experiments/{experiment_id}/report.json",
        )
        observe_spec = spec(strategy_id="observe")
        actionable_spec = spec(strategy_id="actionable", automation=(action,))
        config = EvolutionConfig(
            Path("/tmp"), EvolutionPolicy(), (observe_spec, actionable_spec)
        )
        selector = IntelligentStrategySelector(config)
        rows = [
            {
                "strategy_id": "observe",
                "status": "observing",
                "gates": [
                    {"key": "evidence_integrity", "status": "pass"},
                    {"key": "configured_checks", "status": "pass"},
                ],
                "experiment": {
                    "experiment_id": "observe-i1",
                    "hypothesis": "wait",
                    "action": "observe_only",
                    "change_budget": 0,
                    "success_criteria": [],
                    "stop_conditions": [],
                    "evidence_required": [],
                    "auto_executable": False,
                },
            },
            {
                "strategy_id": "actionable",
                "status": "blocked",
                "gates": [
                    {"key": "evidence_integrity", "status": "pass"},
                    {"key": "configured_checks", "status": "pass"},
                ],
                "experiment": {
                    "experiment_id": "actionable-i1",
                    "hypothesis": "test",
                    "action": "run_cost_walk_forward",
                    "change_budget": 1,
                    "success_criteria": ["pass"],
                    "stop_conditions": ["fail"],
                    "evidence_required": ["report"],
                    "auto_executable": True,
                },
            },
        ]

        selected = selector.select(rows)

        self.assertIsNotNone(selected)
        self.assertEqual("actionable", selected[0].strategy_id)

    def test_executor_rejects_non_allowlisted_script(self):
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data").mkdir()
            action = AutoActionSpec(
                action="run_cost_walk_forward",
                command=(
                    "python3",
                    "scripts/not_allowed.py",
                    "--json-output",
                    "{artifact_json}",
                ),
                artifact_json="data/strategy-evolution/experiments/{experiment_id}/report.json",
            )
            strategy = spec(automation=(action,))
            config = EvolutionConfig(root, EvolutionPolicy(), (strategy,))
            executor = SafeExperimentExecutor(config)
            plan = ExperimentPlan(
                experiment_id="alpha-i1",
                strategy_id="alpha",
                hypothesis="test",
                action="run_cost_walk_forward",
                change_budget=1,
                success_criteria=("pass",),
                stop_conditions=("fail",),
                evidence_required=("report",),
                auto_executable=True,
            )

            outcome = executor.execute(strategy, plan)

            self.assertEqual("safety_rejected", outcome.verdict)
            self.assertEqual("rejected", outcome.status)

    def test_executor_completes_allowlisted_experiment_and_accepts_evidence(self):
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as directory:
            root = Path(directory)
            action = AutoActionSpec(
                action="run_cost_walk_forward",
                command=(
                    "python3",
                    "scripts/walk_forward_pmm_mister.py",
                    "--candidates-json",
                    "{candidate_json}",
                    "--json-output",
                    "{artifact_json}",
                    "--markdown-output",
                    "{artifact_md}",
                ),
                artifact_json="data/strategy-evolution/experiments/{experiment_id}/report.json",
            )
            strategy = spec(strategy_id="pmm_mister", automation=(action,))
            config = EvolutionConfig(root, EvolutionPolicy(), (strategy,))
            executor = SafeExperimentExecutor(config)
            plan = ExperimentPlan(
                experiment_id="pmm_mister-i0001-cost_walk_forward",
                strategy_id="pmm_mister",
                hypothesis="validate candidate",
                action="run_cost_walk_forward",
                change_budget=1,
                success_criteria=("pass",),
                stop_conditions=("fail",),
                evidence_required=("report",),
                auto_executable=True,
            )

            def completed(command, **_kwargs):
                artifact = Path(command[command.index("--json-output") + 1])
                artifact.write_text(
                    json.dumps(
                        {
                            "generated_at": NOW.isoformat(),
                            "strategy": "pmm_mister",
                            "validation_passed": True,
                            "configuration": {"start": 1, "end": 2},
                            "cost_model": {"fee_rate": 0.001},
                            "summary": {
                                "passed": True,
                                "completed_folds": 3,
                                "profitable_fold_ratio": 1.0,
                                "total_adjusted_net_quote": 12.5,
                                "maximum_drawdown_pct": 0.01,
                                "total_positions": 30,
                            },
                            "folds": [
                                {
                                    "status": "completed",
                                    "selected_parameters": {
                                        "spread": 0.002,
                                        "take_profit": 0.003,
                                        "refresh_seconds": 120,
                                    },
                                },
                                {
                                    "status": "completed",
                                    "selected_parameters": {
                                        "spread": 0.002,
                                        "take_profit": 0.003,
                                        "refresh_seconds": 120,
                                    },
                                },
                                {
                                    "status": "completed",
                                    "selected_parameters": {
                                        "spread": 0.002,
                                        "take_profit": 0.003,
                                        "refresh_seconds": 120,
                                    },
                                },
                            ],
                        }
                    ),
                    encoding="utf-8",
                )
                return subprocess.CompletedProcess(command, 0, "ok", "")

            with (
                patch.object(executor, "_git_status", side_effect=[set(), set()]),
                patch.object(executor, "_run_experiment", side_effect=completed),
            ):
                outcome = executor.execute(strategy, plan)

            self.assertEqual("completed", outcome.status, outcome)
            self.assertEqual("accept_candidate_evidence", outcome.verdict)
            accepted = json.loads(
                (
                    root
                    / "data/strategy-evolution/strategies/pmm_mister/accepted-evidence.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(plan.experiment_id, accepted["experiment_id"])

    def test_failed_validation_enters_negative_feedback_lineage(self):
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as directory:
            root = Path(directory)
            action = AutoActionSpec(
                action="run_cost_walk_forward",
                command=(
                    "python3",
                    "scripts/walk_forward_pmm_mister.py",
                    "--candidates-json",
                    "{candidate_json}",
                    "--json-output",
                    "{artifact_json}",
                    "--markdown-output",
                    "{artifact_md}",
                ),
                artifact_json="data/strategy-evolution/experiments/{experiment_id}/report.json",
            )
            strategy = spec(strategy_id="pmm_mister", automation=(action,))
            executor = SafeExperimentExecutor(
                EvolutionConfig(root, EvolutionPolicy(), (strategy,))
            )
            plan = ExperimentPlan(
                experiment_id="pmm_mister-i0001-cost_walk_forward",
                strategy_id="pmm_mister",
                hypothesis="validate candidate",
                action="run_cost_walk_forward",
                change_budget=1,
                success_criteria=("pass",),
                stop_conditions=("fail",),
                evidence_required=("report",),
                auto_executable=True,
            )

            def completed(command, **_kwargs):
                candidates = json.loads(
                    Path(command[command.index("--candidates-json") + 1]).read_text(
                        encoding="utf-8"
                    )
                )
                selected = candidates["candidates"][0]
                artifact = Path(command[command.index("--json-output") + 1])
                artifact.write_text(
                    json.dumps(
                        {
                            "strategy": "pmm_mister",
                            "validation_passed": False,
                            "configuration": {"start": 1, "end": 2},
                            "cost_model": {"fee_rate": 0.001},
                            "summary": {
                                "passed": False,
                                "completed_folds": 3,
                                "profitable_fold_ratio": 0,
                                "total_adjusted_net_quote": 0,
                                "maximum_drawdown_pct": 0,
                                "total_positions": 0,
                            },
                            "folds": [
                                {
                                    "status": "completed",
                                    "selected_parameters": selected,
                                }
                                for _ in range(3)
                            ],
                        }
                    ),
                    encoding="utf-8",
                )
                return subprocess.CompletedProcess(command, 0, "ok", "")

            with (
                patch.object(executor, "_git_status", side_effect=[set(), set()]),
                patch.object(executor, "_run_experiment", side_effect=completed),
            ):
                outcome = executor.execute(strategy, plan)

            evaluation = json.loads(
                (
                    root
                    / "data/strategy-evolution/strategies/pmm_mister/evaluations"
                    / f"{plan.experiment_id}.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual("reject_challenger", outcome.verdict)
            self.assertEqual("reject_challenger", evaluation["decision"])
            self.assertEqual(3, len(evaluation["proposed_parameters"]))
            self.assertIn("no_oos_positions", evaluation["reason_codes"])

    def test_playbook_changes_only_one_parameter_axis(self):
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / "reports" / "pmm.json"
            report.parent.mkdir(parents=True)
            report.write_text(
                json.dumps(
                    {
                        "folds": [
                            {
                                "selected_parameters": {
                                    "spread": 0.002,
                                    "take_profit": 0.003,
                                    "refresh_seconds": 120,
                                }
                            },
                            {
                                "selected_parameters": {
                                    "spread": 0.002,
                                    "take_profit": 0.003,
                                    "refresh_seconds": 120,
                                }
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            strategy = spec(
                strategy_id="pmm_mister", walk_forward_file="reports/pmm.json"
            )
            plan = ExperimentPlan(
                experiment_id="pmm_mister-i0001-cost_walk_forward",
                strategy_id="pmm_mister",
                hypothesis="test spread",
                action="run_cost_walk_forward",
                change_budget=1,
                success_criteria=("pass",),
                stop_conditions=("fail",),
                evidence_required=("report",),
                auto_executable=True,
            )

            payload = CandidatePlaybook(root).generate(
                strategy, plan, root / "candidates.json"
            )

            self.assertEqual("spread", payload["single_axis"])
            baseline = payload["candidates"][0]
            for candidate in payload["candidates"][1:]:
                changed = [key for key in baseline if baseline[key] != candidate[key]]
                self.assertEqual(["spread"], changed)
