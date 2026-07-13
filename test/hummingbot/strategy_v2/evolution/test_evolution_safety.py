import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from unittest.mock import MagicMock

import subprocess

import yaml

from hummingbot.strategy_v2.evolution.config import EvolutionConfig
from hummingbot.strategy_v2.evolution.evidence import EvidenceCollector
from hummingbot.strategy_v2.evolution.models import (
    EvidenceSnapshot,
    EvolutionPolicy,
    StrategySpec,
    StrategyState,
)
from hummingbot.strategy_v2.evolution.paper import PaperCandidateStager
from hummingbot.strategy_v2.evolution.store import EvolutionStore


NOW = datetime(2026, 7, 13, tzinfo=timezone.utc)


def strategy(**overrides) -> StrategySpec:
    values = {
        "strategy_id": "pmm_mister",
        "name": "PMM",
        "family": "market_making",
        "thesis": "test",
        "target": "controllers.generic.pmm_mister",
        "evidence_file": "reports/evidence.json",
        "walk_forward_file": "reports/walk.json",
    }
    values.update(overrides)
    return StrategySpec(**values)


class EvidenceIntegrityTest(TestCase):
    def test_future_report_and_bad_artifact_hash_are_fail_closed(self):
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / "reports").mkdir()
            (root / "reports/evidence.json").write_text(
                json.dumps(
                    {
                        "strategies": {
                            "pmm_mister": {
                                "adapter_tests_passed": True,
                                "stop_path_verified": True,
                                "backtest_passed": True,
                                "walk_forward_passed": True,
                                "costs_included": True,
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            (root / "reports/walk.json").write_text(
                json.dumps(
                    {
                        "generated_at": "2027-07-13T00:00:00+00:00",
                        "validation_passed": True,
                        "summary": {"passed": True},
                    }
                ),
                encoding="utf-8",
            )
            artifact = root / "data/experiment/report.json"
            artifact.parent.mkdir(parents=True)
            artifact.write_text("{}", encoding="utf-8")
            accepted = root / "data/strategy-evolution/strategies/pmm_mister"
            accepted.mkdir(parents=True)
            (accepted / "accepted-evidence.json").write_text(
                json.dumps(
                    {
                        "accepted_at": NOW.isoformat(),
                        "artifact": "data/experiment/report.json",
                        "artifact_sha256": "not-the-real-hash",
                        "candidate_id": "candidate-a",
                    }
                ),
                encoding="utf-8",
            )

            snapshot = EvidenceCollector(root).collect(strategy(), now=NOW)

            self.assertIsNone(snapshot.accepted_candidate_id)
            self.assertTrue(
                any("future timestamp" in error for error in snapshot.source_errors)
            )
            self.assertTrue(
                any("hash mismatch" in error for error in snapshot.source_errors)
            )


class EvolutionStoreSafetyTest(TestCase):
    def test_jsonl_is_rotated_with_bounded_generations(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.dict("os.environ", {"STRATEGY_EVOLUTION_JSONL_MAX_BYTES": "1"}):
                store = EvolutionStore(root)
                store.record_alert(severity="warning", source="test", message="one")
                store.record_alert(severity="warning", source="test", message="two")

            events = root / "data/strategy-evolution/alerts/events.jsonl"
            self.assertTrue(events.exists())
            self.assertTrue(events.with_name("events.jsonl.1").exists())

    def test_alert_webhook_delivery_is_recorded_without_exposing_url(self):
        with TemporaryDirectory() as directory:
            response = MagicMock()
            response.__enter__.return_value.status = 204
            with (
                patch.dict(
                    "os.environ",
                    {
                        "STRATEGY_EVOLUTION_ALERT_WEBHOOK_URL": "https://alerts.invalid/hook"
                    },
                ),
                patch(
                    "hummingbot.strategy_v2.evolution.store.urllib.request.urlopen",
                    return_value=response,
                ) as post,
            ):
                alert = EvolutionStore(Path(directory)).record_alert(
                    severity="critical", source="test", message="unsafe"
                )

            self.assertEqual("delivered", alert["delivery"]["status"])
            self.assertEqual(204, alert["delivery"]["http_status"])
            self.assertNotIn("alerts.invalid", json.dumps(alert))
            post.assert_called_once()

    def test_corrupt_state_does_not_reset_to_generation_zero(self):
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            store = EvolutionStore(root)
            state_file = store.strategy_dir("alpha") / "state.json"
            state_file.parent.mkdir(parents=True)
            state_file.write_text("{broken", encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "corrupt evolution state"):
                store.load_state("alpha")

    def test_experiment_result_is_written_back_to_strategy_state(self):
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            store = EvolutionStore(root)
            state = StrategyState(strategy_id="alpha")
            store.save_cycle(state, {"strategy_id": "alpha"})

            store.start_experiment("alpha", "alpha-i0001")
            updated = store.finish_experiment(
                {
                    "strategy_id": "alpha",
                    "experiment_id": "alpha-i0001",
                    "verdict": "accept_candidate_evidence",
                    "candidate_id": "candidate-a",
                }
            )

            self.assertIsNone(updated.in_flight_experiment_id)
            self.assertEqual("candidate-a", updated.champion_candidate_id)
            self.assertEqual("accept_candidate_evidence", updated.last_outcome_verdict)

    def test_external_rate_limit_sets_persistent_retry_window(self):
        with TemporaryDirectory() as directory:
            store = EvolutionStore(Path(directory).resolve())
            store.save_cycle(
                StrategyState(strategy_id="alpha"), {"strategy_id": "alpha"}
            )
            store.start_experiment("alpha", "alpha-i0001")

            updated = store.finish_experiment(
                {
                    "strategy_id": "alpha",
                    "experiment_id": "alpha-i0001",
                    "verdict": "external_rate_limited",
                    "retry_after_seconds": 900,
                }
            )

            self.assertEqual(1, updated.experiment_failure_count)
            self.assertIsNotNone(updated.next_experiment_after)

    def test_finish_requires_matching_start_and_is_idempotent(self):
        with TemporaryDirectory() as directory:
            store = EvolutionStore(Path(directory).resolve())
            store.save_cycle(
                StrategyState(strategy_id="alpha"), {"strategy_id": "alpha"}
            )
            outcome = {
                "strategy_id": "alpha",
                "experiment_id": "alpha-i0001",
                "verdict": "reject_candidate_evidence",
            }

            with self.assertRaisesRegex(RuntimeError, "no start transaction"):
                store.finish_experiment(outcome)

            store.start_experiment("alpha", "alpha-i0001")
            first = store.finish_experiment(outcome)
            replay = store.finish_experiment(outcome)

            self.assertEqual("alpha-i0001", first.last_experiment_id)
            self.assertEqual(first, replay)
            with self.assertRaisesRegex(RuntimeError, "outcome replay mismatch"):
                store.finish_experiment({**outcome, "verdict": "different"})

    def test_restart_recovers_interrupted_experiment(self):
        with TemporaryDirectory() as directory:
            store = EvolutionStore(Path(directory).resolve())
            store.save_cycle(
                StrategyState(strategy_id="alpha"), {"strategy_id": "alpha"}
            )
            store.start_experiment("alpha", "alpha-i0001")

            recovered = store.recover_in_flight("alpha")
            state = store.load_state("alpha")

            self.assertTrue(recovered["recovered"])
            self.assertEqual("executor_interrupted", recovered["verdict"])
            self.assertIsNone(state.in_flight_experiment_id)
            self.assertEqual("alpha-i0001", state.last_experiment_id)

    def test_research_rejection_sets_persistent_exponential_cooldown(self):
        with TemporaryDirectory() as directory:
            policy = EvolutionPolicy(
                research_rejection_cooldown_seconds=60,
                maximum_research_rejection_cooldown_seconds=600,
            )
            store = EvolutionStore(Path(directory).resolve(), policy)
            store.save_cycle(
                StrategyState(strategy_id="alpha"), {"strategy_id": "alpha"}
            )
            store.start_experiment("alpha", "alpha-i0001")
            first = store.finish_experiment(
                {
                    "strategy_id": "alpha",
                    "experiment_id": "alpha-i0001",
                    "verdict": "reject_challenger",
                }
            )
            store.start_experiment("alpha", "alpha-i0002")
            second = store.finish_experiment(
                {
                    "strategy_id": "alpha",
                    "experiment_id": "alpha-i0002",
                    "verdict": "reject_challenger",
                }
            )

            first_ready = datetime.fromisoformat(first.next_experiment_after)
            second_ready = datetime.fromisoformat(second.next_experiment_after)
            self.assertEqual(2, second.experiment_failure_count)
            self.assertGreater((second_ready - first_ready).total_seconds(), 50)


class PaperCandidateStagerTest(TestCase):
    def test_pmm_bundle_changes_only_allowlisted_strategy_parameters(self):
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / "conf/controllers").mkdir(parents=True)
            (root / "conf/scripts").mkdir(parents=True)
            controller = {
                "id": "pmm-paper",
                "controller_type": "generic",
                "controller_name": "pmm_mister",
                "connector_name": "binance_paper_trade",
                "trading_pair": "ETH-USDT",
                "leverage": 1,
                "total_amount_quote": 1000,
                "global_stop_loss": 0.05,
                "open_order_type": "LIMIT",
                "take_profit_order_type": "LIMIT",
            }
            script = {
                "script_file_name": "v2_with_controllers.py",
                "controllers_config": ["conf_pmm_mister_paper.yml"],
                "max_global_drawdown_quote": 50,
            }
            (root / "conf/controllers/conf_pmm_mister_paper.yml").write_text(
                yaml.safe_dump(controller), encoding="utf-8"
            )
            (root / "conf/scripts/conf_pmm_mister_paper.yml").write_text(
                yaml.safe_dump(script), encoding="utf-8"
            )
            runtime = root / "data/runtime.json"
            runtime.parent.mkdir()
            runtime.write_text(
                json.dumps({"positions": [], "open_orders": []}), encoding="utf-8"
            )
            spec = strategy(runtime_file="data/runtime.json")
            config = EvolutionConfig(root, EvolutionPolicy(), (spec,))

            deployment = PaperCandidateStager(config).stage(
                spec,
                {
                    "candidate_id": "pmm_mister-candidate-a",
                    "parameters": {
                        "spread": 0.0015,
                        "take_profit": 0.004,
                        "refresh_seconds": 90,
                    },
                },
            )
            repeated_stage = PaperCandidateStager(config).stage(
                spec,
                {
                    "candidate_id": "pmm_mister-candidate-a",
                    "parameters": {
                        "spread": 0.0015,
                        "take_profit": 0.004,
                        "refresh_seconds": 90,
                    },
                },
            )

            generated = yaml.safe_load(
                (root / deployment["controller_config"]).read_text(encoding="utf-8")
            )
            generated_script = yaml.safe_load(
                (root / deployment["script_config"]).read_text(encoding="utf-8")
            )
            self.assertEqual("ready_to_start", deployment["status"])
            self.assertEqual(
                deployment["deployment_id"], repeated_stage["deployment_id"]
            )
            self.assertTrue(
                (
                    root
                    / "data/strategy-evolution/strategies/pmm_mister/paper/release-manifest.json"
                ).exists()
            )
            self.assertEqual("binance_paper_trade", generated["connector_name"])
            self.assertEqual(1, generated["leverage"])
            self.assertEqual(0.0015, generated["buy_spreads"])
            self.assertEqual(180, generated["buy_position_effectivization_time"])
            self.assertEqual(
                "pmm_mister-candidate-a", generated_script["evolution_candidate_id"]
            )
            candidate_runtime = root / deployment["runtime_file"]
            candidate_runtime.write_text(
                json.dumps(
                    {
                        "positions": [],
                        "open_orders": [],
                        "evolution_candidate_id": "pmm_mister-candidate-a",
                        "evolution_config_hash": deployment["config_hash"],
                    }
                ),
                encoding="utf-8",
            )
            verified = PaperCandidateStager(config).reconcile_and_maybe_activate(spec)
            self.assertEqual("active_verified", verified["status"])
            release_manifest = json.loads(
                (
                    root
                    / "data/strategy-evolution/strategies/pmm_mister/paper/release-manifest.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual("active_verified", release_manifest["status"])
            self.assertTrue(
                (
                    root
                    / "data/strategy-evolution/strategies/pmm_mister/paper/active.json"
                ).exists()
            )
            champion = PaperCandidateStager(config).promote_paper_candidate(
                spec, "pmm_mister-candidate-a"
            )
            self.assertEqual("paper_champion", champion["status"])
            repeated_champion = PaperCandidateStager(config).promote_paper_candidate(
                spec, "pmm_mister-candidate-a"
            )
            self.assertEqual(champion, repeated_champion)
            self.assertFalse(
                (
                    root
                    / "data/strategy-evolution/strategies/pmm_mister/paper/previous-champion.json"
                ).exists()
            )
            rollback = PaperCandidateStager(config).reconcile_and_maybe_activate(
                spec,
                EvidenceSnapshot(
                    collected_at=NOW.isoformat(),
                    runtime_exists=True,
                    runtime_fresh=True,
                    paper_only=False,
                ),
            )
            self.assertEqual("rollback_waiting_for_credentials", rollback["status"])
            self.assertIn("non_paper_connector_detected", rollback["rollback_reasons"])

    def test_auto_start_is_idempotent_while_runtime_verification_is_pending(self):
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            self._write_pmm_fixture(root, {"positions": [], "open_orders": []})
            spec = strategy(runtime_file="data/runtime.json")
            config = EvolutionConfig(
                root,
                EvolutionPolicy(auto_start_paper_candidates=True),
                (spec,),
            )
            stager = PaperCandidateStager(config)
            deployment = stager.stage(spec, self._candidate())
            evidence = EvidenceSnapshot(
                collected_at=NOW.isoformat(),
                runtime_exists=True,
                runtime_fresh=True,
                paper_only=True,
            )
            completed = subprocess.CompletedProcess([], 0, "started", "")

            with (
                patch.dict("os.environ", {"CONFIG_PASSWORD": "test"}),
                patch(
                    "hummingbot.strategy_v2.evolution.paper.subprocess.run",
                    return_value=completed,
                ) as run,
            ):
                first = stager.reconcile_and_maybe_activate(spec, evidence)
                second = stager.reconcile_and_maybe_activate(spec, evidence)

            self.assertEqual("startup_pending_runtime_verification", first["status"])
            self.assertEqual("startup_pending_runtime_verification", second["status"])
            self.assertEqual(1, run.call_count)
            self.assertEqual(deployment["deployment_id"], second["deployment_id"])

    def test_invalid_runtime_never_starts_paper_candidate(self):
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            self._write_pmm_fixture(root, None)
            (root / "data/runtime.json").write_text("{broken", encoding="utf-8")
            spec = strategy(runtime_file="data/runtime.json")
            config = EvolutionConfig(
                root,
                EvolutionPolicy(auto_start_paper_candidates=True),
                (spec,),
            )
            stager = PaperCandidateStager(config)
            stager.stage(spec, self._candidate())
            evidence = EvidenceSnapshot(
                collected_at=NOW.isoformat(),
                runtime_exists=True,
                runtime_fresh=True,
                paper_only=True,
                source_errors=["runtime JSON is invalid"],
            )

            with (
                patch.dict("os.environ", {"CONFIG_PASSWORD": "test"}),
                patch("hummingbot.strategy_v2.evolution.paper.subprocess.run") as run,
            ):
                result = stager.reconcile_and_maybe_activate(spec, evidence)

            self.assertEqual("waiting_for_valid_flat_runtime", result["status"])
            run.assert_not_called()

    def test_rollback_uses_deployment_runtime_not_baseline_snapshot(self):
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            self._write_pmm_fixture(root, {"positions": [], "open_orders": []})
            spec = strategy(runtime_file="data/runtime.json")
            config = EvolutionConfig(root, EvolutionPolicy(), (spec,))
            stager = PaperCandidateStager(config)
            deployment = stager.stage(spec, self._candidate())
            candidate_runtime = root / deployment["runtime_file"]
            candidate_runtime.write_text(
                json.dumps(
                    {
                        "positions": [{"amount": 1}],
                        "open_orders": [],
                        "evolution_candidate_id": deployment["candidate_id"],
                        "evolution_config_hash": deployment["config_hash"],
                    }
                ),
                encoding="utf-8",
            )
            strategy_dir = root / "data/strategy-evolution/strategies/pmm_mister/paper"
            (strategy_dir / "active.json").write_text(
                json.dumps({**deployment, "status": "active_verified"}),
                encoding="utf-8",
            )

            result = stager.reconcile_and_maybe_activate(
                spec,
                EvidenceSnapshot(
                    collected_at=NOW.isoformat(),
                    runtime_exists=True,
                    runtime_fresh=True,
                    paper_only=False,
                ),
            )

            self.assertEqual("rollback_blocked_open_exposure", result["status"])

    @staticmethod
    def _candidate():
        return {
            "candidate_id": "pmm_mister-candidate-a",
            "parameters": {
                "spread": 0.0015,
                "take_profit": 0.004,
                "refresh_seconds": 90,
            },
        }

    @staticmethod
    def _write_pmm_fixture(root: Path, runtime_payload: dict | None) -> None:
        (root / "conf/controllers").mkdir(parents=True)
        (root / "conf/scripts").mkdir(parents=True)
        (root / "data").mkdir(parents=True)
        controller = {
            "id": "pmm-paper",
            "controller_type": "generic",
            "controller_name": "pmm_mister",
            "connector_name": "binance_paper_trade",
            "trading_pair": "ETH-USDT",
            "leverage": 1,
        }
        script = {
            "script_file_name": "v2_with_controllers.py",
            "controllers_config": ["conf_pmm_mister_paper.yml"],
        }
        (root / "conf/controllers/conf_pmm_mister_paper.yml").write_text(
            yaml.safe_dump(controller), encoding="utf-8"
        )
        (root / "conf/scripts/conf_pmm_mister_paper.yml").write_text(
            yaml.safe_dump(script), encoding="utf-8"
        )
        if runtime_payload is not None:
            (root / "data/runtime.json").write_text(
                json.dumps(runtime_payload), encoding="utf-8"
            )
