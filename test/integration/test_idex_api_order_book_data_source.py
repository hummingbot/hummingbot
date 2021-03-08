import asyncio
import unittest
import aiohttp

from typing import List
from unittest.mock import patch, PropertyMock, AsyncMock

from decimal import Decimal

from hummingbot.core.data_type.order_book_tracker_entry import OrderBookTrackerEntry
from test.integration.assets.mock_data.fixture_idex import FixtureIdex
from hummingbot.connector.exchange.idex.idex_api_order_book_data_source import IdexAPIOrderBookDataSource
from hummingbot.core.data_type.order_book import OrderBook


class IdexAPIOrderBookDataSourceUnitTest(unittest.TestCase):

    eth_sample_pairs: List[str] = [
        "UNI-ETH",
        "LBA-ETH"
    ]

    bsc_sample_pairs: List[str] = [
        "EOS-USDT",
        "BTCB-BNB"
    ]

    REST_URL: str = 'hummingbot.connector.exchange.idex.idex_api_order_book_data_source.' \
                    'IdexAPIOrderBookDataSource._IDEX_REST_URL'
    WS_FEED: str = 'hummingbot.connector.exchange.idex.idex_api_order_book_data_source.' \
                   'IdexAPIOrderBookDataSource._IDEX_WS_FEED'
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

    # Test returns: Success
    # Uses PropertyMock to mock the API URL. Serves more to validate the use of PropertyMock in functions
    # with GET requests to the URL.
    # The appropriate means of testing access to the global_config_map blockchain value should be discussed.
    def test_get_idex_rest_url(self):
        with patch(self.REST_URL, new_callable=PropertyMock) as mocked_api_url:
            # ETH URL
            mocked_api_url.return_value = "https://api-eth.idex.io"
            # mocked_REST_URL.assert_called_with(blockchain=global_config_map['idex_contract_blockchain'].value)
            self.assertEqual("https://api-eth.idex.io", IdexAPIOrderBookDataSource.get_idex_rest_url())
            # BSC URL
            mocked_api_url.return_value = "https://api-bsc.idex.io"
            # mocked_REST_URL.assert_called_with(blockchain=global_config_map['idex_contract_blockchain'].value)
            self.assertEqual("https://api-bsc.idex.io", IdexAPIOrderBookDataSource.get_idex_rest_url())

    # Test returns: Success
    # Uses PropertyMock to mock the WebSocket Feed. Serves more to validate the use of PropertyMock in
    # functions with GET requests to the URL.
    # The appropriate means of testing access to the global_config_map blockchain value should be discussed.
    def test_get_idex_ws_feed(self):
        with patch(self.WS_FEED, new_callable=PropertyMock) as mocked_WS_FEED:
            # ETH URL
            mocked_WS_FEED.return_value = "wss://websocket-eth.idex.io/v1"
            # mocked_REST_URL.assert_called_with(blockchain=global_config_map['idex_contract_blockchain'].value)
            self.assertEqual("wss://websocket-eth.idex.io/v1", IdexAPIOrderBookDataSource.get_idex_ws_feed())
            # BSC URL
            mocked_WS_FEED.return_value = "wss://websocket-bsc.idex.io/v1"
            # mocked_REST_URL.assert_called_with(blockchain=global_config_map['idex_contract_blockchain'].value)
            self.assertEqual("wss://websocket-bsc.idex.io/v1", IdexAPIOrderBookDataSource.get_idex_ws_feed())

    # Test returns: Success
    # Uses PropertyMock to mock the API URL. Test confirms ability to fetch all trading pairs
    # on both exchanges (ETH, BSC).
    def test_fetch_trading_pairs(self):
        with patch(self.REST_URL, new_callable=PropertyMock) as mocked_api_url:
            # ETH URL
            mocked_api_url.return_value = "https://api-eth.idex.io"
            trading_pairs: List[str] = self.run_async(
                self.eth_order_book_data_source.fetch_trading_pairs())
            self.assertIn("UNI-ETH", trading_pairs)
            self.assertIn("LBA-ETH", trading_pairs)
            # possible to use map to iterate through trading pairs list. However, commented out for readability.
            # map(lambda sample_pair : self.assertIn(sample_pair, trading_pairs), self.eth_sample_pairs)
            # BSC URL
            mocked_api_url.return_value = "https://api-bsc.idex.io"
            trading_pairs: List[str] = self.run_async(
                self.bsc_order_book_data_source.fetch_trading_pairs())
            self.assertIn("EOS-USDT", trading_pairs)
            self.assertIn("BTCB-BNB", trading_pairs)

    def test_get_last_traded_price(self):
        with patch(self.GET_MOCK, new_callable=AsyncMock) as mocked_get:
            # ETH URL
            for t_pair in self.eth_sample_pairs:
                mocked_get.return_value.json.return_value = FixtureIdex.TRADING_PAIR_TRADES
                last_traded_price: float = self.run_async(
                    self.eth_order_book_data_source.get_last_traded_price(t_pair, "https://api-eth.idex.io"))
                self.assertEqual(0.01780000, last_traded_price)

    @patch(REST_URL, new_callable=PropertyMock)
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

    @patch(REST_URL, new_callable=PropertyMock)
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
    @patch(REST_URL, new_callable=PropertyMock)
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

    @patch(REST_URL, new_callable=PropertyMock)
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

    @patch(REST_URL, new_callable=PropertyMock)
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
