from decimal import Decimal
from unittest import TestCase

from hummingbot.core.data_type.common import TradeType, PositionAction
from hummingbot.core.data_type.trade_fee import TradeFeeSchema, TradeFeeBase, TokenAmount, AddedToCostTradeFee, \
    DeductedFromReturnsTradeFee


class TradeFeeTests(TestCase):

    def test_added_to_cost_spot_fee_created_for_buy_and_fee_not_deducted_from_return(self):

        schema = TradeFeeSchema(
            percent_fee_token="HBOT",
            maker_percent_fee_decimal=Decimal("1"),
            taker_percent_fee_decimal=Decimal("1"),
            buy_percent_fee_deducted_from_returns=False,
        )

        fee = TradeFeeBase.new_spot_fee(
            fee_schema=schema,
            trade_type=TradeType.BUY,
            percent=Decimal("1.1"),
            percent_token="HBOT",
            flat_fees=[TokenAmount(token="COINALPHA", amount=Decimal("20"))]
        )

        self.assertEqual(AddedToCostTradeFee, type(fee))
        self.assertEqual(Decimal("1.1"), fee.percent)
        self.assertEqual("HBOT", fee.percent_token)
        self.assertEqual([TokenAmount(token="COINALPHA", amount=Decimal("20"))], fee.flat_fees)

    def test_deducted_from_return_spot_fee_created_for_buy_and_fee_deducted_from_return(self):

        schema = TradeFeeSchema(
            maker_percent_fee_decimal=Decimal("1"),
            taker_percent_fee_decimal=Decimal("1"),
            buy_percent_fee_deducted_from_returns=True,
        )

        fee = TradeFeeBase.new_spot_fee(
            fee_schema=schema,
            trade_type=TradeType.BUY,
            percent=Decimal("1.1"),
            percent_token="HBOT",
            flat_fees=[TokenAmount(token="COINALPHA", amount=Decimal("20"))]
        )

        self.assertEqual(DeductedFromReturnsTradeFee, type(fee))
        self.assertEqual(Decimal("1.1"), fee.percent)
        self.assertEqual("HBOT", fee.percent_token)
        self.assertEqual([TokenAmount(token="COINALPHA", amount=Decimal("20"))], fee.flat_fees)

    def test_deducted_from_return_spot_fee_created_for_sell(self):

        schema = TradeFeeSchema(
            percent_fee_token="HBOT",
            maker_percent_fee_decimal=Decimal("1"),
            taker_percent_fee_decimal=Decimal("1"),
            buy_percent_fee_deducted_from_returns=False,
        )

        fee = TradeFeeBase.new_spot_fee(
            fee_schema=schema,
            trade_type=TradeType.SELL,
            percent=Decimal("1.1"),
            percent_token="HBOT",
            flat_fees=[TokenAmount(token="COINALPHA", amount=Decimal("20"))]
        )

        self.assertEqual(DeductedFromReturnsTradeFee, type(fee))
        self.assertEqual(Decimal("1.1"), fee.percent)
        self.assertEqual("HBOT", fee.percent_token)
        self.assertEqual([TokenAmount(token="COINALPHA", amount=Decimal("20"))], fee.flat_fees)

        schema.percent_fee_token = None
        schema.buy_percent_fee_deducted_from_returns = True

        fee = TradeFeeBase.new_spot_fee(
            fee_schema=schema,
            trade_type=TradeType.SELL,
            percent=Decimal("1.1"),
            percent_token="HBOT",
            flat_fees=[TokenAmount(token="COINALPHA", amount=Decimal("20"))]
        )

        self.assertEqual(DeductedFromReturnsTradeFee, type(fee))

    def test_added_to_cost_perpetual_fee_created_when_opening_positions(self):

        schema = TradeFeeSchema(
            maker_percent_fee_decimal=Decimal("1"),
            taker_percent_fee_decimal=Decimal("1"),
            buy_percent_fee_deducted_from_returns=False,
        )

        fee = TradeFeeBase.new_perpetual_fee(
            fee_schema=schema,
            position_action=PositionAction.OPEN,
            percent=Decimal("1.1"),
            percent_token="HBOT",
            flat_fees=[TokenAmount(token="COINALPHA", amount=Decimal("20"))]
        )

        self.assertEqual(AddedToCostTradeFee, type(fee))
        self.assertEqual(Decimal("1.1"), fee.percent)
        self.assertEqual("HBOT", fee.percent_token)
        self.assertEqual([TokenAmount(token="COINALPHA", amount=Decimal("20"))], fee.flat_fees)

        schema.percent_fee_token = "HBOT"

        fee = TradeFeeBase.new_perpetual_fee(
            fee_schema=schema,
            position_action=PositionAction.OPEN,
            percent=Decimal("1.1"),
            percent_token="HBOT",
            flat_fees=[TokenAmount(token="COINALPHA", amount=Decimal("20"))]
        )

        self.assertEqual(AddedToCostTradeFee, type(fee))

    def test_added_to_cost_perpetual_fee_created_when_closing_position_but_schema_has_percent_fee_token(self):

        schema = TradeFeeSchema(
            percent_fee_token="HBOT",
            maker_percent_fee_decimal=Decimal("1"),
            taker_percent_fee_decimal=Decimal("1"),
            buy_percent_fee_deducted_from_returns=False,
        )

        fee = TradeFeeBase.new_perpetual_fee(
            fee_schema=schema,
            position_action=PositionAction.CLOSE,
            percent=Decimal("1.1"),
            percent_token="HBOT",
            flat_fees=[TokenAmount(token="COINALPHA", amount=Decimal("20"))]
        )

        self.assertEqual(AddedToCostTradeFee, type(fee))
        self.assertEqual(Decimal("1.1"), fee.percent)
        self.assertEqual("HBOT", fee.percent_token)
        self.assertEqual([TokenAmount(token="COINALPHA", amount=Decimal("20"))], fee.flat_fees)

    def test_deducted_from_returns_perpetual_fee_created_when_closing_position_and_no_percent_fee_token(self):

        schema = TradeFeeSchema(
            maker_percent_fee_decimal=Decimal("1"),
            taker_percent_fee_decimal=Decimal("1"),
            buy_percent_fee_deducted_from_returns=False,
        )

        fee = TradeFeeBase.new_perpetual_fee(
            fee_schema=schema,
            position_action=PositionAction.CLOSE,
            percent=Decimal("1.1"),
            percent_token="HBOT",
            flat_fees=[TokenAmount(token="COINALPHA", amount=Decimal("20"))]
        )

        self.assertEqual(DeductedFromReturnsTradeFee, type(fee))
        self.assertEqual(Decimal("1.1"), fee.percent)
        self.assertEqual("HBOT", fee.percent_token)
        self.assertEqual([TokenAmount(token="COINALPHA", amount=Decimal("20"))], fee.flat_fees)
