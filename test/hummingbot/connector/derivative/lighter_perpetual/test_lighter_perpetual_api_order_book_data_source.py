import asyncio
from decimal import Decimal
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.connector.derivative.lighter_perpetual import lighter_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_api_order_book_data_source import (
    LighterPerpetualAPIOrderBookDataSource,
)
from hummingbot.core.data_type.order_book_message import OrderBookMessageType


class MockWSAssistant:
    def __init__(self):
        self.sent = []
        self.connect_calls = []

    async def connect(self, **kwargs):
        self.connect_calls.append(kwargs)

    async def send(self, request):
        self.sent.append(request)


class LighterPerpetualAPIOrderBookDataSourceTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.data_source = LighterPerpetualAPIOrderBookDataSource.__new__(LighterPerpetualAPIOrderBookDataSource)

    def test_init_sets_dependencies(self):
        connector = SimpleNamespace()
        api_factory = SimpleNamespace()

        data_source = LighterPerpetualAPIOrderBookDataSource(
            trading_pairs=["ETH-USD"],
            connector=connector,
            api_factory=api_factory,
            domain="lighter_perpetual_testnet",
        )

        self.assertEqual(connector, data_source._connector)
        self.assertEqual(api_factory, data_source._api_factory)
        self.assertEqual("lighter_perpetual_testnet", data_source._domain)

    def test_get_last_traded_prices_delegates_to_connector(self):
        connector = SimpleNamespace(get_last_traded_prices=AsyncMock(return_value={"ETH-USD": 2500.0}))
        data_source = LighterPerpetualAPIOrderBookDataSource(["ETH-USD"], connector, SimpleNamespace())

        prices = asyncio.run(data_source.get_last_traded_prices(["ETH-USD"]))

        self.assertEqual({"ETH-USD": 2500.0}, prices)
        connector.get_last_traded_prices.assert_awaited_once_with(trading_pairs=["ETH-USD"])

    def test_get_funding_info_uses_market_and_response(self):
        market = SimpleNamespace(
            market_id=1,
            raw_info={"mark_price": "2501", "index_price": "2500"},
        )
        connector = SimpleNamespace(
            market_info_for_trading_pair=MagicMock(return_value=market),
            _api_get=AsyncMock(return_value={"funding_rates": [{"market_id": 1, "rate": "0.0002"}]}),
        )
        data_source = LighterPerpetualAPIOrderBookDataSource(["ETH-USD"], connector, SimpleNamespace())

        with patch.object(data_source, "_next_funding_utc_timestamp", return_value=123):
            funding_info = asyncio.run(data_source.get_funding_info("ETH-USD"))

        self.assertEqual("ETH-USD", funding_info.trading_pair)
        self.assertEqual(Decimal("2500"), funding_info.index_price)
        self.assertEqual(Decimal("2501"), funding_info.mark_price)
        self.assertEqual(Decimal("0.0002"), funding_info.rate)
        self.assertEqual(123, funding_info.next_funding_utc_timestamp)

    def test_request_order_book_snapshot_uses_market_id(self):
        market = SimpleNamespace(market_id=1)
        connector = SimpleNamespace(
            market_info_for_trading_pair=MagicMock(return_value=market),
            _api_get=AsyncMock(return_value={"bids": [], "asks": []}),
        )
        data_source = LighterPerpetualAPIOrderBookDataSource(["ETH-USD"], connector, SimpleNamespace())

        snapshot = asyncio.run(data_source._request_order_book_snapshot("ETH-USD"))

        self.assertEqual({"bids": [], "asks": []}, snapshot)
        connector._api_get.assert_awaited_once_with(
            path_url=CONSTANTS.SNAPSHOT_PATH_URL,
            params={"market_id": 1, "limit": CONSTANTS.ORDER_BOOK_SNAPSHOT_LIMIT},
        )

    def test_order_book_snapshot_builds_snapshot_message(self):
        market = SimpleNamespace(market_id=1)
        connector = SimpleNamespace(
            market_info_for_trading_pair=MagicMock(return_value=market),
            _api_get=AsyncMock(
                return_value={
                    "bids": [{"price": "2500", "remaining_base_amount": "1"}],
                    "asks": [{"price": "2501", "remaining_base_amount": "2"}],
                }
            ),
        )
        data_source = LighterPerpetualAPIOrderBookDataSource(["ETH-USD"], connector, SimpleNamespace())

        message = asyncio.run(data_source._order_book_snapshot("ETH-USD"))

        self.assertEqual(OrderBookMessageType.SNAPSHOT, message.type)
        self.assertEqual("ETH-USD", message.trading_pair)
        self.assertEqual(2500, message.bids[0].price)

    def test_connected_websocket_assistant_connects_and_returns_ws(self):
        ws = MockWSAssistant()
        api_factory = SimpleNamespace(get_ws_assistant=AsyncMock(return_value=ws))
        data_source = LighterPerpetualAPIOrderBookDataSource(["ETH-USD"], SimpleNamespace(), api_factory)

        connected_ws = asyncio.run(data_source._connected_websocket_assistant())

        self.assertEqual(ws, connected_ws)
        self.assertEqual(CONSTANTS.PUBLIC_WS_PING_INTERVAL, ws.connect_calls[0]["ping_timeout"])

    def test_subscribe_channels_sends_public_requests(self):
        market = SimpleNamespace(market_id=1)
        connector = SimpleNamespace(market_info_for_trading_pair=MagicMock(return_value=market))
        data_source = LighterPerpetualAPIOrderBookDataSource(["ETH-USD"], connector, SimpleNamespace())
        ws = MockWSAssistant()

        asyncio.run(data_source._subscribe_channels(ws))

        self.assertEqual(3, len(ws.sent))
        self.assertEqual({"type": "subscribe", "channel": "order_book/1"}, ws.sent[0].payload)
        self.assertEqual({"type": "subscribe", "channel": "trade/1"}, ws.sent[1].payload)
        self.assertEqual({"type": "subscribe", "channel": "market_stats/1"}, ws.sent[2].payload)

    def test_subscribe_and_unsubscribe_trading_pair(self):
        market = SimpleNamespace(market_id=1)
        connector = SimpleNamespace(market_info_for_trading_pair=MagicMock(return_value=market))
        data_source = LighterPerpetualAPIOrderBookDataSource(["ETH-USD"], connector, SimpleNamespace())
        data_source._ws_assistant = MockWSAssistant()
        data_source.add_trading_pair = MagicMock()
        data_source.remove_trading_pair = MagicMock()

        subscribe_result = asyncio.run(data_source.subscribe_to_trading_pair("ETH-USD"))
        unsubscribe_result = asyncio.run(data_source.unsubscribe_from_trading_pair("ETH-USD"))

        self.assertTrue(subscribe_result)
        self.assertTrue(unsubscribe_result)
        self.assertEqual(6, len(data_source._ws_assistant.sent))
        data_source.add_trading_pair.assert_called_once_with("ETH-USD")
        data_source.remove_trading_pair.assert_called_once_with("ETH-USD")

    def test_subscribe_to_trading_pair_requires_connected_ws(self):
        self.data_source._ws_assistant = None

        result = asyncio.run(self.data_source.subscribe_to_trading_pair("ETH-USD"))

        self.assertFalse(result)

    def test_funding_rate_from_response_prefers_direct_rate(self):
        rate = self.data_source._funding_rate_from_response(response={"rate": "0.0003"}, market_id=1)

        self.assertEqual(Decimal("0.0003"), rate)

    def test_funding_rate_from_response_uses_market_specific_entry(self):
        response = {
            "funding_rates": [
                {"market_id": 1, "rate": "0.0001"},
                {"market_id": 2, "rate": "0.0002"},
            ]
        }

        rate = self.data_source._funding_rate_from_response(response=response, market_id=2)

        self.assertEqual(Decimal("0.0002"), rate)

    def test_funding_rate_from_response_returns_zero_when_not_found(self):
        response = {"funding_rates": [{"market_id": 1, "rate": "0.0001"}]}

        rate = self.data_source._funding_rate_from_response(response=response, market_id=3)

        self.assertEqual(Decimal("0"), rate)

    @patch("hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_api_order_book_data_source.time.time")
    def test_next_funding_utc_timestamp(self, time_mock):
        time_mock.return_value = 1724979600  # 2024-08-30 01:00:00 UTC

        next_timestamp = self.data_source._next_funding_utc_timestamp()

        expected_timestamp = ((1724979600 // CONSTANTS.FUNDING_INTERVAL_SECONDS) + 1) * CONSTANTS.FUNDING_INTERVAL_SECONDS
        self.assertEqual(expected_timestamp, next_timestamp)

    def test_channel_originating_message_routes_market_stats_to_funding_queue(self):
        self.data_source._funding_info_messages_queue_key = "funding"

        message = {"channel": "market_stats:0", "type": "update/market_stats"}

        self.assertEqual("funding", self.data_source._channel_originating_message(message))

    def test_channel_originating_message_routes_public_messages(self):
        self.data_source._snapshot_messages_queue_key = "snapshot"
        self.data_source._diff_messages_queue_key = "diff"
        self.data_source._trade_messages_queue_key = "trade"
        self.data_source._funding_info_messages_queue_key = "funding"

        self.assertEqual(
            "snapshot",
            self.data_source._channel_originating_message(
                {"channel": "order_book:1", "type": "subscribed/order_book"}
            ),
        )
        self.assertEqual(
            "diff",
            self.data_source._channel_originating_message({"channel": "order_book:1", "type": "update/order_book"}),
        )
        self.assertEqual(
            "trade",
            self.data_source._channel_originating_message({"channel": "trade:1", "type": "update/trade"}),
        )
        self.assertEqual("", self.data_source._channel_originating_message({"channel": "unknown:1"}))

    def test_parse_order_book_and_trade_messages(self):
        market = SimpleNamespace(trading_pair="ETH-USD")
        self.data_source._connector = SimpleNamespace(market_info_for_market_id=MagicMock(return_value=market))
        queue = asyncio.Queue()
        snapshot_message = {
            "channel": "order_book:1",
            "timestamp": "1000",
            "order_book": {
                "nonce": 5,
                "bids": [{"price": "2500", "size": "1"}],
                "asks": [{"price": "2501", "size": "2"}],
            },
        }
        diff_message = {
            "channel": "order_book:1",
            "timestamp": "1001",
            "order_book": {
                "nonce": 6,
                "begin_nonce": 5,
                "bids": [{"price": "2500", "size": "0.5"}],
                "asks": [],
            },
        }
        trade_message = {
            "channel": "trade:1",
            "trades": [
                {
                    "trade_id": "t1",
                    "price": "2500",
                    "size": "0.1",
                    "is_maker_ask": True,
                    "transaction_time": "1000000",
                }
            ],
        }

        asyncio.run(self.data_source._parse_order_book_snapshot_message(snapshot_message, queue))
        asyncio.run(self.data_source._parse_order_book_diff_message(diff_message, queue))
        asyncio.run(self.data_source._parse_trade_message(trade_message, queue))

        self.assertEqual(OrderBookMessageType.SNAPSHOT, queue.get_nowait().type)
        self.assertEqual(OrderBookMessageType.DIFF, queue.get_nowait().type)
        self.assertEqual(OrderBookMessageType.TRADE, queue.get_nowait().type)

    def test_parse_funding_info_message_uses_nested_market_stats_payload(self):
        market = SimpleNamespace(trading_pair="ETH-USD")
        self.data_source._connector = SimpleNamespace(market_info_for_market_id=lambda market_id: market)
        queue = asyncio.Queue()

        raw_message = {
            "channel": "market_stats:0",
            "market_stats": {
                "market_id": 0,
                "index_price": "2500",
                "mark_price": "2499",
                "current_funding_rate": "0.0003",
                "funding_timestamp": 1724979600000,
            },
        }

        asyncio.run(self.data_source._parse_funding_info_message(raw_message, queue))
        update = queue.get_nowait()

        self.assertEqual("ETH-USD", update.trading_pair)
        self.assertEqual(Decimal("2500"), update.index_price)
        self.assertEqual(Decimal("2499"), update.mark_price)
        self.assertEqual(Decimal("0.0003"), update.rate)
        self.assertEqual(1724983200, update.next_funding_utc_timestamp)

    def test_parse_funding_info_message_ignores_missing_or_invalid_market_id(self):
        queue = asyncio.Queue()

        asyncio.run(self.data_source._parse_funding_info_message({"market_stats": {}}, queue))
        asyncio.run(self.data_source._parse_funding_info_message({"market_stats": {"market_id": "bad"}}, queue))

        self.assertTrue(queue.empty())

    def test_process_message_for_unknown_channel_ignores_connected_and_raises_error(self):
        asyncio.run(self.data_source._process_message_for_unknown_channel({"type": "connected"}, SimpleNamespace()))

        with self.assertRaises(IOError):
            asyncio.run(
                self.data_source._process_message_for_unknown_channel(
                    {"error": "boom"},
                    SimpleNamespace(),
                )
            )

    def test_funding_rate_from_response_handles_data_list_and_invalid_entries(self):
        response = {
            "data": [
                "bad",
                {"market_id": None, "rate": "0.1"},
                {"market_id": "bad", "rate": "0.2"},
                {"market_id": 2, "funding_rate": "0.0004"},
            ]
        }

        self.assertEqual(Decimal("0.0004"), self.data_source._funding_rate_from_response(response, market_id=2))
