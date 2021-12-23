from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../")))

import logging; logging.basicConfig(level=logging.ERROR)
import unittest
from unittest.mock import MagicMock
from decimal import Decimal
from hummingbot.strategy.spot_perpetual_arbitrage.arb_proposal import ArbProposalSide, ArbProposal
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple


class TestSpotPerpetualArbitrage(unittest.TestCase):
    trading_pair = "BTC-USDT"
    base_token, quote_token = trading_pair.split("-")

    def test_arb_proposal(self):
        spot_connector = MagicMock()
        spot_connector.display_name = "Binance"
        spot_market_info = MarketTradingPairTuple(spot_connector, self.trading_pair, self.base_token, self.quote_token)
        perp_connector = MagicMock()
        perp_connector.display_name = "Binance Perpetual"
        perp_market_info = MarketTradingPairTuple(perp_connector, self.trading_pair, self.base_token, self.quote_token)
        spot_side = ArbProposalSide(
            spot_market_info,
            True,
            Decimal(100)
        )
        perp_side = ArbProposalSide(
            perp_market_info,
            False,
            Decimal(110)
        )
        proposal = ArbProposal(spot_side, perp_side, Decimal("1"))
        self.assertEqual(Decimal("0.1"), proposal.profit_pct())
        expected_str = "Spot: Binance: Buy BTC at 100 USDT.\n" \
                       "Perpetual: Binance perpetual: Sell BTC at 110 USDT.\n" \
                       "Order amount: 1\n" \
                       "Profit: 10.00%"
        self.assertEqual(expected_str, str(proposal))
        perp_side = ArbProposalSide(
            perp_market_info,
            True,
            Decimal(110)
        )
        with self.assertRaises(Exception) as context:
            proposal = ArbProposal(spot_side, perp_side, Decimal("1"))
        self.assertEqual('Spot and perpetual arb proposal cannot be on the same side.', str(context.exception))
