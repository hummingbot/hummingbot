from unittest import TestCase

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.binance.binance_api_order_book_data_source import BinanceAPIOrderBookDataSource
from hummingbot.connector.exchange.kucoin.kucoin_api_order_book_data_source import KucoinAPIOrderBookDataSource
from hummingbot.connector.exchange.paper_trade import create_paper_trade_market, get_order_book_tracker
from hummingbot.core.data_type.order_book_tracker import OrderBookTracker


class PaperTradeExchangeTests(TestCase):

    def test_get_order_book_tracker_for_connector_using_generic_tracker(self):
        tracker = get_order_book_tracker(connector_name="binance", trading_pairs=["COINALPHA-HBOT"])
        self.assertEqual(OrderBookTracker, type(tracker))

        tracker = get_order_book_tracker(connector_name="kucoin", trading_pairs=["COINALPHA-HBOT"])
        self.assertEqual(OrderBookTracker, type(tracker))

    def test_create_paper_trade_market_for_connector_using_generic_tracker(self):
        paper_exchange = create_paper_trade_market(
            exchange_name="binance",
            client_config_map=ClientConfigAdapter(ClientConfigMap()),
            trading_pairs=["COINALPHA-HBOT"])
        self.assertEqual(BinanceAPIOrderBookDataSource, type(paper_exchange.order_book_tracker.data_source))

        paper_exchange = create_paper_trade_market(
            exchange_name="kucoin",
            client_config_map=ClientConfigAdapter(ClientConfigMap()),
            trading_pairs=["COINALPHA-HBOT"])
        self.assertEqual(KucoinAPIOrderBookDataSource, type(paper_exchange.order_book_tracker.data_source))
