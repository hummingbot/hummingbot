from unittest import TestCase, mock
import asyncio
from test.integration.humming_web_app import HummingWebApp
from urllib.parse import urlparse
from hummingbot.data_feed.exchange_price_manager import ExchangePriceManager
from hummingbot.data_feed.binance_price_feed import BinancePriceFeed
from test.integration.assets.mock_data.fixture_exchange_prices import FixtureExchangePrices
from decimal import Decimal


class ExchangePriceManagerUnitTest(TestCase):

    # To test all support exchange price feeds are able to get api information and update its price_dict
    def test_all_price_feeds(self):
        ev_loop = asyncio.get_event_loop()
        for ex_name in ExchangePriceManager.supported_exchanges:
            ExchangePriceManager.set_exchanges_to_feed([ex_name])
            ExchangePriceManager.start()
            ev_loop.run_until_complete(ExchangePriceManager.wait_til_ready())
            self.assertTrue(len(ExchangePriceManager.ex_feeds[ex_name].price_dict) > 0)
            for trading_pair, price in ExchangePriceManager.ex_feeds[ex_name].price_dict.items():
                self.assertTrue("-" in trading_pair)
                self.assertTrue(isinstance(price, Decimal))
            ExchangePriceManager.stop()


# Mock all api values to test prices are calculated correctly
class ExchangePriceManagerMockAPIUnitTest(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.ev_loop = asyncio.get_event_loop()
        cls.web_app = HummingWebApp.get_instance()
        for ex_feed in ExchangePriceManager.supported_exchanges.values():
            cls.web_app.add_host_to_mock(urlparse(ex_feed.price_feed_url).netloc, [])
        cls.web_app.start()
        cls.ev_loop.run_until_complete(cls.web_app.wait_til_started())
        cls._patcher = mock.patch("aiohttp.client.URL")
        cls._url_mock = cls._patcher.start()
        cls._url_mock.side_effect = cls.web_app.reroute_local
        for ex_name, ex_feed in ExchangePriceManager.supported_exchanges.items():
            cls.web_app.update_response("get", urlparse(ex_feed.price_feed_url).netloc,
                                        urlparse(ex_feed.price_feed_url).path,
                                        getattr(FixtureExchangePrices, ex_name.upper()))

    @classmethod
    def tearDownClass(cls) -> None:
        cls.web_app.stop()
        cls._patcher.stop()

    def test_price_feeds(self):
        ExchangePriceManager.set_exchanges_to_feed(['binance', 'liquid'])
        ExchangePriceManager.start()
        self.ev_loop.run_until_complete(ExchangePriceManager.wait_til_ready())
        self.assertTrue(BinancePriceFeed.get_instance()._ready_event.is_set())
        self.assertEqual(len(BinancePriceFeed.get_instance().price_dict), 3)
        eth_btc_price = ExchangePriceManager.get_price("ETH", "BTC")
        self.assertEqual(Decimal("0.025"), eth_btc_price)

        # ZRX-USDT is not in the fixture, this should return None
        zrx_usdt_price = ExchangePriceManager.get_price("ZRX", "USDT")
        self.assertEqual(None, zrx_usdt_price)

        # LINK-ETH is only in Liquid Fixture
        link_eth_price = ExchangePriceManager.get_price("LINK", "ETH")
        self.assertAlmostEqual(Decimal('0.000575'), link_eth_price)

        ExchangePriceManager.stop()

    def test_use_binance_when_none_supported(self):
        ExchangePriceManager.set_exchanges_to_feed(['coinbase_pro'])
        ExchangePriceManager.start()
        self.ev_loop.run_until_complete(ExchangePriceManager.wait_til_ready())
        self.assertTrue(BinancePriceFeed.get_instance()._ready_event.is_set())
        self.assertEqual(len(BinancePriceFeed.get_instance().price_dict), 3)
        eth_btc_price = ExchangePriceManager.get_price("ETH", "BTC")
        self.assertEqual(Decimal("0.025"), eth_btc_price)
        ExchangePriceManager.stop()

    def test_no_feed_available(self):
        ExchangePriceManager.set_exchanges_to_feed(['coinbase_pro'], False)
        ExchangePriceManager.start()
        self.ev_loop.run_until_complete(ExchangePriceManager.wait_til_ready())
        eth_btc_price = ExchangePriceManager.get_price("ETH", "BTC")
        self.assertEqual(None, eth_btc_price)
        ExchangePriceManager.stop()

    def test_binance_mid_price(self):
        ExchangePriceManager.set_exchanges_to_feed(['binance'], False)
        ExchangePriceManager.start()
        self.ev_loop.run_until_complete(ExchangePriceManager.wait_til_ready())
        expected = (Decimal(FixtureExchangePrices.BINANCE[0]["bidPrice"]) +
                    Decimal(FixtureExchangePrices.BINANCE[0]["askPrice"])) / Decimal("2")
        eth_btc_price = ExchangePriceManager.get_price("ETH", "BTC")
        self.assertEqual(expected, eth_btc_price)
        ExchangePriceManager.stop()

    def test_kucoin_mid_price(self):
        ExchangePriceManager.set_exchanges_to_feed(['kucoin'], False)
        ExchangePriceManager.start()
        self.ev_loop.run_until_complete(ExchangePriceManager.wait_til_ready())
        expected = (Decimal(FixtureExchangePrices.KUCOIN["data"]["ticker"][0]["buy"]) +
                    Decimal(FixtureExchangePrices.KUCOIN["data"]["ticker"][0]["sell"])) / Decimal("2")
        eth_btc_price = ExchangePriceManager.get_price("ETH", "BTC")
        self.assertEqual(expected, eth_btc_price)
        ExchangePriceManager.stop()

    def test_liquid_mid_price(self):
        ExchangePriceManager.set_exchanges_to_feed(['liquid'], False)
        ExchangePriceManager.start()
        self.ev_loop.run_until_complete(ExchangePriceManager.wait_til_ready())
        expected = (Decimal(FixtureExchangePrices.LIQUID[0]["market_bid"]) +
                    Decimal(FixtureExchangePrices.LIQUID[0]["market_ask"])) / Decimal("2")
        eth_btc_price = ExchangePriceManager.get_price("ETH", "BTC")
        self.assertEqual(expected, eth_btc_price)
        ExchangePriceManager.stop()
