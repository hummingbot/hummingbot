"""
Chunk 1: Trading Rules & Formatting tests for XrplExchange.

Covers:
  - _format_trading_rules
  - _format_trading_pair_fee_rules
  - _make_trading_rules_request  (with retry logic)
  - _make_trading_rules_request_impl
  - _update_trading_rules
  - _make_xrpl_trading_pairs_request
  - _initialize_trading_pair_symbols_from_exchange_info
  - _update_trading_fees
"""

from decimal import Decimal
from test.hummingbot.connector.exchange.xrpl.test_xrpl_exchange_base import XRPLExchangeTestBase
from unittest.async_case import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from xrpl.models.requests.request import RequestMethod

from hummingbot.connector.exchange.xrpl import xrpl_constants as CONSTANTS
from hummingbot.connector.exchange.xrpl.xrpl_utils import PoolInfo, XRPLMarket
from hummingbot.connector.trading_rule import TradingRule


class TestXRPLExchangeTradingRules(XRPLExchangeTestBase, IsolatedAsyncioTestCase):
    """Tests for trading-rule formatting, fetching, and update flows."""

    # ------------------------------------------------------------------ #
    # _format_trading_rules
    # ------------------------------------------------------------------ #

    def test_format_trading_rules(self):
        """Migrate from monolith: test_format_trading_rules (line 1793)."""
        trading_rules_info = {
            "XRP-USD": {
                "base_tick_size": 8,
                "quote_tick_size": 8,
                "minimum_order_size": 0.01,
            }
        }

        result = self.connector._format_trading_rules(trading_rules_info)

        expected = TradingRule(
            trading_pair="XRP-USD",
            min_order_size=Decimal(0.01),
            min_price_increment=Decimal("1e-8"),
            min_quote_amount_increment=Decimal("1e-8"),
            min_base_amount_increment=Decimal("1e-8"),
            min_notional_size=Decimal("1e-8"),
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].min_order_size, expected.min_order_size)
        self.assertEqual(result[0].min_price_increment, expected.min_price_increment)
        self.assertEqual(result[0].min_quote_amount_increment, expected.min_quote_amount_increment)
        self.assertEqual(result[0].min_base_amount_increment, expected.min_base_amount_increment)
        self.assertEqual(result[0].min_notional_size, expected.min_notional_size)

    def test_format_trading_rules_multiple_pairs(self):
        """New: formatting works for several pairs with different tick sizes."""
        trading_rules_info = {
            "SOLO-XRP": {
                "base_tick_size": 15,
                "quote_tick_size": 6,
                "minimum_order_size": 1e-6,
            },
            "SOLO-USD": {
                "base_tick_size": 15,
                "quote_tick_size": 15,
                "minimum_order_size": 1e-15,
            },
        }

        result = self.connector._format_trading_rules(trading_rules_info)

        self.assertEqual(len(result), 2)
        solo_xrp = result[0]
        solo_usd = result[1]

        self.assertEqual(solo_xrp.trading_pair, "SOLO-XRP")
        self.assertEqual(solo_xrp.min_base_amount_increment, Decimal("1e-15"))
        self.assertEqual(solo_xrp.min_price_increment, Decimal("1e-6"))

        self.assertEqual(solo_usd.trading_pair, "SOLO-USD")
        self.assertEqual(solo_usd.min_base_amount_increment, Decimal("1e-15"))
        self.assertEqual(solo_usd.min_price_increment, Decimal("1e-15"))

    def test_format_trading_rules_empty_input(self):
        """New: empty dict produces empty list."""
        result = self.connector._format_trading_rules({})
        self.assertEqual(result, [])

    # ------------------------------------------------------------------ #
    # _format_trading_pair_fee_rules
    # ------------------------------------------------------------------ #

    async def test_format_trading_pair_fee_rules(self):
        """Migrate from monolith: test_format_trading_pair_fee_rules (line 1815)."""
        trading_rules_info = {
            "XRP-USD": {
                "base_transfer_rate": 0.01,
                "quote_transfer_rate": 0.01,
            }
        }

        result = self.connector._format_trading_pair_fee_rules(trading_rules_info)

        expected = [
            {
                "trading_pair": "XRP-USD",
                "base_token": "XRP",
                "quote_token": "USD",
                "base_transfer_rate": 0.01,
                "quote_transfer_rate": 0.01,
                "amm_pool_fee": Decimal("0"),
            }
        ]

        self.assertEqual(result, expected)

    def test_format_trading_pair_fee_rules_with_amm_pool(self):
        """New: amm_pool_info present → fee_pct / 100 is used."""
        from xrpl.models import XRP, IssuedCurrency

        pool_info = PoolInfo(
            address="rAMMPool123",
            base_token_address=XRP(),
            quote_token_address=IssuedCurrency(
                currency="534F4C4F00000000000000000000000000000000",
                issuer="rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",
            ),
            lp_token_address=IssuedCurrency(
                currency="039C99CD9AB0B70B32ECDA51EAAE471625608EA2",
                issuer="rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",
            ),
            fee_pct=Decimal("0.5"),
            price=Decimal("0.004"),
            base_token_amount=Decimal("268924465"),
            quote_token_amount=Decimal("23.4649097465469"),
            lp_token_amount=Decimal("79170.1044740602"),
        )

        trading_rules_info = {
            "SOLO-XRP": {
                "base_transfer_rate": 9.999e-05,
                "quote_transfer_rate": 0,
                "amm_pool_info": pool_info,
            }
        }

        result = self.connector._format_trading_pair_fee_rules(trading_rules_info)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["trading_pair"], "SOLO-XRP")
        self.assertEqual(result[0]["amm_pool_fee"], Decimal("0.5") / Decimal("100"))

    def test_format_trading_pair_fee_rules_empty(self):
        """New: empty dict produces empty list."""
        result = self.connector._format_trading_pair_fee_rules({})
        self.assertEqual(result, [])

    # ------------------------------------------------------------------ #
    # _make_trading_rules_request  (with retry + _impl)
    # ------------------------------------------------------------------ #

    async def test_make_trading_rules_request(self):
        """Rewrite from monolith: test_make_trading_rules_request (line 2013).

        Uses _query_xrpl mock instead of mock_client.request.
        """
        async def _dispatch(request, priority=None, timeout=None):
            if hasattr(request, "method"):
                if request.method == RequestMethod.ACCOUNT_INFO:
                    return self._client_response_account_info_issuer()
                elif request.method == RequestMethod.AMM_INFO:
                    return self._client_response_amm_info()
            raise ValueError(f"Unexpected request: {request}")

        self._mock_query_xrpl(side_effect=_dispatch)

        result = await self.connector._make_trading_rules_request()

        # Validate SOLO-XRP
        self.assertEqual(
            result["SOLO-XRP"]["base_currency"].currency,
            "534F4C4F00000000000000000000000000000000",
        )
        self.assertEqual(
            result["SOLO-XRP"]["base_currency"].issuer,
            "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",
        )
        self.assertEqual(result["SOLO-XRP"]["base_tick_size"], 15)
        self.assertEqual(result["SOLO-XRP"]["quote_tick_size"], 6)
        self.assertEqual(result["SOLO-XRP"]["base_transfer_rate"], 9.999999999998899e-05)
        self.assertEqual(result["SOLO-XRP"]["quote_transfer_rate"], 0)
        self.assertEqual(result["SOLO-XRP"]["minimum_order_size"], 1e-06)
        self.assertEqual(result["SOLO-XRP"]["amm_pool_info"].fee_pct, Decimal("0.5"))

        # Validate SOLO-USD entry exists
        self.assertEqual(
            result["SOLO-USD"]["base_currency"].currency,
            "534F4C4F00000000000000000000000000000000",
        )
        self.assertEqual(result["SOLO-USD"]["quote_currency"].currency, "USD")

    async def test_make_trading_rules_request_error(self):
        """Rewrite from monolith: test_make_trading_rules_request_error (line 2049).

        When an issuer account is not found in the ledger, raises ValueError.
        """
        async def _dispatch(request, priority=None, timeout=None):
            if hasattr(request, "method"):
                if request.method == RequestMethod.ACCOUNT_INFO:
                    return self._client_response_account_info_issuer_error()
            raise ValueError(f"Unexpected request: {request}")

        self._mock_query_xrpl(side_effect=_dispatch)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with self.assertRaises(ValueError) as ctx:
                await self.connector._make_trading_rules_request()
            self.assertIn("not found in ledger:", str(ctx.exception))

    async def test_make_trading_rules_request_retries_on_transient_failure(self):
        """New: retry logic retries up to 3 times with backoff."""
        call_count = 0

        async def _dispatch(request, priority=None, timeout=None):
            nonlocal call_count
            if hasattr(request, "method"):
                if request.method == RequestMethod.ACCOUNT_INFO:
                    call_count += 1
                    if call_count <= 2:
                        raise ConnectionError("Transient failure")
                    return self._client_response_account_info_issuer()
                elif request.method == RequestMethod.AMM_INFO:
                    return self._client_response_amm_info()
            raise ValueError(f"Unexpected request: {request}")

        self._mock_query_xrpl(side_effect=_dispatch)

        # Patch asyncio.sleep to avoid actual waiting
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await self.connector._make_trading_rules_request()

        self.assertIn("SOLO-XRP", result)
        # account_info called 3+ times (2 fails + 1 success, then again for SOLO-USD pair)
        self.assertGreaterEqual(call_count, 3)

    async def test_make_trading_rules_request_all_retries_exhausted(self):
        """New: after 3 failures the error is raised."""
        async def _dispatch(request, priority=None, timeout=None):
            raise ConnectionError("Persistent failure")

        self._mock_query_xrpl(side_effect=_dispatch)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with self.assertRaises(ConnectionError):
                await self.connector._make_trading_rules_request()

    async def test_make_trading_rules_request_none_trading_pairs(self):
        """New: when _trading_pairs is None, ValueError is raised."""
        self.connector._trading_pairs = None
        self._mock_query_xrpl()

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with self.assertRaises(ValueError) as ctx:
                await self.connector._make_trading_rules_request()
            self.assertIn("Trading pairs list cannot be None", str(ctx.exception))

    # ------------------------------------------------------------------ #
    # _update_trading_rules
    # ------------------------------------------------------------------ #

    async def test_update_trading_rules(self):
        """New: _update_trading_rules fetches, formats, and stores rules + fee rules."""
        async def _dispatch(request, priority=None, timeout=None):
            if hasattr(request, "method"):
                if request.method == RequestMethod.ACCOUNT_INFO:
                    return self._client_response_account_info_issuer()
                elif request.method == RequestMethod.AMM_INFO:
                    return self._client_response_amm_info()
            raise ValueError(f"Unexpected request: {request}")

        self._mock_query_xrpl(side_effect=_dispatch)

        # Clear pre-existing rules set in setUp
        self.connector._trading_rules.clear()
        self.connector._trading_pair_fee_rules.clear()

        await self.connector._update_trading_rules()

        # Trading rules should now be populated for both trading pairs
        self.assertIn("SOLO-XRP", self.connector._trading_rules)
        self.assertIn("SOLO-USD", self.connector._trading_rules)

        solo_xrp_rule = self.connector._trading_rules["SOLO-XRP"]
        self.assertEqual(solo_xrp_rule.min_price_increment, Decimal("1e-6"))  # XRP has 6 decimals
        self.assertEqual(solo_xrp_rule.min_base_amount_increment, Decimal("1e-15"))

        # Fee rules populated
        self.assertIn("SOLO-XRP", self.connector._trading_pair_fee_rules)
        self.assertIn("SOLO-USD", self.connector._trading_pair_fee_rules)

        solo_xrp_fee = self.connector._trading_pair_fee_rules["SOLO-XRP"]
        self.assertEqual(solo_xrp_fee["base_transfer_rate"], 9.999999999998899e-05)
        self.assertEqual(solo_xrp_fee["quote_transfer_rate"], 0)

        # Symbol map should be populated too
        self.assertTrue(self.connector.trading_pair_symbol_map_ready())

    # ------------------------------------------------------------------ #
    # _make_xrpl_trading_pairs_request
    # ------------------------------------------------------------------ #

    def test_make_xrpl_trading_pairs_request(self):
        """New: returns default MARKETS merged with any custom_markets."""
        result = self.connector._make_xrpl_trading_pairs_request()

        # Should contain all CONSTANTS.MARKETS entries
        for key in CONSTANTS.MARKETS:
            self.assertIn(key, result)
            market = result[key]
            self.assertIsInstance(market, XRPLMarket)
            self.assertEqual(market.base, CONSTANTS.MARKETS[key]["base"])
            self.assertEqual(market.quote, CONSTANTS.MARKETS[key]["quote"])

    def test_make_xrpl_trading_pairs_request_with_custom_markets(self):
        """New: custom markets override / add to default ones."""
        custom = XRPLMarket(
            base="BTC",
            base_issuer="rBTCissuer",
            quote="XRP",
            quote_issuer="",
            trading_pair_symbol="BTC-XRP",
        )
        self.connector._custom_markets["BTC-XRP"] = custom

        result = self.connector._make_xrpl_trading_pairs_request()

        self.assertIn("BTC-XRP", result)
        self.assertEqual(result["BTC-XRP"].base, "BTC")

    # ------------------------------------------------------------------ #
    # _initialize_trading_pair_symbols_from_exchange_info
    # ------------------------------------------------------------------ #

    def test_initialize_trading_pair_symbols_from_exchange_info(self):
        """New: populates the trading pair symbol map from exchange info dict."""
        exchange_info = {
            "FOO-BAR": XRPLMarket(
                base="FOO",
                base_issuer="rFoo",
                quote="BAR",
                quote_issuer="rBar",
                trading_pair_symbol="FOO-BAR",
            ),
            "baz-qux": XRPLMarket(
                base="BAZ",
                base_issuer="rBaz",
                quote="QUX",
                quote_issuer="rQux",
                trading_pair_symbol="baz-qux",
            ),
        }

        self.connector._initialize_trading_pair_symbols_from_exchange_info(exchange_info)

        # After initialization, the symbol map should be ready
        self.assertTrue(self.connector.trading_pair_symbol_map_ready())

    # ------------------------------------------------------------------ #
    # _update_trading_fees
    # ------------------------------------------------------------------ #

    async def test_update_trading_fees(self):
        """New: currently a no-op (pass), but we verify it doesn't raise."""
        await self.connector._update_trading_fees()
        # No exception means success; method is a TODO stub.
