import asyncio
import re
import unittest
from decimal import Decimal
from typing import Any, Awaitable, Dict
from unittest.mock import patch

import ujson
from aioresponses import aioresponses
from bidict import bidict

import hummingbot.connector.exchange.binance.binance_constants as CONSTANTS
import hummingbot.connector.exchange.binance.binance_web_utils as web_utils
import hummingbot.core.utils.market_price as market_price
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.binance.binance_exchange import BinanceExchange


class MarketPriceUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()

        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.binance_ex_trading_pair = f"{cls.base_asset}{cls.quote_asset}"

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @aioresponses()
    @patch("hummingbot.client.settings.ConnectorSetting.non_trading_connector_instance_with_default_configuration")
    def test_get_last_price(self, mock_api, connector_creator_mock):
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        connector = BinanceExchange(
            client_config_map,
            binance_api_key="",
            binance_api_secret="",
            trading_pairs=[],
            trading_required=False)
        connector._set_trading_pair_symbol_map(bidict({f"{self.binance_ex_trading_pair}": self.trading_pair}))
        connector_creator_mock.return_value = connector

        url = web_utils.public_rest_url(path_url=CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_response: Dict[str, Any] = {
            # truncated response
            "symbol": self.binance_ex_trading_pair,
            "lastPrice": "1",
        }
        mock_api.get(regex_url, body=ujson.dumps(mock_response))

        result = self.async_run_with_timeout(market_price.get_last_price(
            exchange="binance",
            trading_pair=self.trading_pair,
        ))

        self.assertEqual(result, Decimal("1.0"))
