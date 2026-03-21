import asyncio
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from hummingbot.connector.exchange.kuru.kuru_api_order_book_data_source import KuruAPIOrderBookDataSource
from hummingbot.core.data_type.order_book_message import OrderBookMessageType


class TestKuruAPIOrderBookDataSource(IsolatedAsyncioTestCase):

    def setUp(self) -> None:
        super().setUp()
        self.trading_pair = "MON-USDC"
        self.connector = SimpleNamespace(
            sdk_orderbook_queue=asyncio.Queue(),
            last_traded_prices={self.trading_pair: 12.5},
            trading_pairs=[self.trading_pair],
        )
        self.data_source = KuruAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair],
            connector=self.connector,
        )

    async def test_get_last_traded_prices_uses_connector_cache(self):
        prices = await self.data_source.get_last_traded_prices([self.trading_pair, "OTHER-USDC"])

        self.assertEqual(12.5, prices[self.trading_pair])
        self.assertEqual(0.0, prices["OTHER-USDC"])

    async def test_listen_for_order_book_snapshots_emits_filtered_snapshot(self):
        output = asyncio.Queue()
        task = asyncio.create_task(
            self.data_source.listen_for_order_book_snapshots(asyncio.get_running_loop(), output)
        )

        await self.connector.sdk_orderbook_queue.put(
            SimpleNamespace(
                b=[(10.0, 2.0), (9.0, 0.0)],
                a=[(11.0, 3.0), (12.0, 0.0)],
            )
        )

        message = await asyncio.wait_for(output.get(), timeout=1)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task

        self.assertEqual(OrderBookMessageType.SNAPSHOT, message.type)
        self.assertEqual(1, message.update_id)
        self.assertEqual([[10.0, 2.0]], message.content["bids"])
        self.assertEqual([[11.0, 3.0]], message.content["asks"])

    async def test_listen_for_order_book_snapshots_skips_empty_updates(self):
        output = asyncio.Queue()
        task = asyncio.create_task(
            self.data_source.listen_for_order_book_snapshots(asyncio.get_running_loop(), output)
        )

        await self.connector.sdk_orderbook_queue.put(SimpleNamespace(b=None, a=None))
        await self.connector.sdk_orderbook_queue.put(SimpleNamespace(b=[(10.0, 1.0)], a=[(11.0, 1.5)]))

        message = await asyncio.wait_for(output.get(), timeout=1)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task

        self.assertEqual(1, message.update_id)
        self.assertEqual([[10.0, 1.0]], message.content["bids"])
        self.assertEqual([[11.0, 1.5]], message.content["asks"])

    async def test_order_book_snapshot_returns_empty_snapshot_on_timeout(self):
        with patch(
            "hummingbot.connector.exchange.kuru.kuru_api_order_book_data_source.asyncio.wait_for",
            side_effect=asyncio.TimeoutError,
        ):
            message = await self.data_source._order_book_snapshot(self.trading_pair)

        self.assertEqual(0, message.update_id)
        self.assertEqual([], message.content["bids"])
        self.assertEqual([], message.content["asks"])

    async def test_order_book_snapshot_returns_snapshot_from_queue(self):
        await self.connector.sdk_orderbook_queue.put(
            SimpleNamespace(
                b=[(10.0, 2.0)],
                a=[(11.0, 3.0)],
            )
        )

        message = await self.data_source._order_book_snapshot(self.trading_pair)

        self.assertEqual(1, message.update_id)
        self.assertEqual([[10.0, 2.0]], message.content["bids"])
        self.assertEqual([[11.0, 3.0]], message.content["asks"])

    async def test_subscribe_and_unsubscribe_return_true(self):
        self.assertTrue(await self.data_source.subscribe_to_trading_pair(self.trading_pair))
        self.assertTrue(await self.data_source.unsubscribe_from_trading_pair(self.trading_pair))
