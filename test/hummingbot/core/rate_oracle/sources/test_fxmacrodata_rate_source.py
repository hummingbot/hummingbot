import json
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import patch

from aioresponses import aioresponses

from hummingbot.core.rate_oracle.sources.fxmacrodata_rate_source import DEFAULT_BASE_URL, FXMacroDataRateSource
from hummingbot.core.web_assistant.connections.connections_factory import ConnectionsFactory

SOURCES_URL = f"{DEFAULT_BASE_URL}/fx/sources"
API_KEY_ENV = {"FXMACRODATA_API_KEY": "test-key"}


def sources_payload(*pairs):
    return {"sources": [{"id": "test", "served_pairs": list(pairs)}]}


def forex_payload(value):
    return {"data": [{"date": "2026-09-10", "val": value}]}


class FXMacroDataRateSourceTest(IsolatedAsyncioWrapperTestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        # The source borrows the process-wide ConnectionsFactory session, so
        # start each test from a closed one and close it again afterwards
        # rather than leaving a session behind on the test's event loop.
        await ConnectionsFactory().close()
        self.addAsyncCleanup(ConnectionsFactory().close)
        # get_prices is memoised on the repr of its arguments, which for
        # ``self`` is the object's address, so a fresh source can collide with
        # a garbage-collected one from an earlier test unless the cache is reset.
        FXMacroDataRateSource.get_prices.cache_clear()
        self.source = FXMacroDataRateSource()
        key_patch = patch.dict("os.environ", API_KEY_ENV, clear=False)
        key_patch.start()
        self.addCleanup(key_patch.stop)

    def _forex_url(self, base: str, quote: str) -> str:
        return f"{DEFAULT_BASE_URL}/forex/{base.lower()}/{quote.lower()}?limit=1"

    def test_name(self):
        self.assertEqual("fxmacrodata", self.source.name)

    @aioresponses()
    async def test_get_prices_returns_every_covered_currency_against_the_quote(self, mock_api):
        mock_api.get(SOURCES_URL, body=json.dumps(sources_payload("EUR/USD", "GBP/USD")))
        mock_api.get(self._forex_url("EUR", "USD"), body=json.dumps(forex_payload(1.0921)))
        mock_api.get(self._forex_url("GBP", "USD"), body=json.dumps(forex_payload(1.2733)))

        prices = await self.source.get_prices(quote_token="USD")

        self.assertEqual(Decimal("1.0921"), prices["EUR-USD"])
        self.assertEqual(Decimal("1.2733"), prices["GBP-USD"])
        # The quote token is never requested against itself.
        self.assertNotIn("USD-USD", prices)

    @aioresponses()
    async def test_the_currency_universe_is_discovered_not_hardcoded(self, mock_api):
        # Only two currencies are covered, so exactly one rate request should
        # follow. This is what stops the source asking for pairs that would 404.
        mock_api.get(SOURCES_URL, body=json.dumps(sources_payload("JPY/USD")))
        mock_api.get(self._forex_url("JPY", "USD"), body=json.dumps(forex_payload(0.0068)))

        prices = await self.source.get_prices(quote_token="USD")

        self.assertEqual({"JPY-USD": Decimal("0.0068")}, prices)

    @aioresponses()
    async def test_a_pair_stored_the_other_way_round_is_requested_in_the_wanted_direction(self, mock_api):
        # FXMacroData stores USD/JPY, not JPY/USD, and derives the inverse
        # itself. The source must ask for the direction it wants rather than
        # reciprocating locally, so JPY/USD is the request made here.
        mock_api.get(SOURCES_URL, body=json.dumps(sources_payload("USD/JPY")))
        mock_api.get(self._forex_url("JPY", "USD"), body=json.dumps(forex_payload(0.00678)))

        prices = await self.source.get_prices(quote_token="USD")

        self.assertEqual({"JPY-USD": Decimal("0.00678")}, prices)

    @aioresponses()
    async def test_a_cross_between_two_covered_currencies_is_requested(self, mock_api):
        # Neither currency is stored against the other, but both are covered,
        # so the API derives the cross and the source must ask for it.
        mock_api.get(SOURCES_URL, body=json.dumps(sources_payload("USD/THB", "USD/BRL")))
        mock_api.get(self._forex_url("THB", "BRL"), body=json.dumps(forex_payload(0.155)))
        mock_api.get(self._forex_url("USD", "BRL"), body=json.dumps(forex_payload(5.11)))

        prices = await self.source.get_prices(quote_token="BRL")

        self.assertEqual(Decimal("0.155"), prices["THB-BRL"])
        self.assertEqual(Decimal("5.11"), prices["USD-BRL"])

    @aioresponses()
    async def test_a_null_rate_is_dropped_not_published_as_zero(self, mock_api):
        # val is documented as anyOf[number, null]. Publishing 0 would make the
        # conversion infinite for every pair touching that currency.
        mock_api.get(SOURCES_URL, body=json.dumps(sources_payload("EUR/USD")))
        mock_api.get(self._forex_url("EUR", "USD"), body=json.dumps(forex_payload(None)))

        prices = await self.source.get_prices(quote_token="USD")

        self.assertEqual({}, prices)

    @aioresponses()
    async def test_a_zero_rate_is_dropped(self, mock_api):
        mock_api.get(SOURCES_URL, body=json.dumps(sources_payload("EUR/USD")))
        mock_api.get(self._forex_url("EUR", "USD"), body=json.dumps(forex_payload(0)))

        prices = await self.source.get_prices(quote_token="USD")

        self.assertEqual({}, prices)

    @aioresponses()
    async def test_an_infinite_rate_is_dropped(self, mock_api):
        # json.dumps writes float("inf") as the bare token Infinity, which the
        # JSON decoder accepts and Decimal turns into Decimal("Infinity").
        # Publishing that would make a direct pair infinite and its inverse zero.
        mock_api.get(SOURCES_URL, body=json.dumps(sources_payload("EUR/USD", "GBP/USD")))
        mock_api.get(self._forex_url("EUR", "USD"), body=json.dumps(forex_payload(float("inf"))))
        mock_api.get(self._forex_url("GBP", "USD"), body='{"data": [{"date": "2026-09-10", "val": 1e999}]}')

        prices = await self.source.get_prices(quote_token="USD")

        self.assertEqual({}, prices)

    @aioresponses()
    async def test_a_nan_rate_is_dropped(self, mock_api):
        # NaN cannot be ordered against zero, so a bare "rate <= 0" check would
        # raise rather than drop it.
        mock_api.get(SOURCES_URL, body=json.dumps(sources_payload("EUR/USD")))
        mock_api.get(self._forex_url("EUR", "USD"), body=json.dumps(forex_payload(float("nan"))))

        prices = await self.source.get_prices(quote_token="USD")

        self.assertEqual({}, prices)

    @aioresponses()
    async def test_empty_data_is_dropped(self, mock_api):
        mock_api.get(SOURCES_URL, body=json.dumps(sources_payload("EUR/USD")))
        mock_api.get(self._forex_url("EUR", "USD"), body=json.dumps({"data": []}))

        prices = await self.source.get_prices(quote_token="USD")

        self.assertEqual({}, prices)

    @aioresponses()
    async def test_an_uncovered_quote_token_warns_and_makes_no_rate_requests(self, mock_api):
        # BTC is not a covered currency, so every pair would 404. One warning
        # naming the covered set is more use than a burst of failures.
        mock_api.get(SOURCES_URL, body=json.dumps(sources_payload("EUR/USD")))

        prices = await self.source.get_prices(quote_token="BTC")

        self.assertEqual({}, prices)
        self.assertEqual(1, len(mock_api.requests))

    @aioresponses()
    async def test_quote_token_defaults_to_usd(self, mock_api):
        mock_api.get(SOURCES_URL, body=json.dumps(sources_payload("EUR/USD")))
        mock_api.get(self._forex_url("EUR", "USD"), body=json.dumps(forex_payload(1.09)))

        prices = await self.source.get_prices()

        self.assertIn("EUR-USD", prices)

    @aioresponses()
    async def test_a_failing_pair_does_not_lose_the_others(self, mock_api):
        mock_api.get(SOURCES_URL, body=json.dumps(sources_payload("EUR/USD", "GBP/USD")))
        mock_api.get(self._forex_url("EUR", "USD"), status=500)
        mock_api.get(self._forex_url("GBP", "USD"), body=json.dumps(forex_payload(1.27)))

        prices = await self.source.get_prices(quote_token="USD")

        self.assertEqual({"GBP-USD": Decimal("1.27")}, prices)

    @aioresponses()
    async def test_an_unreachable_currency_universe_returns_empty_rather_than_raising(self, mock_api):
        mock_api.get(SOURCES_URL, status=503)

        prices = await self.source.get_prices(quote_token="USD")

        self.assertEqual({}, prices)

    @aioresponses()
    async def test_api_key_is_sent_as_a_header_not_a_query_parameter(self, mock_api):
        mock_api.get(SOURCES_URL, body=json.dumps(sources_payload("EUR/USD")))
        mock_api.get(self._forex_url("EUR", "USD"), body=json.dumps(forex_payload(1.09)))

        await self.source.get_prices(quote_token="USD")

        for (_, url), kwargs in mock_api.requests.items():
            self.assertNotIn("test-key", str(url))
            self.assertEqual("test-key", kwargs[0].kwargs["headers"]["X-API-Key"])

    @aioresponses()
    async def test_without_a_key_it_warns_instead_of_making_requests(self, mock_api):
        # The FX reference endpoints are subscriber-only, so firing the requests
        # anyway would just produce a burst of 401s the user cannot act on.
        with patch.dict("os.environ", {}, clear=True):
            prices = await self.source.get_prices(quote_token="USD")

        self.assertEqual({}, prices)
        self.assertEqual(0, len(mock_api.requests))

    @aioresponses()
    async def test_requests_use_the_shared_connections_factory_session(self, mock_api):
        # The source must not own a ClientSession: it borrows the one every
        # connector and data feed shares, so its lifetime is the application's
        # rather than this object's and nothing is left open when the oracle
        # stops or the configured source is replaced.
        mock_api.get(SOURCES_URL, body=json.dumps(sources_payload("EUR/USD")))
        mock_api.get(self._forex_url("EUR", "USD"), body=json.dumps(forex_payload(1.09)))
        self.assertIsNone(ConnectionsFactory()._shared_client)

        await self.source.get_prices(quote_token="USD")

        shared_client = ConnectionsFactory()._shared_client
        self.assertIsNotNone(shared_client)
        api_factory = self.source._get_api_factory()
        self.assertIs(api_factory, self.source._get_api_factory())
        self.assertIs(ConnectionsFactory(), api_factory._connections_factory)

        await ConnectionsFactory().close()

        self.assertTrue(shared_client.closed)
