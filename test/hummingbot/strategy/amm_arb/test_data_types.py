from decimal import Decimal
from unittest import TestCase
from unittest.mock import MagicMock

from hummingbot.core.utils.fixed_rate_source import FixedRateSource
from hummingbot.strategy.amm_arb.data_types import ArbProposalSide, ArbProposal
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple


class ArbProposalTests(TestCase):

    def test_profit_is_cero_when_no_available_sell_to_buy_quote_rate(self):
        buy_market = MagicMock()
        buy_market_info = MarketTradingPairTuple(buy_market, "BTC-USDT", "BTC", "USDT")
        sell_market = MagicMock()
        sell_market_info = MarketTradingPairTuple(sell_market, "BTC-DAI", "BTC", "DAI")

        buy_side = ArbProposalSide(
            buy_market_info,
            True,
            Decimal(30000),
            Decimal(30000),
            Decimal(10)
        )
        sell_side = ArbProposalSide(
            sell_market_info,
            False,
            Decimal(32000),
            Decimal(32000),
            Decimal(10)
        )

        proposal = ArbProposal(buy_side, sell_side)

        self.assertEqual(proposal.profit_pct(), Decimal(0))

    def test_profit_without_fees_for_same_trading_pair(self):
        buy_market = MagicMock()
        buy_market_info = MarketTradingPairTuple(buy_market, "BTC-USDT", "BTC", "USDT")
        sell_market = MagicMock()
        sell_market_info = MarketTradingPairTuple(sell_market, "BTC-USDT", "BTC", "USDT")

        buy_side = ArbProposalSide(
            buy_market_info,
            True,
            Decimal(30000),
            Decimal(30000),
            Decimal(10)
        )
        sell_side = ArbProposalSide(
            sell_market_info,
            False,
            Decimal(32000),
            Decimal(32000),
            Decimal(10)
        )

        proposal = ArbProposal(buy_side, sell_side)

        self.assertEqual(proposal.profit_pct(), Decimal(2000) / buy_side.quote_price)

    def test_profit_without_fees_for_different_quotes_trading_pairs(self):
        buy_market = MagicMock()
        buy_market_info = MarketTradingPairTuple(buy_market, "BTC-USDT", "BTC", "USDT")
        sell_market = MagicMock()
        sell_market_info = MarketTradingPairTuple(sell_market, "BTC-ETH", "BTC", "ETH")

        buy_side = ArbProposalSide(
            buy_market_info,
            True,
            Decimal(30000),
            Decimal(30000),
            Decimal(10)
        )
        sell_side = ArbProposalSide(
            sell_market_info,
            False,
            Decimal(10),
            Decimal(10),
            Decimal(10)
        )

        proposal = ArbProposal(buy_side, sell_side)

        rate_source = FixedRateSource()
        rate_source.add_rate("BTC-USDT", Decimal(30000))
        rate_source.add_rate("BTC-ETH", Decimal(10))
        rate_source.add_rate("ETH-USDT", Decimal(3000))

        expected_sell_result = sell_side.amount * sell_side.quote_price
        sell_quote_to_buy_quote_rate = rate_source.rate("ETH-USDT")
        adjusted_sell_result = expected_sell_result * sell_quote_to_buy_quote_rate

        expected_buy_result = buy_side.amount * buy_side.quote_price

        expected_profit_pct = (adjusted_sell_result - expected_buy_result) / expected_buy_result

        profit = proposal.profit_pct(account_for_fee=False,
                                     rate_source=rate_source)

        self.assertEqual(profit, expected_profit_pct)
