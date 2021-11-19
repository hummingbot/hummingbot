import unittest
from decimal import Decimal

from hummingbot.connector.exchange.paper_trade.paper_trade_exchange import QuantizationParams
from hummingbot.strategy.data_types import Proposal, PriceSize
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.perpetual_market_making import PerpetualMarketMakingStrategy
from test.mock.mock_perp_connector import MockPerpConnector


class PerpetualMarketMakingTest(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.base_asset = "HBOT"
        self.quote_asset = "COINALPHA"
        self.trading_pair = f"{self.base_asset}-{self.quote_asset}"
        self.fee_percent = Decimal("1")
        self.market: MockPerpConnector = MockPerpConnector(self.fee_percent)
        self.market.set_quantization_param(
            QuantizationParams(
                self.trading_pair,
                price_precision=6,
                price_decimals=2,
                order_size_precision=6,
                order_size_decimals=2,
            )
        )
        self.market_info = MarketTradingPairTuple(
            self.market, self.trading_pair, self.base_asset, self.quote_asset
        )

        self.strategy = PerpetualMarketMakingStrategy()
        self.strategy.init_params(
            self.market_info,
            leverage=2,
            position_mode="Hedge",
            bid_spread=Decimal("1"),
            ask_spread=Decimal("1"),
            order_amount=Decimal("2"),
            position_management="Profit_taking",
            long_profit_taking_spread=Decimal("1"),
            short_profit_taking_spread=Decimal("1"),
            ts_activation_spread=Decimal("1"),
            ts_callback_rate=Decimal("1"),
            stop_loss_spread=Decimal("1"),
            close_position_order_type="LIMIT",
        )

    def test_c_apply_budget_constraint(self):
        self.market.set_balance(self.base_asset, Decimal("2"))
        self.market.set_balance(self.quote_asset, Decimal("10"))

        buys = [
            PriceSize(price=Decimal("5"), size=Decimal("1")),
            PriceSize(price=Decimal("6"), size=Decimal("1")),
        ]
        sells = [
            PriceSize(price=Decimal("7"), size=Decimal("1")),
            PriceSize(price=Decimal("8"), size=Decimal("1")),
        ]
        proposal = Proposal(buys, sells)

        self.strategy.apply_budget_constraint(proposal)

        new_buys = proposal.buys
        new_sells = proposal.sells

        self.assertEqual(2, len(new_buys))  # cumulative 11 for leverage of 20
        self.assertEqual(buys[0], new_buys[0])
        self.assertEqual(buys[1], new_buys[1])
        self.assertEqual(1, len(new_sells))  # cumulative 18 for leverage of 20
        self.assertEqual(sells[0], new_sells[0])
