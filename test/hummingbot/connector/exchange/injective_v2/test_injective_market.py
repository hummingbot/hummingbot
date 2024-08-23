from decimal import Decimal
from unittest import TestCase

from pyinjective.core.market import DerivativeMarket, SpotMarket
from pyinjective.core.token import Token

from hummingbot.connector.exchange.injective_v2.injective_market import (
    InjectiveDerivativeMarket,
    InjectiveSpotMarket,
    InjectiveToken,
)


class InjectiveSpotMarketTests(TestCase):

    def setUp(self) -> None:
        super().setUp()

        inj_native_token = Token(
            name="Injective Protocol",
            symbol="INJ",
            denom="inj",
            address="",
            decimals=18,
            logo="",
            updated=0,
        )
        self._inj_token = InjectiveToken(
            unique_symbol="INJ",
            native_token=inj_native_token,
        )

        usdt_native_token = Token(
            name="USDT",
            symbol="USDT",
            denom="peggy0xdAC17F958D2ee523a2206206994597C13D831ec7",
            address="",
            decimals=6,
            logo="",
            updated=0,
        )
        self._usdt_token = InjectiveToken(
            unique_symbol="USDT",
            native_token=usdt_native_token,
        )

        inj_usdt_native_market = SpotMarket(
            id="0xa508cb32923323679f29a032c70342c147c17d0145625922b0ef22e955c844c0",  # noqa: mock
            status="active",
            ticker="INJ/USDT",
            base_token=inj_native_token,
            quote_token=usdt_native_token,
            maker_fee_rate=Decimal("-0.0001"),
            taker_fee_rate=Decimal("0.001"),
            service_provider_fee=Decimal("0.4"),
            min_price_tick_size=Decimal("0.000000000000001"),
            min_quantity_tick_size=Decimal("1000000000000000"),
            min_notional=Decimal("1000000"),
        )
        self._inj_usdt_market = InjectiveSpotMarket(
            market_id="0xa508cb32923323679f29a032c70342c147c17d0145625922b0ef22e955c844c0",  # noqa: mock
            base_token=self._inj_token,
            quote_token=self._usdt_token,
            native_market=inj_usdt_native_market,
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

    def test_convert_quantity_from_special_chain_format(self):
        expected_quantity = Decimal("1234")
        chain_quantity = expected_quantity * Decimal(f"1e{self._inj_token.decimals}") * Decimal("1e18")
        converted_quantity = self._inj_usdt_market.quantity_from_special_chain_format(chain_quantity=chain_quantity)

        self.assertEqual(expected_quantity, converted_quantity)

    def test_convert_price_from_special_chain_format(self):
        expected_price = Decimal("15.43")
        chain_price = expected_price * Decimal(f"1e{self._usdt_token.decimals}") / Decimal(f"1e{self._inj_token.decimals}")
        chain_price = chain_price * Decimal("1e18")
        converted_price = self._inj_usdt_market.price_from_special_chain_format(chain_price=chain_price)

        self.assertEqual(expected_price, converted_price)

    def test_min_price_tick_size(self):
        market = self._inj_usdt_market
        expected_value = market.price_from_chain_format(chain_price=Decimal(market.native_market.min_price_tick_size))

        self.assertEqual(expected_value, market.min_price_tick_size())

    def test_min_quantity_tick_size(self):
        market = self._inj_usdt_market
        expected_value = market.quantity_from_chain_format(
            chain_quantity=Decimal(market.native_market.min_quantity_tick_size)
        )

        self.assertEqual(expected_value, market.min_quantity_tick_size())

    def test_min_notional(self):
        market = self._inj_usdt_market
        expected_value = market.native_market.min_notional / Decimal(f"1e{self._usdt_token.decimals}")

        self.assertEqual(expected_value, market.min_notional())


class InjectiveDerivativeMarketTests(TestCase):

    def setUp(self) -> None:
        super().setUp()

        usdt_native_token = Token(
            name="USDT",
            symbol="USDT",
            denom="peggy0xdAC17F958D2ee523a2206206994597C13D831ec7",
            address="",
            decimals=6,
            logo="",
            updated=0,
        )
        self._usdt_token = InjectiveToken(
            unique_symbol="USDT",
            native_token=usdt_native_token,
        )

        inj_usdt_native_market = DerivativeMarket(
            id="0x17ef48032cb24375ba7c2e39f384e56433bcab20cbee9a7357e4cba2eb00abe6",  # noqa: mock
            status="active",
            ticker="INJ/USDT PERP",
            oracle_base="0x2d9315a88f3019f8efa88dfe9c0f0843712da0bac814461e27733f6b83eb51b3",  # noqa: mock
            oracle_quote="0x1fc18861232290221461220bd4e2acd1dcdfbc89c84092c93c18bdc7756c1588",  # noqa: mock
            oracle_type="pyth",
            oracle_scale_factor=6,
            initial_margin_ratio=Decimal("0.195"),
            maintenance_margin_ratio=Decimal("0.05"),
            quote_token=usdt_native_token,
            maker_fee_rate=Decimal("-0.0003"),
            taker_fee_rate=Decimal("0.003"),
            service_provider_fee=Decimal("0.4"),
            min_price_tick_size=Decimal("100"),
            min_quantity_tick_size=Decimal("0.0001"),
            min_notional=Decimal("1000000"),
        )
        self._inj_usdt_derivative_market = InjectiveDerivativeMarket(
            market_id="0x17ef48032cb24375ba7c2e39f384e56433bcab20cbee9a7357e4cba2eb00abe6",  # noqa: mock
            quote_token=self._usdt_token,
            native_market=inj_usdt_native_market,
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

    def test_convert_quantity_from_special_chain_format(self):
        expected_quantity = Decimal("1234")
        chain_quantity = expected_quantity * Decimal("1e18")
        converted_quantity = self._inj_usdt_derivative_market.quantity_from_special_chain_format(
            chain_quantity=chain_quantity)

        self.assertEqual(expected_quantity, converted_quantity)

    def test_convert_price_from_special_chain_format(self):
        expected_price = Decimal("15.43")
        chain_price = expected_price * Decimal(f"1e{self._usdt_token.decimals}") * Decimal("1e18")
        converted_price = self._inj_usdt_derivative_market.price_from_special_chain_format(chain_price=chain_price)

        self.assertEqual(expected_price, converted_price)

    def test_min_price_tick_size(self):
        market = self._inj_usdt_derivative_market
        expected_value = market.price_from_chain_format(chain_price=market.native_market.min_price_tick_size)

        self.assertEqual(expected_value, market.min_price_tick_size())

    def test_min_quantity_tick_size(self):
        market = self._inj_usdt_derivative_market
        expected_value = market.quantity_from_chain_format(
            chain_quantity=market.native_market.min_quantity_tick_size
        )

        self.assertEqual(expected_value, market.min_quantity_tick_size())

    def test_get_oracle_info(self):
        market = self._inj_usdt_derivative_market

        self.assertEqual(market.native_market.oracle_base, market.oracle_base())
        self.assertEqual(market.native_market.oracle_quote, market.oracle_quote())
        self.assertEqual(market.native_market.oracle_type, market.oracle_type())

    def test_min_notional(self):
        market = self._inj_usdt_derivative_market
        expected_value = market.native_market.min_notional / Decimal(f"1e{self._usdt_token.decimals}")

        self.assertEqual(expected_value, market.min_notional())


class InjectiveTokenTests(TestCase):

    def test_convert_value_from_chain_format(self):
        inj_native_token = Token(
            name="Injective Protocol",
            symbol="INJ",
            denom="inj",
            address="",
            decimals=18,
            logo="",
            updated=0,
        )
        token = InjectiveToken(
            unique_symbol="INJ",
            native_token=inj_native_token,
        )

        converted_value = token.value_from_chain_format(chain_value=Decimal("100_000_000_000_000_000_000"))

        self.assertEqual(Decimal("100"), converted_value)
