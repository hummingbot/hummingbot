import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from hummingbot.strategy_v2.routing.adapters import (
    EvolutionCandidateAdapter,
    account_snapshot_from_runtime,
    merge_runtime_account_snapshots,
)
from hummingbot.strategy_v2.routing.ai_provider import DeepSeekRoutingClient
from hummingbot.strategy_v2.routing.config import load_routing_config
from hummingbot.strategy_v2.routing.data_types import (
    CandidateSignal,
    FixedScoreComponents,
    MarketState,
)
from hummingbot.strategy_v2.routing.release import ReleaseManifest, StrategyRelease
from hummingbot.strategy_v2.routing.service import StrategyRouterService
from hummingbot.strategy_v2.routing.transfer import (
    PaperTransferRequest,
    PaperTransferSimulator,
)
from hummingbot.strategy_v2.routing.worker import PaperWorkerManager
from hummingbot.strategy_v2.routing.worker import WorkerAction


ROOT = Path(__file__).resolve().parents[4]
CONFIG = ROOT / "reports/examples/strategy_router_accounts.example.yml"
NOW = 1_783_887_600.0


def release(controller_ref: str = "conf/controllers/candidate.yml"):
    return StrategyRelease(
        strategy_id="pmm_mister",
        candidate_id="pmm_mister-candidate-1",
        config_hash="1" * 64,
        artifact_ref="conf/scripts/candidate.yml",
        stage="waiting_for_credentials",
        allowed_environments=["paper"],
        generated_at=NOW,
        evidence_refs=[controller_ref],
    )


