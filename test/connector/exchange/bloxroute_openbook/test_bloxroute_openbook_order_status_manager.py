import asyncio
from collections.abc import AsyncGenerator
from typing import List, Tuple
from unittest.mock import AsyncMock, patch

import aiounittest
import bxsolana.provider.grpc
from aiostream import stream
from bxsolana_trader_proto import GetOrderStatusResponse, GetOrderStatusStreamResponse, OrderbookItem, OrderStatus, Side

from hummingbot.connector.exchange.bloxroute_openbook.bloxroute_openbook_order_status_manager import (
    BloxrouteOpenbookOrderStatusManager,
)


class TestOrderbookManager(aiounittest.AsyncTestCase):
    @patch("bxsolana.provider.GrpcProvider.get_order_status_stream")
    async def test_apply_update(self, orderbook_stream_mock: AsyncMock):
        provider = bxsolana.provider.GrpcProvider()
        orderbook_stream_mock.return_value = async_generator(
            [
                ("SOL/USDC", 123, OrderStatus.OS_FILLED, Side.S_ASK),
                ("BTC-USDC", 456, OrderStatus.OS_PARTIAL_FILL, Side.S_BID),
            ]
        )

        os_manager = BloxrouteOpenbookOrderStatusManager(provider, ["SOLUSDC", "BTCUSDC"], "OWNER_ADDRESS")
        os_manager.start()
        await asyncio.sleep(0.1)

        os = os_manager.get_order_status("SOLUSDC", 123)
        self.assertEqual(os, OrderStatus.OS_FILLED)

        os = os_manager.get_order_status("BTCUSDC", 456)
        self.assertEqual(os, OrderStatus.OS_PARTIAL_FILL)

        await os_manager.stop()


async def async_generator(responses: List[Tuple[str, int, OrderStatus, Side]]):
    results = [
        GetOrderStatusStreamResponse(
            slot=1,
            order_info=GetOrderStatusResponse(
                market=market, client_order_i_d=client_order_id, order_status=order_status, side=side
            ),
        )
        for market, client_order_id, order_status, side in responses
    ]
    return stream.iterate(results)
