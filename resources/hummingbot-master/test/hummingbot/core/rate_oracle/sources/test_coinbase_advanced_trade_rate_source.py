import asyncio
import json
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Awaitable

from aioresponses import aioresponses

from hummingbot.connector.exchange.coinbase_advanced_trade import (
    coinbase_advanced_trade_constants as CONSTANTS,
    coinbase_advanced_trade_web_utils as web_utils,
)
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.rate_oracle.sources.coinbase_advanced_trade_rate_source import CoinbaseAdvancedTradeRateSource


class CoinbaseAdvancedTradeRateSourceTest(IsolatedAsyncioWrapperTestCase):
    global_token = None
    target_token = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.target_token = "COINALPHA"
        cls.global_token = "HBOT"
        cls.coinbase_pair = f"{cls.target_token}{cls.global_token}"
        cls.trading_pair = combine_to_hb_trading_pair(base=cls.target_token, quote=cls.global_token)
        cls.coinbase_us_pair = f"{cls.target_token}USD"
        cls.us_trading_pair = combine_to_hb_trading_pair(base=cls.target_token, quote="USD")
        cls.coinbase_ignored_pair = "SOMEPAIR"
        cls.ignored_trading_pair = combine_to_hb_trading_pair(base="SOME", quote="PAIR")

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def setup_coinbase_responses(self, mock_api, expected_rate: Decimal):
        time_url = web_utils.private_rest_url(path_url=CONSTANTS.SERVER_TIME_EP)
        mock_api.get(time_url, body=json.dumps({
            "data": {
                "iso": "2015-06-23T18:02:51Z",
                "epoch": 1435082571
            }
        }))

        product_url = web_utils.private_rest_url(path_url=CONSTANTS.ALL_PAIRS_EP)
        products_response = {
            "products": [
                {
                    "product_id": "COINALPHA-USD",
                    "quote_currency_id": "USD",
                    "base_currency_id": "COINALPHA",
                    "cancel_only": False,
                    "is_disabled": False,
                    "trading_disabled": False,
                    "auction_mode": False,
                    "product_type": "SPOT",
                    "base_min_size": "0.010000000000000000",
                    "base_max_size": "1000000",
                    "quote_increment": "0.010000000000000000",
                    "base_increment": "0.010000000000000000",
                    "quote_min_size": "0.010000000000000000",
                    "price": "1",
                    "supports_limit_orders": True,
                    "supports_market_orders": True
                }
            ],
            "num_products": 1,
        }
        mock_api.get(product_url, body=json.dumps(products_response))

        pairs_url = web_utils.public_rest_url(path_url=CONSTANTS.EXCHANGE_RATES_QUOTE_EP.format(quote_token='USD'))
        symbols_response = {  # truncated
            "data":
                {"currency": "USD",
                 "rates":
                     {"AED": "3.6720916666666667",
                      "AFN": "88.0120479999997356",
                      "ALL": "101.75",
                      "AMD": "386.8585",
                      "ANG": "1.7968655",
                      "AOA": "509.99999999999745",
                      "ARS": "228.661430047360453",
                      "COINALPHA": "0.1",
                      }
                 }

        }
        mock_api.get(pairs_url, body=json.dumps(symbols_response))

    @aioresponses()
    def test_get_coinbase_prices(self, mock_api):
        expected_rate = Decimal("10")
        self.setup_coinbase_responses(mock_api=mock_api, expected_rate=expected_rate)

        rate_source = CoinbaseAdvancedTradeRateSource()
        prices = self.async_run_with_timeout(rate_source.get_prices())

        self.assertIn("COINALPHA-USD", prices)
        self.assertEqual(expected_rate, prices["COINALPHA-USD"])
