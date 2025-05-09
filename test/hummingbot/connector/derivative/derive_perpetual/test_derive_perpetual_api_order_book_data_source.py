import asyncio
import json
import re
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Dict
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses import aioresponses
from bidict import bidict

import hummingbot.connector.derivative.derive_perpetual.derive_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.derive_perpetual.derive_perpetual_web_utils as web_utils
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.derivative.derive_perpetual.derive_perpetual_api_order_book_data_source import (
    DerivePerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.derive_perpetual.derive_perpetual_derivative import DerivePerpetualDerivative
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage


class DeriveAPIOrderBookDataSourceTests(IsolatedAsyncioWrapperTestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "BTC"
        cls.quote_asset = "USDC"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}-PERP"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task = None

        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.connector = DerivePerpetualDerivative(
            client_config_map,
            derive_perpetual_api_key="testkey",
            derive_perpetual_api_secret="13e56ca9cceebf1f33065c2c5376ab38570a114bc1b003b60d838f92be9d7930",  # noqa: mock
            sub_id="45686",
            trading_pairs=[self.trading_pair],
        )
        self.data_source = DerivePerpetualAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory,
        )

        self._original_full_order_book_reset_time = self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = -1

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.connector._set_trading_pair_symbol_map(
            bidict({f"{self.base_asset}-PERP": self.trading_pair}))

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.mocking_assistant = NetworkMockingAssistant()
        self.resume_test_event = asyncio.Event()

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

    def resume_test_callback(self, *_, **__):
        self.resume_test_event.set()
        return None

    @aioresponses()
    @patch("hummingbot.connector.derivative.derive_perpetual.derive_perpetual_api_order_book_data_source"
           ".DerivePerpetualAPIOrderBookDataSource._time")
    async def test_get_new_order_book_successful(self, mock_api, mock_time):
        mock_time.return_value = 1737885894
        order_book: OrderBook = await self.data_source.get_new_order_book(self.trading_pair)

        expected_update_id = 1737885894

        self.assertEqual(expected_update_id, order_book.snapshot_uid)
        bids = list(order_book.bid_entries())
        asks = list(order_book.ask_entries())
        self.assertEqual(0, len(bids))
        self.assertEqual(0, len(asks))

    def _trade_update_event(self):
        resp = {"params": {
            'channel': f'trades.{self.base_asset}-PERP',
            'data': [
                {
                    'trade_id': '5f249af2-2a84-47b2-946e-2552f886f0a8',  # noqa: mock
                    'instrument_name': f'{self.base_asset}-PERP', 'timestamp': 1737810932869,
                    'trade_price': '1.6682', 'trade_amount': '20', 'mark_price': '1.667960602579197952',
                    'index_price': '1.667960602579197952', 'direction': 'sell', 'quote_id': None
                }
            ]
        }}
        return resp

    def get_ws_snapshot_msg(self) -> Dict:
        return {"params": {
            'channel': f'orderbook.{self.base_asset}-PERP.1.100',
            'data': {
                'timestamp': 1700687397643, 'instrument_name': f'{self.base_asset}-PERP', 'publish_id': 2865914,
                'bids': [['1.6679', '2157.37'], ['1.6636', '2876.75'], ['1.51', '1']],
                'asks': [['1.6693', '2157.56'], ['1.6736', '2876.32'], ['2.65', '8.93'], ['2.75', '8.97']]
            }
        }}

    def get_ws_diff_msg(self) -> Dict:
        return {"params": {
            'channel': f'orderbook.{self.base_asset}-PERP.1.100',
            'data': {
                'timestamp': 1700687397643, 'instrument_name': f'{self.base_asset}-PERP', 'publish_id': 2865914,
                'bids': [['1.6679', '2157.37'], ['1.6636', '2876.75'], ['1.51', '1']],
                'asks': [['1.6693', '2157.56'], ['1.6736', '2876.32'], ['2.65', '8.93'], ['2.75', '8.97']]
            }
        }}

    def get_ws_diff_msg_2(self) -> Dict:
        return {
            'channel': f'orderbook.{self.base_asset}-PERP.1.100',
            'data': {
                'timestamp': 1700687397643, 'instrument_name': f'{self.base_asset}-PERP', 'publish_id': 2865914,
                'bids': [['1.6679', '2157.37'], ['1.6636', '2876.75'], ['1.51', '1']],
                'asks': [['1.6693', '2157.56'], ['1.6736', '2876.32'], ['2.65', '8.93'], ['2.75', '8.97']]
            }
        }

    def get_funding_info_rest_msg(self):
        return {"result":
                {
                    'instrument_type': 'perp',
                    'instrument_name': f'{self.base_asset}-PERP',
                    'scheduled_activation': 1728508925,
                    'scheduled_deactivation': 9223372036854775807,
                    'is_active': True,
                    'tick_size': '0.01',
                    'minimum_amount': '0.1',
                    'maximum_amount': '1000',
                    'index_price': '36717.0',
                    'mark_price': '36733.0',
                    'amount_step': '0.01',
                    'mark_price_fee_rate_cap': '0',
                    'maker_fee_rate': '0.0015',
                    'taker_fee_rate': '0.0015',
                    'base_fee': '0.1',
                    'base_currency': self.base_asset,
                    'quote_currency': self.quote_asset,
                    'option_details': None,
                    "perp_details": {
                        "index": "BTC-USDC",
                        "max_rate_per_hour": "0.004",
                        "min_rate_per_hour": "-0.004",
                        "static_interest_rate": "0.0000125",
                        "aggregate_funding": "738.587599416709606114",
                        "funding_rate": "0.00001793"
                    },
                    'erc20_details': None,
                    'base_asset_address': '0xE201fCEfD4852f96810C069f66560dc25B2C7A55', 'base_asset_sub_id': '0', 'pro_rata_fraction': '0', 'fifo_min_allocation': '0', 'pro_rata_amount_step': '1'}
                }

    def get_trading_rule_rest_msg(self):
        return [
            {
                'instrument_type': 'perp',
                'instrument_name': f'{self.base_asset}-PERP',
                'scheduled_activation': 1728508925,
                'scheduled_deactivation': 9223372036854775807,
                'is_active': True,
                'tick_size': '0.01',
                'minimum_amount': '0.1',
                'maximum_amount': '1000',
                'amount_step': '0.01',
                'mark_price_fee_rate_cap': '0',
                'maker_fee_rate': '0.0015',
                'taker_fee_rate': '0.0015',
                'base_fee': '0.1',
                'base_currency': self.base_asset,
                'quote_currency': self.quote_asset,
                'option_details': None,
                "perp_details": {
                    "index": "BTC-USD",
                    "max_rate_per_hour": "0.004",
                    "min_rate_per_hour": "-0.004",
                    "static_interest_rate": "0.0000125",
                    "aggregate_funding": "738.587599416709606114",
                    "funding_rate": "-0.000033660522457857"
                },
                'erc20_details': None,
                'base_asset_address': '0xE201fCEfD4852f96810C069f66560dc25B2C7A55', 'base_asset_sub_id': '0', 'pro_rata_fraction': '0', 'fifo_min_allocation': '0', 'pro_rata_amount_step': '1'}
        ]

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_subscriptions_subscribes_to_trades_diffs_and_orderbooks(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        result_subscribe_diffs = self.get_ws_snapshot_msg()

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_diffs),
        )
        self.listening_task = self.local_event_loop.create_task(self.data_source.listen_for_subscriptions())

        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_subscription_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value
        )
        self.assertEqual(1, len(sent_subscription_messages))
        expected_subscription_channel = "subscribe"
        expected_subscription_payload = {"channels": [f"trades.{self.ex_trading_pair.upper()}", f"orderbook.{self.ex_trading_pair.upper()}.1.100"]}
        self.assertEqual(expected_subscription_channel, sent_subscription_messages[0]["method"])
        self.assertEqual(expected_subscription_payload, sent_subscription_messages[0]["params"])

        self.assertTrue(
            self._is_logged("INFO", "Subscribed to public order book, trade channels...")
        )

    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    @patch("aiohttp.ClientSession.ws_connect")
    async def test_listen_for_subscriptions_raises_cancel_exception(self, mock_ws, _: AsyncMock):
        mock_ws.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_subscriptions()

    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_subscriptions_logs_exception_details(self, mock_ws, sleep_mock):
        mock_ws.side_effect = Exception("TEST ERROR.")
        sleep_mock.side_effect = lambda _: self._create_exception_and_unlock_test_with_event(asyncio.CancelledError())

        self.listening_task = self.local_event_loop.create_task(self.data_source.listen_for_subscriptions())

        await self.resume_test_event.wait()

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error occurred when listening to order book streams. Retrying in 5 seconds..."
            )
        )

    async def test_subscribe_to_channels_raises_cancel_exception(self):
        await self._simulate_trading_rules_initialized()
        mock_ws = MagicMock()
        mock_ws.send.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source._subscribe_channels(mock_ws)

    async def test_subscribe_to_channels_raises_exception_and_logs_error(self):
        mock_ws = MagicMock()
        mock_ws.send.side_effect = Exception("Test Error")

        with self.assertRaises(Exception):
            await self.data_source._subscribe_channels(mock_ws)

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error occurred subscribing to order book data streams.")
        )

    async def test_listen_for_trades_cancelled_when_listening(self):
        mock_queue = MagicMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.data_source._message_queue[self.data_source._trade_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_trades(self.local_event_loop, msg_queue)

    async def test_listen_for_trades_logs_exception(self):
        incomplete_resp = {
            "error": 0,
            "message": "",
            "data": [
                {
                    "created_at": 1642994704633,
                    "trade_id": 1005483402,
                    "instrument_id": "BTC-USDC",
                    "qty": "1.00000000",
                    "side": "sell",
                    "sigma": "0.00000000",
                    "index_price": "2447.79750000",
                    "underlying_price": "0.00000000",
                    "is_block_trade": False
                },
                {
                    "created_at": 1642994704241,
                    "trade_id": 1005483400,
                    "instrument_id": "BTC-USDC",
                    "qty": "1.00000000",
                    "side": "sell",
                    "sigma": "0.00000000",
                    "index_price": "2447.79750000",
                    "underlying_price": "0.00000000",
                    "is_block_trade": False
                }
            ]
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [incomplete_resp, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._trade_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        try:
            await self.data_source.listen_for_trades(self.local_event_loop, msg_queue)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error when processing public trade updates from exchange"))

    async def test_listen_for_trades_successful(self):
        await self._simulate_trading_rules_initialized()

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [self._trade_update_event(), asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._trade_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_trades(self.local_event_loop, msg_queue))

        msg: OrderBookMessage = await (msg_queue.get())

        self.assertEqual("5f249af2-2a84-47b2-946e-2552f886f0a8", msg.trade_id)

    @aioresponses()
    async def test_get_funding_info(self, mock_api):
        endpoint = CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL
        url = web_utils.public_rest_url(endpoint)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        resp = self.get_funding_info_rest_msg()
        mock_api.post(regex_url, body=json.dumps(resp))

        funding_info: FundingInfo = await self.data_source.get_funding_info(self.trading_pair)
        msg_result = resp

        self.assertEqual(self.trading_pair, funding_info.trading_pair)
        self.assertEqual(Decimal(str(msg_result["result"]["perp_details"]["funding_rate"])), funding_info.rate)

    async def _simulate_trading_rules_initialized(self):
        mocked_response = self.get_trading_rule_rest_msg()
        self.connector._initialize_trading_pair_symbols_from_exchange_info(mocked_response)
        self.connector._instrument_ticker = mocked_response
        min_order_size = mocked_response[0]["minimum_amount"]
        min_price_increment = mocked_response[0]["tick_size"]
        min_base_amount_increment = mocked_response[0]["amount_step"]
        self.connector._trading_rules = {
            self.trading_pair: TradingRule(
                trading_pair=self.trading_pair,
                min_order_size=Decimal(str(min_order_size)),
                min_price_increment=Decimal(str(min_price_increment)),
                min_base_amount_increment=Decimal(str(min_base_amount_increment)),
            )
        }

    @aioresponses()
    @patch.object(DerivePerpetualAPIOrderBookDataSource, "_sleep")
    async def test_listen_for_funding_info_cancelled_error_raised(self, mock_api, sleep_mock):
        sleep_mock.side_effect = [asyncio.CancelledError()]
        endpoint = CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL
        url = web_utils.public_rest_url(endpoint)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = self.get_funding_info_rest_msg()
        mock_api.post(regex_url, body=json.dumps(resp))

        mock_queue: asyncio.Queue = asyncio.Queue()
        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_funding_info(mock_queue)

        self.assertEqual(1, mock_queue.qsize())

    @aioresponses()
    async def test_listen_for_funding_info_logs_exception(self, mock_api):
        endpoint = CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL
        url = web_utils.public_rest_url(endpoint)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        resp = self.get_funding_info_rest_msg()
        resp["error"] = ""
        mock_api.post(regex_url, body=json.dumps(resp), callback=self.resume_test_callback)

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.local_event_loop.create_task(self.data_source.listen_for_funding_info(msg_queue))

        await self.resume_test_event.wait()

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error when processing public funding info updates from exchange"))

    @patch(
        "hummingbot.connector.derivative.derive_perpetual.derive_perpetual_api_order_book_data_source."
        "DerivePerpetualAPIOrderBookDataSource._next_funding_time")
    @aioresponses()
    async def test_listen_for_funding_info_successful(self, next_funding_time_mock, mock_api):
        next_funding_time_mock.return_value = 1713272400
        endpoint = CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL
        url = web_utils.public_rest_url(endpoint)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        resp = self.get_funding_info_rest_msg()
        mock_api.post(regex_url, body=json.dumps(resp))

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.local_event_loop.create_task(self.data_source.listen_for_funding_info(msg_queue))

        msg: FundingInfoUpdate = await msg_queue.get()

        self.assertEqual(self.trading_pair, msg.trading_pair)
        expected_index_price = Decimal('36717.0')
        self.assertEqual(expected_index_price, msg.index_price)
        expected_mark_price = Decimal('36733.0')
        self.assertEqual(expected_mark_price, msg.mark_price)
        expected_funding_time = next_funding_time_mock.return_value
        self.assertEqual(expected_funding_time, msg.next_funding_utc_timestamp)
        expected_rate = Decimal('0.00001793')
        self.assertEqual(expected_rate, msg.rate)
