from unittest import TestCase

from controllers.generic.ai_strategy_router import AIStrategyRouter, AIStrategyRouterConfig


class AIStrategyRouterConfigTest(TestCase):
    def test_runtime_candle_fallbacks_use_trading_market(self):
        config = AIStrategyRouterConfig(id="router-test")
        router = AIStrategyRouter.__new__(AIStrategyRouter)
        router.config = config

        self.assertEqual(router._market_data_connector_name(), "binance_perpetual")
        self.assertEqual(router._candles_trading_pair(), "BTC-USDT")

    def test_paper_connector_fallback_uses_real_market_data_source(self):
        config = AIStrategyRouterConfig(
            id="paper-router-test",
            connector_name="binance_perpetual_paper_trade",
            trading_pair="ETH-USDT",
        )
        router = AIStrategyRouter.__new__(AIStrategyRouter)
        router.config = config

        self.assertEqual(router._market_data_connector_name(), "binance_perpetual")
        self.assertEqual(router._candles_trading_pair(), "ETH-USDT")
