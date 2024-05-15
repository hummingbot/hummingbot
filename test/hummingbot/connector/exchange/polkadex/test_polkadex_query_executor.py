import asyncio
import json
from datetime import datetime
from typing import Awaitable
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock, call, patch

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

    def test_timestamp_to_aws_datetime_string(self):
        aws_datetime_str = GrapQLQueryExecutor._timestamp_to_aws_datetime_string(1715663798.5271418)
        self.assertEqual(aws_datetime_str, '2024-05-14T05:16:38.527Z')

    def test_query_all_pages_with_empty_next_token(self):
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

        parameters = {"market_maker": "enflux"}
        field_name = "getAllMarkets"
        throttler_limit_id = "tlid"
        limit = 42

        graphql_query_executor = GrapQLQueryExecutor(MagicMock(), MagicMock())

        with patch("hummingbot.connector.exchange.polkadex.polkadex_query_executor.GrapQLQueryExecutor._execute_query") as execute_query_mock:
            execute_query_mock.return_value = {"items": [23, 42], "nextToken": None}
            result = self.async_run_with_timeout(graphql_query_executor._query_all_pages(
                query,
                parameters,
                field_name,
                throttler_limit_id,
                limit
            ))

        self.assertEqual(result, [23, 42])

        parameters.update({"limit": limit})

        execute_query_mock.assert_called_once_with(
            query,
            parameters,
            field_name,
            throttler_limit_id
        )

    def test_query_all_pages_with_empty_next_token_and_empty_parameters(self):
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

        parameters = None
        field_name = "getAllMarkets"
        throttler_limit_id = "tlid"
        limit = 42

        graphql_query_executor = GrapQLQueryExecutor(MagicMock(), MagicMock())

        with patch("hummingbot.connector.exchange.polkadex.polkadex_query_executor.GrapQLQueryExecutor._execute_query") as execute_query_mock:
            execute_query_mock.return_value = {"items": [23, 42], "nextToken": None}
            result = self.async_run_with_timeout(graphql_query_executor._query_all_pages(
                query,
                parameters,
                field_name,
                throttler_limit_id,
                limit
            ))

        self.assertEqual(result, [23, 42])

        parameters = {"limit": limit}

        execute_query_mock.assert_called_once_with(
            query,
            parameters,
            field_name,
            throttler_limit_id
        )

    def test_query_all_pages_with_non_empty_next_token(self):
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

        parameters = {"market_maker": "enflux"}
        field_name = "getAllMarkets"
        throttler_limit_id = "tlid"
        limit = 42

        graphql_query_executor = GrapQLQueryExecutor(MagicMock(), MagicMock())

        with patch("hummingbot.connector.exchange.polkadex.polkadex_query_executor.GrapQLQueryExecutor._execute_query") as execute_query_mock:
            execute_query_mock.side_effect = [
                {"items": [23, 42], "nextToken": "abc"},
                {"items": [11], "nextToken": None}
            ]
            result = self.async_run_with_timeout(graphql_query_executor._query_all_pages(
                query,
                parameters,
                field_name,
                throttler_limit_id,
                limit
            ))

        self.assertEqual(result, [23, 42, 11])

        self.assertEqual(len(execute_query_mock.call_args_list), 2)

        parameters.update({
            "limit": limit,
            "nextToken": "abc",
        })

        self.assertEqual(
            execute_query_mock.call_args_list[0],
            call(
                query,
                parameters,
                field_name,
                throttler_limit_id,
            )
        )

        del parameters["nextToken"]

        self.assertEqual(
            execute_query_mock.call_args_list[1],
            call(
                query,
                parameters,
                field_name,
                throttler_limit_id,
            )
        )

    def test_place_order_returns_str_result_true(self):
        graphql_query_executor = GrapQLQueryExecutor(MagicMock(), MagicMock())

        query = gql(
            """
            mutation PlaceOrder($payload: String!) {
                place_order(input: {payload: $payload})
            }
            """
        )

        order_info = {"a": 23}
        signature = {"b": 42}
        parameters = {
            "payload": json.dumps({"PlaceOrder": [order_info, signature]}),
        }
        field_name = "place_order"

        with patch("hummingbot.connector.exchange.polkadex.polkadex_query_executor.GrapQLQueryExecutor._execute_query") as execute_query_mock:
            execute_query_mock.return_value = '{"is_success":true,"body":"enflx-001"}'
            result = self.async_run_with_timeout(graphql_query_executor.place_order(
                order_info,
                signature,
            ))

        self.assertEqual(result, "enflx-001")

        execute_query_mock.assert_called_once_with(
            query=query,
            parameters=parameters,
            field_name=field_name,
            throttler_limit_id="PlaceOrder"
        )

    def test_place_order_returns_str_result_false(self):
        graphql_query_executor = GrapQLQueryExecutor(MagicMock(), MagicMock())

        query = gql(
            """
            mutation PlaceOrder($payload: String!) {
                place_order(input: {payload: $payload})
            }
            """
        )

        order_info = {"a": 23}
        signature = {"b": 42}
        parameters = {
            "payload": json.dumps({"PlaceOrder": [order_info, signature]}),
        }
        field_name = "place_order"

        with patch("hummingbot.connector.exchange.polkadex.polkadex_query_executor.GrapQLQueryExecutor._execute_query") as execute_query_mock:
            execute_query_mock.return_value = '{"is_success":false,"body":"error"}'
            result = self.async_run_with_timeout(graphql_query_executor.place_order(
                order_info,
                signature,
            ))

        self.assertIsNone(result)

        execute_query_mock.assert_called_once_with(
            query=query,
            parameters=parameters,
            field_name=field_name,
            throttler_limit_id="PlaceOrder"
        )

    def test_place_order_returns_dict_result_true(self):
        graphql_query_executor = GrapQLQueryExecutor(MagicMock(), MagicMock())

        query = gql(
            """
            mutation PlaceOrder($payload: String!) {
                place_order(input: {payload: $payload})
            }
            """
        )

        order_info = {"a": 23}
        signature = {"b": 42}
        parameters = {
            "payload": json.dumps({"PlaceOrder": [order_info, signature]}),
        }
        field_name = "place_order"

        with patch("hummingbot.connector.exchange.polkadex.polkadex_query_executor.GrapQLQueryExecutor._execute_query") as execute_query_mock:
            execute_query_mock.return_value = {"is_success": True, "body": "enflx-001"}
            result = self.async_run_with_timeout(graphql_query_executor.place_order(
                order_info,
                signature,
            ))

        self.assertEqual(result, "enflx-001")

        execute_query_mock.assert_called_once_with(
            query=query,
            parameters=parameters,
            field_name=field_name,
            throttler_limit_id="PlaceOrder"
        )

    def test_place_order_returns_dict_result_false(self):
        graphql_query_executor = GrapQLQueryExecutor(MagicMock(), MagicMock())

        query = gql(
            """
            mutation PlaceOrder($payload: String!) {
                place_order(input: {payload: $payload})
            }
            """
        )

        order_info = {"a": 23}
        signature = {"b": 42}
        parameters = {
            "payload": json.dumps({"PlaceOrder": [order_info, signature]}),
        }
        field_name = "place_order"

        with patch("hummingbot.connector.exchange.polkadex.polkadex_query_executor.GrapQLQueryExecutor._execute_query") as execute_query_mock:
            execute_query_mock.return_value = {"is_success": False, "body": "error"}
            result = self.async_run_with_timeout(graphql_query_executor.place_order(
                order_info,
                signature,
            ))

        self.assertIsNone(result)

        execute_query_mock.assert_called_once_with(
            query=query,
            parameters=parameters,
            field_name=field_name,
            throttler_limit_id="PlaceOrder"
        )

    def test_listen_to_private_events(self):
        graphql_query_executor = GrapQLQueryExecutor(MagicMock(), MagicMock())

        address = "0xENFLX"
        event_handler_mock = MagicMock()
        event_handler_mock.side_effect = Exception

        with patch("hummingbot.connector.exchange.polkadex.polkadex_query_executor.GrapQLQueryExecutor._subscribe_to_stream") as subscribe_to_stream_mock:
            subscribe_to_stream_mock.return_value = AsyncIter([23, 42])
            with self.assertRaises(SystemExit):
                self.async_run_with_timeout(graphql_query_executor.listen_to_private_events(
                    event_handler_mock,
                    address,
                ))

        subscribe_to_stream_mock.assert_called_once_with(stream_name=address)
        event_handler_mock.assert_called_once_with(event=23)

    def test_listen_to_public_trades(self):
        graphql_query_executor = GrapQLQueryExecutor(MagicMock(), MagicMock())

        market_symbol = "BTC/USDT"
        stream_name = f"{market_symbol}-recent-trades"
        event_handler_mock = MagicMock()
        event_handler_mock.side_effect = Exception

        with patch("hummingbot.connector.exchange.polkadex.polkadex_query_executor.GrapQLQueryExecutor._subscribe_to_stream") as subscribe_to_stream_mock:
            subscribe_to_stream_mock.return_value = AsyncIter([23, 42])
            with self.assertRaises(SystemExit):
                self.async_run_with_timeout(graphql_query_executor.listen_to_public_trades(
                    event_handler_mock,
                    market_symbol,
                ))

        subscribe_to_stream_mock.assert_called_once_with(stream_name=stream_name)
        event_handler_mock.assert_called_once_with(event=23)

    def test_listen_to_orderbook_updates(self):
        graphql_query_executor = GrapQLQueryExecutor(MagicMock(), MagicMock())

        market_symbol = "BTC/USDT"
        stream_name = f"{market_symbol}-ob-inc"
        event_handler_mock = MagicMock()
        event_handler_mock.side_effect = Exception

        with patch("hummingbot.connector.exchange.polkadex.polkadex_query_executor.GrapQLQueryExecutor._subscribe_to_stream") as subscribe_to_stream_mock:
            subscribe_to_stream_mock.return_value = AsyncIter([23, 42])
            with self.assertRaises(SystemExit):
                self.async_run_with_timeout(graphql_query_executor.listen_to_orderbook_updates(
                    event_handler_mock,
                    market_symbol,
                ))

        subscribe_to_stream_mock.assert_called_once_with(stream_name=stream_name)
        event_handler_mock.assert_called_once_with(event=23, market_symbol=market_symbol)

    def test_set_websocket_failure_timestamp(self):
        graphql_query_executor = GrapQLQueryExecutor(MagicMock(), MagicMock())

        self.assertEqual(graphql_query_executor._websocket_failure_timestamp, float(0))
        self.assertFalse(graphql_query_executor._websocket_failure)
        dt = datetime(2020, 5, 9)

        with patch("hummingbot.connector.exchange.polkadex.polkadex_query_executor.datetime") as datetime_mock:
            datetime_mock.utcnow = MagicMock(return_value=dt)
            self.async_run_with_timeout(graphql_query_executor.set_websocket_failure_timestamp())

        self.assertEqual(graphql_query_executor._websocket_failure_timestamp, dt.timestamp())
        self.assertTrue(graphql_query_executor._websocket_failure)

    def test_websocket_connect_failure_no_failure(self):
        graphql_query_executor = GrapQLQueryExecutor(MagicMock(), MagicMock())

        self.assertEqual(graphql_query_executor._websocket_failure_timestamp, float(0))
        self.assertFalse(graphql_query_executor._websocket_failure)
        self.assertFalse(graphql_query_executor._restart_initialization)
        dt = datetime(2020, 5, 9)

        with patch("hummingbot.connector.exchange.polkadex.polkadex_query_executor.datetime") as datetime_mock:
            datetime_mock.utcnow = MagicMock(return_value=dt)
            self.async_run_with_timeout(graphql_query_executor.websocket_connect_failure())

        self.assertEqual(graphql_query_executor._websocket_failure_timestamp, dt.timestamp())
        self.assertTrue(graphql_query_executor._websocket_failure)
        self.assertFalse(graphql_query_executor._restart_initialization)

    def test_websocket_connect_failure_with_previous_failure(self):
        graphql_query_executor = GrapQLQueryExecutor(MagicMock(), MagicMock())

        dt = datetime(2020, 5, 9)
        graphql_query_executor._websocket_failure_timestamp = dt.timestamp()
        graphql_query_executor._websocket_failure = True

        self.assertFalse(graphql_query_executor._restart_initialization)

        with patch("hummingbot.connector.exchange.polkadex.polkadex_query_executor.datetime") as datetime_mock:
            datetime_mock.utcnow = MagicMock(return_value=datetime(2020, 5, 10))
            self.async_run_with_timeout(graphql_query_executor.websocket_connect_failure())

        self.assertEqual(graphql_query_executor._websocket_failure_timestamp, dt.timestamp())
        self.assertTrue(graphql_query_executor._websocket_failure)
        self.assertTrue(graphql_query_executor._restart_initialization)
