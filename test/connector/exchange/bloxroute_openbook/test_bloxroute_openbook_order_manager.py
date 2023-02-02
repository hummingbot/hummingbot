import asyncio
import time
from collections.abc import AsyncGenerator
from typing import List, Tuple
from unittest.mock import AsyncMock, patch

import aiounittest
import bxsolana.provider.grpc
from bxsolana import Provider
from bxsolana_trader_proto import (
    GetOrderbookResponse,
    GetOrderbooksStreamResponse,
    GetOrderStatusResponse,
    GetOrderStatusStreamResponse,
    OrderType, OrderbookItem,
    OrderStatus,
    Side,
)

from bxsolana.provider.constants import LOCAL_API_WS

from hummingbot.connector.exchange.bloxroute_openbook.bloxroute_openbook_constants import OPENBOOK_PROJECT
from hummingbot.connector.exchange.bloxroute_openbook.bloxroute_openbook_order_manager import (
    BloxrouteOpenbookOrderManager,
    OrderStatusInfo,
)

test_private_key = "3771ddf5dd1d38ff72334b9763dc3cbc6fc3196f23e651f391fe65e31e466e3d"
test_owner_address = "OWNER_ADDRESS"


class TestOrderManager(aiounittest.AsyncTestCase):
    @patch("bxsolana.provider.GrpcProvider.get_orderbook")
    async def test_initalize_orderbook(self, mock: AsyncMock):
        provider = bxsolana.provider.GrpcProvider(auth_header="", private_key=test_private_key)

        bids = orders([(5, 2), (6, 7)])
        asks = orders([(7, 4), (8, 4)])
        mock.return_value = GetOrderbookResponse(
            market="SOLUSDC",
            market_address="SOL_USDC_Market",
            bids=bids,
            asks=asks,
        )

        ob_manager = BloxrouteOpenbookOrderManager(provider, ["SOLUSDC"], test_owner_address)
        await ob_manager.start()

        ob = ob_manager.get_order_book("SOLUSDC")
        self.assertListEqual(bids, ob.bids)
        self.assertListEqual(asks, ob.asks)

        self.assertEqual((6, 7), ob_manager.get_price_with_opportunity_size("SOLUSDC", True))
        self.assertEqual((7, 4), ob_manager.get_price_with_opportunity_size("SOLUSDC", False))

        await ob_manager.stop()

    @patch("bxsolana.provider.GrpcProvider.get_orderbooks_stream")
    @patch("bxsolana.provider.GrpcProvider.get_orderbook")
    async def test_apply_orderbook_update_with_empty_side(
        self, orderbook_mock: AsyncMock, orderbook_stream_mock: AsyncMock
    ):
        provider = bxsolana.provider.GrpcProvider(auth_header="", private_key=test_private_key)

        bids = orders([])
        asks = orders([])
        orderbook_mock.return_value = GetOrderbookResponse(
            market="SOLUSDC",
            market_address="SOL_USDC_Market",
            bids=bids,
            asks=asks,
        )

        ob_manager = BloxrouteOpenbookOrderManager(provider, ["SOLUSDC"], test_owner_address)
        await ob_manager.start()
        await asyncio.sleep(0.1)

        ob = ob_manager.get_order_book("SOLUSDC")
        self.assertListEqual(bids, ob.bids)
        self.assertListEqual(asks, ob.asks)

        self.assertEqual((0, 0), ob_manager.get_price_with_opportunity_size("SOLUSDC", True))
        self.assertEqual((0, 0), ob_manager.get_price_with_opportunity_size("SOLUSDC", False))

        await ob_manager.stop()

    @patch("bxsolana.provider.GrpcProvider.get_orderbooks_stream")
    @patch("bxsolana.provider.GrpcProvider.get_orderbook")
    async def test_apply_orderbook_update(self, orderbook_mock: AsyncMock, orderbook_stream_mock: AsyncMock):
        provider = bxsolana.provider.GrpcProvider(auth_header="", private_key=test_private_key)

        # same as first test
        bids = orders([(5, 2), (6, 7)])
        asks = orders([(7, 4), (8, 4)])
        orderbook_mock.return_value = GetOrderbookResponse(
            market="SOLUSDC",
            market_address="SOL_USDC_Market",
            bids=bids,
            asks=asks,
        )

        # new values
        new_bids = orders([(10, 2), (12, 7)])
        new_asks = orders([(14, 3), (16, 4)])
        orderbook_stream_mock.return_value = async_generator_orderbook_stream("SOLUSDC", new_bids, new_asks)

        ob_manager = BloxrouteOpenbookOrderManager(provider, ["SOLUSDC"], test_owner_address)
        await ob_manager.start()
        await asyncio.sleep(0.1)

        ob = ob_manager.get_order_book("SOLUSDC")
        self.assertListEqual(new_bids, ob.bids)
        self.assertListEqual(new_asks, ob.asks)

        self.assertEqual((12, 7), ob_manager.get_price_with_opportunity_size("SOLUSDC", True))
        self.assertEqual((14, 3), ob_manager.get_price_with_opportunity_size("SOLUSDC", False))

        await ob_manager.stop()

    @patch("time.time")
    @patch("bxsolana.provider.GrpcProvider.get_order_status_stream")
    @patch("bxsolana.provider.GrpcProvider.get_orderbooks_stream")
    @patch(
        "hummingbot.connector.exchange.bloxroute_openbook.bloxroute_openbook_order_manager"
        ".BloxrouteOpenbookOrderManager._initialize_order_books"
    )
    @patch("bxsolana.provider.GrpcProvider.get_orderbook")
    async def test_apply_order_status_update(
        self,
        orderbook_mock: AsyncMock,
        initialize_order_book_mock: AsyncMock,
        orderbook_stream_mock: AsyncMock,
        order_status_stream_mock: AsyncMock,
        time_mock: AsyncMock
    ):
        def side_effect_function(**kwargs):
            self.assertIn("market", kwargs)
            market = kwargs["market"]

            if market == "SOLUSDC":
                return async_generator_order_status_stream([("SOL/USDC", 123, OrderStatus.OS_FILLED, Side.S_ASK, 0.3, 0.2)])
            elif market == "BTCUSDC":
                return async_generator_order_status_stream(
                    [
                        ("BTC-USDC", 456, OrderStatus.OS_PARTIAL_FILL, Side.S_BID, 0.4, 0.2),
                    ]
                )

        order_status_stream_mock.side_effect = side_effect_function
        time_mock.return_value = 1

        provider = bxsolana.provider.GrpcProvider(auth_header="", private_key=test_private_key)
        os_manager = BloxrouteOpenbookOrderManager(provider, ["SOLUSDC", "BTCUSDC"], "OWNER_ADDRESS")
        await os_manager.start()
        await asyncio.sleep(0.1)

        os1 = os_manager.get_order_status("SOLUSDC", 123)
        self.assertEqual(os1, [OrderStatusInfo(
            client_order_i_d=123,
            fill_price=0.0,
            order_status=OrderStatus.OS_FILLED,
            quantity_released=0.3,
            quantity_remaining=0.2,
            side=Side.S_ASK,
            timestamp=1
        )])

        os2 = os_manager.get_order_status("BTCUSDC", 456)
        self.assertEqual(os2, [OrderStatusInfo(
            client_order_i_d=456,
            fill_price=0.0,
            order_status=OrderStatus.OS_PARTIAL_FILL,
            quantity_released=0.4,
            quantity_remaining=0.2,
            side=Side.S_BID,
            timestamp=1
        )])

        await os_manager.stop()

    @patch("time.time")
    @patch("bxsolana.provider.GrpcProvider.get_order_status_stream")
    @patch("bxsolana.provider.GrpcProvider.get_orderbooks_stream")
    @patch(
        "hummingbot.connector.exchange.bloxroute_openbook.bloxroute_openbook_order_manager"
        ".BloxrouteOpenbookOrderManager._initialize_order_books"
    )
    @patch("bxsolana.provider.GrpcProvider.get_orderbook")
    async def test_apply_order_status_update_on_existing_order(
        self,
        orderbook_mock: AsyncMock,
        initialize_order_book_mock: AsyncMock,
        orderbook_stream_mock: AsyncMock,
        order_status_stream_mock: AsyncMock,
        time_mock: AsyncMock
    ):
        provider = bxsolana.provider.GrpcProvider(auth_header="", private_key=test_private_key)
        order_status_stream_mock.return_value = async_generator_order_status_stream(
            [
                ("SOL/USDC", 123, OrderStatus.OS_PARTIAL_FILL, Side.S_ASK, 0.1, 0.1),
                ("SOL/USDC", 123, OrderStatus.OS_FILLED, Side.S_ASK, 0.1, 0),
            ]
        )
        time_mock.return_value = 1

        os_manager = BloxrouteOpenbookOrderManager(provider, ["SOLUSDC", "BTCUSDC"], "OWNER_ADDRESS")
        await os_manager.start()
        await asyncio.sleep(0.1)

        os_updates: List[OrderStatusInfo] = os_manager.get_order_status("SOLUSDC", 123)
        expected_os_updates = [
            OrderStatusInfo(
                client_order_i_d=123,
                fill_price=0.0,
                order_status=OrderStatus.OS_PARTIAL_FILL,
                quantity_released=0.1,
                quantity_remaining=0.1,
                side=Side.S_ASK,
                timestamp=1
            ),
            OrderStatusInfo(
                client_order_i_d=123,
                fill_price=0.0,
                order_status=OrderStatus.OS_FILLED,
                quantity_released=0.1,
                quantity_remaining=0,
                side=Side.S_ASK,
                timestamp=1
            )
        ]

        self.assertListEqual(os_updates, expected_os_updates)

        await os_manager.stop()

    @patch("time.time")
    @patch("bxsolana.provider.GrpcProvider.get_order_status_stream")
    @patch("bxsolana.provider.GrpcProvider.get_orderbooks_stream")
    @patch(
        "hummingbot.connector.exchange.bloxroute_openbook.bloxroute_openbook_order_manager"
        ".BloxrouteOpenbookOrderManager._initialize_order_books"
    )
    @patch("bxsolana.provider.GrpcProvider.get_orderbook")
    async def test_apply_order_status_update_on_order_in_existing_market(
        self,
        orderbook_mock: AsyncMock,
        initialize_order_book_mock: AsyncMock,
        orderbook_stream_mock: AsyncMock,
        order_status_stream_mock: AsyncMock,
        time_mock: AsyncMock
    ):
        provider = bxsolana.provider.GrpcProvider(auth_header="", private_key=test_private_key)
        order_status_stream_mock.return_value = async_generator_order_status_stream(
            [
                ("SOL/USDC", 123, OrderStatus.OS_PARTIAL_FILL, Side.S_ASK, 0.3, 0.2),
                ("SOL/USDC", 456, OrderStatus.OS_FILLED, Side.S_ASK, 0.4, 0.2),
            ]
        )
        time_mock.return_value = 1

        os_manager = BloxrouteOpenbookOrderManager(provider, ["SOLUSDC", "BTCUSDC"], "OWNER_ADDRESS")
        await os_manager.start()
        await asyncio.sleep(0.1)

        os = os_manager.get_order_status("SOLUSDC", 123)
        self.assertEqual(os, [OrderStatusInfo(
            client_order_i_d=123,
            fill_price=0.0,
            order_status=OrderStatus.OS_PARTIAL_FILL,
            quantity_released=0.3,
            quantity_remaining=0.2,
            side=Side.S_ASK,
            timestamp=1
        )])

        os2 = os_manager.get_order_status("SOLUSDC", 456)
        self.assertEqual(os2, [OrderStatusInfo(
            client_order_i_d=456,
            fill_price=0.0,
            order_status=OrderStatus.OS_FILLED,
            quantity_released=0.4,
            quantity_remaining=0.2,
            side=Side.S_ASK,
            timestamp=1
        )])

        await os_manager.stop()

