import asyncio
import json
import re
from decimal import Decimal
from typing import Awaitable, Dict, List
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import urlencode

from aioresponses import aioresponses
from bidict import bidict

import hummingbot.connector.derivative.okx_perpetual.okx_perpetual_web_utils as web_utils
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.derivative.okx_perpetual import okx_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.okx_perpetual.okx_perpetual_api_order_book_data_source import (
    OkxPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.okx_perpetual.okx_perpetual_derivative import OkxPerpetualDerivative
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType

BASE_ASSET = "COINALPHA"
QUOTE_ASSET = "HBOT"


class OKXPerpetualAPIOrderBookDataSourceTests(TestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = BASE_ASSET
        cls.quote_asset = QUOTE_ASSET
        cls.trading_pair = f"{BASE_ASSET}-{QUOTE_ASSET}"
        cls.ex_trading_pair = f"{BASE_ASSET}-{QUOTE_ASSET}-SWAP"
        cls.domain = "okx_perpetual"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task = None
        self.mocking_assistant = NetworkMockingAssistant()

        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.connector = OkxPerpetualDerivative(
            client_config_map,
            okx_perpetual_api_key="",
            okx_perpetual_secret_key="",
            okx_perpetual_passphrase="",
            trading_pairs=[self.trading_pair],
            trading_required=False,
            domain=self.domain,
        )
        self.data_source = OkxPerpetualAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory,
            domain=self.domain,
        )

        self._original_full_order_book_reset_time = self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = -1

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.resume_test_event = asyncio.Event()

        self.connector._set_trading_pair_symbol_map(
            bidict({f"{self.base_asset}{self.quote_asset}": self.trading_pair}))

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

    @staticmethod
    def get_rest_snapshot_msg() -> Dict:
        return {
            "code": "0",
            "msg": "",
            "data": [
                {
                    "asks": [
                        ["41006.8", "0.60038921", "0", "1"]
                    ],
                    "bids": [
                        ["41006.3", "0.30178218", "0", "2"]
                    ],
                    "ts": "1629966436396",
                }
            ]
        }

    def get_ws_trade_msg(self) -> Dict:
        return {
            "arg": {
                "channel": "trades",
                "instId": self.trading_pair
            },
            "data": [
                {
                    "instId": self.trading_pair,
                    "tradeId": "130639474",
                    "px": "42219.9",
                    "sz": "0.12060306",
                    "side": "buy",
                    "ts": "1630048897897"
                }
            ]
        }

    def get_ws_order_book_snapshot_msg(self) -> Dict:
        return {
            "arg": {
                "channel": "books",
                "instId": self.ex_trading_pair
            },
            "action": "snapshot",
            "data": [
                {
                    "asks": [
                        ["8476.98", "415", "0", "13"],
                        ["8477", "7", "0", "2"],
                        ["8477.34", "85", "0", "1"],
                        ["8477.56", "1", "0", "1"],
                        ["8505.84", "8", "0", "1"],
                        ["8506.37", "85", "0", "1"],
                        ["8506.49", "2", "0", "1"],
                        ["8506.96", "100", "0", "2"]
                    ],
                    "bids": [
                        ["8476.97", "256", "0", "12"],
                        ["8475.55", "101", "0", "1"],
                        ["8475.54", "100", "0", "1"],
                        ["8475.3", "1", "0", "1"],
                        ["8447.32", "6", "0", "1"],
                        ["8447.02", "246", "0", "1"],
                        ["8446.83", "24", "0", "1"],
                        ["8446", "95", "0", "3"]
                    ],
                    "ts": "1597026383085",
                    "checksum": -855196043,
                    "prevSeqId": -1,
                    "seqId": 123456
                }
            ]
        }

    def get_ws_order_book_diff_msg(self) -> Dict:
        return {
            "arg": {
                "channel": "books",
                "instId": self.ex_trading_pair
            },
            "action": "update",
            "data": [
                {
                    "asks": [
                        ["8476.98", "415", "0", "13"],
                        ["8477", "7", "0", "2"],
                        ["8477.34", "85", "0", "1"],
                    ],
                    "bids": [
                        ["8476.97", "256", "0", "12"],
                        ["8475.55", "101", "0", "1"],
                    ],
                    "ts": "1597026383085",
                    "checksum": -855196043
                }
            ]
        }

    def get_ws_funding_info_msg(self) -> Dict:
        return {
            "arg": {
                "channel": "funding-rate",
                "instId": self.ex_trading_pair
            },
            "data": [
                {
                    "fundingRate": "0.0000691810863830",
                    "fundingTime": "1706169600000",
                    "instId": self.ex_trading_pair,
                    "instType": "SWAP",
                    "maxFundingRate": "0.00375",
                    "method": "next_period",
                    "minFundingRate": "-0.00375",
                    "nextFundingRate": "0.0000188847902064",
                    "nextFundingTime": "1706198400000",
                    "settFundingRate": "-0.0000126482926462",
                    "settState": "settled",
                    "ts": "1706148300320"
                }
            ]
        }

    def get_ws_mark_price_info_msg(self) -> Dict:
        return {
            "arg": {
                "channel": "mark-price",
                "instId": self.ex_trading_pair
            },
            "data": [
                {
                    "instType": "SWAP",
                    "instId": self.ex_trading_pair,
                    "markPx": "0.1",
                    "ts": "1597026383085"
                }
            ]
        }

    def get_ws_index_price_info_msg(self) -> Dict:
        return {
            "arg": {
                "channel": "index-tickers",
                "instId": self.ex_trading_pair
            },
            "data": [
                {
                    "instId": self.ex_trading_pair,
                    "idxPx": "0.1",
                    "high24h": "0.5",
                    "low24h": "0.1",
                    "open24h": "0.1",
                    "sodUtc0": "0.1",
                    "sodUtc8": "0.1",
                    "ts": "1597026383085"
                }
            ]
        }

    def get_index_price_info_rest_msg(self):
        return {
            "code": "0",
            "msg": "",
            "data": [
                {
                    "instId": self.ex_trading_pair,
                    "idxPx": "43350",
                    "high24h": "43649.7",
                    "sodUtc0": "43444.1",
                    "open24h": "43640.8",
                    "low24h": "43261.9",
                    "sodUtc8": "43328.7",
                    "ts": "1649419644492"
                }
            ]
        }

    def get_mark_price_info_rest_msg(self):
        return {
            "code": "0",
            "msg": "",
            "data": [
                {
                    "instType": "SWAP",
                    "instId": self.ex_trading_pair,
                    "markPx": "200",
                    "ts": "1597026383085"
                }
            ]
        }

    def get_funding_info_rest_msg(self):
        return {
            "code": "0",
            "data": [
                {
                    "fundingRate": "0.0000792386885340",
                    "fundingTime": "1703088000000",
                    "instId": self.ex_trading_pair,
                    "instType": "SWAP",
                    "method": "next_period",
                    "maxFundingRate": "0.00375",
                    "minFundingRate": "-0.00375",
                    "nextFundingRate": "0.0002061194322149",
                    "nextFundingTime": "1703116800000",
                    "settFundingRate": "0.0001418433662153",
                    "settState": "settled",
                    "ts": "1703070685309"
                }
            ],
            "msg": ""
        }

    def get_last_traded_prices_rest_msg(self):
        return {
            "code": "0",
            "msg": "",
            "data": [
                {
                    "instType": "SWAP",
                    "instId": self.ex_trading_pair,
                    "last": "9999.99",
                    "lastSz": "1",
                    "askPx": "9999.99",
                    "askSz": "11",
                    "bidPx": "8888.88",
                    "bidSz": "5",
                    "open24h": "9000",
                    "high24h": "10000",
                    "low24h": "8888.88",
                    "volCcy24h": "2222",
                    "vol24h": "2222",
                    "sodUtc0": "0.1",
                    "sodUtc8": "0.1",
                    "ts": "1597026383085"
                },
                {
                    "instType": "SWAP",
                    "instId": "BTC-USD-SWAP",
                    "last": "9999.99",
                    "lastSz": "1",
                    "askPx": "9999.99",
                    "askSz": "11",
                    "bidPx": "8888.88",
                    "bidSz": "5",
                    "open24h": "9000",
                    "high24h": "10000",
                    "low24h": "8888.88",
                    "volCcy24h": "2222",
                    "vol24h": "2222",
                    "sodUtc0": "0.1",
                    "sodUtc8": "0.1",
                    "ts": "1597026383085"
                }
            ]
        }

    @property
    def trading_rules_request_mock_response(self):
        response = {
            "code": "0",
            "data": [
                {
                    "alias": "",
                    "baseCcy": "",
                    "category": "1",
                    "ctMult": "1",
                    "ctType": "linear",
                    "ctVal": "1",
                    "ctValCcy": self.base_asset,
                    "expTime": "",
                    "instFamily": "LTC-USDT",
                    "instId": self.ex_trading_pair,
                    "instType": "SWAP",
                    "lever": "50",
                    "listTime": "1611916828000",
                    "lotSz": "1",
                    "maxIcebergSz": "100000000.0000000000000000",
                    "maxLmtAmt": "20000000",
                    "maxLmtSz": "100000000",
                    "maxMktAmt": "",
                    "maxMktSz": "10000",
                    "maxStopSz": "10000",
                    "maxTriggerSz": "100000000.0000000000000000",
                    "maxTwapSz": "100000000.0000000000000000",
                    "minSz": "1",
                    "optType": "",
                    "quoteCcy": "",
                    "settleCcy": self.quote_asset,
                    "state": "live",
                    "stk": "",
                    "tickSz": "0.01",
                    "uly": self.ex_trading_pair,
                }
            ],
            "msg": ""
        }
        return response

    def configure_trading_rules_response(
            self,
            mock_api: aioresponses,
    ) -> List[str]:
        base_url = web_utils.get_rest_url_for_endpoint(endpoint=CONSTANTS.REST_GET_INSTRUMENTS[CONSTANTS.ENDPOINT],
                                                       domain=CONSTANTS.DEFAULT_DOMAIN)
        params = {
            "instType": "SWAP"
        }
        encoded_params = urlencode(params)
        full_url = f"{base_url}?{encoded_params}"
        regex_url = re.compile(f"^{full_url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        response = self.trading_rules_request_mock_response
        mock_api.get(regex_url, body=json.dumps(response))
        return [base_url]

    # TODO: Check if unclosed client session should remain after test run
    @aioresponses()
    def test_get_new_order_book_successful(self, mock_api):
        self.configure_trading_rules_response(mock_api)
        endpoint = CONSTANTS.REST_ORDER_BOOK[CONSTANTS.ENDPOINT]
        url = web_utils.get_rest_url_for_endpoint(endpoint, self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = self.get_rest_snapshot_msg()
        mock_api.get(regex_url, body=json.dumps(resp))

        order_book = self.async_run_with_timeout(
            self.data_source.get_new_order_book(self.trading_pair)
        )

        expected_update_id = int(float(resp["data"][0]["ts"]))

        self.assertEqual(expected_update_id, order_book.snapshot_uid)
        bids = list(order_book.bid_entries())
        asks = list(order_book.ask_entries())
        self.assertEqual(1, len(bids))
        self.assertEqual(41006.3, bids[0].price)
        self.assertEqual(0.30178218, bids[0].amount)
        self.assertEqual(expected_update_id, bids[0].update_id)
        self.assertEqual(1, len(asks))
        self.assertEqual(41006.8, asks[0].price)
        self.assertEqual(0.60038921, asks[0].amount)
        self.assertEqual(expected_update_id, asks[0].update_id)

    @aioresponses()
    def test_get_new_order_book_raises_exception(self, mock_api):
        self.configure_trading_rules_response(mock_api)
        endpoint = CONSTANTS.REST_ORDER_BOOK[CONSTANTS.ENDPOINT]
        url = web_utils.get_rest_url_for_endpoint(endpoint, self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, status=400)
        with self.assertRaises(IOError):
            self.async_run_with_timeout(
                self.data_source.get_new_order_book(self.trading_pair)
            )

    @aioresponses()
    def test_get_last_traded_prices(self, mock_api):
        url = web_utils.get_rest_url_for_endpoint(CONSTANTS.REST_LATEST_SYMBOL_INFORMATION[CONSTANTS.ENDPOINT], self.domain)
        url_regex = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(url_regex, body=json.dumps(self.get_last_traded_prices_rest_msg()))
        last_traded_prices = self.async_run_with_timeout(
            self.data_source.get_last_traded_prices([self.trading_pair])
        )
        self.assertEqual(2, len(last_traded_prices))
        self.assertEqual(9999.99, last_traded_prices[self.ex_trading_pair])

    @aioresponses()
    def test_get_funding_info(self, mock_api):
        funding_endpoint = CONSTANTS.REST_FUNDING_RATE_INFO[CONSTANTS.ENDPOINT]
        funding_url = web_utils.get_rest_url_for_endpoint(funding_endpoint, self.domain)
        funding_regex_url = re.compile(f"^{funding_url}".replace(".", r"\.").replace("?", r"\?"))
        funding_info_resp = self.get_funding_info_rest_msg()
        mock_api.get(funding_regex_url, body=json.dumps(funding_info_resp))

        index_price_endpoint = CONSTANTS.REST_INDEX_TICKERS[CONSTANTS.ENDPOINT]
        index_price_url = web_utils.get_rest_url_for_endpoint(index_price_endpoint, self.domain)
        index_price_regex_url = re.compile(f"^{index_price_url}".replace(".", r"\.").replace("?", r"\?"))
        index_price_resp = self.get_index_price_info_rest_msg()
        mock_api.get(index_price_regex_url, body=json.dumps(index_price_resp))

        mark_price_endpoint = CONSTANTS.REST_MARK_PRICE[CONSTANTS.ENDPOINT]
        mark_price_url = web_utils.get_rest_url_for_endpoint(mark_price_endpoint, self.domain)
        mark_price_regex_url = re.compile(f"^{mark_price_url}".replace(".", r"\.").replace("?", r"\?"))
        mark_price_resp = self.get_mark_price_info_rest_msg()
        mock_api.get(mark_price_regex_url, body=json.dumps(mark_price_resp))

        funding_info: FundingInfo = self.async_run_with_timeout(
            self.data_source.get_funding_info(self.trading_pair)
        )

        self.assertEqual(self.trading_pair, funding_info.trading_pair)
        self.assertEqual(Decimal(index_price_resp["data"][0]["idxPx"]), funding_info.index_price)
        self.assertEqual(Decimal(mark_price_resp["data"][0]["markPx"]), funding_info.mark_price)
        self.assertEqual(int(funding_info_resp["data"][0]["nextFundingTime"] * 1e-3), funding_info.next_funding_utc_timestamp)
        self.assertEqual(Decimal(funding_info_resp["data"][0]["fundingRate"]), funding_info.rate)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_subscribe_channels_successful(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        result_subscribe_trade = self.get_ws_trade_msg()
        result_subscribe_order_book_snapshot = self.get_ws_order_book_snapshot_msg()
        result_subscribe_index_price_info = self.get_ws_index_price_info_msg()
        result_subscribe_mark_price_info = self.get_ws_mark_price_info_msg()
        result_subscribe_funding_info = self.get_ws_funding_info_msg()

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_trade),
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_order_book_snapshot),
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_index_price_info),
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_mark_price_info),
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_funding_info),
        )

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_subscription_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value
        )

        self.assertEqual(5, len(sent_subscription_messages))

        expected_trade_subscription = {
            "op": "subscribe",
            "args": [
                {
                    "channel": "trades",
                    "instId": self.ex_trading_pair
                }
            ],
        }
        self.assertEqual(expected_trade_subscription, sent_subscription_messages[0])

        expected_order_book_subscription = {
            "op": "subscribe",
            "args": [
                {
                    "channel": "books",
                    "instId": self.ex_trading_pair
                }
            ],
        }
        self.assertEqual(expected_order_book_subscription, sent_subscription_messages[1])

        expected_funding_info_subscription = {
            "op": "subscribe",
            "args": [
                {
                    "channel": "funding-rate",
                    "instId": self.ex_trading_pair
                }
            ],
        }
        self.assertEqual(expected_funding_info_subscription, sent_subscription_messages[2])

        expected_mark_price_subscription = {
            "op": "subscribe",
            "args": [
                {
                    "channel": "mark-price",
                    "instId": self.ex_trading_pair
                }
            ],
        }
        self.assertEqual(expected_mark_price_subscription, sent_subscription_messages[3])

        expected_index_price_subscription = {
            "op": "subscribe",
            "args": [
                {
                    "channel": "index-tickers",
                    "instId": self.ex_trading_pair
                }
            ],
        }
        self.assertEqual(expected_index_price_subscription, sent_subscription_messages[4])

        self.assertTrue(
            self._is_logged("INFO", "Subscribed to public order book, trade and funding info channels...")
        )

    def test_subscribe_channels_raises_cancel_exception(self):
        mock_ws = MagicMock()
        mock_ws.send.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source._subscribe_channels(mock_ws)
            )
            self.async_run_with_timeout(self.listening_task)

    def test_subscribe_channels_raises_exception_and_logs_error(self):
        mock_ws = MagicMock()
        mock_ws.send.side_effect = Exception("Test Error")

        with self.assertRaises(Exception):
            self.listening_task = self.ev_loop.create_task(
                self.data_source._subscribe_channels(mock_ws)
            )
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

    # TODO: Check if raises tests should print exceptions during test run
    def test_listen_for_trades_logs_exception(self):
        incomplete_resp = self.get_ws_trade_msg()
        del incomplete_resp["data"][0]["tradeId"]

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
        mock_queue = AsyncMock()
        trade_event = {
            "arg": {
                "channel": "trades",
                "instId": self.trading_pair
            },
            "data": [
                {
                    "instId": self.trading_pair,
                    "tradeId": "130639474",
                    "px": "42219.9",
                    "sz": "0.12060306",
                    "side": "buy",
                    "ts": "1630048897897"
                }
            ]
        }
        mock_queue.get.side_effect = [trade_event, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._trade_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_trades(self.ev_loop, msg_queue))

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(OrderBookMessageType.TRADE, msg.type)
        self.assertEqual(trade_event["data"][0]["tradeId"], msg.trade_id)
        self.assertEqual(int(trade_event["data"][0]["ts"]), msg.timestamp)

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
            "arg": {
                "channel": "books",
                "instId": self.trading_pair
            },
            "action": "update",
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

    @aioresponses()
    def test_listen_for_order_book_diffs_successful(self, mock_api):
        self.configure_trading_rules_response(mock_api)
        mock_queue = AsyncMock()
        diff_event = self.get_ws_order_book_diff_msg()
        mock_queue.get.side_effect = [diff_event, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._diff_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue))

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(OrderBookMessageType.DIFF, msg.type)
        self.assertEqual(-1, msg.trade_id)
        self.assertEqual(int(diff_event["data"][0]["ts"]), msg.timestamp)
        expected_update_id = int(int(diff_event["data"][0]["ts"]))
        self.assertEqual(expected_update_id, msg.update_id)

        bids = msg.bids
        asks = msg.asks
        self.assertEqual(2, len(bids))
        self.assertEqual(8476.97, bids[0].price)
        self.assertEqual(256, bids[0].amount)
        self.assertEqual(expected_update_id, bids[0].update_id)
        self.assertEqual(3, len(asks))
        self.assertEqual(8476.98, asks[0].price)
        self.assertEqual(415, asks[0].amount)
        self.assertEqual(expected_update_id, asks[0].update_id)

    @aioresponses()
    def test_listen_for_order_book_snapshots_cancelled_when_fetching_snapshot(self, mock_api):
        self.configure_trading_rules_response(mock_api)
        endpoint = CONSTANTS.REST_ORDER_BOOK[CONSTANTS.ENDPOINT]
        url = web_utils.get_rest_url_for_endpoint(endpoint=endpoint, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, exception=asyncio.CancelledError)

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(
                self.data_source.listen_for_order_book_snapshots(self.ev_loop, asyncio.Queue())
            )

    # TODO: Check if unclosed client session should remain after test run
    @aioresponses()
    @patch("hummingbot.core.data_type.order_book_tracker_data_source.OrderBookTrackerDataSource._sleep")
    def test_listen_for_order_book_snapshots_log_exception(self, mock_api, sleep_mock):
        msg_queue: asyncio.Queue = asyncio.Queue()
        sleep_mock.side_effect = lambda _: self._create_exception_and_unlock_test_with_event(asyncio.CancelledError())

        endpoint = CONSTANTS.REST_ORDER_BOOK[CONSTANTS.ENDPOINT]
        url = web_utils.get_rest_url_for_endpoint(endpoint=endpoint, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, exception=Exception)

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
        )
        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertTrue(
            self._is_logged("ERROR", f"Unexpected error fetching order book snapshot for {self.trading_pair}.")
        )

    # TODO
    @aioresponses()
    def test_listen_for_order_book_snapshots_successful(self, mock_api):
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = 1
        mock_queue = AsyncMock()
        snapshot_event = {
            "arg": {
                "channel": "books",
                "instId": self.trading_pair
            },
            "action": "snapshot",
            "data": [
                {
                    "asks": [
                        ["8476.98", "415", "0", "13"],
                        ["8477", "7", "0", "2"],
                        ["8477.34", "85", "0", "1"],
                    ],
                    "bids": [
                        ["8476.97", "256", "0", "12"],
                        ["8475.55", "101", "0", "1"],
                    ],
                    "ts": "1597026383085",
                    "checksum": -855196043
                }
            ]
        }
        mock_queue.get.side_effect = [snapshot_event, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._snapshot_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue))

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(OrderBookMessageType.SNAPSHOT, msg.type)
        self.assertEqual(-1, msg.trade_id)
        self.assertEqual(int(snapshot_event["data"][0]["ts"]), msg.timestamp)
        expected_update_id = int(int(snapshot_event["data"][0]["ts"]))
        self.assertEqual(expected_update_id, msg.update_id)

        bids = msg.bids
        asks = msg.asks
        self.assertEqual(2, len(bids))
        self.assertEqual(8476.97, bids[0].price)
        self.assertEqual(256, bids[0].amount)
        self.assertEqual(expected_update_id, bids[0].update_id)
        self.assertEqual(3, len(asks))
        self.assertEqual(8476.98, asks[0].price)
        self.assertEqual(415, asks[0].amount)
        self.assertEqual(expected_update_id, asks[0].update_id)

    def test_listen_for_mark_price_cancelled_when_listening(self):
        mock_queue = MagicMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.data_source._message_queue[self.data_source._mark_price_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_mark_price_info(msg_queue)
            )
            self.async_run_with_timeout(self.listening_task)

    def test_listen_for_mark_price_logs_exception(self):
        incomplete_resp = self.get_ws_mark_price_info_msg()
        del incomplete_resp["arg"]["instId"]

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [incomplete_resp, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._mark_price_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_mark_price_info(msg_queue))

        try:
            self.async_run_with_timeout(self.listening_task)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error when processing public mark price updates from exchange"))

    def test_listen_for_mark_price_successful(self):
        mark_price_event = self.get_ws_mark_price_info_msg()

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [mark_price_event, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._mark_price_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_mark_price_info(msg_queue))

        mark_price_update = Decimal(mark_price_event["data"][0]["markPx"])
        expected_last_index_price = -1
        expected_last_next_funding_utc_timestamp = -1
        expected_last_rate = -1
        self.data_source._last_index_price = expected_last_index_price
        self.data_source._last_next_funding_utc_timestamp = expected_last_next_funding_utc_timestamp
        self.data_source._last_rate = expected_last_rate
        msg: FundingInfoUpdate = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(self.trading_pair, msg.trading_pair)
        self.assertEqual(mark_price_update, msg.mark_price)
        self.assertEqual(expected_last_next_funding_utc_timestamp, msg.next_funding_utc_timestamp)
        self.assertEqual(expected_last_rate, msg.rate)
        self.assertEqual(expected_last_index_price, msg.index_price)

    def test_listen_for_index_price_cancelled_when_listening(self):
        mock_queue = MagicMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.data_source._message_queue[self.data_source._index_price_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(
                self.data_source.listen_for_index_price_info(msg_queue)
            )
            self.async_run_with_timeout(self.listening_task)

    def test_listen_for_index_price_logs_exception(self):
        incomplete_resp = self.get_ws_index_price_info_msg()
        del incomplete_resp["arg"]["instId"]

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [incomplete_resp, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._index_price_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_index_price_info(msg_queue))

        try:
            self.async_run_with_timeout(self.listening_task)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error when processing public index price updates from exchange"))

    def test_listen_for_index_price_successful(self):
        index_price_event = self.get_ws_index_price_info_msg()

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [index_price_event, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._index_price_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_index_price_info(msg_queue))

        index_price_update = Decimal(index_price_event["data"][0]["idxPx"])
        expected_last_mark_price = -2
        expected_last_next_funding_utc_timestamp = -2
        expected_last_rate = -2

        self.data_source._last_mark_price = expected_last_mark_price
        self.data_source._last_next_funding_utc_timestamp = expected_last_next_funding_utc_timestamp
        self.data_source._last_rate = expected_last_rate
        msg: FundingInfoUpdate = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(self.trading_pair, msg.trading_pair)
        self.assertEqual(index_price_update, msg.index_price)
        self.assertEqual(expected_last_next_funding_utc_timestamp, msg.next_funding_utc_timestamp)
        self.assertEqual(expected_last_rate, msg.rate)
        self.assertEqual(expected_last_mark_price, msg.mark_price)

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
        incomplete_resp = self.get_ws_funding_info_msg()
        del incomplete_resp["arg"]["instId"]

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [incomplete_resp, asyncio.CancelledError()]
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
        index_price_event = self.get_ws_funding_info_msg()

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [index_price_event, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._funding_info_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_funding_info(msg_queue))

        expected_last_index_price = -3
        expected_last_mark_price = -3
        update_next_funding_utc_timestamp = int(index_price_event["data"][0]["nextFundingTime"] * 1e-3)
        update_rate = Decimal(index_price_event["data"][0]["fundingRate"])

        self.data_source._last_mark_price = expected_last_mark_price
        self.data_source._last_index_price = expected_last_index_price
        msg: FundingInfoUpdate = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(self.trading_pair, msg.trading_pair)
        self.assertEqual(expected_last_index_price, msg.index_price)
        self.assertEqual(update_next_funding_utc_timestamp, msg.next_funding_utc_timestamp)
        self.assertEqual(update_rate, msg.rate)
        self.assertEqual(expected_last_mark_price, msg.mark_price)

    def test_channel_originating_message_snapshot_queue(self):
        event_message = self.get_ws_order_book_snapshot_msg()
        channel_result = self.data_source._channel_originating_message(event_message)
        self.assertEqual(channel_result, self.data_source._snapshot_messages_queue_key)

    def test_channel_originating_message_diff_queue(self):
        event_message = self.get_ws_order_book_diff_msg()
        channel_result = self.data_source._channel_originating_message(event_message)
        self.assertEqual(channel_result, self.data_source._diff_messages_queue_key)

    def test_channel_originating_message_trade_queue(self):
        event_message = self.get_ws_trade_msg()
        channel_result = self.data_source._channel_originating_message(event_message)
        self.assertEqual(channel_result, self.data_source._trade_messages_queue_key)
