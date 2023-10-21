from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Tuple
from unittest.mock import AsyncMock, MagicMock, call, patch

from hummingbot.connector.exchange.coinbase_advanced_trade.multi_stream_data_source.multi_stream_data_source import (
    MultiStreamDataSource,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.pipeline.pipe_block import PipeBlock
from hummingbot.connector.exchange.coinbase_advanced_trade.stream_data_source.enums import StreamState
from hummingbot.connector.exchange.coinbase_advanced_trade.task_manager import TaskState


class TestMultiStreamDataSource(IsolatedAsyncioWrapperTestCase):

    async def asyncSetUp(self):
        await super().asyncSetUp()

        # Create a mock stream
        self.stream_mock = AsyncMock()
        self.stream_mock.channel = "test_channel"
        self.stream_mock.pair = "test_pair"

        # Create a mock MultiStreamDataSource
        self.msds = MultiStreamDataSource(
            channels=("channel1", "channel2"),
            pairs=("pair1", "pair2"),
            ws_factory=AsyncMock(),
            ws_url="ws://example.com",
            pair_to_symbol=AsyncMock(),
            subscription_builder=AsyncMock(),
            sequence_reader=MagicMock(),
            transformers=[AsyncMock()],
            collector=AsyncMock()
        )

        for k in self.msds._streams.keys():
            self.msds._streams[k] = AsyncMock()
            self.msds._streams[k].start_task = AsyncMock()
            self.msds._streams[k].stop_task = AsyncMock()
            self.msds._streams[k].open_connection = AsyncMock()
            self.msds._streams[k].close_connection = AsyncMock()

    async def test_open(self):
        with patch.object(MultiStreamDataSource,
                          '_perform_on_all_streams',
                          new_callable=AsyncMock) as mock_perform:
            with patch.object(MultiStreamDataSource,
                              '_pop_unsuccessful_streams',
                              new_callable=AsyncMock) as mock_pop:
                await self.msds.open()
        mock_perform.assert_has_awaits([call(self.msds._open_connection)])
        mock_pop.assert_has_awaits([call(mock_perform.return_value)])

    async def test_close(self):
        with patch.object(MultiStreamDataSource, 'logger') as logger_mock:
            await self.msds.close()
            for s in self.msds._streams.values():
                s.close_connection.assert_awaited()
            # Logger will find that the asyncmock does not set the state and thus a warning is emitted
            logger_mock().warning.assert_called()

    async def test_subscribe(self):
        with patch.object(MultiStreamDataSource,
                          '_perform_on_all_streams',
                          new_callable=AsyncMock) as mock_perform:
            with patch.object(MultiStreamDataSource,
                              '_pop_unsuccessful_streams',
                              new_callable=AsyncMock) as mock_pop:
                await self.msds.subscribe()
        mock_perform.assert_has_awaits([call(self.msds._subscribe)])
        mock_pop.assert_has_awaits([call(mock_perform.return_value)])

    async def test_unsubscribe(self):
        with patch.object(MultiStreamDataSource,
                          '_perform_on_all_streams',
                          new_callable=AsyncMock) as mock_perform:
            await self.msds.unsubscribe()
        mock_perform.assert_has_awaits([call(self.msds._unsubscribe)])

    @patch.object(MultiStreamDataSource, 'logger')
    async def test_start_stream(self, mock_logger):
        with patch.object(self.msds._collector, 'start_all_tasks', new_callable=AsyncMock) as mock_collector_task:
            with patch.object(PipeBlock, 'start_task', new_callable=AsyncMock) as mock_transformers_task:
                with patch.object(MultiStreamDataSource,
                                  '_perform_on_all_streams',
                                  new_callable=AsyncMock) as mock_perform:
                    with patch.object(MultiStreamDataSource,
                                      '_pop_unsuccessful_streams',
                                      new_callable=AsyncMock) as mock_pop:
                        await self.msds.start_stream()
        mock_collector_task.assert_awaited()
        mock_transformers_task.assert_awaited()
        mock_perform.assert_has_awaits([call(self.msds._open_connection), call(self.msds._start_task), ])
        mock_pop.assert_has_awaits([call(mock_perform.return_value), call(mock_perform.return_value)])
        mock_logger().warning.assert_called()

    async def test_stop_stream(self):
        with patch.object(MultiStreamDataSource, 'logger') as logger_mock:
            await self.msds.stop_stream()
            for s in self.msds._streams.values():
                s.close_connection.assert_awaited()
                s.stop_task.assert_awaited()
            # Logger will find that the asyncmock does not set the state and thus a warning is emitted
            logger_mock().warning.assert_called()

    async def test__perform_on_all_streams(self):
        with patch.object(MultiStreamDataSource, 'logger') as logger_mock:
            results: Tuple[bool, ...] = await self.msds._perform_on_all_streams(self.msds._close_connection)
            self.assertTrue(all(results))
            for s in self.msds._streams.values():
                s.close_connection.assert_awaited()
            # Logger will find that the asyncmock does not set the state and thus a warning is emitted
            logger_mock().warning.assert_called()

    async def test__perform_on_all_streams_failure(self):
        failing_stream = next(iter(self.msds._streams.values()))
        failing_stream.close_connection.side_effect = Exception("Test exception")

        with patch.object(MultiStreamDataSource, 'logger') as logger_mock:
            results: Tuple[bool, ...] = await self.msds._perform_on_all_streams(self.msds._close_connection)
        logger_mock().error.assert_called()
        self.assertFalse(all(results))

    async def test__perform_on_all_streams_custom_action(self):
        async def custom_action(stream):
            await stream.close_connection()

        results: Tuple[bool, ...] = await self.msds._perform_on_all_streams(custom_action)
        self.assertTrue(all(results))

    async def test__pop_unsuccessful_streams(self):
        with patch.object(MultiStreamDataSource, 'logger') as logger_mock:
            self.msds._streams = {
                "channel1:pair1": AsyncMock(),
                "channel2:pair2": AsyncMock(),
                "channel3:pair3": AsyncMock()
            }
            # Simulate some streams being unsuccessful
            done = (True, False, True)
            await self.msds._pop_unsuccessful_streams(done)

            self.assertNotIn("channel2:pair2", self.msds._streams)
            self.assertIn("channel1:pair1", self.msds._streams)
            self.assertIn("channel3:pair3", self.msds._streams)
            logger_mock().warning.assert_called()

    async def test__open_connection_successful(self):
        self.stream_mock.state = [StreamState.OPENED, TaskState.STOPPED]
        result = await self.msds._open_connection(self.stream_mock)
        self.assertTrue(result)

    async def test__open_connection_unsuccessful(self):
        self.stream_mock.state = [StreamState.CLOSED, TaskState.STOPPED]
        with patch.object(MultiStreamDataSource, 'logger') as logger_mock:
            result = await self.msds._open_connection(self.stream_mock)
            logger_mock().warning.assert_called()
        self.assertFalse(result)

    async def test__subscribe_successful(self):
        self.stream_mock.state = [StreamState.SUBSCRIBED, TaskState.STOPPED]
        result = await self.msds._subscribe(self.stream_mock)
        self.assertTrue(result)

    async def test__subscribe_unsuccessful(self):
        self.stream_mock.state = [StreamState.UNSUBSCRIBED, TaskState.STOPPED]
        with patch.object(MultiStreamDataSource, 'logger') as logger_mock:
            result = await self.msds._subscribe(self.stream_mock)
            logger_mock().warning.assert_called()
        self.assertFalse(result)

    async def test__start_task_successful(self):
        self.stream_mock.state = [StreamState.SUBSCRIBED, TaskState.STARTED]
        result = await self.msds._start_task(self.stream_mock)
        self.assertTrue(result)

    async def test__start_task_unsuccessful(self):
        self.stream_mock.state = [StreamState.SUBSCRIBED, TaskState.STOPPED]
        with patch.object(MultiStreamDataSource, 'logger') as logger_mock:
            result = await self.msds._start_task(self.stream_mock)
            logger_mock().warning.assert_called()
        self.assertFalse(result)

    async def test__unsubscribe_successful(self):
        self.stream_mock.state = [StreamState.UNSUBSCRIBED, TaskState.STOPPED]
        result = await self.msds._unsubscribe(self.stream_mock)
        self.assertTrue(result)

    async def test__unsubscribe_unsuccessful(self):
        self.stream_mock.state = [StreamState.SUBSCRIBED, TaskState.STOPPED]
        with patch.object(MultiStreamDataSource, 'logger') as logger_mock:
            result = await self.msds._unsubscribe(self.stream_mock)
            logger_mock().warning.assert_called()
        self.assertFalse(result)
