import asyncio
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import List
from unittest.mock import AsyncMock, MagicMock

from hummingbot.connector.exchange.coinbase_advanced_trade.fittings.pipes_pipe_fitting import PipesPipeFitting
from hummingbot.connector.exchange.coinbase_advanced_trade.pipe.pipe import Pipe


class TestPipesPipeFitting(IsolatedAsyncioWrapperTestCase):

    async def asyncSetUp(self) -> None:
        self.source_pipes: List[Pipe] = [MagicMock(spec=Pipe[str]()) for _ in range(3)]
        self.destination_pipe: Pipe[str] = MagicMock(spec=Pipe[str]())

        self.pipes_collector: PipesPipeFitting[str, str] = MagicMock(spec=PipesPipeFitting(
            sources=tuple(self.source_pipes), destination=self.destination_pipe
        ))

    def test_start_task(self) -> None:
        # Mock the start_all_tasks method of the PipePipeFitting instances
        for pipe_block in self.pipes_collector._pipe_blocks:
            pipe_block.start_task = MagicMock()
            pipe_block.is_running = MagicMock(return_value=False)

        self.pipes_collector.start_all_tasks()

        # Assert that start_all_tasks was called on each PipePipeFitting instance
        for pipe_block in self.pipes_collector._pipe_blocks:
            pipe_block.start_task.assert_called_once()

    async def test_stop_task(self) -> None:
        # Mock the stop_all_tasks method of the PipePipeFitting instances
        for pipe_block in self.pipes_collector._pipe_blocks:
            pipe_block.stop_task = AsyncMock()
            pipe_block.is_running = MagicMock(return_value=True)

        await self.pipes_collector.stop_all_tasks()

        # Assert that stop_all_tasks was called on each PipePipeFitting instance
        for pipe_block in self.pipes_collector._pipe_blocks:
            pipe_block.stop_task.assert_called_once()

    async def test_integration(self) -> None:
        class InfiniteAsyncIterable:
            """An async iterable that produces an infinite sequence of messages."""

            def __init__(self, base_message="message"):
                self.base_message = base_message
                self.count = 0

            def __aiter__(self):
                return self

            async def __anext__(self):
                message = f"{self.base_message} {self.count}"
                self.count += 1
                return message

        # Prepare an endless stream of messages
        messages = InfiniteAsyncIterable()

        # Feed the messages to the source pipes
        self.source_pipes: List[Pipe] = [Pipe[str]() for _ in range(3)]
        for pipe in self.source_pipes:
            for _ in range(5):  # we only take the first 5 messages for simplicity
                msg = await messages.__anext__()
                await pipe.put(msg)

        # Start the tasks
        self.pipes_collector: PipesPipeFitting[str, str] = PipesPipeFitting(
            sources=tuple(self.source_pipes), destination=self.destination_pipe
        )
        self.pipes_collector.start_all_tasks()
        await asyncio.sleep(0.1)  # give the tasks time to start

        # Check the running status
        self.assertTrue(all(self.pipes_collector.are_running()))

        await asyncio.sleep(0.1)  # Let some messages flow

        # Stop the tasks
        await self.pipes_collector.stop_all_tasks()
        await asyncio.sleep(0.1)  # give the tasks time to stop

        # Check the running status
        self.assertFalse(any(self.pipes_collector.are_running()))

        # Check the messages in the destination pipe
        # In some cases there can be 3 SENTINEL in the destination (one from each source pipe)
        self.destination_pipe.put.assert_called()
        self.assertGreaterEqual(len(self.destination_pipe.put.mock_calls), len(self.source_pipes) * 5)
        for pipe in self.source_pipes:
            self.assertEqual(pipe.size, 0)
