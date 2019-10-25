import asyncio

import aiohttp
import pandas as pd
from mock import patch
from unittest import TestCase

from test.integration.assets.mock_data.fixture_liquid import FixtureLiquid
from hummingbot.market.liquid.liquid_api_order_book_data_source import LiquidAPIOrderBookDataSource


PATCH_BASE_PATH = \
    'hummingbot.market.liquid.liquid_api_order_book_data_source.LiquidAPIOrderBookDataSource.{method}'


class TestLiquidOrderBookDataSource(TestCase):

    @patch(PATCH_BASE_PATH.format(method='get_exchange_markets_data'))
    def test_get_active_exchange_markets(self, mock_get_exchange_markets_data):
        """
        Test end to end flow from pinging Liquid API for markets and exchange data
        all the way to extract out needed information such as trading_pairs, 
        prices, and volume information.
        """
        loop = asyncio.get_event_loop()

        # Mock Future() object return value as the request response
        f = asyncio.Future()
        f.set_result(FixtureLiquid.EXCHANGE_MARKETS_DATA)
        mock_get_exchange_markets_data.return_value = f

        all_markets_df = loop.run_until_complete(
            LiquidAPIOrderBookDataSource.get_active_exchange_markets())
        # loop.close()

        # Check DF type, dimension, indices, and values
        self.assertIsInstance(all_markets_df, pd.DataFrame)
        self.assertEqual(all_markets_df.shape, (3, 28))  # (num of rows, num of cols)
        self.assertListEqual(
            sorted(all_markets_df.index),
            sorted(['BTCUSD', 'ETHUSD', 'STACETH'])
        )
        self.assertListEqual(
            sorted(all_markets_df.columns),
            [
                'base_currency',
                'btc_minimum_withdraw',
                'cfd_enabled',
                'code',
                'currency',
                'disabled',
                'fiat_minimum_withdraw',
                'high_market_ask',
                'id',
                'indicator',
                'last_event_timestamp',
                'last_price_24h',
                'last_traded_price',
                'last_traded_quantity',
                'low_market_bid',
                'maker_fee',
                'margin_enabled',
                'market_ask',
                'market_bid',
                'name',
                'product_type',
                'pusher_channel',
                'quoted_currency',
                'symbol',
                'taker_fee',
                'usd_volume',
                'volume',
                'volume_24h'
            ]
        )
        self.assertEqual(
            all_markets_df.loc['BTCUSD'].last_traded_price, '7470.49746')


    def test_filter_market_data(self):
        """
        Test the logic to parse out market data from input exchange data,
        and make sure invalid fields and payload are all filtered out in
        this process.
        """
        market_data = LiquidAPIOrderBookDataSource.filter_market_data(
                exchange_markets_data=FixtureLiquid.EXCHANGE_MARKETS_DATA)

        self.assertIsInstance(market_data, list)
        self.assertEqual(len(market_data), 3)

        # Select and compare the first item with largest id from the list
        self.assertDictEqual(
            sorted(market_data, key=lambda x: x['id'], reverse=True)[0],
            {
                'id': '27',
                'product_type': 'CurrencyPair',
                'code': 'CASH',
                'name': ' CASH Trading',
                'market_ask': 162.88941,
                'market_bid': 162.70211,
                'indicator': 1,
                'currency': 'USD',
                'currency_pair_code': 'ETHUSD',
                'symbol': '$',
                'btc_minimum_withdraw': None,
                'fiat_minimum_withdraw': None,
                'pusher_channel': 'product_cash_ethusd_27',
                'taker_fee': '0.001',
                'maker_fee': '0.001',
                'low_market_bid': '159.8',
                'high_market_ask': '163.991',
                'volume_24h': '577.3217041',
                'last_price_24h': '161.63163',
                'last_traded_price': '162.572',
                'last_traded_quantity': '4.0',
                'quoted_currency': 'USD',
                'base_currency': 'ETH',
                'disabled': False,
                'margin_enabled': True,
                'cfd_enabled': False,
                'last_event_timestamp': '1571995382.9368947'
            }
        )
        self.assertListEqual(
            sorted([market['currency_pair_code'] for market in market_data]),
            ['BTCUSD', 'ETHUSD', 'STACETH']
        )

    @patch(PATCH_BASE_PATH.format(method='get_exchange_markets_data'))
    def test_get_trading_pairs(self, mock_get_exchange_markets_data):
        """
        Test the logic where extracts trading pairs as well as the part
        symbol and id mapping is formed
        """
        loop = asyncio.get_event_loop()

        # Mock Future() object return value as the request response
        f = asyncio.Future()
        f.set_result(FixtureLiquid.EXCHANGE_MARKETS_DATA)
        mock_get_exchange_markets_data.return_value = f

        # Instantiate class instance
        liquid_data_source = LiquidAPIOrderBookDataSource()

        snapshot = loop.run_until_complete(
            liquid_data_source.get_trading_pairs())

        self.assertListEqual(
            sorted(snapshot), sorted(['STACETH', 'BTCUSD', 'ETHUSD']))

        self.assertDictEqual(
            liquid_data_source.symbol_id_conversion_dict,
            {'BTCUSD': '1', 'ETHUSD': '27', 'STACETH': '206'}
        )
