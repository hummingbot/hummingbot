from decimal import Decimal
from types import SimpleNamespace
from unittest import TestCase

from scripts.v2_funding_rate_arb import (
    ArbitrageCandidate,
    FundingRateArbitrage,
    FundingRateArbitrageConfig,
)
from hummingbot.core.data_type.common import TradeType


class FakeConnector:
    def __init__(self, fee: Decimal = Decimal("0.0004"), funding_infos=None):
        self.fee = fee
        self.funding_infos = funding_infos or {}

    def get_fee(self, **kwargs):
        return SimpleNamespace(percent=self.fee)

    def get_funding_info(self, trading_pair):
        return self.funding_infos[trading_pair]


class FakeMarketDataProvider:
    def __init__(self, quote_volume_prices=None, mid_prices=None):
        self.quote_volume_prices = quote_volume_prices or {}
        self.mid_prices = mid_prices or {}

    def get_price_for_quote_volume(self, connector_name, trading_pair, quote_volume, is_buy):
        price = self.quote_volume_prices[(connector_name, trading_pair, is_buy)]
        return SimpleNamespace(result_price=price)

    def get_price_by_type(self, connector_name, trading_pair, price_type):
        return self.mid_prices[(connector_name, trading_pair)]


class FundingRateArbitrageTest(TestCase):
    def make_config(self, **overrides):
        config = {
            "connectors": {"hyperliquid_perpetual", "binance_perpetual"},
            "tokens": {"WIF"},
            "position_size_quote": Decimal("100"),
            "min_funding_rate_profitability": Decimal("0.001"),
            "min_net_profitability": Decimal("0.001"),
            "max_trade_profitability_loss": Decimal("0.002"),
            "estimated_exit_cost_buffer": Decimal("0.0005"),
            "single_leg_timeout": 5,
        }
        config.update(overrides)
        return FundingRateArbitrageConfig(**config)

    def make_strategy(self, config=None, connectors=None, market_data_provider=None, executors=None):
        strategy = FundingRateArbitrage.__new__(FundingRateArbitrage)
        strategy.config = config or self.make_config()
        strategy.connectors = connectors or {}
        strategy.market_data_provider = market_data_provider or FakeMarketDataProvider()
        strategy.active_funding_arbitrages = {}
        strategy.stopped_funding_arbitrages = {token: [] for token in strategy.config.tokens}
        strategy._set_current_timestamp(0)
        strategy.get_all_executors = lambda: executors or []
        return strategy

    def test_best_candidate_includes_basis_fees_and_exit_buffer(self):
        funding_infos = {
            "WIF-USD": SimpleNamespace(rate=Decimal("0.0001"), next_funding_utc_timestamp=3600),
            "WIF-USDT": SimpleNamespace(rate=Decimal("0.0016"), next_funding_utc_timestamp=28800),
        }
        connectors = {
            "hyperliquid_perpetual": FakeConnector(funding_infos=funding_infos),
            "binance_perpetual": FakeConnector(funding_infos=funding_infos),
        }
        market_data_provider = FakeMarketDataProvider(
            quote_volume_prices={
                ("hyperliquid_perpetual", "WIF-USD", True): Decimal("100"),
                ("binance_perpetual", "WIF-USDT", False): Decimal("101"),
            }
        )
        strategy = self.make_strategy(connectors=connectors, market_data_provider=market_data_provider)

        candidate = strategy.get_best_arbitrage_candidate("WIF")

        self.assertEqual(candidate.connector_1, "hyperliquid_perpetual")
        self.assertEqual(candidate.connector_2, "binance_perpetual")
        self.assertEqual(candidate.side, TradeType.BUY)
        self.assertEqual(candidate.funding_profitability, Decimal("0.0024"))
        self.assertEqual(candidate.trade_profitability, Decimal("0.0092"))
        self.assertEqual(candidate.net_profitability, Decimal("0.0111"))

    def test_create_actions_skips_when_net_profitability_is_below_threshold(self):
        strategy = self.make_strategy()
        strategy.get_best_arbitrage_candidate = lambda token: ArbitrageCandidate(
            token=token,
            connector_1="hyperliquid_perpetual",
            connector_2="binance_perpetual",
            side=TradeType.BUY,
            funding_profitability=Decimal("0.002"),
            trade_profitability=Decimal("-0.001"),
            net_profitability=Decimal("0.0005"),
        )

        actions = strategy.create_actions_proposal()

        self.assertEqual(actions, [])
        self.assertEqual(strategy.active_funding_arbitrages, {})

    def test_position_amount_is_capped_to_same_base_amount_on_both_legs(self):
        market_data_provider = FakeMarketDataProvider(
            mid_prices={
                ("hyperliquid_perpetual", "WIF-USD"): Decimal("100"),
                ("binance_perpetual", "WIF-USDT"): Decimal("110"),
            }
        )
        strategy = self.make_strategy(market_data_provider=market_data_provider)

        first_config, second_config = strategy.get_position_executors_config(
            "WIF", "hyperliquid_perpetual", "binance_perpetual", TradeType.BUY
        )

        expected_amount = Decimal("100") / Decimal("110")
        self.assertEqual(first_config.amount, expected_amount)
        self.assertEqual(second_config.amount, expected_amount)

    def test_single_leg_timeout_stops_both_active_executors(self):
        executors = [
            SimpleNamespace(
                id="long-leg",
                is_active=True,
                is_trading=True,
                is_done=False,
                close_type=None,
                net_pnl_quote=Decimal("0"),
            ),
            SimpleNamespace(
                id="short-leg",
                is_active=True,
                is_trading=False,
                is_done=False,
                close_type=None,
                net_pnl_quote=Decimal("0"),
            ),
        ]
        strategy = self.make_strategy(executors=executors)
        strategy._set_current_timestamp(10)
        strategy.active_funding_arbitrages["WIF"] = {
            "connector_1": "hyperliquid_perpetual",
            "connector_2": "binance_perpetual",
            "executors_ids": ["long-leg", "short-leg"],
            "side": TradeType.BUY,
            "funding_payments": [],
            "created_at": 0,
            "status": "opening",
            "stop_reason": None,
        }

        actions = strategy.stop_actions_proposal()

        self.assertEqual({action.executor_id for action in actions}, {"long-leg", "short-leg"})
        self.assertEqual(strategy.active_funding_arbitrages["WIF"]["status"], "stopping")
        self.assertEqual(strategy.active_funding_arbitrages["WIF"]["stop_reason"], "single_leg_entry")

    def test_cleanup_completed_arbitrage_removes_active_record(self):
        executors = [
            SimpleNamespace(id="long-leg", is_done=True, net_pnl_quote=Decimal("1")),
            SimpleNamespace(id="short-leg", is_done=True, net_pnl_quote=Decimal("2")),
        ]
        strategy = self.make_strategy(executors=executors)
        strategy._set_current_timestamp(20)
        strategy.active_funding_arbitrages["WIF"] = {
            "executors_ids": ["long-leg", "short-leg"],
            "funding_payments": [SimpleNamespace(amount=Decimal("0.5"))],
        }

        strategy._cleanup_completed_arbitrages()

        self.assertNotIn("WIF", strategy.active_funding_arbitrages)
        self.assertEqual(strategy.stopped_funding_arbitrages["WIF"][0]["final_executor_pnl_quote"], Decimal("3"))
        self.assertEqual(strategy.stopped_funding_arbitrages["WIF"][0]["final_funding_pnl_quote"], Decimal("0.5"))

    def test_stopping_retries_active_leg_and_cleans_up_incomplete_pair(self):
        executor = SimpleNamespace(
            id="long-leg",
            is_active=True,
            is_trading=True,
            is_done=False,
            close_type=None,
            net_pnl_quote=Decimal("0"),
        )
        strategy = self.make_strategy(executors=[executor])
        strategy._set_current_timestamp(10)
        strategy.active_funding_arbitrages["WIF"] = {
            "executors_ids": ["long-leg", "missing-short-leg"],
            "funding_payments": [],
            "created_at": 0,
            "status": "stopping",
            "stop_reason": "missing_executor_after_entry_timeout",
        }

        actions = strategy.stop_actions_proposal()

        self.assertEqual([action.executor_id for action in actions], ["long-leg"])

        executor.is_active = False
        executor.is_trading = False
        executor.is_done = True
        strategy._set_current_timestamp(20)

        self.assertEqual(strategy.stop_actions_proposal(), [])
        self.assertNotIn("WIF", strategy.active_funding_arbitrages)
        self.assertEqual(
            strategy.stopped_funding_arbitrages["WIF"][0]["stop_reason"],
            "missing_executor_after_entry_timeout",
        )
