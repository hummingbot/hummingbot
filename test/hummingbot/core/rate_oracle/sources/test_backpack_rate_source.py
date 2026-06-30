import json
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase

from aioresponses import aioresponses

from hummingbot.connector.exchange.backpack import backpack_constants as CONSTANTS, backpack_web_utils as web_utils
from hummingbot.core.rate_oracle.sources.backpack_rate_source import BackpackRateSource


class BackpackRateSourceTest(IsolatedAsyncioWrapperTestCase):
    def setup_backpack_responses(self, mock_api):
        url = web_utils.public_rest_url(path_url=CONSTANTS.TICKER_BOOK_PATH_URL)
        tickers_response = [
            {"symbol": "BP_USDC", "lastPrice": "0.5905"},
            {"symbol": "BTC_USDC", "lastPrice": "62984.1"},
            {"symbol": "USDT_USDC", "lastPrice": "0.999"},
            # Perpetual market must be ignored by the (spot) rate source.
            {"symbol": "BTC_USDC_PERP", "lastPrice": "62980.0"},
            # Empty/zero prices must be ignored.
            {"symbol": "DEAD_USDC", "lastPrice": "0"},
        ]
        mock_api.get(url, body=json.dumps(tickers_response))

    @aioresponses()
    async def test_get_prices_without_quote_token_returns_all_spot(self, mock_api):
        self.setup_backpack_responses(mock_api=mock_api)

        prices = await BackpackRateSource().get_prices()

        self.assertEqual(Decimal("0.5905"), prices["BP-USDC"])
        self.assertEqual(Decimal("62984.1"), prices["BTC-USDC"])
        self.assertEqual(Decimal("0.999"), prices["USDT-USDC"])
        # Perpetual and zero price are always excluded.
        self.assertNotIn("BTC-USDC-PERP", prices)
        self.assertFalse(any("PERP" in pair.upper() for pair in prices))
        self.assertNotIn("DEAD-USDC", prices)

    @aioresponses()
    async def test_get_prices_with_usdc_quote(self, mock_api):
        self.setup_backpack_responses(mock_api=mock_api)

        prices = await BackpackRateSource().get_prices(quote_token="USDC")

        self.assertEqual(Decimal("0.5905"), prices["BP-USDC"])
        self.assertEqual(Decimal("62984.1"), prices["BTC-USDC"])
        self.assertNotIn("BTC-USDC-PERP", prices)
        self.assertNotIn("DEAD-USDC", prices)

    @aioresponses()
    async def test_get_prices_with_usdt_quote_keeps_bridge(self, mock_api):
        # Backpack has no USDT spot markets; pricing in USDT must still work by keeping the
        # USDC-quoted pairs plus the USDT-USDC bridge so the oracle can cross-convert.
        self.setup_backpack_responses(mock_api=mock_api)

        prices = await BackpackRateSource().get_prices(quote_token="USDT")

        # The bridge pair is retained...
        self.assertEqual(Decimal("0.999"), prices["USDT-USDC"])
        # ...along with the USDC-quoted pairs reachable through it.
        self.assertEqual(Decimal("0.5905"), prices["BP-USDC"])
        self.assertEqual(Decimal("62984.1"), prices["BTC-USDC"])
        self.assertNotIn("BTC-USDC-PERP", prices)

    @aioresponses()
    async def test_get_prices_handles_error(self, mock_api):
        url = web_utils.public_rest_url(path_url=CONSTANTS.TICKER_BOOK_PATH_URL)
        mock_api.get(url, status=500)

        prices = await BackpackRateSource().get_prices(quote_token="USDC")

        self.assertEqual({}, prices)
