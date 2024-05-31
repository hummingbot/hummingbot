import asyncio
from typing import Awaitable
from unittest import TestCase
from unittest.mock import MagicMock, patch

from hummingbot.connector.exchange.polkadex.polkadex_data_source import PolkadexDataSource


class PolkadexDatasourceTests(TestCase):

    def setUp(self) -> None:
        super().setUp()
        self._original_async_loop = asyncio.get_event_loop()
        self.async_loop = asyncio.new_event_loop()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.async_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_check_status_no_need_to_reinit(self):
        ds = PolkadexDataSource(MagicMock(), MagicMock())
        ds._query_executor._restart_initialization = False

        with patch("hummingbot.connector.exchange.polkadex.polkadex_data_source.PolkadexDataSource.stop") as stop_mock:
            with patch("hummingbot.connector.exchange.polkadex.polkadex_data_source.PolkadexDataSource.reinitiaite_query_executor") as reinitiaite_query_executor_mock:
                with patch("hummingbot.connector.exchange.polkadex.polkadex_data_source.PolkadexDataSource.start") as start_mock:
                    self.async_run_with_timeout(ds.check_status())

        stop_mock.assert_not_called()
        reinitiaite_query_executor_mock.assert_not_called()
        start_mock.assert_not_called()

    def test_check_status_should_reinit(self):
        ds = PolkadexDataSource(MagicMock(), MagicMock(), trading_pairs=[23])
        ds._query_executor._restart_initialization = True

        with patch("hummingbot.connector.exchange.polkadex.polkadex_data_source.PolkadexDataSource.stop") as stop_mock:
            with patch("hummingbot.connector.exchange.polkadex.polkadex_data_source.PolkadexDataSource.reinitiaite_query_executor") as reinitiaite_query_executor_mock:
                with patch("hummingbot.connector.exchange.polkadex.polkadex_data_source.PolkadexDataSource.start") as start_mock:
                    self.async_run_with_timeout(ds.check_status())

        stop_mock.assert_called_once_with()
        reinitiaite_query_executor_mock.assert_called_once_with()
        start_mock.assert_called_once_with([23])

    def test_reinitiaite_query_executor(self):
        ds = PolkadexDataSource(MagicMock(), MagicMock(), trading_pairs=[23])
        old_query_executor = ds._query_executor
        self.async_run_with_timeout(ds.reinitiaite_query_executor())
        self.assertIsNotNone(old_query_executor)
        self.assertIsNotNone(ds._query_executor)
        self.assertIsNot(ds._query_executor, old_query_executor)