def orders(price_and_sizes: List[Tuple[int, int]]) -> List[OrderbookItem]:
    orderbook_items = []
    for price, size in price_and_sizes:
        orderbook_items.append(OrderbookItem(price=price, size=size))

    return orderbook_items


async def async_generator_orderbook_stream(market, bids, asks) -> AsyncGenerator:
    yield GetOrderbooksStreamResponse(slot=1, orderbook=GetOrderbookResponse(market=market, bids=bids, asks=asks))


async def async_generator_order_status_stream(
    order_status_updates: List[Tuple[str, int, OrderStatus, Side, float, float]]
) -> AsyncGenerator:
    for market, client_order_id, order_status, side, q_rel, q_rem in order_status_updates:
        yield GetOrderStatusStreamResponse(
            slot=1,
            order_info=GetOrderStatusResponse(
                market=market, client_order_i_d=client_order_id, order_status=order_status, side=side,
                quantity_released=q_rel, quantity_remaining=q_rem
            ),
        )


async def start_os_stream(provider: Provider, market: str, owner_address: str, queue: asyncio.Queue):
    await provider.connect()
    os_stream = provider.get_order_status_stream(market=market, owner_address=owner_address,
                                                 project=OPENBOOK_PROJECT)
    while True:
        up = await os_stream.__anext__()
        queue.put_nowait(up)
