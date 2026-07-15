import asyncio
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock

from hummingbot.connector.exchange.lighter import lighter_constants as CONSTANTS
from hummingbot.connector.exchange.lighter.lighter_api_order_book_data_source import LighterAPIOrderBookDataSource
from hummingbot.core.data_type.order_book_message import OrderBookMessageType


class MockWSAssistant:
    def __init__(self):
        self.sent = []
        self.connect_calls = []

    async def connect(self, **kwargs):
        self.connect_calls.append(kwargs)

    async def send(self, request):
        self.sent.append(request)


class LighterAPIOrderBookDataSourceTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.data_source = LighterAPIOrderBookDataSource.__new__(LighterAPIOrderBookDataSource)
        self.data_source._snapshot_messages_queue_key = "snapshot"
        self.data_source._diff_messages_queue_key = "diff"
        self.data_source._trade_messages_queue_key = "trade"

    def test_channel_originating_message_routes_snapshot(self):
        message = {"channel": "order_book:2048", "type": "subscribed/order_book"}

        self.assertEqual("snapshot", self.data_source._channel_originating_message(message))

    def test_channel_originating_message_routes_diff(self):
        message = {"channel": "order_book:2048", "type": "update/order_book"}

        self.assertEqual("diff", self.data_source._channel_originating_message(message))

    def test_channel_originating_message_routes_trade(self):
        message = {"channel": "trade:2048", "type": "update/trade"}

        self.assertEqual("trade", self.data_source._channel_originating_message(message))

    def test_channel_originating_message_returns_empty_for_unknown_channel(self):
        message = {"channel": "account_all_orders:1", "type": "update"}

        self.assertEqual("", self.data_source._channel_originating_message(message))

    def test_init_sets_dependencies(self):
        connector = SimpleNamespace()
        api_factory = SimpleNamespace()

        data_source = LighterAPIOrderBookDataSource(
            trading_pairs=["ETH-USDC"],
            connector=connector,
            api_factory=api_factory,
            domain="lighter_testnet",
        )

        self.assertEqual(connector, data_source._connector)
        self.assertEqual(api_factory, data_source._api_factory)
        self.assertEqual("lighter_testnet", data_source._domain)

    def test_get_last_traded_prices_delegates_to_connector(self):
        connector = SimpleNamespace(get_last_traded_prices=AsyncMock(return_value={"ETH-USDC": 2500.0}))
        data_source = LighterAPIOrderBookDataSource(["ETH-USDC"], connector, SimpleNamespace())

        prices = asyncio.run(data_source.get_last_traded_prices(["ETH-USDC"]))

        self.assertEqual({"ETH-USDC": 2500.0}, prices)
        connector.get_last_traded_prices.assert_awaited_once_with(trading_pairs=["ETH-USDC"])

    def test_request_order_book_snapshot_uses_market_id(self):
        market = SimpleNamespace(market_id=2048)
        connector = SimpleNamespace(
            market_info_for_trading_pair=MagicMock(return_value=market),
            _api_get=AsyncMock(return_value={"bids": [], "asks": []}),
        )
        data_source = LighterAPIOrderBookDataSource(["ETH-USDC"], connector, SimpleNamespace())

        snapshot = asyncio.run(data_source._request_order_book_snapshot("ETH-USDC"))

        self.assertEqual({"bids": [], "asks": []}, snapshot)
        connector._api_get.assert_awaited_once_with(
            path_url=CONSTANTS.SNAPSHOT_PATH_URL,
            params={"market_id": 2048, "limit": CONSTANTS.ORDER_BOOK_SNAPSHOT_LIMIT},
        )

    def test_order_book_snapshot_builds_snapshot_message(self):
        market = SimpleNamespace(market_id=2048)
        connector = SimpleNamespace(
            market_info_for_trading_pair=MagicMock(return_value=market),
            _api_get=AsyncMock(
                return_value={
                    "bids": [{"price": "2500", "remaining_base_amount": "1"}],
                    "asks": [{"price": "2501", "remaining_base_amount": "2"}],
                }
            ),
        )
        data_source = LighterAPIOrderBookDataSource(["ETH-USDC"], connector, SimpleNamespace())

        message = asyncio.run(data_source._order_book_snapshot("ETH-USDC"))

        self.assertEqual(OrderBookMessageType.SNAPSHOT, message.type)
        self.assertEqual("ETH-USDC", message.trading_pair)
        self.assertEqual(2500, message.bids[0].price)

    def test_connected_websocket_assistant_connects_and_returns_ws(self):
        ws = MockWSAssistant()
        api_factory = SimpleNamespace(get_ws_assistant=AsyncMock(return_value=ws))
        data_source = LighterAPIOrderBookDataSource(["ETH-USDC"], SimpleNamespace(), api_factory)

        connected_ws = asyncio.run(data_source._connected_websocket_assistant())

        self.assertEqual(ws, connected_ws)
        self.assertEqual(CONSTANTS.PUBLIC_WS_PING_INTERVAL, ws.connect_calls[0]["ping_timeout"])

    def test_subscribe_channels_sends_order_book_and_trade_requests(self):
        market = SimpleNamespace(market_id=2048)
        connector = SimpleNamespace(market_info_for_trading_pair=MagicMock(return_value=market))
        data_source = LighterAPIOrderBookDataSource(["ETH-USDC"], connector, SimpleNamespace())
        ws = MockWSAssistant()

        asyncio.run(data_source._subscribe_channels(ws))

        self.assertEqual(2, len(ws.sent))
        self.assertEqual({"type": "subscribe", "channel": "order_book/2048"}, ws.sent[0].payload)
        self.assertEqual({"type": "subscribe", "channel": "trade/2048"}, ws.sent[1].payload)

    def test_subscribe_to_trading_pair_requires_connected_ws(self):
        data_source = LighterAPIOrderBookDataSource.__new__(LighterAPIOrderBookDataSource)
        data_source._ws_assistant = None

        result = asyncio.run(data_source.subscribe_to_trading_pair("ETH-USDC"))

        self.assertFalse(result)

    def test_subscribe_and_unsubscribe_trading_pair(self):
        market = SimpleNamespace(market_id=2048)
        connector = SimpleNamespace(market_info_for_trading_pair=MagicMock(return_value=market))
        data_source = LighterAPIOrderBookDataSource(["ETH-USDC"], connector, SimpleNamespace())
        data_source._ws_assistant = MockWSAssistant()
        data_source.add_trading_pair = MagicMock()
        data_source.remove_trading_pair = MagicMock()

        subscribe_result = asyncio.run(data_source.subscribe_to_trading_pair("ETH-USDC"))
        unsubscribe_result = asyncio.run(data_source.unsubscribe_from_trading_pair("ETH-USDC"))

        self.assertTrue(subscribe_result)
        self.assertTrue(unsubscribe_result)
        self.assertEqual(4, len(data_source._ws_assistant.sent))
        data_source.add_trading_pair.assert_called_once_with("ETH-USDC")
        data_source.remove_trading_pair.assert_called_once_with("ETH-USDC")

    def test_parse_order_book_and_trade_messages(self):
        market = SimpleNamespace(trading_pair="ETH-USDC")
        self.data_source._connector = SimpleNamespace(market_info_for_market_id=MagicMock(return_value=market))
        queue = asyncio.Queue()
        snapshot_message = {
            "channel": "order_book:2048",
            "timestamp": "1000",
            "order_book": {
                "nonce": 5,
                "bids": [{"price": "2500", "size": "1"}],
                "asks": [{"price": "2501", "size": "2"}],
            },
        }
        diff_message = {
            "channel": "order_book:2048",
            "timestamp": "1001",
            "order_book": {
                "nonce": 6,
                "begin_nonce": 5,
                "bids": [{"price": "2500", "size": "0.5"}],
                "asks": [],
            },
        }
        trade_message = {
            "channel": "trade:2048",
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

    def test_process_message_for_unknown_channel_ignores_connected_and_raises_error(self):
        asyncio.run(self.data_source._process_message_for_unknown_channel({"type": "connected"}, SimpleNamespace()))

        with self.assertRaises(IOError):
            asyncio.run(
                self.data_source._process_message_for_unknown_channel(
                    {"error": "boom"},
                    SimpleNamespace(),
                )
            )
