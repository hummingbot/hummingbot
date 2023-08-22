from decimal import Decimal
from unittest import TestCase

from hummingbot.connector.exchange.injective_v2.injective_market import (
    InjectiveDerivativeMarket,
    InjectiveSpotMarket,
    InjectiveToken,
)


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


class InjectiveDerivativeMarketTests(TestCase):

    def setUp(self) -> None:
        super().setUp()

        self._usdt_token = InjectiveToken(
            denom="peggy0x87aB3B4C8661e07D6372361211B96ed4Dc36B1B5",  # noqa: mock
            symbol="USDT",
            unique_symbol="USDT",
            name="Tether",
            decimals=6,
        )

        self._inj_usdt_derivative_market = InjectiveDerivativeMarket(
            market_id="0x17ef48032cb24375ba7c2e39f384e56433bcab20cbee9a7357e4cba2eb00abe6",  # noqa: mock
            quote_token=self._usdt_token,
            market_info={
                "marketId": "0x17ef48032cb24375ba7c2e39f384e56433bcab20cbee9a7357e4cba2eb00abe6",  # noqa: mock
                "marketStatus": "active",
                "ticker": "INJ/USDT PERP",
                "oracleBase": "0x2d9315a88f3019f8efa88dfe9c0f0843712da0bac814461e27733f6b83eb51b3",  # noqa: mock
                "oracleQuote": "0x1fc18861232290221461220bd4e2acd1dcdfbc89c84092c93c18bdc7756c1588",  # noqa: mock
                "oracleType": "pyth",
                "oracleScaleFactor": 6,
                "initialMarginRatio": "0.195",
                "maintenanceMarginRatio": "0.05",
                "quoteDenom": "peggy0x87aB3B4C8661e07D6372361211B96ed4Dc36B1B5",
                "quoteTokenMeta": {
                    "name": "Testnet Tether USDT",
                    "address": "0x0000000000000000000000000000000000000000",
                    "symbol": "USDT",
                    "logo": "https://static.alchemyapi.io/images/assets/825.png",
                    "decimals": 6,
                    "updatedAt": "1687190809716"
                },
                "makerFeeRate": "-0.0003",
                "takerFeeRate": "0.003",
                "serviceProviderFee": "0.4",
                "isPerpetual": True,
                "minPriceTickSize": "100",
                "minQuantityTickSize": "0.0001",
                "perpetualMarketInfo": {
                    "hourlyFundingRateCap": "0.000625",
                    "hourlyInterestRate": "0.00000416666",
                    "nextFundingTimestamp": "1690318800",
                    "fundingInterval": "3600"
                },
                "perpetualMarketFunding": {
                    "cumulativeFunding": "81363.592243119007273334",
                    "cumulativePrice": "1.432536051546776736",
                    "lastTimestamp": "1689423842"
                }
            }
        )

    def test_trading_pair(self):
        self.assertEqual("INJ-USDT", self._inj_usdt_derivative_market.trading_pair())

    def test_convert_quantity_from_chain_format(self):
        expected_quantity = Decimal("1234")
        chain_quantity = expected_quantity
        converted_quantity = self._inj_usdt_derivative_market.quantity_from_chain_format(chain_quantity=chain_quantity)

        self.assertEqual(expected_quantity, converted_quantity)

    def test_convert_price_from_chain_format(self):
        expected_price = Decimal("15.43")
        chain_price = expected_price * Decimal(f"1e{self._usdt_token.decimals}")
        converted_price = self._inj_usdt_derivative_market.price_from_chain_format(chain_price=chain_price)

        self.assertEqual(expected_price, converted_price)

    def test_min_price_tick_size(self):
        market = self._inj_usdt_derivative_market
        expected_value = market.price_from_chain_format(chain_price=Decimal(market.market_info["minPriceTickSize"]))

        self.assertEqual(expected_value, market.min_price_tick_size())

    def test_min_quantity_tick_size(self):
        market = self._inj_usdt_derivative_market
        expected_value = market.quantity_from_chain_format(
            chain_quantity=Decimal(market.market_info["minQuantityTickSize"])
        )

        self.assertEqual(expected_value, market.min_quantity_tick_size())

    def test_get_oracle_info(self):
        market = self._inj_usdt_derivative_market

        self.assertEqual(market.market_info["oracleBase"], market.oracle_base())
        self.assertEqual(market.market_info["oracleQuote"], market.oracle_quote())
        self.assertEqual(market.market_info["oracleType"], market.oracle_type())

    def test_next_funding_timestamp(self):
        market = self._inj_usdt_derivative_market

        self.assertEqual(
            int(market.market_info["perpetualMarketInfo"]["nextFundingTimestamp"]),
            market.next_funding_timestamp()
        )


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
