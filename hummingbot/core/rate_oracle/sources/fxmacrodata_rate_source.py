import os
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set, Tuple

import aiohttp

from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.rate_oracle.sources.rate_source_base import RateSourceBase
from hummingbot.core.utils import async_ttl_cache
from hummingbot.core.utils.async_utils import safe_gather

DEFAULT_BASE_URL = "https://api.fxmacrodata.com/v1"
REQUEST_TIMEOUT = 30
SUBSCRIBE_URL = "https://fxmacrodata.com/subscribe"


class FXMacroDataRateSource(RateSourceBase):
    """
    Official fiat reference rates from FXMacroData.

    Every other rate source here is a crypto venue, so a bot whose global token
    is a fiat currency has nothing official to convert with. This source fills
    that gap: the rates come from central banks and statistical authorities
    (the ECB, Danmarks Nationalbank, Banco Central do Brasil and others) rather
    than from an exchange order book.

    The served pairs are discovered from the API rather than hardcoded, so the
    source picks up new coverage without a code change and never asks for a pair
    that would 404.

    The API serves any pair between the currencies it covers, deriving the
    inverse or the cross itself, so this asks for the pair it wants directly
    rather than reciprocating a rate locally.

    The FX reference endpoints require a subscription. Set ``FXMACRODATA_API_KEY``;
    it is sent as a header so it does not appear in a URL or a log line.
    """

    def __init__(self, base_url: str = DEFAULT_BASE_URL):
        super().__init__()
        self._base_url = base_url.rstrip("/")
        self._shared_client: Optional[aiohttp.ClientSession] = None

    @property
    def name(self) -> str:
        return "fxmacrodata"

    def _http_client(self) -> aiohttp.ClientSession:
        if self._shared_client is None:
            self._shared_client = aiohttp.ClientSession()
        return self._shared_client

    @staticmethod
    def _api_key() -> Optional[str]:
        return os.getenv("FXMACRODATA_API_KEY") or None

    @classmethod
    def _headers(cls) -> Dict[str, str]:
        headers = {"Accept": "application/json"}
        api_key = cls._api_key()
        if api_key:
            # A header rather than a query parameter, so the key is not written
            # into proxy logs or the bot's own request logging.
            headers["X-API-Key"] = api_key
        return headers

    async def _get_json(self, endpoint: str) -> Any:
        client = self._http_client()
        url = f"{self._base_url}/{endpoint.lstrip('/')}"
        async with client.get(
            url, headers=self._headers(), timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        ) as response:
            if response.status != 200:
                raise IOError(f"FXMacroData request to {endpoint} failed with HTTP {response.status}")
            return await response.json()

    async def _covered_currencies(self) -> List[str]:
        """Ask the API which currencies it covers.

        A pair is available whenever both of its currencies are covered: the
        API derives the inverse or the cross, so the covered set is what
        determines availability, not the list of stored pairs.
        """
        payload = await self._get_json("fx/sources")
        sources = payload.get("sources") or payload.get("data") or []
        currencies: Set[str] = set()
        for source in sources:
            for pair in source.get("served_pairs") or []:
                if "/" in pair:
                    base, quote = pair.split("/", 1)
                    currencies.update({base.upper(), quote.upper()})
        return sorted(currencies)

    async def _pair_rate(self, base: str, quote: str) -> Tuple[str, Optional[Decimal]]:
        """Fetch the rate FXMacroData serves for ``base``/``quote``."""
        payload = await self._get_json(f"forex/{base.lower()}/{quote.lower()}?limit=1")
        rows = payload.get("data") or []
        trading_pair = combine_to_hb_trading_pair(base=base, quote=quote)
        if not rows:
            return trading_pair, None
        value = rows[0].get("val")
        # val is documented as anyOf[number, null] and a zero rate would become
        # an infinite conversion, so anything not strictly positive is dropped
        # rather than published as a price.
        if value is None:
            return trading_pair, None
        rate = Decimal(str(value))
        if rate <= 0:
            return trading_pair, None
        return trading_pair, rate

    @async_ttl_cache(ttl=60, maxsize=1)
    async def get_prices(self, quote_token: Optional[str] = None) -> Dict[str, Decimal]:
        """
        Fetch official reference rates for every served pair in ``quote_token``.

        :param quote_token: Quote currency to price against. Defaults to USD.
        :return: A mapping of Hummingbot trading pairs to rates.
        """
        quote = (quote_token or "USD").upper()
        results: Dict[str, Decimal] = {}

        if self._api_key() is None:
            self.logger().warning(
                "FXMacroData reference rates require a subscription. Set the "
                f"FXMACRODATA_API_KEY environment variable, or subscribe at {SUBSCRIBE_URL}."
            )
            return results

        try:
            currencies = await self._covered_currencies()
        except Exception:
            self.logger().network(
                "Error fetching the FXMacroData currency universe.",
                exc_info=True,
                app_warning_msg="Could not reach FXMacroData. Check network connection.",
            )
            return results

        if quote not in currencies:
            self.logger().warning(
                f"FXMacroData does not cover {quote}. "
                f"Set your global token to one of: {', '.join(currencies)}."
            )
            return results

        bases = [currency for currency in currencies if currency != quote]
        responses = await safe_gather(
            *[self._pair_rate(base, quote) for base in bases],
            return_exceptions=True,
        )
        for response in responses:
            if isinstance(response, Exception):
                self.logger().network(
                    "Error fetching a rate from FXMacroData.",
                    exc_info=response,
                    app_warning_msg="Could not fetch a rate from FXMacroData.",
                )
                continue
            trading_pair, rate = response
            if rate is not None:
                results[trading_pair] = rate
        return results

    async def stop_network(self):
        if self._shared_client is not None:
            await self._shared_client.close()
            self._shared_client = None
