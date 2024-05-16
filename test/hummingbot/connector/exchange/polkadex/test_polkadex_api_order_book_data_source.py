import asyncio
import json
import re
from decimal import Decimal
from test.hummingbot.connector.exchange.polkadex.programmable_query_executor import ProgrammableQueryExecutor
from typing import Awaitable, Optional, Union
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock, patch

from bidict import bidict

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.polkadex.polkadex_api_order_book_data_source import PolkadexAPIOrderBookDataSource
from hummingbot.connector.exchange.polkadex.polkadex_exchange import PolkadexExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType


class PolkadexAPIOrderBookDataSourceTests(TestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}-1"

    def setUp(self) -> None:
        super().setUp()
        self._original_async_loop = asyncio.get_event_loop()
        self.async_loop = asyncio.new_event_loop()
        self.async_tasks = []
        asyncio.set_event_loop(self.async_loop)
        self.mocking_assistant = NetworkMockingAssistant()

        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.connector = PolkadexExchange(
            client_config_map=client_config_map,
            polkadex_seed_phrase="",
            trading_pairs=[self.trading_pair],
            trading_required=False,
        )
        self.connector._data_source._query_executor = ProgrammableQueryExecutor()

        self.data_source = PolkadexAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            data_source=self.connector._data_source,
        )

        self._original_full_order_book_reset_time = self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = -1

        self.log_records = []
        self._logs_event: Optional[asyncio.Event] = None
        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.connector._set_trading_pair_symbol_map(bidict({self.ex_trading_pair: self.trading_pair}))

    def tearDown(self) -> None:
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = self._original_full_order_book_reset_time
        self.async_run_with_timeout(self.data_source._data_source.stop())
        for task in self.async_tasks:
            task.cancel()
        self.async_loop.stop()
        self.async_loop.close()
        # Since the event loop will change we need to remove the logs event created in the old event loop
        self._logs_event = None
        asyncio.set_event_loop(self._original_async_loop)
        super().tearDown()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.async_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def create_task(self, coroutine: Awaitable) -> asyncio.Task:
        task = self.async_loop.create_task(coroutine)
        self.async_tasks.append(task)
        return task

    def handle(self, record):
        self.log_records.append(record)
        if self._logs_event is not None:
            self._logs_event.set()

    def is_logged(self, log_level: str, message: Union[str, re.Pattern]) -> bool:
        expression = (
            re.compile(
                f"^{message}$"
                .replace(".", r"\.")
                .replace("?", r"\?")
                .replace("/", r"\/")
                .replace("(", r"\(")
                .replace(")", r"\)")
                .replace("[", r"\[")
                .replace("]", r"\]")
            )
            if isinstance(message, str)
            else message
        )
        return any(
            record.levelname == log_level and expression.match(record.getMessage()) is not None
            for record in self.log_records
        )

    def test_get_new_order_book_successful(self):
        data = [
            {"side": "Ask", "p": 9487.5, "q": 522147, "s": "Ask", "stid": 1},
            {"side": "Bid", "p": 9487, "q": 336241, "s": "Bid", "stid": 1},
        ]
        self.data_source._data_source._query_executor._order_book_snapshots.put_nowait(data)

        order_book = self.async_run_with_timeout(self.data_source.get_new_order_book(self.trading_pair))

        expected_update_id = 1

        self.assertEqual(expected_update_id, order_book.snapshot_uid)
        bids = list(order_book.bid_entries())
        asks = list(order_book.ask_entries())
        self.assertEqual(1, len(bids))
        self.assertEqual(9487, bids[0].price)
        self.assertEqual(336241, bids[0].amount)
        self.assertEqual(expected_update_id, bids[0].update_id)
        self.assertEqual(1, len(asks))
        self.assertEqual(9487.5, asks[0].price)
        self.assertEqual(522147, asks[0].amount)
        self.assertEqual(expected_update_id, asks[0].update_id)

    def test_listen_for_trades_cancelled_when_listening(self):
        mock_queue = MagicMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.data_source._message_queue[self.data_source._trade_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(self.data_source.listen_for_trades(self.async_loop, msg_queue))

    def test_listen_for_trades_logs_exception(self):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [Exception("some error"), asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._trade_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        try:
            self.async_run_with_timeout(self.data_source.listen_for_trades(self.async_loop, msg_queue))
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self.is_logged(
                "ERROR", "Unexpected error when processing public trade updates from exchange"
            )
        )

    def test_listen_for_trades_successful(self):
        expected_trade_id = "1664193952989"
        trade_data = {
            "type": "TradeFormat",
            "m": self.ex_trading_pair,
            "m_side": "Ask",
            "trade_id": expected_trade_id,
            "p": "1718.5",
            "q": "10",
            "t": 1664193952989,
            "stid": "16",
        }
        trade_event = {"websocket_streams": {"data": json.dumps(trade_data)}}

        self.data_source._data_source._query_executor._public_trades_update_events.put_nowait(trade_event)

        msg_queue = asyncio.Queue()
        self.async_run_with_timeout(self.data_source._data_source.start(market_symbols=[self.ex_trading_pair]))

        self.create_task(self.data_source.listen_for_trades(self.async_loop, msg_queue))

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(OrderBookMessageType.TRADE, msg.type)
        self.assertEqual(expected_trade_id, msg.trade_id)
        self.assertEqual(trade_data["t"] * 1e-3, msg.timestamp)
        expected_price = Decimal(trade_data["p"])
        expected_amount = Decimal(trade_data["q"])
        self.assertEqual(expected_amount, msg.content["amount"])
        self.assertEqual(expected_price, msg.content["price"])
        self.assertEqual(self.trading_pair, msg.content["trading_pair"])
        self.assertEqual(float(TradeType.SELL.value), msg.content["trade_type"])

    def test_listen_for_order_book_diffs_cancelled(self):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.data_source._message_queue[self.data_source._diff_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(self.data_source.listen_for_order_book_diffs(self.async_loop, msg_queue))

    def test_listen_for_order_book_diffs_logs_exception(self):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [Exception("some error"), asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._diff_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        try:
            self.async_run_with_timeout(self.data_source.listen_for_order_book_diffs(self.async_loop, msg_queue))
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self.is_logged(
                "ERROR", "Unexpected error when processing public order book updates from exchange"
            )
        )

    @patch("hummingbot.connector.exchange.polkadex.polkadex_data_source.PolkadexDataSource._time")
    def test_listen_for_order_book_diffs_successful(self, time_mock):
        time_mock.return_value = 1640001112.223

        order_book_data = {
            "i": 1,
            "a": {
                "3001": "0",
            },
            "b": {
                "2999": "8",
                "1.671": "52.952",
            },
        }
        order_book_event = {"websocket_streams": {"data": json.dumps(order_book_data)}}

        self.data_source._data_source._query_executor._order_book_update_events.put_nowait(order_book_event)

        msg_queue: asyncio.Queue = asyncio.Queue()
        self.async_run_with_timeout(
            self.data_source._data_source.start(market_symbols=[self.ex_trading_pair])
        )
        self.create_task(self.data_source.listen_for_order_book_diffs(self.async_loop, msg_queue))

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(OrderBookMessageType.DIFF, msg.type)
        self.assertEqual(-1, msg.trade_id)
        self.assertEqual(time_mock.return_value, msg.timestamp)
        expected_update_id = 1
        self.assertEqual(expected_update_id, msg.update_id)

        bids = msg.bids
        asks = msg.asks
        self.assertEqual(2, len(bids))
        self.assertEqual(2999.0, bids[0].price)
        self.assertEqual(8, bids[0].amount)
        self.assertEqual(expected_update_id, bids[0].update_id)
        self.assertEqual(1, len(asks))
        self.assertEqual(3001, asks[0].price)
        self.assertEqual(0, asks[0].amount)
        self.assertEqual(expected_update_id, asks[0].update_id)
