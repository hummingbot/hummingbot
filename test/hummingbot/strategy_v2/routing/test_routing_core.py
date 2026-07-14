import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from hummingbot.strategy_v2.routing.compatibility import CompatibilityEngine
from hummingbot.strategy_v2.routing.config import load_routing_config
from hummingbot.strategy_v2.routing.data_types import (
    AIRoutingSignal,
    AccountSnapshot,
    CandidateSignal,
    FixedScoreComponents,
    MarketState,
    RouteTarget,
    StrategySleeve,
)
from hummingbot.strategy_v2.routing.ledger import DecisionLedger
from hummingbot.strategy_v2.routing.release import (
    ReleaseManifest,
    StrategyRelease,
    load_evolution_release_manifests,
    load_release_manifest,
    validate_evolution_single_writer,
)
from hummingbot.strategy_v2.routing.scoring import DeterministicScorer
from hummingbot.strategy_v2.routing.supervisor import StrategyRoutingSupervisor


ROOT = Path(__file__).resolve().parents[4]
EXAMPLE = ROOT / "reports/examples/strategy_router_accounts.example.yml"
NOW = 1_783_887_600.0


def components(regime, edge, execution, health):
    return FixedScoreComponents(
        regime_fit=regime,
        expected_edge_after_cost=edge,
        execution_quality=execution,
        strategy_health=health,
    )


