from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from hummingbot.connector.exchange.coinbase_advanced_trade.fittings.pipe_pipe_fitting import PipePipeFitting
from hummingbot.connector.exchange.coinbase_advanced_trade.single_stream_data_source.single_stream_data_source import (
    SingleStreamDataSource,
    _close_connection,
    _open_connection,
    _start_task,
    _stop_task,
    _stop_task_nowait,
    _subscribe,
    _unsubscribe,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.stream_data_source.enums import StreamState
from hummingbot.connector.exchange.coinbase_advanced_trade.stream_data_source.stream_data_source import StreamDataSource
from hummingbot.connector.exchange.coinbase_advanced_trade.task_manager import TaskState


class TestSingleStreamDataSourceOperations(IsolatedAsyncioWrapperTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.stream = MagicMock(spec=StreamDataSource)
        self.stream.channel = "test_channel"
        self.stream.pairs = ["pair1", "pair2"]
        self.logger = MagicMock()

    def change_state_to_opened(self):
        self.stream.state = (StreamState.OPENED, TaskState.STOPPED)

    def change_state_to_closed(self):
        self.stream.state = (StreamState.CLOSED, TaskState.STOPPED)

    def change_state_to_subscribed(self):
        self.stream.state = (StreamState.SUBSCRIBED, TaskState.STOPPED)

    def change_state_to_unsubscribed(self):
        self.stream.state = (StreamState.UNSUBSCRIBED, TaskState.STOPPED)

    def change_state_to_started(self):
        self.stream.state = (StreamState.CLOSED, TaskState.STARTED)

    def change_state_to_stopped(self):
        self.stream.state = (StreamState.CLOSED, TaskState.STOPPED)

    async def test__open_connection_when_closed(self):
        self.stream.open_connection = AsyncMock()
        self.stream.state = (StreamState.CLOSED, TaskState.STOPPED)

        self.stream.open_connection.side_effect = self.change_state_to_opened

        result = await _open_connection(self.stream, self.logger)

        self.assertTrue(result)
        self.stream.open_connection.assert_awaited_once()
        self.assertEqual(StreamState.OPENED, self.stream.state[0], )
        self.logger.warning.assert_not_called()

    async def test__open_connection_failed(self):
        self.stream.open_connection = AsyncMock()
        self.stream.state = (StreamState.CLOSED, TaskState.STOPPED)

        result = await _open_connection(self.stream, self.logger)

        self.assertFalse(result)
        self.stream.open_connection.assert_awaited_once()
        self.assertEqual(StreamState.CLOSED, self.stream.state[0], )
        self.logger.warning.assert_called_with(
            f"Stream {self.stream.channel}:{','.join(self.stream.pairs)} failed to open.")

    async def test__open_connection_when_not_closed(self):
        self.stream.open_connection = AsyncMock()
        for s in (StreamState.OPENED, StreamState.SUBSCRIBED, StreamState.UNSUBSCRIBED):
            self.stream.state = (s, TaskState.STOPPED)

            result = await _open_connection(self.stream, self.logger)

            self.assertTrue(result)
            self.stream.open_connection.assert_not_awaited()
            self.assertEqual(s, self.stream.state[0])
            self.logger.warning.assert_not_called()

    async def test__close_connection_when_subscribed(self):
        self.stream.close_connection = AsyncMock()
        self.stream.state = [StreamState.SUBSCRIBED]

        self.stream.close_connection.side_effect = self.change_state_to_closed

        result = await _close_connection(self.stream, self.logger)

        self.assertTrue(result)
        self.stream.unsubscribe.assert_awaited_once()
        self.stream.close_connection.assert_awaited_once()
        self.assertEqual(StreamState.CLOSED, self.stream.state[0])
        self.logger.warning.assert_not_called()

    async def test__close_connection_when_opened(self):
        self.stream.close_connection = AsyncMock()
        self.stream.state = [StreamState.OPENED]

        self.stream.close_connection.side_effect = self.change_state_to_closed

        result = await _close_connection(self.stream, self.logger)

        self.assertTrue(result)
        self.stream.close_connection.assert_awaited_once()
        self.assertEqual(StreamState.CLOSED, self.stream.state[0])
        self.logger.warning.assert_not_called()

    async def test__close_connection_when_already_closed(self):
        self.stream.close_connection = AsyncMock()
        self.stream.state = [StreamState.CLOSED]

        result = await _close_connection(self.stream, self.logger)

        self.assertTrue(result)
        self.stream.close_connection.assert_not_called()
        self.logger.warning.assert_not_called()

    async def test__close_connection_failed(self):
        self.stream.close_connection = AsyncMock()
        self.stream.state = [StreamState.OPENED]

        result = await _close_connection(self.stream, self.logger)

        self.assertFalse(result)
        self.stream.close_connection.assert_awaited_once()
        self.assertEqual(StreamState.OPENED, self.stream.state[0])
        self.logger.warning.assert_called_with(
            f"Stream {self.stream.channel}:{','.join(self.stream.pairs)} failed to close.")

    async def test__subscribe_when_closed(self):
        self.stream.subscribe = AsyncMock()
        self.stream.state = [StreamState.CLOSED, TaskState.STARTED]

        self.stream.subscribe.side_effect = self.change_state_to_subscribed

        result = await _subscribe(self.stream, self.logger)

        self.assertTrue(result)
        self.stream.subscribe.assert_awaited_once()
        self.assertEqual(StreamState.SUBSCRIBED, self.stream.state[0])
        self.logger.warning.assert_not_called()

    async def test__subscribe_when_already_subscribed(self):
        self.stream.subscribe = AsyncMock()
        self.stream.state = [StreamState.SUBSCRIBED, TaskState.STOPPED]

        result = await _subscribe(self.stream, self.logger)

        self.assertTrue(result)
        self.stream.subscribe.assert_not_called()
        self.logger.warning.assert_not_called()

    async def test__subscribe_failed(self):
        self.stream.subscribe = AsyncMock()
        self.stream.state = [StreamState.CLOSED, TaskState.STOPPED]

        result = await _subscribe(self.stream, self.logger)

        self.assertFalse(result)
        self.stream.subscribe.assert_awaited_once()
        self.assertEqual(StreamState.CLOSED, self.stream.state[0])
        self.logger.warning.assert_called_with(
            f"Stream {self.stream.channel}:{','.join(self.stream.pairs)} failed to subscribe.")

    async def test_unsubscribe_when_subscribed(self):
        self.stream.unsubscribe = AsyncMock()
        self.stream.state = [StreamState.SUBSCRIBED]

        self.stream.unsubscribe.side_effect = self.change_state_to_unsubscribed

        result = await _unsubscribe(self.stream, self.logger)

        self.assertTrue(result)
        self.stream.unsubscribe.assert_awaited_once()
        self.assertEqual(StreamState.UNSUBSCRIBED, self.stream.state[0])
        self.logger.warning.assert_not_called()

    async def test_unsubscribe_when_already_unsubscribed(self):
        self.stream.unsubscribe = AsyncMock()
        self.stream.state = [StreamState.UNSUBSCRIBED]

        result = await _unsubscribe(self.stream, self.logger)

        self.assertTrue(result)
        self.stream.unsubscribe.assert_not_called()
        self.logger.warning.assert_not_called()

    async def test_unsubscribe_failed(self):
        self.stream.unsubscribe = AsyncMock()
        self.stream.state = [StreamState.SUBSCRIBED]

        result = await _unsubscribe(self.stream, self.logger)

        self.assertFalse(result)
        self.stream.unsubscribe.assert_awaited_once()
        self.assertEqual(StreamState.SUBSCRIBED, self.stream.state[0])
        self.logger.warning.assert_called_with(
            f"Stream {self.stream.channel}:{','.join(self.stream.pairs)} failed to unsubscribe.")

    async def test__start_task_when_started(self):
        self.stream.start_task = AsyncMock()
        self.stream.state = (StreamState.SUBSCRIBED, TaskState.STARTED)

        result = await _start_task(self.stream, self.logger)

        self.assertTrue(result)
        self.stream.start_task.assert_not_called()
        self.assertEqual((StreamState.SUBSCRIBED, TaskState.STARTED), self.stream.state)
        self.logger.warning.assert_not_called()

    async def test__start_task_when_stopped(self):
        self.stream.start_task = AsyncMock()
        self.stream.state = (StreamState.CLOSED, TaskState.STOPPED)

        self.stream.start_task.side_effect = self.change_state_to_started

        result = await _start_task(self.stream, self.logger)

        self.assertTrue(result)
        self.stream.start_task.assert_called_once()
        self.assertEqual((StreamState.CLOSED, TaskState.STARTED), self.stream.state)
        self.logger.warning.assert_not_called()

    async def test__start_task_failed(self):
        self.stream.start_task = AsyncMock()
        self.stream.state = (StreamState.CLOSED, TaskState.STOPPED)

        result = await _start_task(self.stream, self.logger)

        self.assertFalse(result)
        self.stream.start_task.assert_called_once()
        self.assertEqual((StreamState.CLOSED, TaskState.STOPPED), self.stream.state)
        self.logger.warning.assert_called_with(
            f"Stream {self.stream.channel}:{','.join(self.stream.pairs)} failed to start the task.")

    async def test__stop_task_when_stopped(self):
        self.stream.stop_task = AsyncMock()
        self.stream.state = (StreamState.SUBSCRIBED, TaskState.STOPPED)

        result = await _stop_task(self.stream, self.logger)

        self.assertTrue(result)
        self.stream.stop_task.assert_not_awaited()
        self.assertEqual((StreamState.SUBSCRIBED, TaskState.STOPPED), self.stream.state)
        self.logger.warning.assert_not_called()

    async def test__stop_task_when_started(self):
        self.stream.stop_task = AsyncMock()
        self.stream.state = (StreamState.CLOSED, TaskState.STARTED)

        self.stream.stop_task.side_effect = self.change_state_to_stopped

        result = await _stop_task(self.stream, self.logger)

        self.assertTrue(result)
        self.stream.stop_task.assert_called_once()
        self.assertEqual((StreamState.CLOSED, TaskState.STOPPED), self.stream.state)
        self.logger.warning.assert_not_called()

    async def test__stop_task_when_subscribed(self):
        self.stream.stop_task = AsyncMock()
        self.stream.state = (StreamState.SUBSCRIBED, TaskState.STARTED)

        self.stream.stop_task.side_effect = self.change_state_to_stopped

        result = await _stop_task(self.stream, self.logger)

        self.assertTrue(result)
        self.stream.stop_task.assert_called_once()
        # The StreamState.CLOSED is an artifact of the change_state_to_stopped() method
        self.assertEqual((StreamState.CLOSED, TaskState.STOPPED), self.stream.state)
        self.logger.warning.assert_called_with(
            f"Stream {self.stream.channel}:{','.join(self.stream.pairs)} stopping its task while SUBSCRIBED.")

    async def test__stop_task_failed(self):
        self.stream.stop_task = AsyncMock()
        self.stream.state = (StreamState.CLOSED, TaskState.STARTED)

        result = await _stop_task(self.stream, self.logger)

        self.assertFalse(result)
        self.stream.stop_task.assert_called_once()
        self.assertEqual((StreamState.CLOSED, TaskState.STARTED), self.stream.state)
        self.logger.warning.assert_called_with(
            f"Stream {self.stream.channel}:{','.join(self.stream.pairs)} failed to stop the task.")

    def test__stop_task_nowait_when_stopped(self):
        self.stream.stop_task_nowait = MagicMock()
        self.stream.state = (StreamState.SUBSCRIBED, TaskState.STOPPED)

        result = _stop_task_nowait(self.stream, self.logger)

        self.assertTrue(result)
        self.stream.stop_task_nowait.assert_not_called()
        self.assertEqual((StreamState.SUBSCRIBED, TaskState.STOPPED), self.stream.state)
        self.logger.warning.assert_not_called()

    def test__stop_task_nowait_when_started(self):
        self.stream.stop_task_nowait = MagicMock()
        self.stream.state = (StreamState.CLOSED, TaskState.STARTED)

        self.stream.stop_task_nowait.side_effect = self.change_state_to_stopped

        result = _stop_task_nowait(self.stream, self.logger)

        self.assertTrue(result)
        self.stream.stop_task_nowait.assert_called_once()
        self.assertEqual((StreamState.CLOSED, TaskState.STOPPED), self.stream.state)
        self.logger.warning.assert_not_called()

    def test__stop_task_nowait_when_subscribed(self):
        self.stream.stop_task_nowait = MagicMock()
        self.stream.state = (StreamState.SUBSCRIBED, TaskState.STARTED)

        self.stream.stop_task_nowait.side_effect = self.change_state_to_stopped

        result = _stop_task_nowait(self.stream, self.logger)

        self.assertTrue(result)
        self.stream.stop_task_nowait.assert_called_once()
        # The StreamState.CLOSED is an artifact of the change_state_to_stopped() method
        self.assertEqual((StreamState.CLOSED, TaskState.STOPPED), self.stream.state)
        self.logger.warning.assert_called_with(
            f"Stream {self.stream.channel}:{','.join(self.stream.pairs)} stopping its task while SUBSCRIBED.")

    def test__stop_task_nowait_failed(self):
        self.stream.stop_task_nowait = MagicMock()
        self.stream.state = (StreamState.CLOSED, TaskState.STARTED)

        result = _stop_task_nowait(self.stream, self.logger)

        self.assertFalse(result)
        self.stream.stop_task_nowait.assert_called_once()
        self.assertEqual((StreamState.CLOSED, TaskState.STARTED), self.stream.state)
        self.logger.warning.assert_called_with(
            f"Stream {self.stream.channel}:{','.join(self.stream.pairs)} failed to stop the task.")


class TestSingleStreamDataSource(IsolatedAsyncioWrapperTestCase):

    async def asyncSetUp(self):
        await super().asyncSetUp()

        # Create a mock SingleStreamDataSource
        self.ssds = SingleStreamDataSource(
            channel="channel1",
            pairs=("pair1", "pair2"),
            ws_factory=AsyncMock(),
            ws_url="ws://example.com",
            pair_to_symbol=AsyncMock(),
            subscription_builder=AsyncMock(),
            sequence_reader=MagicMock(),
            transformers=[AsyncMock()],
        )

    def test_sync_stream_methods(self):
        for m in ("stop_task_nowait",):
            with patch.object(SingleStreamDataSource, m, new_callable=MagicMock) as mock_method:
                getattr(self.ssds, m)()
                mock_method.assert_called_once_with()

    @patch.object(SingleStreamDataSource, 'logger')
    async def test_start_stream(self, mock_logger):
        with patch.object(PipePipeFitting, 'start_task', new_callable=AsyncMock) as mock_start_task:
            with patch.object(PipePipeFitting, 'is_running', new_callable=PropertyMock) as mock_is_running:
                with patch.object(SingleStreamDataSource, 'start_task', new_callable=AsyncMock) as stream_start:
                    with patch.object(SingleStreamDataSource, 'open_connection', new_callable=AsyncMock) as open_connection:
                        await self.ssds.start_stream()
                        mock_start_task.assert_called()
                        mock_is_running.assert_called()
                        stream_start.assert_called()
                        open_connection.assert_called()
                        mock_logger().warning.assert_not_called()
                        mock_logger().error.assert_not_called()

    @patch.object(SingleStreamDataSource, 'logger')
    async def test_start_stream_not_running(self, mock_logger):
        with patch.object(PipePipeFitting, 'start_task', new_callable=AsyncMock) as mock_start_task:
            with patch.object(PipePipeFitting, 'is_running', new_callable=PropertyMock) as mock_is_running:
                with patch.object(SingleStreamDataSource, 'start_task', new_callable=AsyncMock) as stream_start:
                    with patch.object(SingleStreamDataSource, 'open_connection', new_callable=AsyncMock) as open_connection:
                        mock_is_running.return_value = False
                        with self.assertRaises(RuntimeError):
                            await self.ssds.start_stream()
                        mock_start_task.assert_called()
                        mock_is_running.assert_called()
                        open_connection.assert_not_called()
                        stream_start.assert_not_called()
                        mock_logger().warning.assert_not_called()
                        mock_logger().error.assert_called_with("A transformer task failed to start for the stream.")

    @patch.object(SingleStreamDataSource, 'logger')
    async def test_stop_stream(self, mock_logger):
        with patch.object(PipePipeFitting, 'stop_task', new_callable=AsyncMock) as mock_stop_task:
            with patch.object(SingleStreamDataSource, 'stop_task', new_callable=AsyncMock) as stream_stop:
                with patch.object(SingleStreamDataSource, 'close_connection', new_callable=AsyncMock) as close_connection:
                    await self.ssds.stop_stream()
                    mock_stop_task.assert_called()
                    stream_stop.assert_called()
                    close_connection.assert_called()
                    mock_logger().warning.assert_not_called()
                    mock_logger().error.assert_not_called()

    async def test_open_connection(self):
        with patch.object(StreamDataSource, 'state', new_callable=PropertyMock) as mock_state:
            with patch.object(StreamDataSource, 'open_connection', new_callable=AsyncMock) as mock_method:
                mock_state.return_value = (StreamState.CLOSED, TaskState.STOPPED)

                # Define side effect to change the state when unsubscribe is called
                async def side_effect():
                    mock_state.return_value = (StreamState.OPENED, TaskState.STOPPED)

                mock_method.side_effect = side_effect

                result = await self.ssds.open_connection()
                self.assertTrue(result)
                mock_method.assert_awaited_once_with()

    async def test_close_connection(self):
        with patch.object(StreamDataSource, 'state', new_callable=PropertyMock) as mock_state:
            with patch.object(StreamDataSource, 'close_connection', new_callable=AsyncMock) as mock_method:
                mock_state.return_value = (StreamState.OPENED, TaskState.STOPPED)

                # Define side effect to change the state when unsubscribe is called
                async def side_effect():
                    mock_state.return_value = (StreamState.CLOSED, TaskState.STOPPED)

                mock_method.side_effect = side_effect

                result = await self.ssds.close_connection()
                self.assertTrue(result)
                mock_method.assert_awaited_once_with()

    async def test_subscribe(self):
        with patch.object(StreamDataSource, 'state', new_callable=PropertyMock) as mock_state:
            with patch.object(StreamDataSource, 'subscribe', new_callable=AsyncMock) as mock_method:
                mock_state.return_value = (StreamState.OPENED, TaskState.STOPPED)

                # Define side effect to change the state when unsubscribe is called
                async def side_effect():
                    mock_state.return_value = (StreamState.SUBSCRIBED, TaskState.STOPPED)

                mock_method.side_effect = side_effect

                result = await self.ssds.subscribe()
                self.assertTrue(result)
                mock_method.assert_awaited_once_with()

    async def test_unsubscribe_when_subscribed(self):
        with patch.object(StreamDataSource, 'state', new_callable=PropertyMock) as mock_state:
            with patch.object(StreamDataSource, 'unsubscribe', new_callable=AsyncMock) as mock_method:
                mock_state.return_value = (StreamState.SUBSCRIBED, TaskState.STOPPED)

                # Define side effect to change the state when unsubscribe is called
                async def side_effect():
                    mock_state.return_value = (StreamState.UNSUBSCRIBED, TaskState.STOPPED)

                mock_method.side_effect = side_effect

                result = await self.ssds.unsubscribe()
                self.assertTrue(result)
                mock_method.assert_awaited()

    async def test_unsubscribe_when_unsubscribed(self):
        with patch.object(StreamDataSource, 'state', new_callable=PropertyMock) as mock_state:
            with patch.object(StreamDataSource, 'unsubscribe', new_callable=AsyncMock) as mock_method:
                mock_state.return_value = (StreamState.UNSUBSCRIBED, TaskState.STOPPED)

                # Define side effect to change the state when unsubscribe is called
                async def side_effect():
                    mock_state.return_value = (StreamState.UNSUBSCRIBED, TaskState.STOPPED)

                mock_method.side_effect = side_effect

                result = await self.ssds.unsubscribe()
                self.assertTrue(result)
                mock_method.assert_not_called()

    async def test_start_task(self):
        with patch.object(StreamDataSource, 'state', new_callable=PropertyMock) as mock_state:
            with patch.object(StreamDataSource, 'start_task', new_callable=AsyncMock) as mock_method:
                mock_state.return_value = (StreamState.OPENED, TaskState.STOPPED)

                # Define side effect to change the state when unsubscribe is called
                async def side_effect():
                    mock_state.return_value = (StreamState.SUBSCRIBED, TaskState.STARTED)

                mock_method.side_effect = side_effect

                result = await self.ssds.start_task()
                self.assertTrue(result)
                mock_method.assert_awaited_once_with()

    async def test_stop_task(self):
        with patch.object(StreamDataSource, 'state', new_callable=PropertyMock) as mock_state:
            with patch.object(StreamDataSource, 'stop_task', new_callable=AsyncMock) as mock_method:
                mock_state.return_value = (StreamState.OPENED, TaskState.STARTED)

                # Define side effect to change the state when unsubscribe is called
                async def side_effect():
                    mock_state.return_value = (StreamState.SUBSCRIBED, TaskState.STOPPED)

                mock_method.side_effect = side_effect

                result = await self.ssds.stop_task()
                self.assertTrue(result)
                mock_method.assert_awaited_once_with()
