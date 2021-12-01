import unittest
from hummingbot.strategy.triangular_arbitrage.order_tracking.order_state import OrderState


class TriangularArbitrageOrderStateTest(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()

    def test_states(self):
        unsent = OrderState.UNSENT
        self.assertTrue(unsent < OrderState.PENDING)
        self.assertTrue(unsent < OrderState.ACTIVE)
        reverse_complete = OrderState.REVERSE_COMPLETE
        self.assertTrue(reverse_complete > OrderState.REVERSE_ACTIVE)
        self.assertTrue(reverse_complete < OrderState.REVERSE_FAILED)
