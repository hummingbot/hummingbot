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

    class MockConnectorDataSourceModule(MagicMock):
        @property
        def MockconnectorAPIOrderBookDataSource(self):
            return TestTradingPairFetcher.MockConnectorDataSource()

    class MockConnectorDataSource(MagicMock):
        async def fetch_trading_pairs(self, *args, **kwargs):
            asyncio.sleep(0.01)
            return 'MOCK-HBOT'

    @classmethod
    def setUpClass(cls) -> None:
        with patch('hummingbot.client.settings.CONNECTOR_SETTINGS', {"mock_exchange_1": cls.MockConnectorSetting()}) as _,\
                patch('hummingbot.core.utils.trading_pair_fetcher.importlib.import_module', return_value=cls.MockConnectorDataSourceModule()) as _:
            from hummingbot.core.utils.trading_pair_fetcher import TradingPairFetcher
            TradingPairFetcher._sf_shared_instance = None   # Need to reset any pre-existent singleton from previous tests
            cls.trading_pair_fetcher = TradingPairFetcher.get_instance()
            asyncio.get_event_loop().run_until_complete(cls.wait_until_trading_pair_fetcher_ready(cls.trading_pair_fetcher))

    @classmethod
    def tearDownClass(cls) -> None:
        # Need to reset TradingPairFetcher module so next time it gets imported it works as expected
        from hummingbot.core.utils.trading_pair_fetcher import TradingPairFetcher
        TradingPairFetcher._sf_shared_instance = None

    def test_trading_pair_fetcher_returns_same_instance_when_get_new_instance_once_initialized(self):
        from hummingbot.core.utils.trading_pair_fetcher import TradingPairFetcher
        instance = TradingPairFetcher.get_instance()
        self.assertIs(instance, self.trading_pair_fetcher)

    def test_fetched_connector_trading_pairs(self):
        trading_pairs = self.trading_pair_fetcher.trading_pairs
        self.assertEqual(trading_pairs, {'mockConnector': 'MOCK-HBOT'})
