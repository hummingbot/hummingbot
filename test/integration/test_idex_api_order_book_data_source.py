import itertools
from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../")))
import asyncio
import inspect
import unittest
import aiohttp
import logging

from typing import List
from unittest.mock import patch, AsyncMock

from decimal import Decimal

from hummingbot.core.data_type.order_book_tracker_entry import OrderBookTrackerEntry
from test.integration.assets.mock_data.fixture_idex import FixtureIdex
from hummingbot.connector.exchange.idex.idex_api_order_book_data_source import IdexAPIOrderBookDataSource
from hummingbot.connector.exchange.idex.idex_order_book_message import IdexOrderBookMessage
from hummingbot.core.data_type.order_book_message import OrderBookMessageType
from hummingbot.core.data_type.order_book import OrderBook


class IdexAPIOrderBookDataSourceUnitTest(unittest.TestCase):

    class AsyncIterator:
        def __init__(self, seq):
            self.iter = iter(seq)

        def __aiter__(self):
            return self

        async def __anext__(self):
            try:
                return next(self.iter)
            except StopIteration:
                raise StopAsyncIteration

    eth_sample_pairs: List[str] = [
        "UNI-ETH",
        "LBA-ETH"
    ]

    bsc_sample_pairs: List[str] = [
        "EOS-USDT",
        "BTCB-BNB"
    ]

    RESOLVE_PATH: str = 'hummingbot.connector.exchange.idex.idex_resolve.{method}'
    GET_MOCK: str = 'aiohttp.ClientSession.get'

    PATCH_BASE_PATH = \
        'hummingbot.connector.exchange.idex.idex_api_order_book_data_source.IdexAPIOrderBookDataSource.{method}'

    @classmethod
    def setUpClass(cls) -> None:
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.eth_order_book_data_source: IdexAPIOrderBookDataSource = IdexAPIOrderBookDataSource(cls.eth_sample_pairs)
        cls.bsc_order_book_data_source: IdexAPIOrderBookDataSource = IdexAPIOrderBookDataSource(cls.bsc_sample_pairs)

    def run_async(self, task):
        return self.ev_loop.run_until_complete(task)
    '''
    def test_get_idex_rest_url(self):
        # Calls blockchain default ("eth") in global_config[blockchain] if blockchain value is None
        # Todo: test with user inputs and blockchain value to ensure ETH and BSC blockchain inputs work
        self.assertEqual("https://api-sandbox-ETH.idex.io/", IdexAPIOrderBookDataSource.get_idex_rest_url())

    def test_get_idex_ws_feed(self):
        # Calls blockchain default ("eth") in global_config[blockchain] if blockchain value is None
        # Todo: test with user inputs and blockchain value to ensure ETH and BSC blockchain inputs work.
        self.assertEqual("wss://websocket-sandbox-ETH.idex.io/v1", IdexAPIOrderBookDataSource.get_idex_ws_feed())
    '''
    # Test returns: Success
    # Uses PropertyMock to mock the API URL. Test confirms ability to fetch all trading pairs
    # on both exchanges (ETH, BSC).
    def test_fetch_trading_pairs(self):
        # ETH URL
        trading_pairs: List[str] = self.run_async(
            self.eth_order_book_data_source.fetch_trading_pairs())
        self.assertIn("UNI-ETH", trading_pairs)
        self.assertIn("LBA-ETH", trading_pairs)

    def test_get_last_traded_price(self):
        with patch(self.GET_MOCK, new_callable=AsyncMock) as mocked_get:
            # ETH URL
            for t_pair in self.eth_sample_pairs:
                mocked_get.return_value.json.return_value = FixtureIdex.TRADING_PAIR_TRADES
                last_traded_price: float = self.run_async(
                    self.eth_order_book_data_source.get_last_traded_price(t_pair, "https://api-eth.idex.io"))
                self.assertEqual(0.01780000, last_traded_price)

    @patch(RESOLVE_PATH.format(method='get_idex_rest_url'))
    @patch(GET_MOCK, new_callable=AsyncMock)
    def test_get_last_traded_prices(self, mocked_get, mocked_api_url):
        # ETH URL
        mocked_api_url.return_value = "https://api-eth.idex.io"
        mocked_get.return_value.json.return_value = FixtureIdex.TRADING_PAIR_TRADES
        last_traded_prices: List[str] = self.run_async(
            self.eth_order_book_data_source.get_last_traded_prices(self.eth_sample_pairs))
        self.assertEqual({"UNI-ETH": 0.01780000,
                         "LBA-ETH": 0.01780000}, last_traded_prices)
        # BSC URL
        mocked_api_url.return_value = "https://api-bsc.idex.io"
        mocked_get.return_value.json.return_value = FixtureIdex.TRADING_PAIR_TRADES
        last_traded_prices: List[str] = self.run_async(
            self.bsc_order_book_data_source.get_last_traded_prices(self.bsc_sample_pairs))
        self.assertEqual({"EOS-USDT": 0.01780000,
                          "BTCB-BNB": 0.01780000}, last_traded_prices)

    @patch(RESOLVE_PATH.format(method='get_idex_rest_url'))
    @patch(GET_MOCK, new_callable=AsyncMock)
    def test_get_mid_price(self, mocked_get, mocked_api_url):
        # ETH URL
        mocked_api_url.return_value = "https://api-eth.idex.io"
        mocked_get.return_value.json.return_value = FixtureIdex.TRADING_PAIR_TICKER
        for t_pair in self.eth_sample_pairs:
            t_pair_mid_price: List[str] = self.run_async(
                self.eth_order_book_data_source.get_mid_price(t_pair))
            self.assertEqual(Decimal("0.016175005"), t_pair_mid_price)
            self.assertIsInstance(t_pair_mid_price, Decimal)

    async def get_snapshot(self, trading_pair):
        async with aiohttp.ClientSession() as client:
            try:
                snapshot = await self.eth_order_book_data_source.get_snapshot(client, trading_pair)
                return snapshot
            except Exception:
                return None

    # @unittest.skip("failing aiohttp response context manager mocks")
    # @patch(REST_URL, new_callable=PropertyMock)
    # @patch(GET_MOCK, new_callable=AsyncMock)
    @patch(RESOLVE_PATH.format(method='get_idex_rest_url'))
    @patch('aiohttp.ClientResponse.json')
    def test_get_snapshot(self, mocked_json, mocked_api_url):

        # mocked_get.return_value.json.return_value = FixtureIdex.ORDER_BOOK_LEVEL2
        # mocked_get.return_value.status = 200

        # Mock aiohttp response
        f = asyncio.Future()
        f.set_result(FixtureIdex.ORDER_BOOK_LEVEL2)
        mocked_json.return_value = f

        mocked_api_url.return_value = "https://api-eth.idex.io"

        # mocked_get.return_value.__aenter__.return_value.text = AsyncMock(side_effect=["custom text"])
        # mocked_get.return_value.__aexit__.return_value = AsyncMock(side_effect=lambda *args: True)
        # mocked_get.return_value = MockGetResponse(FixtureIdex.ORDER_BOOK_LEVEL2, 200)

        snapshot = self.ev_loop.run_until_complete(self.get_snapshot("UNI-ETH"))
        # an artifact created by the way we mock. Normally run_until_complete() returns a result directly
        snapshot = snapshot.result()
        self.assertEqual(FixtureIdex.ORDER_BOOK_LEVEL2, snapshot)

    @patch(RESOLVE_PATH.format(method='get_idex_rest_url'))
    @patch(PATCH_BASE_PATH.format(method='get_snapshot'))
    def test_get_new_order_book(self, mock_get_snapshot, mocked_api_url):

        # Mock Future() object return value as the request response
        # For this particular test, the return value from get_snapshot is not relevant, therefore
        # setting it with a random snapshot from fixture
        f = asyncio.Future()
        f.set_result(FixtureIdex.SNAPSHOT_2)
        mock_get_snapshot.return_value = f.result()

        mocked_api_url.return_value = "https://api-eth.idex.io"
        orderbook = self.ev_loop.run_until_complete(self.eth_order_book_data_source.get_new_order_book("UNI-ETH"))

        print(orderbook.snapshot[0])

        # Validate the returned value is OrderBook
        self.assertIsInstance(orderbook, OrderBook)

        # Ensure the number of bids / asks provided in the snapshot are equal to the respective number of orderbook rows
        self.assertEqual(len(orderbook.snapshot[0].index), len(FixtureIdex.SNAPSHOT_2["bids"]))

    @patch(RESOLVE_PATH.format(method='get_idex_rest_url'))
    @patch(PATCH_BASE_PATH.format(method='get_snapshot'))
    def test_get_tracking_pairs(self, mock_get_snapshot, mocked_api_url):

        mocked_api_url.return_value = "https://api-eth.idex.io"

        # Mock Future() object return value as the request response
        # For this particular test, the return value from get_snapshot is not relevant, therefore
        # setting it with a random snapshot from fixture
        f = asyncio.Future()
        f.set_result(FixtureIdex.SNAPSHOT_2)
        mock_get_snapshot.return_value = f.result()

        tracking_pairs = self.ev_loop.run_until_complete(self.eth_order_book_data_source.get_tracking_pairs())

        # Validate the number of tracking pairs is equal to the number of trading pairs received
        self.assertEqual(len(self.eth_sample_pairs), len(tracking_pairs))

        # Make sure the entry key in tracking pairs matches with what's in the trading pairs
        for trading_pair, tracking_pair_obj in zip(self.eth_sample_pairs, list(tracking_pairs.keys())):
            self.assertEqual(trading_pair, tracking_pair_obj)

        # Validate the data type for each tracking pair value is OrderBookTrackerEntry
        for order_book_tracker_entry in tracking_pairs.values():
            self.assertIsInstance(order_book_tracker_entry, OrderBookTrackerEntry)

        # Validate the order book tracker entry trading_pairs are valid
        for trading_pair, order_book_tracker_entry in zip(self.eth_sample_pairs, tracking_pairs.values()):
            self.assertEqual(order_book_tracker_entry.trading_pair, trading_pair)

    @patch(RESOLVE_PATH.format(method='get_idex_rest_url'))
    @patch(PATCH_BASE_PATH.format(method='get_snapshot'))
    def test_listen_for_order_book_snapshots(self, mock_get_snapshot, mock_api_url):
        """
        test_listen_for_order_book_snapshots (test.integration.test_idex_api_order_book_data_source.
            IdexAPIOrderBookDataSourceUnitTest)
        Example order book message added to the queue:
        IdexOrderBookMessage(
            type = < OrderBookMessageType.SNAPSHOT: 1 > ,
            content = {
                'sequence': int,
                'bids': [
                    ['181.95138', '0.69772000', 2],
                    ...
                ],
                'asks': [
                    ['182.11620', '0.32400000', 4],
                    ...
                ],
            },
            timestamp = 1573041256.2376761)
        """

        mock_api_url.return_value = "https://api-eth.idex.io"

        # Instantiate empty async queue and make sure the initial size is 0
        q = asyncio.Queue()
        self.assertEqual(q.qsize(), 0)

        # Mock Future() object return value as the request response
        # For this particular test, the return value from get_snapshot is not relevant, therefore
        # setting it with a random snapshot from fixture
        f1 = asyncio.Future()
        f1.set_result(FixtureIdex.SNAPSHOT_1)

        # Mock Future() object return value as the request response
        # For this particular test, the return value from get_snapshot is not relevant, therefore
        # setting it with a random snapshot from fixture
        f2 = asyncio.Future()
        f2.set_result(FixtureIdex.SNAPSHOT_2)

        mock_get_snapshot.side_effect = [f1.result(), f2.result()]

        # Listening for tracking pairs within the set timeout timeframe
        timeout = 6

        print('{test_name} is going to run for {timeout} seconds, starting now'.format(
            test_name=inspect.stack()[0][3],
            timeout=timeout))

        try:
            self.run_async(
                # Force exit from event loop after set timeout seconds
                asyncio.wait_for(
                    self.eth_order_book_data_source.listen_for_order_book_snapshots(ev_loop=self.ev_loop, output=q),
                    timeout=timeout
                )
            )
        except asyncio.exceptions.TimeoutError as e:
            print(e)

        # Make sure that the number of items in the queue after certain seconds make sense
        # For instance, when the asyncio sleep time is set to 5 seconds in the method
        # If we configure timeout to be the same length, only 1 item has enough time to be received
        self.assertGreaterEqual(q.qsize(), 1)

        # Validate received response has correct data types
        first_item = q.get_nowait()
        self.assertIsInstance(first_item, IdexOrderBookMessage)
        self.assertIsInstance(first_item.type, OrderBookMessageType)

        # Validate order book message type
        self.assertEqual(first_item.type, OrderBookMessageType.SNAPSHOT)

        # Validate snapshot received matches with the original snapshot received from API
        self.assertEqual(first_item.content['bids'], FixtureIdex.SNAPSHOT_1['bids'])
        self.assertEqual(first_item.content['asks'], FixtureIdex.SNAPSHOT_1['asks'])

        # Validate the rest of the content
        self.assertEqual(first_item.content['trading_pair'], self.eth_sample_pairs[0])
        self.assertEqual(first_item.content['sequence'], FixtureIdex.SNAPSHOT_1['sequence'])

    @patch(RESOLVE_PATH.format(method='get_idex_ws_feed'))
    @patch(PATCH_BASE_PATH.format(method='_inner_messages'))
    def test_listen_for_order_book_diffs(self, mock_inner_messages, mock_ws_feed):
        timeout = 2

        mock_ws_feed.return_value = "wss://websocket-eth.idex.io/v1"

        q = asyncio.Queue()

        #  Socket events receiving in the order from top to bottom
        mocked_socket_responses = itertools.cycle(
            [
                FixtureIdex.WS_PRICE_LEVEL_UPDATE_1,
                FixtureIdex.WS_PRICE_LEVEL_UPDATE_2,
                FixtureIdex.WS_SUBSCRIPTION_SUCCESS
            ]
        )

        mock_inner_messages.return_value = self.AsyncIterator(seq=mocked_socket_responses)

        print('{test_name} is going to run for {timeout} seconds, starting now'.format(
            test_name=inspect.stack()[0][3],
            timeout=timeout))

        try:
            self.run_async(
                # Force exit from event loop after set timeout seconds
                asyncio.wait_for(
                    self.eth_order_book_data_source.listen_for_order_book_diffs(ev_loop=self.ev_loop, output=q),
                    timeout=timeout
                )
            )
        except asyncio.exceptions.TimeoutError as e:
            print(e)

        first_event = q.get_nowait()
        second_event = q.get_nowait()

        recv_events = [first_event, second_event]

        for event in recv_events:
            # Validate the data inject into async queue is in Liquid order book message type
            self.assertIsInstance(event, IdexOrderBookMessage)

            # Validate the event type is equal to DIFF
            self.assertEqual(event.type, OrderBookMessageType.DIFF)

            # Validate the actual content injected is dict type
            self.assertIsInstance(event.content, dict)

    @patch(PATCH_BASE_PATH.format(method='_inner_messages'))
    def test_listen_for_trades(self, mock_inner_messages):
        timeout = 2

        q = asyncio.Queue()

        #  Socket events receiving in the order from top to bottom
        mocked_socket_responses = itertools.cycle(
            [
                FixtureIdex.WS_TRADE_1,
                FixtureIdex.WS_TRADE_2
            ]
        )

        mock_inner_messages.return_value = self.AsyncIterator(seq=mocked_socket_responses)

        print('{test_name} is going to run for {timeout} seconds, starting now'.format(
            test_name=inspect.stack()[0][3],
            timeout=timeout))

        try:
            self.run_async(
                # Force exit from event loop after set timeout seconds
                asyncio.wait_for(
                    self.eth_order_book_data_source.listen_for_trades(ev_loop=self.ev_loop, output=q),
                    timeout=timeout
                )
            )
        except asyncio.exceptions.TimeoutError as e:
            print(e)

        first_event = q.get_nowait()
        second_event = q.get_nowait()

        recv_events = [first_event, second_event]

        for event in recv_events:
            # Validate the data inject into async queue is in Liquid order book message type
            self.assertIsInstance(event, IdexOrderBookMessage)

            # Validate the event type is equal to DIFF
            self.assertEqual(event.type, OrderBookMessageType.TRADE)

            # Validate the actual content injected is dict type
            self.assertIsInstance(event.content, dict)


def main():
    logging.basicConfig(level=logging.INFO)
    unittest.main()


if __name__ == "__main__":
    main()
