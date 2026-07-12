from unittest import TestCase

from hummingbot.strategy_v2.routers.adapters import default_adapter_registry
from hummingbot.strategy_v2.routers.promotion import PromotionEvidence, PromotionStage
from hummingbot.strategy_v2.routers.strategy_registry import default_strategy_registry


class StrategyAdapterTest(TestCase):
    def setUp(self):
        self.adapters = default_adapter_registry()

    def test_core_market_regimes_have_a_registered_adapter(self):
        self.assertEqual(
            {"supertrend_v1", "pmm_mister", "funding_rate_arb"},
            set(self.adapters),
        )
        for adapter in self.adapters.values():
            self.assertTrue(adapter.spec.required_features)
            self.assertTrue(adapter.spec.risk_controls)
            self.assertGreaterEqual(adapter.spec.minimum_paper_hours, 24)
        registry = default_strategy_registry()
        for name in self.adapters:
            self.assertIn(name, registry)
            self.assertFalse(registry[name].enabled)

    def test_promotion_is_fail_closed_without_evidence(self):
        for adapter in self.adapters.values():
            assessment = adapter.assess(PromotionEvidence())
            self.assertEqual(PromotionStage.SHADOW, assessment.stage)
            self.assertFalse(assessment.live_enabled)
            self.assertIn("adapter_tests_required", assessment.blocking_gates)

    def test_all_gates_are_required_for_live_enablement(self):
        adapter = self.adapters["supertrend_v1"]
        evidence = PromotionEvidence(
            adapter_tests_passed=True,
            stop_path_verified=True,
            backtest_passed=True,
            walk_forward_passed=True,
            costs_included=True,
            paper_hours=adapter.spec.minimum_paper_hours,
            paper_scorecard_passed=True,
            canary_approved=True,
            live_release_approved=True,
        )
        assessment = adapter.assess(evidence)
        self.assertEqual(PromotionStage.LIVE_ENABLED, assessment.stage)
        self.assertTrue(assessment.live_enabled)

    def test_paper_time_below_adapter_minimum_blocks_promotion(self):
        adapter = self.adapters["funding_rate_arb"]
        evidence = PromotionEvidence(
            adapter_tests_passed=True,
            stop_path_verified=True,
            backtest_passed=True,
            walk_forward_passed=True,
            costs_included=True,
            paper_hours=24,
            paper_scorecard_passed=True,
        )
        assessment = adapter.assess(evidence)
        self.assertEqual(PromotionStage.BACKTEST_PASSED, assessment.stage)
        self.assertIn("paper_scorecard_72h_required", assessment.blocking_gates)
