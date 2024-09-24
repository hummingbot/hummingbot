import asyncio
import json
import unittest
from decimal import Decimal
from typing import Awaitable
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses.core import aioresponses
from bidict import bidict

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.dexalot.dexalot_api_order_book_data_source import DexalotAPIOrderBookDataSource
from hummingbot.connector.exchange.dexalot.dexalot_exchange import DexalotExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage


class DexalotAPIOrderBookDataSourceUnitTests(unittest.TestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "AVAX"
        cls.quote_asset = "USDC"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = cls.base_asset + "/" + cls.quote_asset
        cls.domain = "com"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task = None
        self.mocking_assistant = NetworkMockingAssistant()

        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.connector = DexalotExchange(
            client_config_map=client_config_map,
            dexalot_api_key="testkey",
            dexalot_api_secret="13e56ca9cceebf1f33065c2c5376ab38570a114bc1b003b60d838f92be9d7930",  # noqa: mock
            trading_pairs=[self.trading_pair],
            trading_required=False,
            domain=self.domain)
        self.data_source = DexalotAPIOrderBookDataSource(trading_pairs=[self.trading_pair],
                                                         connector=self.connector,
                                                         api_factory=self.connector._web_assistants_factory,
                                                         domain=self.domain)
        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self._original_full_order_book_reset_time = self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = -1

        self.resume_test_event = asyncio.Event()

        self.connector._set_trading_pair_symbol_map(bidict({self.ex_trading_pair: self.trading_pair}))

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = self._original_full_order_book_reset_time
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def _successfully_subscribed_event(self):
        resp = {'data': '2024-08-28T01:00:05.000Z', 'type': 'APP_VERSION'}
        return resp

    def _trade_update_event(self):
        resp = {
            'data': [
                {'execId': '1807784856', 'price': '22.484', 'quantity': '33.25', 'takerSide': 1,
                 'ts': '2024-09-03T12:22:14.000Z'}],
            'type': 'lastTrade', 'pair': 'AVAX/USDC', 'cap': 50
        }
        return resp

    def _order_diff_event(self):
        return None

    def _snapshot_response(self):
        resp = {
            "lastUpdateId": 1027024,
            "bids": [
                [
                    "4.00000000",
                    "431.00000000"
                ]
            ],
            "asks": [
                [
                    "4.00000200",
                    "12.00000000"
                ]
            ]
        }
        return resp

    @aioresponses()
    @patch("hummingbot.connector.exchange.dexalot.dexalot_api_order_book_data_source"
           ".DexalotAPIOrderBookDataSource._time")
    def test_get_new_order_book_successful(self, mock_api, mock_time):
        mock_time.return_value = 1640780000
        order_book: OrderBook = self.async_run_with_timeout(
            self.data_source.get_new_order_book(self.trading_pair)
        )

        expected_update_id = 1640780000

        self.assertEqual(expected_update_id, order_book.snapshot_uid)
        bids = list(order_book.bid_entries())
        asks = list(order_book.ask_entries())
        self.assertEqual(0, len(bids))
        self.assertEqual(0, len(asks))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_subscribes_to_trades_and_order_diffs(self, ws_connect_mock):
        self._simulate_trading_rules_initialized()

        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        result_subscribe = {'data': '2024-08-28T01:00:05.000Z', 'type': 'APP_VERSION'}

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe))

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_subscription_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value)

        self.assertEqual(1, len(sent_subscription_messages))

        expected_subscription = [{
            "data": self.ex_trading_pair,
            "pair": self.ex_trading_pair,
            "type": "subscribe",
            "decimal": 3
        }]
        self.assertEqual(expected_subscription, sent_subscription_messages)

        self.assertTrue(self._is_logged(
            "INFO",
            "Subscribed to public order book and trade channels..."
        ))

    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    @patch("aiohttp.ClientSession.ws_connect")
    def test_listen_for_subscriptions_raises_cancel_exception(self, mock_ws, _: AsyncMock):
        mock_ws.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())
            self.async_run_with_timeout(self.listening_task)

    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_logs_exception_details(self, mock_ws, sleep_mock):
        mock_ws.side_effect = Exception("TEST ERROR.")
        sleep_mock.side_effect = lambda _: self._create_exception_and_unlock_test_with_event(asyncio.CancelledError())

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error occurred when listening to order book streams. Retrying in 5 seconds..."))

    def test_subscribe_channels_raises_cancel_exception(self):
        self._simulate_trading_rules_initialized()
        mock_ws = MagicMock()
        mock_ws.send.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(self.data_source._subscribe_channels(mock_ws))
            self.async_run_with_timeout(self.listening_task)

    def test_subscribe_channels_raises_exception_and_logs_error(self):
        self._simulate_trading_rules_initialized()
        mock_ws = MagicMock()
        mock_ws.send.side_effect = Exception("Test Error")

        with self.assertRaises(Exception):
            self.listening_task = self.ev_loop.create_task(self.data_source._subscribe_channels(mock_ws))
            self.async_run_with_timeout(self.listening_task)

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error occurred subscribing to order book trading and delta streams...")
        )

    def test_listen_for_trades_cancelled_when_listening(self):
        mock_queue = MagicMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.data_source._message_queue[self.data_source._trade_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_trades(self.ev_loop, msg_queue)
            )
            self.async_run_with_timeout(self.listening_task)

    def test_listen_for_trades_logs_exception(self):
        incomplete_resp = {
            "m": 1,
            "i": 2,
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [incomplete_resp, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._trade_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_trades(self.ev_loop, msg_queue)
        )

        try:
            self.async_run_with_timeout(self.listening_task)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error when processing public trade updates from exchange"))

    def test_listen_for_trades_successful(self):
        self._simulate_trading_rules_initialized()

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [self._trade_update_event(), asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._trade_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_trades(self.ev_loop, msg_queue))

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual("1807784856", msg.trade_id)

    def get_trading_rule_rest_msg(self):
        return [
            {'env': 'production-multi-subnet', 'pair': 'AVAX/USDC', 'base': 'AVAX', 'quote': 'USDC',
             'basedisplaydecimals': 3,
             'quotedisplaydecimals': 3, 'baseaddress': '0x0000000000000000000000000000000000000000',
             'quoteaddress': '0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E',  # noqa: mock
             'mintrade_amnt': '5.000000000000000000',
             'maxtrade_amnt': '50000.000000000000000000', 'base_evmdecimals': 18, 'quote_evmdecimals': 6,
             'allowswap': True,
             'auctionmode': 0, 'auctionendtime': None, 'status': 'deployed', 'maker_rate_bps': 10, 'taker_rate_bps': 12,
             'allowed_slippage_pct': 5, 'additional_ordertypes': 0, 'taker_fee': 0.001, 'maker_fee': 0.0012}
        ]

    def _simulate_trading_rules_initialized(self):
        mocked_response = self.get_trading_rule_rest_msg()
        self.connector._initialize_trading_pair_symbols_from_exchange_info(mocked_response)
        min_order_size = Decimal(f"1e-{mocked_response[0]['basedisplaydecimals']}")
        min_price_inc = Decimal(f"1e-{mocked_response[0]['quotedisplaydecimals']}")
        self.connector._trading_rules = {
            self.trading_pair: TradingRule(
                trading_pair=self.trading_pair,
                min_order_size=min_order_size,
                min_price_increment=min_price_inc,
                min_base_amount_increment=min_order_size
            )
        }
