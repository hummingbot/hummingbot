import asyncio
from collections.abc import AsyncGenerator
from typing import List, Tuple
from unittest.mock import AsyncMock, patch

import aiounittest
import bxsolana_trader_proto as proto
from bxsolana import Provider

from hummingbot.connector.exchange.bloxroute_openbook.bloxroute_openbook_constants import MAINNET_PROVIDER_ENDPOINT, \
    SPOT_ORDERBOOK_PROJECT, TESTNET_PROVIDER_ENDPOINT
from hummingbot.connector.exchange.bloxroute_openbook.bloxroute_openbook_order_book import OrderStatusInfo
from hummingbot.connector.exchange.bloxroute_openbook.bloxroute_openbook_order_data_manager import (
    BloxrouteOpenbookOrderDataManager,
)
from hummingbot.connector.exchange.bloxroute_openbook.bloxroute_openbook_provider import BloxrouteOpenbookProvider

TEST_PRIVATE_KEY = "3771ddf5dd1d38ff72334b9763dc3cbc6fc3196f23e651f391fe65e31e466e3d"  # randomly generated
TEST_OWNER_ADDRESS = "OWNER_ADDRESS"
MANAGER_START_WAIT = 0.01


class TestOrderDataManager(aiounittest.AsyncTestCase):
    @patch("bxsolana.provider.WsProvider.connect")
    @patch("bxsolana.provider.WsProvider.get_orderbook")
    async def test_initalize_orderbook(self, get_orderbook_mock: AsyncMock, connect_mock: AsyncMock):
        bids = orders([(5, 2), (6, 7)])
        asks = orders([(7, 4), (8, 4)])
        get_orderbook_mock.return_value = proto.GetOrderbookResponse(
            market="SOLUSDC",
            market_address="SOL_USDC_Market",
            bids=bids,
            asks=asks,
        )

        provider = BloxrouteOpenbookProvider(endpoint="", auth_header="", private_key=TEST_PRIVATE_KEY)
        await provider.connect()

        ob_manager = BloxrouteOpenbookOrderDataManager(provider, ["SOLUSDC"], TEST_OWNER_ADDRESS)
        await ob_manager.start()

        ob, timestamp = ob_manager.get_order_book("SOLUSDC")
        self.assertListEqual(bids, ob.bids)
        self.assertListEqual(asks, ob.asks)

        self.assertEqual((6, 7), ob_manager.get_price_with_opportunity_size("SOLUSDC", True))
        self.assertEqual((7, 4), ob_manager.get_price_with_opportunity_size("SOLUSDC", False))

        await ob_manager.stop()

    @patch("bxsolana.provider.WsProvider.connect")
    @patch("bxsolana.provider.WsProvider.get_orderbooks_stream")
    @patch("bxsolana.provider.WsProvider.get_orderbook")
    async def test_apply_orderbook_update_with_empty_side(
        self, orderbook_mock: AsyncMock, orderbook_stream_mock: AsyncMock, connect_mock: AsyncMock
    ):
        bids = orders([])
        asks = orders([])
        orderbook_mock.return_value = proto.GetOrderbookResponse(
            market="SOLUSDC",
            market_address="SOL_USDC_Market",
            bids=bids,
            asks=asks,
        )

        provider = BloxrouteOpenbookProvider(endpoint="", auth_header="", private_key=TEST_PRIVATE_KEY)
        await provider.connect()

        ob_manager = BloxrouteOpenbookOrderDataManager(provider, ["SOLUSDC"], TEST_OWNER_ADDRESS)
        await ob_manager.start()

        ob, timestamp = ob_manager.get_order_book("SOLUSDC")
        self.assertListEqual(bids, ob.bids)
        self.assertListEqual(asks, ob.asks)

        self.assertEqual((0, 0), ob_manager.get_price_with_opportunity_size("SOLUSDC", True))
        self.assertEqual((0, 0), ob_manager.get_price_with_opportunity_size("SOLUSDC", False))

        await ob_manager.stop()

    @patch("bxsolana.provider.WsProvider.connect")
    @patch("bxsolana.provider.WsProvider.get_orderbooks_stream")
    @patch("bxsolana.provider.WsProvider.get_orderbook")
    async def test_apply_orderbook_update(
        self, orderbook_mock: AsyncMock, orderbook_stream_mock: AsyncMock, connect_mock: AsyncMock
    ):
        # same as first test
        bids = orders([(5, 2), (6, 7)])
        asks = orders([(7, 4), (8, 4)])
        orderbook_mock.return_value = proto.GetOrderbookResponse(
            market="SOLUSDC",
            market_address="SOL_USDC_Market",
            bids=bids,
            asks=asks,
        )

        # new values
        new_bids = orders([(10, 2), (12, 7)])
        new_asks = orders([(14, 3), (16, 4)])
        orderbook_stream_mock.return_value = async_generator_orderbook_stream("SOLUSDC", new_bids, new_asks)

        provider = BloxrouteOpenbookProvider(endpoint="", auth_header="", private_key=TEST_PRIVATE_KEY)
        await provider.connect()

        ob_manager = BloxrouteOpenbookOrderDataManager(provider, ["SOLUSDC"], TEST_OWNER_ADDRESS)
        await ob_manager.start()

        await asyncio.sleep(MANAGER_START_WAIT)

        ob, timestamp = ob_manager.get_order_book("SOLUSDC")
        self.assertListEqual(new_bids, ob.bids)
        self.assertListEqual(new_asks, ob.asks)

        self.assertEqual((12, 7), ob_manager.get_price_with_opportunity_size("SOLUSDC", True))
        self.assertEqual((14, 3), ob_manager.get_price_with_opportunity_size("SOLUSDC", False))

        await ob_manager.stop()

    @patch("time.time")
    @patch("bxsolana.provider.WsProvider.connect")
    @patch("bxsolana.provider.WsProvider.get_order_status_stream")
    @patch("bxsolana.provider.WsProvider.get_orderbooks_stream")
    @patch(
        "hummingbot.connector.exchange.bloxroute_openbook.bloxroute_openbook_order_data_manager"
        ".BloxrouteOpenbookOrderDataManager._initialize_order_books"
    )
    async def test_apply_order_status_update(
        self,
        initialize_order_book_mock: AsyncMock,
        orderbook_stream_mock: AsyncMock,
        order_status_stream_mock: AsyncMock,
        connect_mock: AsyncMock,
        time_mock: AsyncMock
    ):
        def side_effect_function(**kwargs):
            self.assertIn("market", kwargs)
            market = kwargs["market"]

            if market == "SOLUSDC":
                return async_generator_order_status_stream(
                    [("SOL/USDC", 123, 10, proto.OrderStatus.OS_FILLED, proto.Side.S_ASK, 0.3, 0.2)]
                )
            elif market == "BTCUSDC":
                return async_generator_order_status_stream(
                    [
                        ("BTC-USDC", 456, 50, proto.OrderStatus.OS_PARTIAL_FILL, proto.Side.S_BID, 0.4, 0.2),
                    ]
                )

        order_status_stream_mock.side_effect = side_effect_function
        time_mock.return_value = 1

        provider = BloxrouteOpenbookProvider(endpoint="", auth_header="", private_key=TEST_PRIVATE_KEY)
        await provider.connect()

        os_manager = BloxrouteOpenbookOrderDataManager(provider, ["SOLUSDC", "BTCUSDC"], "OWNER_ADDRESS")
        await os_manager.start()

        await asyncio.sleep(MANAGER_START_WAIT)

        os1 = os_manager.get_order_statuses("SOLUSDC", 123)
        self.assertEqual([OrderStatusInfo(
            client_order_i_d=123,
            fill_price=0.0,
            order_price=10,
            order_status=proto.OrderStatus.OS_FILLED,
            quantity_released=0.3,
            quantity_remaining=0.2,
            side=proto.Side.S_ASK,
            timestamp=1
        )], os1)

        os2 = os_manager.get_order_statuses("BTCUSDC", 456)
        self.assertEqual(os2, [OrderStatusInfo(
            client_order_i_d=456,
            fill_price=0.0,
            order_price=50,
            order_status=proto.OrderStatus.OS_PARTIAL_FILL,
            quantity_released=0.4,
            quantity_remaining=0.2,
            side=proto.Side.S_BID,
            timestamp=1
        )])

        await os_manager.stop()

    @patch("time.time")
    @patch("bxsolana.provider.WsProvider.connect")
    @patch("bxsolana.provider.WsProvider.get_order_status_stream")
    @patch("bxsolana.provider.WsProvider.get_orderbooks_stream")
    @patch(
        "hummingbot.connector.exchange.bloxroute_openbook.bloxroute_openbook_order_data_manager"
        ".BloxrouteOpenbookOrderDataManager._initialize_order_books"
    )
    async def test_apply_order_status_update_edge_cases(
        self,
        initialize_order_book_mock: AsyncMock,
        orderbook_stream_mock: AsyncMock,
        order_status_stream_mock: AsyncMock,
        connect_mock: AsyncMock,
        time_mock: AsyncMock
    ):
        def side_effect_function(**kwargs):
            self.assertIn("market", kwargs)
            market = kwargs["market"]

            if market == "SOLUSDC":
                return async_generator_order_status_stream([
                    ("SOL/USDC", 123, 10, proto.OrderStatus.OS_OPEN, proto.Side.S_ASK, 0, 0.3),
                    ("SOL/USDC", 123, 10, proto.OrderStatus.OS_OPEN, proto.Side.S_ASK, 0, 0.3),
                    ("SOL/USDC", 123, 10, proto.OrderStatus.OS_FILLED, proto.Side.S_ASK, 0.3, 0),
                ])

        order_status_stream_mock.side_effect = side_effect_function
        time_mock.return_value = 1

        provider = BloxrouteOpenbookProvider(endpoint="", auth_header="", private_key=TEST_PRIVATE_KEY)
        os_manager = BloxrouteOpenbookOrderDataManager(provider, ["SOLUSDC", "BTCUSDC"], "OWNER_ADDRESS")
        await os_manager.start()

        await asyncio.sleep(MANAGER_START_WAIT)

        os = os_manager.get_order_statuses("SOLUSDC", 123)
        self.assertListEqual(os, [
            OrderStatusInfo(
                client_order_i_d=123,
                fill_price=0.0,
                order_price=10,
                order_status=proto.OrderStatus.OS_OPEN,
                quantity_released=0,
                quantity_remaining=0.3,
                side=proto.Side.S_ASK,
                timestamp=1
            ), OrderStatusInfo(
                client_order_i_d=123,
                fill_price=0.0,
                order_price=10,
                order_status=proto.OrderStatus.OS_FILLED,
                quantity_released=0.3,
                quantity_remaining=0.0,
                side=proto.Side.S_ASK,
                timestamp=1
            )])

        await os_manager.stop()

    @patch("time.time")
    @patch("bxsolana.provider.WsProvider.connect")
    @patch("bxsolana.provider.WsProvider.get_order_status_stream")
    @patch("bxsolana.provider.WsProvider.get_orderbooks_stream")
    @patch(
        "hummingbot.connector.exchange.bloxroute_openbook.bloxroute_openbook_order_data_manager"
        ".BloxrouteOpenbookOrderDataManager._initialize_order_books"
    )
    async def test_apply_order_status_update_on_existing_order(
        self,
        initialize_order_book_mock: AsyncMock,
        orderbook_stream_mock: AsyncMock,
        order_status_stream_mock: AsyncMock,
        connect_mock: AsyncMock,
        time_mock: AsyncMock
    ):
        order_status_stream_mock.return_value = async_generator_order_status_stream(
            [
                ("SOL/USDC", 123, 11, proto.OrderStatus.OS_PARTIAL_FILL, proto.Side.S_ASK, 0.1, 0.1),
                ("SOL/USDC", 123, 10, proto.OrderStatus.OS_FILLED, proto.Side.S_ASK, 0.1, 0),
            ]
        )
        time_mock.return_value = 1

        provider = BloxrouteOpenbookProvider(endpoint="", auth_header="", private_key=TEST_PRIVATE_KEY)
        await provider.connect()

        os_manager = BloxrouteOpenbookOrderDataManager(provider, ["SOLUSDC", "BTCUSDC"], "OWNER_ADDRESS")
        await os_manager.start()

        await asyncio.sleep(MANAGER_START_WAIT)

        os_updates: List[OrderStatusInfo] = os_manager.get_order_statuses("SOLUSDC", 123)
        expected_os_updates = [
            OrderStatusInfo(
                client_order_i_d=123,
                fill_price=0.0,
                order_price=11,
                order_status=proto.OrderStatus.OS_PARTIAL_FILL,
                quantity_released=0.1,
                quantity_remaining=0.1,
                side=proto.Side.S_ASK,
                timestamp=1
            ),
            OrderStatusInfo(
                client_order_i_d=123,
                fill_price=0.0,
                order_price=10,
                order_status=proto.OrderStatus.OS_FILLED,
                quantity_released=0.1,
                quantity_remaining=0,
                side=proto.Side.S_ASK,
                timestamp=1
            )
        ]

        self.assertListEqual(os_updates, expected_os_updates)

        await os_manager.stop()

    @patch("time.time")
    @patch("bxsolana.provider.WsProvider.connect")
    @patch("bxsolana.provider.WsProvider.get_order_status_stream")
    @patch("bxsolana.provider.WsProvider.get_orderbooks_stream")
    @patch(
        "hummingbot.connector.exchange.bloxroute_openbook.bloxroute_openbook_order_data_manager"
        ".BloxrouteOpenbookOrderDataManager._initialize_order_books"
    )
    async def test_apply_order_status_update_on_order_in_existing_market(
        self,
        initialize_order_book_mock: AsyncMock,
        orderbook_stream_mock: AsyncMock,
        order_status_stream_mock: AsyncMock,
        connect_mock: AsyncMock,
        time_mock: AsyncMock
    ):
        order_status_stream_mock.return_value = async_generator_order_status_stream(
            [
                ("SOL/USDC", 123, 11, proto.OrderStatus.OS_PARTIAL_FILL, proto.Side.S_ASK, 0.3, 0.2),
                ("SOL/USDC", 456, 10, proto.OrderStatus.OS_FILLED, proto.Side.S_ASK, 0.4, 0.2),
            ]
        )
        time_mock.return_value = 1

        provider = BloxrouteOpenbookProvider(endpoint="", auth_header="", private_key=TEST_PRIVATE_KEY)
        os_manager = BloxrouteOpenbookOrderDataManager(provider, ["SOLUSDC", "BTCUSDC"], "OWNER_ADDRESS")
        await os_manager.start()
        await asyncio.sleep(0.5)

        os = os_manager.get_order_statuses("SOLUSDC", 123)
        self.assertEqual(os, [OrderStatusInfo(
            client_order_i_d=123,
            fill_price=0.0,
            order_price=11,
            order_status=proto.OrderStatus.OS_PARTIAL_FILL,
            quantity_released=0.3,
            quantity_remaining=0.2,
            side=proto.Side.S_ASK,
            timestamp=1
        )])

        os2 = os_manager.get_order_statuses("SOLUSDC", 456)
        self.assertEqual(os2, [OrderStatusInfo(
            client_order_i_d=456,
            fill_price=0.0,
            order_price=10,
            order_status=proto.OrderStatus.OS_FILLED,
            quantity_released=0.4,
            quantity_remaining=0.2,
            side=proto.Side.S_ASK,
            timestamp=1
        )])

        await os_manager.stop()

