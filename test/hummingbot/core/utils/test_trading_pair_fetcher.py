import asyncio
import unittest

from mock import patch, MagicMock

from hummingbot.core.utils.trading_pair_fetcher import TradingPairFetcher


class TestTradingPairFetcher(unittest.TestCase):
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
        TradingPairFetcher._sf_shared_instance = None

    def test_trading_pair_fetcher_returns_same_instance_when_get_new_instance_once_initialized(self):
        instance = TradingPairFetcher.get_instance()
        self.assertIs(instance, TradingPairFetcher.get_instance())

    @patch("hummingbot.core.utils.trading_pair_fetcher.importlib.import_module")
    @patch("hummingbot.client.settings.AllConnectorSettings.get_connector_settings")
    @patch("hummingbot.core.utils.trading_pair_fetcher.TradingPairFetcher._sf_shared_instance")
    def test_fetched_connector_trading_pairs(self, _, mock_connector_settings, mock_import_module, ):
        mock_connector_settings.return_value = {"mock_exchange_1": self.MockConnectorSetting()}
        mock_import_module.return_value = self.MockConnectorDataSourceModule()

        trading_pair_fetcher = TradingPairFetcher()
        asyncio.get_event_loop().run_until_complete(self.wait_until_trading_pair_fetcher_ready(trading_pair_fetcher))
        trading_pairs = trading_pair_fetcher.trading_pairs
        self.assertEqual(trading_pairs, {'mockConnector': 'MOCK-HBOT'})
