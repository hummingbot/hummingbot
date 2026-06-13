from unittest import TestCase

from hummingbot.client.config.client_config_map import PaperTradeConfigMap
from hummingbot.client.settings import AllConnectorSettings
from hummingbot.connector.exchange.binance.binance_api_order_book_data_source import BinanceAPIOrderBookDataSource
from hummingbot.connector.exchange.coinbase_advanced_trade.coinbase_advanced_trade_api_order_book_data_source import (
    CoinbaseAdvancedTradeAPIOrderBookDataSource,
)
from hummingbot.connector.exchange.kucoin.kucoin_api_order_book_data_source import KucoinAPIOrderBookDataSource
from hummingbot.connector.exchange.paper_trade import PaperTradeExchange, create_paper_trade_market, get_order_book_tracker
from hummingbot.core.data_type.order_book_tracker import OrderBookTracker


class PaperTradeExchangeTests(TestCase):

    def setUp(self):
        super().setUp()
        self._original_paper_trade_connectors_names = AllConnectorSettings.paper_trade_connectors_names.copy()
        self._original_all_connector_settings = AllConnectorSettings.all_connector_settings.copy()

    def tearDown(self):
        AllConnectorSettings.paper_trade_connectors_names = self._original_paper_trade_connectors_names
        AllConnectorSettings.all_connector_settings = self._original_all_connector_settings
        super().tearDown()

    def test_get_order_book_tracker_for_connector_using_generic_tracker(self):
        tracker = get_order_book_tracker(connector_name="binance", trading_pairs=["COINALPHA-HBOT"])
        self.assertEqual(OrderBookTracker, type(tracker))

        tracker = get_order_book_tracker(connector_name="kucoin", trading_pairs=["COINALPHA-HBOT"])
        self.assertEqual(OrderBookTracker, type(tracker))

        tracker = get_order_book_tracker(connector_name="coinbase_advanced_trade", trading_pairs=["BTC-USD"])
        self.assertEqual(OrderBookTracker, type(tracker))

    def test_create_paper_trade_market_for_connector_using_generic_tracker(self):
        paper_exchange = create_paper_trade_market(
            exchange_name="binance",
            trading_pairs=["COINALPHA-HBOT"])
        self.assertEqual(BinanceAPIOrderBookDataSource, type(paper_exchange.order_book_tracker.data_source))

        paper_exchange = create_paper_trade_market(
            exchange_name="kucoin",
            trading_pairs=["COINALPHA-HBOT"])
        self.assertEqual(KucoinAPIOrderBookDataSource, type(paper_exchange.order_book_tracker.data_source))

        paper_exchange = create_paper_trade_market(
            exchange_name="coinbase_advanced_trade",
            trading_pairs=["BTC-USD"])
        self.assertEqual(PaperTradeExchange, type(paper_exchange))
        self.assertEqual(
            CoinbaseAdvancedTradeAPIOrderBookDataSource,
            type(paper_exchange.order_book_tracker.data_source),
        )

    def test_coinbase_advanced_trade_is_default_paper_trade_exchange(self):
        config_map = PaperTradeConfigMap()
        self.assertIn("coinbase_advanced_trade", config_map.paper_trade_exchanges)

    def test_initialize_paper_trade_settings_registers_coinbase_paper_connector(self):
        config_map = PaperTradeConfigMap()

        AllConnectorSettings.initialize_paper_trade_settings(config_map.paper_trade_exchanges)

        self.assertIn("coinbase_advanced_trade_paper_trade", AllConnectorSettings.get_connector_settings())