def orders(price_and_sizes: List[Tuple[int, int]]) -> List[proto.OrderbookItem]:
    orderbook_items = []
    for price, size in price_and_sizes:
        orderbook_items.append(proto.OrderbookItem(price=price, size=size))

    return orderbook_items


async def async_generator_orderbook_stream(market, bids, asks) -> AsyncGenerator:
    yield proto.GetOrderbooksStreamResponse(slot=1, orderbook=proto.GetOrderbookResponse(market=market, bids=bids, asks=asks))


async def async_generator_order_status_stream(
    order_status_updates: List[Tuple[str, int, int, proto.OrderStatus, proto.Side, float, float]]
) -> AsyncGenerator:
    for market, client_order_id, order_price, order_status, side, q_rel, q_rem in order_status_updates:
        yield proto.GetOrderStatusStreamResponse(
            slot=1,
            order_info=proto.GetOrderStatusResponse(
                market=market, client_order_i_d=client_order_id, order_price=order_price, order_status=order_status,
                side=side,
                quantity_released=q_rel, quantity_remaining=q_rem
            ),
        )


async def start_os_stream(provider: Provider, market: str, owner_address: str, queue: asyncio.Queue):
    await provider.connect()
    os_stream = provider.get_order_status_stream(market=market, owner_address=owner_address,
                                                 project=SPOT_ORDERBOOK_PROJECT)
    while True:
        up = await os_stream.__anext__()
        queue.put_nowait(up)
