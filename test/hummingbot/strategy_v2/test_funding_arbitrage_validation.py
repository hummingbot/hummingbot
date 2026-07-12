from unittest import TestCase

from hummingbot.strategy_v2.backtesting.funding_arbitrage import (
    FundingArbitrageCosts,
    FundingArbitrageParameters,
    simulate_funding_arbitrage,
)


class FundingArbitrageValidationTest(TestCase):
    def test_round_trip_cost_covers_both_venues_and_directions(self):
        costs = FundingArbitrageCosts(
            binance_taker_bps=5,
            hyperliquid_taker_bps=4.5,
            slippage_bps_per_leg=2,
        )
        self.assertAlmostEqual(0.0027, costs.round_trip_pct)

    def test_simulation_deducts_costs_and_basis_change(self):
        snapshots = [
            {
                "timestamp": 0,
                "binance_price": 100,
                "hyperliquid_price": 100,
                "binance_funding_payment_rate": 0,
                "hyperliquid_funding_payment_rate": 0,
                "binance_forecast_daily_rate": 0,
                "hyperliquid_forecast_daily_rate": 0.01,
            },
            {
                "timestamp": 3600,
                "binance_price": 100,
                "hyperliquid_price": 100,
                "binance_funding_payment_rate": 0,
                "hyperliquid_funding_payment_rate": 0.004,
                "binance_forecast_daily_rate": 0,
                "hyperliquid_forecast_daily_rate": 0.01,
            },
        ]
        metrics = simulate_funding_arbitrage(
            snapshots,
            FundingArbitrageParameters(0.001, 0.01, 24),
            FundingArbitrageCosts(),
            position_size_quote=1000,
        )
        self.assertEqual(1, metrics["total_positions"])
        self.assertAlmostEqual(1.3, metrics["adjusted_net_quote"])
        self.assertAlmostEqual(2.7, metrics["costs_quote"])
