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
        self.assertTrue(reverse_complete >= OrderState.REVERSE_ACTIVE)
        self.assertTrue(reverse_complete <= OrderState.REVERSE_FAILED)
        self.assertTrue(reverse_complete > OrderState.REVERSE_UNSENT)
        self.assertTrue(reverse_complete > OrderState.REVERSE_PENDING)
        self.assertTrue(reverse_complete > OrderState.REVERSE_PARTIAL_TO_CANCEL)
        partial_fill = OrderState.PARTIAL_FILL
        self.assertTrue(partial_fill < OrderState.TO_CANCEL)
        self.assertTrue(partial_fill < OrderState.PENDING_CANCEL)
        self.assertTrue(partial_fill < OrderState.PENDING_PARTIAL_TO_FULL)
        hanging = OrderState.HANGING
        self.assertTrue(hanging < OrderState.COMPLETE)
        self.assertTrue(hanging < OrderState.FAILED)
