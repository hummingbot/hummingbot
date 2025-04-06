import asyncio
import json
import time
import unittest
from unittest.mock import AsyncMock, patch

import websockets

from coinbase.constants import (
    CANDLES,
    FUTURES_BALANCE_SUMMARY,
    HEARTBEATS,
    LEVEL2,
    MARKET_TRADES,
    STATUS,
    TICKER,
    TICKER_BATCH,
    USER,
)
from coinbase.websocket import WSClient

from ..constants import TEST_API_KEY, TEST_API_SECRET

NO_PRODUCT_CHANNELS = {HEARTBEATS, FUTURES_BALANCE_SUMMARY}


class WSBaseTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.on_message_mock = unittest.mock.Mock()

        # set up mock websocket messages
        connection_closed_exception = websockets.ConnectionClosedOK(
            1000, "Normal closure", False
        )
        self.mock_websocket = AsyncMock()
        self.mock_websocket.recv = AsyncMock(
            side_effect=[
                connection_closed_exception,
            ]
        )

        # initialize client
        self.ws = WSClient(
            TEST_API_KEY, TEST_API_SECRET, on_message=self.on_message_mock
        )

    @patch("websockets.connect", new_callable=AsyncMock)
    def generic_channel_test(
        self, channel_func, channel_func_unsub, channel_const, mock_connect
    ):
        # assert you can subscribe and unsubscribe to a channel
        mock_connect.return_value = self.mock_websocket

        # open
        self.ws.open()
        self.assertIsNotNone(self.ws.websocket)

        # subscribe
        product_ids = []
        if channel_const not in NO_PRODUCT_CHANNELS:
            product_ids = ["BTC-USD", "ETH-USD"]
            channel_func(product_ids=product_ids)
        else:
            channel_func()
        self.mock_websocket.send.assert_awaited_once()

        # assert subscribe message
        subscribe = json.loads(self.mock_websocket.send.call_args_list[0][0][0])
        self.assertEqual(subscribe["type"], "subscribe")
        self.assertEqual(subscribe["product_ids"], product_ids)
        self.assertEqual(subscribe["channel"], channel_const)

        # unsubscribe
        if channel_const not in NO_PRODUCT_CHANNELS:
            channel_func_unsub(product_ids=product_ids)
        else:
            channel_func_unsub()
        self.assertEqual(self.mock_websocket.send.await_count, 2)

        # assert unsubscribe message
        unsubscribe = json.loads(self.mock_websocket.send.call_args_list[1][0][0])
        self.assertEqual(unsubscribe["type"], "unsubscribe")
        self.assertEqual(unsubscribe["product_ids"], product_ids)
        self.assertEqual(unsubscribe["channel"], channel_const)

        # close
        self.ws.close()
        self.mock_websocket.close.assert_awaited_once()

    @patch("websockets.connect", new_callable=AsyncMock)
    async def generic_channel_test_async(
        self, channel_func, channel_func_unsub, channel_const, mock_connect
    ):
        # assert you can subscribe and unsubscribe to a channel
        mock_connect.return_value = self.mock_websocket

        # open
        await self.ws.open_async()
        self.assertIsNotNone(self.ws.websocket)

        # subscribe
        product_ids = []
        if channel_const not in NO_PRODUCT_CHANNELS:
            product_ids = ["BTC-USD", "ETH-USD"]
            await channel_func(product_ids=product_ids)
        else:
            await channel_func()
        self.mock_websocket.send.assert_awaited_once()

        # assert subscribe message
        subscribe = json.loads(self.mock_websocket.send.call_args_list[0][0][0])
        self.assertEqual(subscribe["type"], "subscribe")
        self.assertEqual(subscribe["product_ids"], product_ids)
        self.assertEqual(subscribe["channel"], channel_const)

        # unsubscribe
        if channel_const not in NO_PRODUCT_CHANNELS:
            await channel_func_unsub(product_ids=product_ids)
        else:
            await channel_func_unsub()
        self.assertEqual(self.mock_websocket.send.await_count, 2)

        # assert unsubscribe message
        unsubscribe = json.loads(self.mock_websocket.send.call_args_list[1][0][0])
        self.assertEqual(unsubscribe["type"], "unsubscribe")
        self.assertEqual(unsubscribe["product_ids"], product_ids)
        self.assertEqual(unsubscribe["channel"], channel_const)

        # close
        await self.ws.close_async()
        self.mock_websocket.close.assert_awaited_once()

    def test_heartbeats(self):
        self.generic_channel_test(
            self.ws.heartbeats, self.ws.heartbeats_unsubscribe, HEARTBEATS
        )

    def test_heartbeats_async(self):
        asyncio.run(
            self.generic_channel_test_async(
                self.ws.heartbeats_async,
                self.ws.heartbeats_unsubscribe_async,
                HEARTBEATS,
            )
        )

    def test_candles(self):
        self.generic_channel_test(self.ws.candles, self.ws.candles_unsubscribe, CANDLES)

    def test_candles_async(self):
        asyncio.run(
            self.generic_channel_test_async(
                self.ws.candles_async, self.ws.candles_unsubscribe_async, CANDLES
            )
        )

    def test_level2(self):
        self.generic_channel_test(self.ws.level2, self.ws.level2_unsubscribe, LEVEL2)

    def test_level2_async(self):
        asyncio.run(
            self.generic_channel_test_async(
                self.ws.level2_async, self.ws.level2_unsubscribe_async, LEVEL2
            )
        )

    def test_market_trades(self):
        self.generic_channel_test(
            self.ws.market_trades, self.ws.market_trades_unsubscribe, MARKET_TRADES
        )

    def test_market_trades_async(self):
        asyncio.run(
            self.generic_channel_test_async(
                self.ws.market_trades_async,
                self.ws.market_trades_unsubscribe_async,
                MARKET_TRADES,
            )
        )

    def test_status(self):
        self.generic_channel_test(self.ws.status, self.ws.status_unsubscribe, STATUS)

    def test_status_async(self):
        asyncio.run(
            self.generic_channel_test_async(
                self.ws.status_async, self.ws.status_unsubscribe_async, STATUS
            )
        )

    def test_ticker(self):
        self.generic_channel_test(self.ws.ticker, self.ws.ticker_unsubscribe, TICKER)

    def test_ticker_async(self):
        asyncio.run(
            self.generic_channel_test_async(
                self.ws.ticker_async, self.ws.ticker_unsubscribe_async, TICKER
            )
        )

    def test_ticker_batch(self):
        self.generic_channel_test(
            self.ws.ticker_batch, self.ws.ticker_batch_unsubscribe, TICKER_BATCH
        )

    def test_ticker_batch_async(self):
        asyncio.run(
            self.generic_channel_test_async(
                self.ws.ticker_batch_async,
                self.ws.ticker_batch_unsubscribe_async,
                TICKER_BATCH,
            )
        )

    def test_user(self):
        self.generic_channel_test(self.ws.user, self.ws.user_unsubscribe, USER)

    def test_user_async(self):
        asyncio.run(
            self.generic_channel_test_async(
                self.ws.user_async, self.ws.user_unsubscribe_async, USER
            )
        )

    def test_futures_balance_summary(self):
        self.generic_channel_test(
            self.ws.futures_balance_summary,
            self.ws.futures_balance_summary_unsubscribe,
            FUTURES_BALANCE_SUMMARY,
        )

    def test_futures_balance_summary_async(self):
        asyncio.run(
            self.generic_channel_test_async(
                self.ws.futures_balance_summary_async,
                self.ws.futures_balance_summary_unsubscribe_async,
                FUTURES_BALANCE_SUMMARY,
            )
        )
