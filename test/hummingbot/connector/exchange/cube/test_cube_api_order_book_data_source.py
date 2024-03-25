import asyncio
import json
import re
import unittest
from decimal import Decimal
from typing import Awaitable
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
from aioresponses.core import aioresponses

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.cube import cube_constants as CONSTANTS, cube_web_utils as web_utils
from hummingbot.connector.exchange.cube.cube_api_order_book_data_source import CubeAPIOrderBookDataSource
from hummingbot.connector.exchange.cube.cube_exchange import CubeExchange
from hummingbot.connector.exchange.cube.cube_ws_protobufs import market_data_pb2, trade_pb2
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage


class CubeAPIOrderBookDataSourceUnitTests(unittest.TestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "SOL"
        cls.quote_asset = "USDC"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = cls.base_asset + cls.quote_asset
        cls.domain = "live"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task = None
        self.mocking_assistant = NetworkMockingAssistant()

        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.connector = CubeExchange(
            client_config_map=client_config_map,
            cube_api_key="",
            cube_api_secret="",
            cube_subaccount_id="1",
            trading_pairs=[self.trading_pair],
            trading_required=False,
            domain=self.domain,
        )
        self.data_source = CubeAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory,
            domain=self.domain,
        )
        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self._original_full_order_book_reset_time = self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = -1

        self.resume_test_event = asyncio.Event()

        # self.connector._set_trading_pair_symbol_map(bidict({self.ex_trading_pair: self.trading_pair}))

        # mapping_market_id = bidict()
        # mapping_market_id[100006] = self.trading_pair
        # self.connector._set_trading_pair_market_id_map(mapping_market_id)

        exchange_market_info = {"result": {
            "assets": [{
                "assetId": 5,
                "symbol": "SOL",
                "decimals": 9,
                "displayDecimals": 2,
                "settles": "true",
                "assetType": "Crypto",
                "sourceId": 3,
                "metadata": {},
                "status": 1
            }, {
                "assetId": 7,
                "symbol": "USDC",
                "decimals": 6,
                "displayDecimals": 2,
                "settles": "true",
                "assetType": "Crypto",
                "sourceId": 3,
                "metadata": {
                    "mint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
                },
                "status": 1
            }],
            "markets": [
                {
                    "marketId": 100006,
                    "symbol": "SOLUSDC",
                    "baseAssetId": 5,
                    "baseLotSize": "10000000",
                    "quoteAssetId": 7,
                    "quoteLotSize": "100",
                    "priceDisplayDecimals": 2,
                    "protectionPriceLevels": 1000,
                    "priceBandBidPct": 25,
                    "priceBandAskPct": 400,
                    "priceTickSize": "0.01",
                    "quantityTickSize": "0.01",
                    "status": 1,
                    "feeTableId": 2
                }
            ]
        }}

        self.connector._initialize_trading_pair_symbols_from_exchange_info(exchange_market_info)

        trading_rule = TradingRule(
            self.trading_pair,
            min_order_size=Decimal("0.001"),
            min_price_increment=Decimal("0.01"),
            min_base_amount_increment=Decimal("10000000") / (10 ** 9),
            min_notional_size=Decimal("100") / (10 ** 6),
        )

        self.connector._trading_rules[self.trading_pair] = trading_rule

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = self._original_full_order_book_reset_time
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 5):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def _trade_update_event(self):
        trade = market_data_pb2.Trades.Trade(
            tradeId=78636499,
            price=16551,
            aggressing_side=trade_pb2.Side.ASK,
            resting_exchange_order_id=4642880746,
            fill_quantity=5,
            transact_time=1710913579056259412,
            aggressing_exchange_order_id=4642881712
        )

        trade_data = market_data_pb2.Trades(trades=[trade])

        resp = {"trading_pair": self.trading_pair, "trades": trade_data}
        return resp

    def _order_diff_event(self):
        diff = market_data_pb2.MarketByPriceDiff.Diff(
            price=16521,
            quantity=53,
            op=market_data_pb2.MarketByPriceDiff.DiffOp.REPLACE
        )

        diff_data = market_data_pb2.MarketByPriceDiff(diffs=[diff])

        resp = {"trading_pair": self.trading_pair, "mbp_diff": diff_data}
        return resp

    def _snapshot_response(self):
        resp = {'result': {
            'levels': [{'price': 17695, 'quantity': 16, 'side': 0}, {'price': 17694, 'quantity': 42, 'side': 0},
                       {'price': 17693, 'quantity': 55, 'side': 0}, {'price': 17692, 'quantity': 49, 'side': 0},
                       {'price': 17691, 'quantity': 51, 'side': 0}, {'price': 17690, 'quantity': 82, 'side': 0},
                       {'price': 17689, 'quantity': 141, 'side': 0}, {'price': 17688, 'quantity': 56, 'side': 0},
                       {'price': 17698, 'quantity': 20, 'side': 1}, {'price': 17699, 'quantity': 29, 'side': 1},
                       {'price': 17700, 'quantity': 3, 'side': 1}, {'price': 17701, 'quantity': 37, 'side': 1},
                       {'price': 17702, 'quantity': 27, 'side': 1}, {'price': 17703, 'quantity': 13, 'side': 1},
                       {'price': 17704, 'quantity': 4, 'side': 1}, {'price': 17705, 'quantity': 26, 'side': 1}],
            'lastTransactTime': 1710840543845664276, 'lastTradePrice': 17695, 'marketState': 'normalOperation'}}
        return resp

    @aioresponses()
    def test_get_new_order_book_successful(self, mock_api):
        url = web_utils.public_rest_url(path_url=CONSTANTS.MARKET_DATA_REQUEST_URL + "/book/100006/snapshot",
                                        domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        resp = self._snapshot_response()

        mock_api.get(regex_url, body=json.dumps(resp))

        order_book: OrderBook = self.async_run_with_timeout(self.data_source.get_new_order_book(self.trading_pair))

        expected_update_id = resp["result"]["lastTransactTime"]

        self.assertEqual(expected_update_id, order_book.snapshot_uid)
        bids = list(order_book.bid_entries())
        asks = list(order_book.ask_entries())
        self.assertEqual(8, len(bids))
        self.assertEqual(176.95000000000002, bids[0].price)
        self.assertEqual(0.016, bids[0].amount)
        self.assertEqual(expected_update_id, bids[0].update_id)
        self.assertEqual(8, len(asks))
        self.assertEqual(176.98, asks[0].price)
        self.assertEqual(0.02, asks[0].amount)
        self.assertEqual(expected_update_id, asks[0].update_id)

    @aioresponses()
    def test_get_new_order_book_raises_exception(self, mock_api):
        url = web_utils.public_rest_url(path_url=CONSTANTS.MARKET_DATA_REQUEST_URL + "/book/100006/snapshot", domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, status=400)
        with self.assertRaises(Exception):
            self.async_run_with_timeout(self.data_source.get_new_order_book(self.trading_pair))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_subscribes_to_trades_and_order_diffs(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        trade = market_data_pb2.Trades.Trade(
            tradeId=78636499,
            price=16551,
            aggressing_side=trade_pb2.Side.ASK,
            resting_exchange_order_id=4642880746,
            fill_quantity=5,
            transact_time=1710913579056259412,
            aggressing_exchange_order_id=4642881712
        )
        trade_data = market_data_pb2.Trades(trades=[trade])
        diff = market_data_pb2.MarketByPriceDiff.Diff(
            price=16521,
            quantity=53,
            op=market_data_pb2.MarketByPriceDiff.DiffOp.REPLACE
        )
        diff_data = market_data_pb2.MarketByPriceDiff(diffs=[diff])
        trade_md_msg = market_data_pb2.MdMessage(
            trades=trade_data,
        )
        diff_md_msg = market_data_pb2.MdMessage(
            mbp_diff=diff_data,
        )
        md_messages = market_data_pb2.MdMessages(
            messages=[trade_md_msg, diff_md_msg]
        )

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value, message=md_messages.SerializeToString(), message_type=aiohttp.WSMsgType.BINARY
        )

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_subscriptions())
        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)
        trade_message = self.async_run_with_timeout(self.data_source._message_queue[CONSTANTS.TRADE_EVENT_TYPE].get())
        diff_message = self.async_run_with_timeout(self.data_source._message_queue[CONSTANTS.DIFF_EVENT_TYPE].get())

        trades: market_data_pb2.Trades = trade_message["trades"]
        diffs: market_data_pb2.MarketByPriceDiff = diff_message["mbp_diff"]
        trade: market_data_pb2.Trades.Trade
        diff: market_data_pb2.MarketByPriceDiff.Diff

        for trade in trades.trades:
            self.assertEqual(78636499, trade.tradeId)
            self.assertEqual(16551, trade.price)
            self.assertEqual(trade_pb2.Side.ASK, trade.aggressing_side)
            self.assertEqual(4642880746, trade.resting_exchange_order_id)
            self.assertEqual(5, trade.fill_quantity)
            self.assertEqual(1710913579056259412, trade.transact_time)
            self.assertEqual(4642881712, trade.aggressing_exchange_order_id)

        for diff in diffs.diffs:
            self.assertEqual(16521, diff.price)
            self.assertEqual(53, diff.quantity)
            self.assertEqual(market_data_pb2.MarketByPriceDiff.DiffOp.REPLACE, diff.op)

        self.assertTrue(self._is_logged("INFO", f"Subscribed to public order book for {self.trading_pair} and trade channels..."))

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
                "ERROR", "Unexpected error occurred when listening to order book streams. Retrying in 5 seconds..."
            )
        )

    def test_listen_for_trades_cancelled_when_listening(self):
        mock_queue = MagicMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.data_source._message_queue[CONSTANTS.TRADE_EVENT_TYPE] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_trades(self.ev_loop, msg_queue))
            self.async_run_with_timeout(self.listening_task)

    def test_listen_for_trades_logs_exception(self):
        incomplete_resp = {
            "m": 1,
            "i": 2,
        }

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [incomplete_resp, asyncio.CancelledError()]
        self.data_source._message_queue[CONSTANTS.TRADE_EVENT_TYPE] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_trades(self.ev_loop, msg_queue))

        try:
            self.async_run_with_timeout(self.listening_task)
        except asyncio.CancelledError:
            pass

        self.assertTrue(self._is_logged("ERROR", "Unexpected error when processing public trade updates from exchange"))

    def test_listen_for_trades_successful(self):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = [self._trade_update_event(), asyncio.CancelledError()]
        self.data_source._message_queue[CONSTANTS.TRADE_EVENT_TYPE] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_trades(self.ev_loop, msg_queue))

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(78636499, msg.trade_id)

    def test_listen_for_order_book_diffs_cancelled(self):
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.data_source._message_queue[CONSTANTS.DIFF_EVENT_TYPE] = mock_queue

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
        self.data_source._message_queue[CONSTANTS.DIFF_EVENT_TYPE] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue)
        )

        try:
            self.async_run_with_timeout(self.listening_task)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error when processing public order book updates from exchange")
        )

    def test_listen_for_order_book_diffs_successful(self):
        mock_queue = AsyncMock()
        diff_event = self._order_diff_event()
        mock_queue.get.side_effect = [diff_event, asyncio.CancelledError()]
        self.data_source._message_queue[CONSTANTS.DIFF_EVENT_TYPE] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_diffs(self.ev_loop, msg_queue)
        )

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual("SOL-USDC", msg.content["trading_pair"])
        self.assertEqual(165.21, msg.content["bids"][0].price)

    @aioresponses()
    def test_listen_for_order_book_snapshots_cancelled_when_fetching_snapshot(self, mock_api):
        url = web_utils.public_rest_url(path_url=CONSTANTS.MARKET_DATA_REQUEST_URL + "/book/100006/snapshot", domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, exception=asyncio.CancelledError, repeat=True)

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(self.data_source.listen_for_order_book_snapshots(self.ev_loop, asyncio.Queue()))

    @aioresponses()
    @patch(
        "hummingbot.connector.exchange.cube.cube_api_order_book_data_source"
        ".CubeAPIOrderBookDataSource._sleep"
    )
    def test_listen_for_order_book_snapshots_log_exception(self, mock_api, sleep_mock):
        msg_queue: asyncio.Queue = asyncio.Queue()
        sleep_mock.side_effect = lambda _: self._create_exception_and_unlock_test_with_event(asyncio.CancelledError())

        url = web_utils.public_rest_url(path_url=CONSTANTS.MARKET_DATA_REQUEST_URL + "/book/100006/snapshot", domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, exception=Exception, repeat=True)

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
        )
        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertTrue(
            self._is_logged("ERROR", f"Unexpected error fetching order book snapshot for {self.trading_pair}.")
        )

    @aioresponses()
    def test_listen_for_order_book_snapshots_successful(
            self,
            mock_api,
    ):
        msg_queue: asyncio.Queue = asyncio.Queue()
        url = web_utils.public_rest_url(path_url=CONSTANTS.MARKET_DATA_REQUEST_URL + "/book/100006/snapshot", domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, body=json.dumps(self._snapshot_response()))

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_order_book_snapshots(self.ev_loop, msg_queue)
        )

        msg: OrderBookMessage = self.async_run_with_timeout(msg_queue.get())

        self.assertEqual(1710840543845664276, msg.content["update_id"])
        self.assertEqual("SOL-USDC", msg.content["trading_pair"])
