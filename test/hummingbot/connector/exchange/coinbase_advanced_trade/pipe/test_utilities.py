from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock, call

from hummingbot.connector.exchange.coinbase_advanced_trade.pipe import (
    SENTINEL,
    PipeGetPtl,
    PipePutPtl,
    PutOperationPtl,
    pipe_snapshot,
    process_residual_data_on_cancel,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.pipe.errors import PipeFullError, PipeTypeError


class TestPipeSnapshot(IsolatedAsyncioWrapperTestCase):

    async def test_snapshot_success(self):
        pipe = AsyncMock(spec=PipeGetPtl)
        pipe.snapshot = AsyncMock(return_value="snapshot")
        result = await pipe_snapshot(pipe)
        self.assertEqual(result, "snapshot")
        pipe.snapshot.assert_awaited_once()

    async def test_snapshot_failure(self):
        pipe = AsyncMock(spec=PipePutPtl)  # Incorrect type
        with self.assertRaises(PipeTypeError):
            await pipe_snapshot(pipe)


class TestProcessResidualDataOnCancel(IsolatedAsyncioWrapperTestCase):

    async def test_process_data_success(self):
        source = AsyncMock(spec=PipeGetPtl)
        put_operation = AsyncMock(spec=PutOperationPtl)
        destination = AsyncMock(spec=PipePutPtl)

        source.snapshot = AsyncMock(return_value=(1, 2, SENTINEL))
        await process_residual_data_on_cancel(source, put_operation, destination)

        put_operation.assert_has_awaits([
            call(1),
            call(2)], any_order=False)
        destination.stop.assert_awaited_once()

    async def test_process_data_passed_as_list(self):
        source = AsyncMock(spec=PipeGetPtl)
        put_operation = AsyncMock(spec=PutOperationPtl)
        destination = AsyncMock(spec=PipePutPtl)

        source.snapshot = AsyncMock(return_value=[1, 2, SENTINEL])
        await process_residual_data_on_cancel(source, put_operation, destination)

        put_operation.assert_has_awaits([call([1, 2, SENTINEL])], any_order=False)
        destination.stop.assert_awaited_once()

    async def test_process_data_when_destination_full(self):
        source = AsyncMock(spec=PipeGetPtl)
        put_operation = AsyncMock(spec=PutOperationPtl)
        destination = AsyncMock(spec=PipePutPtl)
        logger = MagicMock()

        source.snapshot = AsyncMock(return_value=(1, 2, SENTINEL))
        put_operation.side_effect = PipeFullError
        await process_residual_data_on_cancel(source, put_operation, destination, logger)

        put_operation.assert_awaited_once_with(1)
        destination.stop.assert_awaited_once()
        logger.error.assert_called_once()
