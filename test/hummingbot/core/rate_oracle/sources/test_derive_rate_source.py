import asyncio
import json
import re
import unittest
from decimal import Decimal
from typing import Awaitable, Callable, List, Optional
from unittest.mock import AsyncMock, patch

from aioresponses import aioresponses

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.derive import derive_constants as CONSTANTS, derive_web_utils as web_utils
from hummingbot.connector.exchange.derive.derive_exchange import DeriveExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.rate_oracle.sources.derive_rate_source import DeriveRateSource


class DeriveRateSourceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.target_token = "COINALPHA"
        cls.global_token = "USDC"
        cls.derive_pair = f"{cls.target_token}-{cls.global_token}"
        cls.trading_pair = combine_to_hb_trading_pair(base=cls.target_token, quote=cls.global_token)
        cls.derive_ignored_pair = "SOMEPAIR"
        cls.ignored_trading_pair = combine_to_hb_trading_pair(base="SOME", quote="PAIR")

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.mocking_assistant = NetworkMockingAssistant()
        self.exchange = self.create_exchange_instance()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def create_exchange_instance(self):
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        return DeriveExchange(
            client_config_map=client_config_map,
            derive_api_key="testAPIKey",
            derive_api_secret="testSecret",
            sub_id="45465",
            trading_required = False,
            trading_pairs=[self.trading_pair],
        )

    @property
    def all_symbols_url(self):
        url = web_utils.public_rest_url(CONSTANTS.EXCHANGE_CURRENCIES_PATH_URL)
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def trading_rules_url(self):
        url = web_utils.public_rest_url(CONSTANTS.EXCHANGE_CURRENCIES_PATH_URL)
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def trading_rules_currency_url(self):
        url = web_utils.public_rest_url(CONSTANTS.EXCHANGE_INFO_PATH_URL)
        url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?") + ".*")
        return url

    @property
    def trading_rules_request_mock_response(self):
        return {"result": {
            "instruments": [
                {
                    'instrument_type': 'erc20',  # noqa: mock
                    'instrument_name': 'COINALPHA-USDC',
                    'scheduled_activation': 1728508925,
                    'scheduled_deactivation': 9223372036854775807,
                    'is_active': True,
                    'tick_size': '0.01',
                    'minimum_amount': '0.1',
                    'maximum_amount': '1000',
                    'amount_step': '0.01',
                    'mark_price_fee_rate_cap': '0',
                    'maker_fee_rate': '0.0015',
                    'taker_fee_rate': '0.0015',
                    'base_fee': '0.1',
                    'base_currency': 'COINALPHA',
                    'quote_currency': 'USDC',
                    'option_details': None,
                    "erc20_details": {
                        "decimals": 18,
                        "underlying_erc20_address": "0x15CEcd5190A43C7798dD2058308781D0662e678E",  # noqa: mock
                        "borrow_index": "1",
                        "supply_index": "1"
                    },
                    "base_asset_address": "0xE201fCEfD4852f96810C069f66560dc25B2C7A55",  # noqa: mock
                    "base_asset_sub_id": "0",
                    "pro_rata_fraction": "0",
                    "fifo_min_allocation": "0",
                    "pro_rata_amount_step": "1"
                }
            ],
            "pagination": {
                "num_pages": 1,
                "count": 1
            }
        },
            "id": "dedda961-4a97-46fb-84fb-6510f90dceb0"  # noqa: mock
        }

    @property
    def currency_request_mock_response(self):
        return {
            'result': [
                {'currency': 'COINALPHA', 'spot_price': '27.761323954505412608', 'spot_price_24h': '33.240154426604556288'},
            ]
        }

    def configure_trading_rules_response(
            self,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> List[str]:

        url = self.trading_rules_url
        response = self.trading_rules_request_mock_response
        mock_api.post(url, body=json.dumps(response), callback=callback)
        return [url]

    def configure_currency_trading_rules_response(
            self,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> List[str]:

        url = self.trading_rules_currency_url
        response = self.currency_request_mock_response
        mock_api.post(url, body=json.dumps(response), callback=callback)
        return [url]

    def configure_all_symbols_response(
            self,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
    ) -> List[str]:

        url = self.all_symbols_url
        response = self.trading_rules_request_mock_response
        mock_api.post(url, body=json.dumps(response), callback=callback)
        return [url]

    def setup_derive_responses(self, mock_request, mock_prices, mock_api, expected_rate: Decimal):
        url = web_utils.private_rest_url(CONSTANTS.SERVER_TIME_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = {"result": 1640000003000}

        mock_api.get(regex_url,
                     body=json.dumps(response))

        pairs_url = web_utils.public_rest_url(path_url=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL)
        symbols_response = self.trading_rules_request_mock_response

        derive_prices_global_url = web_utils.public_rest_url(path_url=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL)
        derive_prices_global_response = {
            "result": {
                "instrument_type": "erc20",
                "instrument_name": "COINALPHA-USDC",
                "scheduled_activation": 1728508925,
                "scheduled_deactivation": 9223372036854776000,
                "is_active": True,
                "tick_size": "0.01",
                "minimum_amount": "0.1",
                "maximum_amount": "1000",
                "amount_step": "0.01",
                "mark_price_fee_rate_cap": "0",
                "maker_fee_rate": "0.0015",
                "taker_fee_rate": "0.0015",
                "base_fee": "0.1",
                "base_currency": "COINALPHA-USDC",
                "quote_currency": "USDC",
                "option_details": None,
                "perp_details": None,
                "erc20_details": {
                    "decimals": 18,
                    "underlying_erc20_address": "0x15CEcd5190A43C7798dD2058308781D0662e678E",
                    "borrow_index": "1",
                    "supply_index": "1"
                },
                "base_asset_address": "0xE201fCEfD4852f96810C069f66560dc25B2C7A55",
                "base_asset_sub_id": "0",
                "pro_rata_fraction": "0",
                "fifo_min_allocation": "0",
                "pro_rata_amount_step": "1",
                "best_ask_amount": "2.86",
                "best_ask_price": "3149.46",
                "best_bid_amount": "2.86",
                "best_bid_price": "3143.16",
                "five_percent_bid_depth": "13.24",
                "five_percent_ask_depth": "6.67",
                "option_pricing": None,
                "index_price": "3147.17",
                "mark_price": "10",
                "stats": {
                    "contract_volume": "1.27",
                    "num_trades": "10",
                    "open_interest": "2305.747423837198057937",
                    "high": "3287.67",
                    "low": "3123.59",
                    "percent_change": "-0.046946",
                    "usd_change": "-155.02"
                },
                "timestamp": 1738456434000,
                "min_price": "3085.47",
                "max_price": "3210.11"
            },
            "id": "0a34780b-cad3-462c-be5c-7097a36cc9a0"
        }
        mock_api.post(pairs_url, body=json.dumps(symbols_response))
        # mock_api.post(derive_prices_us_url, body=json.dumps(derive_prices_us_response))
        mock_api.post(derive_prices_global_url, body=json.dumps(derive_prices_global_response))

    @patch("hummingbot.connector.exchange.derive.derive_exchange.DeriveExchange._make_trading_rules_request", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.derive.derive_exchange.DeriveExchange._make_currency_request", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.derive.derive_exchange.DeriveExchange.get_all_pairs_prices", new_callable=AsyncMock)
    @aioresponses()
    def test_get_prices(self, mock_prices: AsyncMock, mock_request: AsyncMock, mock_rules, mock_api):

        res = [{"symbol": {"instrument_name": "COINALPHA-USDC", "best_bid": "3143.16", "best_ask": "3149.46"}}]

        expected_rate = Decimal("3146.31")
        self.setup_derive_responses(mock_api=mock_api, mock_request=mock_request, mock_prices=mock_prices, expected_rate=expected_rate)

        rate_source = DeriveRateSource()
        self.configure_currency_trading_rules_response(mock_api=mock_api)
        mock_request.return_value = self.currency_request_mock_response

        mocked_response = self.trading_rules_request_mock_response
        self.configure_trading_rules_response(mock_api=mock_api)
        mock_rules.side_effect = self.trading_rules_request_mock_response
        self.exchange._instrument_ticker = mocked_response["result"]["instruments"]
        mock_prices.side_effect = [res]

        mock_request.side_effect = [self.currency_request_mock_response]
        prices = self.async_run_with_timeout(rate_source.get_prices(quote_token="USDC"))
        self.assertIn(self.trading_pair, prices)
        self.assertEqual(expected_rate, prices[self.trading_pair])
        # self.assertIn(self.us_trading_pair, prices)
        self.assertNotIn(self.ignored_trading_pair, prices)
