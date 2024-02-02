from unittest import TestCase

from hummingbot.connector.derivative.injective_v2_perpetual.injective_v2_perpetual_utils import InjectiveConfigMap
from hummingbot.connector.exchange.injective_v2.injective_v2_utils import (
    FEE_CALCULATOR_MODES,
    InjectiveMessageBasedTransactionFeeCalculatorMode,
    InjectiveSimulatedTransactionFeeCalculatorMode,
)


class InjectiveConfigMapTests(TestCase):

    def test_fee_calculator_validator(self):
        config = InjectiveConfigMap()

        config.fee_calculator = InjectiveSimulatedTransactionFeeCalculatorMode.Config.title
        self.assertEqual(InjectiveSimulatedTransactionFeeCalculatorMode(), config.fee_calculator)

        config.fee_calculator = InjectiveMessageBasedTransactionFeeCalculatorMode.Config.title
        self.assertEqual(InjectiveMessageBasedTransactionFeeCalculatorMode(), config.fee_calculator)

        with self.assertRaises(ValueError) as ex_context:
            config.fee_calculator = "invalid"

        self.assertEqual(
            f"Invalid fee calculator, please choose a value from {list(FEE_CALCULATOR_MODES.keys())}.",
            str(ex_context.exception.args[0][0].exc)
        )
