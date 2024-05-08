import asyncio
from typing import Awaitable
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock, patch

from gql import gql

from hummingbot.connector.exchange.polkadex.polkadex_query_executor import GrapQLQueryExecutor


class AsyncIter:
    def __init__(self, items):
        self.items = items

    async def __aiter__(self):
        for item in self.items:
            yield item


class PolkadexQueryExecutorTests(TestCase):

    def setUp(self) -> None:
        super().setUp()
        self._original_async_loop = asyncio.get_event_loop()
        self.async_loop = asyncio.new_event_loop()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.async_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @patch("hummingbot.connector.exchange.polkadex.polkadex_query_executor.AIOHTTPTransport")
    @patch("hummingbot.connector.exchange.polkadex.polkadex_query_executor.Client")
    def test_execute_query(self, mock_client, mock_transport):
        graphql_query_executor = GrapQLQueryExecutor(MagicMock(), MagicMock())

        session_mock = AsyncMock()
        session_mock.execute.return_value = {"getAllMarkets": 23}
        mock_client.return_value.__aenter__.return_value = session_mock

        query = gql(
            """
            query MyQuery {
                getAllMarkets {
                    items {
                        market
                        min_volume
                        price_tick_size
                        qty_step_size
                    }
                }
            }
            """
        )

        result = self.async_run_with_timeout(graphql_query_executor._execute_query(
            query,
            {},
            "getAllMarkets",
            "getAllMarkets"
        ))

        mock_transport.called_once()
        mock_client.assert_called_once_with(transport=mock_transport(), fetch_schema_from_transport=False)
        session_mock.execute.called_once_with(query, variable_values={}, parse_result=True)
        self.assertEqual(result, 23)

    @patch("hummingbot.connector.exchange.polkadex.polkadex_query_executor.AppSyncWebsocketsTransport")
    @patch("hummingbot.connector.exchange.polkadex.polkadex_query_executor.Client")
    def test_subscribe_to_stream(self, mock_client, mock_transport):
        async def get_all_items_from_async_iter(async_iter):
            all_items = []
            async for item in async_iter:
                all_items.append(item)
            return all_items

        graphql_query_executor = GrapQLQueryExecutor(MagicMock(), MagicMock())

        session_mock = MagicMock()
        session_mock.subscribe.return_value = AsyncIter([23, 42])
        mock_client.return_value.__aenter__.return_value = session_mock

        query = gql(
            """
            subscription WebsocketStreamsMessage($name: String!) {
                websocket_streams(name: $name) {
                    data
                }
            }
            """
        )

        result = self.async_run_with_timeout(
            get_all_items_from_async_iter(graphql_query_executor._subscribe_to_stream("big-bro-is-watching-you"))
        )

        mock_transport.called_once()
        mock_client.assert_called_once_with(transport=mock_transport(), fetch_schema_from_transport=False)
        session_mock.subscribe.called_once_with(query, variable_values={"name": "big-bro-is-watching-you"}, parse_result=True)
        self.assertEqual(result, [23, 42])
