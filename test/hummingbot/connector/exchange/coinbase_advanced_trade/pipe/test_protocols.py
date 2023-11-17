import unittest
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from hummingbot.connector.exchange.coinbase_advanced_trade.pipe import PipeGetPtl, PipePtl, PipePutPtl, PutOperationPtl
from hummingbot.connector.exchange.coinbase_advanced_trade.pipe.pipe import Pipe


class MockPipeGetPtl(PipeGetPtl):
    def __init__(self):
        self._size = MagicMock(return_value=10)

    @property
    def size(self) -> int:
        return self._size()

    async def get(self) -> Any:
        return AsyncMock()

    def task_done(self) -> None:
        pass

    async def join(self) -> None:
        pass

    async def snapshot(self) -> Any:
        return AsyncMock()


class MockPipePutPtl(PipePutPtl):
    async def put(self, item: Any, *, timeout: float = 10) -> None:
        pass

    def full(self) -> bool:
        return False

    async def stop(self) -> None:
        pass


class MockPipePtl(PipePtl):
    _logger = MagicMock()

    @classmethod
    def logger(cls) -> Any:
        return cls._logger

    @property
    def pipe(self) -> Any:
        return MagicMock()

    @property
    def is_stopped(self) -> bool:
        return False


class MockPutOperationPtl(PutOperationPtl):
    async def __call__(self, item: Any, **kwargs: Any) -> None:
        pass


class TestPipeProtocols(IsolatedAsyncioWrapperTestCase):

    async def test_mock_pipe_get_ptl(self):
        mock = MockPipeGetPtl()
        self.assertIsInstance(mock.size, int)
        self.assertIsNone(mock.task_done())
        self.assertIsNone(await (mock.join()))
        self.assertIsNotNone(await (mock.snapshot()))

    async def test_mock_pipe_put_ptl(self):
        mock = MockPipePutPtl()
        self.assertIsNone(await (mock.put("test")))
        self.assertFalse(mock.full())
        self.assertIsNone(await (mock.stop()))

    async def test_mock_pipe_ptl(self):
        mock = MockPipePtl()
        self.assertIsNotNone(MockPipePtl.logger())
        self.assertFalse(mock.is_stopped)

    async def test_mock_put_operation_ptl(self):
        mock = MockPutOperationPtl()
        self.assertIsNone(await (mock("test")))


class TestPipeImplementation(unittest.TestCase):

    def setUp(self):
        self.pipe = Pipe(maxsize=10)  # Adjust parameters as needed

    def test_pipe_is_instance_of_pipeptl(self):
        self.assertTrue(isinstance(self.pipe, PipePtl))

    def test_pipe_is_instance_of_pipegetptl(self):
        self.assertTrue(isinstance(self.pipe, PipeGetPtl))

    def test_pipe_is_instance_of_pipeputptl(self):
        self.assertTrue(isinstance(self.pipe, PipePutPtl))


if __name__ == "__main__":
    unittest.main()
