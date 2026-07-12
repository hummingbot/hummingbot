from unittest import TestCase

from hummingbot.strategy_v2.backtesting.walk_forward import (
    CostModel,
    ValidationCriteria,
    apply_cost_model,
    generate_rolling_windows,
    summarize_out_of_sample,
    validation_score,
)


class WalkForwardValidationTest(TestCase):
    def test_windows_are_rolling_and_purged(self):
        windows = generate_rolling_windows(0, 1_000, train_seconds=400, test_seconds=200, purge_seconds=10)
        self.assertEqual(2, len(windows))
        self.assertEqual((0, 400, 410, 610), (
            windows[0].train_start, windows[0].train_end, windows[0].test_start, windows[0].test_end,
        ))
        self.assertEqual(200, windows[1].train_start)

    def test_cost_model_deducts_slippage_switching_and_funding(self):
        metrics = apply_cost_model(
            {
                "net_pnl_quote": 20,
                "total_fees_quote": 4,
                "total_volume": 5_000,
                "total_executors_with_position": 2,
                "max_drawdown_pct": -0.03,
            },
            capital_quote=1_000,
            window_seconds=86_400,
            costs=CostModel(slippage_bps=2, switch_bps=1, funding_rate_daily=0.0001),
        )
        self.assertAlmostEqual(18.7, metrics["adjusted_net_quote"])
        self.assertAlmostEqual(0.0187, metrics["adjusted_return"])
        self.assertAlmostEqual(0.03, metrics["max_drawdown_pct"])
        self.assertLess(validation_score(metrics), metrics["adjusted_return"])

    def test_summary_fails_closed_when_folds_are_insufficient(self):
        folds = [{"status": "completed", "metrics": {"adjusted_net_quote": 10, "max_drawdown_pct": 0.02, "total_positions": 2}}]
        summary = summarize_out_of_sample(folds, ValidationCriteria(minimum_folds=2))
        self.assertFalse(summary["passed"])

    def test_summary_passes_only_when_all_criteria_pass(self):
        folds = [
            {"status": "completed", "metrics": {"adjusted_net_quote": 10, "max_drawdown_pct": 0.02, "total_positions": 2}},
            {"status": "completed", "metrics": {"adjusted_net_quote": 5, "max_drawdown_pct": 0.03, "total_positions": 1}},
            {"status": "completed", "metrics": {"adjusted_net_quote": -1, "max_drawdown_pct": 0.04, "total_positions": 1}},
        ]
        summary = summarize_out_of_sample(folds, ValidationCriteria())
        self.assertTrue(summary["passed"])
        self.assertEqual(4, summary["total_positions"])
