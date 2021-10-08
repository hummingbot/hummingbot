import asyncio
import json
import unittest
from collections import Awaitable
from typing import List, Dict, Any

from aioresponses import aioresponses

from hummingbot.connector.exchange.eterbase.eterbase_api_order_book_data_source import EterbaseAPIOrderBookDataSource
from hummingbot.connector.exchange.eterbase import eterbase_constants as CONSTANTS


class EterbaseAPIOrderBookDataSourceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"

    def setUp(self) -> None:
        super().setUp()
        self.data_source = EterbaseAPIOrderBookDataSource(trading_pairs=[self.trading_pair])

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def get_markets_response_mock(self, trading_pair_exch_id: int = 659) -> List[Dict[str, Any]]:
        markets_response_mock = [
            {
                "id": trading_pair_exch_id,
                "symbol": f"{self.quote_asset}{self.base_asset}",
                "base": self.base_asset,
                "quote": self.quote_asset,
                "state": "Trading",
                "priceSigDigs": 5,
                "qtySigDigs": 8,
                "costSigDigs": 8,
                "tradingRules": [
                    {
                        "attribute": "Qty",
                        "condition": "Min",
                        "value": 1.23456
                    }
                ],
                "allowedOrderTypes": [
                    1,
                    2,
                    3,
                    4
                ]
            },
            {
                "id": 123,
                "symbol": "ETHBTC",
                "base": "ETH",
                "quote": "BTC",
                "state": "Inactive",
                "priceSigDigs": 5,
                "qtySigDigs": 8,
                "costSigDigs": 8,
                "tradingRules": [
                    {
                        "attribute": "Qty",
                        "condition": "Min",
                        "value": 1.23456
                    }
                ],
                "allowedOrderTypes": [
                    1,
                    2,
                    3,
                    4
                ]
            }
        ]
        return markets_response_mock

    @aioresponses()
    def test_get_map_marketid(self, mocked_api):
        url = f"{CONSTANTS.REST_URL}/markets"
        trading_pair_exch_id = 659
        resp = self.get_markets_response_mock(trading_pair_exch_id)
        mocked_api.get(url, body=json.dumps(resp))

        tp_to_exch_id_map = self.async_run_with_timeout(self.data_source.get_map_marketid())

        self.assertEqual(1, len(tp_to_exch_id_map))
        self.assertEqual(trading_pair_exch_id, tp_to_exch_id_map[self.trading_pair])
