from decimal import Decimal
from unittest import TestCase

from hummingbot.connector.exchange.injective_v2.injective_market import InjectiveSpotMarket, InjectiveToken


class InjectiveSpotMarketTests(TestCase):

    def setUp(self) -> None:
        super().setUp()

        self._inj_token = InjectiveToken(
            denom="inj",
            symbol="INJ",
            unique_symbol="INJ",
            name="Injective Protocol",
            decimals=18,
        )
        self._usdt_token = InjectiveToken(
            denom="peggy0xdAC17F958D2ee523a2206206994597C13D831ec7",  # noqa: mock
            symbol="USDT",
            unique_symbol="USDT",
            name="Tether",
            decimals=6,
        )

        self._inj_usdt_market = InjectiveSpotMarket(
            market_id="0xa508cb32923323679f29a032c70342c147c17d0145625922b0ef22e955c844c0",  # noqa: mock
            base_token=self._inj_token,
            quote_token=self._usdt_token,
            market_info={
                "marketId": "0xa508cb32923323679f29a032c70342c147c17d0145625922b0ef22e955c844c0",  # noqa: mock
                "marketStatus": "active",
                "ticker": "INJ/USDT",
                "baseDenom": "inj",
                "baseTokenMeta": {
                    "name": "Injective Protocol",
                    "address": "0xe28b3B32B6c345A34Ff64674606124Dd5Aceca30",
                    "symbol": "INJ",
                    "logo": "https://static.alchemyapi.io/images/assets/7226.png",
                    "decimals": 18,
                    "updatedAt": "1685371052879"
                },
                "quoteDenom": "peggy0xdAC17F958D2ee523a2206206994597C13D831ec7",
                "quoteTokenMeta": {
                    "name": "Tether",
                    "address": "0xdAC17F958D2ee523a2206206994597C13D831ec7",  # noqa: mock
                    "symbol": "USDT",
                    "logo": "https://static.alchemyapi.io/images/assets/825.png",
                    "decimals": 6,
                    "updatedAt": "1685371052879"
                },
                "makerFeeRate": "-0.0001",
                "takerFeeRate": "0.001",
                "serviceProviderFee": "0.4",
                "minPriceTickSize": "0.000000000000001",
                "minQuantityTickSize": "1000000000000000"
            }
        )

    def test_trading_pair(self):
        self.assertEqual("INJ-USDT", self._inj_usdt_market.trading_pair())

    def test_convert_quantity_from_chain_format(self):
        expected_quantity = Decimal("1234")
        chain_quantity = expected_quantity * Decimal(f"1e{self._inj_token.decimals}")
        converted_quantity = self._inj_usdt_market.quantity_from_chain_format(chain_quantity=chain_quantity)

        self.assertEqual(expected_quantity, converted_quantity)

    def test_convert_price_from_chain_format(self):
        expected_price = Decimal("15.43")
        chain_price = expected_price * Decimal(f"1e{self._usdt_token.decimals}") / Decimal(f"1e{self._inj_token.decimals}")
        converted_price = self._inj_usdt_market.price_from_chain_format(chain_price=chain_price)

        self.assertEqual(expected_price, converted_price)

    def test_min_price_tick_size(self):
        market = self._inj_usdt_market
        expected_value = market.price_from_chain_format(chain_price=Decimal(market.market_info["minPriceTickSize"]))

        self.assertEqual(expected_value, market.min_price_tick_size())

    def test_min_quantity_tick_size(self):
        market = self._inj_usdt_market
        expected_value = market.quantity_from_chain_format(
            chain_quantity=Decimal(market.market_info["minQuantityTickSize"])
        )

        self.assertEqual(expected_value, market.min_quantity_tick_size())


class InjectiveTokenTests(TestCase):

    def test_convert_value_from_chain_format(self):
        token = InjectiveToken(
            denom="inj",
            symbol="INJ",
            unique_symbol="INJ",
            name="Injective Protocol",
            decimals=18,
        )

        converted_value = token.value_from_chain_format(chain_value=Decimal("100_000_000_000_000_000_000"))

        self.assertEqual(Decimal("100"), converted_value)
