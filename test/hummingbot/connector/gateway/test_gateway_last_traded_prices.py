import unittest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.connector.gateway.gateway import Gateway


class GatewayLastTradedPricesTests(unittest.IsolatedAsyncioTestCase):
    """Gateway must expose the plural get_last_traded_prices fan-out.

    ExchangeBase provides it for order-book connectors, but Gateway extends
    ConnectorBase directly and so never inherited it -- leaving the per-pair
    _get_last_traded_price with no caller, and every consumer of the plural form
    (Hummingbot API's market-data route among them) raising AttributeError.
    """

    PAIR = "ANSEM-SOL"
    OTHER_PAIR = "SOL-USDC"

    def setUp(self):
        self.connector = Gateway.__new__(Gateway)
        self.connector._logger = MagicMock()

    async def test_returns_a_price_per_pair(self):
        with patch.object(Gateway, "_get_last_traded_price", new_callable=AsyncMock) as mock_price:
            mock_price.side_effect = [1.5, 200.0]
            prices = await self.connector.get_last_traded_prices([self.PAIR, self.OTHER_PAIR])

        self.assertEqual({self.PAIR: 1.5, self.OTHER_PAIR: 200.0}, prices)

    async def test_unpriceable_pair_is_omitted_not_zeroed(self):
        """A caller must be able to tell "no price" from "the price is 0"."""
        with patch.object(Gateway, "_get_last_traded_price", new_callable=AsyncMock) as mock_price:
            mock_price.side_effect = [0.0, 200.0]
            prices = await self.connector.get_last_traded_prices([self.PAIR, self.OTHER_PAIR])

        self.assertNotIn(self.PAIR, prices)
        self.assertEqual(200.0, prices[self.OTHER_PAIR])

    async def test_one_failing_pair_does_not_sink_the_others(self):
        with patch.object(Gateway, "_get_last_traded_price", new_callable=AsyncMock) as mock_price:
            mock_price.side_effect = [RuntimeError("gateway unreachable"), 200.0]
            prices = await self.connector.get_last_traded_prices([self.PAIR, self.OTHER_PAIR])

        self.assertNotIn(self.PAIR, prices)
        self.assertEqual(200.0, prices[self.OTHER_PAIR])

    async def test_falls_back_to_a_quote_when_the_oracle_is_empty(self):
        """The oracle only holds pairs MarketDataProvider tracks; quote the rest."""
        with patch("hummingbot.connector.gateway.gateway.RateOracle") as mock_oracle, \
             patch.object(Gateway, "get_quote_price", new_callable=AsyncMock) as mock_quote:
            mock_oracle.get_instance.return_value.get_pair_rate.return_value = None
            mock_quote.return_value = Decimal("0.000000028336")

            price = await self.connector._get_last_traded_price(self.PAIR)

        mock_quote.assert_awaited_once()
        self.assertAlmostEqual(2.8336e-8, price)

    async def test_cached_rate_is_preferred_over_a_quote(self):
        with patch("hummingbot.connector.gateway.gateway.RateOracle") as mock_oracle, \
             patch.object(Gateway, "get_quote_price", new_callable=AsyncMock) as mock_quote:
            mock_oracle.get_instance.return_value.get_pair_rate.return_value = Decimal("1.5")

            price = await self.connector._get_last_traded_price(self.PAIR)

        mock_quote.assert_not_awaited()
        self.assertEqual(1.5, price)
