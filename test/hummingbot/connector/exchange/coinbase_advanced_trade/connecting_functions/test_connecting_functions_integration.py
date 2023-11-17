from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock, call

from hummingbot.connector.exchange.coinbase_advanced_trade.connecting_functions import pipe_to_pipe_connector
from hummingbot.connector.exchange.coinbase_advanced_trade.pipe.protocols import PipeGetPtl, PipePutPtl
from hummingbot.connector.exchange.coinbase_advanced_trade.pipe.sentinel import SENTINEL


class TestIntegration(IsolatedAsyncioWrapperTestCase):
    async def test_pipe_integration(self):
        # Setup
        source_data = ["item1", "item2", "item3"]
        source = AsyncMock(spec=PipeGetPtl)
        source.get.side_effect = source_data + [SENTINEL]
        destination = AsyncMock(spec=PipePutPtl)
        handler = MagicMock(side_effect=lambda x: x.upper())  # Example handler that converts items to uppercase

        # Execute
        await pipe_to_pipe_connector(
            source=source,
            handler=handler,
            destination=destination
        )

        # Test
        expected_calls = [call(item.upper(), timeout=0.1) for item in source_data]
        destination.put.assert_has_awaits(expected_calls)
        self.assertEqual(handler.call_count, len(source_data))
