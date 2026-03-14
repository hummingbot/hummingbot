import asyncio
import time
import unittest
from decimal import Decimal
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_api_order_book_data_source import (
    DecibelPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.decibel_perpetual import decibel_perpetual_constants as CONSTANTS
from hummingbot.core.data_type.order_book_message import OrderBookMessageType


def _make_connector(exchange_symbol="BTC/USD", api_key="test_api_key"):
    """Build a minimal mock connector suitable for the data source."""
    connector = MagicMock()
    connector._api_key = api_key
    connector.exchange_symbol_associated_to_pair = AsyncMock(return_value=exchange_symbol)
    connector.trading_pair_associated_to_exchange_symbol = AsyncMock(return_value="BTC-USD")
    return connector


def _make_aiohttp_response(json_data: Any, status: int = 200):
    """Build a context-manager mock that returns the given JSON."""
    resp = AsyncMock()
    resp.status = status
    resp.json = AsyncMock(return_value=json_data)
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=resp)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


class TestDecibelPerpetualAPIOrderBookDataSource(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.connector = _make_connector()
        self.api_factory = MagicMock()
        self.data_source = DecibelPerpetualAPIOrderBookDataSource(
            trading_pairs=["BTC-USD"],
            connector=self.connector,
            api_factory=self.api_factory,
            domain=CONSTANTS.DEFAULT_DOMAIN,
        )

    # ------------------------------------------------------------------
    # Test 1: get_last_traded_prices returns float for valid response
    # ------------------------------------------------------------------
    @patch("aiohttp.ClientSession")
    async def test_get_last_traded_prices_success(self, mock_session_cls):
        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        price_response = {"mark_px": "50000.5"}
        mock_session.get = MagicMock(return_value=_make_aiohttp_response(price_response))

        result = await self.data_source.get_last_traded_prices(["BTC-USD"])
        self.assertIn("BTC-USD", result)
        self.assertAlmostEqual(result["BTC-USD"], 50000.5)

    # ------------------------------------------------------------------
    # Test 2: get_last_traded_prices handles missing price gracefully
    # ------------------------------------------------------------------
    @patch("aiohttp.ClientSession")
    async def test_get_last_traded_prices_missing_price(self, mock_session_cls):
        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_session.get = MagicMock(return_value=_make_aiohttp_response({}))
        result = await self.data_source.get_last_traded_prices(["BTC-USD"])
        # Should not raise; BTC-USD entry may be missing
        self.assertIsInstance(result, dict)

    # ------------------------------------------------------------------
    # Test 3: _order_book_snapshot returns SNAPSHOT message
    # ------------------------------------------------------------------
    @patch("aiohttp.ClientSession")
    async def test_order_book_snapshot_message_type(self, mock_session_cls):
        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        ob_response = {
            "bids": [["50000", "1.0"], ["49999", "2.0"]],
            "asks": [["50001", "1.5"], ["50002", "0.5"]],
        }
        mock_session.get = MagicMock(return_value=_make_aiohttp_response(ob_response))

        msg = await self.data_source._order_book_snapshot("BTC-USD")
        self.assertEqual(msg.type, OrderBookMessageType.SNAPSHOT)

    # ------------------------------------------------------------------
    # Test 4: _order_book_snapshot parses bids and asks
    # ------------------------------------------------------------------
    @patch("aiohttp.ClientSession")
    async def test_order_book_snapshot_parses_bids_asks(self, mock_session_cls):
        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        ob_response = {
            "bids": [{"price": "50000", "size": "1.0"}],
            "asks": [{"price": "50001", "size": "1.5"}],
        }
        mock_session.get = MagicMock(return_value=_make_aiohttp_response(ob_response))

        msg = await self.data_source._order_book_snapshot("BTC-USD")
        self.assertEqual(msg.content["trading_pair"], "BTC-USD")
        self.assertIsInstance(msg.content["bids"], list)
        self.assertIsInstance(msg.content["asks"], list)

    # ------------------------------------------------------------------
    # Test 5: _order_book_snapshot handles empty book gracefully
    # ------------------------------------------------------------------
    @patch("aiohttp.ClientSession")
    async def test_order_book_snapshot_empty(self, mock_session_cls):
        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_session.get = MagicMock(return_value=_make_aiohttp_response({"bids": [], "asks": []}))

        msg = await self.data_source._order_book_snapshot("BTC-USD")
        self.assertEqual(msg.content["bids"], [])
        self.assertEqual(msg.content["asks"], [])

    # ------------------------------------------------------------------
    # Test 6: get_funding_info returns expected keys
    # ------------------------------------------------------------------
    @patch("aiohttp.ClientSession")
    async def test_get_funding_info_keys(self, mock_session_cls):
        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        price_resp = {"mark_px": "50000", "index_px": "49999"}
        funding_resp = {"funding_rates": [{"funding_rate": "0.0001", "next_funding_time": 1700000000}]}

        call_count = [0]
        def side_effect_get(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return _make_aiohttp_response(price_resp)
            return _make_aiohttp_response(funding_resp)

        mock_session.get = MagicMock(side_effect=side_effect_get)

        info = await self.data_source.get_funding_info("BTC-USD")
        self.assertIsNotNone(info)
        self.assertIn("mark_price", info)
        self.assertIn("rate", info)

    # ------------------------------------------------------------------
    # Test 7: get_funding_info returns None on exception
    # ------------------------------------------------------------------
    @patch("aiohttp.ClientSession")
    async def test_get_funding_info_exception(self, mock_session_cls):
        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_session.get = MagicMock(side_effect=Exception("Connection error"))

        result = await self.data_source.get_funding_info("BTC-USD")
        self.assertIsNone(result)

    # ------------------------------------------------------------------
    # Test 8: auth headers include Bearer token
    # ------------------------------------------------------------------
    def test_get_auth_headers_with_api_key(self):
        headers = self.data_source._get_auth_headers()
        self.assertEqual(headers.get("Authorization"), "Bearer test_api_key")

    # ------------------------------------------------------------------
    # Test 9: auth headers empty without api_key
    # ------------------------------------------------------------------
    def test_get_auth_headers_without_api_key(self):
        self.connector._api_key = ""
        headers = self.data_source._get_auth_headers()
        self.assertNotIn("Authorization", headers)

    # ------------------------------------------------------------------
    # Test 10: listen_for_trades emits TRADE messages
    # ------------------------------------------------------------------
    @patch("aiohttp.ClientSession")
    async def test_listen_for_trades_emits_messages(self, mock_session_cls):
        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        trades_response = {
            "trades": [
                {
                    "trade_id": "trade001",
                    "price": "50000",
                    "size": "0.1",
                    "is_buyer_maker": True,
                    "timestamp": time.time() * 1000,
                }
            ]
        }
        mock_session.get = MagicMock(return_value=_make_aiohttp_response(trades_response))

        output_queue: asyncio.Queue = asyncio.Queue()

        async def run_briefly():
            try:
                await asyncio.wait_for(
                    self.data_source.listen_for_trades(asyncio.get_event_loop(), output_queue),
                    timeout=0.5,
                )
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass

        await run_briefly()
        # Should have emitted at least one trade message
        self.assertFalse(output_queue.empty())
        msg = output_queue.get_nowait()
        self.assertEqual(msg.type, OrderBookMessageType.TRADE)


if __name__ == "__main__":
    unittest.main()