class RuntimeIntegrationTest(TestCase):
    def setUp(self):
        self.config = load_routing_config(CONFIG)
        self.market = MarketState(
            timestamp=NOW,
            symbol="ETH-USDT",
            trend_strength=0.2,
            realized_volatility=0.1,
            liquidity_bucket="healthy",
        )

    def test_runtime_snapshot_becomes_fail_closed_account_snapshot(self):
        payload = {
            "generated_at": "2026-07-12T20:20:00+00:00",
            "evolution_candidate_id": "candidate-1",
            "balances": [
                {
                    "paper": True,
                    "asset": "USDT",
                    "total": "2500",
                    "available": "2200",
                }
            ],
            "positions": [
                {"paper": True, "side": "BUY", "notional": "200", "pnl": "-5"}
            ],
            "open_orders": [{"paper": True}],
            "market_data": [{"stale": False}],
        }
        with TemporaryDirectory() as directory:
            path = Path(directory) / "runtime.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            snapshot = account_snapshot_from_runtime("binance-mm", path)
        self.assertEqual(2495, snapshot.equity_quote)
        self.assertEqual(200, snapshot.gross_exposure_quote)
        self.assertEqual(5, snapshot.drawdown_quote)
        self.assertTrue(snapshot.data_fresh)

    def test_runtime_mapping_replaces_bootstrap_snapshot(self):
        runtime = {
            "generated_at": "2026-07-12T20:20:00+00:00",
            "balances": [
                {
                    "paper": True,
                    "asset": "USDT",
                    "total": "3000",
                    "available": "2800",
                }
            ],
            "positions": [],
            "open_orders": [],
            "market_data": [{"stale": False}],
        }
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data").mkdir()
            (root / "data/runtime.json").write_text(
                json.dumps(runtime), encoding="utf-8"
            )
            mapping = root / "mapping.json"
            mapping.write_text(
                json.dumps(
                    {"runtime_snapshots": {"binance-mm": {"path": "data/runtime.json"}}}
                ),
                encoding="utf-8",
            )
            merged = merge_runtime_account_snapshots(
                root,
                mapping,
                {
                    "binance-mm": self._bootstrap_snapshot(),
                },
            )
        self.assertEqual(3000, merged["binance-mm"].equity_quote)

    def test_evolution_candidate_adapter_reads_controller_artifact(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            controller = root / "conf/controllers/candidate.yml"
            controller.parent.mkdir(parents=True)
            controller.write_text(
                "\n".join(
                    [
                        "connector_name: binance_paper_trade",
                        "trading_pair: ETH-USDT",
                        "total_amount_quote: 1000",
                        "buy_spreads: 0.002",
                        "sell_spreads: 0.002",
                        "position_side: BUY",
                    ]
                ),
                encoding="utf-8",
            )
            manifest = ReleaseManifest(
                version=1,
                generated_at=NOW,
                releases=[release()],
            )
            candidates = EvolutionCandidateAdapter(root, self.config).build(
                manifest, self.market
            )
        self.assertEqual(1, len(candidates))
        self.assertEqual("binance_paper_trade", candidates[0].connector)
        self.assertEqual(1000, candidates[0].requested_capital_quote)

    def test_deepseek_adapter_bounds_json_adjustments(self):
        settings = self.config.ai.model_copy(update={"enabled": True, "mode": "active"})

        def transport(url, headers, body, timeout):
            self.assertTrue(url.endswith("/chat/completions"))
            self.assertIn("Authorization", headers)
            self.assertTrue(body)
            self.assertEqual(settings.request_timeout_seconds, timeout)
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "abstain": False,
                                    "ttl_seconds": 300,
                                    "confidence": 0.8,
                                    "strategy_adjustments": {"pmm_mister": 9},
                                    "reason_codes": ["range"],
                                }
                            )
                        }
                    }
                ]
            }

        candidate = CandidateSignal(
            strategy_id="pmm_mister",
            trading_pair="ETH-USDT",
            requested_capital_quote=1000,
            score_components=FixedScoreComponents(
                regime_fit=0.8,
                expected_edge_after_cost=0.7,
                execution_quality=0.9,
                strategy_health=0.8,
            ),
        )
        with (
            TemporaryDirectory() as directory,
            patch.dict("os.environ", {"DEEPSEEK_API_KEY": "test-key"}),
        ):
            client = DeepSeekRoutingClient(
                settings,
                Path(directory) / "circuit.json",
                transport=transport,
                clock=lambda: NOW,
            )
            signal = client.evaluate(self.market, [candidate])
        self.assertIsNotNone(signal)
        self.assertEqual(
            settings.max_adjustment, signal.strategy_adjustments["pmm_mister"]
        )

    def test_worker_manager_plans_exact_release_start_without_side_effects(self):
        manifest = ReleaseManifest(
            version=1,
            generated_at=NOW,
            releases=[release()],
        )
        from hummingbot.strategy_v2.routing.data_types import RoutePlan, RouteTarget

        plan = RoutePlan(
            decision_id="route-test",
            generated_at=NOW,
            effective_at=NOW,
            expires_at=NOW + 300,
            environment="paper",
            allocations=[
                RouteTarget(
                    account_id="binance-mm",
                    sleeve="market_making",
                    strategy_id="pmm_mister",
                    candidate_id="pmm_mister-candidate-1",
                    config_hash="1" * 64,
                    trading_pair="ETH-USDT",
                    target_capital_quote=1000,
                    score=0.8,
                )
            ],
            input_hash="1" * 64,
        )
        with TemporaryDirectory() as directory:
            manager = PaperWorkerManager(
                ROOT,
                self.config,
                Path(directory) / "workers.json",
                container_probe=lambda _: False,
            )
            actions = manager.plan_actions(plan, manifest)
        self.assertEqual("start", actions[0].action)
        self.assertEqual("hummingbot-pmm-mister-paper", actions[0].worker_id)

    def test_worker_manager_never_duplicates_an_unmanaged_running_container(self):
        manifest = ReleaseManifest(
            version=1,
            generated_at=NOW,
            releases=[release()],
        )
        from hummingbot.strategy_v2.routing.data_types import RoutePlan, RouteTarget

        plan = RoutePlan(
            decision_id="route-test-running",
            generated_at=NOW,
            effective_at=NOW,
            expires_at=NOW + 300,
            environment="paper",
            allocations=[
                RouteTarget(
                    account_id="binance-mm",
                    sleeve="market_making",
                    strategy_id="pmm_mister",
                    candidate_id="pmm_mister-candidate-1",
                    config_hash="1" * 64,
                    trading_pair="ETH-USDT",
                    target_capital_quote=1000,
                    score=0.8,
                )
            ],
            input_hash="2" * 64,
        )
        with TemporaryDirectory() as directory:
            manager = PaperWorkerManager(
                ROOT,
                self.config,
                Path(directory) / "workers.json",
                container_probe=lambda _: True,
            )
            actions = manager.plan_actions(plan, manifest)
        self.assertEqual("blocked", actions[0].action)
        self.assertIn("unmanaged_running_worker", actions[0].reason_codes)

    def test_legacy_adoption_requires_running_verifiable_paper_worker(self):
        runtime = {
            "balances": [{"paper": True}],
            "open_orders": [{"paper": True}],
            "positions": [],
        }
        with TemporaryDirectory() as directory:
            runtime_path = Path(directory) / "runtime.json"
            runtime_path.write_text(json.dumps(runtime), encoding="utf-8")
            manager = PaperWorkerManager(
                ROOT,
                self.config,
                Path(directory) / "workers.json",
                container_probe=lambda _: True,
            )
            worker = manager.adopt_legacy_paper_worker(
                "binance-mm",
                runtime_path,
                approved_by="paper-operator",
            )
            reconciled = manager.reconcile_runtime("binance-mm", runtime_path)
        self.assertTrue(worker["legacy"])
        self.assertEqual("running", reconciled["status"])
        self.assertFalse(reconciled["reconcile_blockers"])

    def test_drain_never_stops_worker_without_restart_credentials(self):
        action = WorkerAction(
            account_id="binance-mm",
            worker_id="hummingbot-pmm-mister-paper",
            action="drain",
            strategy_id="pmm_mister",
            candidate_id="candidate-1",
            config_hash="1" * 64,
        )
        manifest = ReleaseManifest(
            version=1,
            generated_at=NOW,
            releases=[release()],
        )
        with TemporaryDirectory() as directory:
            manager = PaperWorkerManager(
                ROOT,
                self.config,
                Path(directory) / "workers.json",
                container_probe=lambda _: True,
            )
            with (
                patch.dict("os.environ", {}, clear=True),
                patch.object(manager, "_stop") as stop,
            ):
                with self.assertRaisesRegex(ValueError, "CONFIG_PASSWORD"):
                    manager.apply([action], manifest)
                stop.assert_not_called()

    def test_paper_transfer_is_manual_idempotent_and_preserves_reserve(self):
        with TemporaryDirectory() as directory:
            simulator = PaperTransferSimulator(
                self.config,
                Path(directory) / "balances.json",
                Path(directory) / "transfers.jsonl",
                clock=lambda: NOW,
            )
            simulator.seed({"binance-treasury": 5000, "binance-mm": 0})
            request = PaperTransferRequest(
                transfer_id="transfer-1",
                source_account_id="binance-treasury",
                target_account_id="binance-mm",
                amount_quote=500,
                approved_by="paper-operator",
                requested_at=NOW,
            )
            first = simulator.execute(request)
            second = simulator.execute(request)
        self.assertEqual("simulated", first["status"])
        self.assertEqual(first, second)
        self.assertEqual(4500, first["balances_after"]["binance-treasury"])

    def test_service_runs_full_release_to_worker_plan_pipeline(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "conf/controllers").mkdir(parents=True)
            (root / "conf").mkdir(exist_ok=True)
            (root / "conf/strategy_evolution.json").write_text(
                json.dumps({"policy": {"auto_start_paper_candidates": False}}),
                encoding="utf-8",
            )
            (root / "conf/controllers/candidate.yml").write_text(
                "connector_name: binance_paper_trade\n"
                "trading_pair: ETH-USDT\n"
                "total_amount_quote: 1000\n"
                "buy_spreads: 0.002\n"
                "sell_spreads: 0.002\n"
                "position_side: BUY\n",
                encoding="utf-8",
            )
            release_path = (
                root
                / "data/strategy-evolution/strategies/pmm_mister/paper/release-manifest.json"
            )
            release_path.parent.mkdir(parents=True)
            release_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "deployment_id": "paper-candidate-1",
                        "strategy_id": "pmm_mister",
                        "candidate_id": "pmm_mister-candidate-1",
                        "controller_config": "conf/controllers/candidate.yml",
                        "script_config": "conf/scripts/candidate.yml",
                        "config_hash": "1" * 64,
                        "status": "waiting_for_credentials",
                        "paper_only": True,
                        "staged_at": "2026-07-12T20:00:00+00:00",
                        "start_command": ["scripts/run_pmm_mister_paper.sh"],
                    }
                ),
                encoding="utf-8",
            )
            market = root / "market.json"
            market.write_text(self.market.model_dump_json(), encoding="utf-8")
            accounts = root / "accounts.json"
            account_rows = [
                {
                    "account_id": row.id,
                    "observed_at": NOW,
                    "equity_quote": 2500,
                    "available_quote": 2200,
                }
                for row in self.config.accounts
                if row.trading_enabled
            ]
            accounts.write_text(
                json.dumps({"accounts": account_rows}), encoding="utf-8"
            )
            service = StrategyRouterService(
                root,
                CONFIG,
                state_dir=root / "state",
                container_probe=lambda _: False,
            )
            result = service.run_once(market, accounts, now=NOW)
        self.assertEqual("pmm_mister", result["plan"]["allocations"][0]["strategy_id"])
        self.assertEqual("blocked", result["worker_actions"][0]["action"])
        self.assertIn(
            "transition_candidate",
            result["worker_actions"][0]["reason_codes"],
        )

    @staticmethod
    def _bootstrap_snapshot():
        from hummingbot.strategy_v2.routing.data_types import AccountSnapshot

        return AccountSnapshot(
            account_id="binance-mm",
            observed_at=NOW,
            equity_quote=2500,
            available_quote=2200,
        )
