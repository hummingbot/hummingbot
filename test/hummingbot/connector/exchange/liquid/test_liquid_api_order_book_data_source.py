import asyncio
import json
import unittest
from typing import Dict, Awaitable, Any, List

from aioresponses import aioresponses

from hummingbot.connector.exchange.liquid.liquid_api_order_book_data_source import LiquidAPIOrderBookDataSource
from hummingbot.connector.exchange.liquid.constants import Constants


class LiquidAPIOrderBookDataSourceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"

    def setUp(self) -> None:
        super().setUp()
        self.data_source = LiquidAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair])

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def get_products_response_mock(self, trading_pair_exch_id: int = 659) -> List[Dict[str, Any]]:
        products_mock = [
            {
                "id": str(trading_pair_exch_id),
                "product_type": "CurrencyPair",
                "code": "CASH",
                "name": None,
                "market_ask": 12.5,
                "market_bid": 12.04,
                "indicator": None,
                "currency": self.base_asset,
                "currency_pair_code": f"{self.quote_asset}{self.base_asset}",
                "symbol": None,
                "btc_minimum_withdraw": None,
                "fiat_minimum_withdraw": None,
                "pusher_channel": f"product_cash_{self.quote_asset}{self.base_asset}_659".lower(),
                "taker_fee": "0.0",
                "maker_fee": "0.0",
                "low_market_bid": "11.91",
                "high_market_ask": "12.5",
                "volume_24h": "2361.64741972",
                "last_price_24h": "11.92",
                "last_traded_price": "12.32",
                "last_traded_quantity": "2.00340964",
                "average_price": "12.33314",
                "quoted_currency": self.quote_asset,
                "base_currency": self.base_asset,
                "tick_size": "0.01",
                "disabled": False,
                "margin_enabled": False,
                "cfd_enabled": False,
                "perpetual_enabled": False,
                "last_event_timestamp": "1598864820.004941733",
                "timestamp": "1598864820.004941733",
                "multiplier_up": "1.4",
                "multiplier_down": "0.6",
                "average_time_interval": 300
            },
            {
                "id": "1",
                "product_type": "CurrencyPair",
                "code": "CASH",
                "name": " CASH Trading",
                "market_ask": 11628.9,
                "market_bid": 11619.42,
                "indicator": 1,
                "currency": "USD",
                "currency_pair_code": "BTCUSD",
                "symbol": "$",
                "btc_minimum_withdraw": None,
                "fiat_minimum_withdraw": None,
                "pusher_channel": "product_cash_btcusd_1",
                "taker_fee": "0.0",
                "maker_fee": "0.0",
                "low_market_bid": "11576.4",
                "high_market_ask": "11751.04",
                "volume_24h": "138.1747948",
                "last_price_24h": "11577.59",
                "last_traded_price": "11626.37",
                "last_traded_quantity": "0.1201",
                "average_price": "11628.69213",
                "quoted_currency": "USD",
                "base_currency": "BTC",
                "tick_size": "0.01",
                "disabled": True,
                "margin_enabled": True,
                "cfd_enabled": True,
                "perpetual_enabled": False,
                "last_event_timestamp": "1598865015.73273117",
                "timestamp": "1598865015.73273117",
                "multiplier_up": "1.4",
                "multiplier_down": "0.6",
                "average_time_interval": 300
            }
        ]
        return products_mock

    @aioresponses()
    def test_get_trading_pairs(self, mocked_api):
        url = Constants.GET_EXCHANGE_MARKETS_URL
        resp = self.get_products_response_mock()
        mocked_api.get(url, body=json.dumps(resp))

        trading_pairs = self.async_run_with_timeout(self.data_source.get_trading_pairs())

        self.assertEqual(1, len(trading_pairs))

    @aioresponses()
    def test_get_trading_pairs_updates_conversion_dict(self, mocked_api):
        url = Constants.GET_EXCHANGE_MARKETS_URL
        trading_pair_exch_id = 659
        resp = self.get_products_response_mock(trading_pair_exch_id)
        mocked_api.get(url, body=json.dumps(resp))

        self.async_run_with_timeout(self.data_source.get_trading_pairs())

        self.assertIn(self.trading_pair, self.data_source.trading_pair_id_conversion_dict)
        self.assertEqual(
            str(trading_pair_exch_id), self.data_source.trading_pair_id_conversion_dict[self.trading_pair]
        )