class RoutingCoreTest(TestCase):
    def setUp(self):
        loaded = load_routing_config(EXAMPLE)
        integration = loaded.integration.model_copy(
            update={
                "evolution": loaded.integration.evolution.model_copy(
                    update={"enabled": False}
                )
            }
        )
        self.config = loaded.model_copy(update={"integration": integration})
        self.snapshots = {
            account.id: AccountSnapshot(
                account_id=account.id,
                observed_at=NOW,
                equity_quote=2500,
                available_quote=2200,
            )
            for account in self.config.accounts
            if account.trading_enabled
        }
        self.market = MarketState(timestamp=NOW, symbol="BTC-USDT")

    def test_supervisor_selects_compatible_multi_account_portfolio(self):
        candidates = [
            CandidateSignal(
                strategy_id="pmm_mister",
                trading_pair="BTC-USDT",
                requested_capital_quote=1000,
                score_components=components(0.9, 0.8, 0.9, 0.8),
            ),
            CandidateSignal(
                strategy_id="grid_strike",
                trading_pair="BTC-USDT",
                requested_capital_quote=800,
                score_components=components(0.6, 0.5, 0.7, 0.7),
            ),
            CandidateSignal(
                strategy_id="supertrend_v1",
                trading_pair="ETH-USDT",
                requested_capital_quote=500,
                position_side="LONG",
                score_components=components(0.9, 0.7, 0.8, 0.8),
            ),
            CandidateSignal(
                strategy_id="funding_rate_arb",
                trading_pair="BTC-USDT",
                requested_capital_quote=500,
                score_components=components(0.8, 0.8, 0.7, 0.8),
            ),
            CandidateSignal(
                strategy_id="hedge_asset",
                trading_pair="ETH-USDT",
                requested_capital_quote=300,
                position_side="SHORT",
                score_components=components(0.5, 0.4, 0.8, 0.9),
            ),
        ]

        plan = StrategyRoutingSupervisor(self.config).plan(
            self.market,
            self.snapshots,
            candidates,
            now=NOW,
        )

        self.assertFalse(plan.risk_blockers)
        self.assertEqual(
            {"pmm_mister", "supertrend_v1", "funding_rate_arb", "hedge_asset"},
            {row.strategy_id for row in plan.allocations},
        )
        self.assertNotIn("grid_strike", {row.strategy_id for row in plan.allocations})
        grid = next(
            row for row in plan.blocked_candidates if row.strategy_id == "grid_strike"
        )
        self.assertTrue(
            any(
                reason.startswith("compatibility_conditions_missing")
                for reason in grid.reason_codes
            )
        )
        self.assertEqual(7700, plan.reserve_quote)

    def test_global_risk_fails_closed(self):
        candidate = CandidateSignal(
            strategy_id="pmm_mister",
            trading_pair="BTC-USDT",
            requested_capital_quote=5000,
            score_components=components(1, 1, 1, 1),
        )

        strict_risk = self.config.global_risk.model_copy(
            update={"maximum_market_making_sleeve_pct": 0.10}
        )
        config = self.config.model_copy(update={"global_risk": strict_risk})
        plan = StrategyRoutingSupervisor(config).plan(
            self.market,
            self.snapshots,
            [candidate],
            now=NOW,
        )

        self.assertFalse(plan.allocations)
        self.assertIn("sleeve_allocation_limit:market_making", plan.risk_blockers)

    def test_stale_market_blocks_new_allocations(self):
        market = self.market.model_copy(update={"data_fresh": False})
        candidate = CandidateSignal(
            strategy_id="pmm_mister",
            trading_pair="BTC-USDT",
            requested_capital_quote=500,
            score_components=components(1, 1, 1, 1),
        )

        plan = StrategyRoutingSupervisor(self.config).plan(
            market,
            self.snapshots,
            [candidate],
            now=NOW,
        )

        self.assertFalse(plan.allocations)
        self.assertIn("market_state_stale", plan.risk_blockers)

    def test_timestamp_staleness_is_enforced_without_boolean_hint(self):
        stale_market = self.market.model_copy(
            update={
                "timestamp": NOW
                - self.config.global_risk.snapshot_stale_after_seconds
                - 1
            }
        )
        candidate = CandidateSignal(
            strategy_id="pmm_mister",
            trading_pair="BTC-USDT",
            requested_capital_quote=500,
            score_components=components(1, 1, 1, 1),
        )
        plan = StrategyRoutingSupervisor(self.config).plan(
            stale_market,
            self.snapshots,
            [candidate],
            now=NOW,
        )
        self.assertFalse(plan.allocations)
        self.assertIn("market_state_stale", plan.risk_blockers)

        snapshots = dict(self.snapshots)
        snapshots["binance-mm"] = snapshots["binance-mm"].model_copy(
            update={"observed_at": NOW - 21}
        )
        plan = StrategyRoutingSupervisor(self.config).plan(
            self.market,
            snapshots,
            [candidate],
            now=NOW,
        )
        self.assertFalse(plan.allocations)
        self.assertIn(
            "binance-mm:account_snapshot_stale",
            plan.blocked_candidates[0].reason_codes,
        )

    def test_candidate_score_floor_blocks_weak_routes(self):
        candidate = CandidateSignal(
            strategy_id="pmm_mister",
            trading_pair="BTC-USDT",
            requested_capital_quote=500,
            score_components=components(0, 0, 0, 0),
        )
        plan = StrategyRoutingSupervisor(self.config).plan(
            self.market,
            self.snapshots,
            [candidate],
            now=NOW,
        )
        self.assertFalse(plan.allocations)
        self.assertIn(
            "candidate_score_below_minimum",
            plan.blocked_candidates[0].reason_codes,
        )

    def test_strategy_instance_limit_is_enforced_per_account(self):
        candidates = [
            CandidateSignal(
                strategy_id="pmm_mister",
                trading_pair=pair,
                requested_capital_quote=500,
                score_components=components(0.9, 0.9, 0.9, 0.9),
            )
            for pair in ("BTC-USDT", "ETH-USDT")
        ]
        plan = StrategyRoutingSupervisor(self.config).plan(
            self.market,
            self.snapshots,
            candidates,
            now=NOW,
        )
        self.assertEqual(1, len(plan.allocations))
        self.assertTrue(
            any(
                "strategy_instance_limit:binance-mm" in row.reason_codes
                for row in plan.blocked_candidates
            )
        )

    def test_ai_adjustment_is_ignored_in_shadow_and_bounded_when_active(self):
        signal = AIRoutingSignal(
            observed_at=NOW,
            strategy_adjustments={"pmm_mister": 0.9},
        )
        fixed = components(0.5, 0.5, 0.5, 0.5)
        shadow = DeterministicScorer(self.config.router.score_weights, self.config.ai)
        _, adjustment, _, applied = shadow.score(
            "pmm_mister", fixed, now=NOW, ai_signal=signal
        )
        self.assertEqual(0, adjustment)
        self.assertFalse(applied)

        active_ai = self.config.ai.model_copy(
            update={"enabled": True, "mode": "active"}
        )
        active = DeterministicScorer(self.config.router.score_weights, active_ai)
        base, adjustment, final, applied = active.score(
            "pmm_mister", fixed, now=NOW, ai_signal=signal
        )
        self.assertAlmostEqual(0.45, base)
        self.assertAlmostEqual(0.10, adjustment)
        self.assertAlmostEqual(0.55, final)
        self.assertTrue(applied)

    def test_default_same_account_pair_is_exclusive(self):
        engine = CompatibilityEngine(self.config.compatibility)
        selected = [
            RouteTarget(
                account_id="binance-mm",
                sleeve=StrategySleeve.MARKET_MAKING,
                strategy_id="unknown_existing",
                trading_pair="BTC-USDT",
                target_capital_quote=100,
                score=0.5,
            )
        ]

        blockers = engine.assess(
            "another_unknown",
            "binance-mm",
            "BTC-USDT",
            selected,
        )

        self.assertTrue(blockers)

    def test_decision_ledger_is_idempotent(self):
        candidate = CandidateSignal(
            strategy_id="pmm_mister",
            trading_pair="BTC-USDT",
            requested_capital_quote=500,
            score_components=components(0.9, 0.8, 0.9, 0.8),
        )
        plan = StrategyRoutingSupervisor(self.config).plan(
            self.market,
            self.snapshots,
            [candidate],
            now=NOW,
        )
        with TemporaryDirectory() as directory:
            ledger = DecisionLedger(Path(directory) / "decisions.jsonl")
            self.assertTrue(ledger.append(plan))
            self.assertFalse(ledger.append(plan))
            self.assertEqual(1, ledger.path.read_text(encoding="utf-8").count("\n"))

    def test_evolution_release_manifest_is_fail_closed_and_authorizes_exact_candidate(
        self,
    ):
        integration = self.config.integration.model_copy(
            update={
                "evolution": self.config.integration.evolution.model_copy(
                    update={"enabled": True}
                )
            }
        )
        config = self.config.model_copy(update={"integration": integration})
        candidate = CandidateSignal(
            strategy_id="pmm_mister",
            candidate_id="pmm-candidate-1",
            config_hash="12345678abcdef",
            trading_pair="BTC-USDT",
            requested_capital_quote=500,
            score_components=components(0.9, 0.8, 0.9, 0.8),
        )
        supervisor = StrategyRoutingSupervisor(config)

        blocked = supervisor.plan(
            self.market,
            self.snapshots,
            [candidate],
            now=NOW,
        )
        self.assertFalse(blocked.allocations)
        self.assertIn(
            "release_manifest_missing", blocked.blocked_candidates[0].reason_codes
        )

        manifest = ReleaseManifest(
            version=1,
            generated_at=NOW - 1,
            releases=[
                StrategyRelease(
                    strategy_id="pmm_mister",
                    candidate_id="pmm-candidate-1",
                    config_hash="12345678abcdef",
                    artifact_ref="data/strategy-evolution/candidates/pmm-candidate-1.json",
                    stage="paper_passed",
                    allowed_environments=["paper"],
                    generated_at=NOW - 1,
                    expires_at=NOW + 3600,
                )
            ],
        )
        authorized = supervisor.plan(
            self.market,
            self.snapshots,
            [candidate],
            now=NOW,
            release_manifest=manifest,
        )
        self.assertEqual(
            ["pmm_mister"], [row.strategy_id for row in authorized.allocations]
        )
        self.assertEqual("pmm-candidate-1", authorized.allocations[0].candidate_id)

    def test_loads_real_evolution_paper_release_contract(self):
        payload = {
            "version": 1,
            "deployment_id": "paper-pmm_mister-candidate-1-abc123",
            "strategy_id": "pmm_mister",
            "candidate_id": "pmm_mister-candidate-1",
            "previous_deployment_id": None,
            "controller_config": "conf/controllers/candidate.yml",
            "script_config": "conf/scripts/candidate.yml",
            "config_hash": "1" * 64,
            "status": "waiting_for_credentials",
            "paper_only": True,
            "staged_at": "2026-07-12T20:39:34.842160+00:00",
            "start_command": ["scripts/run_pmm_mister_paper.sh"],
        }
        with TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = (
                root
                / "data/strategy-evolution/strategies/pmm_mister/paper/release-manifest.json"
            )
            manifest_path.parent.mkdir(parents=True)
            manifest_path.write_text(json.dumps(payload), encoding="utf-8")
            manifest = load_release_manifest(manifest_path)

            aggregated = load_evolution_release_manifests(
                root,
                "data/strategy-evolution/strategies/*/paper/release-manifest.json",
            )

        self.assertEqual(1, len(manifest.releases))
        release = manifest.releases[0]
        self.assertEqual("pmm_mister", release.strategy_id)
        self.assertEqual("paper", release.allowed_environments[0].value)
        self.assertEqual(64, len(release.config_hash))
        self.assertIn("pmm_mister", {row.strategy_id for row in aggregated.releases})

    def test_evolution_single_writer_preflight_rejects_auto_start(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = root / "conf/strategy_evolution.json"
            config_path.parent.mkdir(parents=True)
            config_path.write_text(
                json.dumps({"policy": {"auto_start_paper_candidates": True}}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "auto_start_paper_candidates"):
                validate_evolution_single_writer(root, "conf/strategy_evolution.json")
