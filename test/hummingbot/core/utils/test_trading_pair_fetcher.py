from unittest import TestCase
from mock import patch, MagicMock
import asyncio


class TestTradingPairFetcher(TestCase):
    @classmethod
    async def wait_until_trading_pair_fetcher_ready(cls, tpf):
        while True:
            if tpf.ready:
                break
            else:
                await asyncio.sleep(0)

    class MockConnectorSetting(MagicMock):
        name = 'mockConnector'

        def base_name(self):
            return 'mockConnector'

    class MockConnectorDataSource(MagicMock):
        async def fetch_trading_pairs(self, *args, **kwargs):
            return 'MOCK-HBOT'

    class MockConnectorDataSourceModule(MagicMock):
        @property
        def MockconnectorAPIOrderBookDataSource(self):
            return TestTradingPairFetcher.MockConnectorDataSource()

    @classmethod
    def tearDownClass(cls) -> None:
        # Need to reset TradingPairFetcher module so next time it gets imported it works as expected
        from hummingbot.core.utils.trading_pair_fetcher import TradingPairFetcher
        TradingPairFetcher._sf_shared_instance = None

    def test_trading_pair_fetcher_returns_same_instance_when_get_new_instance_once_initialized(self):
        from hummingbot.core.utils.trading_pair_fetcher import TradingPairFetcher
        instance = TradingPairFetcher.get_instance()
        self.assertIs(instance, TradingPairFetcher.get_instance())

    def test_fetched_connector_trading_pairs(self):
        with patch('hummingbot.core.utils.trading_pair_fetcher.CONNECTOR_SETTINGS',
                   {"mock_exchange_1": self.MockConnectorSetting()}) as _, \
                patch('hummingbot.core.utils.trading_pair_fetcher.importlib.import_module',
                      return_value=self.MockConnectorDataSourceModule()) as _, \
                patch('hummingbot.core.utils.trading_pair_fetcher.TradingPairFetcher._sf_shared_instance', None):
            from hummingbot.core.utils.trading_pair_fetcher import TradingPairFetcher
            trading_pair_fetcher = TradingPairFetcher()
            asyncio.get_event_loop().run_until_complete(self.wait_until_trading_pair_fetcher_ready(trading_pair_fetcher))
            trading_pairs = trading_pair_fetcher.trading_pairs
            self.assertEqual(trading_pairs, {'mockConnector': 'MOCK-HBOT'})
