import unittest

from hummingbot.connector.exchange.xrpl.xrpl_utils import XRPLMarket

BTC_ISSUER = "rvYAfWj5gh67oV6fW32ZzP3Aw4Eubs59B"  # noqa: mock
SOLO_ISSUER = "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz"  # noqa: mock


class XRPLMarketGetTokenSymbolTests(unittest.TestCase):
    """``trading_pair_symbol`` is an optional alias, not a precondition for matching.

    ``_update_balances`` resolves every trustline the ledger returns through
    ``get_token_symbol`` and skips the balance when it comes back None. Returning None
    for any market without an alias therefore dropped real on-ledger holdings out of
    balances and portfolio entirely — not shown at zero, absent. Entries in
    ``custom_markets`` are written without an alias unless the user knows to add one,
    including the ``SOLO-XRP`` example that ships as the field's own default.
    """

    def setUp(self):
        self.market = XRPLMarket(base="BTC", quote="XRP", base_issuer=BTC_ISSUER, quote_issuer="")
        self.aliased = XRPLMarket(
            base="BTC",
            quote="XRP",
            base_issuer=BTC_ISSUER,
            quote_issuer="",
            trading_pair_symbol="WBTC-XRP",
        )

    def test_base_resolves_without_an_alias(self):
        self.assertEqual(self.market.get_token_symbol("BTC", BTC_ISSUER), "BTC")

    def test_quote_resolves_without_an_alias(self):
        self.assertEqual(self.market.get_token_symbol("XRP", ""), "XRP")

    def test_an_alias_still_takes_precedence(self):
        self.assertEqual(self.aliased.get_token_symbol("BTC", BTC_ISSUER), "WBTC")
        self.assertEqual(self.aliased.get_token_symbol("XRP", ""), "XRP")

    def test_a_different_issuer_is_not_a_match(self):
        """Same currency code from another gateway is a different asset."""
        self.assertIsNone(self.market.get_token_symbol("BTC", SOLO_ISSUER))

    def test_an_unknown_code_is_not_a_match(self):
        self.assertIsNone(self.market.get_token_symbol("DOGE", BTC_ISSUER))

    def test_matching_is_case_insensitive(self):
        self.assertEqual(self.market.get_token_symbol("btc", BTC_ISSUER.lower()), "BTC")

    def test_the_symbol_is_uppercase(self):
        lowercase = XRPLMarket(base="btc", quote="xrp", base_issuer=BTC_ISSUER, quote_issuer="")
        self.assertEqual(lowercase.get_token_symbol("BTC", BTC_ISSUER), "BTC")

    def test_two_issuers_of_one_currency_code_stay_distinct(self):
        """The fallback returns the currency code, so it is worth pinning that a market
        still only answers for its own issuer. Two gateways issuing "BTC" are different
        assets, and each market matches exactly one of them."""
        theirs = XRPLMarket(base="BTC", quote="XRP", base_issuer=SOLO_ISSUER, quote_issuer="")

        self.assertEqual(self.market.get_token_symbol("BTC", BTC_ISSUER), "BTC")
        self.assertIsNone(self.market.get_token_symbol("BTC", SOLO_ISSUER))
        self.assertEqual(theirs.get_token_symbol("BTC", SOLO_ISSUER), "BTC")
        self.assertIsNone(theirs.get_token_symbol("BTC", BTC_ISSUER))

    def test_the_shipped_default_market_resolves(self):
        """The SOLO-XRP entry that XRPLConfigMap.custom_markets defaults to carries no
        alias, so before this fix the connector's own default configuration dropped
        SOLO balances."""
        from hummingbot.connector.exchange.xrpl.xrpl_utils import XRPLConfigMap

        default_markets = XRPLConfigMap.model_fields["custom_markets"].default
        solo = default_markets["SOLO-XRP"]
        self.assertIsNone(solo.trading_pair_symbol)
        self.assertEqual(solo.get_token_symbol("SOLO", SOLO_ISSUER), "SOLO")


if __name__ == "__main__":
    unittest.main()
