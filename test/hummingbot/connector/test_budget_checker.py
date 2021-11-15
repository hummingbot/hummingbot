import unittest
from decimal import Decimal

from hummingbot.connector.budget_checker import OrderCandidate
from hummingbot.connector.exchange.paper_trade.paper_trade_exchange import QuantizationParams
from hummingbot.core.event.events import OrderType, TradeType
from test.mock.mock_paper_exchange import MockPaperExchange


class BudgetCheckerTest(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.base_asset = "COINALPHA"
        self.quote_asset = "HBOT"
        self.trading_pair = f"{self.base_asset}-{self.quote_asset}"

        self.fee_percent = Decimal("1")
        self.exchange = MockPaperExchange(self.fee_percent)
        self.budget_checker = self.exchange.budget_checker

    def test_populate_collateral_fields_buy_order(self):
        order_candidate = OrderCandidate(
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=Decimal("10"),
            price=Decimal("2"),
        )
        populated_candidate = self.budget_checker.populate_collateral_fields(order_candidate)

        self.assertEqual(self.quote_asset, populated_candidate.collateral_token)
        self.assertEqual(Decimal("20.2"), populated_candidate.collateral_amount)

    def test_populate_collateral_fields_sell_order(self):
        order_candidate = OrderCandidate(
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            order_side=TradeType.SELL,
            amount=Decimal("10"),
            price=Decimal("2"),
        )
        populated_candidate = self.budget_checker.populate_collateral_fields(order_candidate)

        self.assertEqual(self.base_asset, populated_candidate.collateral_token)
        self.assertEqual(Decimal("10"), populated_candidate.collateral_amount)

    def test_adjust_candidate_sufficient_funds(self):
        self.exchange.set_balance(self.quote_asset, Decimal("100"))

        order_candidate = OrderCandidate(
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=Decimal("10"),
            price=Decimal("2"),
        )
        adjusted_candidate = self.budget_checker.adjust_candidate(order_candidate)

        self.assertEqual(self.quote_asset, adjusted_candidate.collateral_token)
        self.assertEqual(Decimal("20.2"), adjusted_candidate.collateral_amount)
        self.assertEqual(Decimal("10"), adjusted_candidate.amount)

    def test_adjust_candidate_insufficient_funds_all_or_none(self):
        self.exchange.set_balance(self.quote_asset, Decimal("10"))

        order_candidate = OrderCandidate(
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=Decimal("10"),
            price=Decimal("2"),
        )
        adjusted_candidate = self.budget_checker.adjust_candidate(order_candidate, all_or_none=True)

        self.assertEqual(self.quote_asset, adjusted_candidate.collateral_token)
        self.assertEqual(Decimal("0"), adjusted_candidate.collateral_amount)
        self.assertEqual(Decimal("0"), adjusted_candidate.amount)

    def test_adjust_candidate_buy_insufficient_funds_partial_adjustment_allowed(self):
        q_params = QuantizationParams(
            trading_pair=self.trading_pair,
            price_precision=8,
            price_decimals=2,
            order_size_precision=8,
            order_size_decimals=2,
        )
        self.exchange.set_quantization_param(q_params)
        self.exchange.set_balance(self.quote_asset, Decimal("10"))

        order_candidate = OrderCandidate(
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=Decimal("10"),
            price=Decimal("2"),
        )
        adjusted_candidate = self.budget_checker.adjust_candidate(order_candidate, all_or_none=False)

        self.assertEqual(self.quote_asset, adjusted_candidate.collateral_token)
        self.assertEqual(Decimal("10"), adjusted_candidate.collateral_amount)
        self.assertEqual(Decimal("4.95"), adjusted_candidate.amount)  # quantized at two decimals

    def test_adjust_candidate_sell_insufficient_funds_partial_adjustment_allowed(self):
        self.exchange.set_balance(self.base_asset, Decimal("5"))

        order_candidate = OrderCandidate(
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            order_side=TradeType.SELL,
            amount=Decimal("10"),
            price=Decimal("2"),
        )
        adjusted_candidate = self.budget_checker.adjust_candidate(order_candidate, all_or_none=False)

        self.assertEqual(self.base_asset, adjusted_candidate.collateral_token)
        self.assertEqual(Decimal("5"), adjusted_candidate.collateral_amount)
        self.assertEqual(Decimal("5"), adjusted_candidate.amount)

    def test_adjust_candidate_and_lock_available_collateral(self):
        self.exchange.set_balance(self.base_asset, Decimal("10"))

        first_order_candidate = OrderCandidate(
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            order_side=TradeType.SELL,
            amount=Decimal("7"),
            price=Decimal("2"),
        )
        first_adjusted_candidate = self.budget_checker.adjust_candidate_and_lock_available_collateral(
            first_order_candidate, all_or_none=False
        )
        second_order_candidate = OrderCandidate(
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            order_side=TradeType.SELL,
            amount=Decimal("5"),
            price=Decimal("2"),
        )
        second_adjusted_candidate = self.budget_checker.adjust_candidate_and_lock_available_collateral(
            second_order_candidate, all_or_none=False
        )
        third_order_candidate = OrderCandidate(
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            order_side=TradeType.SELL,
            amount=Decimal("5"),
            price=Decimal("2"),
        )
        third_adjusted_candidate = self.budget_checker.adjust_candidate_and_lock_available_collateral(
            third_order_candidate, all_or_none=False
        )

        self.assertEqual(Decimal("7"), first_adjusted_candidate.amount)
        self.assertEqual(Decimal("3"), second_adjusted_candidate.amount)
        self.assertEqual(Decimal("0"), third_adjusted_candidate.amount)

    def test_reset_locked_collateral(self):
        self.exchange.set_balance(self.base_asset, Decimal("10"))

        first_order_candidate = OrderCandidate(
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            order_side=TradeType.SELL,
            amount=Decimal("7"),
            price=Decimal("2"),
        )
        first_adjusted_candidate = self.budget_checker.adjust_candidate_and_lock_available_collateral(
            first_order_candidate, all_or_none=False
        )

        self.budget_checker.reset_locked_collateral()

        second_order_candidate = OrderCandidate(
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            order_side=TradeType.SELL,
            amount=Decimal("5"),
            price=Decimal("2"),
        )
        second_adjusted_candidate = self.budget_checker.adjust_candidate_and_lock_available_collateral(
            second_order_candidate, all_or_none=False
        )

        self.assertEqual(Decimal("7"), first_adjusted_candidate.amount)
        self.assertEqual(Decimal("5"), second_adjusted_candidate.amount)

    def test_adjust_candidates(self):
        self.exchange.set_balance(self.base_asset, Decimal("10"))

        first_order_candidate = OrderCandidate(
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            order_side=TradeType.SELL,
            amount=Decimal("7"),
            price=Decimal("2"),
        )
        second_order_candidate = OrderCandidate(
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            order_side=TradeType.SELL,
            amount=Decimal("5"),
            price=Decimal("2"),
        )
        third_order_candidate = OrderCandidate(
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            order_side=TradeType.SELL,
            amount=Decimal("5"),
            price=Decimal("2"),
        )

        first_adjusted_candidate, second_adjusted_candidate, third_adjusted_candidate = (
            self.budget_checker.adjust_candidates(
                [first_order_candidate, second_order_candidate, third_order_candidate], all_or_none=False
            )
        )

        self.assertEqual(Decimal("7"), first_adjusted_candidate.amount)
        self.assertEqual(Decimal("3"), second_adjusted_candidate.amount)
        self.assertEqual(Decimal("0"), third_adjusted_candidate.amount)

    def test_adjust_candidates_resets_locked_collateral(self):
        self.exchange.set_balance(self.base_asset, Decimal("10"))

        first_order_candidate = OrderCandidate(
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            order_side=TradeType.SELL,
            amount=Decimal("7"),
            price=Decimal("2"),
        )
        first_adjusted_candidate, = self.budget_checker.adjust_candidates(
            [first_order_candidate], all_or_none=False
        )

        second_order_candidate = OrderCandidate(
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            order_side=TradeType.SELL,
            amount=Decimal("5"),
            price=Decimal("2"),
        )
        second_adjusted_candidate = self.budget_checker.adjust_candidate_and_lock_available_collateral(
            second_order_candidate, all_or_none=False
        )

        self.assertEqual(Decimal("7"), first_adjusted_candidate.amount)
        self.assertEqual(Decimal("5"), second_adjusted_candidate.amount)
