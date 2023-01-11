from decimal import Decimal
from unittest import TestCase
from unittest.mock import MagicMock, patch

from hummingbot.core.data_type.trade_fee import TradeFeeSchema
from hummingbot.core.utils.fixed_rate_source import FixedRateSource
from hummingbot.strategy.amm_arb.data_types import ArbProposal, ArbProposalSide, TokenAmount
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple


class ArbProposalTests(TestCase):

    level = 0
    log_records = []

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.buy_market = MagicMock()
        self.sell_market = MagicMock()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    def test_profit_is_zero_when_no_available_sell_to_buy_quote_rate(self):
        buy_market_info = MarketTradingPairTuple(self.buy_market, "BTC-USDT", "BTC", "USDT")
        sell_market_info = MarketTradingPairTuple(self.sell_market, "BTC-DAI", "BTC", "DAI")

        buy_side = ArbProposalSide(
            buy_market_info,
            True,
            Decimal(30000),
            Decimal(30000),
            Decimal(10),
            []
        )
        sell_side = ArbProposalSide(
            sell_market_info,
            False,
            Decimal(32000),
            Decimal(32000),
            Decimal(10),
            []
        )

        proposal = ArbProposal(buy_side, sell_side)
        proposal.logger().setLevel(1)
        proposal.logger().addHandler(self)

        self.assertEqual(proposal.profit_pct(), Decimal(0))
        self.assertTrue(self._is_logged('WARNING',
                                        ("The arbitrage proposal profitability could not be calculated due to"
                                         " a missing rate (BTC-BTC=1, DAI-USDT=None)")))

    def test_profit_without_fees_for_same_trading_pair(self):
        buy_market_info = MarketTradingPairTuple(self.buy_market, "BTC-USDT", "BTC", "USDT")
        sell_market_info = MarketTradingPairTuple(self.sell_market, "BTC-USDT", "BTC", "USDT")

        buy_side = ArbProposalSide(
            buy_market_info,
            True,
            Decimal(30000),
            Decimal(30000),
            Decimal(10),
            []
        )
        sell_side = ArbProposalSide(
            sell_market_info,
            False,
            Decimal(32000),
            Decimal(32000),
            Decimal(10),
            []
        )

        proposal = ArbProposal(buy_side, sell_side)

        self.assertEqual(proposal.profit_pct(), Decimal(2000) / buy_side.quote_price)

    def test_profit_without_fees_for_different_quotes_trading_pairs(self):
        buy_market_info = MarketTradingPairTuple(self.buy_market, "BTC-USDT", "BTC", "USDT")
        sell_market_info = MarketTradingPairTuple(self.sell_market, "BTC-ETH", "BTC", "ETH")

        buy_side = ArbProposalSide(
            buy_market_info,
            True,
            Decimal(30000),
            Decimal(30000),
            Decimal(10),
            []
        )
        sell_side = ArbProposalSide(
            sell_market_info,
            False,
            Decimal(10),
            Decimal(10),
            Decimal(10),
            []
        )

        proposal = ArbProposal(buy_side, sell_side)

        rate_source = FixedRateSource()
        rate_source.add_rate("BTC-USDT", Decimal(30000))
        rate_source.add_rate("BTC-ETH", Decimal(10))
        rate_source.add_rate("ETH-USDT", Decimal(3000))

        expected_sell_result = sell_side.amount * sell_side.quote_price
        sell_quote_to_buy_quote_rate = rate_source.get_pair_rate("ETH-USDT")
        adjusted_sell_result = expected_sell_result * sell_quote_to_buy_quote_rate

        expected_buy_result = buy_side.amount * buy_side.quote_price

        expected_profit_pct = (adjusted_sell_result - expected_buy_result) / expected_buy_result

        profit = proposal.profit_pct(account_for_fee=False,
                                     rate_source=rate_source)

        self.assertEqual(profit, expected_profit_pct)

    def test_profit_without_fees_for_different_base_trading_pairs_and_different_amount_on_sides(self):
        """
        If the amount is different on both sides and the base tokens are different, then
        the profit calculation should not apply the conversion rate for the base tokens because
        the different orders of magnitude for the tokens might have been considered when configuring
        the arbitrage sides.
        """
        buy_market_info = MarketTradingPairTuple(self.buy_market, "BTC-USDT", "BTC", "USDT")
        sell_market_info = MarketTradingPairTuple(self.sell_market, "XRP-USDT", "XRP", "USDT")

        buy_side = ArbProposalSide(
            buy_market_info,
            True,
            Decimal(30000),
            Decimal(30000),
            Decimal(10),
            []
        )
        sell_side = ArbProposalSide(
            sell_market_info,
            False,
            Decimal(1.1),
            Decimal(1.1),
            Decimal(27000),
            []
        )

        proposal = ArbProposal(buy_side, sell_side)

        rate_source = FixedRateSource()
        rate_source.add_rate("BTC-USDT", Decimal(30000))
        rate_source.add_rate("BTC-XRP", Decimal(27000))

        expected_sell_result = sell_side.amount * sell_side.quote_price

        expected_buy_result = buy_side.amount * buy_side.quote_price
        expected_profit_pct = (expected_sell_result - expected_buy_result) / expected_buy_result

        profit = proposal.profit_pct(account_for_fee=False,
                                     rate_source=rate_source)

        self.assertEqual(profit, expected_profit_pct)

    @patch("hummingbot.client.config.trade_fee_schema_loader.TradeFeeSchemaLoader.configured_schema_for_exchange",
           return_value=TradeFeeSchema())
    def test_profit_with_network_fees(self, _):
        buy_market_info = MarketTradingPairTuple(self.buy_market, "WETH-DAI", "WETH", "DAI")
        sell_market_info = MarketTradingPairTuple(self.sell_market, "ETH-USDT", "ETH", "USDT")

        buy_side = ArbProposalSide(
            buy_market_info,
            True,
            Decimal("3300"),
            Decimal("3300"),
            Decimal("1"),
            [TokenAmount("ETH", Decimal("0.003"))]
        )
        sell_side = ArbProposalSide(
            sell_market_info,
            False,
            Decimal("3350"),
            Decimal("3350"),
            Decimal("1"),
            [TokenAmount("ETH", Decimal("0.001"))]
        )

        proposal = ArbProposal(buy_side, sell_side)

        rate_source = FixedRateSource()
        rate_source.add_rate("WETH-DAI", Decimal(3300))
        rate_source.add_rate("ETH-USDT", Decimal(3350))
        rate_source.add_rate("WETH-ETH", Decimal(1))
        rate_source.add_rate("USDT-DAI", Decimal(1))

        expected_sell_result: Decimal = (sell_side.amount * sell_side.quote_price -
                                         sell_side.extra_flat_fees[0].amount * sell_side.quote_price)
        expected_buy_result: Decimal = (buy_side.amount * buy_side.quote_price +
                                        (buy_side.extra_flat_fees[0].amount * buy_side.quote_price))
        expected_profit_pct: Decimal = (expected_sell_result - expected_buy_result) / expected_buy_result
        calculated_profit: Decimal = proposal.profit_pct(account_for_fee=True, rate_source=rate_source)

        self.assertEqual(expected_profit_pct, calculated_profit)
