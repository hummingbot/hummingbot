# distutils: language=c++

import timeit
import numpy as np
from decimal import Decimal
from typing import Optional
from scipy.optimize import linprog
from hummingbot.core.event.events import TradeType
from hummingbot.strategy.triangular_arbitrage.optimizer.constraint_solver import ConstraintSolver
import logging

s_tao_logger = None
s_decimal_0 = Decimal(0.)
s_status = {
    0: "Success",
    1: "Iteration limit reached",
    2: "Problem appears to be infeasible",
    3: "Problem appears to be unbounded",
    4: "Numerical difficulties encountered",
}


_SSS = tuple([TradeType.SELL, TradeType.SELL, TradeType.SELL])
_BSS = tuple([TradeType.BUY, TradeType.SELL, TradeType.SELL])
_SSB = tuple([TradeType.SELL, TradeType.SELL, TradeType.BUY])
_BSB = tuple([TradeType.BUY, TradeType.SELL, TradeType.BUY])
_BBB = tuple([TradeType.BUY, TradeType.BUY, TradeType.BUY])
_BBS = tuple([TradeType.BUY, TradeType.BUY, TradeType.SELL])
_SBB = tuple([TradeType.SELL, TradeType.BUY, TradeType.BUY])
_SBS = tuple([TradeType.SELL, TradeType.BUY, TradeType.SELL])

cdef class Optimizer():
    def __init__(self):
        self._constraint_solver = ConstraintSolver()

    @classmethod
    def logger(cls):
        global s_tao_logger
        if s_tao_logger is None:
            s_tao_logger = logging.getLogger(__name__)
        return s_tao_logger

    def optimize(self,
                 sequence_type: str,
                 first_book: np.ndarray,
                 second_book: np.ndarray,
                 third_book: np.ndarray,
                 fee: Decimal
                 ) -> np.ndarray:

        return self.c_optimize(sequence_type, first_book, second_book, third_book, fee)

    cdef object c_optimize(self,
                           str sequence_type,
                           object first_book,
                           object second_book,
                           object third_book,
                           object fee
                           ):
        (target, constraint_1, constraint_2, bounds) = self._constraint_solver.generate_constraints(
            sequence_type, first_book, second_book, third_book, fee)

        optimized_amounts = None

        c = target
        # Solver only does minimize, invert sign to maximize
        c = Decimal(-1.)*c

        # Equality constraints
        A_eq = np.array([
            constraint_1,
            constraint_2,
        ])

        b_eq = np.array([
            0,
            0,
        ])

        try:
            startt = timeit.default_timer()
            res = linprog(c, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method="revised simplex")
            if res.success:
                fun_val = res.fun * (-1)
                self.logger().info(f"c_optimize latency: {((timeit.default_timer()-startt)*1000):.6f} ms "
                                   f"Fun: {fun_val:.6f} status: {res.status} - {s_status[res.status]} \nAmounts:\n {res.x}")
                optimized_amounts = res.x
            else:
                self.logger().error(f"c_optimize failed status: {res.status} - {s_status[res.status]}")
        except Exception as e:
            self.logger().error(f"c_optimize error: {e}")

        return optimized_amounts, fun_val
