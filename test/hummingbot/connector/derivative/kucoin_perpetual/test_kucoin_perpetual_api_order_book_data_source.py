import asyncio
import json
import logging
import os
import re
from decimal import Decimal
from typing import Awaitable, Dict
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses import aioresponses
from bidict import bidict

import hummingbot.connector.derivative.kucoin_perpetual.kucoin_perpetual_web_utils as web_utils
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.derivative.kucoin_perpetual import kucoin_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.kucoin_perpetual.kucoin_perpetual_api_order_book_data_source import (
    KucoinPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.kucoin_perpetual.kucoin_perpetual_derivative import KucoinPerpetualDerivative
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.funding_info import FundingInfo
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType

os.environ['PYTHONASYNCIODEBUG'] = '1'


class KucoinPerpetualAPIOrderBookDataSourceTests(TestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "HBOT"
        cls.quote_asset = "PERP"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}-{cls.quote_asset}"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task = None
        self.mocking_assistant = NetworkMockingAssistant()
        self.mock_time_provider = MagicMock()
        self.mock_time_provider.time.return_value = 1000

        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.connector = KucoinPerpetualDerivative(
            client_config_map,
            kucoin_perpetual_api_key="",
            kucoin_perpetual_secret_key="",
            kucoin_perpetual_passphrase="",
            trading_pairs=[self.trading_pair],
            trading_required=False,
        )
        self.data_source = KucoinPerpetualAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory,
        )
        self._original_full_order_book_reset_time = self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = -1

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.connector._set_trading_pair_symbol_map(
            bidict({self.ex_trading_pair: self.trading_pair}))

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = self._original_full_order_book_reset_time
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def get_rest_snapshot_msg(self) -> Dict:
        return {
            "code": "200000",
            "data": {
                "symbol": "XBTUSDM",
                "sequence": 100,
                "asks": [
                    ["5000.0", 1000],
                    ["6000.0", 1983]
                ],
                "bids": [
                    ["3200.0", 800],
                    ["3100.0", 100]
                ],
                "ts": 1604643655040584408
            }
        }

    @aioresponses()
    def test_get_new_order_book_successful(self, mock_api):
        self._simulate_trading_rules_initialized()
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=CONSTANTS.ORDER_BOOK_ENDPOINT.format(symbol=self.trading_pair)
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        resp = {
            "code": "200000",
            "data": {
                "asks": [
                    [
                        4114.25,
                        6.263
                    ]
                ],
                "bids": [
                    [
                        4112.25,
                        49.29
                    ]
                ]
            }
        }

        mock_api.get(regex_url, body=json.dumps(resp))

        order_book: OrderBook = self.async_run_with_timeout(
            self.data_source.get_new_order_book(self.trading_pair)
        )

        bids = list(order_book.bid_entries())
        asks = list(order_book.ask_entries())
        self.assertEqual(1, len(bids))
        self.assertEqual(4112.25, bids[0].price)
        self.assertEqual(49.29 * 0.000001, bids[0].amount)
        self.assertEqual(1, len(asks))
        self.assertEqual(4114.25, asks[0].price)
        self.assertEqual(6.263 * 0.000001, asks[0].amount)

    @aioresponses()
    def test_get_new_order_book_raises_exception(self, mock_api):
        url = web_utils.get_rest_url_for_endpoint(endpoint=CONSTANTS.ORDER_BOOK_ENDPOINT.format(symbol=self.trading_pair))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, status=400)
        with self.assertRaises(IOError):
            self.async_run_with_timeout(
                self.data_source.get_new_order_book(self.trading_pair)
            )

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.derivative.kucoin_perpetual.kucoin_perpetual_web_utils.next_message_id")
    def test_listen_for_subscriptions_subscribes_to_trades_order_diffs_and_instruments(self, mock_api, id_mock, mock_ws):
        id_mock.side_effect = [1, 2, 3]
        url = web_utils.get_rest_url_for_endpoint(endpoint=CONSTANTS.PUBLIC_WS_DATA_PATH_URL)

        resp = {
            "code": "200000",
            "data": {
                "instanceServers": [
                    {
                        "endpoint": "wss://test.url/endpoint",
                        "protocol": "websocket",
                        "encrypt": True,
                        "pingInterval": 50000,
                        "pingTimeout": 10000
                    }
                ],
                "token": "testToken"
            }
        }
        mock_api.post(url, body=json.dumps(resp))

        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()

        result_subscribe_trades = {
            "type": "ack",
            "id": 1
        }
        result_subscribe_diffs = {
            "type": "ack",
            "id": 2
        }
        result_subscribe_instruments = {
            "type": "ack",
            "id": 3
        }

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(result_subscribe_trades))
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(result_subscribe_diffs))
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=mock_ws.return_value,
            message=json.dumps(result_subscribe_instruments))

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        sent_subscription_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=mock_ws.return_value)

        self.assertEqual(3, len(sent_subscription_messages))
        expected_trade_subscription = {
            "id": 1,
            "type": "subscribe",
            "topic": f"/contractMarket/ticker:{self.trading_pair}",
            "privateChannel": False,
            "response": False
        }
        self.assertEqual(expected_trade_subscription, sent_subscription_messages[0])
        expected_diff_subscription = {
            "id": 2,
            "type": "subscribe",
            "topic": f"/contractMarket/level2:{self.trading_pair}",
            "privateChannel": False,
            "response": False
        }
        self.assertEqual(expected_diff_subscription, sent_subscription_messages[1])

        self.assertTrue(self._is_logged(
            "INFO",
            "Subscribed to public order book, trade and funding info channels..."
        ))

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    def test_listen_for_subscriptions_logs_exception_details(self, mock_api, _, ws_connect_mock):
        url = web_utils.get_rest_url_for_endpoint(endpoint=CONSTANTS.PUBLIC_WS_DATA_PATH_URL)

        resp = {
            "code": "200000",
            "data": {
                "instanceServers": [
                    {
                        "endpoint": "wss://test.url/endpoint",
                        "protocol": "websocket",
                        "encrypt": True,
                        "pingInterval": 50000,
                        "pingTimeout": 10000
                    }
                ],
                "token": "testToken"
            }
        }
        mock_api.post(url, body=json.dumps(resp))

        ws_connect_mock.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())
            self.async_run_with_timeout(self.listening_task)

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    def test_listen_for_subscriptions_raises_cancel_exception(self, mock_api, _, ws_connect_mock):
        url = web_utils.get_rest_url_for_endpoint(endpoint=CONSTANTS.PUBLIC_WS_DATA_PATH_URL)

        resp = {
            "code": "200000",
            "data": {
                "instanceServers": [
                    {
                        "endpoint": "wss://test.url/endpoint",
                        "protocol": "websocket",
                        "encrypt": True,
                        "pingInterval": 50000,
                        "pingTimeout": 10000
                    }
                ],
                "token": "testToken"
            }
        }
        mock_api.post(url, body=json.dumps(resp))

        ws_connect_mock.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())
            self.async_run_with_timeout(self.listening_task)

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
            "channel": CONSTANTS.WS_TRADES_TOPIC,
            "market": self.ex_trading_pair,
            "type": "update",
            "data": [
                {
                    "price": 10000,
                }
            ]
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
        trade_event = {
            "type": "message",
            "topic": f"/market/match:{self.trading_pair}",
            "subject": "trade.l3match",
            "data": {
                "sequence": "1545896669145",
                "type": "match",
                "symbol": self.trading_pair,
                "side": "buy",
                "price": "0.08200000000000000000",
                "size": "0.01022222000000000000",
                "tradeId": "5c24c5da03aa673885cd67aa",
                "takerOrderId": "5c24c5d903aa6772d55b371e",
                "makerOrderId": "5c2187d003aa677bd09d5c93",
                "time": "1545913818099033203"
            }
        }

        mock_queue.get.side_effect = [trade_event, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._trade_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_trades(self.ev_loop, msg_queue))

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(OrderBookMessageType.TRADE, msg.type)
        self.assertTrue(trade_event["data"]["tradeId"], msg.trade_id)

    def test_listen_for_order_book_diffs_cancelled(self):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.data_source._message_queue[self.data_source._diff_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue)
            )
            self.async_run_with_timeout(self.listening_task)

    def test_listen_for_order_book_diffs_logs_exception(self):
        incomplete_resp = {
            "type": "message",
            "topic": f"/contractMarket/level2:{self.trading_pair}",
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [incomplete_resp, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._diff_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue)
        )

        try:
            self.async_run_with_timeout(self.listening_task)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error when processing public order book updates from exchange"))

    def test_listen_for_order_book_diffs_successful(self):
        self._simulate_trading_rules_initialized()
        mock_queue = AsyncMock()
        diff_event = {
            "subject": "level2",
            "topic": f"/contractMarket/level2:{self.trading_pair}",
            "type": "message",
            "data": {
                "sequence": 18,
                "change": "5000.0,sell,83",
                "timestamp": 1551770400000,
            }
        }

        mock_queue.get.side_effect = [diff_event, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._diff_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue))

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(OrderBookMessageType.DIFF, msg.type)
        self.assertEqual(-1, msg.trade_id)
        self.assertEqual(diff_event["data"]["timestamp"] * 1e-3, msg.timestamp)
        expected_update_id = 18
        self.assertEqual(expected_update_id, msg.update_id)

        bids = msg.bids
        asks = msg.asks
        self.assertEqual(0, len(bids))
        self.assertEqual(1, len(asks))
        self.assertEqual(5000.0, asks[0].price)
        self.assertEqual(83 * 0.000001, asks[0].amount)
        self.assertEqual(expected_update_id, asks[0].update_id)

    @aioresponses()
    def test_listen_for_order_book_snapshots_cancelled_when_fetching_snapshot(self, mock_api):
        endpoint = CONSTANTS.ORDER_BOOK_ENDPOINT.format(symbol=self.trading_pair)
        url = web_utils.get_rest_url_for_endpoint(
            endpoint=endpoint
        )
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, exception=asyncio.CancelledError)

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(
                self.data_source.listen_for_order_book_snapshots(self.ev_loop, asyncio.Queue())
            )

    @aioresponses()
    @patch("hummingbot.connector.derivative.kucoin_perpetual.kucoin_perpetual_api_order_book_data_source"
           ".KucoinPerpetualAPIOrderBookDataSource._sleep")
    def test_listen_for_order_book_snapshots_log_exception(self, mock_api, sleep_mock):
        msg_queue: asyncio.Queue = asyncio.Queue()
        sleep_mock.side_effect = asyncio.CancelledError

        url = web_utils.get_rest_url_for_endpoint(endpoint=CONSTANTS.ORDER_BOOK_ENDPOINT)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, exception=Exception)

        try:
            self.async_run_with_timeout(self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue))
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged("ERROR", f"Unexpected error fetching order book snapshot for {self.trading_pair}."))

    @aioresponses()
    def test_listen_for_order_book_snapshots_successful(self, mock_api):
        self._simulate_trading_rules_initialized()
        logging.getLogger("asyncio").setLevel(logging.WARNING)
        msg_queue: asyncio.Queue = asyncio.Queue()
        url = web_utils.get_rest_url_for_endpoint(endpoint=CONSTANTS.ORDER_BOOK_ENDPOINT.format(symbol=self.trading_pair))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        snapshot_data = {
            "code": "200000",
            "data": {
                "sequence": "3262786978",
                "time": 1550653727731,
                "bids": [["6500.12", "0.45054140"],
                         ["6500.11", "0.45054140"]],
                "asks": [["6500.16", "0.57753524"],
                         ["6500.15", "0.57753524"]]
            }
        }

        mock_api.get(regex_url, body=json.dumps(snapshot_data))

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
        )

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(int(snapshot_data["data"]["sequence"]), msg.update_id)
        self.assertEqual(OrderBookMessageType.SNAPSHOT, msg.type)
        self.assertEqual(-1, msg.trade_id)
        self.assertEqual(float(snapshot_data["data"]["time"]) * 1e-3, msg.timestamp)

        bids = msg.bids
        asks = msg.asks

        self.assertEqual(OrderBookMessageType.SNAPSHOT, msg.type)
        self.assertEqual(-1, msg.trade_id)
        self.assertEqual(int(snapshot_data["data"]["sequence"]), msg.update_id)

        bids = msg.bids
        asks = msg.asks
        self.assertEqual(2, len(bids))
        self.assertEqual(6500.12, bids[0].price)
        self.assertEqual(4.505414e-07, bids[0].amount)
        self.assertEqual(6500.11, bids[1].price)
        self.assertEqual(4.505414e-07, bids[1].amount)
        self.assertEqual(2, len(asks))
        self.assertEqual(6500.16, asks[0].price)
        self.assertEqual(5.7753524e-07, asks[0].amount)
        self.assertEqual(6500.15, asks[1].price)
        self.assertEqual(5.7753524e-07, asks[1].amount)

    def test_listen_for_funding_info_cancelled_when_listening(self):
        mock_queue = MagicMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.data_source._message_queue[self.data_source._funding_info_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_funding_info(msg_queue)
            )
            self.async_run_with_timeout(self.listening_task)

    def test_listen_for_funding_info_logs_exception(self):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [Exception, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._funding_info_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_funding_info(msg_queue))

        try:
            self.async_run_with_timeout(self.listening_task)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error when processing public funding info updates from exchange"))

    def test_listen_for_funding_info_successful(self):
        # KuCoin doesn't have ws updates for funding info
        pass

    @aioresponses()
    def test_get_funding_info(self, mock_api):
        future_info_url = web_utils.get_rest_url_for_endpoint(
            endpoint = CONSTANTS.GET_CONTRACT_INFO_PATH_URL.format(symbol=self.ex_trading_pair)
        )
        future_info_regex_url = re.compile(f"^{future_info_url}".replace(".", r"\.").replace("?", r"\?"))
        future_info_response = {
            "code": "200000",
            "data": {
                "symbol": self.ex_trading_pair,
                "rootSymbol": "USDT",
                "type": "FFWCSX",
                "firstOpenDate": 1610697600000,
                "baseCurrency": "HBOT",
                "quoteCurrency": "USDT",
                "settleCurrency": "USDT",
                "maxOrderQty": 1000000,
                "maxPrice": 1000000.0,
                "lotSize": 1,
                "tickSize": 0.01,
                "indexPriceTickSize": 0.01,
                "multiplier": 0.01,
                "initialMargin": 0.05,
                "maintainMargin": 0.025,
                "maxRiskLimit": 100000,
                "minRiskLimit": 100000,
                "riskStep": 50000,
                "makerFeeRate": 0.0002,
                "takerFeeRate": 0.0006,
                "takerFixFee": 0.0,
                "makerFixFee": 0.0,
                "isDeleverage": True,
                "isQuanto": False,
                "isInverse": False,
                "markMethod": "FairPrice",
                "fairMethod": "FundingRate",
                "fundingBaseSymbol": ".HBOTINT8H",
                "fundingQuoteSymbol": ".USDTINT8H",
                "fundingRateSymbol": ".HBOTUSDTMFPI8H",
                "indexSymbol": ".KHBOTUSDT",
                "settlementSymbol": "",
                "status": "Open",
                "fundingFeeRate": 0.0001,
                "predictedFundingFeeRate": 0.0001,
                "openInterest": "2487402",
                "turnoverOf24h": 3166644.36115288,
                "volumeOf24h": 32299.4,
                "markPrice": 101.6,
                "indexPrice": 101.59,
                "lastTradePrice": 101.54,
                "nextFundingRateTime": 22646889,
                "maxLeverage": 20,
                "sourceExchanges": [
                    "huobi",
                    "Okex",
                    "Binance",
                    "Kucoin",
                    "Poloniex",
                    "Hitbtc"
                ],
                "premiumsSymbol1M": ".HBOTUSDTMPI",
                "premiumsSymbol8H": ".HBOTUSDTMPI8H",
                "fundingBaseSymbol1M": ".HBOTINT",
                "fundingQuoteSymbol1M": ".USDTINT",
                "lowPrice": 88.88,
                "highPrice": 102.21,
                "priceChgPct": 0.1401,
                "priceChg": 12.48
            }
        }
        mock_api.get(future_info_regex_url, body=json.dumps(future_info_response))

        funding_info: FundingInfo = self.async_run_with_timeout(
            self.data_source.get_funding_info(self.trading_pair)
        )

        self.assertEqual(self.trading_pair, funding_info.trading_pair)
        self.assertEqual(Decimal(str(future_info_response["data"]["indexPrice"])), funding_info.index_price)
        self.assertEqual(Decimal(str(future_info_response["data"]["markPrice"])), funding_info.mark_price)

    def _simulate_trading_rules_initialized(self):
        self.connector._trading_rules = {
            self.trading_pair: TradingRule(
                trading_pair=self.trading_pair,
                min_order_size=Decimal(str(0.01)),
                min_price_increment=Decimal(str(0.0001)),
                min_base_amount_increment=Decimal(str(0.000001)),
            )
        }
