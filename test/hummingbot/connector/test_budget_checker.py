import unittest
from decimal import Decimal
from test.mock.mock_paper_exchange import MockPaperExchange

from hummingbot.connector.budget_checker import BudgetChecker
from hummingbot.connector.exchange.paper_trade.paper_trade_exchange import QuantizationParams
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeSchema
from hummingbot.core.event.events import OrderType, TradeType


class BudgetCheckerTest(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.base_asset = "COINALPHA"
        self.quote_asset = "HBOT"
        self.trading_pair = f"{self.base_asset}-{self.quote_asset}"

        trade_fee_schema = TradeFeeSchema(
            maker_percent_fee_decimal=Decimal("0.01"), taker_percent_fee_decimal=Decimal("0.02")
        )
        self.exchange = MockPaperExchange(trade_fee_schema)
        self.budget_checker: BudgetChecker = self.exchange.budget_checker

    def test_populate_collateral_fields_buy_order(self):
        order_candidate = OrderCandidate(
            trading_pair=self.trading_pair,
            is_maker=True,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=Decimal("10"),
            price=Decimal("2"),
        )
        populated_candidate = self.budget_checker.populate_collateral_entries(order_candidate)

        self.assertEqual(self.quote_asset, populated_candidate.order_collateral.token)
        self.assertEqual(Decimal("20"), populated_candidate.order_collateral.amount)
        self.assertEqual(self.quote_asset, populated_candidate.percent_fee_collateral.token)
        self.assertEqual(Decimal("0.2"), populated_candidate.percent_fee_collateral.amount)
        self.assertEqual(self.quote_asset, populated_candidate.percent_fee_value.token)
        self.assertEqual(Decimal("0.2"), populated_candidate.percent_fee_value.amount)
        self.assertEqual(0, len(populated_candidate.fixed_fee_collaterals))
        self.assertEqual(self.base_asset, populated_candidate.potential_returns.token)
        self.assertEqual(Decimal("10"), populated_candidate.potential_returns.amount)

    def test_populate_collateral_fields_taker_buy_order(self):
        order_candidate = OrderCandidate(
            trading_pair=self.trading_pair,
            is_maker=False,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=Decimal("10"),
            price=Decimal("2"),
        )
        populated_candidate = self.budget_checker.populate_collateral_entries(order_candidate)

        self.assertEqual(self.quote_asset, populated_candidate.order_collateral.token)
        self.assertEqual(Decimal("20"), populated_candidate.order_collateral.amount)
        self.assertEqual(self.quote_asset, populated_candidate.percent_fee_collateral.token)
        self.assertEqual(Decimal("0.4"), populated_candidate.percent_fee_collateral.amount)
        self.assertEqual(self.quote_asset, populated_candidate.percent_fee_value.token)
        self.assertEqual(Decimal("0.4"), populated_candidate.percent_fee_value.amount)
        self.assertEqual(0, len(populated_candidate.fixed_fee_collaterals))
        self.assertEqual(self.base_asset, populated_candidate.potential_returns.token)
        self.assertEqual(Decimal("10"), populated_candidate.potential_returns.amount)

    def test_populate_collateral_fields_buy_order_percent_fee_from_returns(self):
        trade_fee_schema = TradeFeeSchema(
            maker_percent_fee_decimal=Decimal("0.01"),
            taker_percent_fee_decimal=Decimal("0.01"),
            buy_percent_fee_deducted_from_returns=True,
        )
        exchange = MockPaperExchange(trade_fee_schema)
        budget_checker: BudgetChecker = exchange.budget_checker
        order_candidate = OrderCandidate(
            trading_pair=self.trading_pair,
            is_maker=True,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=Decimal("10"),
            price=Decimal("2"),
        )
        populated_candidate = budget_checker.populate_collateral_entries(order_candidate)

        self.assertEqual(self.quote_asset, populated_candidate.order_collateral.token)
        self.assertEqual(Decimal("20"), populated_candidate.order_collateral.amount)
        self.assertIsNone(populated_candidate.percent_fee_collateral)
        self.assertEqual(self.base_asset, populated_candidate.percent_fee_value.token)
        self.assertEqual(Decimal("0.1"), populated_candidate.percent_fee_value.amount)
        self.assertEqual(0, len(populated_candidate.fixed_fee_collaterals))
        self.assertEqual(self.base_asset, populated_candidate.potential_returns.token)
        self.assertEqual(Decimal("9.90"), populated_candidate.potential_returns.amount)

    def test_populate_collateral_fields_sell_order(self):
        order_candidate = OrderCandidate(
            trading_pair=self.trading_pair,
            is_maker=True,
            order_type=OrderType.LIMIT,
            order_side=TradeType.SELL,
            amount=Decimal("10"),
            price=Decimal("2"),
        )
        populated_candidate = self.budget_checker.populate_collateral_entries(order_candidate)

        self.assertEqual(self.base_asset, populated_candidate.order_collateral.token)
        self.assertEqual(Decimal("10"), populated_candidate.order_collateral.amount)
        self.assertIsNone(populated_candidate.percent_fee_collateral)
        self.assertEqual(self.quote_asset, populated_candidate.percent_fee_value.token)
        self.assertEqual(Decimal("0.2"), populated_candidate.percent_fee_value.amount)
        self.assertEqual(0, len(populated_candidate.fixed_fee_collaterals))
        self.assertEqual(self.quote_asset, populated_candidate.potential_returns.token)
        self.assertEqual(Decimal("19.8"), populated_candidate.potential_returns.amount)

    def test_populate_collateral_fields_percent_fees_in_third_token(self):
        pfc_token = "PFC"
        trade_fee_schema = TradeFeeSchema(
            percent_fee_token=pfc_token,
            maker_percent_fee_decimal=Decimal("0.01"),
            taker_percent_fee_decimal=Decimal("0.01"),
        )
        exchange = MockPaperExchange(trade_fee_schema)
        pfc_quote_pair = combine_to_hb_trading_pair(self.quote_asset, pfc_token)
        exchange.set_balanced_order_book(  # the quote to pfc price will be 1:2
            trading_pair=pfc_quote_pair,
            mid_price=1.5,
            min_price=1,
            max_price=2,
            price_step_size=1,
            volume_step_size=1,
        )
        budget_checker: BudgetChecker = exchange.budget_checker

        order_candidate = OrderCandidate(
            trading_pair=self.trading_pair,
            is_maker=True,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=Decimal("10"),
            price=Decimal("2"),
        )
        populated_candidate = budget_checker.populate_collateral_entries(order_candidate)

        self.assertEqual(self.quote_asset, populated_candidate.order_collateral.token)
        self.assertEqual(Decimal("20"), populated_candidate.order_collateral.amount)
        self.assertEqual(pfc_token, populated_candidate.percent_fee_collateral.token)
        self.assertEqual(Decimal("0.4"), populated_candidate.percent_fee_collateral.amount)
        self.assertEqual(pfc_token, populated_candidate.percent_fee_value.token)
        self.assertEqual(Decimal("0.4"), populated_candidate.percent_fee_value.amount)
        self.assertEqual(0, len(populated_candidate.fixed_fee_collaterals))
        self.assertEqual(self.base_asset, populated_candidate.potential_returns.token)
        self.assertEqual(Decimal("10"), populated_candidate.potential_returns.amount)

    def test_populate_collateral_fields_fixed_fees_in_quote_token(self):
        trade_fee_schema = TradeFeeSchema(
            maker_fixed_fees=[TokenAmount(self.quote_asset, Decimal("1"))],
            taker_fixed_fees=[TokenAmount(self.base_asset, Decimal("2"))],
        )
        exchange = MockPaperExchange(trade_fee_schema)
        budget_checker: BudgetChecker = exchange.budget_checker

        order_candidate = OrderCandidate(
            trading_pair=self.trading_pair,
            is_maker=True,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=Decimal("10"),
            price=Decimal("2"),
        )
        populated_candidate = budget_checker.populate_collateral_entries(order_candidate)

        self.assertEqual(self.quote_asset, populated_candidate.order_collateral.token)
        self.assertEqual(Decimal("20"), populated_candidate.order_collateral.amount)
        self.assertIsNone(populated_candidate.percent_fee_collateral)
        self.assertIsNone(populated_candidate.percent_fee_value)
        self.assertEqual(1, len(populated_candidate.fixed_fee_collaterals))

        fixed_fee_collateral = populated_candidate.fixed_fee_collaterals[0]

        self.assertEqual(self.quote_asset, fixed_fee_collateral.token)
        self.assertEqual(Decimal("1"), fixed_fee_collateral.amount)
        self.assertEqual(self.base_asset, populated_candidate.potential_returns.token)
        self.assertEqual(Decimal("10"), populated_candidate.potential_returns.amount)

    def test_adjust_candidate_sufficient_funds(self):
        self.exchange.set_balance(self.quote_asset, Decimal("100"))

        order_candidate = OrderCandidate(
            trading_pair=self.trading_pair,
            is_maker=True,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=Decimal("10"),
            price=Decimal("2"),
        )
        adjusted_candidate = self.budget_checker.adjust_candidate(order_candidate)

        self.assertEqual(self.quote_asset, adjusted_candidate.order_collateral.token)
        self.assertEqual(Decimal("20"), adjusted_candidate.order_collateral.amount)
        self.assertEqual(self.quote_asset, adjusted_candidate.percent_fee_collateral.token)
        self.assertEqual(Decimal("0.2"), adjusted_candidate.percent_fee_collateral.amount)
        self.assertEqual(self.quote_asset, adjusted_candidate.percent_fee_value.token)
        self.assertEqual(Decimal("0.2"), adjusted_candidate.percent_fee_value.amount)
        self.assertEqual(0, len(adjusted_candidate.fixed_fee_collaterals))
        self.assertEqual(self.base_asset, adjusted_candidate.potential_returns.token)
        self.assertEqual(Decimal("10"), adjusted_candidate.potential_returns.amount)

    def test_adjust_candidate_insufficient_funds_all_or_none(self):
        self.exchange.set_balance(self.quote_asset, Decimal("10"))

        order_candidate = OrderCandidate(
            trading_pair=self.trading_pair,
            is_maker=True,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=Decimal("10"),
            price=Decimal("2"),
        )
        adjusted_candidate = self.budget_checker.adjust_candidate(order_candidate, all_or_none=True)

        self.assertEqual(0, adjusted_candidate.amount)
        self.assertIsNone(adjusted_candidate.order_collateral)
        self.assertIsNone(adjusted_candidate.percent_fee_collateral)
        self.assertIsNone(adjusted_candidate.percent_fee_value)
        self.assertEqual(0, len(adjusted_candidate.fixed_fee_collaterals))
        self.assertIsNone(adjusted_candidate.potential_returns)

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
            is_maker=True,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=Decimal("10"),
            price=Decimal("2"),
        )
        adjusted_candidate = self.budget_checker.adjust_candidate(order_candidate, all_or_none=False)

        # order amount quantized to two decimal places
        self.assertEqual(Decimal("4.95"), adjusted_candidate.amount)  # 5 * .99
        self.assertEqual(self.quote_asset, adjusted_candidate.order_collateral.token)
        self.assertEqual(Decimal("9.9"), adjusted_candidate.order_collateral.amount)  # 4.95 * 2
        self.assertEqual(self.quote_asset, adjusted_candidate.percent_fee_collateral.token)
        self.assertEqual(Decimal("0.099"), adjusted_candidate.percent_fee_collateral.amount)  # 9.9 * 0.01
        self.assertEqual(self.quote_asset, adjusted_candidate.percent_fee_value.token)
        self.assertEqual(Decimal("0.099"), adjusted_candidate.percent_fee_value.amount)  # 9.9 * 0.01
        self.assertEqual(0, len(adjusted_candidate.fixed_fee_collaterals))
        self.assertEqual(self.base_asset, adjusted_candidate.potential_returns.token)
        self.assertEqual(Decimal("4.95"), adjusted_candidate.potential_returns.amount)

    def test_adjust_candidate_sell_insufficient_funds_partial_adjustment_allowed(self):
        self.exchange.set_balance(self.base_asset, Decimal("5"))

        order_candidate = OrderCandidate(
            trading_pair=self.trading_pair,
            is_maker=True,
            order_type=OrderType.LIMIT,
            order_side=TradeType.SELL,
            amount=Decimal("10"),
            price=Decimal("2"),
        )
        adjusted_candidate = self.budget_checker.adjust_candidate(order_candidate, all_or_none=False)

        self.assertEqual(Decimal("5"), adjusted_candidate.amount)
        self.assertEqual(self.base_asset, adjusted_candidate.order_collateral.token)
        self.assertEqual(Decimal("5"), adjusted_candidate.order_collateral.amount)
        self.assertIsNone(adjusted_candidate.percent_fee_collateral)
        self.assertEqual(self.quote_asset, adjusted_candidate.percent_fee_value.token)
        self.assertEqual(Decimal("0.1"), adjusted_candidate.percent_fee_value.amount)  # 10 * 0.01
        self.assertEqual(0, len(adjusted_candidate.fixed_fee_collaterals))
        self.assertEqual(self.quote_asset, adjusted_candidate.potential_returns.token)
        self.assertEqual(Decimal("9.9"), adjusted_candidate.potential_returns.amount)  # 10 * 0.99

    def test_adjust_candidate_insufficient_funds_for_flat_fees_same_token(self):
        trade_fee_schema = TradeFeeSchema(
            maker_fixed_fees=[TokenAmount(self.quote_asset, Decimal("1"))],
        )
        exchange = MockPaperExchange(trade_fee_schema)
        budget_checker: BudgetChecker = exchange.budget_checker
        exchange.set_balance(self.quote_asset, Decimal("11"))

        order_candidate = OrderCandidate(
            trading_pair=self.trading_pair,
            is_maker=True,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=Decimal("10"),
            price=Decimal("2"),
        )
        adjusted_candidate = budget_checker.adjust_candidate(order_candidate, all_or_none=False)

        self.assertEqual(Decimal("5"), adjusted_candidate.amount)
        self.assertEqual(self.quote_asset, adjusted_candidate.order_collateral.token)
        self.assertEqual(Decimal("10"), adjusted_candidate.order_collateral.amount)
        self.assertIsNone(adjusted_candidate.percent_fee_collateral)
        self.assertIsNone(adjusted_candidate.percent_fee_value)
        self.assertEqual(1, len(adjusted_candidate.fixed_fee_collaterals))

        fixed_fee_collateral = adjusted_candidate.fixed_fee_collaterals[0]

        self.assertEqual(self.quote_asset, fixed_fee_collateral.token)
        self.assertEqual(Decimal("1"), fixed_fee_collateral.amount)
        self.assertEqual(self.base_asset, adjusted_candidate.potential_returns.token)
        self.assertEqual(Decimal("5"), adjusted_candidate.potential_returns.amount)

    def test_adjust_candidate_insufficient_funds_for_flat_fees_third_token(self):
        fee_asset = "FEE"
        trade_fee_schema = TradeFeeSchema(
            maker_fixed_fees=[TokenAmount(fee_asset, Decimal("11"))],
        )
        exchange = MockPaperExchange(trade_fee_schema)
        budget_checker: BudgetChecker = exchange.budget_checker
        exchange.set_balance(self.quote_asset, Decimal("100"))
        exchange.set_balance(fee_asset, Decimal("10"))

        order_candidate = OrderCandidate(
            trading_pair=self.trading_pair,
            is_maker=True,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=Decimal("10"),
            price=Decimal("2"),
        )
        adjusted_candidate = budget_checker.adjust_candidate(order_candidate, all_or_none=False)

        self.assertTrue(adjusted_candidate.is_zero_order)

    def test_adjust_candidate_insufficient_funds_for_flat_fees_and_percent_fees(self):
        trade_fee_schema = TradeFeeSchema(
            maker_percent_fee_decimal=Decimal("0.1"),
            maker_fixed_fees=[TokenAmount(self.quote_asset, Decimal("1"))],
        )
        exchange = MockPaperExchange(trade_fee_schema)
        budget_checker: BudgetChecker = exchange.budget_checker
        exchange.set_balance(self.quote_asset, Decimal("12"))

        order_candidate = OrderCandidate(
            trading_pair=self.trading_pair,
            is_maker=True,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=Decimal("10"),
            price=Decimal("2"),
        )
        adjusted_candidate = budget_checker.adjust_candidate(order_candidate, all_or_none=False)

        self.assertEqual(Decimal("5"), adjusted_candidate.amount)
        self.assertEqual(self.quote_asset, adjusted_candidate.order_collateral.token)
        self.assertEqual(Decimal("10"), adjusted_candidate.order_collateral.amount)
        self.assertEqual(self.quote_asset, adjusted_candidate.percent_fee_collateral.token)
        self.assertEqual(Decimal("1"), adjusted_candidate.percent_fee_collateral.amount)
        self.assertEqual(self.quote_asset, adjusted_candidate.percent_fee_value.token)
        self.assertEqual(Decimal("1"), adjusted_candidate.percent_fee_value.amount)
        self.assertEqual(1, len(adjusted_candidate.fixed_fee_collaterals))

        fixed_fee_collateral = adjusted_candidate.fixed_fee_collaterals[0]

        self.assertEqual(self.quote_asset, fixed_fee_collateral.token)
        self.assertEqual(Decimal("1"), fixed_fee_collateral.amount)
        self.assertEqual(self.base_asset, adjusted_candidate.potential_returns.token)
        self.assertEqual(Decimal("5"), adjusted_candidate.potential_returns.amount)

    def test_adjust_candidate_insufficient_funds_for_flat_fees_and_percent_fees_third_token(self):
        fc_token = "PFC"
        trade_fee_schema = TradeFeeSchema(
            percent_fee_token=fc_token,
            maker_percent_fee_decimal=Decimal("0.01"),
            taker_percent_fee_decimal=Decimal("0.01"),
            maker_fixed_fees=[TokenAmount(fc_token, Decimal("1"))]
        )
        exchange = MockPaperExchange(trade_fee_schema)
        pfc_quote_pair = combine_to_hb_trading_pair(self.quote_asset, fc_token)
        exchange.set_balanced_order_book(  # the quote to pfc price will be 1:2
            trading_pair=pfc_quote_pair,
            mid_price=1.5,
            min_price=1,
            max_price=2,
            price_step_size=1,
            volume_step_size=1,
        )
        budget_checker: BudgetChecker = exchange.budget_checker
        exchange.set_balance(self.quote_asset, Decimal("20"))
        exchange.set_balance(fc_token, Decimal("1.2"))  # 0.2 less than required; will result in 50% order reduction

        order_candidate = OrderCandidate(
            trading_pair=self.trading_pair,
            is_maker=True,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=Decimal("10"),
            price=Decimal("2"),
        )
        adjusted_candidate = budget_checker.adjust_candidate(order_candidate, all_or_none=False)

        self.assertEqual(Decimal("5"), adjusted_candidate.amount)
        self.assertEqual(self.quote_asset, adjusted_candidate.order_collateral.token)
        self.assertEqual(Decimal("10"), adjusted_candidate.order_collateral.amount)
        self.assertEqual(fc_token, adjusted_candidate.percent_fee_collateral.token)
        self.assertEqual(Decimal("0.2"), adjusted_candidate.percent_fee_collateral.amount)
        self.assertEqual(fc_token, adjusted_candidate.percent_fee_value.token)
        self.assertEqual(Decimal("0.2"), adjusted_candidate.percent_fee_value.amount)
        self.assertEqual(1, len(adjusted_candidate.fixed_fee_collaterals))

        fixed_fee_collateral = adjusted_candidate.fixed_fee_collaterals[0]

        self.assertEqual(fc_token, fixed_fee_collateral.token)
        self.assertEqual(Decimal("1"), fixed_fee_collateral.amount)
        self.assertEqual(self.base_asset, adjusted_candidate.potential_returns.token)
        self.assertEqual(Decimal("5"), adjusted_candidate.potential_returns.amount)

    def test_adjust_candidate_and_lock_available_collateral(self):
        self.exchange.set_balance(self.base_asset, Decimal("10"))

        first_order_candidate = OrderCandidate(
            trading_pair=self.trading_pair,
            is_maker=True,
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
            is_maker=True,
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
            is_maker=True,
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
        self.assertEqual(Decimal("3"), second_adjusted_candidate.order_collateral.amount)
        self.assertEqual(Decimal("0"), third_adjusted_candidate.amount)
        self.assertIsNone(third_adjusted_candidate.order_collateral)

    def test_reset_locked_collateral(self):
        self.exchange.set_balance(self.base_asset, Decimal("10"))

        first_order_candidate = OrderCandidate(
            trading_pair=self.trading_pair,
            is_maker=True,
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
            is_maker=True,
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
            is_maker=True,
            order_type=OrderType.LIMIT,
            order_side=TradeType.SELL,
            amount=Decimal("7"),
            price=Decimal("2"),
        )
        second_order_candidate = OrderCandidate(
            trading_pair=self.trading_pair,
            is_maker=True,
            order_type=OrderType.LIMIT,
            order_side=TradeType.SELL,
            amount=Decimal("5"),
            price=Decimal("2"),
        )
        third_order_candidate = OrderCandidate(
            trading_pair=self.trading_pair,
            is_maker=True,
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
        self.assertEqual(Decimal("3"), second_adjusted_candidate.order_collateral.amount)
        self.assertEqual(Decimal("0"), third_adjusted_candidate.amount)
        self.assertIsNone(third_adjusted_candidate.order_collateral)

    def test_adjust_candidates_resets_locked_collateral(self):
        self.exchange.set_balance(self.base_asset, Decimal("10"))

        first_order_candidate = OrderCandidate(
            trading_pair=self.trading_pair,
            is_maker=True,
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
            is_maker=True,
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
