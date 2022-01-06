import unittest
from decimal import Decimal
from test.mock.mock_perp_connector import MockPerpConnector

from hummingbot.connector.derivative.perpetual_budget_checker import PerpetualBudgetChecker
from hummingbot.connector.exchange.paper_trade.paper_trade_exchange import QuantizationParams
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.order_candidate import PerpetualOrderCandidate
from hummingbot.core.data_type.trade_fee import TradeFeeSchema
from hummingbot.core.event.events import OrderType, TradeType


class PerpetualBudgetCheckerTest(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()

        self.base_asset = "COINALPHA"
        self.quote_asset = "HBOT"
        self.trading_pair = f"{self.base_asset}-{self.quote_asset}"

        trade_fee_schema = TradeFeeSchema(
            maker_percent_fee_decimal=Decimal("0.01"), taker_percent_fee_decimal=Decimal("0.02")
        )
        self.exchange = MockPerpConnector(trade_fee_schema)
        self.budget_checker = self.exchange.budget_checker

    def test_populate_collateral_fields_buy_order(self):
        order_candidate = PerpetualOrderCandidate(
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
        self.assertIsNone(populated_candidate.potential_returns)  # order results in position open

    def test_populate_collateral_fields_taker_buy_order(self):
        order_candidate = PerpetualOrderCandidate(
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
        self.assertIsNone(populated_candidate.potential_returns)  # order results in position open

    def test_populate_collateral_fields_buy_order_with_leverage(self):
        order_candidate = PerpetualOrderCandidate(
            trading_pair=self.trading_pair,
            is_maker=True,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=Decimal("10"),
            price=Decimal("2"),
            leverage=Decimal("2")
        )
        populated_candidate = self.budget_checker.populate_collateral_entries(order_candidate)

        self.assertEqual(self.quote_asset, populated_candidate.order_collateral.token)
        self.assertEqual(Decimal("10"), populated_candidate.order_collateral.amount)
        self.assertEqual(self.quote_asset, populated_candidate.percent_fee_collateral.token)
        self.assertEqual(Decimal("0.2"), populated_candidate.percent_fee_collateral.amount)
        self.assertEqual(self.quote_asset, populated_candidate.percent_fee_value.token)
        self.assertEqual(Decimal("0.2"), populated_candidate.percent_fee_value.amount)
        self.assertEqual(0, len(populated_candidate.fixed_fee_collaterals))
        self.assertIsNone(populated_candidate.potential_returns)  # order results in position open

    def test_populate_collateral_fields_sell_order(self):
        order_candidate = PerpetualOrderCandidate(
            trading_pair=self.trading_pair,
            is_maker=True,
            order_type=OrderType.LIMIT,
            order_side=TradeType.SELL,
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
        self.assertIsNone(populated_candidate.potential_returns)  # order results in position open

    def test_populate_collateral_fields_sell_order_with_leverage(self):
        order_candidate = PerpetualOrderCandidate(
            trading_pair=self.trading_pair,
            is_maker=True,
            order_type=OrderType.LIMIT,
            order_side=TradeType.SELL,
            amount=Decimal("10"),
            price=Decimal("2"),
            leverage=Decimal("2"),
        )
        populated_candidate = self.budget_checker.populate_collateral_entries(order_candidate)

        self.assertEqual(self.quote_asset, populated_candidate.order_collateral.token)
        self.assertEqual(Decimal("10"), populated_candidate.order_collateral.amount)
        self.assertEqual(self.quote_asset, populated_candidate.percent_fee_collateral.token)
        self.assertEqual(Decimal("0.2"), populated_candidate.percent_fee_collateral.amount)
        self.assertEqual(self.quote_asset, populated_candidate.percent_fee_value.token)
        self.assertEqual(Decimal("0.2"), populated_candidate.percent_fee_value.amount)
        self.assertEqual(0, len(populated_candidate.fixed_fee_collaterals))
        self.assertIsNone(populated_candidate.potential_returns)  # order results in position open

    def test_populate_collateral_fields_percent_fees_in_third_token(self):
        pfc_token = "PFC"
        trade_fee_schema = TradeFeeSchema(
            percent_fee_token=pfc_token,
            maker_percent_fee_decimal=Decimal("0.01"),
            taker_percent_fee_decimal=Decimal("0.01"),
        )
        exchange = MockPerpConnector(trade_fee_schema)
        pfc_quote_pair = combine_to_hb_trading_pair(self.quote_asset, pfc_token)
        exchange.set_balanced_order_book(  # the quote to pfc price will be 1:2
            trading_pair=pfc_quote_pair,
            mid_price=1.5,
            min_price=1,
            max_price=2,
            price_step_size=1,
            volume_step_size=1,
        )
        budget_checker: PerpetualBudgetChecker = exchange.budget_checker

        order_candidate = PerpetualOrderCandidate(
            trading_pair=self.trading_pair,
            is_maker=True,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=Decimal("10"),
            price=Decimal("2"),
            leverage=Decimal("2"),
        )
        populated_candidate = budget_checker.populate_collateral_entries(order_candidate)

        self.assertEqual(self.quote_asset, populated_candidate.order_collateral.token)
        self.assertEqual(Decimal("10"), populated_candidate.order_collateral.amount)
        self.assertEqual(pfc_token, populated_candidate.percent_fee_collateral.token)
        self.assertEqual(Decimal("0.4"), populated_candidate.percent_fee_collateral.amount)
        self.assertEqual(pfc_token, populated_candidate.percent_fee_value.token)
        self.assertEqual(Decimal("0.4"), populated_candidate.percent_fee_value.amount)
        self.assertEqual(0, len(populated_candidate.fixed_fee_collaterals))
        self.assertIsNone(populated_candidate.potential_returns)  # order results in position open

    def test_populate_collateral_for_position_close(self):
        order_candidate = PerpetualOrderCandidate(
            trading_pair=self.trading_pair,
            is_maker=True,
            order_type=OrderType.LIMIT,
            order_side=TradeType.SELL,
            amount=Decimal("10"),
            price=Decimal("2"),
            leverage=Decimal("2"),
            position_close=True,
        )
        populated_candidate = self.budget_checker.populate_collateral_entries(order_candidate)

        self.assertIsNone(populated_candidate.order_collateral)  # the collateral is the contract itself
        self.assertIsNone(populated_candidate.percent_fee_collateral)
        self.assertIsNone(populated_candidate.percent_fee_value)
        self.assertEqual(0, len(populated_candidate.fixed_fee_collaterals))
        self.assertEqual(self.quote_asset, populated_candidate.potential_returns.token)
        self.assertEqual(Decimal("19.8"), populated_candidate.potential_returns.amount)

    def test_adjust_candidate_sufficient_funds(self):
        self.exchange.set_balance(self.quote_asset, Decimal("100"))

        order_candidate = PerpetualOrderCandidate(
            trading_pair=self.trading_pair,
            is_maker=True,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=Decimal("10"),
            price=Decimal("2"),
        )
        adjusted_candidate = self.budget_checker.adjust_candidate(order_candidate)

        self.assertEqual(Decimal("10"), adjusted_candidate.amount)
        self.assertEqual(self.quote_asset, adjusted_candidate.order_collateral.token)
        self.assertEqual(Decimal("20"), adjusted_candidate.order_collateral.amount)
        self.assertEqual(self.quote_asset, adjusted_candidate.percent_fee_collateral.token)
        self.assertEqual(Decimal("0.2"), adjusted_candidate.percent_fee_collateral.amount)
        self.assertEqual(self.quote_asset, adjusted_candidate.percent_fee_value.token)
        self.assertEqual(Decimal("0.2"), adjusted_candidate.percent_fee_value.amount)
        self.assertEqual(0, len(adjusted_candidate.fixed_fee_collaterals))
        self.assertIsNone(adjusted_candidate.potential_returns)  # order results in position open

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

        order_candidate = PerpetualOrderCandidate(
            trading_pair=self.trading_pair,
            is_maker=True,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=Decimal("10"),
            price=Decimal("2"),
        )
        adjusted_candidate = self.budget_checker.adjust_candidate(order_candidate, all_or_none=False)

        self.assertEqual(Decimal("4.95"), adjusted_candidate.amount)  # 5 * .99
        self.assertEqual(self.quote_asset, adjusted_candidate.order_collateral.token)
        self.assertEqual(Decimal("9.9"), adjusted_candidate.order_collateral.amount)  # 4.95 * 2
        self.assertEqual(self.quote_asset, adjusted_candidate.percent_fee_collateral.token)
        self.assertEqual(Decimal("0.099"), adjusted_candidate.percent_fee_collateral.amount)  # 9.9 * 0.01
        self.assertEqual(self.quote_asset, adjusted_candidate.percent_fee_value.token)
        self.assertEqual(Decimal("0.099"), adjusted_candidate.percent_fee_value.amount)  # 9.9 * 0.01
        self.assertEqual(0, len(adjusted_candidate.fixed_fee_collaterals))
        self.assertIsNone(adjusted_candidate.potential_returns)  # order results in position open

    def test_adjust_candidate_sell_insufficient_funds_partial_adjustment_allowed(self):
        q_params = QuantizationParams(
            trading_pair=self.trading_pair,
            price_precision=8,
            price_decimals=2,
            order_size_precision=8,
            order_size_decimals=2,
        )
        self.exchange.set_quantization_param(q_params)
        self.exchange.set_balance(self.quote_asset, Decimal("10"))

        order_candidate = PerpetualOrderCandidate(
            trading_pair=self.trading_pair,
            is_maker=True,
            order_type=OrderType.LIMIT,
            order_side=TradeType.SELL,
            amount=Decimal("10"),
            price=Decimal("2"),
        )
        adjusted_candidate = self.budget_checker.adjust_candidate(order_candidate, all_or_none=False)

        self.assertEqual(Decimal("4.95"), adjusted_candidate.amount)  # 5 * .99
        self.assertEqual(self.quote_asset, adjusted_candidate.order_collateral.token)
        self.assertEqual(Decimal("9.9"), adjusted_candidate.order_collateral.amount)  # 4.95 * 2
        self.assertEqual(self.quote_asset, adjusted_candidate.percent_fee_collateral.token)
        self.assertEqual(Decimal("0.099"), adjusted_candidate.percent_fee_collateral.amount)  # 9.9 * 0.01
        self.assertEqual(self.quote_asset, adjusted_candidate.percent_fee_value.token)
        self.assertEqual(Decimal("0.099"), adjusted_candidate.percent_fee_value.amount)  # 9.9 * 0.01
        self.assertEqual(0, len(adjusted_candidate.fixed_fee_collaterals))
        self.assertIsNone(adjusted_candidate.potential_returns)  # order results in position open
