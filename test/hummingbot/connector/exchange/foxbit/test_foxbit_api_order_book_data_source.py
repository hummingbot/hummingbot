import asyncio
import json
import re
import unittest
from typing import Awaitable
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses.core import aioresponses
from bidict import bidict

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.foxbit import foxbit_constants as CONSTANTS, foxbit_web_utils as web_utils
from hummingbot.connector.exchange.foxbit.foxbit_api_order_book_data_source import FoxbitAPIOrderBookDataSource
from hummingbot.connector.exchange.foxbit.foxbit_exchange import FoxbitExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage


class FoxbitAPIOrderBookDataSourceUnitTests(unittest.TestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.domain = CONSTANTS.DEFAULT_DOMAIN

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task = None
        self.mocking_assistant = NetworkMockingAssistant()

        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.connector = FoxbitExchange(
            client_config_map=client_config_map,
            foxbit_api_key="",
            foxbit_api_secret="",
            foxbit_user_id="",
            trading_pairs=[],
            trading_required=False,
            domain=self.domain)
        self.data_source = FoxbitAPIOrderBookDataSource(trading_pairs=[self.trading_pair],
                                                        connector=self.connector,
                                                        api_factory=self.connector._web_assistants_factory,
                                                        domain=self.domain)
        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)
        self.data_source._live_stream_connected[1] = True
        self.resume_test_event = asyncio.Event()

        self.connector._set_trading_pair_symbol_map(bidict({self.ex_trading_pair: self.trading_pair}))
        self.connector._set_trading_pair_instrument_id_map(bidict({1: self.ex_trading_pair}))

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
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
        resp = {
            "result": None,
            "id": 1
        }
        return resp

    def _trade_update_event(self):
        return {'m': 3, 'i': 10, 'n': 'TradeDataUpdateEvent', 'o': '[[194,1,"0.1","8432.0",787704,792085,1661952966311,0,0,false,0]]'}

    def _order_diff_event(self):
        return {'m': 3, 'i': 8, 'n': 'Level2UpdateEvent', 'o': '[[187,0,1661952966257,1,8432,0,8432,1,7.6,1]]'}

    def _snapshot_response(self):
        resp = {
            "sequence_id": 1,
            "asks": [
                [
                    "145901.0",
                    "8.65827849"
                ],
                [
                    "145902.0",
                    "10.0"
                ],
                [
                    "145903.0",
                    "10.0"
                ]
            ],
            "bids": [
                [
                    "145899.0",
                    "2.33928943"
                ],
                [
                    "145898.0",
                    "9.96927011"
                ],
                [
                    "145897.0",
                    "10.0"
                ],
                [
                    "145896.0",
                    "10.0"
                ]
            ]
        }
        return resp

    def _level_1_response(self):
        return [
            {
                "OMSId": 1,
                "InstrumentId": 4,
                "MarketId": "ethbrl",
                "BestBid": 112824.303,
                "BestOffer": 113339.6599,
                "LastTradedPx": 112794.1036,
                "LastTradedQty": 0.00443286,
                "LastTradeTime": 1658841244,
                "SessionOpen": 119437.9079,
                "SessionHigh": 115329.8396,
                "SessionLow": 112697.42,
                "SessionClose": 113410.0483,
                "Volume": 0.00443286,
                "CurrentDayVolume": 91.4129,
                "CurrentDayNumTrades": 1269,
                "CurrentDayPxChange": -1764.6783,
                "Rolling24HrVolume": 103.5911,
                "Rolling24NumTrades": 3354,
                "Rolling24HrPxChange": -5.0469,
                "TimeStamp": 1658841286
            }
        ]

    @patch("hummingbot.connector.exchange.foxbit.foxbit_api_order_book_data_source.FoxbitAPIOrderBookDataSource._ORDER_BOOK_INTERVAL", 0.0)
    @aioresponses()
    def test_get_new_order_book_successful(self, mock_api):
        url = web_utils.public_rest_url(path_url=CONSTANTS.SNAPSHOT_PATH_URL.format(self.trading_pair), domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, body=json.dumps(self._snapshot_response()))

        order_book: OrderBook = self.async_run_with_timeout(
            coroutine=self.data_source.get_new_order_book(self.trading_pair),
            timeout=2000
        )

        expected_update_id = order_book.snapshot_uid

        self.assertEqual(expected_update_id, order_book.snapshot_uid)
        bids = list(order_book.bid_entries())
        asks = list(order_book.ask_entries())
        self.assertEqual(4, len(bids))
        self.assertEqual(145899, bids[0].price)
        self.assertEqual(2.33928943, bids[0].amount)
        self.assertEqual(3, len(asks))
        self.assertEqual(145901, asks[0].price)
        self.assertEqual(8.65827849, asks[0].amount)

    @patch("hummingbot.connector.exchange.foxbit.foxbit_api_order_book_data_source.FoxbitAPIOrderBookDataSource._ORDER_BOOK_INTERVAL", 0.0)
    @aioresponses()
    def test_get_new_order_book_raises_exception(self, mock_api):
        url = web_utils.public_rest_url(path_url=CONSTANTS.SNAPSHOT_PATH_URL.format(self.trading_pair), domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, status=400)
        with self.assertRaises(IOError):
            self.async_run_with_timeout(
                coroutine=self.data_source.get_new_order_book(self.trading_pair),
                timeout=2000
            )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_subscribes_to_trades_and_order_diffs(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ixm_config = {
            'm': 0,
            'i': 1,
            'n': 'GetInstruments',
            'o': '[{"OMSId":1,"InstrumentId":1,"Symbol":"COINALPHA/HBOT","Product1":1,"Product1Symbol":"COINALPHA","Product2":2,"Product2Symbol":"HBOT","InstrumentType":"Standard","VenueInstrumentId":1,"VenueId":1,"SortIndex":0,"SessionStatus":"Running","PreviousSessionStatus":"Paused","SessionStatusDateTime":"2020-07-11T01:27:02.851Z","SelfTradePrevention":true,"QuantityIncrement":1e-8,"PriceIncrement":0.01,"MinimumQuantity":1e-8,"MinimumPrice":0.01,"VenueSymbol":"BTC/BRL","IsDisable":false,"MasterDataId":0,"PriceCollarThreshold":0,"PriceCollarPercent":0,"PriceCollarEnabled":false,"PriceFloorLimit":0,"PriceFloorLimitEnabled":false,"PriceCeilingLimit":0,"PriceCeilingLimitEnabled":false,"CreateWithMarketRunning":true,"AllowOnlyMarketMakerCounterParty":false}]'
        }
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(ixm_config))

        ixm_response = {
            'm': 0,
            'i': 1,
            'n':
            'SubscribeLevel1',
            'o': '{"OMSId":1,"InstrumentId":1,"MarketId":"coinalphahbot","BestBid":145899,"BestOffer":145901,"LastTradedPx":145899,"LastTradedQty":0.0009,"LastTradeTime":1662663925,"SessionOpen":145899,"SessionHigh":145901,"SessionLow":145899,"SessionClose":145901,"Volume":0.0009,"CurrentDayVolume":0.008,"CurrentDayNumTrades":17,"CurrentDayPxChange":2,"Rolling24HrVolume":0.008,"Rolling24NumTrades":17,"Rolling24HrPxChange":0.0014,"TimeStamp":1662736972}'
        }
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(ixm_response))

        result_subscribe_trades = {
            "result": None,
            "id": 1
        }
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_trades))

        result_subscribe_diffs = {
            'm': 0,
            'i': 2,
            'n': 'SubscribeLevel2',
            'o': '[[1,0,1667228256347,0,8454,0,8435.1564,1,0.001,0],[2,0,1667228256347,0,8454,0,8418,1,13.61149632,0],[3,0,1667228256347,0,8454,0,8417,1,10,0],[4,0,1667228256347,0,8454,0,8416,1,10,0],[5,0,1667228256347,0,8454,0,8415,1,10,0],[6,0,1667228256347,0,8454,0,8454,1,6.44410902,1],[7,0,1667228256347,0,8454,0,8455,1,10,1],[8,0,1667228256347,0,8454,0,8456,1,10,1],[9,0,1667228256347,0,8454,0,8457,1,10,1],[10,0,1667228256347,0,8454,0,8458,1,10,1]]'
        }
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_diffs))

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_subscription_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value)

        self.assertEqual(2, len(sent_subscription_messages))
        expected_trade_subscription = {
            'Content-Type': 'application/json',
            'User-Agent': 'HBOT',
            'm': 0,
            'i': 2,
            'n': 'GetInstruments',
            'o': '{"OMSId": 1, "InstrumentId": 1, "Depth": 10}'
        }
        self.assertEqual(expected_trade_subscription['o'], sent_subscription_messages[0]['o'])

        expected_diff_subscription = {
            'Content-Type': 'application/json',
            'User-Agent': 'HBOT',
            'm': 0,
            'i': 2,
            'n': 'SubscribeLevel2',
            'o': '{"InstrumentId": 1}'
        }
        self.assertEqual(expected_diff_subscription['o'], sent_subscription_messages[1]['o'])

        self.assertTrue(self._is_logged(
            "INFO",
            "Subscribed to public order book channel..."
        ))

    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_raises_cancel_exception(self, ws_connect_mock, _: AsyncMock):
        ws_connect_mock.side_effect = asyncio.CancelledError

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

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_subscribe_channels_raises_cancel_exception(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ixm_config = {
            'm': 0,
            'i': 1,
            'n': 'GetInstruments',
            'o': '[{"OMSId":1,"InstrumentId":1,"Symbol":"COINALPHA/HBOT","Product1":1,"Product1Symbol":"COINALPHA","Product2":2,"Product2Symbol":"HBOT","InstrumentType":"Standard","VenueInstrumentId":1,"VenueId":1,"SortIndex":0,"SessionStatus":"Running","PreviousSessionStatus":"Paused","SessionStatusDateTime":"2020-07-11T01:27:02.851Z","SelfTradePrevention":true,"QuantityIncrement":1e-8,"PriceIncrement":0.01,"MinimumQuantity":1e-8,"MinimumPrice":0.01,"VenueSymbol":"BTC/BRL","IsDisable":false,"MasterDataId":0,"PriceCollarThreshold":0,"PriceCollarPercent":0,"PriceCollarEnabled":false,"PriceFloorLimit":0,"PriceFloorLimitEnabled":false,"PriceCeilingLimit":0,"PriceCeilingLimitEnabled":false,"CreateWithMarketRunning":true,"AllowOnlyMarketMakerCounterParty":false}]'
        }
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(ixm_config))

        ixm_response = {
            'm': 0,
            'i': 1,
            'n':
            'SubscribeLevel1',
            'o': '{"OMSId":1,"InstrumentId":1,"MarketId":"coinalphahbot","BestBid":145899,"BestOffer":145901,"LastTradedPx":145899,"LastTradedQty":0.0009,"LastTradeTime":1662663925,"SessionOpen":145899,"SessionHigh":145901,"SessionLow":145899,"SessionClose":145901,"Volume":0.0009,"CurrentDayVolume":0.008,"CurrentDayNumTrades":17,"CurrentDayPxChange":2,"Rolling24HrVolume":0.008,"Rolling24NumTrades":17,"Rolling24HrPxChange":0.0014,"TimeStamp":1662736972}'
        }
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(ixm_response))

        mock_ws = MagicMock()
        mock_ws.send.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(self.data_source._subscribe_channels(mock_ws))
            self.async_run_with_timeout(self.listening_task)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_subscribe_channels_raises_exception_and_logs_error(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ixm_config = {
            'm': 0,
            'i': 1,
            'n': 'GetInstruments',
            'o': '[{"OMSId":1,"InstrumentId":1,"Symbol":"COINALPHA/HBOT","Product1":1,"Product1Symbol":"COINALPHA","Product2":2,"Product2Symbol":"HBOT","InstrumentType":"Standard","VenueInstrumentId":1,"VenueId":1,"SortIndex":0,"SessionStatus":"Running","PreviousSessionStatus":"Paused","SessionStatusDateTime":"2020-07-11T01:27:02.851Z","SelfTradePrevention":true,"QuantityIncrement":1e-8,"PriceIncrement":0.01,"MinimumQuantity":1e-8,"MinimumPrice":0.01,"VenueSymbol":"BTC/BRL","IsDisable":false,"MasterDataId":0,"PriceCollarThreshold":0,"PriceCollarPercent":0,"PriceCollarEnabled":false,"PriceFloorLimit":0,"PriceFloorLimitEnabled":false,"PriceCeilingLimit":0,"PriceCeilingLimitEnabled":false,"CreateWithMarketRunning":true,"AllowOnlyMarketMakerCounterParty":false}]'
        }
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(ixm_config))

        ixm_response = {
            'm': 0,
            'i': 1,
            'n':
            'SubscribeLevel1',
            'o': '{"OMSId":1,"InstrumentId":1,"MarketId":"coinalphahbot","BestBid":145899,"BestOffer":145901,"LastTradedPx":145899,"LastTradedQty":0.0009,"LastTradeTime":1662663925,"SessionOpen":145899,"SessionHigh":145901,"SessionLow":145899,"SessionClose":145901,"Volume":0.0009,"CurrentDayVolume":0.008,"CurrentDayNumTrades":17,"CurrentDayPxChange":2,"Rolling24HrVolume":0.008,"Rolling24NumTrades":17,"Rolling24HrPxChange":0.0014,"TimeStamp":1662736972}'
        }
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(ixm_response))

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
        self.data_source._message_queue["trade"] = mock_queue

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
        self.data_source._message_queue["trade"] = mock_queue

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

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_trades_successful(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ixm_config = {
            'm': 0,
            'i': 1,
            'n': 'GetInstruments',
            'o': '[{"OMSId":1,"InstrumentId":1,"Symbol":"COINALPHA/HBOT","Product1":1,"Product1Symbol":"COINALPHA","Product2":2,"Product2Symbol":"HBOT","InstrumentType":"Standard","VenueInstrumentId":1,"VenueId":1,"SortIndex":0,"SessionStatus":"Running","PreviousSessionStatus":"Paused","SessionStatusDateTime":"2020-07-11T01:27:02.851Z","SelfTradePrevention":true,"QuantityIncrement":1e-8,"PriceIncrement":0.01,"MinimumQuantity":1e-8,"MinimumPrice":0.01,"VenueSymbol":"BTC/BRL","IsDisable":false,"MasterDataId":0,"PriceCollarThreshold":0,"PriceCollarPercent":0,"PriceCollarEnabled":false,"PriceFloorLimit":0,"PriceFloorLimitEnabled":false,"PriceCeilingLimit":0,"PriceCeilingLimitEnabled":false,"CreateWithMarketRunning":true,"AllowOnlyMarketMakerCounterParty":false}]'
        }
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(ixm_config))

        ixm_response = {
            'm': 0,
            'i': 1,
            'n':
            'SubscribeLevel1',
            'o': '{"OMSId":1,"InstrumentId":1,"MarketId":"coinalphahbot","BestBid":145899,"BestOffer":145901,"LastTradedPx":145899,"LastTradedQty":0.0009,"LastTradeTime":1662663925,"SessionOpen":145899,"SessionHigh":145901,"SessionLow":145899,"SessionClose":145901,"Volume":0.0009,"CurrentDayVolume":0.008,"CurrentDayNumTrades":17,"CurrentDayPxChange":2,"Rolling24HrVolume":0.008,"Rolling24NumTrades":17,"Rolling24HrPxChange":0.0014,"TimeStamp":1662736972}'
        }
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(ixm_response))

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [self._trade_update_event(), asyncio.CancelledError()]
        self.data_source._message_queue["trade"] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_trades(self.ev_loop, msg_queue))

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(194, msg.trade_id)

    def test_listen_for_order_book_diffs_cancelled(self):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.data_source._message_queue["order_book_diff"] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue)
            )
            self.async_run_with_timeout(self.listening_task)

    def test_listen_for_order_book_diffs_logs_exception(self):
        incomplete_resp = {
            "m": 1,
            "i": 2,
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [incomplete_resp, asyncio.CancelledError()]
        self.data_source._message_queue["order_book_diff"] = mock_queue

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

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_order_book_diffs_successful(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ixm_config = {
            'm': 0,
            'i': 1,
            'n': 'GetInstruments',
            'o': '[{"OMSId":1,"InstrumentId":1,"Symbol":"COINALPHA/HBOT","Product1":1,"Product1Symbol":"COINALPHA","Product2":2,"Product2Symbol":"HBOT","InstrumentType":"Standard","VenueInstrumentId":1,"VenueId":1,"SortIndex":0,"SessionStatus":"Running","PreviousSessionStatus":"Paused","SessionStatusDateTime":"2020-07-11T01:27:02.851Z","SelfTradePrevention":true,"QuantityIncrement":1e-8,"PriceIncrement":0.01,"MinimumQuantity":1e-8,"MinimumPrice":0.01,"VenueSymbol":"BTC/BRL","IsDisable":false,"MasterDataId":0,"PriceCollarThreshold":0,"PriceCollarPercent":0,"PriceCollarEnabled":false,"PriceFloorLimit":0,"PriceFloorLimitEnabled":false,"PriceCeilingLimit":0,"PriceCeilingLimitEnabled":false,"CreateWithMarketRunning":true,"AllowOnlyMarketMakerCounterParty":false}]'
        }
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(ixm_config))

        ixm_response = {
            'm': 0,
            'i': 1,
            'n':
            'SubscribeLevel1',
            'o': '{"OMSId":1,"InstrumentId":1,"MarketId":"coinalphahbot","BestBid":145899,"BestOffer":145901,"LastTradedPx":145899,"LastTradedQty":0.0009,"LastTradeTime":1662663925,"SessionOpen":145899,"SessionHigh":145901,"SessionLow":145899,"SessionClose":145901,"Volume":0.0009,"CurrentDayVolume":0.008,"CurrentDayNumTrades":17,"CurrentDayPxChange":2,"Rolling24HrVolume":0.008,"Rolling24NumTrades":17,"Rolling24HrPxChange":0.0014,"TimeStamp":1662736972}'
        }
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(ixm_response))

        mock_queue = AsyncMock()
        diff_event = self._order_diff_event()
        mock_queue.get.side_effect = [diff_event, asyncio.CancelledError()]
        self.data_source._message_queue["order_book_diff"] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue))

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        expected_id = eval(diff_event["o"])[0][0]
        self.assertEqual(expected_id, msg.update_id)
