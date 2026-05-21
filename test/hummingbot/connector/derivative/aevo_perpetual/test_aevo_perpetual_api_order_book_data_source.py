import asyncio
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock

from bidict import bidict

from hummingbot.connector.derivative.aevo_perpetual import aevo_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.aevo_perpetual.aevo_perpetual_api_order_book_data_source import (
    AevoPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.aevo_perpetual.aevo_perpetual_derivative import AevoPerpetualDerivative
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessageType
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest


class AevoPerpetualAPIOrderBookDataSourceTests(IsolatedAsyncioWrapperTestCase):
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "ETH"
        cls.quote_asset = "USDC"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}-PERP"

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.log_records = []

        self.connector = AevoPerpetualDerivative(
            aevo_perpetual_api_key="",
            aevo_perpetual_api_secret="",
            aevo_perpetual_signing_key="",
            aevo_perpetual_account_address="",
            trading_pairs=[self.trading_pair],
            trading_required=False,
        )
        self.data_source = AevoPerpetualAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory,
        )

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.connector._set_trading_pair_symbol_map(bidict({self.ex_trading_pair: self.trading_pair}))

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    async def test_get_last_traded_prices_delegates_connector(self):
        self.connector.get_last_traded_prices = AsyncMock(return_value={self.trading_pair: 123.45})

        result = await self.data_source.get_last_traded_prices([self.trading_pair])

        self.connector.get_last_traded_prices.assert_awaited_once_with(trading_pairs=[self.trading_pair])
        self.assertEqual({self.trading_pair: 123.45}, result)

    async def test_get_funding_info_requests_rest_endpoints(self):
        self.connector.exchange_symbol_associated_to_pair = AsyncMock(return_value=self.ex_trading_pair)
        funding_response = {"funding_rate": "0.0001", "next_epoch": "1000000000000000000"}
        instrument_response = {"index_price": "2000", "mark_price": "2001"}
        self.connector._api_get = AsyncMock(side_effect=[funding_response, instrument_response])

        result = await self.data_source.get_funding_info(self.trading_pair)

        self.assertIsInstance(result, FundingInfo)
        self.assertEqual(self.trading_pair, result.trading_pair)
        self.assertEqual(Decimal("2000"), result.index_price)
        self.assertEqual(Decimal("2001"), result.mark_price)
        self.assertEqual(1000000000, result.next_funding_utc_timestamp)
        self.assertEqual(Decimal("0.0001"), result.rate)

    async def test_listen_for_funding_info_pushes_updates(self):
        funding_info = FundingInfo(
            trading_pair=self.trading_pair,
            index_price=Decimal("100"),
            mark_price=Decimal("101"),
            next_funding_utc_timestamp=123,
            rate=Decimal("0.0002"),
        )
        self.data_source.get_funding_info = AsyncMock(return_value=funding_info)
        self.data_source._sleep = AsyncMock(side_effect=asyncio.CancelledError)

        queue = asyncio.Queue()
        listen_task = self.local_event_loop.create_task(self.data_source.listen_for_funding_info(queue))

        update: FundingInfoUpdate = await queue.get()
        self.assertEqual(self.trading_pair, update.trading_pair)
        self.assertEqual(funding_info.index_price, update.index_price)
        self.assertEqual(funding_info.mark_price, update.mark_price)
        self.assertEqual(funding_info.next_funding_utc_timestamp, update.next_funding_utc_timestamp)
        self.assertEqual(funding_info.rate, update.rate)

        with self.assertRaises(asyncio.CancelledError):
            await listen_task

    async def test_request_order_book_snapshot_calls_connector(self):
        self.connector.exchange_symbol_associated_to_pair = AsyncMock(return_value=self.ex_trading_pair)
        self.connector._api_get = AsyncMock(return_value={"data": "snapshot"})

        result = await self.data_source._request_order_book_snapshot(self.trading_pair)

        self.assertEqual({"data": "snapshot"}, result)
        self.connector._api_get.assert_awaited_once_with(
            path_url=CONSTANTS.ORDERBOOK_PATH_URL,
            params={"instrument_name": self.ex_trading_pair},
        )

    async def test_order_book_snapshot_builds_message(self):
        self.data_source._request_order_book_snapshot = AsyncMock(return_value={
            "last_updated": 1000000000,
            "bids": [["100", "1.5"]],
            "asks": [["101", "2"]],
        })

        message = await self.data_source._order_book_snapshot(self.trading_pair)

        self.assertEqual(OrderBookMessageType.SNAPSHOT, message.type)
        self.assertEqual(self.trading_pair, message.content["trading_pair"])
        self.assertEqual(1000000000, message.update_id)
        self.assertEqual([[100.0, 1.5]], message.content["bids"])
        self.assertEqual([[101.0, 2.0]], message.content["asks"])
        self.assertEqual(1.0, message.timestamp)

    async def test_connected_websocket_assistant_connects(self):
        ws_mock = AsyncMock()
        self.data_source._api_factory.get_ws_assistant = AsyncMock(return_value=ws_mock)

        ws_assistant = await self.data_source._connected_websocket_assistant()

        self.assertIs(ws_mock, ws_assistant)
        ws_mock.connect.assert_awaited_once_with(
            ws_url=CONSTANTS.WSS_URL,
            ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL,
        )

    async def test_subscribe_channels_sends_expected_requests(self):
        ws_mock = AsyncMock()
        self.connector.exchange_symbol_associated_to_pair = AsyncMock(return_value=self.ex_trading_pair)

        await self.data_source._subscribe_channels(ws_mock)

        self.assertEqual(2, ws_mock.send.call_count)
        first_call = ws_mock.send.call_args_list[0].args[0]
        second_call = ws_mock.send.call_args_list[1].args[0]
        self.assertIsInstance(first_call, WSJSONRequest)
        self.assertIsInstance(second_call, WSJSONRequest)
        self.assertEqual(
            {"op": "subscribe", "data": [f"{CONSTANTS.WS_TRADE_CHANNEL}:{self.ex_trading_pair}"]},
            first_call.payload,
        )
        self.assertEqual(
            {"op": "subscribe", "data": [f"{CONSTANTS.WS_ORDERBOOK_CHANNEL}:{self.ex_trading_pair}"]},
            second_call.payload,
        )
        self.assertTrue(self._is_logged("INFO", "Subscribed to public order book and trade channels..."))

    async def test_channel_originating_message_routes_channels(self):
        snapshot_message = {
            "channel": f"{CONSTANTS.WS_ORDERBOOK_CHANNEL}:{self.ex_trading_pair}",
            "data": {"type": "snapshot"},
        }
        diff_message = {
            "channel": f"{CONSTANTS.WS_ORDERBOOK_CHANNEL}:{self.ex_trading_pair}",
            "data": {"type": "update"},
        }
        trade_message = {"channel": f"{CONSTANTS.WS_TRADE_CHANNEL}:{self.ex_trading_pair}"}
        unknown_message = {"channel": "unknown-channel"}

        self.assertEqual(self.data_source._snapshot_messages_queue_key,
                         self.data_source._channel_originating_message(snapshot_message))
        self.assertEqual(self.data_source._diff_messages_queue_key,
                         self.data_source._channel_originating_message(diff_message))
        self.assertEqual(self.data_source._trade_messages_queue_key,
                         self.data_source._channel_originating_message(trade_message))
        self.assertEqual("", self.data_source._channel_originating_message(unknown_message))
        self.assertTrue(self._is_logged("WARNING", "Unknown WS channel received: unknown-channel"))

    async def test_parse_order_book_diff_message_puts_order_book_message(self):
        queue = asyncio.Queue()
        raw_message = {
            "data": {
                "last_updated": 1000000000,
                "instrument_name": self.ex_trading_pair,
                "bids": [["100", "1"]],
                "asks": [["101", "2"]],
            }
        }
        self.connector.trading_pair_associated_to_exchange_symbol = AsyncMock(return_value=self.trading_pair)

        await self.data_source._parse_order_book_diff_message(raw_message, queue)
        message = await queue.get()

        self.assertEqual(OrderBookMessageType.DIFF, message.type)
        self.assertEqual(self.trading_pair, message.trading_pair)
        self.assertEqual(1000000000, message.update_id)
        self.assertEqual([[100.0, 1.0]], message.content["bids"])
        self.assertEqual([[101.0, 2.0]], message.content["asks"])
        self.assertEqual(1.0, message.timestamp)

    async def test_parse_order_book_snapshot_message_puts_order_book_message(self):
        queue = asyncio.Queue()
        raw_message = {
            "data": {
                "last_updated": 2000000000,
                "instrument_name": self.ex_trading_pair,
                "bids": [["99", "1"]],
                "asks": [["102", "3"]],
            }
        }
        self.connector.trading_pair_associated_to_exchange_symbol = AsyncMock(return_value=self.trading_pair)

        await self.data_source._parse_order_book_snapshot_message(raw_message, queue)
        message = await queue.get()

        self.assertEqual(OrderBookMessageType.SNAPSHOT, message.type)
        self.assertEqual(self.trading_pair, message.trading_pair)
        self.assertEqual(2000000000, message.update_id)
        self.assertEqual([[99.0, 1.0]], message.content["bids"])
        self.assertEqual([[102.0, 3.0]], message.content["asks"])
        self.assertEqual(2.0, message.timestamp)

    async def test_parse_trade_message_puts_trade_message(self):
        queue = asyncio.Queue()
        raw_message = {
            "data": {
                "instrument_name": self.ex_trading_pair,
                "created_timestamp": "3000000000",
                "trade_id": 789,
                "side": "buy",
                "price": "105",
                "amount": "0.25",
            }
        }
        self.connector.trading_pair_associated_to_exchange_symbol = AsyncMock(return_value=self.trading_pair)

        await self.data_source._parse_trade_message(raw_message, queue)
        message = await queue.get()

        self.assertEqual(OrderBookMessageType.TRADE, message.type)
        self.assertEqual(self.trading_pair, message.trading_pair)
        self.assertEqual(str(789), message.trade_id)
        self.assertEqual(float(TradeType.BUY.value), message.content["trade_type"])
        self.assertEqual(105.0, message.content["price"])
        self.assertEqual(0.25, message.content["amount"])
        self.assertEqual(3.0, message.timestamp)
