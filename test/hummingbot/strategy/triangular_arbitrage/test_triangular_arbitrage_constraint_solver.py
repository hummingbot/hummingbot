
import unittest
import numpy as np
from decimal import Decimal
from hummingbot.core.data_type.order_book_row import ClientOrderBookRow
from hummingbot.strategy.triangular_arbitrage.optimizer.constraint_solver import ConstraintSolver


class TestConstraintSolver(unittest.TestCase):
    def setUp(self):
        self._solver = ConstraintSolver()
        # the constraint solver is just expecting lists of prices
        self._first_book = [
            ClientOrderBookRow(Decimal('100.8'), Decimal('0.1'), 0),
            ClientOrderBookRow(Decimal('101'), Decimal('2'), 0),
            ClientOrderBookRow(Decimal('103'), Decimal('0.2'), 0)
        ]

        self._second_book = [
            ClientOrderBookRow(Decimal('0.58'), Decimal('42'), 0),
            ClientOrderBookRow(Decimal('0.6'), Decimal('0.1'), 0),
            ClientOrderBookRow(Decimal('1'), Decimal('100'), 0)
        ]

        # note that this has four orders whereas the others have three
        self._third_book = [
            ClientOrderBookRow(Decimal('1001'), Decimal('0.1'), 0),
            ClientOrderBookRow(Decimal('1002.77'), Decimal('0.13'), 0),
            ClientOrderBookRow(Decimal('1100'), Decimal('7'), 0),
            ClientOrderBookRow(Decimal('1202'), Decimal('0.5'), 0)
        ]

        # Width of data created by constraint generator depends on the orderbook levels
        self._total_book_levels = len(self._first_book) + len(self._second_book) + len(self._third_book)

    def test_bss(self):
        constraints = self._solver.generate_constraints('BSS', self._first_book, self._second_book, self._third_book, Decimal('0.1'))
        print(f"\nbss target:\n\t{np.array(constraints.target, dtype=float)}")
        print(f"bss first corner:\n\t{np.array(constraints.first_corner, dtype=float)}")
        print(f"bss second corner:\n\t{np.array(constraints.second_corner, dtype=float)}")
        print(f"bss second bounds:\n{np.array(constraints.bounds, dtype=float)}")

        self.assertTrue(isinstance(constraints.target, np.ndarray))
        self.assertTrue(isinstance(constraints.first_corner, np.ndarray))
        self.assertTrue(isinstance(constraints.second_corner, np.ndarray))
        self.assertEqual(len(constraints.target), self._total_book_levels)
        self.assertEqual(len(constraints.first_corner), self._total_book_levels)
        self.assertEqual(len(constraints.second_corner), self._total_book_levels)

    def test_bbs(self):
        constraints = self._solver.generate_constraints('BBS', self._first_book, self._second_book, self._third_book, Decimal('0.1'))
        print(f"\nbbs target:\n\t{np.array(constraints.target, dtype=float)}")
        print(f"bbs first corner:\n\t{np.array(constraints.first_corner, dtype=float)}")
        print(f"bbs second corner:\n\t{np.array(constraints.second_corner, dtype=float)}")
        print(f"bbs second bounds:\n{np.array(constraints.bounds, dtype=float)}")

        self.assertTrue(isinstance(constraints.target, np.ndarray))
        self.assertTrue(isinstance(constraints.first_corner, np.ndarray))
        self.assertTrue(isinstance(constraints.second_corner, np.ndarray))
        self.assertEqual(len(constraints.target), self._total_book_levels)
        self.assertEqual(len(constraints.first_corner), self._total_book_levels)
        self.assertEqual(len(constraints.second_corner), self._total_book_levels)
